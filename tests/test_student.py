"""Tests du Monte Carlo en loi de Student.

Trois choses sont verrouillées : l'estimation de ν par maximum de vraisemblance
(et sa robustesse face à l'échec observé de `scipy.stats.t.fit`), le piège de
mise à l'échelle Σ → S, et la géométrie attendue entre VaR Student et normale.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import kurtosis, t

from backend.db.init_db import connect
from backend.risk_engine.portfolio import load_price_panel
from backend.risk_engine.returns import align_panel, portfolio_returns, simple_returns
from backend.risk_engine.var import (
    fit_student_t,
    monte_carlo_student_var,
    monte_carlo_var,
    parametric_var,
    simulate_student_returns,
    student_scale_matrix,
    student_t_var,
)

BASE_REELLE = Path(__file__).resolve().parents[1] / "data" / "mx_risk.sqlite"

TICKERS = ["A", "B", "C"]
SIGMA = pd.DataFrame(
    [
        [1.44e-4, 0.60e-4, 0.30e-4],
        [0.60e-4, 2.25e-4, 0.45e-4],
        [0.30e-4, 0.45e-4, 0.81e-4],
    ],
    index=TICKERS,
    columns=TICKERS,
)
POIDS = {"A": 0.5, "B": 0.3, "C": 0.2}
SIGMA_PORTEFEUILLE = float(
    np.sqrt(np.array(list(POIDS.values())) @ SIGMA.to_numpy() @ np.array(list(POIDS.values())))
)


# ------------------------------------------------ Estimation de ν par MLE --


@pytest.mark.parametrize("nu_vrai", [3.0, 5.0, 8.0])
def test_le_mle_retrouve_nu_sur_un_echantillon_student(nu_vrai):
    rng = np.random.default_rng(3)
    echantillon = 0.01 * t.rvs(nu_vrai, size=5000, random_state=rng)

    ajustement = fit_student_t(echantillon)

    assert ajustement.nu == pytest.approx(nu_vrai, rel=0.35)
    assert ajustement.observations == 5000


def test_le_mle_n_est_jamais_moins_vraisemblable_que_scipy():
    rng = np.random.default_rng(17)
    for nu in (2.5, 4.0, 7.0):
        x = 0.012 * t.rvs(nu, size=800, random_state=rng) + 0.0003
        naif = t.fit(x)
        assert fit_student_t(x).log_likelihood >= np.sum(t.logpdf(x, *naif)) - 1e-6


def test_la_methode_des_moments_ne_peut_pas_descendre_sous_quatre():
    """La raison du choix du MLE, chiffrée.

    `ν = 6/κ + 4` rend toujours plus de 4 dès que le kurtosis en excès est
    positif : sur un vrai Student à ν = 3, elle se trompe structurellement, là
    où le maximum de vraisemblance retrouve la bonne zone.
    """
    x = t.rvs(3.0, size=5000, random_state=np.random.default_rng(1))
    par_moments = 6.0 / kurtosis(x, fisher=True) + 4.0

    assert par_moments > 4.0
    assert fit_student_t(x).nu < 4.0


def test_trop_peu_d_observations_pour_estimer_nu():
    with pytest.raises(ValueError, match="observations"):
        fit_student_t(np.random.default_rng(0).normal(0, 0.01, 10))


@pytest.mark.skipif(not BASE_REELLE.exists(), reason="base locale absente")
def test_non_regression_sur_la_serie_ou_scipy_a_echoue():
    """Série réelle figée : six titres, poids exacts, dates fixes.

    Au moment de l'écriture, `scipy.stats.t.fit` s'arrêtait sur cette série à
    ν = 2,01 avec une log-vraisemblance inférieure de 13 unités au maximum, situé
    vers ν = 4,07. Le test n'exige pas que scipy échoue — il cesserait de passer
    le jour où scipy s'améliorerait — mais que notre estimateur reste dans la
    zone plausible et ne soit jamais moins vraisemblable.
    """
    poids = {
        "AAPL": 0.15163155753051752,
        "JNJ": 0.16053210972779627,
        "JPM": 0.2558439926982774,
        "KO": 0.12629551780741557,
        "MSFT": 0.14775649945273145,
        "XOM": 0.15794032278326184,
    }
    with closing(connect(BASE_REELLE)) as conn:
        panel = align_panel(
            load_price_panel(conn, list(poids), date(2024, 9, 4), date(2026, 9, 9))
        )
    x = portfolio_returns(simple_returns(panel), poids).to_numpy()

    ajustement = fit_student_t(x)
    naif = t.fit(x)

    assert len(x) == 504
    assert 3.5 < ajustement.nu < 4.7
    assert ajustement.log_likelihood >= np.sum(t.logpdf(x, *naif)) - 1e-6


# ------------------------------------------------- Piège de mise à l'échelle --


def test_la_covariance_simulee_retombe_sur_sigma():
    """S = Σ·(ν−2)/ν : la simulation reproduit la covariance des données.

    L'écart est mesuré en unités de corrélation (normalisé par les diagonales) :
    un écart relatif sur une covariance proche de zéro n'aurait pas de sens.
    """
    tirages = simulate_student_returns(SIGMA, nu=5.0, simulations=400_000, seed=1)
    simulee = np.cov(tirages, rowvar=False)
    echelle = np.sqrt(np.outer(np.diag(SIGMA), np.diag(SIGMA)))

    assert np.max(np.abs(simulee - SIGMA.to_numpy()) / echelle) < 0.02


def test_passer_sigma_comme_echelle_gonflerait_la_volatilite():
    """Le piège, chiffré : √(ν/(ν−2)) de trop, soit +29 % à ν = 5."""
    nu, n = 5.0, 400_000
    vecteur = np.array(list(POIDS.values()))
    rng = np.random.default_rng(7)

    facteur = np.linalg.cholesky(SIGMA.to_numpy())
    naifs = (rng.standard_normal((n, 3)) @ facteur.T) * np.sqrt(nu / rng.chisquare(nu, n))[:, None]
    justes = simulate_student_returns(SIGMA, nu, simulations=n, seed=7)

    rapport_naif = np.std(naifs @ vecteur) / SIGMA_PORTEFEUILLE
    rapport_juste = np.std(justes @ vecteur) / SIGMA_PORTEFEUILLE

    assert rapport_naif == pytest.approx(np.sqrt(nu / (nu - 2.0)), rel=0.01)
    assert rapport_juste == pytest.approx(1.0, rel=0.01)
    assert student_scale_matrix(SIGMA, nu).to_numpy() == pytest.approx(
        SIGMA.to_numpy() * 3.0 / 5.0
    )


# ----------------------------------------------------- ν ≤ 2 : pas de variance --


@pytest.mark.parametrize("nu", [2.0, 1.5])
def test_nu_inferieur_ou_egal_a_deux_leve_une_erreur(nu):
    with pytest.raises(ValueError, match="variance finie"):
        student_t_var(0.01, nu, 0.99)
    with pytest.raises(ValueError, match="variance finie"):
        student_scale_matrix(SIGMA, nu)
    with pytest.raises(ValueError, match="variance finie"):
        monte_carlo_student_var(POIDS, SIGMA, nu, simulations=1_000)


def test_un_nu_estime_sous_deux_est_detecte_et_non_contraint():
    # ν paramétré en log : l'optimiseur peut trouver ν < 2, ce qui doit remonter
    # jusqu'à l'erreur au lieu d'être masqué par une borne.
    x = 0.01 * t.rvs(1.5, size=5000, random_state=np.random.default_rng(4))
    ajustement = fit_student_t(x)

    assert ajustement.nu < 2.0
    with pytest.raises(ValueError, match="variance finie"):
        monte_carlo_student_var(POIDS, SIGMA, ajustement.nu, simulations=1_000)


# ------------------------------------------------- Convergences et géométrie --


def test_la_var_student_converge_vers_la_normale_quand_nu_tend_vers_l_infini():
    sigma = 0.012
    for niveau in (0.95, 0.99):
        normale = parametric_var(sigma, niveau)
        ecarts = [abs(student_t_var(sigma, nu, niveau) - normale) for nu in (5, 30, 1_000, 1e6)]
        assert ecarts == sorted(ecarts, reverse=True), "l'écart doit se resserrer"
        assert ecarts[-1] == pytest.approx(0.0, abs=1e-7)

    simulee = monte_carlo_student_var(POIDS, SIGMA, nu=1e5, confidence=0.99, simulations=400_000, seed=2)
    assert simulee.value == pytest.approx(parametric_var(SIGMA_PORTEFEUILLE, 0.99), rel=0.01)


def test_le_monte_carlo_student_converge_vers_la_forme_fermee():
    """Vérification croisée, comme le Monte Carlo normal face à la paramétrique."""
    for niveau in (0.95, 0.99):
        attendu = student_t_var(SIGMA_PORTEFEUILLE, 4.5, niveau)
        simulee = monte_carlo_student_var(POIDS, SIGMA, 4.5, niveau, simulations=400_000, seed=3)
        assert simulee.value == pytest.approx(attendu, rel=0.015)
        assert simulee.nu == 4.5


@pytest.mark.parametrize("nu", [3.0, 4.0, 5.0, 6.0, 10.0, 30.0])
def test_epaules_plus_minces_et_extremes_plus_lourds(nu):
    """À variance égale : Student moins sévère à 95 % (épaule), plus à 99 % (queue)."""
    sigma = 0.01
    assert student_t_var(sigma, nu, 0.95) < parametric_var(sigma, 0.95)
    assert student_t_var(sigma, nu, 0.99) > parametric_var(sigma, 0.99)


def test_pres_de_nu_deux_les_quantiles_moderes_s_effondrent():
    # L'artefact qu'aurait produit l'échec de scipy (ν = 2,01) : même à 99 %,
    # la VaR Student passerait très en dessous de la normale.
    sigma = 0.01
    assert student_t_var(sigma, 2.012, 0.99) < 0.5 * parametric_var(sigma, 0.99)


def test_la_graine_rend_le_resultat_reproductible():
    premier = monte_carlo_student_var(POIDS, SIGMA, 4.0, simulations=20_000)
    second = monte_carlo_student_var(POIDS, SIGMA, 4.0, simulations=20_000)
    autre = monte_carlo_student_var(POIDS, SIGMA, 4.0, simulations=20_000, seed=99)

    assert premier.value == second.value
    assert autre.value != premier.value


def test_le_student_s_ecarte_du_normal_dans_le_sens_attendu_en_simulation():
    commun = dict(simulations=400_000, seed=11)
    for niveau, plus_severe in ((0.95, False), (0.99, True)):
        normal = monte_carlo_var(POIDS, SIGMA, niveau, **commun).value
        student = monte_carlo_student_var(POIDS, SIGMA, 4.0, niveau, **commun).value
        assert (student > normal) is plus_severe
