"""Migration du schéma et couche d'écriture des portefeuilles.

Une migration est la seule opération du projet qui modifie une base déjà
peuplée. Trois propriétés la rendent sûre, et chacune a son test : elle est
idempotente, elle laisse une base neuve et une base migrée indiscernables, et
elle n'invente aucune donnée pour les lignes existantes.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from backend.db.init_db import connect, init_db
from backend.db.migrate import (
    migrate,
    missing_schema_hint,
    schema_is_current,
    table_columns,
)
from backend.db import portfolios as store


@pytest.fixture
def base_v1(tmp_path):
    """Une base au schéma d'avant la phase 7A, avec une ligne dedans."""
    chemin = tmp_path / "v1.sqlite"
    init_db(chemin)
    conn = connect(chemin)
    with conn:
        conn.execute("DROP TABLE positions")
        conn.execute("DROP TABLE portfolios")
        conn.execute(
            "CREATE TABLE portfolios ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE positions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, portfolio_id INTEGER NOT NULL, "
            "ticker TEXT NOT NULL, quantity REAL NOT NULL, cost_basis REAL, "
            "UNIQUE (portfolio_id, ticker), "
            "FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE)"
        )
        conn.execute("INSERT INTO portfolios (owner) VALUES ('ancien')")
    yield conn, chemin
    conn.close()


# ══════════════════════════════════════════════════════ Migration ══


def test_la_migration_ajoute_les_deux_colonnes(base_v1):
    conn, _ = base_v1
    assert not schema_is_current(conn)
    appliquees = migrate(conn)
    assert len(appliquees) == 2
    assert schema_is_current(conn)
    assert {"id", "owner", "name", "updated_at"} == table_columns(conn, "portfolios")


def test_la_migration_est_idempotente(base_v1):
    """Elle inspecte l'état de la base avant d'écrire : la relancer ne lève pas."""
    conn, _ = base_v1
    migrate(conn)
    assert migrate(conn) == []
    assert migrate(conn) == []


def test_une_base_neuve_et_une_base_migree_sont_indiscernables(base_v1, tmp_path):
    """Sinon on testerait contre une forme que personne n'utilise.

    La base de l'utilisateur est migrée, pas recréée : c'est elle qui doit
    correspondre à `schema.sql`, y compris dans l'ORDRE des colonnes, puisque
    `ALTER TABLE ADD COLUMN` ajoute en fin de table.
    """
    conn, _ = base_v1
    migrate(conn)
    migree = [r["name"] for r in conn.execute("PRAGMA table_info(portfolios)")]

    neuve_chemin = tmp_path / "neuve.sqlite"
    init_db(neuve_chemin)
    neuve = connect(neuve_chemin)
    attendue = [r["name"] for r in neuve.execute("PRAGMA table_info(portfolios)")]
    neuve.close()

    assert migree == attendue


def test_la_migration_ne_date_pas_retroactivement_les_lignes_existantes(base_v1):
    """`updated_at` reste NULL.

    Écrire la date du jour affirmerait une date de modification qu'on ne connaît
    pas — exactement ce que le projet s'interdit partout ailleurs pour les dates
    de valorisation. NULL se lit « jamais modifié depuis l'application », et
    c'est vrai.
    """
    conn, _ = base_v1
    migrate(conn)
    ligne = conn.execute("SELECT name, updated_at FROM portfolios").fetchone()
    assert ligne["updated_at"] is None
    assert ligne["name"] == "Portefeuille"


def test_la_migration_conserve_les_donnees(base_v1):
    conn, _ = base_v1
    migrate(conn)
    assert conn.execute("SELECT owner FROM portfolios").fetchone()["owner"] == "ancien"


def test_migrer_une_base_sans_table_est_refuse_avec_la_bonne_commande(tmp_path):
    chemin = tmp_path / "rien.sqlite"
    conn = connect(chemin)
    try:
        assert "init_db" in missing_schema_hint(conn)
        with pytest.raises(sqlite3.OperationalError, match="init_db"):
            migrate(conn)
    finally:
        conn.close()


def test_le_conseil_distingue_base_non_initialisee_et_base_non_migree(base_v1):
    """Deux causes, deux commandes : un message unique enverrait au mauvais endroit."""
    conn, _ = base_v1
    conseil = missing_schema_hint(conn)
    assert "migrate" in conseil
    assert "name" in conseil and "updated_at" in conseil
    migrate(conn)
    assert missing_schema_hint(conn) is None


def test_l_application_refuse_de_demarrer_sur_une_base_non_migree(
    base_v1, client_factory
):
    """La panne se produit au démarrage avec la commande à lancer, plutôt qu'à la
    première requête sous la forme d'un « no such column » en 500."""
    conn, chemin = base_v1
    conn.close()
    with pytest.raises(RuntimeError, match="migrate"):
        with client_factory(chemin):
            pass


# ═════════════════════════════════════ Écriture des portefeuilles ══


@pytest.fixture
def base_ecriture(tmp_path):
    chemin = tmp_path / "ecriture.sqlite"
    init_db(chemin)
    conn = connect(chemin)
    with conn:
        conn.execute("INSERT INTO securities (ticker, name) VALUES ('ALFA', 'Alfa')")
        conn.execute("INSERT INTO securities (ticker, name) VALUES ('ZULU', 'Zulu')")
    yield conn
    conn.close()


def test_la_creation_laisse_updated_at_nul(base_ecriture):
    portefeuille = store.create(base_ecriture, "Test")
    assert portefeuille.updated_at is None
    assert store.get(base_ecriture, portefeuille.id) == portefeuille


def test_le_remplacement_date_les_positions_et_non_la_creation(base_ecriture):
    portefeuille = store.create(base_ecriture)
    store.replace_positions(
        base_ecriture,
        portefeuille.id,
        [store.PositionRow("ALFA", 10.0, None)],
        updated_on=date(2026, 3, 4),
    )
    relu = store.get(base_ecriture, portefeuille.id)
    assert relu.updated_at == date(2026, 3, 4)


def test_le_remplacement_efface_les_anciennes_lignes(base_ecriture):
    portefeuille = store.create(base_ecriture)
    store.replace_positions(
        base_ecriture,
        portefeuille.id,
        [store.PositionRow("ALFA", 10.0, None), store.PositionRow("ZULU", 5.0, None)],
    )
    store.replace_positions(
        base_ecriture, portefeuille.id, [store.PositionRow("ZULU", 1.0, None)]
    )
    assert store.load_positions(base_ecriture, portefeuille.id) == [
        store.PositionRow("ZULU", 1.0, None)
    ]


def test_un_remplacement_qui_echoue_ne_detruit_pas_l_existant(base_ecriture):
    """La transaction couvre le DELETE et les INSERT.

    Sans elle, un ticker absent de `securities` laisserait le portefeuille vidé
    de ses lignes valides — un état plus mauvais que celui de départ.
    """
    portefeuille = store.create(base_ecriture)
    store.replace_positions(
        base_ecriture, portefeuille.id, [store.PositionRow("ALFA", 10.0, None)]
    )

    with pytest.raises(sqlite3.IntegrityError):
        store.replace_positions(
            base_ecriture,
            portefeuille.id,
            [
                store.PositionRow("ZULU", 2.0, None),
                store.PositionRow("INCONNU", 1.0, None),
            ],
        )

    assert store.load_positions(base_ecriture, portefeuille.id) == [
        store.PositionRow("ALFA", 10.0, None)
    ]


def test_la_suppression_cascade_sur_les_positions(base_ecriture):
    """La cascade suppose `PRAGMA foreign_keys = ON`, réémis à chaque ouverture."""
    portefeuille = store.create(base_ecriture)
    store.replace_positions(
        base_ecriture, portefeuille.id, [store.PositionRow("ALFA", 10.0, None)]
    )
    assert store.delete(base_ecriture, portefeuille.id) is True
    assert store.get(base_ecriture, portefeuille.id) is None
    assert store.load_positions(base_ecriture, portefeuille.id) == []


def test_supprimer_un_portefeuille_absent_ne_leve_pas(base_ecriture):
    assert store.delete(base_ecriture, 999) is False


def test_un_portefeuille_absent_rend_none_plutot_que_de_lever(base_ecriture):
    """L'absence est une réponse ordinaire à une question d'existence ;
    l'appelant en tire le code HTTP qui lui convient."""
    assert store.get(base_ecriture, 999) is None
