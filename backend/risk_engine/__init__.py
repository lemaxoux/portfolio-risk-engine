"""Moteur de risque.

Trois couches, séparées volontairement :

* `measures` — fonctions PURES : tableaux en entrée, nombres en sortie, aucune
  base de données. C'est là que vit tout ce qui produit un chiffre, et c'est ce
  qui rend les calculs testables contre des résultats connus à la main.
* `returns` — construction et alignement des séries de rendements. Pures elles
  aussi.
* `portfolio` / `engine` — la seule couche qui touche SQLite : elle charge,
  compose, et attache à chaque résultat la fenêtre d'estimation utilisée.

Bloc 4A : volatilité (écart-type et EWMA), max drawdown, Sharpe, Sortino,
concentration HHI. Les mesures multi-titres — covariance, corrélation, beta,
VaR, CVaR — relèvent du bloc 4B et ne sont pas ici.
"""

from __future__ import annotations

from .config import (
    DDOF,
    DEFAULT_BENCHMARK,
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_WINDOW,
    EWMA_LAMBDA,
    RISK_FREE_RATE_OBSERVED_ON,
    TRADING_DAYS_PER_YEAR,
    daily_risk_free_rate,
    risk_free_observation_date,
    risk_free_rate,
)
from .covariance import Beta, beta, correlation_matrix, covariance_matrix
from .engine import (
    BetaResult,
    ConcentrationResult,
    CovarianceResult,
    DrawdownResult,
    ExpectedShortfallResult,
    PortfolioSeries,
    RiskReport,
    SharpeResult,
    SortinoResult,
    VolatilityResult,
    Window,
    VarResult,
    analyse_portfolio,
    beta_vs_benchmark,
    build_portfolio_series,
    covariance_matrices,
)
from .measures import (
    Drawdown,
    annualised_volatility,
    downside_deviation,
    equal_weight_reference,
    ewma_volatility,
    herfindahl_index,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from .portfolio import (
    PortfolioError,
    PortfolioWeights,
    Position,
    load_positions,
    load_price_panel,
    market_value_weights,
)
from .var import (
    QUANTILE_METHOD,
    expected_shortfall,
    historical_var,
    monte_carlo_var,
    parametric_var,
)
from .returns import (
    align_panel,
    log_returns,
    portfolio_returns,
    simple_returns,
    wealth_curve,
)

__all__ = [
    "DDOF",
    "DEFAULT_BENCHMARK",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_WINDOW",
    "EWMA_LAMBDA",
    "RISK_FREE_RATE_OBSERVED_ON",
    "TRADING_DAYS_PER_YEAR",
    "QUANTILE_METHOD",
    "Beta",
    "BetaResult",
    "ConcentrationResult",
    "CovarianceResult",
    "Drawdown",
    "DrawdownResult",
    "PortfolioError",
    "PortfolioSeries",
    "PortfolioWeights",
    "Position",
    "RiskReport",
    "SharpeResult",
    "ExpectedShortfallResult",
    "SortinoResult",
    "VarResult",
    "VolatilityResult",
    "Window",
    "align_panel",
    "analyse_portfolio",
    "annualised_volatility",
    "beta",
    "beta_vs_benchmark",
    "build_portfolio_series",
    "correlation_matrix",
    "covariance_matrices",
    "covariance_matrix",
    "daily_risk_free_rate",
    "downside_deviation",
    "equal_weight_reference",
    "ewma_volatility",
    "expected_shortfall",
    "historical_var",
    "herfindahl_index",
    "load_positions",
    "load_price_panel",
    "log_returns",
    "market_value_weights",
    "max_drawdown",
    "monte_carlo_var",
    "parametric_var",
    "portfolio_returns",
    "risk_free_observation_date",
    "risk_free_rate",
    "sharpe_ratio",
    "simple_returns",
    "sortino_ratio",
    "wealth_curve",
]
