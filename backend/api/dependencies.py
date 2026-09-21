"""Dépendances FastAPI : une connexion SQLite par requête, fermée à coup sûr.

UNE CONNEXION PAR REQUÊTE, PAS UNE GLOBALE. Les routes de ce projet sont
écrites en `def` et non en `async def` : elles font du SQLite et du pandas, deux
travaux bloquants, et FastAPI les exécute donc dans un fil du pool plutôt que
dans la boucle d'événements. Un objet `sqlite3.Connection` partagé entre fils
lèverait `ProgrammingError: SQLite objects created in a thread can only be used
in that same thread`. Ouvrir la connexion dans la dépendance règle le problème
par construction, sans `check_same_thread=False` — lequel n'éliminerait pas la
course, il la rendrait silencieuse.

Le coût d'une ouverture SQLite locale est de l'ordre de la dizaine de
microsecondes : négligeable devant l'analyse elle-même.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from backend.db.init_db import connect


def get_connection() -> Iterator[sqlite3.Connection]:
    """Connexion ouverte pour la durée de la requête, fermée dans tous les cas.

    Le `finally` couvre aussi la requête interrompue et l'exception remontée
    depuis la route : sans lui, un descripteur de fichier fuit à chaque erreur,
    et sous Windows le fichier de base reste verrouillé.
    """
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
