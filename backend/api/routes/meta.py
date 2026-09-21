"""`GET /api/meta` — état de la base."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.risk_engine.portfolio import latest_price_date, load_securities

from ..dependencies import get_connection
from ..schemas import MetaOut

router = APIRouter(tags=["méta"])


@router.get("/meta", response_model=MetaOut)
def read_meta(conn: sqlite3.Connection = Depends(get_connection)) -> MetaOut:
    """Dernière séance en base et taille de l'univers.

    `as_of` vient de la table des prix, jamais de l'horloge : c'est la seule
    définition de fraîcheur qui ne mente pas un lundi matin, un jour férié, ou
    après une ingestion en panne.
    """
    return MetaOut(
        as_of=latest_price_date(conn),
        securities_count=len(load_securities(conn)),
    )
