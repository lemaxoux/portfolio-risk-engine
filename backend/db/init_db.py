"""Création de la base SQLite locale à partir de `schema.sql`.

Usage :
    python -m backend.db.init_db

Le script est idempotent (toutes les tables sont créées en IF NOT EXISTS) :
le relancer sur une base existante ne détruit aucune donnée.

Corollaire : il ne migre pas non plus. Ajouter une colonne au schéma n'a aucun
effet sur une table déjà créée -- IF NOT EXISTS passe simplement son tour. Tant
que la base est vide, supprimer le fichier et relancer suffit ; une fois
l'historique chargé, il faudra un ALTER TABLE explicite.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/db/init_db.py -> backend/db -> backend -> racine du projet
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "mx_risk.sqlite"


def get_db_path() -> Path:
    """Chemin de la base : MX_RISK_DB_PATH si défini, sinon data/mx_risk.sqlite."""
    override = os.getenv("MX_RISK_DB_PATH")
    return Path(override).expanduser() if override else DEFAULT_DB_PATH


def connect(db_path: Path | None = None, *, cross_thread: bool = False) -> sqlite3.Connection:
    """Ouvre une connexion avec les contraintes de clés étrangères actives.

    SQLite désactive les foreign keys par défaut, et le PRAGMA est local à la
    connexion : il doit être réémis à chaque ouverture, pas seulement à la
    création de la base.

    `cross_thread` lève le contrôle de `sqlite3` qui refuse qu'une connexion
    serve hors du fil qui l'a ouverte. Réservé à la connexion d'UNE requête
    HTTP, qui passe d'un fil à l'autre sans jamais être utilisée par deux à la
    fois (voir `backend/api/dependencies.py`). Jamais pour une connexion
    partagée.
    """
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=not cross_thread)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> Path:
    """Applique `schema.sql` et renvoie le chemin de la base."""
    path = db_path or get_db_path()
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema)
    return path


if __name__ == "__main__":
    created = init_db()
    print(f"Base initialisée : {created}")
