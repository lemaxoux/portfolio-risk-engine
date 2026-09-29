"""Portefeuilles : création, lecture valorisée, remplacement des positions,
import CSV, suppression.

TOUTE ÉCRITURE DE POSITIONS EST UN REMPLACEMENT COMPLET — `PUT` comme import
CSV. C'est la sémantique de l'écran de saisie : le tableau affiché à l'écran, ou
le fichier déposé, EST le portefeuille. Un import qui ajouterait aux lignes
existantes doublerait silencieusement les quantités à chaque dépôt du même
fichier, et la valorisation qui en sortirait serait plausible et fausse.

AUCUNE ÉCRITURE PARTIELLE — la validation est complète avant la première
écriture, et le remplacement tient dans une transaction. Un portefeuille à
moitié remplacé n'existe à aucun instant.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, UploadFile, status

from backend.db import portfolios as store
from backend.risk_engine.portfolio import (
    PortfolioError,
    load_securities,
    market_value_weights,
)

from ..csv_import import PROBE_BYTES, CsvError, read as read_csv
from ..dependencies import get_connection
from ..errors import ApiError, Problem, not_found, unprocessable
from ..schemas import (
    CsvImportOut,
    CsvSourceOut,
    PortfolioCreate,
    PortfolioDetailOut,
    PortfolioOut,
    PositionOut,
    PositionsReplace,
    PositionsWrittenOut,
    ValuationOut,
)
from ..validation import SubmittedPosition, validate

router = APIRouter(prefix="/portfolios", tags=["portefeuilles"])


def _detail(
    conn: sqlite3.Connection, row: store.PortfolioRow, strict: bool
) -> PortfolioDetailOut:
    """Portefeuille et sa valorisation, ou la raison pour laquelle elle manque.

    `strict` distingue les deux usages. Interrogé SEUL, un portefeuille non
    valorisable répond en 409 : c'est la ressource demandée qui est en cause, et
    rendre un objet à moitié vide obligerait le client à traiter un cas d'erreur
    déguisé en succès. Dans la LISTE, le même portefeuille ressort avec
    `valuation: null` et sa raison : un portefeuille cassé ne doit pas priver
    l'utilisateur des autres.

    Les positions stockées sont lues UNE fois et servent aux deux usages : la
    liste brute (`positions`), publiée même sans valorisation, et la
    valorisation elle-même. Deux lectures pourraient décrire deux états.
    """
    stockees = store.load_positions(conn, row.id)
    positions = [PositionOut.of(ligne) for ligne in stockees]
    try:
        poids = market_value_weights(conn, row.id)
    except PortfolioError as exc:
        if strict:
            raise ApiError(status.HTTP_409_CONFLICT, str(exc)) from exc
        return PortfolioDetailOut(
            id=row.id,
            name=row.name,
            owner=row.owner,
            updated_at=row.updated_at,
            positions=positions,
            valuation=None,
            valuation_error=str(exc),
        )

    return PortfolioDetailOut(
        id=row.id,
        name=row.name,
        owner=row.owner,
        updated_at=row.updated_at,
        positions=positions,
        valuation=ValuationOut.of(
            poids,
            stockees,
            {titre.ticker: titre.name for titre in load_securities(conn)},
        ),
        valuation_error=None,
    )


def _resume(problemes: tuple[Problem, ...]) -> str:
    """Phrase d'en-tête d'un refus.

    Un problème unique est repris tel quel : le résumer par « 1 position
    refusée » remplacerait une explication par un décompte, et obligerait le
    client à ouvrir `problems` pour lire ce qui tient en une ligne.
    """
    if len(problemes) == 1:
        return problemes[0].problem
    return f"{len(problemes)} lignes refusées : aucune position n'a été écrite."


def _require(conn: sqlite3.Connection, portfolio_id: int) -> store.PortfolioRow:
    """Le portefeuille, ou 404.

    L'existence est vérifiée par une lecture explicite, jamais en cherchant un
    mot dans le message d'une exception : un code HTTP qui dépendrait de la
    langue d'un message serait cassé par une reformulation.
    """
    row = store.get(conn, portfolio_id)
    if row is None:
        raise not_found(portfolio_id)
    return row


def _write(
    conn: sqlite3.Connection,
    portfolio_id: int,
    submitted: list[SubmittedPosition],
) -> store.PortfolioRow:
    """Valide puis remplace. Ne renvoie qu'une fois l'écriture faite."""
    retenues, problemes = validate(submitted, load_securities(conn))
    if problemes:
        raise unprocessable(_resume(problemes), problemes)

    try:
        store.replace_positions(conn, portfolio_id, retenues)
    except sqlite3.IntegrityError as exc:
        # Filet de sécurité : la validation couvre déjà les tickers inconnus.
        # Une contrainte violée ici signale un écart entre `securities` et ce que
        # la validation a lu, pas une erreur de l'utilisateur.
        raise ApiError(
            status.HTTP_409_CONFLICT,
            f"Écriture refusée par la base : {exc}",
        ) from exc

    row = store.get(conn, portfolio_id)
    assert row is not None
    return row


@router.post(
    "", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED
)
def create_portfolio(
    payload: PortfolioCreate | None = None,
    conn: sqlite3.Connection = Depends(get_connection),
) -> PortfolioOut:
    """Crée un portefeuille vide et renvoie son identifiant.

    `updated_at` reste nul : aucune position n'a encore été écrite, et dater la
    création annoncerait une fraîcheur de positions qui n'existe pas.
    """
    demande = payload or PortfolioCreate()
    return PortfolioOut.of(store.create(conn, demande.name, demande.owner))


@router.get("", response_model=list[PortfolioDetailOut])
def list_portfolios(
    conn: sqlite3.Connection = Depends(get_connection),
) -> list[PortfolioDetailOut]:
    return [_detail(conn, row, strict=False) for row in store.list_all(conn)]


@router.get("/{portfolio_id}", response_model=PortfolioDetailOut)
def read_portfolio(
    portfolio_id: int, conn: sqlite3.Connection = Depends(get_connection)
) -> PortfolioDetailOut:
    return _detail(conn, _require(conn, portfolio_id), strict=True)


@router.put("/{portfolio_id}/positions", response_model=PositionsWrittenOut)
def replace_positions(
    portfolio_id: int,
    payload: PositionsReplace,
    conn: sqlite3.Connection = Depends(get_connection),
) -> PositionsWrittenOut:
    """Remplace TOUTES les positions du portefeuille.

    `line`, quand le client le fournit, suit la position jusqu'à ses refus :
    c'est le numéro que l'utilisateur voit dans son tableau, comme celui d'une
    ligne de fichier pour l'import CSV. L'API ne l'interprète pas.
    """
    _require(conn, portfolio_id)
    soumises = [
        SubmittedPosition(
            ticker=position.ticker,
            quantity=position.quantity,
            cost_basis=position.cost_basis,
            line=position.line,
        )
        for position in payload.positions
    ]
    row = _write(conn, portfolio_id, soumises)
    assert row.updated_at is not None
    return PositionsWrittenOut(
        portfolio_id=portfolio_id,
        positions_count=len(payload.positions),
        updated_at=row.updated_at,
    )


@router.post("/{portfolio_id}/positions/csv", response_model=CsvImportOut)
def import_positions_csv(
    portfolio_id: int,
    file: UploadFile = File(
        description="Fichier CSV. En-tête attendu : ticker;quantity[;cost_basis]"
    ),
    conn: sqlite3.Connection = Depends(get_connection),
) -> CsvImportOut:
    """Importe un CSV de positions, y compris celui d'un Excel français.

    Le fichier est lu en OCTETS, jamais décodé implicitement : l'encodage, le
    séparateur de champs et le séparateur décimal sont déduits des octets, puis
    rendus dans la réponse. Voir `api.csv_import` pour le raisonnement.
    """
    _require(conn, portfolio_id)

    try:
        # Lecture BORNÉE : un octet de plus que la limite suffit à savoir que le
        # fichier la dépasse, et le reste n'est jamais chargé.
        lecture = read_csv(file.file.read(PROBE_BYTES), file.filename)
    except CsvError as exc:
        raise unprocessable(str(exc)) from exc

    if lecture.problems:
        raise unprocessable(_resume(lecture.problems), lecture.problems)

    row = _write(conn, portfolio_id, list(lecture.positions))
    assert row.updated_at is not None
    return CsvImportOut(
        portfolio_id=portfolio_id,
        positions_count=len(lecture.positions),
        updated_at=row.updated_at,
        source=CsvSourceOut(
            filename=lecture.source.filename,
            encoding=lecture.source.encoding,
            delimiter=lecture.source.delimiter,
            decimal_separator=lecture.source.decimal_separator,
            rows_read=lecture.source.rows_read,
        ),
    )


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_portfolio(
    portfolio_id: int, conn: sqlite3.Connection = Depends(get_connection)
) -> None:
    """Supprime le portefeuille et ses positions (cascade du schéma)."""
    _require(conn, portfolio_id)
    store.delete(conn, portfolio_id)
