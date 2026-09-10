"""Chargement d'un portefeuille et de son historique depuis SQLite.

Couche mince et unique frontière entre le moteur et la base : tout ce qui est
au-dessus (`measures`, `returns`) travaille sur des tableaux et ignore d'où ils
viennent, exactement comme `data_provider` isole le fournisseur de prix.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

import pandas as pd


class PortfolioError(Exception):
    """Portefeuille introuvable, vide, ou sans prix exploitables."""


@dataclass(frozen=True)
class Position:
    ticker: str
    quantity: float
    cost_basis: float | None


@dataclass(frozen=True)
class PortfolioWeights:
    """Poids en valeur de marché, et de quoi les auditer.

    Les poids sont en VALEUR, pas en nombre de titres : 10 actions à 500 € pèsent
    dix fois plus que 10 actions à 50 €, et c'est la valeur qui détermine
    l'exposition au risque.
    """

    weights: dict[str, float]
    values: dict[str, float]
    prices: dict[str, float]
    total_value: float
    as_of: date

    @property
    def tickers(self) -> list[str]:
        return list(self.weights)


def load_positions(conn: sqlite3.Connection, portfolio_id: int) -> list[Position]:
    """Lignes d'un portefeuille. Lève `PortfolioError` s'il est vide."""
    lignes = conn.execute(
        """
        SELECT ticker, quantity, cost_basis
        FROM positions
        WHERE portfolio_id = ?
        ORDER BY ticker
        """,
        (portfolio_id,),
    ).fetchall()

    if not lignes:
        existe = conn.execute(
            "SELECT 1 FROM portfolios WHERE id = ?", (portfolio_id,)
        ).fetchone()
        raise PortfolioError(
            f"Portefeuille {portfolio_id} "
            + ("sans position." if existe else "introuvable.")
        )

    return [
        Position(r["ticker"], float(r["quantity"]), r["cost_basis"]) for r in lignes
    ]


def latest_closes(
    conn: sqlite3.Connection, tickers: list[str]
) -> dict[str, tuple[date, float]]:
    """Dernière clôture connue de chaque titre, avec sa date.

    Utilise `close` et non `adj_close`. Les deux coïncident sur la séance la
    plus récente, mais ils ne mesurent pas la même chose : `close` est un prix
    auquel on peut traiter, `adj_close` est un indice de performance totale dont
    le niveau historique est rebasé à chaque dividende. Valoriser un
    portefeuille avec un indice rebasé n'aurait pas de sens ; `adj_close` reste
    réservé aux rendements.
    """
    if not tickers:
        return {}

    marques = ",".join("?" * len(tickers))
    lignes = conn.execute(
        f"""
        SELECT p.ticker, p.date, p.close
        FROM prices p
        JOIN (
            SELECT ticker, MAX(date) AS derniere
            FROM prices
            WHERE ticker IN ({marques})
            GROUP BY ticker
        ) d ON d.ticker = p.ticker AND d.derniere = p.date
        """,
        tickers,
    ).fetchall()

    return {
        r["ticker"]: (date.fromisoformat(r["date"]), float(r["close"]))
        for r in lignes
    }


def market_value_weights(
    conn: sqlite3.Connection, portfolio_id: int
) -> PortfolioWeights:
    """Poids en valeur de marché, à la dernière clôture disponible."""
    positions = load_positions(conn, portfolio_id)
    tickers = [p.ticker for p in positions]
    closes = latest_closes(conn, tickers)

    sans_prix = [t for t in tickers if t not in closes]
    if sans_prix:
        raise PortfolioError(
            f"Aucun prix en base pour {sorted(sans_prix)}. "
            "Lancer : python -m backend.ingestion add <TICKER>"
        )

    valeurs = {p.ticker: p.quantity * closes[p.ticker][1] for p in positions}
    total = sum(valeurs.values())
    if total <= 0:
        raise PortfolioError(
            f"Valeur de marché totale nulle ou négative ({total:.2f}) : "
            "les poids ne sont pas définis."
        )

    return PortfolioWeights(
        weights={t: v / total for t, v in valeurs.items()},
        values=valeurs,
        prices={t: closes[t][1] for t in tickers},
        total_value=total,
        # La date la plus ancienne parmi les dernières clôtures : c'est jusque
        # là que la valorisation est vraie pour TOUTES les lignes. Annoncer la
        # plus récente laisserait croire que le portefeuille entier est
        # valorisé à cette date alors qu'une ligne y serait périmée.
        as_of=min(d for d, _ in closes.values()),
    )


def load_price_panel(
    conn: sqlite3.Connection,
    tickers: list[str],
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Panel des cours ajustés : une ligne par date, une colonne par titre.

    Le pivot se fait sur la colonne `date`, donc les séries sont appariées par
    date et jamais par position dans le tableau. Les dates incomplètes ressortent
    avec des NaN, que `returns.align_panel` retire ensuite explicitement.
    """
    if not tickers:
        raise PortfolioError("Aucun titre demandé.")

    marques = ",".join("?" * len(tickers))
    clauses, params = [f"ticker IN ({marques})"], list(tickers)
    if start is not None:
        clauses.append("date >= ?")
        params.append(start.isoformat())
    if end is not None:
        clauses.append("date <= ?")
        params.append(end.isoformat())

    lignes = conn.execute(
        f"SELECT date, ticker, adj_close FROM prices "
        f"WHERE {' AND '.join(clauses)} ORDER BY date",
        params,
    ).fetchall()

    if not lignes:
        raise PortfolioError(
            f"Aucun prix en base pour {sorted(tickers)} sur la période demandée."
        )

    brut = pd.DataFrame(
        [(r["date"], r["ticker"], r["adj_close"]) for r in lignes],
        columns=["date", "ticker", "adj_close"],
    )
    panel = brut.pivot(index="date", columns="ticker", values="adj_close")
    panel.index = pd.to_datetime(panel.index).date
    panel.index.name = "date"
    return panel.sort_index()
