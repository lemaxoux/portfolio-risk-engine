"""Les séries publiées pour être tracées : rendements, richesse, histogramme.

Un graphique ne dit la vérité que s'il dessine les MÊMES points que ceux sur
lesquels les mesures ont été calculées. Ces tests vérifient donc des
RELATIONS entre ce qui est tracé et ce qui est affirmé — le creux dessiné est
le `max_drawdown` publié, les rendements comptés sont la fenêtre annoncée —
plutôt que des valeurs, qui dépendent des données.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.risk_engine.config import HISTOGRAM_BIN_WIDTH
from backend.risk_engine.measures import return_histogram

from .conftest import construire_base


def _creux(points: list[dict]) -> tuple[float, str, str]:
    """Perte pic-creux d'une liste de points, recalculée ICI, à la main.

    Volontairement indépendante de `measures.max_drawdown` : vérifier la courbe
    publiée avec la fonction qui a produit le chiffre publié ne prouverait que
    la cohérence de la fonction avec elle-même.
    """
    pic_valeur, pic_date = float("-inf"), ""
    pire, pire_pic, pire_creux = 0.0, "", ""
    for point in points:
        if point["value"] > pic_valeur:
            pic_valeur, pic_date = point["value"], point["date"]
        ecart = point["value"] / pic_valeur - 1.0
        if ecart < pire:
            pire, pire_pic, pire_creux = ecart, pic_date, point["date"]
    return pire, pire_pic, pire_creux


# ═══════════════════════════════════════════════════ Rendements et richesse ══


def test_autant_de_rendements_publies_que_d_observations(analyse_reelle):
    corps = analyse_reelle.json()
    rendements = corps["series"]["returns"]
    assert len(rendements) == corps["estimation_window"]["observations"]
    assert corps["series"]["window"] == corps["estimation_window"]
    assert rendements[0]["date"] == corps["estimation_window"]["start"]
    assert rendements[-1]["date"] == corps["estimation_window"]["end"]


def test_la_richesse_commence_au_point_de_depart_a_un(analyse_reelle):
    """Le point à 1,0 précède le premier rendement d'une séance.

    Sans lui, la courbe commence à `1 + r₁` : si le portefeuille baisse dès la
    première séance, le sommet d'où part le creux n'est pas dessiné.
    """
    serie = analyse_reelle.json()["series"]
    richesse, rendements = serie["wealth"], serie["returns"]

    assert richesse[0]["value"] == 1.0
    assert len(richesse) == len(rendements) + 1
    assert richesse[0]["date"] < rendements[0]["date"]
    assert [p["date"] for p in richesse[1:]] == [p["date"] for p in rendements]


def test_la_richesse_est_le_cumul_des_rendements_publies(analyse_reelle):
    """Les deux séries publiées décrivent le même portefeuille, point à point."""
    serie = analyse_reelle.json()["series"]
    richesse = [p["value"] for p in serie["wealth"]]
    rendements = [p["value"] for p in serie["returns"]]
    attendu = np.cumprod([1.0] + [1.0 + r for r in rendements])
    assert richesse == pytest.approx(list(attendu), rel=1e-12)


def test_le_creux_recalcule_sur_la_courbe_publiee_est_le_drawdown_publie(
    analyse_reelle,
):
    """Le creux que le graphique DESSINE est celui que la mesure AFFIRME."""
    corps = analyse_reelle.json()
    publie = corps["risk"]["drawdown"]

    valeur, pic, creux = _creux(corps["series"]["wealth"])

    assert valeur == pytest.approx(publie["value"], rel=1e-12)
    assert pic == publie["peak_date"]
    assert creux == publie["trough_date"]


def test_pic_et_creux_tombent_sur_des_points_de_la_courbe(analyse_reelle):
    """Les annotations se posent SUR la courbe (§9.4) : leurs dates doivent en
    être des points, et le rapport de leurs niveaux est le drawdown publié."""
    corps = analyse_reelle.json()
    publie = corps["risk"]["drawdown"]
    niveaux = {p["date"]: p["value"] for p in corps["series"]["wealth"]}

    assert publie["peak_date"] in niveaux
    assert publie["trough_date"] in niveaux
    assert niveaux[publie["trough_date"]] / niveaux[publie["peak_date"]] - 1.0 == (
        pytest.approx(publie["value"], rel=1e-12)
    )


@pytest.fixture
def client_baisse_immediate(tmp_path, client_factory):
    """Un titre qui perd 10 % dès la première séance de la fenêtre, puis remonte.

    Le cas exact que le point de départ existe pour couvrir : le sommet d'où
    part le creux est la séance qui PRÉCÈDE le premier rendement.
    """
    seances = 80
    generateur = np.random.default_rng(7)
    # Après la chute, des hausses seulement, mais inégales : aucun creux plus
    # profond ne peut apparaître, et la série n'est pas dégénérée pour
    # l'ajustement de Student.
    hausses = 1.0 + generateur.uniform(0.001, 0.004, seances - 2)
    prix = [100.0] + [float(v) for v in 90.0 * np.cumprod(np.r_[1.0, hausses])]
    marche = [float(v) for v in 400.0 * np.cumprod(1.0 + generateur.normal(0.0004, 0.009, seances))]
    chemin = construire_base(
        tmp_path / "baisse.sqlite",
        {"BAISSE": ("Baisse Inc", "Energy", prix), "SPY": ("S&P 500 ETF", None, marche)},
        seances,
    )
    with client_factory(chemin) as client:
        identifiant = client.post("/api/portfolios", json={}).json()["id"]
        client.put(
            f"/api/portfolios/{identifiant}/positions",
            json={"positions": [{"ticker": "BAISSE", "quantity": 10}]},
        )
        yield client, identifiant


def test_sans_le_point_de_depart_le_creux_dessine_serait_faux(client_baisse_immediate):
    client, identifiant = client_baisse_immediate
    corps = client.get(f"/api/portfolios/{identifiant}/analysis?window=504").json()
    serie = corps["series"]
    publie = corps["risk"]["drawdown"]

    # Le creux part du point de départ, pas du premier rendement.
    assert publie["peak_date"] == serie["wealth"][0]["date"]
    assert publie["value"] == pytest.approx(-0.10, abs=1e-12)
    assert _creux(serie["wealth"])[0] == pytest.approx(publie["value"], rel=1e-12)

    # Tracée sans lui, la courbe ne montrerait AUCUN creux de 10 % : elle
    # commencerait au creux lui-même.
    assert _creux(serie["wealth"][1:])[0] > -0.10 + 1e-9


# ═══════════════════════════════════════════════════════════ Histogramme ══


def _classe_de(rendement: float, classes: list[dict]) -> list[dict]:
    """Les classes publiées qui contiennent ce rendement, selon `closed: left`."""
    return [c for c in classes if c["lower"] <= rendement < c["upper"]]


def test_chaque_rendement_publie_tombe_dans_exactement_une_classe(analyse_reelle):
    """Vérifié avec les bornes PUBLIÉES et la convention publiée : un lecteur
    qui recompte à partir de la réponse retombe sur les mêmes classes."""
    corps = analyse_reelle.json()
    histogramme = corps["histogram"]
    assert histogramme["closed"] == "left"

    for point in corps["series"]["returns"]:
        assert len(_classe_de(point["value"], histogramme["bins"])) == 1, point

    recompte = [
        len([p for p in corps["series"]["returns"] if c["lower"] <= p["value"] < c["upper"]])
        for c in histogramme["bins"]
    ]
    assert recompte == [c["count"] for c in histogramme["bins"]]


def test_la_somme_des_classes_est_la_fenetre(analyse_reelle):
    corps = analyse_reelle.json()
    total = sum(c["count"] for c in corps["histogram"]["bins"])
    assert total == corps["estimation_window"]["observations"]
    assert corps["histogram"]["window"] == corps["estimation_window"]


def test_zero_est_une_borne_et_toutes_les_bornes_sont_des_multiples(analyse_reelle):
    histogramme = analyse_reelle.json()["histogram"]
    largeur = histogramme["bin_width"]
    bornes = [c["lower"] for c in histogramme["bins"]] + [histogramme["bins"][-1]["upper"]]

    assert 0.0 in bornes
    for borne in bornes:
        assert borne / largeur == pytest.approx(round(borne / largeur), abs=1e-9)
    for gauche, droite in zip(histogramme["bins"], histogramme["bins"][1:]):
        assert gauche["upper"] == droite["lower"]
        assert droite["upper"] - droite["lower"] == pytest.approx(largeur, abs=1e-12)


def test_deux_portefeuilles_se_lisent_sur_la_meme_grille(
    analyse_reelle, client_synthetique, portefeuille_synthetique
):
    """Même largeur, mêmes bornes possibles, quelle que soit la dispersion."""
    reel = analyse_reelle.json()["histogram"]
    synthetique = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["histogram"]

    assert reel["bin_width"] == synthetique["bin_width"] == HISTOGRAM_BIN_WIDTH
    bornes_reelles = {c["lower"] for c in reel["bins"]}
    bornes_synthetiques = {c["lower"] for c in synthetique["bins"]}
    # Deux grilles alignées partagent leurs bornes là où elles se recouvrent.
    communes = bornes_reelles & bornes_synthetiques
    assert 0.0 in communes and len(communes) > 5


def test_un_rendement_egal_a_une_borne_va_dans_la_classe_qui_y_commence():
    histogramme = return_histogram([0.0, 0.005, -0.0025, 0.0075], bin_width=0.0025)
    par_borne = {c.lower: c.count for c in histogramme.bins}
    assert par_borne[0.0] == 1  # 0 est dans [0 ; 0,25 %), pas dans [−0,25 % ; 0)
    assert par_borne[0.005] == 1
    assert par_borne[-0.0025] == 1
    # 0,0075 n'est pas représentable : la borne est rendue arrondie, et le
    # rendement est rangé contre elle — pas contre 3 × 0,0025 en binaire.
    assert par_borne[0.0075] == 1
    assert histogramme.observations == 4


def test_les_classes_vides_entre_deux_extremes_sont_publiees():
    """Sauter les classes vides rapprocherait à l'œil la séance extrême du reste."""
    histogramme = return_histogram([0.001, 0.0012, 0.0213], bin_width=0.0025)
    assert [c.count for c in histogramme.bins] == [2, 0, 0, 0, 0, 0, 0, 0, 1]
    assert histogramme.bins[0].lower == 0.0


def test_zero_reste_une_borne_quand_toutes_les_seances_ont_le_meme_signe():
    positives = return_histogram([0.011, 0.012], bin_width=0.0025)
    assert positives.bins[0].lower == 0.0 and positives.bins[0].count == 0
    negatives = return_histogram([-0.011, -0.012], bin_width=0.0025)
    assert negatives.bins[-1].upper == 0.0 and negatives.bins[-1].count == 0


def test_la_largeur_ne_depend_pas_des_donnees():
    calme = return_histogram(np.random.default_rng(1).normal(0, 0.004, 500))
    agite = return_histogram(np.random.default_rng(2).normal(0, 0.03, 500))
    assert calme.bin_width == agite.bin_width == HISTOGRAM_BIN_WIDTH
    assert len(agite.bins) > 3 * len(calme.bins)


def test_une_largeur_non_positive_ou_une_serie_vide_sont_refusees():
    with pytest.raises(ValueError, match="non positive"):
        return_histogram([0.01], bin_width=0.0)
    with pytest.raises(ValueError, match="vide"):
        return_histogram([], bin_width=0.0025)
