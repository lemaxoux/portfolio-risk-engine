"""`/analysis` — ce que la sérialisation ne doit jamais perdre en route.

Cette phase ne calcule rien : elle publie. Les pannes qu'elle peut produire sont
donc toutes des pannes SILENCIEUSES — un champ disparu, un `null` sans raison,
une étiquette décalée d'un cran, un NaN écrit tel quel dans le corps. Aucune ne
lève d'exception, toutes produisent une réponse d'apparence normale. Ces tests
existent pour qu'elles fassent du bruit.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from backend.typography import MINUS, NARROW_NBSP, NBSP

from backend.db.init_db import connect
from backend.risk_engine.engine import analyse_portfolio

from .conftest import construire_base
from .gardes_texte import ESPACE_AVANT_MOT, ESPACE_AVANT_POURCENT, toutes_les_chaines


def interdit(constante: str):
    raise AssertionError(f"constante JSON non standard dans la réponse : {constante}")


def objets(noeud, cle: str):
    """Tous les dictionnaires de la réponse qui portent la clé `cle`."""
    trouves = []
    if isinstance(noeud, dict):
        if cle in noeud:
            trouves.append(noeud)
        for valeur in noeud.values():
            trouves.extend(objets(valeur, cle))
    elif isinstance(noeud, list):
        for element in noeud:
            trouves.extend(objets(element, cle))
    return trouves


# ═════════════════════════════════════ 1. Les octets sont du JSON standard ══


def test_les_octets_bruts_se_parsent_avec_un_analyseur_strict(analyse_reelle):
    """NaN et Infinity ne sont pas du JSON.

    `json.dumps` les écrit tels quels et `JSON.parse` plante dessus côté
    navigateur. La vérification porte sur les OCTETS de la réponse, pas sur un
    dictionnaire Python : un `float('nan')` inspecté en Python est un flottant
    parfaitement valide, et un test écrit sur le dict ne verrait rien.
    """
    json.loads(analyse_reelle.content, parse_constant=interdit)


def test_aucune_constante_non_standard_dans_le_texte_de_la_reponse(analyse_reelle):
    """Deuxième garde, sur le texte : `parse_constant` ne se déclenche que si
    l'analyseur rencontre le jeton, et un jeton mal placé pourrait échouer
    autrement."""
    texte = analyse_reelle.content.decode("utf-8")
    for jeton in ("NaN", "Infinity", "-Infinity"):
        assert f":{jeton}" not in texte.replace(" ", "")


# ══════════════════════════════════════════ 2. La provenance survit au JSON ══


CHEMINS_AVEC_FENETRE = (
    ("risk", "volatility"),
    ("risk", "ewma_volatility"),
    ("risk", "parametric_volatility"),
    ("risk", "drawdown"),
    ("risk", "sharpe"),
    ("risk", "sortino"),
    ("risk", "matrices"),
    ("risk", "variance_contributions"),
    ("risk", "beta"),
)


def test_chaque_mesure_estimee_porte_sa_fenetre_complete(analyse_reelle):
    """`observations`, `start`, `end` — un chiffre de risque sans sa fenêtre
    n'est pas interprétable."""
    corps = analyse_reelle.json()
    for chemin in CHEMINS_AVEC_FENETRE:
        noeud = corps
        for segment in chemin:
            noeud = noeud[segment]
        fenetre = noeud["window"]
        assert fenetre["observations"] == 504, chemin
        assert fenetre["start"] == "2024-09-05", chemin
        assert fenetre["end"] == "2026-09-09", chemin
        assert fenetre["requested"] == 504, chemin
        assert fenetre["complete"] is True, chemin


def test_toute_fenetre_publiee_est_complete_ou_ne_l_est_pas_mais_le_dit(
    analyse_reelle,
):
    """Aucune fenêtre tronquée à trois champs quelque part dans la réponse."""
    attendus = {"requested", "observations", "start", "end", "complete"}
    # `parameters.window` est un ENTIER — la fenêtre demandée, pas une fenêtre
    # effective. Seuls les objets fenêtre sont concernés.
    fenetres = [
        noeud
        for noeud in objets(analyse_reelle.json(), "window")
        if isinstance(noeud["window"], dict)
    ]
    assert len(fenetres) >= 9
    for noeud in fenetres:
        assert set(noeud["window"]) == attendus


def test_chaque_mesure_porte_sa_methode(analyse_reelle):
    risque = analyse_reelle.json()["risk"]
    assert "écart-type" in risque["volatility"]["method"]
    assert "EWMA" in risque["ewma_volatility"]["method"]
    assert "covariance" in risque["parametric_volatility"]["method"]

    methodes = {
        niveau[champ]["method"]
        for niveau in risque["tail_risk"]["levels"]
        for champ in ("historical_var", "parametric_var", "monte_carlo_var")
    }
    assert methodes == {"historique", "paramétrique", "Monte Carlo"}


def test_nu_accompagne_les_var_de_student_et_seulement_elles(analyse_reelle):
    """`nu` est une donnée du résultat, pas une mention noyée dans `detail`."""
    for niveau in analyse_reelle.json()["risk"]["tail_risk"]["levels"]:
        assert niveau["historical_var"]["nu"] is None
        assert niveau["parametric_var"]["nu"] is None
        assert niveau["monte_carlo_var"]["nu"] is None
        assert niveau["student_parametric_var"]["nu"] > 2.0
        assert niveau["student_monte_carlo_var"]["nu"] > 2.0


def test_aucune_fenetre_n_est_hissee_en_tete_de_reponse(analyse_reelle):
    """Chaque mesure garde SA fenêtre.

    Le beta est régressé sous une contrainte d'échantillon minimal qui lui est
    propre, et un scénario à couverture partielle a sa propre portée : une
    fenêtre au niveau du document serait fausse pour toute mesure qui n'utilise
    pas celle-là. Seule la fenêtre DEMANDÉE figure en tête, sous `parameters`,
    et elle est nommée comme telle.

    `estimation_window` n'est pas une contre-exemple : ce n'est pas la fenêtre
    d'une mesure hissée, c'est celle du PANEL, publiée sous son propre nom. Le
    test qui suit dit ce qu'elle est.
    """
    corps = analyse_reelle.json()
    assert "window" not in corps
    assert "window" not in corps["risk"]
    assert corps["parameters"]["window"] == 504


def test_la_fenetre_du_panel_est_publiee_sous_son_propre_nom(analyse_reelle):
    """`estimation_window` est `PortfolioSeries.window`, pas une mesure promue.

    Sans ce champ, un client qui veut afficher la fenêtre du régime courant en
    tête de page n'a que deux options, toutes deux mauvaises : lire
    `parameters.window`, qui est le DEMANDÉ et vaudrait 504 alors que le calcul
    a tourné sur 40 ; ou lire `risk.volatility.window`, ce qui promeut une
    mesure particulière en fenêtre du document par convention silencieuse — la
    convention se trouve juste aujourd'hui, et rien ne la garantit demain.

    Le champ porte donc le nom de l'objet du moteur, et il a la forme complète
    d'une fenêtre : `objets(corps, "window")` ne le voit pas, puisque sa clé
    n'est pas « window ».
    """
    corps = analyse_reelle.json()
    panel = corps["estimation_window"]
    assert set(panel) == {"requested", "observations", "start", "end", "complete"}
    assert panel["observations"] == 504
    assert panel["requested"] == 504
    assert panel["start"] == "2024-09-05"
    assert panel["end"] == "2026-09-09"
    assert panel["complete"] is True

    # Les mesures calculées sur ce panel la partagent — c'est ce qui rend le
    # champ publiable. Le beta de crise, lui, n'a pas de `window` du tout.
    assert corps["risk"]["volatility"]["window"] == panel
    assert corps["risk"]["tail_risk"]["levels"][0]["historical_var"]["window"] == panel


def test_la_fenetre_du_panel_suit_l_historique_reel_pas_la_demande(
    analyse_historique_court,
):
    """Une ligne cotée depuis peu la fait tomber, sans qu'aucun paramètre change.

    C'est la raison d'être du champ : `parameters.window` dirait encore 504. Un
    bandeau qui lirait le demandé annoncerait une profondeur d'historique que le
    calcul n'a jamais eue.
    """
    corps = analyse_historique_court(40).json()
    panel = corps["estimation_window"]
    assert corps["parameters"]["window"] == 504
    assert panel["requested"] == 504
    assert panel["observations"] == 39
    assert panel["complete"] is False
    assert [p["ticker"] for p in corps["limiting_positions"]] == ["COURT"]


def test_le_beta_regresse_de_crise_porte_ses_propres_observations(analyse_reelle):
    """Il ne porte PAS de `window` : le moteur ne lui en attache pas, et en
    fabriquer une inventerait une fenêtre « demandée » qui ne l'a jamais été."""
    crise = analyse_reelle.json()["regimes"][1]["crisis_beta"]
    assert "window" not in crise
    assert crise["observations"] > 0
    assert crise["start"] < crise["end"]
    assert crise["min_observations"] == 60
    # Le krach COVID tient en 23 séances : l'échantillon est trop mince et la
    # réponse doit le dire plutôt que de présenter la pente comme solide.
    assert crise["sample_too_thin"] is True


# ═══════════════════════════ 3. Un indéfini se dit, il ne s'efface pas ══


@pytest.fixture
def client_monotone(tmp_path, client_factory):
    """Un portefeuille qui ne baisse jamais : le Sortino y est indéfini.

    Aucune observation sous la cible, donc déviation à la baisse nulle, donc
    ratio indéfini — pas infini, pas nul.
    """
    # Hausse à taux VARIABLE : un taux constant rendrait aussi le Sharpe
    # indéfini (écart-type nul), et le moteur refuserait tout le rapport avant
    # même d'arriver au Sortino. Ce qu'on veut isoler ici, c'est la seule
    # absence de rendement SOUS LA CIBLE.
    taux = [0.0004, 0.0021, 0.0009, 0.0035, 0.0012]
    hausse = [100.0]
    for jour in range(199):
        hausse.append(hausse[-1] * (1.0 + taux[jour % len(taux)]))
    marche = [400.0]
    for jour in range(199):
        marche.append(marche[-1] * (1.0008 if jour % 2 else 0.9995))

    chemin = construire_base(
        tmp_path / "monotone.sqlite",
        {
            "UPUP": ("Toujours en hausse", "Utilities", hausse),
            "SPY": ("S&P 500 ETF", None, marche),
        },
        200,
    )
    with client_factory(chemin) as client:
        yield client


def test_un_sortino_indefini_ressort_null_avec_sa_raison(client_monotone):
    """Ni absent, ni zéro.

    Zéro se lirait « ratio nul », donc un portefeuille sans excédent de
    rendement — l'inverse exact de ce qui se passe ici. C'est la raison pour
    laquelle `response_model_exclude_none` est banni : il supprimerait
    précisément le champ qui explique le blanc.
    """
    identifiant = client_monotone.post("/api/portfolios", json={}).json()["id"]
    client_monotone.put(
        f"/api/portfolios/{identifiant}/positions",
        json={"positions": [{"ticker": "UPUP", "quantity": 10}]},
    )
    reponse = client_monotone.get(f"/api/portfolios/{identifiant}/analysis?window=150")
    assert reponse.status_code == 200, reponse.text

    sortino = reponse.json()["risk"]["sortino"]
    assert "annualised" in sortino
    assert sortino["annualised"] is None
    assert "aucun rendement sous la cible" in sortino["undefined_reason"]
    # Le reste du résultat est bien là : l'indéfinition d'un ratio n'efface pas
    # la déviation qui l'a produite.
    assert sortino["downside_deviation_daily"] == 0.0
    assert sortino["target_daily"] == 0.0


def test_un_sortino_defini_ne_porte_pas_de_raison_d_indefinition(analyse_reelle):
    sortino = analyse_reelle.json()["risk"]["sortino"]
    assert sortino["annualised"] is not None
    assert sortino["undefined_reason"] is None


# ══════════════════════ 4. Les étiquettes des matrices suivent les valeurs ══


def test_l_ordre_des_tickers_de_la_matrice_correspond_aux_valeurs(
    client_synthetique, portefeuille_synthetique, base_synthetique
):
    """Construit sur des tickers dont l'ordre alphabétique DIFFÈRE de l'ordre
    des poids, sinon le test passerait par accident.

    ALFA/MIKE/ZULU en alphabétique ; MIKE/ZULU/ALFA en poids décroissants ;
    ZULU/ALFA/MIKE à l'insertion. Trois ordres distincts : une liste d'étiquettes
    prise à la mauvaise source se verrait.
    """
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()

    matrice = corps["risk"]["matrices"]["correlation"]
    conn = connect(base_synthetique)
    reference = analyse_portfolio(
        conn, portefeuille_synthetique, window=250
    ).matrices.correlation
    conn.close()

    # Chaque cellule publiée est relue dans la matrice du moteur PAR SON COUPLE
    # D'ÉTIQUETTES : une permutation des libellés ferait échouer la comparaison.
    for i, ligne in enumerate(matrice["tickers"]):
        for j, colonne in enumerate(matrice["tickers"]):
            assert matrice["values"][i][j] == pytest.approx(
                float(reference.at[ligne, colonne])
            ), (ligne, colonne)


def test_la_structure_de_correlation_est_reconnaissable_dans_les_etiquettes(
    client_synthetique, portefeuille_synthetique
):
    """Contrôle sémantique, indépendant du moteur.

    ALFA et ZULU partagent un facteur commun, MIKE est indépendant. Si les
    étiquettes et les valeurs se désalignaient, la matrice resterait symétrique
    et de diagonale 1 — donc plausible — mais la paire fortement corrélée
    changerait de nom.
    """
    matrice = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["risk"]["matrices"]["correlation"]

    position = {t: i for i, t in enumerate(matrice["tickers"])}
    valeur = lambda a, b: matrice["values"][position[a]][position[b]]

    assert valeur("ALFA", "ZULU") > 0.8
    assert abs(valeur("ALFA", "MIKE")) < 0.2
    assert abs(valeur("MIKE", "ZULU")) < 0.2
    for ticker in matrice["tickers"]:
        assert valeur(ticker, ticker) == pytest.approx(1.0)


def test_la_meme_liste_de_tickers_gouverne_les_poids_et_les_matrices(
    client_synthetique, portefeuille_synthetique
):
    """Une carte de chaleur et une barre de poids ne doivent pas pouvoir
    s'étiqueter différemment."""
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()

    canonique = corps["tickers"]
    assert [w["ticker"] for w in corps["weights"]] == canonique
    assert corps["risk"]["matrices"]["correlation"]["tickers"] == canonique
    assert corps["risk"]["matrices"]["covariance"]["tickers"] == canonique
    assert corps["risk"]["variance_contributions"]["tickers"] == canonique
    assert [
        c["ticker"] for c in corps["risk"]["variance_contributions"]["contributions"]
    ] == canonique


def test_les_matrices_sont_carrees_et_de_la_taille_du_portefeuille(
    client_synthetique, portefeuille_synthetique
):
    matrices = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["risk"]["matrices"]
    for nom in ("correlation", "covariance"):
        matrice = matrices[nom]
        assert len(matrice["tickers"]) == 3
        assert len(matrice["values"]) == 3
        assert all(len(ligne) == 3 for ligne in matrice["values"])


# ═══════════════════════════════ 5. Les seuils disent d'où ils viennent ══


def test_chaque_seuil_porte_son_kind_machine(analyse_reelle):
    """Le client distingue un seuil choisi d'un seuil dérivé sans chercher le
    mot « choisi » dans du texte français."""
    seuils = [
        seuil
        for observation in analyse_reelle.json()["observations"]
        for seuil in observation["thresholds"]
    ]
    assert seuils
    assert {s["kind"] for s in seuils} == {
        "chosen",
        "derived",
        "portfolio_relative",
    }
    for seuil in seuils:
        assert seuil["chosen"] is (seuil["kind"] == "chosen")
        assert seuil["rationale"]
        assert seuil["rendered"]
        assert isinstance(seuil["value"], (int, float))


def test_chaque_seuil_dit_s_il_est_un_seuil_ou_une_reference(analyse_reelle):
    """`role`, champ machine : le client écrit « Seuil » ou « Référence » sans
    déduire l'un de l'autre à partir de `kind`, qui ne suffit pas."""
    observations = analyse_reelle.json()["observations"]
    for observation in observations:
        for seuil in observation["thresholds"]:
            assert seuil["role"] in ("threshold", "reference")
            if seuil["kind"] == "chosen":
                assert seuil["role"] == "threshold"
            if seuil["kind"] == "portfolio_relative":
                assert seuil["role"] == "reference"

    (diversification,) = [
        o for o in observations if o["rule"] == "apparent_diversification"
    ]
    assert [s["role"] for s in diversification["thresholds"]] == [
        "threshold",
        "reference",
    ]
    # La paire porte le caractère de liaison (U+2060) qui l'empêche de se
    # couper au tiret, posé à la publication.
    assert "Référence\u00a0: corrélation JNJ–\u2060KO" in diversification["rendered"]
    for contribution in (o for o in observations if o["rule"] == "variance_contribution"):
        assert contribution["thresholds"][0]["role"] == "reference"


def test_un_meme_nombre_a_la_meme_forme_dans_la_phrase_et_la_ligne_de_seuil(
    analyse_reelle,
):
    (diversification,) = [
        o
        for o in analyse_reelle.json()["observations"]
        if o["rule"] == "apparent_diversification"
    ]
    seuil, paire = diversification["thresholds"]

    assert "aucune corrélation n'atteint 0,70." in diversification["statement"]
    assert seuil["rendered"].startswith(
        "corrélation forte = 0,70, choisi à la main (non dérivé des données). "
    )
    # « corrélation JNJ–KO = 0,42, calculée sur ce portefeuille. … » : la
    # valeur s'arrête à la virgule qui précède la provenance.
    rho = paire["rendered"].split(" = ")[1].split(", ")[0]
    assert f"à {rho}." in diversification["statement"]


def test_un_seuil_choisi_le_dit_dans_le_champ_et_dans_le_texte(analyse_reelle):
    choisis = [
        seuil
        for observation in analyse_reelle.json()["observations"]
        for seuil in observation["thresholds"]
        if seuil["kind"] == "chosen"
    ]
    assert choisis
    for seuil in choisis:
        assert "choisi à la main (non dérivé des données)" in seuil["rendered"]


def test_une_observation_sans_seuil_a_une_liste_vide_et_non_un_null(analyse_reelle):
    """« Aucun seuil » est une décision du moteur de règles, pas un oubli."""
    sans_seuil = [
        o for o in analyse_reelle.json()["observations"] if not o["thresholds"]
    ]
    assert sans_seuil
    for observation in sans_seuil:
        assert observation["thresholds"] == []
        assert observation["uses_chosen_threshold"] is False


def test_les_observations_portent_un_identifiant_machine_et_un_libelle(
    analyse_reelle,
):
    observations = analyse_reelle.json()["observations"]
    assert len(observations) >= 6
    regles = {o["rule"] for o in observations}
    assert "effective_concentration" in regles
    assert "variance_contribution" in regles
    for observation in observations:
        assert observation["rule"].islower()
        assert observation["rule_label"]
        assert observation["statement"]
        assert observation["provenance"]
        assert observation["rendered"]


# ══════════════════ 6. Les propriétés du moteur sont dans la réponse ══


def test_prediction_gap_et_systematic_share_change_sont_publies(analyse_reelle):
    """Deux `@property` qu'un `asdict()` aurait perdues sans lever.

    `prediction_gap` est décrit dans la docstring du moteur comme « le
    livrable » de la comparaison de régimes : une API d'où il serait absent
    publierait la section sans son résultat.
    """
    regimes = analyse_reelle.json()["regimes"]
    assert len(regimes) == 3
    for regime in regimes:
        assert "prediction_gap" in regime
        assert "systematic_share_change" in regime
        assert "ratio_beta_divergence" in regime

    calculables = [r for r in regimes if r["unavailable_reason"] is None]
    assert calculables
    for regime in calculables:
        assert regime["prediction_gap"] is not None
        assert regime["systematic_share_change"] is not None
        assert regime["crisis_beta"] is not None
        assert regime["calm_beta"] is not None
        assert regime["summary"]


def test_l_avertissement_permanent_du_cvar_a_99_est_publie(analyse_reelle):
    """`caveat` est une propriété, allumée en permanence à 99 % : à ce niveau la
    queue ne compte que 1 % de la fenêtre. Ce n'est pas une anomalie, c'est la
    structure du chiffre."""
    niveaux = {
        n["confidence"]: n for n in analyse_reelle.json()["risk"]["tail_risk"]["levels"]
    }
    assert niveaux[0.95]["expected_shortfall"]["caveat"] is None
    caveat = niveaux[0.99]["expected_shortfall"]["caveat"]
    assert caveat is not None
    assert "jours de bourse seulement" in caveat
    assert niveaux[0.99]["expected_shortfall"]["tail_observations"] > 0


def test_les_proprietes_derivees_des_contributions_sont_publiees(analyse_reelle):
    contributions = analyse_reelle.json()["risk"]["variance_contributions"]
    assert "effective_positions" in contributions
    assert "has_negative_contribution" in contributions
    for ligne in contributions["contributions"]:
        assert "excess_over_weight" in ligne
        assert ligne["excess_over_weight"] == pytest.approx(
            ligne["contribution"] - ligne["weight"]
        )


def test_le_beta_publie_sa_part_idiosyncratique(analyse_reelle):
    beta = analyse_reelle.json()["risk"]["beta"]
    assert beta["idiosyncratic_share"] == pytest.approx(1.0 - beta["r_squared"])


def test_les_contributions_de_scenario_publient_pnl_et_derive_de_poids(
    analyse_reelle,
):
    contributions = analyse_reelle.json()["scenarios"][0]["contributions"]
    assert contributions
    for ligne in contributions:
        assert ligne["pnl"] == pytest.approx(
            ligne["end_value"] - ligne["start_value"]
        )
        assert ligne["weight_drift"] == pytest.approx(
            ligne["end_weight"] - ligne["start_weight"]
        )


# ═══════════════════════════ 7. Un scénario, trois chiffres indissociables ══


def test_un_scenario_publie_toujours_ses_trois_chiffres(analyse_reelle):
    """Sortie, pire moment traversé, et portée : jamais l'un sans les autres.

    Le pire moment est souvent plus profond que la sortie — publier la sortie
    seule laisserait croire que la baisse s'est arrêtée là.
    """
    for scenario in analyse_reelle.json()["scenarios"]:
        assert "end_to_end_return" in scenario
        assert "max_drawdown" in scenario
        assert "value_share" in scenario["coverage"]

        if scenario["end_to_end_return"] is None:
            assert scenario["max_drawdown"] is None
            assert scenario["unavailable_reason"]
        else:
            assert scenario["max_drawdown"] is not None
            # Le creux traversé est au moins aussi profond que la sortie.
            assert scenario["max_drawdown"]["value"] <= scenario["end_to_end_return"]
            assert 0.0 <= scenario["coverage"]["value_share"] <= 1.0


def test_un_scenario_non_calculable_dit_pourquoi_sans_fabriquer_de_chiffre(
    client_synthetique, portefeuille_synthetique
):
    """La base synthétique commence en 2024 : aucune ligne n'a traversé 2008.

    Les deux chiffres valent `null` ENSEMBLE, avec la raison. En fabriquer un
    serait pire que de n'en donner aucun.
    """
    scenarios = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["scenarios"]

    assert len(scenarios) == 3
    for scenario in scenarios:
        assert scenario["end_to_end_return"] is None
        assert scenario["max_drawdown"] is None
        assert "Aucune de vos lignes" in scenario["unavailable_reason"]
        assert scenario["coverage"]["value_share"] == 0.0
        assert scenario["summary"]


def test_la_couverture_publie_ses_parts_et_ses_exclusions(analyse_reelle):
    for scenario in analyse_reelle.json()["scenarios"]:
        couverture = scenario["coverage"]
        assert set(couverture) == {
            "covered",
            "excluded",
            "covered_value",
            "total_value",
            "value_share",
            "is_complete",
            "covered_count",
            "total_count",
        }


# ═══════════════════════════════════ 8. Des fractions, jamais des pourcents ══


def test_les_valeurs_restent_des_fractions(analyse_reelle):
    """Une VaR de 1,38 % se sérialise 0.0138.

    Le formatage — pourcentage, virgule décimale, arrondi — est décidé à un seul
    endroit, côté frontend. Deux conventions dans un même produit finiraient par
    se croiser.
    """
    corps = analyse_reelle.json()
    assert 0.0 < corps["risk"]["volatility"]["annualised"] < 1.0
    assert 0.0 < corps["risk"]["tail_risk"]["levels"][0]["historical_var"]["value"] < 0.2
    assert sum(w["weight"] for w in corps["weights"]) == pytest.approx(1.0)
    assert 0.0 < corps["risk"]["concentration"]["hhi"] < 1.0


def test_aucune_valeur_numerique_n_est_une_chaine_formatee(analyse_reelle):
    """Un « 1,38 % » publié comme chaîne serait un formatage déguisé en donnée."""
    risque = analyse_reelle.json()["risk"]
    for mesure in ("volatility", "ewma_volatility", "parametric_volatility"):
        assert isinstance(risque[mesure]["annualised"], float)
    assert isinstance(risque["drawdown"]["value"], float)
    assert isinstance(risque["sharpe"]["annualised"], float)


def test_les_dates_sont_en_iso(analyse_reelle):
    corps = analyse_reelle.json()
    assert corps["as_of"] == "2026-09-09"
    assert corps["risk"]["concentration"]["as_of"] == "2026-09-09"
    assert corps["risk"]["sharpe"]["risk_free_observed_on"] == "2026-09-09"


# ═══════════════════════════════════════════════ 9. Le volet Student ══


def test_la_var_normale_et_la_var_student_voyagent_ensemble(analyse_reelle):
    """L'écart entre les deux chiffre le coût de l'hypothèse de normalité.

    À 99 %, le quantile est déjà dans la queue : la Student y est plus sévère
    que la normale. Publier la normale seule la ferait passer pour le dernier
    mot.
    """
    niveaux = {
        n["confidence"]: n for n in analyse_reelle.json()["risk"]["tail_risk"]["levels"]
    }
    haut = niveaux[0.99]
    assert haut["student_parametric_var"]["value"] > haut["parametric_var"]["value"]
    assert analyse_reelle.json()["risk"]["tail_risk"]["student_fit"]["nu"] > 2.0
    assert (
        analyse_reelle.json()["risk"]["tail_risk"]["student_unavailable_reason"] is None
    )


def test_un_volet_student_indisponible_sort_null_avec_la_raison_du_moteur(
    client_synthetique, portefeuille_synthetique, monkeypatch
):
    """Une erreur imprévue des simulations ne doit pas emporter tout le rapport.

    Le moteur absorbe lui-même les refus qu'il connaît — volet Student, dont
    ν ≤ 2, et Monte Carlo normal sur une covariance singulière — et en range
    les raisons dans le rapport. Ce test simule une `ValueError` qu'il n'aurait
    PAS prévue, levée seulement quand les simulations sont demandées : le filet
    de la route sert alors le rapport sans simulations, et relaie le message
    MOT POUR MOT comme raison. Jamais un blanc sans raison.
    """
    from backend.api.routes import analysis as module

    reel = module.analyse_portfolio
    message = (
        "Erreur imprévue dans les simulations\u00a0: aucun tirage n'a pu être "
        "produit."
    )

    def faux(conn, portfolio_id, *, monte_carlo=False, **reste):
        if monte_carlo:
            raise ValueError(message)
        return reel(conn, portfolio_id, monte_carlo=False, **reste)

    monkeypatch.setattr(module, "analyse_portfolio", faux)

    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    )
    assert reponse.status_code == 200, reponse.text
    queue = reponse.json()["risk"]["tail_risk"]

    assert queue["student_fit"] is None
    assert queue["student_unavailable_reason"] == message
    for niveau in queue["levels"]:
        assert niveau["student_parametric_var"] is None
        assert niveau["student_monte_carlo_var"] is None
        assert niveau["monte_carlo_var"] is None
        # Le reste du rapport est servi : le refus d'un volet n'est pas le refus
        # de la page.
        assert niveau["historical_var"]["value"] is not None
        assert niveau["parametric_var"]["value"] is not None
        assert niveau["expected_shortfall"]["value"] is not None


def test_le_filet_de_la_route_donne_aussi_sa_raison_au_monte_carlo(
    client_synthetique, portefeuille_synthetique, monkeypatch
):
    """Sur le filet, les deux volets manquent pour la même cause : chacun la
    porte. Un Monte Carlo à `null` sans raison serait un blanc inexpliqué."""
    from backend.api.routes import analysis as module

    reel = module.analyse_portfolio
    message = "Erreur imprévue dans les simulations."

    def faux(conn, portfolio_id, *, monte_carlo=False, **reste):
        if monte_carlo:
            raise ValueError(message)
        return reel(conn, portfolio_id, monte_carlo=False, **reste)

    monkeypatch.setattr(module, "analyse_portfolio", faux)
    queue = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["risk"]["tail_risk"]

    assert queue["monte_carlo_unavailable_reason"] == message
    assert queue["student_unavailable_reason"] == message


def test_une_student_indiscernable_de_la_normale_sort_null_avec_sa_raison(
    analyse_historique_court,
):
    """Rendements synthétiques NORMAUX : le maximum de vraisemblance pousse ν
    vers l'infini, et le moteur refuse l'ajustement au-delà de 30, seuil
    choisi. Sans ce refus, la provenance publiait un ν de l'ordre de 10²⁰, et
    au-delà de 10²⁷ l'analyse tombait en 500.

    La raison est relayée telle quelle, et n'écrit jamais ν : son seul
    nombre est la taille de la fenêtre, et elle dit que le seuil est choisi à
    la main.
    """
    corps = analyse_historique_court(40).json()
    queue = corps["risk"]["tail_risk"]
    seances = corps["estimation_window"]["observations"]

    assert queue["student_fit"] is None
    raison = queue["student_unavailable_reason"]
    assert "ne s'écartent pas de la loi normale" in raison
    assert "seuil choisi à la main" in raison
    assert set(re.findall(r"\d+", raison)) == {str(seances)}
    for niveau in queue["levels"]:
        assert niveau["student_parametric_var"] is None
        assert niveau["parametric_var"]["value"] is not None


def test_une_student_refusee_laisse_le_monte_carlo_normal_avec_sa_provenance(
    analyse_historique_court,
):
    """Le Monte Carlo normal ne dépend pas de ν : le refus de la Student ne
    l'emporte plus. Il reste la vérification croisée de la VaR paramétrique,
    avec sa graine et sa fenêtre."""
    corps = analyse_historique_court(40).json()
    queue = corps["risk"]["tail_risk"]
    seances = corps["estimation_window"]["observations"]

    assert queue["student_fit"] is None
    assert queue["student_unavailable_reason"] is not None
    assert queue["monte_carlo_unavailable_reason"] is None
    for niveau in queue["levels"]:
        simule = niveau["monte_carlo_var"]
        assert simule is not None
        assert simule["method"] == "Monte Carlo"
        assert "graine" in simule["detail"]
        assert simule["window"]["observations"] == seances


def test_student_et_monte_carlo_impossibles_publient_chacun_leur_raison(
    analyse_historique_court,
):
    """Deux séances d'observation pour deux lignes : la covariance est de rang
    un, le Monte Carlo normal n'a pas de facteur de Cholesky ; la Student
    manque de séances. Aucun des deux blancs n'est sans raison, et aucune
    raison ne tient lieu de l'autre."""
    queue = analyse_historique_court(3).json()["risk"]["tail_risk"]

    assert queue["student_fit"] is None
    raison = queue["student_unavailable_reason"]
    assert raison.startswith("Pas assez de jours pour ajuster la loi de Student")
    assert raison.endswith("il en faut au moins 30, la période en compte 2.")
    assert queue["monte_carlo_unavailable_reason"].startswith("La fenêtre compte 2")
    assert "davantage que de lignes" in queue["monte_carlo_unavailable_reason"]
    for niveau in queue["levels"]:
        assert niveau["monte_carlo_var"] is None
        assert niveau["student_parametric_var"] is None


def test_sous_trente_seances_la_volatilite_et_la_var_normale_publient_leur_reserve(
    analyse_historique_court,
):
    """Le chiffre reste, la réserve l'accompagne : marquée, pas refusée."""
    risque = analyse_historique_court(3).json()["risk"]

    for volatilite in ("volatility", "ewma_volatility", "parametric_volatility"):
        assert risque[volatilite]["annualised"] > 0.0
        assert risque[volatilite]["caveat"].startswith("Estimation mince")
    for niveau in risque["tail_risk"]["levels"]:
        assert niveau["parametric_var"]["value"] is not None
        assert "seuil choisi à la main" in niveau["parametric_var"]["caveat"]


def test_a_fenetre_pleine_aucune_reserve_d_estimation_mince(analyse_reelle):
    risque = analyse_reelle.json()["risk"]
    for volatilite in ("volatility", "ewma_volatility", "parametric_volatility"):
        assert risque[volatilite]["caveat"] is None
    for niveau in risque["tail_risk"]["levels"]:
        for var in (
            "historical_var",
            "parametric_var",
            "monte_carlo_var",
            "student_parametric_var",
            "student_monte_carlo_var",
        ):
            assert niveau[var]["caveat"] is None, var


def test_sur_sept_seances_var_historique_et_cvar_sont_refusees_aux_deux_niveaux(
    analyse_historique_court,
):
    for niveau in analyse_historique_court(8).json()["risk"]["tail_risk"]["levels"]:
        var_historique, cvar = niveau["historical_var"], niveau["expected_shortfall"]
        assert var_historique["value"] is None
        assert var_historique["undefined_reason"].startswith(f"Sur 7{NBSP}jours de bourse")
        assert cvar["value"] is None and cvar["threshold"] is None
        assert cvar["tail_observations"] is None and cvar["caveat"] is None
        # Refusées ensemble, pour la même raison : le même texte.
        assert cvar["undefined_reason"] == var_historique["undefined_reason"]
        # Les autres VaR restent : paramétrique marquée mince, Monte Carlo.
        assert niveau["parametric_var"]["value"] is not None


def test_sur_trente_neuf_seances_seul_le_niveau_99_est_refuse(analyse_historique_court):
    niveaux = {
        n["confidence"]: n
        for n in analyse_historique_court(40).json()["risk"]["tail_risk"]["levels"]
    }
    assert niveaux[0.95]["historical_var"]["value"] is not None
    assert niveaux[0.95]["expected_shortfall"]["value"] is not None
    assert niveaux[0.99]["historical_var"]["value"] is None
    assert niveaux[0.99]["expected_shortfall"]["value"] is None


def test_la_reference_ne_refuse_aucune_mesure_de_queue(analyse_reelle):
    for niveau in analyse_reelle.json()["risk"]["tail_risk"]["levels"]:
        assert niveau["historical_var"]["value"] is not None
        assert niveau["historical_var"]["undefined_reason"] is None
        assert niveau["expected_shortfall"]["undefined_reason"] is None


def test_la_reference_n_a_ni_refus_student_ni_refus_monte_carlo(analyse_reelle):
    queue = analyse_reelle.json()["risk"]["tail_risk"]
    assert queue["student_unavailable_reason"] is None
    assert queue["monte_carlo_unavailable_reason"] is None
    assert all(niveau["monte_carlo_var"] is not None for niveau in queue["levels"])


def test_une_erreur_qui_n_est_pas_celle_de_student_remonte_en_4xx(
    client_synthetique, portefeuille_synthetique, monkeypatch
):
    """Le réessai sans Monte Carlo est le discriminant.

    Si l'erreur persiste sans le volet Student, elle ne venait pas de lui : elle
    doit atteindre le client plutôt que d'être avalée en rapport partiel.
    """
    from backend.api.routes import analysis as module

    def faux(conn, portfolio_id, *, monte_carlo=False, **reste):
        raise ValueError("Fenêtre trop courte : 1 (minimum 2 séances).")

    monkeypatch.setattr(module, "analyse_portfolio", faux)

    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    )
    assert reponse.status_code == 422
    assert "Fenêtre trop courte" in reponse.json()["detail"]


# ═══════════════════════════════════════ 10. Les erreurs restent lisibles ══


def test_un_benchmark_absent_de_la_base_renvoie_le_message_du_moteur(
    client_synthetique, portefeuille_synthetique
):
    """`PortfolioError` porte déjà la commande à lancer. L'écraser en 500
    remplacerait une instruction par un aveu d'impuissance."""
    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?benchmark=ABSENT"
    )
    assert reponse.status_code == 409
    detail = reponse.json()["detail"]
    assert "ABSENT" in detail
    assert "python -m backend.ingestion add" in detail


def test_le_beta_se_desactive_avec_un_benchmark_vide(
    client_synthetique, portefeuille_synthetique
):
    """Pour un portefeuille dont l'indice de référence n'est pas en base."""
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250&benchmark="
    ).json()
    assert corps["risk"]["beta"] is None
    assert corps["parameters"]["benchmark"] is None
    # Les autres mesures sont là : désactiver le beta n'ampute pas le rapport.
    assert corps["risk"]["volatility"]["annualised"] > 0.0


def test_une_fenetre_hors_domaine_est_refusee_a_la_validation(
    client_synthetique, portefeuille_synthetique
):
    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=1"
    )
    assert reponse.status_code == 422
    assert reponse.json()["problems"][0]["field"] == "window"


# ═════════════════════════════════════════ 11. Le bandeau et l'as_of ══


def test_le_bandeau_est_structure_et_cite_la_fenetre_demandee(analyse_reelle):
    bandeau = analyse_reelle.json()["disclaimer"]
    assert bandeau["title"]
    assert len(bandeau["sections"]) == 5
    assert all(s["title"] and s["body"] for s in bandeau["sections"])
    assert "connaissance de cause" in bandeau["confirmation"]
    assert "504 dernières séances" in bandeau["text"]


def test_le_bandeau_suit_la_fenetre_reellement_demandee(
    client_synthetique, portefeuille_synthetique
):
    """Le texte ne peut pas annoncer une durée que le calcul n'a pas utilisée."""
    bandeau = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["disclaimer"]
    assert "250 dernières séances" in bandeau["text"]
    assert "504" not in bandeau["text"]


def test_un_seul_as_of_gouverne_toute_la_reponse(analyse_reelle):
    """La raison d'être de l'endpoint unique.

    Si la page était assemblée à partir de plusieurs appels et que la base était
    rafraîchie entre-temps, la section volatilité et la section scénarios
    décriraient deux dates sans que rien ne le signale.
    """
    corps = analyse_reelle.json()
    assert corps["as_of"] == corps["risk"]["concentration"]["as_of"]


def test_l_as_of_du_portefeuille_n_est_pas_celui_de_la_base(analyse_reelle):
    """Deux dates distinctes, volontairement.

    Celle de la base est la dernière séance tous titres confondus ; celle du
    portefeuille est la plus ANCIENNE des dernières clôtures de ses lignes, donc
    la date jusqu'à laquelle la valorisation est vraie pour TOUTES.
    """
    corps = analyse_reelle.json()
    assert corps["as_of"] <= "2026-09-09"
    assert "as_of" not in corps["parameters"]


def test_la_reponse_porte_le_portefeuille_qu_elle_decrit(
    client_synthetique, portefeuille_synthetique
):
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()
    assert corps["portfolio_id"] == portefeuille_synthetique
    assert corps["portfolio"]["name"] == "Synthétique"


# ══════════════════════════════ 12. Taille effective de l'échantillon ══
#
# La 7A a rendu atteignable un trou du moteur : en ouvrant `window`, un rapport
# servi en 200 affirmait « 100 % de la variance s'explique par SPY (R² 1,00) »
# et « corrélation de 1,00 » pour les dix paires — sur deux séances, où ces
# valeurs sont des identités arithmétiques.
#
# Deux verrous, et un seul des deux protège vraiment.


def test_une_fenetre_sous_le_minimum_du_moteur_est_refusee(
    client_synthetique, portefeuille_synthetique
):
    """Le plancher vient de `MIN_REGRESSION_OBSERVATIONS`, pas d'un littéral."""
    for fenetre in (2, 10, 59):
        reponse = client_synthetique.get(
            f"/api/portfolios/{portefeuille_synthetique}/analysis?window={fenetre}"
        )
        assert reponse.status_code == 422, fenetre
        assert reponse.json()["problems"][0]["field"] == "window"

    assert (
        client_synthetique.get(
            f"/api/portfolios/{portefeuille_synthetique}/analysis?window=60"
        ).status_code
        == 200
    )


def test_le_plancher_de_fenetre_suit_la_constante_du_moteur(client_synthetique):
    """S'il était écrit en dur, il dériverait le jour où le moteur change d'avis."""
    from backend.risk_engine.config import MIN_REGRESSION_OBSERVATIONS

    parametres = client_synthetique.get("/openapi.json").json()["paths"][
        "/api/portfolios/{portfolio_id}/analysis"
    ]["get"]["parameters"]
    fenetre = next(p for p in parametres if p["name"] == "window")
    assert fenetre["schema"]["minimum"] == MIN_REGRESSION_OBSERVATIONS


def test_une_ligne_a_l_historique_court_fait_tomber_la_fenetre_effective(
    analyse_historique_court,
):
    """Le plancher sur le paramètre ne protège PAS de ce cas.

    Le panel aligné se réduit à l'intersection des dates : une ligne cotée
    depuis quarante séances rend `observations` égal à 39, alors que la fenêtre
    demandée valait 504 et que rien dans la requête ne l'annonçait.
    """
    reponse = analyse_historique_court(40)
    assert reponse.status_code == 200, reponse.text

    corps = reponse.json()
    assert corps["parameters"]["window"] == 504
    assert corps["risk"]["volatility"]["window"]["observations"] == 39
    assert corps["risk"]["volatility"]["window"]["complete"] is False


def test_sur_un_echantillon_mince_les_deux_observations_portent_le_seuil_choisi(
    analyse_historique_court,
):
    """Ce que `crisis_degradation` faisait déjà pour le R² de crise."""
    corps = analyse_historique_court(40).json()
    concernees = [
        o
        for o in corps["observations"]
        if o["rule"] in ("systematic_share", "apparent_diversification")
    ]
    assert len(concernees) >= 2
    assert {o["rule"] for o in concernees} == {
        "systematic_share",
        "apparent_diversification",
    }

    for observation in concernees:
        assert "Estimation mince\u00a0: sur 39\u00a0jours de bourse" in observation["statement"]
        assert observation["uses_chosen_threshold"] is True
        minimum = [
            s
            for s in observation["thresholds"]
            if s["name"] == "nombre minimal de séances d'une régression"
        ]
        assert minimum, observation["rule"]
        assert minimum[0]["kind"] == "chosen"
        assert minimum[0]["value"] == 60.0


@pytest.mark.parametrize("seances_courtes", [1, 2])
def test_sous_trois_seances_communes_l_analyse_repond_409_et_non_422(
    analyse_historique_court, seances_courtes
):
    """Moins de deux rendements : c'est l'état de la base, pas la requête.

    Deux cotations en commun ne donnent qu'un rendement. L'API répondait alors
    422 « Au moins 2 observations sont nécessaires (reçu : 1). », comme si la
    requête était fautive. Elle est correcte : 409, avec ce qui a été reçu et
    ce qu'il faut, et la commande qui permet de vérifier.
    """
    reponse = analyse_historique_court(seances_courtes)
    assert reponse.status_code == 409, reponse.text
    detail = reponse.json()["detail"]
    assert "python -m backend.ingestion status" in detail
    if seances_courtes == 2:
        assert "il en faut au moins 3" in detail


def test_sous_trois_seances_l_api_refuse_de_chiffrer_et_dit_pourquoi(
    analyse_historique_court,
):
    """Trois cotations en commun donnent deux rendements : le régime dégénéré.

    Le rapport reste servi — les autres mesures existent —, mais ces deux
    observations ne portent aucun chiffre, et le seuil qui l'explique est
    DÉRIVÉ : il se démontre, il n'a pas été choisi.
    """
    reponse = analyse_historique_court(3)
    assert reponse.status_code == 200, reponse.text

    corps = reponse.json()
    assert corps["risk"]["volatility"]["window"]["observations"] == 2

    concernees = [
        o
        for o in corps["observations"]
        if o["rule"] in ("systematic_share", "apparent_diversification")
    ]
    assert {o["rule"] for o in concernees} == {
        "systematic_share",
        "apparent_diversification",
    }

    for observation in concernees:
        assert "n'a pas de sens\u00a0: il en faut au moins 3." in observation["statement"]
        assert observation["uses_chosen_threshold"] is False
        (seuil,) = observation["thresholds"]
        assert seuil["kind"] == "derived"
        assert seuil["value"] == 3.0
        assert "le centrage ne laisse qu'une seule direction" in seuil["rationale"]
        assert seuil["chosen"] is False


@pytest.mark.parametrize("seances_courtes", [3, 4, 40])
def test_aucune_valeur_degeneree_n_est_affirmee_dans_la_reponse(
    analyse_historique_court, seances_courtes
):
    """La garde de bout en bout, sur le JSON réellement servi.

    Sous soixante séances, une phrase ne peut porter « 1,00 » que si la valeur
    a été réellement estimée — trois observations au moins — et qu'elle est
    accompagnée du seuil CHOISI qui dit l'échantillon mince.
    """
    corps = analyse_historique_court(seances_courtes).json()
    seances = corps["risk"]["volatility"]["window"]["observations"]
    assert seances < 60

    for observation in corps["observations"]:
        if observation["rule"] not in (
            "systematic_share",
            "apparent_diversification",
        ):
            continue
        phrase = observation["statement"]
        # Un R² de 1 se lit « 100 % des variations … ont suivi celles du marché ».
        degeneree = "corrélation de 1,00" in phrase or "100\u202f% des variations" in phrase
        if seances < 3:
            assert not degeneree, phrase
        elif degeneree:
            assert observation["uses_chosen_threshold"], phrase


def test_une_ligne_a_variance_nulle_est_refusee_par_le_moteur_pas_par_un_nan(
    tmp_path, client_factory
):
    """Un cours inchangé rend la corrélation indéfinie — ni ±1, ni 0.

    Ce cas n'atteint jamais les règles ni les schémas : `correlation_matrix` le
    refuse d'abord, avec un message qui nomme la ligne fautive. Il ressort donc
    en 422 lisible, et non en 500 sur un NaN que les schémas auraient rejeté à
    la construction. Test de non-régression sur ce chemin.
    """
    from .conftest import _series_prix, construire_base

    generateur = np.random.default_rng(11)
    seances = 200
    chemin = construire_base(
        tmp_path / "fige.sqlite",
        {
            "BOUGE": (
                "Bouge Inc",
                "Energy",
                _series_prix(generateur.normal(0.0004, 0.011, seances), 100.0),
            ),
            "FIGE": ("Figé SA", "Utilities", [50.0] * seances),
            "SPY": (
                "S&P 500 ETF",
                None,
                _series_prix(generateur.normal(0.0004, 0.009, seances), 400.0),
            ),
        },
        seances,
    )

    with client_factory(chemin) as client:
        identifiant = client.post("/api/portfolios", json={}).json()["id"]
        client.put(
            f"/api/portfolios/{identifiant}/positions",
            json={
                "positions": [
                    {"ticker": "BOUGE", "quantity": 10},
                    {"ticker": "FIGE", "quantity": 10},
                ]
            },
        )
        reponse = client.get(f"/api/portfolios/{identifiant}/analysis?window=150")

    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert "Variance nulle" in detail
    assert "FIGE" in detail

# ═════════════════════════ 13. Conventions de signe et de casse ══


def test_le_seuil_du_cvar_est_un_rendement_et_sa_valeur_une_perte(analyse_reelle):
    """Deux conventions de signe dans le même objet, et c'est documenté.

    `value` est une perte positive, `threshold` est le quantile brut de la
    distribution des rendements, donc négatif. L'en-tête de `risk_engine.var`
    annonce pourtant que « toutes les valeurs de ce module sont des pertes
    positives » : l'écart est dans le moteur, et la couche API le publie tel
    quel plutôt que de retourner un nombre que le moteur n'a jamais produit.

    La relation exacte : `threshold` est l'opposé de `historical_var.value` au
    même niveau, les deux sortant du même quantile empirique.
    """
    for niveau in analyse_reelle.json()["risk"]["tail_risk"]["levels"]:
        cvar = niveau["expected_shortfall"]
        assert cvar["value"] > 0.0, "la perte moyenne est rendue positive"
        assert cvar["threshold"] < 0.0, "le seuil est un rendement"
        assert cvar["threshold"] == pytest.approx(
            -niveau["historical_var"]["value"]
        )
        # Le CVaR est au moins aussi sévère que la VaR, par construction.
        assert cvar["value"] >= niveau["historical_var"]["value"]


def test_la_convention_de_signe_du_seuil_est_dans_le_schema(analyse_reelle):
    """Un champ dont le signe surprend doit porter sa convention.

    Sans description, un client qui lirait `threshold` comme une perte
    afficherait « −1,73 % » là où la perte vaut 1,73 %, et le signe passerait
    pour une erreur de saisie.
    """
    from backend.api.schemas import ExpectedShortfallOut

    description = ExpectedShortfallOut.model_fields["threshold"].description
    assert description is not None
    assert "RENDEMENT" in description
    assert "opposé" in description


def test_le_benchmark_est_insensible_a_la_casse(
    client_synthetique, portefeuille_synthetique
):
    """Les tickers des positions sont mis en capitales ; le benchmark aussi.

    Sans cette normalisation, `?benchmark=spy` répondait 409 « aucun prix en
    base » alors que `spy` dans un CSV s'importe sans broncher : deux portes
    d'entrée de la même API, deux exigences différentes sur la même donnée.
    """
    for saisie in ("spy", "SPY", "Spy", " spy "):
        reponse = client_synthetique.get(
            f"/api/portfolios/{portefeuille_synthetique}/analysis",
            params={"window": 250, "benchmark": saisie},
        )
        assert reponse.status_code == 200, (saisie, reponse.text)
        corps = reponse.json()
        assert corps["parameters"]["benchmark"] == "SPY"
        assert corps["risk"]["beta"]["benchmark"] == "SPY"


def test_un_benchmark_vraiment_inconnu_reste_refuse(
    client_synthetique, portefeuille_synthetique
):
    """La normalisation ne doit pas faire passer n'importe quoi."""
    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis",
        params={"window": 250, "benchmark": "absent"},
    )
    assert reponse.status_code == 409
    # Le message nomme le ticker tel qu'il sera cherché en base, en capitales.
    assert "ABSENT" in reponse.json()["detail"]

# ═══════════════ 14. La fenêtre effective, dans les mesures et les phrases ══
#
# Le trou corrigé ici est plus large que les deux règles de la passe
# précédente : quatre règles lisent la même matrice de covariance, et le bloc
# `risk` publiait encore les valeurs dégénérées que ces règles refusaient de
# commenter. En 7B, une carte de chaleur lit la matrice, pas la phrase.


def test_sous_trois_seances_la_correlation_et_le_beta_sortent_null(
    analyse_historique_court,
):
    """Le refus vit dans la MESURE, pas seulement dans le commentaire."""
    corps = analyse_historique_court(3).json()
    assert corps["risk"]["volatility"]["window"]["observations"] == 2

    matrices = corps["risk"]["matrices"]
    assert matrices["correlation"] is None
    raison = matrices["correlation_undefined_reason"]
    assert f"Sur 2{NBSP}jours de bourse" in raison
    assert "une corrélation n'a pas de sens" in raison
    # La covariance reste publiée : wᵀΣw porte la volatilité et la VaR.
    assert matrices["covariance"]["values"]

    beta = corps["risk"]["beta"]
    assert beta["beta"] is None, "la pente aussi, pas seulement le R²"
    assert beta["r_squared"] is None
    assert beta["idiosyncratic_share"] is None
    assert "la sensibilité au marché n'a pas de sens" in beta["undefined_reason"]
    # Ce qui manque est le chiffre, pas la provenance.
    assert beta["benchmark"] == "SPY"
    assert beta["window"]["observations"] == 2


def test_sous_trois_seances_aucune_part_de_variance_ni_ligne_effective_en_risque(
    analyse_historique_court,
):
    corps = analyse_historique_court(3).json()
    par_regle = {}
    for observation in corps["observations"]:
        par_regle.setdefault(observation["rule"], []).append(observation)

    (contribution,) = par_regle["variance_contribution"]
    assert contribution["subject"] == "portefeuille"
    assert "la part de chaque ligne dans les variations n'a pas de sens" in contribution["statement"]
    assert contribution["facts"].get("part_de_variance") is None

    (concentration,) = par_regle["effective_concentration"]
    assert "Ce qu'elles font bouger n'est pas chiffré." in concentration["statement"]
    assert concentration["facts"]["lignes_effectives_risque"] is None
    assert concentration["facts"]["lignes_effectives_capital"] is not None

    # Les quatre règles refusent, et toutes avec le seuil DÉRIVÉ.
    for regle in (
        "effective_concentration",
        "variance_contribution",
        "apparent_diversification",
        "systematic_share",
    ):
        for observation in par_regle[regle]:
            assert observation["uses_chosen_threshold"] is False, regle
            (seuil,) = observation["thresholds"]
            assert seuil["kind"] == "derived", regle
            assert seuil["value"] == 3.0, regle


def test_les_quatre_regles_portent_le_seuil_choisi_sur_quarante_seances(
    analyse_historique_court,
):
    """Le trou d'origine : seules les régressions de crise appliquaient le 60."""
    corps = analyse_historique_court(40).json()
    assert corps["risk"]["volatility"]["window"]["observations"] == 39

    concernees = [
        o
        for o in corps["observations"]
        if o["rule"]
        in (
            "effective_concentration",
            "variance_contribution",
            "apparent_diversification",
            "systematic_share",
        )
    ]
    assert {o["rule"] for o in concernees} == {
        "effective_concentration",
        "variance_contribution",
        "apparent_diversification",
        "systematic_share",
    }
    for observation in concernees:
        assert "Estimation mince\u00a0: sur 39\u00a0jours de bourse" in observation["statement"], (
            observation["rule"]
        )
        minimum = [
            s
            for s in observation["thresholds"]
            if s["name"] == "nombre minimal de séances d'une régression"
        ]
        assert minimum, observation["rule"]
        assert minimum[0]["kind"] == "chosen"
        assert minimum[0]["value"] == 60.0


def test_la_ligne_qui_raccourcit_la_fenetre_est_nommee_avec_sa_date(
    analyse_historique_court,
):
    """`complete: false` dit que la fenêtre est courte, pas à cause de qui.

    C'est pourtant la seule information sur laquelle l'utilisateur peut agir, et
    le bandeau de la 7B en a besoin.
    """
    corps = analyse_historique_court(40).json()

    assert corps["risk"]["volatility"]["window"]["complete"] is False
    (limitante,) = corps["limiting_positions"]
    assert limitante["ticker"] == "COURT"

    # La date est celle de l'entrée en cotation de la ligne. Elle précède d'une
    # séance le début de la fenêtre : le premier cours commun ne produit pas de
    # rendement, il sert de point de départ au suivant.
    fenetre = corps["risk"]["volatility"]["window"]
    assert limitante["first_available"] < fenetre["start"]


@pytest.mark.parametrize("seances_courtes", [3, 40])
def test_une_ligne_limitante_est_nommee_des_que_la_fenetre_est_incomplete(
    analyse_historique_court, seances_courtes
):
    corps = analyse_historique_court(seances_courtes).json()
    assert [p["ticker"] for p in corps["limiting_positions"]] == ["COURT"]


def test_a_fenetre_pleine_la_reponse_est_inchangee_et_sans_ligne_limitante(
    analyse_reelle,
):
    """Le portefeuille de démonstration, 504 séances : rien ne bouge.

    Aucune ligne limitante, aucun seuil de taille d'échantillon nulle part, et
    les chiffres sont ceux d'avant cette passe — les champs ajoutés
    (`limiting_positions`, `correlation_undefined_reason`, `undefined_reason`)
    sont additifs et valent `null` ou liste vide.
    """
    corps = analyse_reelle.json()

    assert corps["risk"]["volatility"]["window"]["observations"] == 504
    assert corps["risk"]["volatility"]["window"]["complete"] is True
    assert corps["limiting_positions"] == []

    # Les mesures sont là, avec leurs valeurs de référence.
    assert corps["risk"]["matrices"]["correlation"] is not None
    assert corps["risk"]["matrices"]["correlation_undefined_reason"] is None
    assert corps["risk"]["beta"]["undefined_reason"] is None
    assert corps["risk"]["beta"]["beta"] == pytest.approx(0.5672, abs=1e-3)
    assert corps["risk"]["beta"]["r_squared"] == pytest.approx(0.4949, abs=1e-3)
    assert corps["risk"]["volatility"]["annualised"] == pytest.approx(
        0.13327, abs=1e-4
    )
    assert corps["risk"]["tail_risk"]["levels"][1]["historical_var"][
        "value"
    ] == pytest.approx(0.01730, abs=1e-4)

    # Aucune règle ne signale d'échantillon mince, et aucune ne refuse.
    for observation in corps["observations"]:
        assert "Estimation mince" not in observation["statement"]
        assert "n'a pas de sens" not in observation["statement"]
        noms = {s["name"] for s in observation["thresholds"]}
        assert "nombre minimal de séances estimables" not in noms
        if observation["rule"] != "crisis_degradation":
            assert "nombre minimal de séances d'une régression" not in noms


def test_les_contributions_a_la_variance_restent_completes_a_fenetre_pleine(
    analyse_reelle,
):
    """Contrôle de non-régression : six lignes, six observations, somme à 1."""
    corps = analyse_reelle.json()
    contributions = [
        o for o in corps["observations"] if o["rule"] == "variance_contribution"
    ]
    assert len(contributions) == 6
    total = sum(o["facts"]["part_de_variance"] for o in contributions)
    assert total == pytest.approx(1.0)

# ═══════════════ 15. Une raison par mesure, et le refus des contributions ══


def test_chaque_raison_de_refus_n_affirme_que_ce_qui_la_concerne(
    analyse_historique_court,
):
    """Une explication fausse attachée à un refus juste est pire qu'un refus nu.

    « Le coefficient vaut ±1 » est vrai d'une corrélation et faux d'une pente :
    à deux séances le beta prend n'importe quelle valeur. Chaque raison, en
    clair, nomme SA mesure ; seule celle de la corrélation garde une
    conséquence, vraie d'elle seule. La démonstration est dans METHODOLOGY.md,
    « Two sample-size regimes ».
    """
    corps = analyse_historique_court(3).json()

    correlation = corps["risk"]["matrices"]["correlation_undefined_reason"]
    beta = corps["risk"]["beta"]["undefined_reason"]
    contributions = corps["risk"]["variance_contributions"]["undefined_reason"]

    assert "une corrélation" in correlation
    assert "la sensibilité au marché" in beta
    assert "la part de chaque ligne dans les variations" in contributions

    assert f"+1 ou {MINUS}1" in correlation
    assert "+1" not in beta
    assert "+1" not in contributions

    # Aucune n'emprunte la justification d'une autre mesure.
    for raison in (correlation, beta, contributions):
        assert "régression" not in raison
        assert "rang" not in raison

    # La partie commune ne dit que ce qui vaut des trois.
    for raison in (correlation, beta, contributions):
        assert f"Sur 2{NBSP}jours de bourse" in raison
        assert f"n'a pas de sens{NBSP}: il en faut au moins 3." in raison


def test_les_contributions_a_la_variance_sortent_null_sous_trois_seances(
    analyse_historique_court,
):
    """En 7B, un graphe à barres lira `contributions`, pas la phrase.

    Des parts qui somment à 1 ont l'air d'une décomposition quel que soit leur
    contenu — exactement le même piège que la carte de chaleur.
    """
    contributions = analyse_historique_court(3).json()["risk"][
        "variance_contributions"
    ]

    assert contributions["contributions"] is None
    assert contributions["effective_positions"] is None
    assert contributions["has_negative_contribution"] is None
    assert (
        "la part de chaque ligne dans les variations n'a pas de sens"
        in contributions["undefined_reason"]
    )
    # L'ordre canonique reste publié : il ne dépend pas de la fenêtre.
    assert contributions["tickers"]


def test_les_poids_restent_publies_quand_les_contributions_refusent(
    analyse_historique_court,
):
    """Les poids sont ponctuels : la brièveté de l'historique ne les touche pas."""
    corps = analyse_historique_court(3).json()

    assert corps["weights"]
    assert sum(w["weight"] for w in corps["weights"]) == pytest.approx(1.0)
    assert corps["risk"]["concentration"]["hhi"] > 0.0


def test_sous_trois_seances_la_volatilite_reste_publiee_la_var_historique_est_refusee(
    analyse_historique_court,
):
    """La ligne de partage, vue du client.

    On refuse ce qui ne dépend plus des données, et ce qui n'est plus la mesure
    annoncée ; on signale ce qui en dépend mal. Une volatilité sur deux
    observations est mauvaise, pas dégénérée — et `window.observations`,
    `limiting_positions` et le seuil de 60 séances la couvrent. Une VaR
    historique sur deux séances n'est que le minimum de la fenêtre : refusée,
    avec sa raison. Ce test affirmait le contraire jusqu'à la 7B.3a.
    """
    risque = analyse_historique_court(3).json()["risk"]

    assert risque["volatility"]["annualised"] > 0.0
    assert risque["matrices"]["covariance"]["values"]
    var_historique = risque["tail_risk"]["levels"][0]["historical_var"]
    assert var_historique["value"] is None
    assert var_historique["undefined_reason"].startswith(
        f"Sur 2{NBSP}jours de bourse, aucun ne tombe"
    )
    assert risque["volatility"]["window"]["observations"] == 2


def test_a_fenetre_pleine_les_contributions_sont_completes(analyse_reelle):
    """Non-régression : rien de tout ça ne touche le cas nominal."""
    contributions = analyse_reelle.json()["risk"]["variance_contributions"]

    assert contributions["undefined_reason"] is None
    assert len(contributions["contributions"]) == 6
    assert contributions["effective_positions"] > 1.0
    assert contributions["has_negative_contribution"] in (True, False)
    total = sum(c["contribution"] for c in contributions["contributions"])
    assert total == pytest.approx(1.0)

# ═══════════════════════════════ 16. Typographie du texte rédigé côté serveur ══
#
# Le backend ne rend pas que des nombres : il rédige des phrases — observations,
# `summary()` des scénarios, `caveat` du CVaR, provenance des seuils, bandeau.
# Ces phrases sont affichées telles quelles, et une espace ordinaire y laisse le
# « % » partir seul à la ligne suivante. Voir `backend/typography.py`.

# Les expressions de ces sondes vivent dans `gardes_texte.py`.

def test_aucune_espace_secable_avant_un_pourcent(analyse_reelle):
    """U+202F, espace FINE insécable, sinon le « % » se retrouve seul en tête
    de ligne."""
    fautes = [
        (chemin, extrait)
        for chemin, texte in toutes_les_chaines(analyse_reelle.json())
        for extrait in ESPACE_AVANT_POURCENT.findall(texte)
    ]
    assert not fautes, f"{len(fautes)} espace(s) sécable(s) avant % : {fautes[:3]}"


def test_aucune_espace_secable_entre_un_nombre_et_le_mot_qu_il_compte(
    analyse_reelle,
):
    """U+00A0 : « 504 séances » ne se coupe pas en « 504 » puis « séances »."""
    fautes = [
        (chemin, extrait)
        for chemin, texte in toutes_les_chaines(analyse_reelle.json())
        for extrait in ESPACE_AVANT_MOT.findall(texte)
    ]
    assert not fautes, f"{len(fautes)} lien(s) sécable(s) : {fautes[:3]}"


def test_une_couverture_partielle_n_a_aucune_espace_secable_avant_un_pourcent(
    base_figee, client_factory
):
    """La justification du seuil de couverture (« à 80 % … à 50 % ») n'est
    publiée que sous 80 % de couverture : le portefeuille de référence, couvert
    à 100 %, ne la montrait jamais aux sondes ci-dessus. Elle portait deux
    espaces ordinaires avant « % ».

    Sur la copie figée propre au test, JPM perd son historique avant 2023 : les
    trois crises l'excluent, et la couverture tombe à 74 %.
    """
    from contextlib import closing

    from .conftest import PORTEFEUILLE_DEMO

    with closing(connect(base_figee)) as conn, conn:
        conn.execute("DELETE FROM prices WHERE ticker = 'JPM' AND date < '2023-01-01'")

    with client_factory(base_figee) as client:
        identifiant = client.post("/api/portfolios", json={"name": "Partielle"}).json()["id"]
        client.put(
            f"/api/portfolios/{identifiant}/positions",
            json={
                "positions": [
                    {"ticker": ticker, "quantity": quantite}
                    for ticker, quantite in PORTEFEUILLE_DEMO.items()
                ]
            },
        )
        corps = client.get(f"/api/portfolios/{identifiant}/analysis").json()

    # Témoin : la réponse publie bien le seuil de couverture, sans quoi la
    # sonde surveillerait une absence.
    seuils = [
        seuil
        for observation in corps["observations"]
        for seuil in observation["thresholds"]
        if seuil["name"] == "couverture minimale d'un scénario"
    ]
    assert seuils, "aucune observation ne cite le seuil de couverture"
    assert all(s["value"] == 0.80 for s in seuils)

    fautes = [
        (chemin, extrait)
        for chemin, texte in toutes_les_chaines(corps)
        for extrait in ESPACE_AVANT_POURCENT.findall(texte)
    ]
    assert not fautes, f"{len(fautes)} espace(s) sécable(s) avant % : {fautes[:3]}"


def test_le_texte_contient_bien_les_deux_caracteres_attendus(analyse_reelle):
    """Contrôle en sens inverse.

    Les deux tests ci-dessus passeraient sur une réponse qui ne contiendrait
    aucun pourcentage et aucun décompte — ils vérifient une absence. Celui-ci
    vérifie que les caractères sont bien là, donc que les deux autres ont
    quelque chose à surveiller.
    """
    textes = [texte for _, texte in toutes_les_chaines(analyse_reelle.json())]
    assemble = " ".join(textes)

    assert f"{NARROW_NBSP}%" in assemble
    assert f"{NBSP}séances" in assemble
    assert f"{NBSP}lignes" in assemble


def test_les_observations_du_moteur_de_regles_suivent_la_convention(
    analyse_reelle,
):
    """Contrôle ciblé sur ce que l'utilisateur lit en premier."""
    for observation in analyse_reelle.json()["observations"]:
        for champ in ("statement", "rendered", "provenance"):
            texte = observation[champ]
            assert not ESPACE_AVANT_POURCENT.findall(texte), (
                observation["rule"],
                champ,
                texte,
            )
            assert not ESPACE_AVANT_MOT.findall(texte), (
                observation["rule"],
                champ,
                texte,
            )


def test_les_resumes_de_scenarios_et_de_regimes_suivent_la_convention(
    analyse_reelle,
):
    corps = analyse_reelle.json()
    resumes = [s["summary"] for s in corps["scenarios"]]
    resumes += [r["summary"] for r in corps["regimes"]]
    assert resumes

    for resume in resumes:
        assert not ESPACE_AVANT_POURCENT.findall(resume), resume
        assert not ESPACE_AVANT_MOT.findall(resume), resume


def test_le_bandeau_et_les_seuils_suivent_la_convention(analyse_reelle):
    corps = analyse_reelle.json()
    textes = [corps["disclaimer"]["text"]]
    textes += [s["body"] for s in corps["disclaimer"]["sections"]]
    textes += [
        seuil["rendered"]
        for observation in corps["observations"]
        for seuil in observation["thresholds"]
    ]

    for texte in textes:
        assert not ESPACE_AVANT_POURCENT.findall(texte), texte
        assert not ESPACE_AVANT_MOT.findall(texte), texte


def test_les_grands_nombres_sont_groupes_a_l_espace_fine(analyse_reelle):
    """« 100 000 tirages » et non « 100000 tirages »."""
    details = [
        niveau[champ]["detail"]
        for niveau in analyse_reelle.json()["risk"]["tail_risk"]["levels"]
        for champ in ("monte_carlo_var", "student_monte_carlo_var")
        if niveau[champ] is not None
    ]
    assert details
    for detail in details:
        assert f"100{NARROW_NBSP}000{NBSP}tirages" in detail, detail


# ═════════════════════════ 9. Ce que citent les phrases de lecture ══
#
# Les données ajoutées pour les textes de lecture, publiées telles que le
# moteur les calcule. Sur la copie figée, la baisse d'avril 2025 est effacée
# avant la fin de la fenêtre.


def test_chaque_montant_est_la_mesure_appliquee_a_la_valeur(analyse_reelle):
    corps = analyse_reelle.json()
    total = corps["total_value"]
    champs = (
        "historical_var",
        "parametric_var",
        "monte_carlo_var",
        "student_parametric_var",
        "student_monte_carlo_var",
        "expected_shortfall",
    )
    for niveau in corps["risk"]["tail_risk"]["levels"]:
        for champ in champs:
            mesure = niveau[champ]
            assert mesure is not None, champ
            assert mesure["amount"] == mesure["value"] * total, champ
    creux = corps["risk"]["drawdown"]
    assert creux["amount"] == creux["value"] * total
    pire = corps["risk"]["worst_day"]
    assert pire["amount"] == pire["loss"] * total


def test_le_retour_au_pic_se_lit_sur_la_courbe_publiee(analyse_reelle):
    corps = analyse_reelle.json()
    creux = corps["risk"]["drawdown"]
    niveaux = {point["date"]: point["value"] for point in corps["series"]["wealth"]}
    dates = list(niveaux)
    pic, bas, retour = creux["peak_date"], creux["trough_date"], creux["recovery_date"]

    assert retour is not None
    assert niveaux[retour] >= niveaux[pic]
    entre = dates[dates.index(bas) : dates.index(retour)]
    assert all(niveaux[jour] < niveaux[pic] for jour in entre)
    assert creux["recovery_sessions"] == dates.index(retour) - dates.index(bas)


def test_la_pire_seance_est_le_plus_mauvais_rendement_publie(analyse_reelle):
    corps = analyse_reelle.json()
    rendements = corps["series"]["returns"]
    pire = min(rendements, key=lambda point: point["value"])
    publiee = corps["risk"]["worst_day"]
    assert publiee["date"] == pire["date"]
    assert publiee["loss"] == -pire["value"]
    assert publiee["window"] == corps["estimation_window"]


def test_les_libelles_de_periode_suivent_la_fenetre_obtenue(analyse_reelle):
    corps = analyse_reelle.json()
    attendu = f"ces deux{NBSP}dernières années"
    risque = corps["risk"]
    assert corps["estimation_period_label"] == attendu
    assert risque["volatility"]["period_label"] == attendu
    assert risque["drawdown"]["period_label"] == attendu
    for niveau in risque["tail_risk"]["levels"]:
        for champ in ("historical_var", "parametric_var", "expected_shortfall"):
            assert niveau[champ]["period_label"] == attendu, champ
    for regime in corps["regimes"]:
        assert regime["calm_period_label"] == attendu


def test_l_indice_de_reference_est_nomme_et_mesure_sur_la_meme_fenetre(analyse_reelle):
    corps = analyse_reelle.json()
    parametres = corps["parameters"]
    assert parametres["benchmark_label"] == "le S&P 500"
    assert parametres["benchmark_description"] == (
        "l'indice de 500 grandes entreprises américaines"
    )
    indice = corps["risk"]["benchmark_volatility"]
    assert indice["window"] == corps["estimation_window"]
    assert indice["method"] == corps["risk"]["volatility"]["method"]
    assert indice["annualised"] > 0
    assert indice["annualised"] != corps["risk"]["volatility"]["annualised"]
    for regime in corps["regimes"]:
        assert regime["benchmark_label"] == "le S&P 500"


def test_chaque_crise_publie_son_montant_et_son_verdict_de_couverture(analyse_reelle):
    for scenario in analyse_reelle.json()["scenarios"]:
        couverture = scenario["coverage"]
        assert scenario["end_to_end_amount"] == (
            scenario["end_to_end_return"] * couverture["covered_value"]
        )
        assert scenario["coverage_sufficient"] is True


def test_sans_indice_de_reference_ni_nom_ni_volatilite_d_indice(
    client_synthetique, portefeuille_synthetique
):
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250&benchmark="
    ).json()
    assert corps["parameters"]["benchmark_label"] is None
    assert corps["parameters"]["benchmark_description"] is None
    assert corps["risk"]["benchmark_volatility"] is None
