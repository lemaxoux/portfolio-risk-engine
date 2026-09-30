"""La connexion d'une requête traverse plusieurs fils, l'un après l'autre.

FastAPI exécute une dépendance à `yield` et la route qui s'en sert dans des
fils du pool DISTINCTS : l'ouverture dans l'un, la route dans un autre, la
fermeture dans un troisième. `sqlite3` refuse par défaut qu'une connexion
serve hors du fil qui l'a ouverte. Tant que les requêtes arrivaient une à une,
le pool réutilisait le plus souvent le même fil et le défaut ne se voyait pas.
Les pages de saisie envoient plusieurs requêtes à la fois — liste des
portefeuilles, univers des titres — : la liste répondait 500, au hasard.

Ces tests reproduisent le trajet avec un fil NEUF à chaque étape.
"""

from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.api.dependencies import get_connection
from backend.db.init_db import init_db


def _dans_un_fil_neuf(fonction):
    """Exécute `fonction` dans un fil qui n'a jamais servi, et rend son résultat."""
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(fonction).result()


@pytest.fixture
def base(tmp_path, monkeypatch):
    chemin = init_db(tmp_path / "fils.sqlite")
    monkeypatch.setenv("MX_RISK_DB_PATH", str(chemin))
    return chemin


def test_ouverte_dans_un_fil_utilisee_dans_un_autre_fermee_dans_un_troisieme(base):
    dependance = get_connection()
    fils = []

    def ouvrir():
        fils.append(threading.get_ident())
        return next(dependance)

    conn = _dans_un_fil_neuf(ouvrir)

    def router():
        fils.append(threading.get_ident())
        return conn.execute("SELECT count(*) FROM portfolios").fetchone()[0]

    assert _dans_un_fil_neuf(router) == 0

    def fermer():
        fils.append(threading.get_ident())
        next(dependance, None)

    _dans_un_fil_neuf(fermer)

    assert len(set(fils)) == 3, "témoin : trois fils distincts ont bien servi"
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
