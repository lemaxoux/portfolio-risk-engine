"""Tests des scénarios de stress : bornes, convention achat-conservation,
couverture, et décomposition par ligne.

Le premier bloc vérifie les dates du catalogue contre l'historique réel — les
bornes sont des affirmations sur le marché, pas des constantes de code, et un
test doit pouvoir les contredire.
"""

from __future__ import annotations

import shutil
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from backend.db.init_db import connect, init_db
from backend.risk_engine.engine import (
    assess_scenario_coverage,
    run_all_scenarios,
    run_scenario,
)
from backend.risk_engine.measures import max_drawdown
from backend.risk_engine.portfolio import load_price_panel, market_value_weights
from backend.risk_engine.returns import portfolio_returns, simple_returns
from backend.risk_engine.scenarios import SCENARIOS, Scenario, get_scenario
from backend.risk_engine.stress import (
    buy_and_hold_value,
    end_to_end_return,
    held_quantities,
    position_contributions,
)

BASE_REELLE = Path(__file__).resolve().parents[1] / "data" / "mx_risk.sqlite"

besoin_de_la_base = pytest.mark.skipif(
    not BASE_REELLE.exists(),
    reason="base locale absente — lancer `python -m backend.ingestion backfill`",
)

# Ordres de grandeur relevés sur l'historique réel du S&P 500.
AMPLITUDES_ATTENDUES = {
    "gfc_2008": -0.55,
    "covid_2020": -0.34,
    "tightening_2022": -0.25,
}


def cours_du_benchmark(scenario: Scenario) -> pd.Series:
    with closing(connect(BASE_REELLE)) as conn:
        panel = load_price_panel(
            conn, [scenario.benchmark], scenario.start, scenario.end
        )
    return panel[scenario.benchmark]


# ----------------------------------------- Bornes des scénarios, sur le réel --


@besoin_de_la_base
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
def test_le_creux_du_benchmark_tombe_a_la_date_de_fin_declaree(scenario: Scenario):
    """Les dates du catalogue sont vérifiées, pas supposées.

    Une borne fausse ne se verrait pas autrement : le calcul tournerait et
    rendrait un chiffre plausible pour un épisode qui n'est pas celui annoncé.
    Le drawdown du benchmark est recalculé DANS la fenêtre ; son creux doit
    tomber à la date de fin déclarée, et son pic à la date de début.
    """
    resultat = max_drawdown(cours_du_benchmark(scenario))

    assert resultat.trough_date == scenario.end, (
        f"{scenario.key} : le creux du benchmark tombe le {resultat.trough_date}, "
        f"pas le {scenario.end} déclaré"
    )
    assert resultat.peak_date == scenario.start, (
        f"{scenario.key} : le sommet du benchmark tombe le {resultat.peak_date}, "
        f"pas le {scenario.start} déclaré"
    )


@besoin_de_la_base
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
def test_l_amplitude_du_scenario_correspond_a_l_histoire(scenario: Scenario):
    assert max_drawdown(cours_du_benchmark(scenario)).value == pytest.approx(
        AMPLITUDES_ATTENDUES[scenario.key], abs=0.01
    )


def test_le_catalogue_est_une_structure_de_donnees():
    assert [s.key for s in SCENARIOS] == list(AMPLITUDES_ATTENDUES)
    for s in SCENARIOS:
        assert s.start < s.end
        assert s.benchmark
        assert s.description.strip()


def test_un_scenario_inconnu_liste_les_cles_disponibles():
    with pytest.raises(KeyError, match="gfc_2008"):
        get_scenario("krach_de_1929")


# ------------------------------------- Point de départ : les poids actuels --


def jours(n: int, depart: date = date(2008, 1, 2)) -> list[date]:
    return [depart + timedelta(days=i) for i in range(n)]


def test_le_portefeuille_entre_dans_l_episode_avec_ses_poids_actuels():
    """Le point de départ du rejeu est l'allocation d'aujourd'hui.

    Les cours de départ sont volontairement très différents d'un titre à l'autre.
    Appliquer les quantités d'aujourd'hui à ces cours donnerait des poids de
    départ sans rapport avec le portefeuille détenu ; ici, chaque ligne démarre
    exactement à son poids actuel.
    """
    panel = pd.DataFrame(
        {"A": [500.0, 450.0], "B": [5.0, 4.0], "C": [80.0, 88.0]}, index=jours(2)
    )
    poids_actuels = {"A": 0.5, "B": 0.3, "C": 0.2}

    contributions = {c.ticker: c for c in position_contributions(panel, poids_actuels)}

    for ticker, poids in poids_actuels.items():
        assert contributions[ticker].start_weight == pytest.approx(poids)
    assert buy_and_hold_value(panel, poids_actuels).iloc[0] == pytest.approx(1.0)


def test_les_quantites_sont_figees_apres_le_depart():
    panel = pd.DataFrame(
        {"A": [100.0, 200.0, 50.0], "B": [10.0, 10.0, 30.0]}, index=jours(3)
    )
    quantites = held_quantities(panel, {"A": 0.5, "B": 0.5})

    valeurs = buy_and_hold_value(panel, {"A": 0.5, "B": 0.5})
    for i in range(len(panel)):
        attendu = quantites["A"] * panel["A"].iloc[i] + quantites["B"] * panel["B"].iloc[i]
        assert valeurs.iloc[i] == pytest.approx(attendu)


def test_les_poids_sont_normalises_et_apparies_par_etiquette():
    panel = pd.DataFrame({"B": [10.0, 20.0], "A": [100.0, 100.0]}, index=jours(2))
    # Poids non normalisés et dans un ordre différent des colonnes.
    valeurs = buy_and_hold_value(panel, {"A": 3.0, "B": 1.0})
    assert end_to_end_return(valeurs) == pytest.approx(0.25 * 1.0)


# ----------------------------------- Achat-conservation vs poids constants --


def test_l_achat_conservation_diverge_des_poids_constants():
    """La rupture de convention avec la Phase 4, chiffrée.

    A double à chaque séance, B est divisé par deux. À quantités figées, la
    ligne gagnante prend mécaniquement du poids. À poids constants, on la
    vendrait chaque jour pour racheter la perdante — ce que ne fait pas un
    porteur passif, et qui donne un résultat très différent sur plusieurs
    périodes.
    """
    panel = pd.DataFrame(
        {"A": [100.0, 200.0, 400.0], "B": [100.0, 50.0, 25.0]}, index=jours(3)
    )
    poids = {"A": 0.5, "B": 0.5}

    achat_conservation = end_to_end_return(buy_and_hold_value(panel, poids))
    serie = portfolio_returns(simple_returns(panel), poids)
    poids_constants = float((1.0 + serie).prod() - 1.0)

    assert achat_conservation == pytest.approx(0.5 * 4.0 + 0.5 * 0.25 - 1.0)
    assert poids_constants == pytest.approx(1.25 * 1.25 - 1.0)
    assert achat_conservation != pytest.approx(poids_constants, rel=0.01)


def test_les_poids_derivent_pendant_l_episode():
    panel = pd.DataFrame({"A": [100.0, 200.0], "B": [100.0, 50.0]}, index=jours(2))
    contributions = {
        c.ticker: c for c in position_contributions(panel, {"A": 0.5, "B": 0.5})
    }

    assert contributions["A"].start_weight == pytest.approx(0.5)
    assert contributions["A"].end_weight == pytest.approx(1.0 / 1.25)
    assert contributions["A"].weight_drift > 0.0
    assert contributions["B"].weight_drift < 0.0


# ------------------------------------- Les deux mesures, à ne pas confondre --


def test_le_drawdown_peut_etre_plus_profond_que_le_bout_en_bout():
    """Le pire moment traversé n'est pas ce qu'on retrouve à la sortie."""
    panel = pd.DataFrame(
        {"A": [100.0, 70.0, 95.0], "B": [50.0, 35.0, 47.5]}, index=jours(3)
    )
    valeurs = buy_and_hold_value(panel, {"A": 0.5, "B": 0.5})

    assert end_to_end_return(valeurs) == pytest.approx(-0.05)
    assert max_drawdown(valeurs).value == pytest.approx(-0.30)


def test_le_drawdown_est_celui_du_portefeuille_pas_la_somme_des_pires_points():
    """Chaque ligne touche son plancher un jour différent.

    Composer les pires points individuels fabriquerait un épisode où toutes les
    lignes s'effondrent le même jour — ce qui n'arrive jamais et surestime la
    perte. Ici chaque titre perd 20 % à son propre creux, mais le portefeuille
    n'a jamais perdu plus de 10 %.
    """
    panel = pd.DataFrame(
        {
            "A": [100.0, 80.0, 100.0, 100.0],
            "B": [100.0, 100.0, 100.0, 80.0],
        },
        index=jours(4),
    )
    valeurs = buy_and_hold_value(panel, {"A": 0.5, "B": 0.5})

    assert max_drawdown(panel["A"]).value == pytest.approx(-0.20)
    assert max_drawdown(panel["B"]).value == pytest.approx(-0.20)
    assert max_drawdown(valeurs).value == pytest.approx(-0.10)


# ------------------------------------------------- Contributions par ligne --


def test_les_contributions_somment_au_rendement_de_bout_en_bout():
    panel = pd.DataFrame(
        {"A": [100.0, 60.0], "B": [50.0, 45.0], "C": [200.0, 210.0]},
        index=jours(2),
    )
    poids = {"A": 0.45, "B": 0.35, "C": 0.20}

    total = end_to_end_return(buy_and_hold_value(panel, poids))
    contributions = position_contributions(panel, poids)

    assert sum(c.contribution for c in contributions) == pytest.approx(total)
    assert total == pytest.approx(0.45 * -0.40 + 0.35 * -0.10 + 0.20 * 0.05)


def test_les_contributions_sont_triees_de_la_pire_a_la_meilleure():
    panel = pd.DataFrame({"A": [100.0, 50.0], "B": [100.0, 120.0]}, index=jours(2))
    contributions = position_contributions(panel, {"A": 0.5, "B": 0.5})
    assert [c.ticker for c in contributions] == ["A", "B"]


def test_une_petite_ligne_qui_s_effondre_pese_peu():
    # Rendement propre catastrophique, contribution marginale : c'est la
    # distinction qui rend le résultat actionnable.
    panel = pd.DataFrame(
        {"GROSSE": [100.0, 95.0], "PETITE": [10.0, 1.0]}, index=jours(2)
    )
    contributions = {
        c.ticker: c
        for c in position_contributions(panel, {"GROSSE": 0.99, "PETITE": 0.01})
    }

    assert contributions["PETITE"].own_return == pytest.approx(-0.90)
    assert contributions["PETITE"].contribution == pytest.approx(-0.009)
    assert contributions["GROSSE"].contribution == pytest.approx(-0.0495)


# ----------------------------------------------------- Couverture, en base --


@pytest.fixture
def conn(tmp_path):
    chemin = tmp_path / "stress.sqlite"
    init_db(chemin)
    connexion = connect(chemin)
    yield connexion
    connexion.close()


SCENARIO_TEST = Scenario(
    key="test",
    name="Episode de test",
    start=date(2020, 1, 6),
    end=date(2020, 1, 17),
    benchmark="SPY",
    description="Fenêtre synthétique pour les tests.",
)


def seances(n: int, depart: date = date(2020, 1, 6)) -> list[date]:
    resultat, jour = [], depart
    while len(resultat) < n:
        if jour.weekday() < 5:
            resultat.append(jour)
        jour += timedelta(days=1)
    return resultat


def peupler(conn, ajustes, positions, bruts=None):
    """Portefeuille id 1. `ajustes` alimente adj_close ; `bruts`, s'il est
    fourni, alimente close (sinon close = adj_close)."""
    conn.execute("INSERT INTO portfolios (owner) VALUES ('test')")
    for ticker, serie in ajustes.items():
        conn.execute(
            "INSERT INTO securities (ticker, name) VALUES (?, ?)", (ticker, ticker)
        )
        closes = dict((bruts or {}).get(ticker, serie))
        for jour, ajuste in serie:
            conn.execute(
                "INSERT INTO prices (ticker, date, close, adj_close) VALUES (?,?,?,?)",
                (ticker, jour.isoformat(), closes[jour], ajuste),
            )
    for ticker, quantite in positions.items():
        conn.execute(
            "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1,?,?)",
            (ticker, quantite),
        )
    conn.commit()
    return 1


def test_le_rejeu_en_base_part_des_poids_actuels_en_valeur_de_marche(conn):
    """Le test qui attrape l'erreur de convention sur données en base.

    A valait 10 au début de la fenêtre et vaut 100 aujourd'hui ; B est stable.
    Avec des quantités égales, A pèse aujourd'hui ~91 %. Le rejeu doit partir
    de ces 91 %, et non des ~50 % que donneraient les quantités d'aujourd'hui
    appliquées aux cours de début de fenêtre.
    """
    j = seances(10)
    j_aujourd_hui = seances(1, date(2026, 9, 9))[0]
    peupler(
        conn,
        {
            "A": [(d, 10.0 + i) for i, d in enumerate(j)] + [(j_aujourd_hui, 100.0)],
            "B": [(d, 10.0) for d in j] + [(j_aujourd_hui, 10.0)],
        },
        {"A": 1, "B": 1},
    )
    actuels = market_value_weights(conn, 1).weights
    resultat = run_scenario(conn, 1, SCENARIO_TEST)
    depart = {c.ticker: c.start_weight for c in resultat.contributions}

    assert actuels["A"] == pytest.approx(100.0 / 110.0)
    assert depart["A"] == pytest.approx(actuels["A"])
    assert depart["B"] == pytest.approx(actuels["B"])


def test_une_couverture_complete_est_signalee_comme_telle(conn):
    j = seances(10)
    peupler(
        conn,
        {
            "A": [(d, 100.0 - i) for i, d in enumerate(j)],
            "B": [(d, 50.0 - i * 0.5) for i, d in enumerate(j)],
        },
        {"A": 10, "B": 20},
    )
    resultat = run_scenario(conn, 1, SCENARIO_TEST)

    assert resultat.coverage.is_complete
    assert resultat.coverage.covered_count == resultat.coverage.total_count == 2
    assert resultat.coverage.value_share == pytest.approx(1.0)
    assert "portefeuille complet" in resultat.summary()


def test_une_ligne_sans_historique_sur_la_fenetre_est_declaree_pas_ignoree(conn):
    """Le cas que les 14 titres de dev masquent.

    B n'existe qu'à partir du milieu de la fenêtre : le scénario ne peut rien
    dire de lui. L'exclure en silence sous-estimerait la perte sans que
    personne ne le voie — d'où la déclaration explicite de la couverture.
    """
    j = seances(10)
    peupler(
        conn,
        {
            "A": [(d, 100.0 - i) for i, d in enumerate(j)],
            "B": [(d, 50.0) for d in j[5:]],  # introduit en cours de fenêtre
        },
        {"A": 10, "B": 40},
    )
    resultat = run_scenario(conn, 1, SCENARIO_TEST)
    couverture = resultat.coverage

    assert not couverture.is_complete
    assert couverture.covered == ("A",)
    assert (couverture.covered_count, couverture.total_count) == (1, 2)
    assert [e.ticker for e in couverture.excluded] == ["B"]
    assert "après l'ouverture" in couverture.excluded[0].reason
    assert couverture.excluded[0].first_available == j[5]

    # Un chiffre reste produit, mais sur une part déclarée de la valeur.
    assert resultat.end_to_end_return is not None
    assert couverture.value_share == pytest.approx(910.0 / (910.0 + 2000.0))
    assert "de la valeur seulement" in resultat.summary()
    assert "portefeuille complet" not in resultat.summary()


def test_une_ligne_exclue_n_est_pas_supposee_stable(conn):
    """La perte ne doit pas être diluée dans une valeur non rejouée.

    A (couverte) perd 50 % ; B (exclue) pèse la moitié du portefeuille. Prêter à
    B un rendement nul afficherait −25 % pour tout le portefeuille : une
    sous-estimation silencieuse. Le résultat porte sur la partie couverte
    (−50 %), avec sa portée déclarée (50 % de la valeur).
    """
    j = seances(10)
    peupler(
        conn,
        {
            "A": [(d, 100.0 - 50.0 * i / 9) for i, d in enumerate(j)],
            "B": [(d, 50.0) for d in j[5:]],
        },
        {"A": 1, "B": 1},
    )
    resultat = run_scenario(conn, 1, SCENARIO_TEST)

    assert resultat.end_to_end_return == pytest.approx(-0.50)
    assert resultat.coverage.value_share == pytest.approx(0.5)


def test_la_couverture_se_compte_en_valeur_pas_en_nombre_de_lignes(conn):
    # Une ligne exclue sur deux, mais elle pèse ~95 % de la valeur : dire
    # « 1 ligne sur 2 » masquerait la portée réelle du trou.
    j = seances(10)
    peupler(
        conn,
        {"PETITE": [(d, 10.0) for d in j], "GROSSE": [(d, 100.0) for d in j[5:]]},
        {"PETITE": 20, "GROSSE": 40},
    )
    couverture = assess_scenario_coverage(conn, 1, SCENARIO_TEST)

    assert couverture.covered_count == 1
    assert couverture.value_share == pytest.approx(200.0 / 4200.0)


def test_sans_aucune_ligne_couverte_aucun_chiffre_n_est_produit(conn):
    """Mieux vaut pas de chiffre qu'un chiffre fabriqué."""
    j = seances(10, date(2021, 6, 1))  # entièrement après la fenêtre
    peupler(conn, {"A": [(d, 100.0) for d in j]}, {"A": 10})

    resultat = run_scenario(conn, 1, SCENARIO_TEST)

    assert resultat.end_to_end_return is None
    assert resultat.max_drawdown is None
    assert resultat.contributions == ()
    assert resultat.coverage.value_share == 0.0
    assert "aucune ligne" in resultat.unavailable_reason
    assert "non calculable" in resultat.summary()


def test_le_scenario_utilise_adj_close_et_non_close(conn):
    """Sur la fenêtre, close reste plat pendant qu'adj_close baisse de 45 %.

    Un calcul fondé sur close rendrait 0 % ; seul adj_close donne la trajectoire
    de performance totale attendue.
    """
    j = seances(10)
    peupler(
        conn,
        {"A": [(d, 100.0 - i * 5) for i, d in enumerate(j)]},
        {"A": 1},
        bruts={"A": [(d, 100.0) for d in j]},
    )
    resultat = run_scenario(conn, 1, SCENARIO_TEST)

    assert resultat.end_to_end_return == pytest.approx(55.0 / 100.0 - 1.0)


def test_un_scenario_hors_catalogue_fonctionne_sans_toucher_a_la_logique(conn):
    """Les scénarios sont des données : en ajouter un ne demande aucun code."""
    j = seances(10)
    peupler(conn, {"A": [(d, 100.0 - i) for i, d in enumerate(j)]}, {"A": 10})

    maison = Scenario(
        key="maison",
        name="Episode inventé",
        start=date(2020, 1, 6),
        end=date(2020, 1, 15),
        benchmark="SPY",
        description="Défini à la volée, hors du catalogue.",
    )
    resultat = run_scenario(conn, 1, maison)

    assert resultat.scenario.key == "maison"
    assert resultat.end_to_end_return is not None


# --------------------------------------------- Bout en bout, données réelles --


@besoin_de_la_base
def test_les_trois_scenarios_tournent_sur_un_portefeuille_reel(tmp_path):
    """Rejeu complet sur une COPIE de la base : rien n'est écrit dans la vraie."""
    copie = tmp_path / "copie.sqlite"
    shutil.copy(BASE_REELLE, copie)

    with closing(connect(copie)) as conn:
        conn.execute("INSERT INTO portfolios (owner) VALUES ('test')")
        pid = conn.execute("SELECT MAX(id) FROM portfolios").fetchone()[0]
        for ticker, quantite in {"AAPL": 40, "JPM": 60, "KO": 120}.items():
            conn.execute(
                "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (?,?,?)",
                (pid, ticker, quantite),
            )
        conn.commit()
        actuels = market_value_weights(conn, pid).weights
        resultats = run_all_scenarios(conn, pid)

    assert [r.scenario.key for r in resultats] == list(AMPLITUDES_ATTENDUES)
    for r in resultats:
        assert r.coverage.is_complete, "les 14 titres de dev couvrent tout depuis 2005"
        assert r.end_to_end_return < 0.0, "les trois épisodes sont des baisses"
        assert r.max_drawdown.value <= r.end_to_end_return + 1e-12
        assert sum(c.contribution for c in r.contributions) == pytest.approx(
            r.end_to_end_return
        )
        for c in r.contributions:
            assert c.start_weight == pytest.approx(actuels[c.ticker]), (
                f"{r.scenario.key} : {c.ticker} doit entrer dans l'épisode à son poids actuel"
            )
