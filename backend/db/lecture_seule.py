"""La base du serveur public : ouverte en lecture seule, et rien d'autre.

Le serveur public (`backend/public_api/`, chantier 9.6) analyse une
composition qu'il reçoit et ne garde pas. Sa base ne contient aucun
portefeuille, et rien ne doit pouvoir y en écrire un. Ce module est son seul
accès à SQLite, et le seul SQL du serveur public.

═══ LECTURE SEULE AU NIVEAU DE SQLITE ═══

`ouvrir` n'emploie pas `db.init_db.connect`, qui ouvre en écriture et crée le
dossier de la base. Elle ouvre par une adresse `file:` avec `mode=ro` : SQLite
refuse alors toute écriture dans le fichier (« attempt to write a readonly
database »), quoi que fasse le code au-dessus. `immutable=1` ajoute que le
fichier ne changera pas pendant qu'il est ouvert : SQLite ne pose aucun
verrou et ne cherche aucun journal à côté de lui.

═══ LE MOTEUR LIT UN PORTEFEUILLE EN BASE ; CELUI-CI N'Y EST PAS ═══

Toutes les entrées du moteur prennent une connexion et un numéro de
portefeuille, et relisent la table `positions`. Plutôt que de leur donner une
seconde entrée, `poser_la_composition` écrit la composition reçue dans deux
tables TEMPORAIRES, `portfolios` et `positions`, sous le numéro `NUMERO`.

SQLite cherche un nom de table non qualifié dans le schéma temporaire AVANT
la base : le moteur, inchangé, lit donc la composition du visiteur. Ces
tables vivent en mémoire (`temp_store`), dans la connexion de la requête, et
disparaissent avec elle. Deux requêtes ont deux connexions, donc deux jeux de
tables : `tests/test_lecture_seule.py` lance deux analyses en même temps et
compare chacune à celle obtenue seule.

═══ PUIS LA CONNEXION ENTIÈRE EST VERROUILLÉE ═══

Une fois la composition posée, un autorisateur SQLite refuse tout ce qui
n'est pas une lecture : écriture, table temporaire comprise, création,
`ATTACH`, `PRAGMA`. Le moteur ne fait que lire ; s'il cessait de le faire, la
requête échouerait au lieu d'écrire.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from backend.db.portfolios import PositionRow

# Le numéro sous lequel le moteur lit la composition posée. Il n'est jamais
# publié : la réponse du serveur public n'a pas d'identifiant de portefeuille.
NUMERO = 1

# Ce qu'une connexion verrouillée laisse faire : lire une table, lire une
# colonne, appeler une fonction SQL (`MIN`, `MAX`, `COUNT`).
_LECTURES = frozenset({sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION})


def ouvrir(chemin: Path) -> sqlite3.Connection:
    """Une connexion en lecture seule sur la base du serveur.

    `check_same_thread=False` pour la raison de `api/dependencies.py` : la
    connexion d'une requête peut passer d'un fil à l'autre, sans jamais servir
    à deux à la fois.
    """
    adresse = f"{chemin.resolve().as_uri()}?mode=ro&immutable=1"
    conn = sqlite3.connect(adresse, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _lecture_seule(action: int, *_details: object) -> int:
    return sqlite3.SQLITE_OK if action in _LECTURES else sqlite3.SQLITE_DENY


def verrouiller(conn: sqlite3.Connection) -> None:
    """Refuse désormais, sur cette connexion, tout ce qui n'est pas une lecture."""
    conn.set_authorizer(_lecture_seule)


def poser_la_composition(conn: sqlite3.Connection, positions: Sequence[PositionRow]) -> int:
    """Écrit la composition dans des tables temporaires qui masquent celles de
    la base, verrouille la connexion, et rend le numéro sous lequel le moteur
    la lira.

    Les lignes sont celles que `api.validation.validate` a retenues : tickers
    connus, quantités positives, aucun doublon. Les tables n'ont donc pas de
    clé étrangère, qu'une table temporaire ne pourrait d'ailleurs pas porter
    vers la base.
    """
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute(
        """
        CREATE TEMP TABLE portfolios (
            id         INTEGER PRIMARY KEY,
            owner      TEXT NOT NULL,
            name       TEXT NOT NULL,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TEMP TABLE positions (
            portfolio_id INTEGER NOT NULL,
            ticker       TEXT    NOT NULL,
            quantity     REAL    NOT NULL,
            cost_basis   REAL,
            UNIQUE (portfolio_id, ticker)
        )
        """
    )
    # Qualifiées : sans la table temporaire, l'écriture viserait la base, et
    # échouerait de toute façon.
    conn.execute(
        "INSERT INTO temp.portfolios (id, owner, name) VALUES (?, 'public', 'composition')",
        (NUMERO,),
    )
    conn.executemany(
        "INSERT INTO temp.positions (portfolio_id, ticker, quantity, cost_basis) VALUES (?, ?, ?, ?)",
        [(NUMERO, p.ticker, p.quantity, p.cost_basis) for p in positions],
    )
    conn.commit()
    verrouiller(conn)
    return NUMERO


def portefeuilles_en_base(conn: sqlite3.Connection) -> tuple[int, int]:
    """Le nombre de portefeuilles et de positions que la base contient : zéro
    et zéro pour une base du serveur, qui refuse de démarrer sinon."""
    portefeuilles = conn.execute("SELECT COUNT(*) FROM main.portfolios").fetchone()[0]
    positions = conn.execute("SELECT COUNT(*) FROM main.positions").fetchone()[0]
    return portefeuilles, positions


def nombre_de_seances(conn: sqlite3.Connection) -> int:
    """Le nombre de séances distinctes de la base, tous titres confondus."""
    return conn.execute("SELECT COUNT(DISTINCT date) FROM main.prices").fetchone()[0]


def seances_par_titre(conn: sqlite3.Connection) -> dict[str, tuple[int, date, date]]:
    """Pour chaque titre qui a des prix : son nombre de séances, la première
    et la dernière."""
    return {
        ligne["ticker"]: (
            ligne["seances"],
            date.fromisoformat(ligne["debut"]),
            date.fromisoformat(ligne["fin"]),
        )
        for ligne in conn.execute(
            """
            SELECT ticker, COUNT(*) AS seances, MIN(date) AS debut, MAX(date) AS fin
            FROM main.prices
            GROUP BY ticker
            """
        )
    }
