"""Fixtures communes aux tests d'API.

LA BASE DE TEST EST TOUJOURS UNE COPIE. Les tests écrivent des portefeuilles,
en suppriment, remplacent des positions : les faire travailler sur
`data/mx_risk.sqlite` détruirait les données de l'utilisateur. La variable
d'environnement `MX_RISK_DB_PATH` est repositionnée pour chaque test qui
utilise l'application, puisque c'est elle que lit `db.init_db.get_db_path`, donc
la dépendance de connexion.

POURQUOI PAS UNE BASE SYNTHÉTIQUE PARTOUT — la plupart des tests d'API
construisent leur propre univers, pour contrôler exactement les prix. Mais
certains doivent tourner sur les vraies séries : un scénario 2008 rejoué sur
seize séances inventées ne dirait rien de la sérialisation d'une couverture
partielle, ni du volet Student, qui dépend de la forme réelle des queues.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from backend.db.init_db import connect, init_db

RACINE = Path(__file__).resolve().parents[1]
BASE_REELLE = RACINE / "data" / "mx_risk.sqlite"

besoin_base_reelle = pytest.mark.skipif(
    not BASE_REELLE.exists(), reason="base locale absente"
)


@pytest.fixture
def client_factory(tmp_path, monkeypatch):
    """Fabrique un client de test sur une base donnée.

    Le client est utilisé comme gestionnaire de contexte, ce qui déclenche le
    `lifespan` de l'application — donc le contrôle de schéma. Un test qui
    l'oublierait passerait à côté de cette garde.
    """
    from fastapi.testclient import TestClient

    def _fabriquer(db_path: Path):
        monkeypatch.setenv("MX_RISK_DB_PATH", str(db_path))
        from backend.api.app import create_app

        return TestClient(create_app())

    return _fabriquer


@pytest.fixture
def base_copiee(tmp_path) -> Path:
    """Copie de la base réelle, jetable."""
    if not BASE_REELLE.exists():
        pytest.skip("base locale absente")
    copie = tmp_path / "copie.sqlite"
    shutil.copy(BASE_REELLE, copie)
    return copie


@pytest.fixture
def client_reel(base_copiee, client_factory) -> Iterator:
    with client_factory(base_copiee) as client:
        yield client


PORTEFEUILLE_DEMO = {
    "AAPL": 40,
    "MSFT": 25,
    "JPM": 60,
    "JNJ": 50,
    "XOM": 80,
    "KO": 120,
}


@pytest.fixture
def portefeuille_reel(client_reel) -> int:
    """Portefeuille de six titres sur la base réelle ; renvoie son identifiant."""
    identifiant = client_reel.post(
        "/api/portfolios", json={"name": "Démo"}
    ).json()["id"]
    reponse = client_reel.put(
        f"/api/portfolios/{identifiant}/positions",
        json={
            "positions": [
                {"ticker": ticker, "quantity": quantite}
                for ticker, quantite in PORTEFEUILLE_DEMO.items()
            ]
        },
    )
    assert reponse.status_code == 200, reponse.text
    return identifiant


@pytest.fixture
def analyse_reelle(client_reel, portefeuille_reel):
    """Réponse brute de `/analysis` : l'objet `httpx`, pas le dict.

    Les octets comptent autant que le contenu — c'est sur eux que se vérifie
    l'absence de NaN.
    """
    reponse = client_reel.get(f"/api/portfolios/{portefeuille_reel}/analysis")
    assert reponse.status_code == 200, reponse.text
    return reponse


# ═════════════════════════════════════════════════ Bases synthétiques ══
#
# Prix fabriqués, pour contrôler exactement ce que le moteur va trouver. Les
# tickers sont choisis pour que l'ordre ALPHABÉTIQUE, l'ordre d'INSERTION et
# l'ordre des POIDS soient tous les trois différents : un test d'alignement
# construit sur des tickers dont ces ordres coïncident passerait par accident.

DEBUT = "2024-01-01"


def _series_prix(rendements: np.ndarray, depart: float = 100.0) -> list[float]:
    return [float(v) for v in depart * np.cumprod(1.0 + rendements)]


def construire_base(chemin: Path, titres: dict, seances: int) -> Path:
    """Crée une base peuplée. `titres` : ticker -> (nom, secteur, prix)."""
    init_db(chemin)
    dates = [
        (np.datetime64(DEBUT) + np.timedelta64(jour, "D")).astype(str)
        for jour in range(seances)
    ]
    conn = connect(chemin)
    try:
        with conn:
            for ticker, (nom, secteur, prix) in titres.items():
                conn.execute(
                    "INSERT OR REPLACE INTO securities (ticker, name, sector) "
                    "VALUES (?, ?, ?)",
                    (ticker, nom, secteur),
                )
                conn.executemany(
                    "INSERT OR REPLACE INTO prices "
                    "(ticker, date, close, adj_close) VALUES (?, ?, ?, ?)",
                    [
                        (ticker, date, valeur, valeur)
                        for date, valeur in zip(dates, prix)
                    ],
                )
    finally:
        conn.close()
    return chemin


@pytest.fixture
def base_synthetique(tmp_path) -> Path:
    """Trois titres corrélés différemment, plus le benchmark.

    ALFA et ZULU bougent presque ensemble ; MIKE est indépendant. Les
    corrélations hors diagonale sont donc franchement distinctes, ce qui rend
    une permutation d'étiquettes détectable — sur une matrice dont toutes les
    cases se ressembleraient, un désalignement passerait inaperçu.
    """
    generateur = np.random.default_rng(20260920)
    seances = 300
    commun = generateur.normal(0.0004, 0.011, seances)
    propre_alfa = generateur.normal(0.0, 0.004, seances)
    propre_zulu = generateur.normal(0.0, 0.004, seances)
    propre_mike = generateur.normal(0.0003, 0.013, seances)
    marche = generateur.normal(0.0004, 0.009, seances)

    return construire_base(
        tmp_path / "synthetique.sqlite",
        {
            # Ordre d'insertion volontairement ni alphabétique ni celui des poids.
            "ZULU": ("Zulu Corp", "Energy", _series_prix(commun + propre_zulu, 80.0)),
            "ALFA": ("Alfa Inc", "Financials", _series_prix(commun + propre_alfa, 50.0)),
            "SPY": ("S&P 500 ETF", None, _series_prix(marche, 400.0)),
            "MIKE": ("Mike Ltd", "Health Care", _series_prix(propre_mike, 200.0)),
        },
        seances,
    )


# Quantités telles que l'ordre des POIDS (MIKE, ZULU, ALFA en valeur
# décroissante) diffère de l'ordre alphabétique (ALFA, MIKE, ZULU).
QUANTITES_SYNTHETIQUES = {"ALFA": 10, "MIKE": 30, "ZULU": 40}


@pytest.fixture
def client_synthetique(base_synthetique, client_factory) -> Iterator:
    with client_factory(base_synthetique) as client:
        yield client


@pytest.fixture
def portefeuille_synthetique(client_synthetique) -> int:
    identifiant = client_synthetique.post(
        "/api/portfolios", json={"name": "Synthétique"}
    ).json()["id"]
    reponse = client_synthetique.put(
        f"/api/portfolios/{identifiant}/positions",
        json={
            "positions": [
                {"ticker": ticker, "quantity": quantite}
                for ticker, quantite in QUANTITES_SYNTHETIQUES.items()
            ]
        },
    )
    assert reponse.status_code == 200, reponse.text
    return identifiant
