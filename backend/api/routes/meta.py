"""`GET /api/meta` — état de la base. `GET /api/disclaimer` — le bandeau.
`GET /api/csv-format` — le format que lit l'import CSV."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.langue import Langue
from backend.risk_engine.config import PRICE_CURRENCY
from backend.risk_engine.portfolio import latest_price_date, load_securities

from .. import csv_import
from ..dependencies import get_connection
from ..langue import langue_demandee
from ..schemas import CsvDelimiterOut, CsvFormatOut, DisclaimerOut, MetaOut
from ..validation import MAX_POSITIONS

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
        price_currency=PRICE_CURRENCY,
    )


@router.get("/disclaimer", response_model=DisclaimerOut)
def read_disclaimer(langue: Langue = Depends(langue_demandee)) -> DisclaimerOut:
    """Le bandeau d'acceptation, EN LECTURE SEULE et sans portefeuille.

    L'écran d'acceptation est une page entière que l'on traverse avant le
    premier accès (DESIGN.md §15) : il précède donc l'existence du moindre
    portefeuille. Servir ce texte uniquement dans `/analysis` forcerait le
    client à en embarquer une copie, et cette copie deviendrait le texte
    réellement affiché le jour où le bandeau changerait — un texte à portée
    quasi juridique figé dans un bundle, sans que personne s'en aperçoive.

    Cette route ne prend qu'un paramètre, la langue du texte (`lang`, « fr »
    par défaut, chantier 7D), et ne touche pas à la base. La fenêtre citée est
    celle de la configuration du moteur (`DEFAULT_WINDOW`), la même que celle
    qu'une analyse demande par défaut. Une analyse lancée sur une autre fenêtre
    publie son propre texte dans sa réponse, où la fenêtre citée est celle qui
    a réellement servi.
    """
    return DisclaimerOut.seul(langue=langue)


@router.get("/csv-format", response_model=CsvFormatOut)
def read_csv_format() -> CsvFormatOut:
    """Le format que lit l'import CSV, EN LECTURE SEULE et sans base.

    L'écran d'import affiche ce format en clair, sur place (DESIGN.md §8.2,
    §13). Il le lit ici plutôt que d'en garder une copie : chaque valeur vient
    de la table ou de la constante que le lecteur consulte lui-même, si bien
    qu'un format affiché ne peut pas diverger du format lu.
    """
    return CsvFormatOut(
        expected_header=csv_import.EN_TETE_ATTENDU,
        required_columns=list(csv_import.COLONNES_REQUISES),
        optional_columns=list(csv_import.COLONNES_FACULTATIVES),
        delimiters=[
            CsvDelimiterOut(
                delimiter=separateur,
                decimal_separators=list(csv_import.DECIMALES_ADMISES[separateur]),
            )
            for separateur in csv_import.DELIMITERS
        ],
        thousands_separators=list(csv_import.ESPACES),
        encodings=[csv_import.ENCODAGE_BOM, *csv_import.ENCODAGES_ESSAYES],
        max_bytes=csv_import.MAX_BYTES,
        max_positions=MAX_POSITIONS,
        example=csv_import.EXEMPLE,
    )
