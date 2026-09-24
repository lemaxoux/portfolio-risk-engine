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

ET LA COPIE DES VRAIES SÉRIES EST FIGÉE — voir `DATE_GEL`.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest

from backend.db.init_db import connect, init_db

RACINE = Path(__file__).resolve().parents[1]
BASE_REELLE = RACINE / "data" / "mx_risk.sqlite"

# Dernière séance que voient les tests écrits sur les vraies séries.
#
# `data/mx_risk.sqlite` est un fichier VIVANT : `python -m backend.ingestion
# refresh` y ajoute des séances chaque jour. Un test qui en lit la dernière
# date vérifie donc l'état du fichier, et non le code — il échoue le lendemain
# d'un rattrapage sans qu'une ligne ait changé. C'est arrivé : la fenêtre
# attendue 2024-09-05 → 2026-09-09 est devenue 2024-09-19 → 2026-09-23 au
# premier rafraîchissement.
#
# La copie de test est donc tronquée à cette date. Ce qui la rend stable :
#
# * `refresh` repart de la dernière séance EN BASE, donc postérieure au gel :
#   il n'a aucune raison de réécrire une séance figée ;
# * un dividende multiplie tous les `adj_close` ANTÉRIEURS par un même facteur
#   (vérifié chez Tiingo : ratio adj_close / close identique avant la date de
#   détachement). Même si un split déclenchait une reprise complète de
#   l'historique, les RENDEMENTS dans la fenêtre figée ne bougeraient pas ;
# * les cours BRUTS (`close`), qui servent à la valorisation, ne sont jamais
#   ajustés.
#
# Une exception connue, qui vient de l'ingestion et non du gel : le rattrapage
# du 2026-09-23 a réécrit la séance du 2026-09-09 sur la base ajustée d'après
# un dividende, sans toucher à celle du 2026-09-08. Pour KO et SPY, le dernier
# rendement de la fenêtre figée porte donc un faux saut de l'ordre du
# dividende. Les valeurs de référence (beta 0,5672, volatilité 0,13327) sont
# retrouvées à moins de 3e-4 près, dans les tolérances des tests.
DATE_GEL = "2026-09-09"


def copier_base_reelle_figee(destination: Path) -> Path:
    """Copie la base réelle et en retire toute séance postérieure au gel.

    La suppression porte sur la COPIE, jamais sur `data/mx_risk.sqlite`.
    """
    shutil.copy(BASE_REELLE, destination)
    with closing(connect(destination)) as conn, conn:
        conn.execute("DELETE FROM prices WHERE date > ?", (DATE_GEL,))
    return destination

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


PORTEFEUILLE_DEMO = {
    "AAPL": 40,
    "MSFT": 25,
    "JPM": 60,
    "JNJ": 50,
    "XOM": 80,
    "KO": 120,
}


@pytest.fixture(scope="session")
def analyse_reelle(tmp_path_factory):
    """Réponse brute de `/analysis` : l'objet `httpx`, pas le dict.

    Les octets comptent autant que le contenu — c'est sur eux que se vérifie
    l'absence de NaN.

    SESSION-SCOPED, et c'est sûr : ce qui est partagé est une réponse HTTP DÉJÀ
    REÇUE, que les tests se contentent de lire. Aucun d'eux ne la modifie, et
    aucun n'écrit dans la base qui l'a produite — celle-ci est fermée avant même
    que le premier test ne s'exécute. La calculer par test coûtait 2,7 s (copie
    de 9 Mo, analyse complète, scénarios, régimes) répétés une vingtaine de
    fois, pour un résultat identique à chaque tour.

    Un test qui ÉCRIRAIT sur la base réelle ne doit pas réutiliser cette
    fixture : il se copie la base dans son propre `tmp_path` et passe par
    `client_factory`, comme le font déjà les trois tests « sur un portefeuille
    réel » de `test_regime`, `test_rules` et `test_stress`. La frontière est
    là : lire une réponse se partage, toucher une base ne se partage pas.

    `monkeypatch` étant function-scoped, la variable d'environnement est posée
    dans un `MonkeyPatch.context()` qui la retire dès la réponse obtenue : elle
    ne fuit pas sur les tests suivants, qui ont leur propre base.
    """
    if not BASE_REELLE.exists():
        pytest.skip("base locale absente")

    from fastapi.testclient import TestClient

    copie = copier_base_reelle_figee(
        tmp_path_factory.mktemp("analyse_reelle") / "copie.sqlite"
    )

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MX_RISK_DB_PATH", str(copie))
        from backend.api.app import create_app

        with TestClient(create_app()) as client:
            identifiant = client.post(
                "/api/portfolios", json={"name": "Démo"}
            ).json()["id"]
            ecriture = client.put(
                f"/api/portfolios/{identifiant}/positions",
                json={
                    "positions": [
                        {"ticker": ticker, "quantity": quantite}
                        for ticker, quantite in PORTEFEUILLE_DEMO.items()
                    ]
                },
            )
            assert ecriture.status_code == 200, ecriture.text
            reponse = client.get(f"/api/portfolios/{identifiant}/analysis")

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


@pytest.fixture
def base_historique_court(tmp_path):
    """Fabrique une base où une ligne n'a qu'un historique récent.

    C'est le chemin par lequel une fenêtre EFFECTIVE tombe sous les seuils sans
    qu'aucun paramètre ait changé : le panel aligné se réduit à l'intersection
    des dates, donc une demande de 504 séances rend `observations` égal à
    l'historique de la ligne la plus courte, moins un.

    Un plancher sur le paramètre `window` ne protège pas de ce cas — d'où le
    contrôle sur `window.observations` dans le moteur de règles.
    """

    def _fabriquer(seances_courtes: int, seances: int = 300) -> Path:
        generateur = np.random.default_rng(5)
        chemin = construire_base(
            tmp_path / f"court{seances_courtes}.sqlite",
            {
                "LONG": (
                    "Long Inc",
                    "Energy",
                    _series_prix(generateur.normal(0.0004, 0.011, seances), 100.0),
                ),
                "SPY": (
                    "S&P 500 ETF",
                    None,
                    _series_prix(generateur.normal(0.0004, 0.009, seances), 400.0),
                ),
            },
            seances,
        )
        conn = connect(chemin)
        dates = [
            ligne[0]
            for ligne in conn.execute(
                "SELECT DISTINCT date FROM prices ORDER BY date"
            )
        ]
        cours = _series_prix(
            generateur.normal(0.0004, 0.013, seances_courtes), 60.0
        )
        with conn:
            conn.execute(
                "INSERT INTO securities (ticker, name, sector) "
                "VALUES ('COURT', 'Court Ltd', 'Health Care')"
            )
            conn.executemany(
                "INSERT INTO prices (ticker, date, close, adj_close) "
                "VALUES ('COURT', ?, ?, ?)",
                [
                    (date, valeur, valeur)
                    for date, valeur in zip(dates[-seances_courtes:], cours)
                ],
            )
        conn.close()
        return chemin

    return _fabriquer


@pytest.fixture
def analyse_historique_court(base_historique_court, client_factory):
    """Analyse d'un portefeuille dont une ligne a `seances_courtes` cotations."""

    def _analyser(seances_courtes: int):
        chemin = base_historique_court(seances_courtes)
        with client_factory(chemin) as client:
            identifiant = client.post("/api/portfolios", json={}).json()["id"]
            client.put(
                f"/api/portfolios/{identifiant}/positions",
                json={
                    "positions": [
                        {"ticker": "LONG", "quantity": 10},
                        {"ticker": "COURT", "quantity": 20},
                    ]
                },
            )
            return client.get(f"/api/portfolios/{identifiant}/analysis?window=504")

    return _analyser
