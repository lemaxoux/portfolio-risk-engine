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
titres lui est passé en argument. Il décide des refus ; leurs phrases sont
rédigées dans la langue demandée par `textes/{fr,en}/api.py` (chantier 7D).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from types import ModuleType

from backend.db.portfolios import PositionRow
from backend.langue import Langue
from backend.risk_engine.portfolio import Security
from backend.textes import textes

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
    submitted: Sequence[SubmittedPosition],
    catalogue: Sequence[Security],
    *,
    langue: Langue = "fr",
    redaction: ModuleType | None = None,
) -> tuple[list[PositionRow], tuple[Problem, ...]]:
    """Positions prêtes à écrire, et la liste complète des refus, rédigés dans
    `langue`.

    Quand la seconde n'est pas vide, la première ne doit pas être utilisée.

    `redaction` est le module de textes qui rédige les refus : celui de l'API
    (`textes/<langue>/api.py`) par défaut. Le serveur public passe le sien
    (`public.py`, chantier 9.6), mêmes noms et mêmes signatures : les
    décisions restent ici, une seule fois.
    """
    t = textes(langue).api if redaction is None else redaction
    par_ticker = {s.ticker: s for s in catalogue}
    problemes: list[Problem] = []
    retenues: list[PositionRow] = []
    vues: dict[str, int | None] = {}

    if not submitted:
        return [], (Problem(problem=t.AUCUNE_POSITION),)

    if len(submitted) > MAX_POSITIONS:
        return [], (Problem(problem=t.trop_de_positions(len(submitted), MAX_POSITIONS)),)

    for position in submitted:
        ticker = normalise_ticker(position.ticker)
        ligne = position.line

        if not ticker:
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=position.ticker,
                    problem=t.TICKER_VIDE,
                )
            )
            continue

        if ticker in vues:
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=ticker,
                    problem=t.doublon(ticker, vues[ticker]),
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
                    problem=t.titre_inconnu(ticker, _connus(catalogue)),
                )
            )
            continue

        if not security.has_prices:
            problemes.append(
                Problem(
                    line=ligne,
                    field="ticker",
                    value=ticker,
                    problem=t.titre_sans_prix(ticker),
                )
            )
            continue

        if not math.isfinite(position.quantity):
            problemes.append(
                Problem(
                    line=ligne,
                    field="quantity",
                    value=str(position.quantity),
                    problem=t.quantite_non_finie(ticker),
                )
            )
            continue

        if position.quantity <= 0.0:
            problemes.append(
                Problem(
                    line=ligne,
                    field="quantity",
                    value=str(position.quantity),
                    problem=t.quantite_non_positive(ticker, position.quantity),
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
                        problem=t.prix_de_revient_non_fini(ticker),
                    )
                )
                continue
            if position.cost_basis < 0.0:
                problemes.append(
                    Problem(
                        line=ligne,
                        field="cost_basis",
                        value=str(position.cost_basis),
                        problem=t.prix_de_revient_negatif(ticker),
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
