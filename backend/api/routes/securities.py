"""`GET /api/securities` — l'univers et la couverture de chaque titre."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.risk_engine.portfolio import load_securities

from ..dependencies import get_connection
from ..schemas import SecurityOut

router = APIRouter(tags=["univers"])


@router.get("/securities", response_model=list[SecurityOut])
def read_securities(
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[SecurityOut]:
    """Tous les titres suivis, avec leur première et dernière séance en base.

    Un titre sans aucun prix apparaît avec deux dates nulles et `has_prices` à
    faux, plutôt que de disparaître : « présent mais jamais ingéré » et « absent
    de l'univers » appellent deux actions différentes.
    """
    return [SecurityOut.of(security) for security in load_securities(conn)]
