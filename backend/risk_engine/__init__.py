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
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_WINDOW,
    EWMA_LAMBDA,
    RISK_FREE_RATE_OBSERVED_ON,
    TRADING_DAYS_PER_YEAR,
    daily_risk_free_rate,
    risk_free_observation_date,
    risk_free_rate,
)
from .engine import (
    ConcentrationResult,
    DrawdownResult,
    PortfolioSeries,
    RiskReport,
    SharpeResult,
    SortinoResult,
    VolatilityResult,
    Window,
    analyse_portfolio,
    build_portfolio_series,
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
from .returns import (
    align_panel,
    log_returns,
    portfolio_returns,
    simple_returns,
    wealth_curve,
)

__all__ = [
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_WINDOW",
    "EWMA_LAMBDA",
    "RISK_FREE_RATE_OBSERVED_ON",
    "TRADING_DAYS_PER_YEAR",
    "ConcentrationResult",
    "Drawdown",
    "DrawdownResult",
    "PortfolioError",
    "PortfolioSeries",
    "PortfolioWeights",
    "Position",
    "RiskReport",
    "SharpeResult",
    "SortinoResult",
    "VolatilityResult",
    "Window",
    "align_panel",
    "analyse_portfolio",
    "annualised_volatility",
    "build_portfolio_series",
    "daily_risk_free_rate",
    "downside_deviation",
    "equal_weight_reference",
    "ewma_volatility",
    "herfindahl_index",
    "load_positions",
    "load_price_panel",
    "log_returns",
    "market_value_weights",
    "max_drawdown",
    "portfolio_returns",
    "risk_free_observation_date",
    "risk_free_rate",
    "sharpe_ratio",
    "simple_returns",
    "sortino_ratio",
    "wealth_curve",
]
