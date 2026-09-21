"""Écriture et lecture des portefeuilles de l'utilisateur.

Symétrique de l'existant : `ingestion/prices.py` écrit la table `prices`,
`risk_engine/portfolio.py` la lit. Ici, ce module écrit `portfolios` et
`positions`, et `risk_engine/portfolio.py` les lit. Que deux modules connaissent
les colonnes de `positions` — l'un qui écrit, l'autre qui lit — est le motif du
projet, pas une duplication à corriger.

POURQUOI PAS DANS `risk_engine` — le moteur est en lecture seule par
construction, et `ON DELETE CASCADE` est actif sur ces tables : un `DELETE FROM
portfolios` y efface des positions en silence. Un module capable de ça n'est plus
« une couche mince de lecture ».

POURQUOI PAS DANS `api` — une future commande en ligne (`python -m
backend.db.portfolios`) devrait alors importer la couche HTTP pour écrire en
base. Dépendance à l'envers.

Ce module ne calcule rien et ne valide rien d'autre que ce que le schéma impose :
la validation métier des positions (ticker connu, historique disponible, quantité
positive, doublons) appartient à l'appelant, qui seul sait quoi faire d'une
erreur — un code HTTP, un message de console, une ligne de journal.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

DEFAULT_OWNER = "local"
DEFAULT_NAME = "Portefeuille"


@dataclass(frozen=True)
class PortfolioRow:
    """Un portefeuille tel qu'il est stocké, sans aucune valorisation.

    `updated_at` date le dernier remplacement des POSITIONS. None se lit
    « jamais modifié depuis l'application » : c'est le cas d'un portefeuille
    créé mais encore vide, et celui des lignes antérieures à la migration, pour
    lesquelles la date est réellement inconnue.
    """

    id: int
    name: str
    owner: str
    updated_at: date | None


@dataclass(frozen=True)
class PositionRow:
    ticker: str
    quantity: float
    cost_basis: float | None


def _row(ligne: sqlite3.Row) -> PortfolioRow:
    brut = ligne["updated_at"]
    return PortfolioRow(
        id=ligne["id"],
        name=ligne["name"],
        owner=ligne["owner"],
        updated_at=None if brut is None else date.fromisoformat(brut),
    )


def create(
    conn: sqlite3.Connection,
    name: str = DEFAULT_NAME,
    owner: str = DEFAULT_OWNER,
) -> PortfolioRow:
    """Crée un portefeuille vide et le renvoie.

    `updated_at` reste NULL : aucune position n'a encore été écrite, et dater la
    création reviendrait à annoncer une fraîcheur de positions qui n'existe pas.
    """
    with conn:
        curseur = conn.execute(
            "INSERT INTO portfolios (owner, name) VALUES (?, ?)", (owner, name)
        )
    identifiant = curseur.lastrowid
    return PortfolioRow(id=identifiant, name=name, owner=owner, updated_at=None)


def get(conn: sqlite3.Connection, portfolio_id: int) -> PortfolioRow | None:
    """Le portefeuille, ou None s'il n'existe pas.

    Rend None plutôt que de lever : l'absence est une réponse ordinaire à une
    question d'existence, et l'appelant en tire le code qui lui convient.
    """
    ligne = conn.execute(
        "SELECT id, name, owner, updated_at FROM portfolios WHERE id = ?",
        (portfolio_id,),
    ).fetchone()
    return None if ligne is None else _row(ligne)


def list_all(conn: sqlite3.Connection) -> list[PortfolioRow]:
    """Tous les portefeuilles, du plus récemment identifié au plus ancien."""
    return [
        _row(ligne)
        for ligne in conn.execute(
            "SELECT id, name, owner, updated_at FROM portfolios ORDER BY id"
        )
    ]


def load_positions(conn: sqlite3.Connection, portfolio_id: int) -> list[PositionRow]:
    """Positions brutes, sans valorisation ni contrôle d'existence.

    Doublon apparent avec `risk_engine.portfolio.load_positions`, qui lève sur un
    portefeuille vide parce qu'un portefeuille sans ligne n'a pas de risque à
    mesurer. Ici, un portefeuille vide rend simplement une liste vide : c'est un
    état d'édition normal, pas une erreur.
    """
    return [
        PositionRow(ligne["ticker"], float(ligne["quantity"]), ligne["cost_basis"])
        for ligne in conn.execute(
            """
            SELECT ticker, quantity, cost_basis
            FROM positions
            WHERE portfolio_id = ?
            ORDER BY ticker
            """,
            (portfolio_id,),
        )
    ]


def replace_positions(
    conn: sqlite3.Connection,
    portfolio_id: int,
    positions: Sequence[PositionRow],
    *,
    updated_on: date | None = None,
) -> int:
    """Remplace TOUTES les positions du portefeuille. Renvoie le nombre écrit.

    Une seule transaction : le portefeuille ne passe jamais par un état où les
    anciennes lignes ont disparu sans que les nouvelles soient écrites. Si un
    INSERT échoue — un ticker absent de `securities` viole la clé étrangère —,
    le DELETE est annulé avec lui.

    `updated_on` DATE DU JOUR, et c'est correct ici alors que ça ne l'est jamais
    pour un `as_of`. Les deux ne répondent pas à la même question : un `as_of`
    dit de quand datent les PRIX, information que seule la base détient ; un
    `updated_at` dit quand l'utilisateur a modifié SES positions, ce qui se passe
    à l'instant où il le fait. Le paramètre reste injectable pour que les tests
    n'aient pas à dépendre de l'horloge.
    """
    quand = updated_on or date.today()
    with conn:
        conn.execute("DELETE FROM positions WHERE portfolio_id = ?", (portfolio_id,))
        conn.executemany(
            """
            INSERT INTO positions (portfolio_id, ticker, quantity, cost_basis)
            VALUES (?, ?, ?, ?)
            """,
            [(portfolio_id, p.ticker, p.quantity, p.cost_basis) for p in positions],
        )
        conn.execute(
            "UPDATE portfolios SET updated_at = ? WHERE id = ?",
            (quand.isoformat(), portfolio_id),
        )
    return len(positions)


def delete(conn: sqlite3.Connection, portfolio_id: int) -> bool:
    """Supprime le portefeuille et, par cascade, ses positions.

    La cascade suppose `PRAGMA foreign_keys = ON`, que `db.init_db.connect`
    réémet à chaque ouverture — le PRAGMA est local à la connexion, pas
    persistant dans le fichier.
    """
    with conn:
        curseur = conn.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    return curseur.rowcount > 0
