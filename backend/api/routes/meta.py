"""`GET /api/meta` — état de la base. `GET /api/disclaimer` — le bandeau."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.risk_engine.portfolio import latest_price_date, load_securities

from ..dependencies import get_connection
from ..schemas import DisclaimerOut, MetaOut

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


@router.get("/disclaimer", response_model=DisclaimerOut)
def read_disclaimer() -> DisclaimerOut:
    """Le bandeau d'acceptation, EN LECTURE SEULE et sans portefeuille.

    L'écran d'acceptation est une page entière que l'on traverse avant le
    premier accès (DESIGN.md §15) : il précède donc l'existence du moindre
    portefeuille. Servir ce texte uniquement dans `/analysis` forcerait le
    client à en embarquer une copie, et cette copie deviendrait le texte
    réellement affiché le jour où le bandeau changerait — un texte à portée
    quasi juridique figé dans un bundle, sans que personne s'en aperçoive.

    Cette route ne prend AUCUN paramètre et ne touche pas à la base. La fenêtre
    citée est celle de la configuration du moteur (`DEFAULT_WINDOW`), la même
    que celle qu'une analyse demande par défaut. Une analyse lancée sur une
    autre fenêtre publie son propre texte dans sa réponse, où la fenêtre citée
    est celle qui a réellement servi.
    """
    return DisclaimerOut.seul()
