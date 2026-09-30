"""Dépendances FastAPI : une connexion SQLite par requête, fermée à coup sûr.

UNE CONNEXION PAR REQUÊTE, PAS UNE GLOBALE. Les routes de ce projet sont
écrites en `def` et non en `async def` : elles font du SQLite et du pandas, deux
travaux bloquants, et FastAPI les exécute donc dans un fil du pool plutôt que
dans la boucle d'événements. Une connexion partagée entre requêtes serait
utilisée par plusieurs fils EN MÊME TEMPS : c'est ce qu'il faut exclure, et une
connexion par requête l'exclut par construction.

MAIS LA CONNEXION D'UNE REQUÊTE CHANGE DE FIL. FastAPI ouvre la dépendance dans
un fil du pool, exécute la route dans un autre, et referme la dépendance dans
un troisième. `sqlite3` refuse par défaut qu'une connexion serve hors du fil
qui l'a ouverte (`ProgrammingError: SQLite objects created in a thread can only
be used in that same thread`). Tant que les requêtes arrivaient une à une, le
pool réutilisait le plus souvent le même fil ; dès que des pages en ont envoyé
plusieurs à la fois, des requêtes ont répondu 500 au hasard.

D'où `cross_thread=True` ICI, et seulement ici. Ce n'est pas le partage d'une
connexion entre fils qui travaillent ensemble : c'est une connexion qui passe
de main en main, chaque étape attendue avant la suivante — ouverture, route,
fermeture. Aucun accès simultané, donc aucune course à rendre silencieuse.
`tests/test_api_dependencies.py` rejoue le trajet sur trois fils neufs.

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
    conn = connect(cross_thread=True)
    try:
        yield conn
    finally:
        conn.close()
