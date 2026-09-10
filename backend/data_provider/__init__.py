"""Accès aux données de marché.

Seul module autorisé à parler au fournisseur de prix (Tiingo en v1). Le reste
du projet importe exclusivement ce qui est exposé ici : ni `tiingo`, ni
`requests`, ni un nom de champ propre au fournisseur ne doivent apparaître
ailleurs. Changer de fournisseur revient alors à écrire un nouvel adaptateur
et à modifier `_build_default_provider`, sans toucher au reste du code.
"""

from __future__ import annotations

from datetime import date

from .base import (
    DailyBar,
    MarketDataProvider,
    ProviderError,
    RateLimitError,
    SecurityInfo,
    UnknownTickerError,
)
from .tiingo import TiingoProvider

__all__ = [
    "DailyBar",
    "SecurityInfo",
    "MarketDataProvider",
    "ProviderError",
    "RateLimitError",
    "UnknownTickerError",
    "get_daily_adjusted",
    "get_security_info",
    "get_provider",
    "set_provider",
]

_provider: MarketDataProvider | None = None


def _build_default_provider() -> MarketDataProvider:
    """Le seul endroit du projet qui décide quel fournisseur est utilisé."""
    return TiingoProvider()


def get_provider() -> MarketDataProvider:
    """Fournisseur par défaut, construit à la première utilisation.

    La construction est différée pour qu'importer ce module ne réclame pas de
    clé API : les tests et le moteur de risque importent les types sans jamais
    ouvrir de connexion.
    """
    global _provider
    if _provider is None:
        _provider = _build_default_provider()
    return _provider


def set_provider(provider: MarketDataProvider | None) -> None:
    """Remplace le fournisseur par défaut (tests, double de simulation).

    `None` réinitialise, pour qu'un test ne laisse pas son double en place.
    """
    global _provider
    _provider = provider


def get_daily_adjusted(ticker: str, start: date, end: date) -> list[DailyBar]:
    """Séances de `start` à `end` inclus, triées par date croissante."""
    return get_provider().get_daily_adjusted(ticker, start, end)


def get_security_info(ticker: str) -> SecurityInfo:
    """Métadonnées descriptives du titre (nom, place de cotation)."""
    return get_provider().get_security_info(ticker)
