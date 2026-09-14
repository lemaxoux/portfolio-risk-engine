"""Tests de la comparaison régime calme / régime de crise.

Ce qui est verrouillé ici : le ratio d'amplification n'est pas un beta, le beta
de crise porte son incertitude et signale un échantillon trop mince, et la
divergence entre les deux est un résultat, pas une anomalie.
"""

from __future__ import annotations

import math
import shutil
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.db.init_db import connect, init_db
from backend.risk_engine.config import MIN_REGRESSION_OBSERVATIONS
from backend.risk_engine.covariance import beta
from backend.risk_engine.engine import (
    RegressedBeta,
    beta_vs_benchmark,
    build_portfolio_series,
    compare_all_regimes,
    compare_regimes,
)
from backend.risk_engine.regime import (
    amplification_ratio,
    beta_implied_return,
    log_return,
)
from backend.risk_engine.scenarios import Scenario

BASE_REELLE = Path(__file__).resolve().parents[1] / "data" / "mx_risk.sqlite"


# ---------------------------------------------------- Fonctions pures --


def test_le_ratio_vaut_un_quand_le_portefeuille_suit_le_marche():
    assert amplification_ratio(-0.30, -0.30) == pytest.approx(1.0)


def test_le_ratio_est_un_rapport_de_rendements_log():
    # Un portefeuille dont le rendement log est le double de celui du marché :
    # (1 − 0,30)² − 1 = −51 %. Le ratio vaut exactement 2 en log, alors que le
    # rapport des rendements simples vaudrait 1,7.
    marche = -0.30
    portefeuille = (1.0 + marche) ** 2 - 1.0

    assert amplification_ratio(portefeuille, marche) == pytest.approx(2.0, abs=1e-12)
    assert portefeuille / marche == pytest.approx(1.7)


def test_le_ratio_est_negatif_si_le_portefeuille_evolue_a_contre_sens():
    assert amplification_ratio(0.10, -0.20) < 0.0


def test_le_ratio_est_indefini_si_le_benchmark_n_a_pas_bouge():
    assert amplification_ratio(-0.10, 0.0) is None


def test_une_perte_totale_n_a_pas_de_rendement_log():
    with pytest.raises(ValueError, match="perte totale"):
        log_return(-1.0)


def test_la_prediction_du_beta_se_fait_en_log():
    # β = 0,5 face à −50 % : √0,5 − 1 = −29,3 %, et non −25 % en linéaire.
    assert beta_implied_return(0.5, -0.50) == pytest.approx(math.sqrt(0.5) - 1.0)
    assert beta_implied_return(0.5, -0.50) != pytest.approx(-0.25, abs=0.01)


def test_la_prediction_aux_bornes():
    assert beta_implied_return(1.0, -0.37) == pytest.approx(-0.37)
    assert beta_implied_return(0.0, -0.37) == pytest.approx(0.0)


def test_l_erreur_type_du_beta_suit_la_formule_des_moindres_carres():
    rng = np.random.default_rng(21)
    index = [date(2024, 1, 1) + timedelta(days=i) for i in range(250)]
    marche = rng.normal(0.0, 0.01, 250)
    portefeuille = 0.8 * marche + rng.normal(0.0, 0.006, 250)

    resultat = beta(pd.Series(portefeuille, index=index), pd.Series(marche, index=index))

    x = marche - marche.mean()
    y = portefeuille - portefeuille.mean()
    pente = (x @ y) / (x @ x)
    residus = y - pente * x
    attendu = math.sqrt((residus @ residus) / (len(x) - 2) / (x @ x))

    assert resultat.beta == pytest.approx(pente, rel=1e-10)
    assert resultat.standard_error == pytest.approx(attendu, rel=1e-8)


def test_l_erreur_type_n_est_pas_definie_sur_deux_points():
    index = [date(2024, 1, 1), date(2024, 1, 2)]
    resultat = beta(pd.Series([0.01, -0.02], index=index), pd.Series([0.02, -0.01], index=index))
    assert resultat.standard_error is None


def test_un_echantillon_trop_mince_est_signale():
    commun = dict(beta=1.07, r_squared=0.98, standard_error=0.03,
                  start=date(2020, 2, 20), end=date(2020, 3, 23))
    mince = RegressedBeta(observations=23, **commun)
    solide = RegressedBeta(observations=355, **commun)

    assert mince.sample_too_thin
    assert "TROP MINCE" in str(mince)
    assert not solide.sample_too_thin
    assert "TROP MINCE" not in str(solide)
    assert MIN_REGRESSION_OBSERVATIONS == 60


# ------------------------------------------------------------ En base --


@pytest.fixture
def conn(tmp_path):
    chemin = tmp_path / "regime.sqlite"
    init_db(chemin)
    connexion = connect(chemin)
    yield connexion
    connexion.close()


def seances(n: int, depart: date = date(2020, 1, 6)) -> list[date]:
    resultat, jour = [], depart
    while len(resultat) < n:
        if jour.weekday() < 5:
            resultat.append(jour)
        jour += timedelta(days=1)
    return resultat


def peupler(conn, cours: dict[str, pd.Series], positions: dict[str, float]):
    conn.execute("INSERT INTO portfolios (owner) VALUES ('test')")
    for ticker, serie in cours.items():
        conn.execute("INSERT INTO securities (ticker, name) VALUES (?, ?)", (ticker, ticker))
        for jour, valeur in serie.items():
            conn.execute(
                "INSERT INTO prices (ticker, date, close, adj_close) VALUES (?,?,?,?)",
                (ticker, jour.isoformat(), float(valeur), float(valeur)),
            )
    for ticker, quantite in positions.items():
        conn.execute(
            "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1,?,?)",
            (ticker, quantite),
        )
    conn.commit()


def cours_depuis(rendements: np.ndarray, dates: list[date], initial: float = 100.0) -> pd.Series:
    return pd.Series(initial * np.cumprod(1.0 + rendements), index=dates)


JOURS = seances(260)
CRISE = Scenario(
    key="crise_test",
    name="Crise de test",
    start=JOURS[20],
    end=JOURS[119],
    benchmark="SPY",
    description="Fenêtre synthétique de cent séances.",
)


def marche_synthetique(graine: int = 5) -> np.ndarray:
    """Marché calme, puis cent séances de baisse, puis retour au calme."""
    rng = np.random.default_rng(graine)
    rendements = rng.normal(0.0004, 0.008, len(JOURS))
    rendements[20:120] = rng.normal(-0.004, 0.015, 100)
    return rendements


def test_un_portefeuille_100_pct_benchmark(conn):
    """Identité parfaite : ratio 1, betas 1, prédiction = réalisé, écart nul."""
    peupler(conn, {"SPY": cours_depuis(marche_synthetique(), JOURS)}, {"SPY": 10})

    c = compare_regimes(conn, 1, CRISE, window=100)

    assert c.amplification_ratio == pytest.approx(1.0, abs=1e-12)
    assert c.crisis_beta.beta == pytest.approx(1.0, abs=1e-12)
    assert c.crisis_beta.r_squared == pytest.approx(1.0, abs=1e-12)
    assert c.calm_beta.beta == pytest.approx(1.0, abs=1e-12)
    assert c.predicted_return == pytest.approx(c.benchmark_return, abs=1e-12)
    assert c.prediction_gap == pytest.approx(0.0, abs=1e-12)
    assert c.systematic_share_change == pytest.approx(0.0, abs=1e-12)


def test_ratio_et_beta_divergent_quand_le_portefeuille_derive_seul(conn):
    """La divergence est un résultat, pas une anomalie.

    A reproduit chaque jour le rendement du marché, plus 0,3 %. La co-variation
    quotidienne est parfaite — beta 1, R² 1 —, mais la dérive se compose sur
    cent séances : A perd beaucoup moins que le marché, et le ratio
    d'amplification tombe nettement sous 1. Le beta seul ne le dirait pas.
    """
    marche = marche_synthetique()
    peupler(
        conn,
        {"SPY": cours_depuis(marche, JOURS), "A": cours_depuis(marche + 0.003, JOURS)},
        {"A": 10},
    )
    c = compare_regimes(conn, 1, CRISE, window=100)

    assert c.crisis_beta.beta == pytest.approx(1.0, abs=1e-9)
    assert c.crisis_beta.r_squared == pytest.approx(1.0, abs=1e-9)
    assert c.benchmark_return < c.portfolio_return
    assert c.amplification_ratio < 0.8
    assert c.ratio_beta_divergence == pytest.approx(c.amplification_ratio - 1.0, abs=1e-9)


def test_la_fenetre_de_crise_porte_ses_observations_et_son_incertitude(conn):
    peupler(conn, {"SPY": cours_depuis(marche_synthetique(), JOURS)}, {"SPY": 1})

    large = compare_regimes(conn, 1, CRISE, window=100)
    courte = compare_regimes(
        conn, 1,
        Scenario("court", "Choc bref", JOURS[20], JOURS[43], "SPY", "Vingt-quatre séances."),
        window=100,
    )

    assert large.crisis_beta.observations == 99
    assert not large.crisis_beta.sample_too_thin
    assert courte.crisis_beta.observations == 23
    assert courte.crisis_beta.sample_too_thin
    assert "TROP MINCE" in courte.summary()
    assert (large.crisis_beta.start, large.crisis_beta.end) == (JOURS[21], JOURS[119])


def test_le_beta_calme_egale_celui_du_bloc_4b_en_couverture_complete(conn):
    rng = np.random.default_rng(8)
    marche = marche_synthetique()
    peupler(
        conn,
        {
            "SPY": cours_depuis(marche, JOURS),
            "A": cours_depuis(0.7 * marche + rng.normal(0, 0.006, len(JOURS)), JOURS),
            "B": cours_depuis(1.2 * marche + rng.normal(0, 0.009, len(JOURS)), JOURS, 50.0),
        },
        {"A": 10, "B": 15},
    )
    c = compare_regimes(conn, 1, CRISE, window=100)
    b4 = beta_vs_benchmark(build_portfolio_series(conn, 1, window=100, benchmark="SPY"))

    assert c.calm_beta.beta == pytest.approx(b4.beta, rel=1e-12)
    assert c.calm_beta.observations == 100


def test_le_beta_calme_porte_sur_les_lignes_couvertes_renormalisees(conn):
    """Sans renormalisation, le beta calme serait dilué.

    A est une copie du marché ; B, introduit en cours de crise, est exclu. Le
    beta calme de la partie couverte vaut 1. Calculé avec le poids brut de A
    (environ la moitié), il vaudrait environ 0,5 — et l'écart de prédiction
    mélangerait un effet de couverture à un effet de régime.
    """
    marche = marche_synthetique()
    b = cours_depuis(np.random.default_rng(2).normal(0, 0.01, len(JOURS)), JOURS)
    peupler(
        conn,
        {"SPY": cours_depuis(marche, JOURS), "A": cours_depuis(marche, JOURS), "B": b.iloc[60:]},
        {"A": 1, "B": 100.0 / b.iloc[-1]},
    )
    c = compare_regimes(conn, 1, CRISE, window=100)

    assert not c.coverage.is_complete
    assert c.coverage.covered == ("A",)
    assert c.calm_beta.beta == pytest.approx(1.0, abs=1e-9)
    assert c.crisis_beta.beta == pytest.approx(1.0, abs=1e-9)
    assert "sous-estimée" in c.summary()


def test_la_hausse_du_r2_en_crise_mesure_la_degradation_de_la_diversification(conn):
    """Le co-mouvement monte en crise : la part de risque systématique aussi.

    A mêle le marché et un bruit propre. En régime calme, le bruit propre domine
    et la diversification opère ; pendant la crise, le mouvement de marché
    s'amplifie tandis que le bruit propre reste le même, et le R² grimpe.
    """
    rng = np.random.default_rng(31)
    marche = marche_synthetique()
    marche[20:120] *= 3.0  # la crise amplifie le facteur commun
    propre = rng.normal(0.0, 0.012, len(JOURS))
    peupler(
        conn,
        {"SPY": cours_depuis(marche, JOURS), "A": cours_depuis(0.8 * marche + propre, JOURS)},
        {"A": 10},
    )
    c = compare_regimes(conn, 1, CRISE, window=100)

    assert c.crisis_beta.r_squared > c.calm_beta.r_squared
    assert c.systematic_share_change == pytest.approx(
        c.crisis_beta.r_squared - c.calm_beta.r_squared
    )
    assert c.systematic_share_change > 0.2
    assert "part de risque systématique (R²)" in c.summary()


def test_le_r2_est_affiche_a_cote_de_l_erreur_type():
    b = RegressedBeta(
        beta=0.96, r_squared=0.86, standard_error=0.02, observations=355,
        start=date(2007, 10, 10), end=date(2009, 3, 9),
    )
    assert str(b) == "0.96 ± 0.02, R² 0.86 (355 séances)"


def test_le_resume_ne_presente_pas_le_ratio_comme_un_beta(conn):
    peupler(conn, {"SPY": cours_depuis(marche_synthetique(), JOURS)}, {"SPY": 1})
    texte = compare_regimes(conn, 1, CRISE, window=100).summary()

    assert "pas un beta" in texte
    assert "prédisait" in texte and "écart" in texte


def test_sans_ligne_couverte_la_comparaison_est_impossible(conn):
    tardif = seances(200, date(2021, 1, 4))
    peupler(conn, {"A": pd.Series(100.0, index=tardif), "SPY": pd.Series(400.0, index=tardif)}, {"A": 1})

    c = compare_regimes(conn, 1, CRISE, window=100)
    assert c.unavailable_reason is not None
    assert c.amplification_ratio is None and c.calm_beta is None
    assert c.systematic_share_change is None
    assert "impossible" in c.summary()


def test_sans_benchmark_en_base_la_comparaison_est_impossible(conn):
    peupler(conn, {"A": cours_depuis(marche_synthetique(), JOURS)}, {"A": 1})

    c = compare_regimes(conn, 1, CRISE, window=100)
    assert "SPY" in c.unavailable_reason


# ------------------------------------------------ Données réelles --


@pytest.mark.skipif(not BASE_REELLE.exists(), reason="base locale absente")
def test_comparaison_des_trois_scenarios_sur_un_portefeuille_reel(tmp_path):
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
        comparaisons = {c.scenario.key: c for c in compare_all_regimes(conn, pid)}
        b4 = beta_vs_benchmark(build_portfolio_series(conn, pid, benchmark="SPY")).beta

    for c in comparaisons.values():
        assert c.unavailable_reason is None
        assert c.calm_beta.beta == pytest.approx(b4, rel=1e-12)
        assert c.prediction_gap == pytest.approx(c.portfolio_return - c.predicted_return)

    for c in comparaisons.values():
        assert 0.0 <= c.crisis_beta.r_squared <= 1.0
        assert c.systematic_share_change == pytest.approx(
            c.crisis_beta.r_squared - c.calm_beta.r_squared
        )

    assert comparaisons["covid_2020"].crisis_beta.sample_too_thin
    assert not comparaisons["gfc_2008"].crisis_beta.sample_too_thin
    assert not comparaisons["tightening_2022"].crisis_beta.sample_too_thin
