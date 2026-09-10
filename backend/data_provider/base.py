"""Contrat agnostique du fournisseur de données de marché.

Ce module ne connaît aucun fournisseur. Il définit les types et les erreurs que
le reste du projet manipule, de sorte qu'un appelant n'ait jamais à attraper une
exception de `requests` ni à lire un champ nommé comme chez Tiingo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class DailyBar:
    """Une séance pour un titre.

    `close` est le cours brut, `adj_close` le cours ajusté des splits et des
    dividendes. Les deux divergent après chaque opération sur titre, et seul
    `adj_close` donne des rendements justes.

    `split_factor` vaut 1.0 hors split. Toute autre valeur signale que le
    fournisseur a retraité l'historique du titre : les `adj_close` déjà en base
    sont alors périmés (voir `backend.ingestion.prices`).
    """

    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    adj_close: float
    volume: int | None
    split_factor: float = 1.0


@dataclass(frozen=True)
class SecurityInfo:
    """Métadonnées descriptives d'un titre.

    Pas de secteur : aucun des fournisseurs retenus ne l'expose sur son plan
    gratuit. Il est renseigné à la main au seed (`backend.ingestion.universe`).
    """

    ticker: str
    name: str
    exchange: str | None = None


class ProviderError(Exception):
    """Échec d'accès aux données de marché, quel que soit le fournisseur."""


class UnknownTickerError(ProviderError):
    """Le fournisseur ne connaît pas ce ticker. Inutile de réessayer."""


class RateLimitError(ProviderError):
    """Quota du fournisseur épuisé, après épuisement des tentatives."""


class MarketDataProvider(Protocol):
    """Ce que tout adaptateur de fournisseur doit savoir faire."""

    def get_daily_adjusted(
        self, ticker: str, start: date, end: date
    ) -> list[DailyBar]:
        """Séances de `start` à `end` inclus, triées par date croissante.

        Renvoie une liste vide si le titre n'a pas coté sur la période (week-end,
        jours fériés) — ce n'est pas une erreur.
        """
        ...

    def get_security_info(self, ticker: str) -> SecurityInfo:
        """Métadonnées du titre. Lève `UnknownTickerError` s'il est inconnu."""
        ...
