"""`/analysis` — ce que la sérialisation ne doit jamais perdre en route.

Cette phase ne calcule rien : elle publie. Les pannes qu'elle peut produire sont
donc toutes des pannes SILENCIEUSES — un champ disparu, un `null` sans raison,
une étiquette décalée d'un cran, un NaN écrit tel quel dans le corps. Aucune ne
lève d'exception, toutes produisent une réponse d'apparence normale. Ces tests
existent pour qu'elles fassent du bruit.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from backend.db.init_db import connect
from backend.risk_engine.engine import analyse_portfolio

from .conftest import construire_base


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
    """
    corps = analyse_reelle.json()
    assert "window" not in corps
    assert "window" not in corps["risk"]
    assert corps["parameters"]["window"] == 504


def test_le_beta_regresse_de_crise_porte_ses_propres_observations(analyse_reelle):
    """Il ne porte PAS de `window` : le moteur ne lui en attache pas, et en
    fabriquer une inventerait une fenêtre « demandée » qui ne l'a jamais été."""
    crise = analyse_reelle.json()["regimes"][1]["crisis_beta"]
    assert "window" not in crise
    assert crise["observations"] > 0
    assert crise["start"] < crise["end"]
    assert crise["min_observations"] == 60
    # Le krach COVID tient en 23 séances : l'échantillon est trop mince et la
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
    assert sortino["annualised"] is not 0
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
    mot « CHOISI » dans du texte français."""
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


def test_un_seuil_choisi_le_dit_dans_le_champ_et_dans_le_texte(analyse_reelle):
    choisis = [
        seuil
        for observation in analyse_reelle.json()["observations"]
        for seuil in observation["thresholds"]
        if seuil["kind"] == "chosen"
    ]
    assert choisis
    for seuil in choisis:
        assert "CHOISI" in seuil["rendered"]


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
    """`caveat` est une propriété, allumée en permanence à 99 % : à ce niveau la
    queue ne compte que 1 % de la fenêtre. Ce n'est pas une anomalie, c'est la
    structure du chiffre."""
    niveaux = {
        n["confidence"]: n for n in analyse_reelle.json()["risk"]["tail_risk"]["levels"]
    }
    assert niveaux[0.95]["expected_shortfall"]["caveat"] is None
    caveat = niveaux[0.99]["expected_shortfall"]["caveat"]
    assert caveat is not None
    assert "séances seulement" in caveat
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
        assert "aucune ligne" in scenario["unavailable_reason"]
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
    """Une VaR de 1,38 % se sérialise 0.0138.

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
    """Un « 1,38 % » publié comme chaîne serait un formatage déguisé en donnée."""
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

    À 99 %, le quantile est déjà dans la queue : la Student y est plus sévère
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
    """ν ≤ 2 ne doit pas emporter tout le rapport.

    Le refus du moteur est relayé MOT POUR MOT : c'est lui qui explique que sans
    variance finie, une VaR « à variance ajustée » n'a pas de sens — et le
    lecteur a besoin de savoir que les autres mesures de la même page reposent
    elles aussi sur une variance.
    """
    from backend.api.routes import analysis as module

    reel = module.analyse_portfolio
    message = (
        "ν = 1.900 ≤ 2 : la loi de Student n'a pas de variance finie. "
        "Aucune matrice d'échelle ne peut reproduire la covariance observée."
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


def test_une_erreur_qui_n_est_pas_celle_de_student_remonte_en_4xx(
    client_synthetique, portefeuille_synthetique, monkeypatch
):
    """Le réessai sans Monte Carlo est le discriminant.

    Si l'erreur persiste sans le volet Student, elle ne venait pas de lui : elle
    doit atteindre le client plutôt que d'être avalée en rapport partiel.
    """
    from backend.api.routes import analysis as module

    def faux(conn, portfolio_id, *, monte_carlo=False, **reste):
        raise ValueError("Fenêtre trop courte : 1 (minimum 2 séances).")

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
    assert "504 dernières séances" in bandeau["text"]


def test_le_bandeau_suit_la_fenetre_reellement_demandee(
    client_synthetique, portefeuille_synthetique
):
    """Le texte ne peut pas annoncer une durée que le calcul n'a pas utilisée."""
    bandeau = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()["disclaimer"]
    assert "250 dernières séances" in bandeau["text"]
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
# servi en 200 affirmait « 100 % de la variance s'explique par SPY (R² 1,00) »
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
        assert "Estimation mince : 39 séances" in observation["statement"]
        assert observation["uses_chosen_threshold"] is True
        minimum = [
            s
            for s in observation["thresholds"]
            if s["name"] == "nombre minimal de séances d'une régression"
        ]
        assert minimum, observation["rule"]
        assert minimum[0]["kind"] == "chosen"
        assert minimum[0]["value"] == 60.0


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
        assert "estimable" in observation["statement"]
        assert observation["uses_chosen_threshold"] is False
        (seuil,) = observation["thresholds"]
        assert seuil["kind"] == "derived"
        assert seuil["value"] == 3.0
        assert "degrés de liberté résiduels" in seuil["rationale"]
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
        degeneree = "corrélation de 1,00" in phrase or "R² 1,00" in phrase
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
    afficherait « −1,73 % » là où la perte vaut 1,73 %, et le signe passerait
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
