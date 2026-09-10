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

from . import measures
from .config import (
    DEFAULT_WINDOW,
    EWMA_LAMBDA,
    TRADING_DAYS_PER_YEAR,
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
    # Date d'observation du taux sans risque, ou None s'il a été surchargé.
    # Même principe que la fenêtre d'estimation : le chiffre transporte de quoi
    # juger sa fraîcheur, au lieu d'obliger à retrouver la constante.
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
    la provenance est la fenêtre ; pour une mesure ponctuelle, c'est la date des
    prix ayant servi à calculer les poids — un HHI de 0,18 ne dit pas la même
    chose s'il décrit le portefeuille d'aujourd'hui ou celui d'il y a six mois.
    """

    hhi: float
    effective_positions: float
    equal_weight_reference: float
    n_positions: int
    valuation_date: date


@dataclass(frozen=True)
class PortfolioSeries:
    """Série de rendements d'un portefeuille et son contexte."""

    returns: pd.Series
    wealth: pd.Series
    weights: PortfolioWeights
    window: Window
    asset_returns: pd.DataFrame = field(repr=False)


@dataclass(frozen=True)
class RiskReport:
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


# ------------------------------------------------------------------ Séries --


def build_portfolio_series(
    conn: sqlite3.Connection,
    portfolio_id: int,
    window: int = DEFAULT_WINDOW,
) -> PortfolioSeries:
    """Construit la série de rendements du portefeuille sur la fenêtre demandée.

    Poids ACTUELS appliqués aux rendements historiques : hypothèse de
    rééquilibrage quotidien, détaillée dans `returns.portfolio_returns`.
    """
    if window < 2:
        raise ValueError(f"Fenêtre trop courte : {window} (minimum 2 séances).")

    poids = market_value_weights(conn, portfolio_id)
    panel = load_price_panel(conn, poids.tickers)
    aligne = align_panel(panel)

    if len(aligne) < 2:
        raise PortfolioError(
            "Moins de deux séances communes à tous les titres : impossible de "
            "calculer un rendement. Vérifier la couverture avec "
            "`python -m backend.ingestion status`."
        )

    rendements_titres = simple_returns(aligne)
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
    serie: PortfolioSeries, annual_risk_free: float | None = None
) -> SharpeResult:
    surcharge = annual_risk_free is not None
    taux_annuel = annual_risk_free if surcharge else risk_free_rate()
    taux_quotidien = daily_risk_free_rate(taux_annuel)
    return SharpeResult(
        annualised=measures.sharpe_ratio(serie.returns, risk_free_daily=taux_quotidien),
        risk_free_annual=taux_annuel,
        risk_free_daily=taux_quotidien,
        window=serie.window,
        # Un taux passé en argument n'a pas de date connue du moteur.
        risk_free_observed_on=None if surcharge else risk_free_observation_date(),
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
        valuation_date=poids.as_of,
    )


# ----------------------------------------------------------------- Rapport --


def analyse_portfolio(
    conn: sqlite3.Connection,
    portfolio_id: int,
    *,
    window: int = DEFAULT_WINDOW,
    annual_risk_free: float | None = None,
    sortino_target_daily: float = 0.0,
) -> RiskReport:
    """Toutes les mesures du bloc 4A sur un portefeuille.

    Les mesures multi-titres — covariance, corrélation, beta, VaR, CVaR — ne
    sont pas ici : elles relèvent du bloc 4B.
    """
    serie = build_portfolio_series(conn, portfolio_id, window=window)
    return RiskReport(
        portfolio_id=portfolio_id,
        as_of=serie.weights.as_of,
        total_value=serie.weights.total_value,
        weights=serie.weights.weights,
        window=serie.window,
        volatility=volatility(serie),
        ewma_volatility=ewma_volatility(serie),
        drawdown=drawdown(serie),
        sharpe=sharpe(serie, annual_risk_free),
        sortino=sortino(serie, sortino_target_daily),
        concentration=concentration(serie.weights),
    )
