"""Tests des mesures multi-titres : matrices, beta, VaR, CVaR, Monte Carlo.

Fonctions pures uniquement — tableaux en entrée, nombres en sortie. La
composition sur base réelle est testée dans `test_risk_engine.py`.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from backend.risk_engine.config import DDOF, TRADING_DAYS_PER_YEAR
from backend.risk_engine.covariance import (
    beta,
    correlation_matrix,
    covariance_matrix,
    parametric_volatility,
    portfolio_variance,
)
from backend.risk_engine.measures import annualised_volatility
from backend.risk_engine.returns import portfolio_returns
from backend.risk_engine.var import (
    QUANTILE_METHOD,
    expected_shortfall,
    historical_var,
    monte_carlo_var,
    parametric_var,
)


def jours(n: int, depart: date = date(2024, 1, 1)) -> list[date]:
    return [depart + timedelta(days=i) for i in range(n)]


def panel_aleatoire(n: int = 504, k: int = 4, graine: int = 7) -> pd.DataFrame:
    """Panel de rendements corrélés, reproductible."""
    rng = np.random.default_rng(graine)
    facteur = rng.normal(0.0, 0.010, n)
    colonnes = {
        f"T{i}": 0.6 * facteur + rng.normal(0.0002, 0.008, n) for i in range(k)
    }
    return pd.DataFrame(colonnes, index=jours(n))


# ------------------------------------------------------ Matrices : invariants --


def test_la_diagonale_de_la_correlation_vaut_exactement_un():
    corr = correlation_matrix(panel_aleatoire())
    diagonale = np.diag(corr.to_numpy())
    assert (diagonale == 1.0).all(), "exactement 1, pas 0,9999999999999999"


def test_les_matrices_sont_symetriques():
    panel = panel_aleatoire()
    for matrice in (covariance_matrix(panel), correlation_matrix(panel)):
        valeurs = matrice.to_numpy()
        assert np.array_equal(valeurs, valeurs.T)


def test_toutes_les_valeurs_propres_de_la_covariance_sont_positives():
    """Semi-définie positive : condition d'existence du Cholesky du Monte Carlo.

    C'est ce que l'estimation sur données complètes garantit et qu'une
    suppression paire à paire peut casser.
    """
    valeurs_propres = np.linalg.eigvalsh(covariance_matrix(panel_aleatoire()).to_numpy())
    assert (valeurs_propres >= -1e-12).all()


def test_les_correlations_restent_dans_moins_un_plus_un():
    corr = correlation_matrix(panel_aleatoire()).to_numpy()
    assert corr.min() >= -1.0
    assert corr.max() <= 1.0


def test_un_panel_avec_des_nan_est_refuse():
    panel = panel_aleatoire(n=10, k=2)
    panel.iloc[3, 1] = np.nan
    with pytest.raises(ValueError, match="COMPL"):
        covariance_matrix(panel)


def test_un_titre_a_variance_nulle_est_signale():
    panel = pd.DataFrame({"A": [0.01] * 20, "B": [0.01] * 20}, index=jours(20))
    with pytest.raises(ValueError, match="Variance nulle"):
        correlation_matrix(panel)


def test_deux_series_identiques_ont_une_correlation_de_un():
    base = panel_aleatoire(n=100, k=1)["T0"]
    panel = pd.DataFrame({"A": base, "B": base})
    assert correlation_matrix(panel).loc["A", "B"] == pytest.approx(1.0)


# ------------------------------------------------------------ Le piège du ddof --


def test_la_volatilite_parametrique_egale_celle_de_la_serie():
    """L'identité qui casse si les conventions de ddof divergent.

    √(wᵀΣw) et l'écart-type de la série w·r sont la MÊME quantité calculée par
    deux chemins. Ce n'est pas une approximation, donc la tolérance est celle du
    flottant. Une incohérence ddof=0 / ddof=1 introduirait un écart de
    N/(N−1) ≈ 0,1 % sur 504 séances : invisible à l'œil, faux quand même.
    """
    panel = panel_aleatoire(n=504, k=4)
    poids = {"T0": 0.4, "T1": 0.3, "T2": 0.2, "T3": 0.1}

    par_matrice = parametric_volatility(poids, covariance_matrix(panel))
    par_serie = annualised_volatility(portfolio_returns(panel, poids))

    assert par_matrice == pytest.approx(par_serie, rel=1e-12)


def test_l_ecart_ddof_serait_visible_si_les_conventions_divergeaient():
    # Démonstration chiffrée de ce que le test précédent protège.
    panel = panel_aleatoire(n=504, k=3)
    poids = {"T0": 0.5, "T1": 0.3, "T2": 0.2}

    juste = portfolio_variance(poids, covariance_matrix(panel, ddof=1))
    faux = portfolio_variance(poids, covariance_matrix(panel, ddof=0))

    n = len(panel)
    assert juste / faux == pytest.approx(n / (n - 1), rel=1e-9)
    assert math.sqrt(juste / faux) == pytest.approx(1.00099, abs=1e-5)


def test_la_convention_partagee_est_bien_celle_d_echantillon():
    assert DDOF == 1


def test_la_variance_de_portefeuille_est_positive_et_coherente():
    panel = panel_aleatoire(n=200, k=3)
    poids = {"T0": 0.5, "T1": 0.3, "T2": 0.2}
    cov = covariance_matrix(panel)

    variance = portfolio_variance(poids, cov)
    assert variance > 0.0
    assert parametric_volatility(poids, cov) == pytest.approx(
        math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR)
    )


def test_les_poids_sont_apparies_a_la_matrice_par_etiquette():
    panel = panel_aleatoire(n=100, k=3)
    cov = covariance_matrix(panel)
    poids = {"T2": 0.5, "T0": 0.5}  # ordre différent des colonnes

    attendu = (
        0.25 * cov.loc["T2", "T2"]
        + 0.25 * cov.loc["T0", "T0"]
        + 2 * 0.25 * cov.loc["T0", "T2"]
    )
    assert portfolio_variance(poids, cov) == pytest.approx(attendu)


def test_un_titre_absent_de_la_matrice_est_signale():
    cov = covariance_matrix(panel_aleatoire(n=50, k=2))
    with pytest.raises(KeyError, match="ZZZZ"):
        portfolio_variance({"T0": 0.5, "ZZZZ": 0.5}, cov)


# --------------------------------------------------------------------- Beta --


def test_un_portefeuille_100_pct_benchmark_a_un_beta_de_un():
    """Le test décisif : identité parfaite ⇒ β = 1 et R² = 1, exactement."""
    marche = panel_aleatoire(n=300, k=1)["T0"]
    portefeuille = portfolio_returns(pd.DataFrame({"SPY": marche}), {"SPY": 1.0})

    resultat = beta(portefeuille, marche)

    assert resultat.beta == 1.0
    assert resultat.r_squared == 1.0
    assert resultat.observations == 300


def test_un_portefeuille_deux_fois_plus_volatil_a_un_beta_de_deux():
    marche = panel_aleatoire(n=300, k=1)["T0"]
    resultat = beta(2.0 * marche, marche)

    assert resultat.beta == pytest.approx(2.0)
    assert resultat.r_squared == pytest.approx(1.0), "toujours 100 % systématique"


def test_un_portefeuille_independant_du_marche_a_un_beta_proche_de_zero():
    rng = np.random.default_rng(11)
    index = jours(2000)
    marche = pd.Series(rng.normal(0, 0.01, 2000), index=index)
    independant = pd.Series(rng.normal(0, 0.01, 2000), index=index)

    resultat = beta(independant, marche)

    assert resultat.beta == pytest.approx(0.0, abs=0.05)
    assert resultat.r_squared < 0.01, "quasi rien n'est expliqué par le marché"


def test_le_beta_apparie_les_dates_par_jointure():
    """Une séance absente du benchmark ne doit pas décaler la régression."""
    index = jours(10)
    marche = pd.Series(np.linspace(0.01, 0.10, 10), index=index)
    portefeuille = pd.Series(2.0 * np.linspace(0.01, 0.10, 10), index=index)

    tronque = marche.drop(index[4])
    resultat = beta(portefeuille, tronque)

    assert resultat.observations == 9, "seules les dates communes sont régressées"
    assert resultat.beta == pytest.approx(2.0)


def test_un_benchmark_constant_n_a_pas_de_beta_defini():
    index = jours(50)
    with pytest.raises(ValueError, match="benchmark"):
        beta(
            pd.Series(np.random.default_rng(3).normal(0, 0.01, 50), index=index),
            pd.Series([0.001] * 50, index=index),
        )


def test_trop_peu_de_seances_communes_est_refuse():
    with pytest.raises(ValueError, match="communes"):
        beta(
            pd.Series([0.01], index=jours(1)),
            pd.Series([0.01], index=jours(1)),
        )


# ------------------------------------------------------- VaR : convention --


def test_la_var_est_rendue_en_perte_positive():
    # Des rendements majoritairement négatifs doivent donner une VaR positive.
    rendements = np.array([-0.05, -0.03, -0.02, -0.01, 0.01])
    assert historical_var(rendements, 0.80) > 0.0


def test_la_var_99_depasse_la_var_95_en_magnitude():
    rendements = panel_aleatoire(n=1000, k=1)["T0"]
    assert historical_var(rendements, 0.99) >= historical_var(rendements, 0.95)


def test_un_niveau_de_confiance_hors_bornes_est_refuse():
    for niveau in (0.0, 1.0, 1.5, -0.2):
        with pytest.raises(ValueError, match="confiance"):
            historical_var([0.01, -0.01], niveau)


def test_la_var_historique_rend_une_observation_reelle():
    """`method="lower"` : la perte annoncée a réellement eu lieu."""
    rendements = [-0.10, -0.05, -0.02, 0.01, 0.03]
    resultat = historical_var(rendements, 0.90)
    assert -resultat in rendements
    assert QUANTILE_METHOD == "lower"


def test_la_var_historique_est_conservatrice_face_a_l_interpolation():
    rendements = list(np.linspace(-0.08, 0.05, 40))
    basse = historical_var(rendements, 0.95, method="lower")
    lineaire = historical_var(rendements, 0.95, method="linear")
    assert basse >= lineaire, "la statistique d'ordre est la plus prudente"


# --------------------------------------------------- VaR paramétrique --


def test_la_var_parametrique_suit_la_formule():
    sigma, confiance = 0.012, 0.99
    z = float(norm.ppf(1 - confiance))
    assert parametric_var(sigma, confiance) == pytest.approx(-(0.0 + z * sigma))


def test_le_quantile_normal_vient_de_scipy_pas_d_une_table():
    # 1,6449 et 2,3263 : les valeurs de référence à 95 % et 99 %.
    assert parametric_var(1.0, 0.95) == pytest.approx(1.6449, abs=1e-4)
    assert parametric_var(1.0, 0.99) == pytest.approx(2.3263, abs=1e-4)


def test_la_moyenne_est_exclue_par_defaut_et_optionnelle():
    sigma, mu = 0.01, 0.0005
    sans = parametric_var(sigma, 0.95)
    avec = parametric_var(sigma, 0.95, mean_daily=mu)

    assert avec == pytest.approx(sans - mu)
    assert sans != avec


def test_une_volatilite_negative_est_refusee():
    with pytest.raises(ValueError, match="négative"):
        parametric_var(-0.01, 0.95)


# --------------------------------------------------- Expected Shortfall --


def test_le_cvar_depasse_la_var_en_magnitude():
    rendements = panel_aleatoire(n=1000, k=1)["T0"]
    for confiance in (0.90, 0.95, 0.99):
        es = expected_shortfall(rendements, confiance)
        assert es.value >= historical_var(rendements, confiance)


def test_le_cvar_porte_le_nombre_d_observations_de_queue():
    """La fragilité de la queue doit être visible dans la sortie.

    À 99 % sur 504 séances, la moyenne ne porte que sur une poignée de points —
    une estimation d'une nature différente de celle du 95 %, et le chiffre seul
    ne le dirait pas.
    """
    rendements = panel_aleatoire(n=504, k=1)["T0"]

    a_95 = expected_shortfall(rendements, 0.95)
    a_99 = expected_shortfall(rendements, 0.99)

    assert a_95.observations == 504
    assert a_99.tail_observations < a_95.tail_observations
    assert a_99.tail_observations <= 10
    assert a_95.tail_observations >= 20


def test_le_cvar_moyenne_bien_la_queue():
    rendements = [-0.10, -0.08, -0.05, -0.01, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
    resultat = expected_shortfall(rendements, 0.80)

    queue = [r for r in rendements if r <= resultat.threshold]
    assert resultat.value == pytest.approx(-np.mean(queue))
    assert resultat.tail_observations == len(queue)


# ------------------------------------------------------------ Monte Carlo --


def test_la_var_monte_carlo_converge_vers_la_var_parametrique():
    """Vérification croisée entre deux implémentations de la même hypothèse.

    Les deux supposent la normalité : la simulation doit rejoindre la formule
    fermée quand le nombre de tirages augmente. Un écart persistant signalerait
    une erreur dans l'une des deux, pas un hasard de tirage.
    """
    panel = panel_aleatoire(n=504, k=4)
    poids = {"T0": 0.4, "T1": 0.3, "T2": 0.2, "T3": 0.1}
    cov = covariance_matrix(panel)

    sigma = parametric_volatility(poids, cov, periods_per_year=1)
    attendu = parametric_var(sigma, 0.95)

    ecarts = [
        abs(monte_carlo_var(poids, cov, 0.95, simulations=n, seed=1).value - attendu)
        for n in (1_000, 20_000, 400_000)
    ]

    assert ecarts[-1] < ecarts[0], "l'écart doit se resserrer avec les tirages"
    assert ecarts[-1] == pytest.approx(0.0, abs=2e-4)


def test_la_graine_rend_le_resultat_reproductible():
    panel = panel_aleatoire(n=200, k=3)
    poids = {"T0": 0.5, "T1": 0.3, "T2": 0.2}
    cov = covariance_matrix(panel)

    premier = monte_carlo_var(poids, cov, simulations=5_000)
    second = monte_carlo_var(poids, cov, simulations=5_000)

    assert premier.value == second.value, "un risque qui bouge est inutilisable"
    autre = monte_carlo_var(poids, cov, simulations=5_000, seed=99)
    assert autre.value != premier.value


def test_une_matrice_singuliere_donne_une_erreur_explicite():
    # Deux titres parfaitement corrélés : la matrice n'est pas définie positive.
    base = panel_aleatoire(n=100, k=1)["T0"]
    panel = pd.DataFrame({"A": base, "B": base})
    cov = covariance_matrix(panel)

    with pytest.raises(ValueError, match="Cholesky"):
        monte_carlo_var({"A": 0.5, "B": 0.5}, cov, simulations=1_000)


def test_la_var_monte_carlo_respecte_l_ordre_des_niveaux():
    panel = panel_aleatoire(n=300, k=3)
    poids = {"T0": 0.5, "T1": 0.3, "T2": 0.2}
    cov = covariance_matrix(panel)

    a_95 = monte_carlo_var(poids, cov, 0.95, simulations=50_000)
    a_99 = monte_carlo_var(poids, cov, 0.99, simulations=50_000)
    assert a_99.value > a_95.value
