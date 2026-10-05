"""Tests de la couche qui touche SQLite et de la composition des mesures.

Les mesures elles-mêmes sont testées dans `test_risk_measures.py`, sans base.
Ici on vérifie le chargement, les poids, l'alignement des dates et le fait que
chaque résultat porte bien sa fenêtre.

Le dernier test est une non-régression sur données RÉELLES : il ne tourne que
si la base locale existe, et se saute proprement sur un clone frais.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from backend.db.init_db import connect, init_db
from backend.risk_engine.config import (
    DEFAULT_RISK_FREE_RATE,
    MAX_STUDENT_NU,
    MIN_SCENARIO_COVERAGE_SHARE,
    RISK_FREE_RATE_OBSERVED_ON,
)
from backend.risk_engine.engine import (
    ExcludedPosition,
    LimitingPosition,
    RegimeComparison,
    RegressedBeta,
    ScenarioCoverage,
    Window,
    analyse_portfolio,
    benchmark_name,
    build_portfolio_series,
    concentration,
    period_label,
    run_scenario,
    student_fit,
)
from backend.risk_engine.scenarios import SCENARIOS, Scenario
from backend.typography import NARROW_NBSP, NBSP, cardinal
from backend.risk_engine.var import fit_student_t
from backend.risk_engine.measures import max_drawdown
from backend.risk_engine.portfolio import (
    PortfolioError,
    latest_price_date,
    load_price_panel,
    load_securities,
    market_value_weights,
)
from backend.risk_engine.returns import simple_returns, wealth_curve

@pytest.fixture
def conn(tmp_path):
    chemin = tmp_path / "risque.sqlite"
    init_db(chemin)
    connexion = connect(chemin)
    yield connexion
    connexion.close()


def seances(n: int, depart: date = date(2026, 1, 5)) -> list[date]:
    """`n` dates ouvrées consécutives."""
    resultat, jour = [], depart
    while len(resultat) < n:
        if jour.weekday() < 5:
            resultat.append(jour)
        jour += timedelta(days=1)
    return resultat


def cours(dates, initial=100.0, sigma=0.01, derive=0.0002, graine=1):
    """Serie de cours par composition de rendements successifs.

    Un `(1 + tirage) ** i` eleverait UN seul tirage a la puissance i : la serie
    exploserait ou s'effondrerait au lieu de suivre une marche aleatoire.
    """
    import numpy as np

    rng = np.random.default_rng(graine)
    rendements = rng.normal(derive, sigma, len(dates))
    niveaux = initial * np.cumprod(1.0 + rendements)
    return [(d, float(v)) for d, v in zip(dates, niveaux, strict=True)]


def cours_student(dates, initial=100.0, sigma=0.01, derive=0.0002, graine=1, nu=4):
    """Comme `cours`, avec des innovations de Student à ν degrés de liberté,
    ramenées au même écart-type σ.

    Une Student à ν degrés de liberté a pour variance ν/(ν − 2) : le facteur
    √((ν − 2)/ν) la ramène à 1. Des rendements NORMAUX ne se prêtent pas à
    l'ajustement d'une Student — le maximum de vraisemblance y pousse ν vers
    l'infini, et le moteur refuse l'ajustement au-delà de `MAX_STUDENT_NU`.
    Un test qui veut un volet Student a besoin de queues épaisses.
    """
    rng = np.random.default_rng(graine)
    tirages = rng.standard_t(nu, len(dates))
    rendements = derive + sigma * np.sqrt((nu - 2) / nu) * tirages
    niveaux = initial * np.cumprod(1.0 + rendements)
    return [(d, float(v)) for d, v in zip(dates, niveaux, strict=True)]


def peupler(conn, prix, positions, adj=None):
    """Crée un portefeuille (id 1) avec ses titres, prix et lignes.

    `prix` : {ticker: [(date, close), ...]}. `adj` permet de dissocier
    `adj_close` de `close` pour tester lequel sert à quoi.
    """
    conn.execute("INSERT INTO portfolios (owner) VALUES ('test')")
    for ticker, serie in prix.items():
        conn.execute(
            "INSERT INTO securities (ticker, name) VALUES (?, ?)", (ticker, ticker)
        )
        for jour, close in serie:
            ajuste = (adj or {}).get(ticker, {}).get(jour, close)
            conn.execute(
                "INSERT INTO prices (ticker, date, close, adj_close) "
                "VALUES (?, ?, ?, ?)",
                (ticker, jour.isoformat(), close, ajuste),
            )
    for ticker, quantite in positions.items():
        conn.execute(
            "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1, ?, ?)",
            (ticker, quantite),
        )
    conn.commit()
    return 1


# ------------------------------------------------------------------- Poids --


def test_les_poids_sont_en_valeur_pas_en_nombre_de_titres(conn):
    # Même quantité, prix dix fois différents : les poids doivent refléter la
    # valeur, sinon deux lignes de 10 titres pèseraient identiquement.
    jour = seances(1)[0]
    peupler(
        conn,
        {"CHER": [(jour, 500.0)], "PASCHER": [(jour, 50.0)]},
        {"CHER": 10, "PASCHER": 10},
    )
    poids = market_value_weights(conn, 1)

    assert poids.weights["CHER"] == pytest.approx(5000 / 5500)
    assert poids.weights["PASCHER"] == pytest.approx(500 / 5500)
    assert poids.total_value == pytest.approx(5500.0)


def test_les_poids_somment_a_un(conn):
    jour = seances(1)[0]
    peupler(
        conn,
        {"A": [(jour, 12.3)], "B": [(jour, 45.6)], "C": [(jour, 7.8)]},
        {"A": 3, "B": 11, "C": 42},
    )
    assert sum(market_value_weights(conn, 1).weights.values()) == pytest.approx(1.0)


def test_les_poids_utilisent_la_derniere_cloture(conn):
    j = seances(3)
    peupler(
        conn,
        {"A": [(j[0], 10.0), (j[1], 20.0), (j[2], 100.0)]},
        {"A": 2},
    )
    poids = market_value_weights(conn, 1)

    assert poids.total_value == pytest.approx(200.0), "dernière clôture, pas la 1re"
    assert poids.as_of == j[2]


def test_les_poids_utilisent_close_et_non_adj_close(conn):
    # adj_close est un indice de performance totale rebasé, pas un prix
    # traitable : valoriser un portefeuille avec lui n'aurait pas de sens.
    jour = seances(1)[0]
    peupler(
        conn,
        {"A": [(jour, 100.0)]},
        {"A": 1},
        adj={"A": {jour: 42.0}},
    )
    assert market_value_weights(conn, 1).total_value == pytest.approx(100.0)


def test_un_portefeuille_inexistant_leve_une_erreur(conn):
    with pytest.raises(PortfolioError, match="introuvable"):
        market_value_weights(conn, 999)


def test_un_portefeuille_sans_position_leve_une_erreur(conn):
    conn.execute("INSERT INTO portfolios (owner) VALUES ('vide')")
    conn.commit()
    with pytest.raises(PortfolioError, match="sans position"):
        market_value_weights(conn, 1)


def test_un_titre_sans_prix_leve_une_erreur(conn):
    conn.execute("INSERT INTO portfolios (owner) VALUES ('test')")
    conn.execute("INSERT INTO securities (ticker, name) VALUES ('A', 'A')")
    conn.execute(
        "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1, 'A', 5)"
    )
    conn.commit()
    with pytest.raises(PortfolioError, match="Aucun prix"):
        market_value_weights(conn, 1)


# ------------------------------------------------------------- Alignement --


def test_le_panel_est_indexe_par_date_et_colonne_par_titre(conn):
    j = seances(2)
    peupler(
        conn,
        {"A": [(j[0], 10.0), (j[1], 11.0)], "B": [(j[0], 20.0), (j[1], 22.0)]},
        {"A": 1, "B": 1},
    )
    panel = load_price_panel(conn, ["A", "B"])

    assert list(panel.columns) == ["A", "B"]
    assert list(panel.index) == j


def test_une_seance_manquante_ne_decale_pas_les_series(conn):
    """Le point que l'alignement positionnel casserait silencieusement.

    B ne cote pas le deuxième jour. Après alignement, les deux séries portent
    sur les mêmes dates (j0 et j2) et leurs rendements couvrent le même
    intervalle. Un appariement par position aurait comparé le rendement j0→j1 de
    A à celui j0→j2 de B, sans que rien ne le signale.
    """
    j = seances(3)
    peupler(
        conn,
        {
            "A": [(j[0], 100.0), (j[1], 110.0), (j[2], 121.0)],
            "B": [(j[0], 50.0), (j[2], 60.0)],
        },
        {"A": 1, "B": 1},
    )
    serie = build_portfolio_series(conn, 1, window=10)

    assert list(serie.asset_returns.index) == [j[2]], "seule la date commune reste"
    assert serie.asset_returns.loc[j[2], "A"] == pytest.approx(0.21)
    assert serie.asset_returns.loc[j[2], "B"] == pytest.approx(0.20)


# --------------------------------------------------------------- Fenêtre --


def test_la_fenetre_borne_le_nombre_d_observations(conn):
    j = seances(60)
    peupler(conn, {"A": [(d, 100.0 + i) for i, d in enumerate(j)]}, {"A": 1})

    serie = build_portfolio_series(conn, 1, window=10)

    assert serie.window.observations == 10
    assert serie.window.requested == 10
    assert serie.window.complete
    assert serie.window.end == j[-1], "la fenêtre se termine à la séance la plus récente"


def test_une_fenetre_plus_longue_que_l_historique_est_signalee(conn):
    j = seances(20)
    peupler(conn, {"A": [(d, 100.0 + i) for i, d in enumerate(j)]}, {"A": 1})

    fenetre = build_portfolio_series(conn, 1, window=504).window

    assert fenetre.observations == 19, "20 prix donnent 19 rendements"
    assert fenetre.requested == 504
    assert not fenetre.complete, "une fenêtre incomplète ne doit pas passer inaperçue"


def test_chaque_mesure_porte_sa_fenetre(conn):
    j = seances(40)
    peupler(
        conn,
        {
            "A": [(d, 100.0 * (1.001**i)) for i, d in enumerate(j)],
            "B": [(d, 50.0 * (0.999**i)) for i, d in enumerate(j)],
        },
        {"A": 10, "B": 20},
    )
    rapport = analyse_portfolio(
        conn, 1, window=30, benchmark=None)

    for mesure in (
        rapport.volatility,
        rapport.ewma_volatility,
        rapport.drawdown,
        rapport.sharpe,
        rapport.sortino,
    ):
        assert isinstance(mesure.window, Window)
        assert mesure.window.observations == 30
        assert mesure.window.requested == 30


def test_une_fenetre_trop_courte_est_refusee(conn):
    j = seances(5)
    peupler(conn, {"A": [(d, 100.0 + i) for i, d in enumerate(j)]}, {"A": 1})
    with pytest.raises(ValueError, match="Fenêtre trop courte"):
        build_portfolio_series(conn, 1, window=1)


def test_deux_seances_communes_ne_font_pas_un_rapport(conn):
    """Deux séances ne donnent qu'un rendement : aucune dispersion n'existe.

    La SÉRIE existe — l'alignement des dates se vérifie sur un rendement
    unique, plus haut —, mais le RAPPORT non. Le refus est une
    `PortfolioError`, l'état de la base, et non la `ValueError` que levait la
    mesure plus loin et que l'API rendait comme un refus de la requête. Le
    message dit ce qui a été reçu et ce qu'il faut.
    """
    communes = 2
    j = seances(10)
    peupler(
        conn,
        {
            "A": [(d, 100.0 + i) for i, d in enumerate(j)],
            # B n'est coté que sur les deux dernières séances de A.
            "B": [(d, 50.0 + i) for i, d in enumerate(j[-communes:])],
        },
        {"A": 1, "B": 1},
    )
    assert build_portfolio_series(conn, 1, window=504).window.observations == 1
    with pytest.raises(PortfolioError, match="il en faut au moins 3") as refus:
        analyse_portfolio(conn, 1, window=504, benchmark=None)
    assert f"{communes}\u00a0séance" in str(refus.value)
    assert "2\u00a0rendements" in str(refus.value)


def test_trois_seances_communes_suffisent(conn):
    """La frontière : trois cotations en commun, deux rendements, un rapport."""
    j = seances(10)
    peupler(
        conn,
        {
            "A": [(d, 100.0 + i) for i, d in enumerate(j)],
            "B": [(d, 50.0 + i) for i, d in enumerate(j[-3:])],
        },
        {"A": 1, "B": 1},
    )
    rapport = analyse_portfolio(conn, 1, window=504, benchmark=None)
    assert rapport.window.observations == 2


# ------------------------------------------------------------- Composition --


def test_les_poids_actuels_s_appliquent_a_tout_l_historique(conn):
    """Hypothèse de poids constants (rééquilibrage quotidien).

    A est plat à 100, B monte de 1 % par séance et finit à 100 × 1,01⁹. Les
    poids d'AUJOURD'HUI s'appliquent à toute la série, y compris aux dates
    anciennes où B pesait moins qu'aujourd'hui. Le rendement de chaque séance
    vaut donc w_A × 0 % + w_B × 1 %, avec les mêmes poids partout.
    """
    j = seances(10)
    prix_final_b = 100.0 * (1.01**9)
    peupler(
        conn,
        {
            "A": [(d, 100.0) for d in j],
            "B": [(d, 100.0 * (1.01**i)) for i, d in enumerate(j)],
        },
        {"A": 1, "B": 1},
    )
    serie = build_portfolio_series(conn, 1, window=20)

    total = 100.0 + prix_final_b
    assert serie.weights.weights["A"] == pytest.approx(100.0 / total)
    assert serie.weights.weights["B"] == pytest.approx(prix_final_b / total)

    attendu = (prix_final_b / total) * 0.01
    # Poids constants : la MÊME valeur sur toutes les séances, pas seulement la
    # dernière. Des poids dérivants donneraient une série croissante.
    assert serie.returns.to_numpy() == pytest.approx(attendu, rel=1e-9)


def test_le_hhi_d_un_portefeuille_equipondere_en_valeur(conn):
    # Quatre lignes de même valeur de marché malgré des prix et quantités
    # différents : le HHI doit ressortir exactement à 1/4.
    jour = seances(1)[0]
    peupler(
        conn,
        {
            "A": [(jour, 100.0)],
            "B": [(jour, 50.0)],
            "C": [(jour, 25.0)],
            "D": [(jour, 10.0)],
        },
        {"A": 1, "B": 2, "C": 4, "D": 10},
    )
    resultat = concentration(market_value_weights(conn, 1))

    assert resultat.hhi == pytest.approx(0.25)
    assert resultat.equal_weight_reference == pytest.approx(0.25)
    assert resultat.effective_positions == pytest.approx(4.0)
    assert resultat.n_positions == 4


def test_le_rapport_expose_toutes_les_mesures_du_bloc(conn):
    j = seances(40)
    peupler(
        conn,
        {
            "A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)],
            "B": [(d, 80.0 * (1.0 - 0.001 * (i % 7))) for i, d in enumerate(j)],
        },
        {"A": 5, "B": 9},
    )
    rapport = analyse_portfolio(
        conn, 1, window=30, benchmark=None)

    assert rapport.volatility.annualised >= 0.0
    assert rapport.ewma_volatility.method.startswith("EWMA")
    assert rapport.drawdown.peak_date <= rapport.drawdown.trough_date
    assert rapport.sharpe.risk_free_annual > 0.0
    assert rapport.sortino.annualised is not None or rapport.sortino.undefined_reason
    assert rapport.concentration.hhi >= rapport.concentration.equal_weight_reference
    assert rapport.total_value > 0.0


def test_le_taux_sans_risque_est_un_parametre_pas_une_constante_enfouie(conn):
    j = seances(40)
    peupler(conn, {"A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)]}, {"A": 1})

    sans_taux = analyse_portfolio(
        conn, 1, window=30, benchmark=None, annual_risk_free=0.0)
    avec_taux = analyse_portfolio(
        conn, 1, window=30, benchmark=None, annual_risk_free=0.10)

    assert avec_taux.sharpe.annualised < sans_taux.sharpe.annualised
    assert avec_taux.sharpe.risk_free_annual == 0.10
    assert avec_taux.sharpe.risk_free_daily == pytest.approx(
        1.10 ** (1 / 252) - 1, rel=1e-9
    )


# --------------------------------------------- Non-régression, données réelles --


def test_regression_le_drawdown_de_spy_pendant_le_covid_reste_a_moins_33_7_pct(
    base_figee_partagee,
):
    """Ancrage sur l'histoire réelle, pas sur une valeur inventée.

    Le S&P 500 a perdu environ 34 % entre son sommet du 19 février 2020 et son
    creux du 23 mars. Ce test traverse toute la chaîne — lecture des cours
    ajustés, rendements simples, courbe de valeur, drawdown à pic glissant — et
    tombera si l'une de ces étapes est modifiée de travers, même de façon
    subtile (rendements log au lieu de simples, `close` au lieu d'`adj_close`,
    pic global au lieu de glissant).
    """
    connexion = connect(base_figee_partagee)
    try:
        panel = load_price_panel(
            connexion, ["SPY"], date(2020, 2, 19), date(2020, 3, 23)
        )
    finally:
        connexion.close()

    prix = panel["SPY"]
    courbe = wealth_curve(simple_returns(prix), initial_date=prix.index[0])
    resultat = max_drawdown(courbe)

    assert resultat.value == pytest.approx(-0.337, abs=0.002)
    assert resultat.peak_date == date(2020, 2, 19)
    assert resultat.trough_date == date(2020, 3, 23)


# ----------------------------------------------- Provenance des résultats --


def test_le_taux_par_defaut_est_l_equivalent_coupon_source_et_date():
    """Le taux n'est ni inventé ni orphelin de sa date.

    L'équivalent coupon rapporte le gain au prix payé sur base 365 ; le taux
    d'escompte le rapporte à la valeur faciale sur base 360 et ressort plus bas.
    Retenir l'escompte donnerait un Sharpe flatteur sans qu'aucun calcul ne soit
    faux — d'où la vérification que la constante est bien celle attendue.
    """
    assert DEFAULT_RISK_FREE_RATE == pytest.approx(0.0390)
    assert RISK_FREE_RATE_OBSERVED_ON == date(2026, 9, 9)


def test_le_sharpe_transporte_la_date_d_observation_du_taux(conn):
    j = seances(40)
    peupler(conn, {"A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)]}, {"A": 1})

    rapport = analyse_portfolio(
        conn, 1, window=30, benchmark=None)

    assert rapport.sharpe.risk_free_annual == pytest.approx(0.0390)
    assert rapport.sharpe.risk_free_observed_on == RISK_FREE_RATE_OBSERVED_ON


def test_un_taux_surcharge_n_a_pas_de_date_d_observation(conn):
    # Le moteur ne sait pas d'où vient un taux qu'on lui impose : lui attribuer
    # la date du défaut serait une provenance fausse.
    j = seances(40)
    peupler(conn, {"A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)]}, {"A": 1})

    rapport = analyse_portfolio(
        conn, 1, window=30, benchmark=None, annual_risk_free=0.02)

    assert rapport.sharpe.risk_free_annual == 0.02
    assert rapport.sharpe.risk_free_observed_on is None


def test_la_concentration_porte_sa_date_de_valorisation(conn):
    """Provenance d'une mesure ponctuelle.

    Pas de fenêtre d'estimation — le HHI ne s'estime pas sur un historique —
    mais la date des prix qui ont servi aux poids, sans laquelle un HHI de 0,18
    ne dit pas s'il décrit le portefeuille d'aujourd'hui ou celui d'il y a six
    mois. Le champ se nomme `as_of`, comme partout ailleurs pour ce concept.
    """
    j = seances(3)
    peupler(
        conn,
        {
            "A": [(d, 100.0) for d in j],
            "B": [(d, 100.0) for d in j],
        },
        {"A": 1, "B": 1},
    )
    resultat = concentration(market_value_weights(conn, 1))

    assert resultat.as_of == j[-1], "la dernière clôture, pas la première"
    assert not hasattr(resultat, "window"), "une mesure ponctuelle n'a pas de fenêtre"


def test_le_hhi_leve_sur_un_poids_negatif_mais_les_autres_mesures_tiennent(conn):
    """La levée est au moteur ; c'est la présentation (Phase 7) qui rattrape.

    Une position vendeuse rend le HHI ininterprétable, mais volatilité,
    drawdown, Sharpe et Sortino restent parfaitement valides. Ce test fige le
    contrat sur lequel la couche de présentation s'appuiera.
    """
    j = seances(40)
    peupler(
        conn,
        {
            "A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)],
            "B": [(d, 50.0) for d in j],
        },
        {"A": 10, "B": -4},  # vente à découvert
    )
    serie = build_portfolio_series(conn, 1, window=30)

    with pytest.raises(ValueError, match="longues"):
        concentration(serie.weights)

    from backend.risk_engine.engine import drawdown, sharpe, volatility

    assert volatility(serie).annualised >= 0.0
    assert drawdown(serie).value <= 0.0
    assert sharpe(serie).annualised is not None


def test_un_taux_impose_peut_porter_sa_propre_date_d_observation(conn):
    """La provenance voyage quand elle est connue.

    Sans ce paramètre, `None` recouvrait deux situations distinctes : personne
    ne connaît la date, ou bien elle est connue de l'appelant mais le moteur n'a
    aucun moyen de la recevoir. Le second cas disparaît.
    """
    j = seances(40)
    peupler(conn, {"A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)]}, {"A": 1})

    observe = date(2026, 3, 31)
    rapport = analyse_portfolio(
        conn, 1, window=30, benchmark=None, annual_risk_free=0.045, risk_free_observed_on=observe,
    )

    assert rapport.sharpe.risk_free_annual == 0.045
    assert rapport.sharpe.risk_free_observed_on == observe


def test_dater_le_taux_par_defaut_est_refuse(conn):
    # Le défaut porte déjà sa provenance : la remplacer serait affirmer sur
    # cette valeur quelque chose qui n'est pas vrai.
    j = seances(40)
    peupler(conn, {"A": [(d, 100.0 * (1.002**i)) for i, d in enumerate(j)]}, {"A": 1})
    serie = build_portfolio_series(conn, 1, window=30)

    from backend.risk_engine.engine import sharpe

    with pytest.raises(ValueError, match="risk_free_observed_on"):
        sharpe(serie, risk_free_observed_on=date(2020, 1, 1))


# ------------------------------------------------- Bloc 4B : multi-titres --


def test_la_volatilite_parametrique_egale_celle_de_la_serie(conn):
    """L'identité du ddof, vérifiée bout en bout depuis la base.

    √(wᵀΣw) et l'écart-type de la série du portefeuille sont la même quantité
    calculée par deux chemins. Une divergence de convention entre 4A et 4B
    introduirait un écart de N/(N−1) — 0,1 % sur 504 séances, indétectable à
    l'œil et faux quand même.
    """
    j = seances(120)
    peupler(
        conn,
        {
            "A": cours(j, 100.0, 0.010, graine=1),
            "B": cours(j, 50.0, 0.012, graine=2),
            "C": cours(j, 80.0, 0.008, graine=3),
        },
        {"A": 10, "B": 20, "C": 15},
    )
    serie = build_portfolio_series(conn, 1, window=100)

    from backend.risk_engine.engine import parametric_volatility, volatility

    assert parametric_volatility(serie).annualised == pytest.approx(
        volatility(serie).annualised, rel=1e-12
    )


def test_un_portefeuille_100_pct_benchmark_a_un_beta_de_un(conn):
    """Le test décisif du beta, depuis la base : β et R² exactement 1."""
    j = seances(60)
    peupler(conn, {"SPY": cours(j, 400.0, 0.010, graine=9)}, {"SPY": 10})

    rapport = analyse_portfolio(conn, 1, window=50, benchmark="SPY")

    assert rapport.beta.beta == 1.0
    assert rapport.beta.r_squared == 1.0
    assert rapport.beta.idiosyncratic_share == 0.0
    assert rapport.beta.benchmark == "SPY"
    assert "bruts" in rapport.beta.basis


def test_le_benchmark_est_aligne_dans_le_meme_panel(conn):
    """Sans quoi le beta comparerait des intervalles différents.

    B ne cote pas le deuxième jour. Le rendement du portefeuille au jour 3
    couvre donc j1→j3 ; celui du benchmark doit couvrir le même intervalle, pas
    j2→j3.
    """
    j = seances(3)
    peupler(
        conn,
        {
            "A": [(j[0], 100.0), (j[1], 110.0), (j[2], 121.0)],
            "B": [(j[0], 50.0), (j[2], 60.0)],
            "SPY": [(j[0], 400.0), (j[1], 404.0), (j[2], 420.0)],
        },
        {"A": 1, "B": 1},
    )
    serie = build_portfolio_series(conn, 1, window=10, benchmark="SPY")

    assert list(serie.benchmark_returns.index) == [j[2]]
    assert serie.benchmark_returns.loc[j[2]] == pytest.approx(420.0 / 400.0 - 1.0), (
        "le benchmark doit couvrir j1→j3 comme le portefeuille, pas j2→j3"
    )


def test_un_benchmark_absent_de_la_base_est_signale_clairement(conn):
    # Les titres détenus ont des prix, le benchmark non : le cas passerait au
    # travers d'un contrôle qui ne vérifie que « le panel est-il vide ».
    j = seances(30)
    peupler(conn, {"A": cours(j, graine=4)}, {"A": 1})

    with pytest.raises(PortfolioError, match="SPY"):
        build_portfolio_series(conn, 1, window=20, benchmark="SPY")


def test_l_analyse_sans_benchmark_omet_le_beta(conn):
    j = seances(40)
    peupler(conn, {"A": cours(j, graine=5)}, {"A": 1})

    rapport = analyse_portfolio(conn, 1, window=30, benchmark=None)
    assert rapport.beta is None
    assert rapport.historical_var[0.95] is not None


def test_le_rapport_expose_les_var_aux_deux_niveaux(conn):
    j = seances(200)
    peupler(
        conn,
        {"A": cours(j, 100.0, 0.012, graine=4), "SPY": cours(j, 400.0, 0.009, graine=6)},
        {"A": 10},
    )
    rapport = analyse_portfolio(conn, 1, window=150)

    for famille in (rapport.historical_var, rapport.parametric_var):
        assert famille[0.99].value >= famille[0.95].value, "99 % ≥ 95 % en perte"
        assert famille[0.95].window.observations == 150
        assert famille[0.95].value > 0.0, "convention : perte positive"

    for niveau in (0.95, 0.99):
        es = rapport.expected_shortfall[niveau]
        assert es.value >= rapport.historical_var[niveau].value, "CVaR ≥ VaR"
        assert es.tail_observations > 0


def test_le_cvar_a_99_porte_son_avertissement_en_permanence(conn):
    """La fragilité du CVaR à 99 % est lisible dans la sortie, attachée au chiffre.

    Sur 250 séances, le 95 % moyenne une douzaine de points quand le 99 % n'en
    moyenne que trois. À 99 %, la queue est courte par construction : ce n'est
    pas une anomalie à détecter, l'avertissement accompagne donc toujours le
    chiffre plutôt que de se déclencher.
    """
    j = seances(300)
    peupler(
        conn,
        {"A": cours(j, 100.0, 0.012, graine=7), "SPY": cours(j, 400.0, 0.009, graine=8)},
        {"A": 10},
    )
    rapport = analyse_portfolio(conn, 1, window=250)

    fin = rapport.expected_shortfall[0.99]
    large = rapport.expected_shortfall[0.95]

    assert fin.tail_observations < large.tail_observations
    assert fin.caveat.startswith(f"Moyenne de {fin.tail_observations} séances seulement")
    assert large.caveat is None


# ------------------------------------------------- Estimations minces --
#
# Sous 30 séances (seuil choisi), la volatilité et la VaR paramétrique normale
# restent publiées — elles bougent avec les données — mais portent une réserve.


def _rapport_sur(conn, rendements):
    j = seances(rendements + 1)
    peupler(conn, {"A": cours(j, 100.0, 0.012, graine=4)}, {"A": 10})
    rapport = analyse_portfolio(conn, 1, window=504, benchmark=None)
    assert rapport.window.observations == rendements
    return rapport


def test_sous_trente_seances_volatilite_et_var_normale_sont_marquees_minces(conn):
    rapport = _rapport_sur(conn, 29)

    marquees = [
        rapport.volatility,
        rapport.ewma_volatility,
        rapport.parametric_volatility,
        *rapport.parametric_var.values(),
    ]
    for mesure in marquees:
        assert mesure.caveat == (
            "Estimation mince : 29\u00a0séances seulement, moins que les 30 "
            "retenues pour estimer une loi (seuil choisi à la main). Quelques "
            "séances suffisent à déplacer ce chiffre, et le moteur de règles "
            "n'en tire aucune conclusion."
        )
        # Marquée, pas refusée : le chiffre reste là.
        assert mesure.window.observations == 29

    assert rapport.volatility.annualised > 0.0
    assert all(v.value > 0.0 for v in rapport.parametric_var.values())


def test_a_trente_seances_aucune_reserve_d_estimation_mince(conn):
    rapport = _rapport_sur(conn, 30)
    for mesure in (
        rapport.volatility,
        rapport.ewma_volatility,
        rapport.parametric_volatility,
        *rapport.parametric_var.values(),
    ):
        assert mesure.caveat is None


def test_le_seuil_des_estimations_minces_est_celui_de_la_student():
    """Un seul nombre pour les deux décisions : sous lui, ni loi de Student
    ajustée, ni volatilité sans réserve."""
    from backend.risk_engine import var
    from backend.risk_engine.config import MIN_DISTRIBUTION_OBSERVATIONS

    assert var.STUDENT_MIN_OBSERVATIONS == MIN_DISTRIBUTION_OBSERVATIONS == 30


# ------------------------------------------- Une queue qui contient une séance --
#
# Sous 1/(1 − α) séances — 20 à 95 %, 100 à 99 % —, aucune ne tombe dans la
# queue : la VaR historique et la CVaR du même niveau sont refusées.


@pytest.mark.parametrize(
    "confiance, minimum",
    [(0.95, 20), (0.99, 100)],
)
def test_la_var_historique_et_sa_cvar_sont_refusees_juste_sous_le_minimum(
    conn, confiance, minimum
):
    rapport = _rapport_sur(conn, minimum - 1)
    var_historique = rapport.historical_var[confiance]
    cvar = rapport.expected_shortfall[confiance]

    assert var_historique.value is None
    assert var_historique.method == "historique"
    assert var_historique.window.observations == minimum - 1
    assert cvar.value is None and cvar.threshold is None
    assert cvar.tail_observations is None and cvar.caveat is None
    assert var_historique.undefined_reason.endswith(
        f"il en faut au moins {minimum} pour une VaR historique à "
        f"{int(confiance * 100)}\u202f%."
    )
    assert cvar.undefined_reason.endswith(
        f"il en faut au moins {minimum} pour une CVaR à {int(confiance * 100)}\u202f%."
    )


@pytest.mark.parametrize("confiance, minimum", [(0.95, 20), (0.99, 100)])
def test_au_minimum_la_queue_contient_une_seance_et_les_mesures_sont_publiees(
    conn, confiance, minimum
):
    rapport = _rapport_sur(conn, minimum)
    assert rapport.historical_var[confiance].value is not None
    assert rapport.historical_var[confiance].undefined_reason is None
    cvar = rapport.expected_shortfall[confiance]
    assert cvar.value is not None and cvar.tail_observations >= 1
    assert cvar.undefined_reason is None


def test_la_raison_dit_ce_qui_a_ete_recu_et_ce_qu_il_faut(conn):
    """La phrase de Maxence, à sept séances, aux deux niveaux."""
    rapport = _rapport_sur(conn, 7)
    assert rapport.historical_var[0.99].undefined_reason == (
        "Sur 7\u00a0séances, aucune ne tombe dans le 1\u202f% des pires : il en "
        "faut au moins 100 pour une VaR historique à 99\u202f%."
    )
    assert rapport.historical_var[0.95].undefined_reason == (
        "Sur 7\u00a0séances, aucune ne tombe dans les 5\u202f% des pires : il en "
        "faut au moins 20 pour une VaR historique à 95\u202f%."
    )


def test_le_minimum_d_une_mesure_de_queue_est_un_inverse_arrondi_juste():
    """1 − 0,9 vaut 0,09999999999999998 en flottant : sans arrondi, le plafond
    de 1/(1 − 0,9) donnerait 11."""
    from backend.risk_engine.config import historical_var_min_observations

    assert [historical_var_min_observations(c) for c in (0.9, 0.95, 0.99, 0.999)] == [
        10, 20, 100, 1000,
    ]
    with pytest.raises(ValueError):
        historical_var_min_observations(1.0)


def test_les_matrices_du_rapport_sont_coherentes(conn):
    j = seances(120)
    peupler(
        conn,
        {
            "A": cours(j, 100.0, 0.010, graine=8),
            "B": cours(j, 50.0, 0.011, graine=9),
            "SPY": cours(j, 400.0, 0.009, graine=10),
        },
        {"A": 10, "B": 20},
    )
    rapport = analyse_portfolio(conn, 1, window=100)
    matrices = rapport.matrices

    assert list(matrices.covariance.columns) == ["A", "B"], (
        "le benchmark sert au beta, il n'entre pas dans la matrice des détenus"
    )
    assert (np.diag(matrices.correlation.to_numpy()) == 1.0).all()
    assert matrices.ddof == 1
    assert matrices.window.observations == 100


def test_le_monte_carlo_est_optionnel_et_reproductible(conn):
    j = seances(150)
    peupler(
        conn,
        {
            "A": cours_student(j, 100.0, 0.011, graine=12),
            "B": cours_student(j, 70.0, 0.013, graine=13),
            "SPY": cours(j, 400.0, 0.009, graine=14),
        },
        {"A": 10, "B": 12},
    )
    sans = analyse_portfolio(conn, 1, window=120)
    assert sans.monte_carlo_var is None

    avec = analyse_portfolio(conn, 1, window=120, monte_carlo=True)
    encore = analyse_portfolio(conn, 1, window=120, monte_carlo=True)

    assert avec.monte_carlo_var[0.95].value == encore.monte_carlo_var[0.95].value
    assert "graine" in avec.monte_carlo_var[0.95].detail


def test_le_rapport_porte_l_ajustement_student_et_nu_dans_chaque_var(conn):
    j = seances(300)
    peupler(
        conn,
        {
            "A": cours_student(j, 100.0, 0.011, graine=21),
            "B": cours_student(j, 70.0, 0.013, graine=22),
            "SPY": cours(j, 400.0, 0.009, graine=23),
        },
        {"A": 10, "B": 12},
    )
    sans = analyse_portfolio(conn, 1, window=250)
    assert sans.student_fit is None and sans.student_monte_carlo_var is None

    rapport = analyse_portfolio(conn, 1, window=250, monte_carlo=True)
    ajustement = rapport.student_fit

    assert ajustement.observations == 250
    for niveau in (0.95, 0.99):
        for famille in (rapport.student_parametric_var, rapport.student_monte_carlo_var):
            assert famille[niveau].nu == ajustement.nu, "ν est une donnée du résultat"
            assert famille[niveau].window.observations == 250
        assert "Σ·(ν−2)/ν" in rapport.student_monte_carlo_var[niveau].detail
        assert rapport.parametric_var[niveau].nu is None
        assert rapport.student_monte_carlo_var[niveau].value == pytest.approx(
            rapport.student_parametric_var[niveau].value, rel=0.03
        )


def _serie_a_deux_lignes(conn, fabrique, graines, seances_totales, fenetre):
    j = seances(seances_totales)
    peupler(
        conn,
        {
            "A": fabrique(j, 100.0, 0.011, graine=graines[0]),
            "B": fabrique(j, 70.0, 0.013, graine=graines[1]),
        },
        {"A": 10, "B": 12},
    )
    return build_portfolio_series(conn, 1, window=fenetre, benchmark=None)


def test_une_student_indiscernable_de_la_normale_est_refusee_sans_ecrire_nu(conn):
    """Sur des rendements normaux, le maximum de vraisemblance pousse ν vers
    l'infini : ici 1,5 × 10¹⁴. Au-delà de `MAX_STUDENT_NU`, seuil choisi, le
    moteur refuse l'ajustement.

    La raison décrit un résultat — pas de queues plus épaisses sur la fenêtre —
    et n'écrit jamais ν : les seuls nombres de la phrase sont la taille de la
    fenêtre et le seuil.
    """
    serie = _serie_a_deux_lignes(conn, cours, (21, 22), 300, 250)
    assert fit_student_t(serie.returns).nu > 1e12, "l'estimateur, lui, rend son maximum"

    with pytest.raises(ValueError) as refus:
        student_fit(serie)
    raison = str(refus.value)
    assert "la loi de Student ne se distingue pas de la normale" in raison
    assert "seuil choisi à la main" in raison
    assert "aucun choc extrême" in raison
    assert set(re.findall(r"\d+", raison)) == {"250", "30"}


def test_une_student_a_queues_epaisses_reste_ajustee(conn):
    serie = _serie_a_deux_lignes(conn, cours_student, (21, 22), 300, 250)
    assert student_fit(serie).nu < MAX_STUDENT_NU


# ------------------------------- Monte Carlo normal et volet Student séparés --
#
# Le Monte Carlo NORMAL ne dépend pas de ν. Un refus de la Student — au-delà de
# ν = 30, fréquent sur fenêtre courte, ou ν ≤ 2 — ne doit pas l'emporter : il
# reste la vérification croisée de la VaR paramétrique. Et quand le Monte Carlo
# normal est lui-même impossible, il a SA raison, que celle de la Student ne
# masque pas.


def _monte_carlo_normal_present(rapport, observations):
    for niveau in (0.95, 0.99):
        simule = rapport.monte_carlo_var[niveau]
        assert simule.method == "Monte Carlo"
        assert "graine" in simule.detail
        assert simule.window.observations == observations
    assert rapport.monte_carlo_unavailable_reason is None


def test_une_student_indiscernable_de_la_normale_laisse_le_monte_carlo_normal(conn):
    _serie_a_deux_lignes(conn, cours, (21, 22), 300, 250)
    rapport = analyse_portfolio(conn, 1, window=250, benchmark=None, monte_carlo=True)

    assert rapport.student_fit is None
    assert rapport.student_parametric_var is None
    assert rapport.student_monte_carlo_var is None
    assert "ne se distingue pas de la normale" in rapport.student_unavailable_reason
    _monte_carlo_normal_present(rapport, 250)


def test_nu_inferieur_ou_egal_a_deux_laisse_le_monte_carlo_normal(conn, monkeypatch):
    """ν ≤ 2 est refusé plus loin que l'ajustement, par la VaR Student elle-même
    (variance infinie). Le Monte Carlo normal n'en dépend pas davantage."""
    from backend.risk_engine import var

    _serie_a_deux_lignes(conn, cours_student, (21, 22), 300, 250)
    monkeypatch.setattr(
        var,
        "fit_student_t",
        lambda rendements: var.StudentFit(
            nu=1.9, loc=0.0, scale=0.01, log_likelihood=0.0, observations=250
        ),
    )
    rapport = analyse_portfolio(conn, 1, window=250, benchmark=None, monte_carlo=True)

    assert rapport.student_fit is None
    assert rapport.student_parametric_var is None
    assert "≤ 2" in rapport.student_unavailable_reason
    _monte_carlo_normal_present(rapport, 250)


def test_student_et_monte_carlo_impossibles_ont_chacun_leur_raison(conn):
    """Trois séances d'observation pour trois lignes : la covariance est de rang
    deux au plus, le Monte Carlo normal n'a pas de facteur de Cholesky. La
    Student, elle, manque de séances. Deux raisons distinctes, et aucune ne
    remplace l'autre."""
    j = seances(4)
    peupler(
        conn,
        {
            "A": cours(j, 100.0, 0.011, graine=31),
            "B": cours(j, 70.0, 0.013, graine=32),
            "C": cours(j, 40.0, 0.015, graine=33),
        },
        {"A": 10, "B": 12, "C": 20},
    )
    rapport = analyse_portfolio(conn, 1, window=504, benchmark=None, monte_carlo=True)
    assert rapport.window.observations == 3

    assert rapport.monte_carlo_var is None
    # En clair pour un particulier : la cause est la longueur de la fenêtre.
    raison = rapport.monte_carlo_unavailable_reason
    assert raison.startswith("La fenêtre compte 3")
    assert "il en faut davantage que de lignes pour simuler le portefeuille" in raison
    assert "non définie positive" not in raison
    assert rapport.student_fit is None
    # En clair, comme le Monte Carlo : la cause est la longueur de la fenêtre.
    assert rapport.student_unavailable_reason == (
        "La fenêtre compte 3\u00a0séances : il en faut au moins 30 pour "
        "ajuster une loi de Student."
    )
    assert rapport.monte_carlo_unavailable_reason != rapport.student_unavailable_reason


def test_une_covariance_singuliere_pour_une_autre_cause_garde_le_message_technique(conn):
    """Dix séances pour deux lignes, mais B vaut exactement deux fois A : mêmes
    rendements, covariance de rang un. La fenêtre n'y est pour rien ; le
    message du moteur, qui nomme les causes à vérifier, reste tel quel."""
    j = seances(11)
    prix_a = cours(j, 100.0, 0.011, graine=41)
    peupler(
        conn,
        {"A": prix_a, "B": [(d, 2.0 * v) for d, v in prix_a]},
        {"A": 10, "B": 12},
    )
    rapport = analyse_portfolio(conn, 1, window=504, benchmark=None, monte_carlo=True)
    assert rapport.window.observations == 10

    assert rapport.monte_carlo_var is None
    assert "non définie positive" in rapport.monte_carlo_unavailable_reason
    assert not rapport.monte_carlo_unavailable_reason.startswith("La fenêtre compte")


# Les raisons de refus du volet Student sont des PHRASES : l'interface les
# affiche en Spectral, qui n'a aucun glyphe grec. Un « ν » y passerait dans une
# police de repli, où il se lit « v ». La provenance des VaR Student, elle,
# garde « ν = 4,07 » : elle s'affiche en IBM Plex Sans, qui a le grec.
LETTRE_GRECQUE = re.compile("[\u0370-\u03ff]")


def _refus_student(conn, monkeypatch, cas):
    from backend.risk_engine import var

    if cas == "fenêtre courte":
        j = seances(4)
        peupler(
            conn,
            {"A": cours(j, 100.0, 0.011, graine=31), "B": cours(j, 70.0, 0.013, graine=32)},
            {"A": 10, "B": 12},
        )
    elif cas == "loi normale":
        _serie_a_deux_lignes(conn, cours, (21, 22), 300, 250)
    else:
        _serie_a_deux_lignes(conn, cours_student, (21, 22), 300, 250)
        monkeypatch.setattr(
            var,
            "fit_student_t",
            lambda rendements: var.StudentFit(
                nu=1.9, loc=0.0, scale=0.01, log_likelihood=0.0, observations=250
            ),
        )
    rapport = analyse_portfolio(conn, 1, window=250, benchmark=None, monte_carlo=True)
    return rapport.student_unavailable_reason


@pytest.mark.parametrize("cas", ["fenêtre courte", "loi normale", "variance infinie"])
def test_aucune_raison_de_refus_student_n_ecrit_de_lettre_grecque(conn, monkeypatch, cas):
    raison = _refus_student(conn, monkeypatch, cas)
    assert raison is not None
    assert not LETTRE_GRECQUE.search(raison), raison


def test_le_refus_de_variance_infinie_dit_la_cause_en_clair(conn, monkeypatch):
    """ν ≤ 2 : la phrase écrit le nombre de degrés de liberté, à la virgule,
    et la borne — pas le symbole."""
    raison = _refus_student(conn, monkeypatch, "variance infinie")
    assert raison.startswith(
        "Sur cette fenêtre de 250\u00a0séances, la loi de Student ajustée n'a "
        "pas de variance finie (degrés de liberté estimés à 1,90 ≤ 2)"
    ), raison


def test_sans_monte_carlo_demande_aucune_raison_n_est_inventee(conn):
    _serie_a_deux_lignes(conn, cours, (21, 22), 300, 250)
    rapport = analyse_portfolio(conn, 1, window=250, benchmark=None)
    assert rapport.monte_carlo_var is None and rapport.student_fit is None
    assert rapport.monte_carlo_unavailable_reason is None
    assert rapport.student_unavailable_reason is None


# ------------------------------------------------ Catalogue de la base --
#
# Deux lectures ajoutées pour la phase 7A. Elles ne produisent aucun chiffre de
# risque, mais elles répondent à la même question que `price_coverage` — quel
# titre a quelque chose à dire, et sur quelle période — posée sur l'univers
# entier plutôt que sur les lignes d'un portefeuille.


def test_le_catalogue_donne_les_bornes_de_couverture_de_chaque_titre(conn):
    j = seances(5)
    peupler(conn, {"A": cours(j), "B": cours(j[2:], 50.0)}, {"A": 1})

    catalogue = {t.ticker: t for t in load_securities(conn)}
    assert catalogue["A"].first_price_date == j[0]
    assert catalogue["A"].last_price_date == j[-1]
    # B est entré en cotation plus tard : ses bornes le disent, plutôt que
    # d'être comblées.
    assert catalogue["B"].first_price_date == j[2]
    assert catalogue["B"].has_prices is True


def test_un_titre_sans_aucun_prix_reste_au_catalogue_avec_des_bornes_nulles(conn):
    """« Présent mais jamais ingéré » et « absent de l'univers » n'appellent pas
    la même action : les confondre ferait chercher au mauvais endroit."""
    j = seances(3)
    peupler(conn, {"A": cours(j)}, {"A": 1})
    conn.execute("INSERT INTO securities (ticker, name) VALUES ('VIDE', 'Sans prix')")
    conn.commit()

    catalogue = {t.ticker: t for t in load_securities(conn)}
    assert catalogue["VIDE"].first_price_date is None
    assert catalogue["VIDE"].last_price_date is None
    assert catalogue["VIDE"].has_prices is False


def test_le_catalogue_est_trie_par_ticker(conn):
    j = seances(3)
    peupler(conn, {"Z": cours(j), "A": cours(j)}, {"A": 1})
    assert [t.ticker for t in load_securities(conn)] == ["A", "Z"]


def test_le_catalogue_porte_le_nom_et_le_secteur_eventuellement_nul(conn):
    j = seances(3)
    peupler(conn, {"A": cours(j)}, {"A": 1})
    conn.execute("UPDATE securities SET name = 'Alfa Inc', sector = 'Energy'")
    conn.execute(
        "INSERT INTO securities (ticker, name, sector) VALUES ('IDX', 'Indice', NULL)"
    )
    conn.commit()

    catalogue = {t.ticker: t for t in load_securities(conn)}
    assert catalogue["A"].name == "Alfa Inc"
    assert catalogue["A"].sector == "Energy"
    # Un indice n'a pas de secteur propre : il les contient tous.
    assert catalogue["IDX"].sector is None


def test_l_as_of_de_la_base_est_la_derniere_seance_presente(conn):
    """Jamais `date.today()`.

    Un week-end, un jour férié ou une ingestion en panne laissent la base en
    arrière, et c'est exactement cet écart que l'utilisateur doit pouvoir voir.
    """
    j = seances(5)
    peupler(conn, {"A": cours(j), "B": cours(j[:3], 50.0)}, {"A": 1})
    assert latest_price_date(conn) == j[-1]


def test_l_as_of_d_une_base_sans_prix_est_nul(conn):
    """Pas de date plutôt qu'une date fausse."""
    assert latest_price_date(conn) is None


def test_l_as_of_de_la_base_peut_devancer_celui_d_un_portefeuille(conn):
    """Deux dates distinctes, et volontairement.

    Celle de la base est la dernière séance tous titres confondus ; celle du
    portefeuille retient la plus ANCIENNE des dernières clôtures de ses lignes,
    seule date à laquelle la valorisation est vraie pour TOUTES. Les confondre
    annoncerait un portefeuille valorisé à une date où une ligne est périmée.
    """
    j = seances(6)
    peupler(conn, {"A": cours(j), "B": cours(j[:4], 50.0)}, {"A": 10, "B": 5})

    assert latest_price_date(conn) == j[-1]
    assert market_value_weights(conn, 1).as_of == j[3]

# ------------------------------- Refus dans les MESURES, pas les phrases --
#
# Le moteur de règles peut refuser de commenter un chiffre ; ça ne l'empêche pas
# d'être publié et dessiné. Une carte de chaleur de corrélations toutes à ±1
# reste symétrique et de diagonale 1 — donc parfaitement plausible, et
# entièrement fausse. Le refus doit donc exister là où la valeur est produite.


def test_la_correlation_n_est_pas_estimee_sous_trois_seances(conn):
    """À deux observations, toutes les cellules hors diagonale valent ±1."""
    j = seances(3)
    peupler(conn, {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)}, {"A": 10, "B": 5})
    rapport = analyse_portfolio(conn, 1, window=504)

    assert rapport.matrices.window.observations == 2
    assert rapport.matrices.correlation is None
    raison = rapport.matrices.correlation_undefined_reason
    assert f"2 séances seulement" in raison
    assert "le centrage ne laisse qu'une seule direction" in raison
    # La covariance reste publiée : wᵀΣw est la variance de la série du
    # portefeuille, estimable dès deux observations, et elle porte la VaR.
    assert rapport.matrices.covariance is not None
    assert rapport.volatility.annualised > 0.0


def test_la_correlation_revient_des_trois_seances(conn):
    j = seances(4)
    peupler(conn, {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)}, {"A": 10, "B": 5})
    rapport = analyse_portfolio(conn, 1, window=504)

    assert rapport.matrices.window.observations == 3
    assert rapport.matrices.correlation is not None
    assert rapport.matrices.correlation_undefined_reason is None


def test_la_pente_du_beta_est_indefinie_aussi_pas_seulement_le_r2(conn):
    """À zéro degré de liberté résiduel, la droite passe par les points.

    Elle n'a pas d'erreur type : ce n'est plus une estimation mais une
    construction géométrique. Rendre la pente en nullifiant le seul R²
    laisserait croire que la sensibilité au marché a été mesurée et que seule sa
    qualité d'ajustement manque.
    """
    j = seances(3)
    peupler(conn, {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)}, {"A": 10, "B": 5})
    beta = analyse_portfolio(conn, 1, window=504).beta

    assert beta.beta is None
    assert beta.r_squared is None
    assert beta.idiosyncratic_share is None
    assert "un beta n'est pas estimable" in beta.undefined_reason
    # Ce qui manque est le chiffre, pas la provenance.
    assert beta.benchmark == "SPY"
    assert beta.window.observations == 2


def test_un_beta_indefini_ne_se_confond_pas_avec_un_beta_non_demande(conn):
    """`report.beta is None` veut dire « aucun benchmark demandé ».

    Un beta non estimable garde son objet et dit pourquoi : les deux situations
    appellent des affichages différents, et un `None` unique les confondrait.
    """
    j = seances(3)
    peupler(conn, {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)}, {"A": 10, "B": 5})

    assert analyse_portfolio(conn, 1, window=504, benchmark=None).beta is None
    assert analyse_portfolio(conn, 1, window=504).beta is not None


# ---------------------------------- Quelle ligne raccourcit la fenêtre ? --


def test_la_ligne_qui_borne_la_fenetre_est_nommee_avec_sa_premiere_date(conn):
    """`Window.complete` dit que la fenêtre est courte, pas à cause de qui.

    C'est pourtant la seule information sur laquelle l'utilisateur peut agir :
    une ligne à 5 % du portefeuille, cotée depuis peu, ramène TOUTES les mesures
    à son propre historique.
    """
    j = seances(120)
    peupler(
        conn,
        {
            "VIEUX": cours(j),
            "RECENT": cours(j[80:], 50.0, graine=7),
            "SPY": cours(j, 300.0, graine=9),
        },
        {"VIEUX": 10, "RECENT": 5},
    )
    serie = build_portfolio_series(conn, 1, window=504)

    assert serie.window.complete is False
    assert [p.ticker for p in serie.limiting_positions] == ["RECENT"]
    assert serie.limiting_positions[0].first_available == j[80]


def test_une_fenetre_pleine_n_a_aucune_ligne_limitante(conn):
    """Elle a été bornée par la demande, pas par l'historique.

    Nommer une ligne ferait porter à quelqu'un la responsabilité d'un choix de
    paramètre.
    """
    j = seances(120)
    peupler(conn, {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)}, {"A": 10, "B": 5})
    serie = build_portfolio_series(conn, 1, window=50)

    assert serie.window.complete is True
    assert serie.limiting_positions == ()


def test_plusieurs_lignes_entrees_le_meme_jour_sont_toutes_nommees(conn):
    j = seances(120)
    peupler(
        conn,
        {
            "VIEUX": cours(j),
            "RECENT_A": cours(j[80:], 50.0, graine=7),
            "RECENT_B": cours(j[80:], 20.0, graine=11),
            "SPY": cours(j, 300.0, graine=9),
        },
        {"VIEUX": 10, "RECENT_A": 5, "RECENT_B": 3},
    )
    serie = build_portfolio_series(conn, 1, window=504)

    assert [p.ticker for p in serie.limiting_positions] == ["RECENT_A", "RECENT_B"]


def test_aucune_ligne_n_est_nommee_quand_la_troncature_vient_d_un_trou(conn):
    """Attribution PROUVÉE, pas devinée.

    Ici le panel commence après la première date de CHAQUE ligne : VIEUX a un
    trou le jour où RECENT entre en cotation, et l'intersection ne démarre donc
    que le lendemain. Aucune ligne n'explique à elle seule la troncature, et
    mieux vaut ne désigner personne que désigner à tort.
    """
    j = seances(120)
    prix_vieux = [(jour, valeur) for jour, valeur in cours(j) if jour != j[80]]
    peupler(
        conn,
        {
            "VIEUX": prix_vieux,
            "RECENT": cours(j[80:], 50.0, graine=7),
            "SPY": cours(j, 300.0, graine=9),
        },
        {"VIEUX": 10, "RECENT": 5},
    )
    serie = build_portfolio_series(conn, 1, window=504)

    assert serie.window.complete is False
    assert serie.window.start > j[80]
    assert serie.limiting_positions == ()


def test_les_lignes_limitantes_voyagent_jusqu_au_rapport(conn):
    j = seances(120)
    peupler(
        conn,
        {
            "VIEUX": cours(j),
            "RECENT": cours(j[80:], 50.0, graine=7),
            "SPY": cours(j, 300.0, graine=9),
        },
        {"VIEUX": 10, "RECENT": 5},
    )
    rapport = analyse_portfolio(conn, 1, window=504)

    assert [p.ticker for p in rapport.limiting_positions] == ["RECENT"]

# ---------------------- Chaque refus n'affirme que ce qui est vrai de LUI --
#
# Les trois mesures refusent sous le même SEUIL, pas pour la même RAISON. Un
# texte commun affirmerait de chacune ce qui n'est vrai que d'une seule — et une
# explication fausse attachée à un refus juste est pire qu'un refus sans
# explication : le lecteur en tire une conclusion sur ses données.


def base_a_deux_seances(conn):
    j = seances(3)
    peupler(
        conn,
        {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)},
        {"A": 10, "B": 5},
    )
    return analyse_portfolio(conn, 1, window=504)


def test_la_raison_du_beta_ne_parle_pas_de_coefficient_a_plus_ou_moins_un(conn):
    """« ±1 » est vrai d'une corrélation, faux d'une pente.

    À deux séances le beta vaut n'importe quoi — 11,84 puis 8,65 sur deux
    fenêtres de la base réelle. Ce qui le disqualifie n'est pas sa valeur, c'est
    l'absence de résidu.
    """
    raison = base_a_deux_seances(conn).beta.undefined_reason

    # Pas même pour le nier : « ±1 » n'a rien à faire dans la raison d'un beta.
    assert "±1" not in raison
    assert "pas d'erreur type" in raison
    assert "n'importe quelle valeur" in raison
    # Le beta est la seule des trois à naître d'une régression.
    assert "régression" in raison


def test_la_raison_de_la_correlation_parle_bien_du_coefficient_a_plus_ou_moins_un(conn):
    raison = base_a_deux_seances(conn).matrices.correlation_undefined_reason

    assert "±1" in raison
    assert "Deux points centrés sont colinéaires" in raison
    # La colinéarité est propre à la corrélation : le beta, lui, n'a pas de
    # résidu, ce qui est une autre façon de dégénérer.
    assert "erreur type" not in raison


def test_la_raison_des_contributions_parle_du_rang_de_la_covariance(conn):
    raison = base_a_deux_seances(conn).variance_contributions.undefined_reason

    assert "rang 1" in raison
    assert "rang au plus n − 1" in raison
    assert "±1" not in raison
    assert "erreur type" not in raison
    # Il n'y a AUCUNE régression dans une décomposition de variance : l'invoquer
    # serait une justification empruntée à une autre mesure.
    assert "régression" not in raison


def test_les_trois_raisons_partagent_la_demonstration_et_rien_de_plus(conn):
    """Le partage s'arrête où les mesures cessent de dégénérer pareil."""
    rapport = base_a_deux_seances(conn)
    raisons = [
        rapport.matrices.correlation_undefined_reason,
        rapport.beta.undefined_reason,
        rapport.variance_contributions.undefined_reason,
    ]

    # La partie commune ne dit que ce qui vaut des trois : à deux observations,
    # le centrage ne laisse qu'une direction. Elle ne parle NI de régression —
    # il n'y en a pas dans une décomposition de variance — NI de coefficient à
    # ±1, qui n'est vrai que de la corrélation.
    commun = "le centrage ne laisse qu'une seule direction"
    for raison in raisons:
        assert f"2 séances seulement" in raison
        assert commun in raison
        assert "un unique écart journalier" in raison

    # Et les conséquences, elles, sont toutes différentes.
    consequences = [raison.split("unique écart journalier.")[1] for raison in raisons]
    assert len(set(consequences)) == 3


# ------------------------ Les contributions refusent dans la MESURE aussi --


def test_les_contributions_ne_sont_pas_estimees_sous_trois_seances(conn):
    """À n = 2 elles valent exactement wᵢδᵢ/(wᵀδ) : une identité arithmétique."""
    vc = base_a_deux_seances(conn).variance_contributions

    assert vc.contributions is None
    assert vc.effective_positions is None
    assert vc.excess_over_weight("A") is None
    # `False` affirmerait qu'aucune ligne n'a évolué à rebours des autres, alors
    # que rien n'a été mesuré.
    assert vc.has_negative_contribution is None
    # Les poids restent : ils sont ponctuels, lus sur la dernière valorisation.
    assert set(vc.weights) == {"A", "B"}
    assert sum(vc.weights.values()) == pytest.approx(1.0)


def test_les_contributions_reviennent_des_trois_seances(conn):
    j = seances(4)
    peupler(
        conn,
        {"A": cours(j), "B": cours(j, 50.0, graine=7), "SPY": cours(j, 300.0, graine=9)},
        {"A": 10, "B": 5},
    )
    vc = analyse_portfolio(conn, 1, window=504).variance_contributions

    assert vc.contributions is not None
    assert vc.undefined_reason is None
    assert sum(vc.contributions.values()) == pytest.approx(1.0)
    assert vc.effective_positions is not None
    assert vc.has_negative_contribution in (True, False)


def test_a_deux_seances_la_volatilite_reste_publiee_la_var_historique_est_refusee(conn):
    """La ligne de partage : on refuse ce qui ne dépend plus des données, et
    ce qui n'est plus la mesure annoncée.

    Une volatilité sur deux observations est une estimation à un seul degré de
    liberté — très mauvaise, mais elle BOUGE avec les données, contrairement à
    une corrélation qui vaut ±1 quoi qu'il arrive : publiée, et signalée.

    La VaR historique, elle, est refusée : sur deux séances, aucune ne tombe
    dans les 5 % des pires, et le quantile ne serait que le minimum de la
    fenêtre. Ce test affirmait le contraire jusqu'à la 7B.3a.
    """
    rapport = base_a_deux_seances(conn)

    assert rapport.volatility.annualised > 0.0
    assert rapport.matrices.covariance is not None
    var_historique = rapport.historical_var[0.95]
    assert var_historique.value is None
    assert var_historique.undefined_reason.startswith(
        "Sur 2\u00a0séances, aucune ne tombe dans les 5\u202f% des pires"
    )
    assert rapport.drawdown.value <= 0.0


# ══════════════════════════════ Ce que citent les phrases de lecture ══
#
# Données ajoutées au rapport pour les textes de lecture : libellés de
# période, montants, retour au pic, volatilité de l'indice de référence, pire
# séance, verdict de couverture d'un scénario, nom lisible d'un indice. Le
# moteur les calcule ; le client ne fait que les citer.


@pytest.mark.parametrize(
    "observations, attendu",
    [
        (504, f"ces deux{NBSP}dernières années"),
        (500, f"ces deux{NBSP}dernières années"),
        (1008, f"ces quatre{NBSP}dernières années"),
        (260, "cette dernière année"),
        (252, "cette dernière année"),
        (300, f"ces 14{NBSP}derniers mois"),
        (241, f"ces 11{NBSP}derniers mois"),
        (60, f"ces trois{NBSP}derniers mois"),
        (25, "ce dernier mois"),
        (21, "ce dernier mois"),
        (20, f"ces 20{NBSP}derniers jours de bourse"),
        (7, f"ces sept{NBSP}derniers jours de bourse"),
        (2, f"ces deux{NBSP}derniers jours de bourse"),
        (1, "ce dernier jour de bourse"),
    ],
)
def test_le_libelle_de_periode_suit_la_regle_des_textes_de_lecture(observations, attendu):
    """Années près d'un entier à partir de 252 séances, mois arrondis à
    partir de 21, jours de bourse en deçà. 241 séances ne font pas « cette
    dernière année » : la règle part de 252."""
    assert period_label(observations) == attendu


def test_le_libelle_de_periode_refuse_une_fenetre_vide():
    with pytest.raises(ValueError):
        period_label(0)


def test_une_fenetre_dit_la_periode_obtenue_et_non_la_periode_demandee():
    fenetre = Window(
        requested=504, observations=7, start=date(2026, 9, 17), end=date(2026, 9, 25)
    )
    assert fenetre.period_label == f"ces sept{NBSP}derniers jours de bourse"


def test_les_nombres_d_une_phrase_s_ecrivent_en_lettres_jusqu_a_dix():
    assert [cardinal(n) for n in (0, 1, 2, 10)] == ["zéro", "un", "deux", "dix"]
    assert cardinal(11) == "11"
    assert cardinal(1234) == f"1{NARROW_NBSP}234"


def test_chaque_var_et_chaque_cvar_portent_leur_montant(conn):
    j = seances(300)
    peupler(
        conn,
        {
            "A": cours_student(j, 100.0, 0.011, graine=21),
            "B": cours_student(j, 70.0, 0.013, graine=22),
            "SPY": cours(j, 400.0, 0.009, graine=23),
        },
        {"A": 10, "B": 12},
    )
    rapport = analyse_portfolio(conn, 1, window=250, monte_carlo=True)
    assert rapport.student_parametric_var is not None, "témoin : la Student est ajustée"
    familles = (
        rapport.historical_var,
        rapport.parametric_var,
        rapport.monte_carlo_var,
        rapport.student_parametric_var,
        rapport.student_monte_carlo_var,
        rapport.expected_shortfall,
    )
    for famille in familles:
        for resultat in famille.values():
            assert resultat.amount == resultat.value * rapport.total_value
            assert resultat.amount > 0, "une perte positive donne un montant positif"


def test_une_var_refusee_n_a_pas_de_montant(conn):
    j = seances(12)
    peupler(conn, {"A": cours(j, graine=24)}, {"A": 10})
    rapport = analyse_portfolio(conn, 1, window=10, benchmark=None)
    for niveau in (0.95, 0.99):
        assert rapport.historical_var[niveau].value is None
        assert rapport.historical_var[niveau].amount is None
        assert rapport.expected_shortfall[niveau].amount is None
        assert rapport.parametric_var[niveau].amount is not None


def test_le_creux_porte_son_montant_et_son_retour_au_pic(conn):
    j = seances(8)
    # Pic à 110, creux à 90, retour au-dessus du pic à 112, deux séances
    # après le creux.
    prix = [100.0, 110.0, 100.0, 90.0, 95.0, 112.0, 115.0, 111.0]
    peupler(conn, {"A": list(zip(j, prix))}, {"A": 10})
    rapport = analyse_portfolio(conn, 1, window=7, benchmark=None)
    creux = rapport.drawdown
    assert (creux.peak_date, creux.trough_date) == (j[1], j[3])
    assert creux.amount == creux.value * rapport.total_value
    assert creux.amount < 0
    assert (creux.recovery_date, creux.recovery_sessions) == (j[5], 2)


def test_un_creux_non_efface_n_a_pas_de_date_de_retour(conn):
    j = seances(6)
    prix = [100.0, 110.0, 100.0, 90.0, 95.0, 100.0]
    peupler(conn, {"A": list(zip(j, prix))}, {"A": 10})
    creux = analyse_portfolio(conn, 1, window=5, benchmark=None).drawdown
    assert creux.recovery_date is None
    assert creux.recovery_sessions is None


def test_la_volatilite_de_l_indice_porte_sur_les_seances_du_portefeuille(conn):
    """Une séance manque à SPY : elle disparaît pour le portefeuille comme pour
    l'indice, et la volatilité de l'indice se calcule sur le panel aligné."""
    j = seances(70)
    spy = [point for rang, point in enumerate(cours(j, 400.0, 0.02, graine=26)) if rang != 30]
    peupler(conn, {"A": cours(j, graine=25), "SPY": spy}, {"A": 10})
    rapport = analyse_portfolio(conn, 1, window=60)

    niveaux = np.array([valeur for _, valeur in spy])
    rendements = (niveaux[1:] / niveaux[:-1] - 1.0)[-60:]
    attendue = float(np.std(rendements, ddof=1) * np.sqrt(252))

    indice = rapport.benchmark_volatility
    assert indice.annualised == pytest.approx(attendue, rel=1e-12)
    assert indice.window == rapport.volatility.window
    assert indice.method == rapport.volatility.method
    assert indice.annualised != rapport.volatility.annualised


def test_la_volatilite_de_l_indice_porte_la_meme_reserve_que_celle_du_portefeuille(conn):
    j = seances(10)
    peupler(conn, {"A": cours(j, graine=27), "SPY": cours(j, 400.0, graine=28)}, {"A": 10})
    rapport = analyse_portfolio(conn, 1, window=7)
    assert rapport.volatility.caveat is not None
    assert rapport.benchmark_volatility.caveat == rapport.volatility.caveat


def test_sans_indice_de_reference_pas_de_volatilite_de_l_indice(conn):
    j = seances(40)
    peupler(conn, {"A": cours(j, graine=29)}, {"A": 10})
    assert analyse_portfolio(conn, 1, window=30, benchmark=None).benchmark_volatility is None


def test_la_pire_seance_est_celle_du_rapport_avec_son_montant(conn):
    j = seances(30)
    peupler(conn, {"A": cours(j, graine=30)}, {"A": 10})
    rapport = analyse_portfolio(conn, 1, window=25, benchmark=None)
    pire = rapport.worst_day
    assert pire.date == rapport.returns.idxmin()
    assert pire.loss == -rapport.returns.min()
    assert pire.amount == pire.loss * rapport.total_value
    assert pire.window == rapport.window


def test_le_resultat_d_un_scenario_porte_son_montant_sur_la_valeur_couverte(conn):
    j = seances(40)
    # B n'est coté qu'à partir de la onzième séance : exclu de l'épisode.
    peupler(conn, {"A": cours(j, graine=31), "B": cours(j[10:], graine=32)}, {"A": 10, "B": 5})
    episode = Scenario(
        key="essai", name="Épisode d'essai", start=j[2], end=j[8], benchmark="A", description=""
    )
    resultat = run_scenario(conn, 1, episode)
    assert not resultat.coverage.is_complete
    assert resultat.end_to_end_amount == (
        resultat.end_to_end_return * resultat.coverage.covered_value
    )


def test_un_scenario_sans_ligne_couverte_n_a_pas_de_montant(conn):
    j = seances(20)
    peupler(conn, {"A": cours(j, graine=33)}, {"A": 10})
    avant = Scenario(
        key="avant",
        name="Avant la cotation",
        start=date(2020, 1, 2),
        end=date(2020, 2, 3),
        benchmark="A",
        description="",
    )
    resultat = run_scenario(conn, 1, avant)
    assert resultat.end_to_end_return is None
    assert resultat.end_to_end_amount is None
    assert not resultat.coverage.sufficient


def test_la_couverture_suffit_a_partir_du_seuil_choisi():
    def couverture(part):
        return ScenarioCoverage(
            covered=("A",),
            excluded=(ExcludedPosition("B", "absent", 1.0 - part, 1.0 - part),),
            covered_value=part,
            total_value=1.0,
        )

    assert couverture(MIN_SCENARIO_COVERAGE_SHARE).sufficient
    assert couverture(0.95).sufficient
    assert not couverture(0.79).sufficient


def test_le_seuil_de_couverture_n_a_qu_une_valeur():
    """La constante du moteur et le seuil déclaré des règles sont le même
    nombre : le verdict publié avec un scénario et l'observation du moteur de
    règles ne peuvent pas se contredire."""
    from backend.rules.thresholds import MIN_SCENARIO_COVERAGE

    assert MIN_SCENARIO_COVERAGE.value == MIN_SCENARIO_COVERAGE_SHARE
    assert MIN_SCENARIO_COVERAGE.chosen


def test_seul_un_indice_connu_recoit_un_nom():
    nom = benchmark_name("SPY")
    assert nom.label == "le S&P 500"
    assert nom.description == "l'indice de 500 grandes entreprises américaines"
    assert benchmark_name("QQQ") is None
    assert benchmark_name(None) is None


def test_une_comparaison_de_regimes_nomme_son_indice_et_sa_periode_calme():
    commun = dict(
        beta=0.5, r_squared=0.4, standard_error=0.05, start=date(2024, 9, 5), end=date(2026, 9, 9)
    )
    comparaison = RegimeComparison(
        scenario=SCENARIOS[0],
        coverage=ScenarioCoverage(("A",), (), 1.0, 1.0),
        benchmark="SPY",
        crisis_beta=RegressedBeta(observations=355, **commun),
        calm_beta=RegressedBeta(observations=504, **commun),
    )
    assert comparaison.benchmark_label == "le S&P 500"
    assert comparaison.calm_period_label == f"ces deux{NBSP}dernières années"

    autre = replace(comparaison, benchmark="QQQ", calm_beta=None)
    assert autre.benchmark_label is None
    assert autre.calm_period_label is None
