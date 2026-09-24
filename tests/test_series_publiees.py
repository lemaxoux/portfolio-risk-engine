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
