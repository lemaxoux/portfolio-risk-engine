"""Migrations du schéma SQLite.

`init_db` applique `schema.sql` en `IF NOT EXISTS` : il crée ce qui manque, il
ne modifie jamais une table existante. Ajouter une colonne au fichier de schéma
n'a donc aucun effet sur une base déjà peuplée — et la base peuplée est
justement celle qui sert aux tests sur données réelles. D'où ce module, qui
porte les ALTER TABLE explicites.

Usage :
    python -m backend.db.migrate

Trois règles tenues par chaque migration :

* **idempotente** — l'état de la base est inspecté (`PRAGMA table_info`) avant
  toute écriture, et la relancer ne produit ni erreur ni doublon ;
* **écrite aussi dans `schema.sql`** — sinon une base neuve et une base migrée
  divergent, et on teste contre une forme que personne n'utilise ;
* **elle ne remplit pas rétroactivement ce qu'elle ne sait pas.** `updated_at`
  reste NULL sur les lignes existantes : écrire la date du jour affirmerait une
  date de modification inconnue, exactement ce que le projet s'interdit partout
  ailleurs pour les dates de valorisation.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .init_db import connect, get_db_path

# Colonnes attendues sur `portfolios`, avec leur définition d'ALTER TABLE.
#
# `name` est NOT NULL avec DEFAULT : SQLite refuse d'ajouter une colonne NOT NULL
# sans valeur par défaut, puisqu'il devrait l'inventer pour les lignes déjà là.
# Ici le défaut est un libellé neutre, pas une donnée fabriquée.
COLONNES_PORTFOLIOS: tuple[tuple[str, str], ...] = (
    ("name", "TEXT NOT NULL DEFAULT 'Portefeuille'"),
    ("updated_at", "TEXT"),
)


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Colonnes existantes d'une table ; ensemble vide si la table n'existe pas."""
    return {ligne["name"] for ligne in conn.execute(f"PRAGMA table_info({table})")}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Vrai si la table existe : `PRAGMA table_info` lui trouve des
    colonnes."""
    return bool(table_columns(conn, table))


def schema_is_current(conn: sqlite3.Connection) -> bool:
    """Vrai si la base porte déjà toutes les colonnes attendues."""
    colonnes = table_columns(conn, "portfolios")
    if not colonnes:
        return False
    return all(nom in colonnes for nom, _ in COLONNES_PORTFOLIOS)


def missing_schema_hint(conn: sqlite3.Connection) -> str | None:
    """Ce qu'il reste à faire sur cette base, en une phrase actionnable.

    None quand la base est à jour. Distingue les deux causes, parce qu'elles
    n'appellent pas la même commande : une base sans table est une base jamais
    initialisée, une base sans colonne est une base à migrer.
    """
    if not table_exists(conn, "portfolios"):
        return (
            "Base non initialisée : la table `portfolios` est absente. "
            "Lancer : python -m backend.db.init_db"
        )
    if not schema_is_current(conn):
        manquantes = sorted(
            nom
            for nom, _ in COLONNES_PORTFOLIOS
            if nom not in table_columns(conn, "portfolios")
        )
        return (
            f"Base non migrée : colonnes manquantes sur `portfolios` : "
            f"{', '.join(manquantes)}. Lancer : python -m backend.db.migrate"
        )
    return None


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Applique les migrations manquantes ; renvoie les instructions exécutées."""
    if not table_exists(conn, "portfolios"):
        raise sqlite3.OperationalError(
            "La table `portfolios` n'existe pas : initialiser la base d'abord "
            "avec `python -m backend.db.init_db`."
        )

    existantes = table_columns(conn, "portfolios")
    appliquees: list[str] = []
    with conn:
        for nom, definition in COLONNES_PORTFOLIOS:
            if nom in existantes:
                continue
            instruction = f"ALTER TABLE portfolios ADD COLUMN {nom} {definition}"
            conn.execute(instruction)
            appliquees.append(instruction)
    return appliquees


def migrate_path(db_path: Path | None = None) -> list[str]:
    """Ouvre la base (`get_db_path` par défaut), applique `migrate` et la
    referme, même en cas d'erreur. Rend les instructions exécutées, une liste
    vide si la base était à jour ; lève comme `migrate` sur une base sans
    table `portfolios`."""
    chemin = db_path or get_db_path()
    conn = connect(chemin)
    try:
        return migrate(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    chemin = get_db_path()
    instructions = migrate_path(chemin)
    if instructions:
        print(f"Base migrée : {chemin}")
        for instruction in instructions:
            print(f"  {instruction}")
    else:
        print(f"Base déjà à jour : {chemin}")
