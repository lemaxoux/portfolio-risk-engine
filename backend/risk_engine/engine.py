"""Composition des mesures sur un portefeuille réel.

Cette couche assemble : elle charge (via `portfolio`), construit les séries (via
`returns`), applique les mesures (via `measures`) et rend des résultats qui
portent leur fenêtre d'estimation.

Aucun calcul n'est fait ici — tout ce qui produit un nombre vit dans `measures`,
où il se teste sans base de données.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from . import covariance, measures, var
from .config import (
    DDOF,
    DEFAULT_BENCHMARK,
    DEFAULT_WINDOW,
    EWMA_LAMBDA,
    TRADING_DAYS_PER_YEAR,
    MONTE_CARLO_SEED,
    MONTE_CARLO_SIMULATIONS,
    daily_risk_free_rate,
    risk_free_observation_date,
    risk_free_rate,
)
from .portfolio import (
    PortfolioError,
    PortfolioWeights,
    load_price_panel,
    market_value_weights,
)
from .returns import align_panel, portfolio_returns, simple_returns, wealth_curve


@dataclass(frozen=True)
class Window:
    """Fenêtre d'estimation effectivement utilisée.

    Accompagne chaque résultat. Un chiffre de risque sans sa fenêtre n'est pas
    interprétable : une volatilité de 18 % ne veut pas dire la même chose selon
    qu'elle est estimée sur deux ans ou sur vingt, et rien dans le nombre ne
    permet de le deviner. Transporter la fenêtre avec la valeur est ce qui
    empêche qu'on compare deux mesures incomparables — ou qu'on estime un jour
    une VaR sur tout l'historique depuis 2005 sans s'en apercevoir.
    """

    requested: int
    observations: int
    start: date
    end: date

    @property
    def complete(self) -> bool:
        """Vrai si la fenêtre demandée a pu être remplie entièrement."""
        return self.observations >= self.requested

    def __str__(self) -> str:
        etat = "" if self.complete else f" (demandé : {self.requested})"
        return f"{self.observations} séances, {self.start} → {self.end}{etat}"


@dataclass(frozen=True)
class VolatilityResult:
    annualised: float
    daily: float
    method: str
    window: Window


@dataclass(frozen=True)
class DrawdownResult:
    value: float
    peak_date: date
    trough_date: date
    window: Window


@dataclass(frozen=True)
class SharpeResult:
    annualised: float
    risk_free_annual: float
    risk_free_daily: float
    window: Window
    # Date d'observation du taux sans risque. Même principe que la fenêtre
    # d'estimation : le chiffre transporte de quoi juger sa fraîcheur, au lieu
    # d'obliger à retrouver la constante. None signifie que la date est
    # réellement inconnue — taux imposé sans provenance fournie — et non
    # qu'elle a été perdue en chemin.
    risk_free_observed_on: date | None = None


@dataclass(frozen=True)
class SortinoResult:
    annualised: float | None
    downside_deviation_daily: float
    target_daily: float
    window: Window
    undefined_reason: str | None = None


@dataclass(frozen=True)
class ConcentrationResult:
    """Concentration des poids. Mesure PONCTUELLE, sans fenêtre d'estimation.

    Contrairement aux autres résultats de ce module, elle ne porte pas de
    `Window` : elle ne s'estime pas sur un historique, elle décrit la structure
    du portefeuille à un instant donné. Lui attacher une fenêtre laisserait
    croire à une moyenne dans le temps.

    Elle porte en revanche sa PROVENANCE, qui est la règle de fond : aucun
    résultat ne doit être ininterprétable isolément. Pour une mesure estimée,
    la provenance est la fenêtre ; pour une mesure ponctuelle, c'est la date de
    valorisation — celle des prix ayant servi à calculer les poids. Un HHI de
    0,18 ne dit pas la même chose s'il décrit le portefeuille d'aujourd'hui ou
    celui d'il y a six mois.

    Le champ s'appelle `as_of`, comme dans `PortfolioWeights` et `RiskReport` :
    un même concept, un seul mot.
    """

    hhi: float
    effective_positions: float
    equal_weight_reference: float
    n_positions: int
    as_of: date


@dataclass(frozen=True)
class CovarianceResult:
    """Matrices de covariance et de corrélation des titres détenus.

    Estimées sur observations COMPLÈTES, jamais paire à paire : toutes les
    cellules reposent sur les mêmes dates, ce qui garantit que la matrice reste
    semi-définie positive et donc utilisable par Cholesky.
    """

    covariance: pd.DataFrame = field(repr=False)
    correlation: pd.DataFrame = field(repr=False)
    window: Window
    ddof: int = DDOF


@dataclass(frozen=True)
class BetaResult:
    """Sensibilité au marché et décomposition du risque.

    `r_squared` est la part de variance du portefeuille expliquée par le
    benchmark : c'est le risque systématique. Son complément à 1 est le risque
    idiosyncratique, celui que la diversification peut encore réduire.
    """

    beta: float
    r_squared: float
    benchmark: str
    basis: str
    window: Window

    @property
    def idiosyncratic_share(self) -> float:
        return 1.0 - self.r_squared


@dataclass(frozen=True)
class VarResult:
    """Value at Risk à horizon une séance, en PERTE POSITIVE.

    Voir la convention de signe en tête de `risk_engine.var` : une valeur de
    0,021 se lit « perte d'au moins 2,1 % », une valeur négative signifie un
    gain à ce niveau de confiance.
    """

    value: float
    confidence: float
    method: str
    window: Window
    detail: str = ""


@dataclass(frozen=True)
class ExpectedShortfallResult:
    """Perte moyenne au-delà du quantile de VaR, en perte positive.

    `tail_observations` est porté par le résultat et non relegué aux logs : à
    99 % sur 504 séances, la moyenne ne porte que sur ~5 points. Le chiffre
    reste calculable mais son incertitude n'a rien à voir avec celle du même
    calcul à 95 %, et cela doit se voir dans la sortie.
    """

    value: float
    confidence: float
    tail_observations: int
    threshold: float
    window: Window

    @property
    def thin_tail(self) -> bool:
        """Vrai quand la queue est trop courte pour une moyenne stable."""
        return self.tail_observations < 10


@dataclass(frozen=True)
class PortfolioSeries:
    """Série de rendements d'un portefeuille et son contexte."""

    returns: pd.Series
    wealth: pd.Series
    weights: PortfolioWeights
    window: Window
    asset_returns: pd.DataFrame = field(repr=False)
    benchmark: str | None = None
    benchmark_returns: pd.Series | None = field(default=None, repr=False)


@dataclass(frozen=True)
class RiskReport:
    """Rapport complet : mesures d'une série (4A) et multi-titres (4B).

    Les VaR et Expected Shortfall sont indexés par niveau de confiance, pour que
    le 95 % et le 99 % soient lisibles côte à côte sans multiplier les champs.
    """

    portfolio_id: int
    as_of: date
    total_value: float
    weights: dict[str, float]
    window: Window
    volatility: VolatilityResult
    ewma_volatility: VolatilityResult
    drawdown: DrawdownResult
    sharpe: SharpeResult
    sortino: SortinoResult
    concentration: ConcentrationResult
    parametric_volatility: VolatilityResult
    matrices: CovarianceResult
    historical_var: dict[float, VarResult]
    parametric_var: dict[float, VarResult]
    expected_shortfall: dict[float, ExpectedShortfallResult]
    beta: BetaResult | None = None
    monte_carlo_var: dict[float, VarResult] | None = None


# ------------------------------------------------------------------ Séries --


def build_portfolio_series(
    conn: sqlite3.Connection,
    portfolio_id: int,
    window: int = DEFAULT_WINDOW,
    benchmark: str | None = None,
) -> PortfolioSeries:
    """Construit la série de rendements du portefeuille sur la fenêtre demandée.

    Poids ACTUELS appliqués aux rendements historiques : hypothèse de
    rééquilibrage quotidien, détaillée dans `returns.portfolio_returns`.

    Le benchmark, quand il est demandé, entre dans le MÊME panel aligné que les
    titres détenus. Ce n'est pas un détail d'implémentation : charger sa série
    séparément ferait porter ses rendements sur ses propres séances à lui. Si
    une séance manque à un titre du portefeuille, le rendement du portefeuille
    couvrirait alors j1→j3 pendant que celui du benchmark couvrirait j2→j3, et
    le beta comparérait des intervalles différents sans que rien ne le signale.
    """
    if window < 2:
        raise ValueError(f"Fenêtre trop courte : {window} (minimum 2 séances).")

    poids = market_value_weights(conn, portfolio_id)
    tickers = poids.tickers
    colonnes = tickers + (
        [benchmark] if benchmark and benchmark not in tickers else []
    )

    panel = load_price_panel(conn, colonnes)

    # `load_price_panel` ne lève que si AUCUN titre n'a de prix ; un benchmark
    # absent alors que les titres détenus sont là passerait donc au travers et
    # ressortirait bien plus loin en KeyError sur une colonne manquante.
    absents = [t for t in colonnes if t not in panel.columns]
    if absents:
        aide = (
            f" Le charger avec `python -m backend.ingestion add {benchmark}`, "
            "ou demander l'analyse sans benchmark (benchmark=None)."
            if benchmark in absents
            else ""
        )
        raise PortfolioError(f"Aucun prix en base pour {absents}.{aide}")

    aligne = align_panel(panel)
    if len(aligne) < 2:
        raise PortfolioError(
            "Moins de deux séances communes à tous les titres : impossible de "
            "calculer un rendement. Vérifier la couverture avec "
            "`python -m backend.ingestion status`."
        )

    rendements = simple_returns(aligne)
    rendements_titres = rendements[tickers]
    serie_complete = portfolio_returns(rendements_titres, poids.weights)
    serie = serie_complete.tail(window)

    # Le point de départ de la courbe de valeur est la séance qui PRÉCÈDE le
    # premier rendement retenu : sans elle, le sommet initial manquerait et le
    # drawdown serait mesuré depuis un pic trop bas.
    dates_alignees = list(aligne.index)
    depart = dates_alignees[dates_alignees.index(serie.index[0]) - 1]

    return PortfolioSeries(
        returns=serie,
        wealth=wealth_curve(serie, initial_date=depart),
        weights=poids,
        window=Window(
            requested=window,
            observations=len(serie),
            start=serie.index[0],
            end=serie.index[-1],
        ),
        asset_returns=rendements_titres.tail(window),
        benchmark=benchmark,
        benchmark_returns=(
            rendements[benchmark].tail(window) if benchmark else None
        ),
    )


# ---------------------------------------------------------------- Mesures --


def volatility(serie: PortfolioSeries) -> VolatilityResult:
    annualisee = measures.annualised_volatility(serie.returns)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method="écart-type (√252)",
        window=serie.window,
    )


def ewma_volatility(
    serie: PortfolioSeries, lam: float = EWMA_LAMBDA
) -> VolatilityResult:
    annualisee = measures.ewma_volatility(serie.returns, lam=lam)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method=f"EWMA (λ={lam})",
        window=serie.window,
    )


def drawdown(serie: PortfolioSeries) -> DrawdownResult:
    brut = measures.max_drawdown(serie.wealth)
    return DrawdownResult(
        value=brut.value,
        peak_date=brut.peak_date,
        trough_date=brut.trough_date,
        window=serie.window,
    )


def sharpe(
    serie: PortfolioSeries,
    annual_risk_free: float | None = None,
    risk_free_observed_on: date | None = None,
) -> SharpeResult:
    """Sharpe annualisé du portefeuille.

    `risk_free_observed_on` permet de faire voyager la provenance d'un taux
    imposé : celui qui fournit le taux est le seul à savoir de quand il date.
    Sans lui, un taux surchargé ressort avec une date `None`, qui signifie alors
    « réellement inconnue » et non « perdue par construction ».

    Dater le taux par DÉFAUT est refusé : sa provenance est déjà connue
    (`RISK_FREE_RATE_OBSERVED_ON`), et lui en attribuer une autre reviendrait à
    affirmer sur cette valeur quelque chose qui n'est pas vrai.
    """
    surcharge = annual_risk_free is not None
    if risk_free_observed_on is not None and not surcharge:
        raise ValueError(
            "risk_free_observed_on ne se fournit qu'avec annual_risk_free. "
            "Le taux par défaut porte déjà sa date d'observation "
            "(RISK_FREE_RATE_OBSERVED_ON) ; la remplacer lui attribuerait une "
            "provenance qui n'est pas la sienne."
        )

    taux_annuel = annual_risk_free if surcharge else risk_free_rate()
    taux_quotidien = daily_risk_free_rate(taux_annuel)
    return SharpeResult(
        annualised=measures.sharpe_ratio(serie.returns, risk_free_daily=taux_quotidien),
        risk_free_annual=taux_annuel,
        risk_free_daily=taux_quotidien,
        window=serie.window,
        risk_free_observed_on=(
            risk_free_observed_on if surcharge else risk_free_observation_date()
        ),
    )


def sortino(serie: PortfolioSeries, target_daily: float = 0.0) -> SortinoResult:
    deviation = measures.downside_deviation(serie.returns, target_daily)
    ratio = measures.sortino_ratio(serie.returns, target_daily)
    return SortinoResult(
        annualised=ratio,
        downside_deviation_daily=deviation,
        target_daily=target_daily,
        window=serie.window,
        undefined_reason=(
            None
            if ratio is not None
            else "aucun rendement sous la cible sur la fenêtre : "
            "la déviation à la baisse est nulle et le ratio indéfini"
        ),
    )


def concentration(poids: PortfolioWeights) -> ConcentrationResult:
    hhi = measures.herfindahl_index(poids.weights)
    n = len(poids.weights)
    return ConcentrationResult(
        hhi=hhi,
        effective_positions=1.0 / hhi,
        equal_weight_reference=measures.equal_weight_reference(n),
        n_positions=n,
        as_of=poids.as_of,
    )


# ------------------------------------------------------- Mesures multi-titres --


def covariance_matrices(serie: PortfolioSeries) -> CovarianceResult:
    """Covariance et corrélation des titres détenus, sur la fenêtre."""
    return CovarianceResult(
        covariance=covariance.covariance_matrix(serie.asset_returns),
        correlation=covariance.correlation_matrix(serie.asset_returns),
        window=serie.window,
    )


def parametric_volatility(serie: PortfolioSeries) -> VolatilityResult:
    """Volatilité annualisée par la matrice : `√(wᵀΣw) × √252`.

    Égale à `volatility(serie)` à la tolérance flottante près — identité
    algébrique, pas approximation, garantie par la convention `DDOF` partagée.
    """
    matrice = covariance.covariance_matrix(serie.asset_returns)
    annualisee = covariance.parametric_volatility(serie.weights.weights, matrice)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method="matrice de covariance (√(wᵀΣw))",
        window=serie.window,
    )


def beta_vs_benchmark(serie: PortfolioSeries) -> BetaResult:
    """Beta et R² contre le benchmark chargé avec la série."""
    if serie.benchmark is None or serie.benchmark_returns is None:
        raise ValueError(
            "Aucun benchmark dans cette série. La construire avec "
            "`build_portfolio_series(..., benchmark=\"SPY\")`."
        )
    brut = covariance.beta(serie.returns, serie.benchmark_returns)
    return BetaResult(
        beta=brut.beta,
        r_squared=brut.r_squared,
        benchmark=serie.benchmark,
        basis="rendements bruts (non excédentaires)",
        window=serie.window,
    )


# ------------------------------------------------------------------- VaR --


def historical_var(
    serie: PortfolioSeries, confidence: float = 0.95
) -> VarResult:
    return VarResult(
        value=var.historical_var(serie.returns, confidence),
        confidence=confidence,
        method="historique",
        window=serie.window,
        detail=f"quantile empirique, interpolation {var.QUANTILE_METHOD!r}",
    )


def parametric_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    include_mean: bool = False,
) -> VarResult:
    """VaR sous hypothèse de normalité, à partir de `√(wᵀΣw)`.

    `include_mean=False` par défaut : voir `var.parametric_var` pour le
    raisonnement sur l'erreur type de la moyenne.
    """
    matrice = covariance.covariance_matrix(serie.asset_returns)
    sigma_quotidien = covariance.parametric_volatility(
        serie.weights.weights, matrice, periods_per_year=1
    )
    moyenne = float(serie.returns.mean()) if include_mean else 0.0
    return VarResult(
        value=var.parametric_var(sigma_quotidien, confidence, moyenne),
        confidence=confidence,
        method="paramétrique",
        window=serie.window,
        detail=(
            "normalité, μ estimée" if include_mean else "normalité, μ = 0"
        ),
    )


def expected_shortfall(
    serie: PortfolioSeries, confidence: float = 0.95
) -> ExpectedShortfallResult:
    brut = var.expected_shortfall(serie.returns, confidence)
    return ExpectedShortfallResult(
        value=brut.value,
        confidence=confidence,
        tail_observations=brut.tail_observations,
        threshold=brut.threshold,
        window=serie.window,
    )


def monte_carlo_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
) -> VarResult:
    matrice = covariance.covariance_matrix(serie.asset_returns)
    brut = var.monte_carlo_var(
        serie.weights.weights,
        matrice,
        confidence=confidence,
        simulations=simulations,
        seed=seed,
    )
    return VarResult(
        value=brut.value,
        confidence=confidence,
        method="Monte Carlo",
        window=serie.window,
        detail=f"{brut.simulations} tirages normaux corrélés, graine {brut.seed}",
    )


# ----------------------------------------------------------------- Rapport --


def analyse_portfolio(
    conn: sqlite3.Connection,
    portfolio_id: int,
    *,
    window: int = DEFAULT_WINDOW,
    annual_risk_free: float | None = None,
    risk_free_observed_on: date | None = None,
    sortino_target_daily: float = 0.0,
    benchmark: str | None = DEFAULT_BENCHMARK,
    confidence_levels: tuple[float, ...] = (0.95, 0.99),
    monte_carlo: bool = False,
) -> RiskReport:
    """Toutes les mesures des blocs 4A et 4B sur un portefeuille.

    `benchmark=None` désactive le beta, pour un portefeuille dont l'indice de
    référence n'est pas en base. `monte_carlo=False` par défaut : la simulation
    est déterministe (graine fixe) mais reste un calcul qu'on ne paie que si on
    le demande.
    """
    serie = build_portfolio_series(
        conn, portfolio_id, window=window, benchmark=benchmark
    )
    return RiskReport(
        portfolio_id=portfolio_id,
        as_of=serie.weights.as_of,
        total_value=serie.weights.total_value,
        weights=serie.weights.weights,
        window=serie.window,
        volatility=volatility(serie),
        ewma_volatility=ewma_volatility(serie),
        drawdown=drawdown(serie),
        sharpe=sharpe(serie, annual_risk_free, risk_free_observed_on),
        sortino=sortino(serie, sortino_target_daily),
        concentration=concentration(serie.weights),
        parametric_volatility=parametric_volatility(serie),
        matrices=covariance_matrices(serie),
        historical_var={c: historical_var(serie, c) for c in confidence_levels},
        parametric_var={c: parametric_var(serie, c) for c in confidence_levels},
        expected_shortfall={
            c: expected_shortfall(serie, c) for c in confidence_levels
        },
        beta=beta_vs_benchmark(serie) if benchmark else None,
        monte_carlo_var=(
            {c: monte_carlo_var(serie, c) for c in confidence_levels}
            if monte_carlo
            else None
        ),
    )
