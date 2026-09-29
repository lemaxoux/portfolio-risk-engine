"""Contrôle des positions soumises, avant toute écriture en base.

Le même contrôle sert au `PUT` en JSON et à l'import CSV : les deux écrivent les
mêmes lignes, ils doivent refuser les mêmes choses. Deux validations parallèles
finiraient par diverger, et la porte la plus laxiste deviendrait la porte
d'entrée.

DEUX PRINCIPES

**Tout est refusé d'un coup.** Les problèmes sont accumulés, jamais levés au
premier rencontré. Un fichier de douze lignes dont trois sont fautives produit
une réponse qui nomme les trois, pas trois allers-retours.

**Rien n'est écrit tant que tout n'est pas valide.** Aucun import partiel : un
portefeuille à moitié remplacé serait pire que pas remplacé du tout, puisque la
valorisation qui en sortirait serait plausible et fausse.

Ce module ne fait aucun calcul et ne touche pas la base : le catalogue des
titres lui est passé en argument.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from backend.db.portfolios import PositionRow
from backend.risk_engine.portfolio import Security

from .errors import Problem

MAX_POSITIONS = 200


@dataclass(frozen=True)
class SubmittedPosition:
    """Une ligne soumise, telle qu'elle a été reçue.

    `line` est le numéro de ligne tel que l'utilisateur le voit : dans le
    fichier CSV, tel qu'un tableur l'affiche, ou dans le tableau de saisie,
    quand le client le fournit avec une soumission JSON. Il vaut None sinon.
    """

    ticker: str
    quantity: float
    cost_basis: float | None = None
    line: int | None = None


def normalise_ticker(brut: str) -> str:
    """Espaces retirés, capitales forcées.

    Les tickers sont stockés en capitales. Refuser `aapl` au motif qu'il n'est
    pas `AAPL` serait un refus sur une convention d'écriture, pas sur une
    donnée manquante.
    """
    return brut.strip().upper()


def _connus(catalogue: Sequence[Security]) -> str:
    return ", ".join(s.ticker for s in catalogue)


def validate(
    submitted: Sequence[SubmittedPosition], catalogue: Sequence[Security]
) -> tuple[list[PositionRow], tuple[Problem, ...]]:
    """Positions prêtes à écrire, et la liste complète des refus.

    Quand la seconde n'est pas vide, la première ne doit pas être utilisée.
    """
    par_ticker = {s.ticker: s for s in catalogue}
    problemes: list[Problem] = []
    retenues: list[PositionRow] = []
    vues: dict[str, int | None] = {}

    if not submitted:
        return [], (
            Problem(
                problem=(
                    "Aucune position soumise. Un portefeuille sans ligne n'a pas "
                    "de risque à mesurer ; pour vider un portefeuille, le "
                    "supprimer."
                ),
            ),
        )

    if len(submitted) > MAX_POSITIONS:
        return [], (
            Problem(
                problem=(
                    f"{len(submitted)} positions soumises, maximum {MAX_POSITIONS}. "
                    "Cette limite protège la mémoire du processus ; elle n'a pas "
                    "de justification méthodologique."
                ),
            ),
        )

    for position in submitted:
        ticker = normalise_ticker(position.ticker)
        ligne = position.line

        if not ticker:
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=position.ticker,
                    problem="Ticker vide.",
                )
            )
            continue

        if ticker in vues:
            precedente = vues[ticker]
            ou = "" if precedente is None else f" (déjà ligne {precedente})"
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=ticker,
                    problem=(
                        f"{ticker} apparaît deux fois{ou}. Une ligne par titre : "
                        "additionner les quantités avant de soumettre."
                    ),
                )
            )
            continue
        vues[ticker] = ligne

        security = par_ticker.get(ticker)
        if security is None:
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=ticker,
                    problem=(
                        f"Ticker inconnu : {ticker}. Titres disponibles : "
                        f"{_connus(catalogue)}. Pour en ajouter un : "
                        f"python -m backend.ingestion add {ticker}"
                    ),
                )
            )
            continue

        if not security.has_prices:
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=ticker,
                    problem=(
                        f"{ticker} est connu mais n'a aucun historique de prix en "
                        "base : il ne peut être ni valorisé ni analysé. "
                        f"Le charger avec : python -m backend.ingestion add {ticker}"
                    ),
                )
            )
            continue

        if not math.isfinite(position.quantity):
            problemes.append(
                Problem(
                    line=ligne,
                    field="quantity",
                    value=str(position.quantity),
                    problem=f"Quantité non finie pour {ticker}.",
                )
            )
            continue

        if position.quantity <= 0.0:
            problemes.append(
                Problem(
                    line=ligne,
                    field="quantity",
                    value=str(position.quantity),
                    problem=(
                        f"Quantité nulle ou négative pour {ticker} "
                        f"({position.quantity}). Les poids sont calculés en valeur "
                        "de marché : une position vendue à découvert n'est pas "
                        "prise en charge en v1."
                    ),
                )
            )
            continue

        if position.cost_basis is not None:
            if not math.isfinite(position.cost_basis):
                problemes.append(
                    Problem(
                        line=ligne,
                        field="cost_basis",
                        value=str(position.cost_basis),
                        problem=f"Prix de revient non fini pour {ticker}.",
                    )
                )
                continue
            if position.cost_basis < 0.0:
                problemes.append(
                    Problem(
                        line=ligne,
                        field="cost_basis",
                        value=str(position.cost_basis),
                        problem=f"Prix de revient négatif pour {ticker}.",
                    )
                )
                continue

        retenues.append(
            PositionRow(
                ticker=ticker,
                quantity=position.quantity,
                cost_basis=position.cost_basis,
            )
        )

    if problemes:
        return [], tuple(problemes)
    return retenues, ()
