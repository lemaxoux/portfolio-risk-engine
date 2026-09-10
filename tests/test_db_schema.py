"""Vérifie que le schéma SQLite s'applique et que ses contraintes tiennent.

Test de setup, pas de test métier : il valide que l'initialisation de la base
fonctionne, pas le moteur de risque (qui n'existe pas encore).
"""

import sqlite3

import pytest

from backend.db.init_db import connect, init_db


@pytest.fixture
def db(tmp_path):
    """Base jetable — n'écrit jamais dans data/."""
    path = tmp_path / "test.sqlite"
    init_db(path)
    with connect(path) as conn:
        yield conn


def test_les_quatre_tables_existent(db):
    tables = {
        row["name"]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"securities", "prices", "portfolios", "positions"} <= tables


def test_init_db_est_idempotent(tmp_path):
    path = tmp_path / "test.sqlite"
    init_db(path)
    with connect(path) as conn:
        conn.execute("INSERT INTO securities (ticker, name) VALUES ('AAPL', 'Apple')")

    init_db(path)  # relance sur une base existante

    with connect(path) as conn:
        rows = conn.execute("SELECT COUNT(*) AS n FROM securities").fetchone()
    assert rows["n"] == 1, "relancer init_db ne doit pas effacer les données"


def test_une_position_exige_un_titre_connu(db):
    db.execute("INSERT INTO portfolios (owner) VALUES ('maxence')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1, 'INCONNU', 10)"
        )


def test_un_prix_ne_peut_pas_etre_duplique(db):
    db.execute("INSERT INTO securities (ticker, name) VALUES ('AAPL', 'Apple')")
    db.execute(
        "INSERT INTO prices (ticker, date, close, adj_close) VALUES ('AAPL', '2026-01-02', 100.0, 100.0)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO prices (ticker, date, close, adj_close) VALUES ('AAPL', '2026-01-02', 101.0, 101.0)"
        )


def test_cost_basis_est_optionnel(db):
    db.execute("INSERT INTO securities (ticker, name) VALUES ('AAPL', 'Apple')")
    db.execute("INSERT INTO portfolios (owner) VALUES ('maxence')")
    db.execute(
        "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1, 'AAPL', 10)"
    )
    row = db.execute("SELECT cost_basis FROM positions").fetchone()
    assert row["cost_basis"] is None
