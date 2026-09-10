"""Ingestion des données de marché vers la base locale.

Trois opérations, une par situation :

* `backfill`      — chargement initial depuis `BACKFILL_START`.
* `refresh`       — rattrapage depuis la dernière séance connue de chaque titre.
* `ensure_ticker` — chargement à la demande d'un titre absent de la base.

Toutes passent par `backend.data_provider` et ignorent quel fournisseur est
derrière.
"""

from __future__ import annotations

from .prices import (
    IngestionReport,
    TickerResult,
    backfill,
    ensure_ticker,
    last_stored_date,
    refresh,
)
from .universe import BACKFILL_START, BENCHMARK_TICKER, DEV_UNIVERSE, dev_tickers

__all__ = [
    "BACKFILL_START",
    "BENCHMARK_TICKER",
    "DEV_UNIVERSE",
    "IngestionReport",
    "TickerResult",
    "backfill",
    "dev_tickers",
    "ensure_ticker",
    "last_stored_date",
    "refresh",
]
