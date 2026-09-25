"""Sauvegarde de la base avant une opération qui en réécrit une partie.

Aucune opération ne l'appelle d'elle-même : c'est la commande qui réécrit
(`python -m backend.ingestion rebuild`) qui sauvegarde d'abord, et le dit.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path


def sauvegarder(chemin: Path, jour: date) -> Path:
    """Copie la base à côté d'elle, sous `backup-AAAA-MM-JJ.sqlite`.

    Par l'API de sauvegarde de SQLite plutôt que par une copie de fichier :
    elle rend une image cohérente même si l'API lit la base au même moment.

    Une sauvegarde existante n'est jamais écrasée. Relancer deux fois le même
    jour remplacerait sinon l'état d'avant la première opération par celui
    d'après, et la sauvegarde ne sauverait plus rien. La suivante prend un
    suffixe : `backup-AAAA-MM-JJ-2.sqlite`.
    """
    if not chemin.exists():
        raise FileNotFoundError(f"Base introuvable : {chemin}")

    destination = chemin.with_name(f"backup-{jour.isoformat()}.sqlite")
    rang = 2
    while destination.exists():
        destination = chemin.with_name(f"backup-{jour.isoformat()}-{rang}.sqlite")
        rang += 1

    with closing(sqlite3.connect(chemin)) as source, closing(
        sqlite3.connect(destination)
    ) as copie:
        source.backup(copie)
    return destination
