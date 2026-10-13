"""Les trois routes du serveur public, et aucune autre.

    GET  /health     le réveil : le serveur répond, et dit ce qu'il sert
    POST /analysis   l'analyse d'une composition
    POST /csv        la lecture d'un fichier CSV, sans analyse

═══ NI FENÊTRE, NI INDICE EN PARAMÈTRE ═══

La route de l'application accepte `window` et `benchmark`. Celle-ci n'accepte
que `lang`. Ce n'est pas une simplification : deux analyses de la même
composition sur n et n + 1 séances ne diffèrent que d'une observation, et
leur différence redonne le rendement de la séance ajoutée. En balayant n, on
reconstruirait la série d'une composition d'une ligne, donc celle d'un titre.
La fenêtre et l'indice sont ceux de la configuration du moteur, fixes, sur
une base figée : une composition a une analyse, et une seule.

═══ LA COMPOSITION VOYAGE DANS LE CORPS ═══

`POST`, et non `GET` avec la composition dans l'adresse : une adresse entre
dans des journaux de requêtes, un corps n'entre dans aucun journal de ce
serveur. Rien n'est écrit, nulle part : la composition est posée dans des
tables temporaires le temps du calcul (`db/lecture_seule.py`).

═══ LES REFUS ═══

Le corps d'un refus est celui de l'application : `detail`, puis `problems`,
chacun avec sa ligne. Les décisions sont les siennes aussi
(`api.validation.validate`, `api.csv_import.read`) ; les phrases sont celles
du serveur public (`textes/<langue>/public.py`), qui ne portent aucune
commande.

Le moteur, lui, n'est jamais cité : quand il refuse une composition, sa
phrase dit quoi lancer sur un poste. Le serveur public la remplace par la
sienne. Sur sa base, où chaque titre a tout l'historique (`base.py`), aucune
composition valide ne devrait y mener ; le texte existe quand même.

Aucun calcul ici, aucun SQL : `tests/test_serveur_public.py` applique à ce
module les détecteurs de `tests/test_api_discipline.py`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from types import ModuleType

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from backend.api.csv_import import CsvError, read as read_csv
from backend.api.errors import ApiError, Problem, unprocessable
from backend.api.langue import langue_de_la_requete, langue_demandee
from backend.api.schemas import (
    CsvSourceOut,
    DisclaimerOut,
    LimitingPositionOut,
    ObservationOut,
    ParametersOut,
    PositionOut,
    RegimeOut,
    ReturnHistogramOut,
    RiskOut,
    ScenarioOut,
    ValuationOut,
    WeightOut,
    WindowOut,
)
from backend.api.validation import SubmittedPosition, validate
from backend.db.lecture_seule import ouvrir, poser_la_composition
from backend.db.portfolios import PositionRow
from backend.langue import Langue
from backend.risk_engine.config import DEFAULT_BENCHMARK, DEFAULT_WINDOW
from backend.risk_engine.engine import (
    RiskReport,
    analyse_portfolio,
    benchmark_name,
    compare_all_regimes,
    run_all_scenarios,
)
from backend.risk_engine.portfolio import PortfolioError
from backend.rules.rules import evaluate
from backend.textes import ErreurRedigee, texte_d_erreur, textes

from .base import Base
from .limites import (
    OCTETS_DU_FICHIER_CSV,
    SONDE_DU_FICHIER_CSV,
    ServeurOccupe,
    adresse_du_client,
)
from .schemas import HealthOut, PublicAnalysisIn, PublicAnalysisOut, PublicCsvOut

router = APIRouter()

# Niveaux publiés : ceux de la route de l'application.
CONFIDENCE_LEVELS: tuple[float, ...] = (0.95, 0.99)


def limite_par_adresse(request: Request) -> None:
    """Compte la requête pour son adresse, et la refuse au-delà de la limite.

    Posée sur les deux routes qui coûtent, pas sur `/health`, que le client
    sonde pendant le réveil et qui ne calcule rien.
    """
    compteur = request.app.state.compteur
    pair = request.client.host if request.client else None
    adresse = adresse_du_client(request.headers.get("x-forwarded-for"), pair)
    if not compteur.admet(adresse):
        t = textes(langue_de_la_requete(request)).public
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            t.limite_atteinte(compteur.maximum, compteur.periode_en_minutes),
        )


def _resume(problemes: tuple[Problem, ...], en_tete: Callable[[int], str]) -> str:
    """La phrase d'en-tête d'un refus : un problème unique est repris tel
    quel, comme dans l'application."""
    if len(problemes) == 1:
        return problemes[0].problem
    return en_tete(len(problemes))


def _retenir(
    soumises: list[SubmittedPosition],
    base: Base,
    langue: Langue,
    t: ModuleType,
    en_tete: Callable[[int], str],
) -> list[PositionRow]:
    """Les lignes prêtes à analyser, ou un refus qui les nomme toutes.

    La borne du nombre de lignes est le nombre de titres de la base : DÉRIVÉE,
    pas choisie. Un titre ne figure qu'une fois dans un portefeuille, donc
    aucun portefeuille valide n'en a davantage.
    """
    if len(soumises) > len(base.catalogue):
        raise unprocessable(t.trop_de_positions(len(soumises), len(base.catalogue)))
    retenues, problemes = validate(soumises, base.catalogue, langue=langue, redaction=t)
    if problemes:
        raise unprocessable(_resume(problemes, en_tete), problemes)
    return retenues


def _rediger(erreur: ErreurRedigee, t: ModuleType) -> str:
    """Le texte d'un fichier illisible, lu dans le module public : l'erreur
    garde le nom de son texte et ses arguments."""
    source = getattr(t, erreur.redaction)
    return source(*erreur.arguments) if callable(source) else source


@contextmanager
def _composition(base: Base, positions: list[PositionRow]) -> Iterator[tuple[sqlite3.Connection, int]]:
    """Une connexion en lecture seule où la composition est posée, fermée
    dans tous les cas : il n'en reste rien après la requête."""
    conn = ouvrir(base.chemin)
    try:
        yield conn, poser_la_composition(conn, positions)
    finally:
        conn.close()


def _rapport(conn: sqlite3.Connection, numero: int, langue: Langue) -> RiskReport:
    """Le rapport avec ses simulations, comme la route de l'application : le
    même filet, pour une `ValueError` que le moteur n'aurait pas prévue dans
    ses simulations (voir `api/routes/analysis.py`)."""
    arguments = {"window": DEFAULT_WINDOW, "benchmark": DEFAULT_BENCHMARK, "langue": langue}
    try:
        return analyse_portfolio(conn, numero, monte_carlo=True, **arguments)
    except ValueError as exc:
        return replace(
            analyse_portfolio(conn, numero, monte_carlo=False, **arguments),
            monte_carlo_unavailable_reason=texte_d_erreur(exc, langue),
            student_unavailable_reason=texte_d_erreur(exc, langue),
        )


@router.get("/health", response_model=HealthOut)
async def sante(request: Request) -> HealthOut:
    """Le serveur répond, et dit ce qu'il sert.

    Aucun paramètre, aucun corps lu, aucune lecture de la base : les quatre
    valeurs ont été établies au démarrage (`base.py`).
    """
    base: Base = request.app.state.base
    return HealthOut(
        status="ready",
        freeze_date=base.date_gel,
        database_sha256=base.sha256,
        code_sha256=base.code_sha256,
    )


@router.post(
    "/analysis", response_model=PublicAnalysisOut, dependencies=[Depends(limite_par_adresse)]
)
def analyser(
    payload: PublicAnalysisIn,
    request: Request,
    langue: Langue = Depends(langue_demandee),
) -> PublicAnalysisOut:
    """L'analyse d'une composition : rapport de risque, scénarios, régimes,
    observations et bandeau, sans identifiant ni série."""
    base: Base = request.app.state.base
    t = textes(langue).public
    soumises = [
        SubmittedPosition(
            ticker=position.ticker,
            quantity=position.quantity,
            cost_basis=position.cost_basis,
            line=position.line,
        )
        for position in payload.positions
    ]
    retenues = _retenir(soumises, base, langue, t, t.lignes_refusees)

    try:
        with request.app.state.file.tour(), _composition(base, retenues) as (conn, numero):
            report = _rapport(conn, numero, langue)
            scenarios = run_all_scenarios(conn, numero, langue=langue)
            regimes = compare_all_regimes(conn, numero, window=DEFAULT_WINDOW, langue=langue)
    except ServeurOccupe as exc:
        raise ApiError(status.HTTP_503_SERVICE_UNAVAILABLE, t.SERVEUR_OCCUPE) from exc
    except PortfolioError as exc:
        # La phrase du moteur dirait quoi lancer sur un poste : le serveur
        # public a la sienne.
        raise ApiError(status.HTTP_409_CONFLICT, t.ANALYSE_IMPOSSIBLE) from exc
    except ValueError as exc:
        raise unprocessable(t.ANALYSE_IMPOSSIBLE) from exc

    rules_report = evaluate(report, scenarios, regimes, langue=langue)

    # L'ordre canonique de la réponse : celui de la matrice de covariance,
    # comme dans la route de l'application.
    tickers = [str(colonne) for colonne in report.matrices.covariance.columns]
    nom_indice = benchmark_name(DEFAULT_BENCHMARK, langue)

    return PublicAnalysisOut(
        as_of=report.as_of,
        total_value=report.total_value,
        tickers=tickers,
        weights=[
            WeightOut(ticker=ticker, weight=report.weights[ticker]) for ticker in tickers
        ],
        valuation=ValuationOut.of(report.valuation, retenues, base.noms, order=tickers),
        estimation_window=WindowOut.of(report.window),
        estimation_period_label=report.window.periode(langue),
        limiting_positions=[
            LimitingPositionOut.of(position) for position in report.limiting_positions
        ],
        parameters=ParametersOut(
            window=DEFAULT_WINDOW,
            benchmark=DEFAULT_BENCHMARK,
            confidence_levels=list(CONFIDENCE_LEVELS),
            benchmark_label=None if nom_indice is None else nom_indice.label,
            benchmark_description=None if nom_indice is None else nom_indice.description,
        ),
        risk=RiskOut.of(report, tickers, langue),
        histogram=ReturnHistogramOut.of(report),
        scenarios=[ScenarioOut.of(s, langue) for s in scenarios],
        regimes=[RegimeOut.of(r, langue) for r in regimes],
        observations=[ObservationOut.of(o) for o in rules_report.observations],
        disclaimer=DisclaimerOut.of(rules_report, report.window.requested, langue),
    )


@router.post("/csv", response_model=PublicCsvOut, dependencies=[Depends(limite_par_adresse)])
def lire_un_fichier(
    request: Request,
    file: UploadFile = File(
        description="Fichier CSV. En-tête attendu : ticker;quantity[;cost_basis]"
    ),
    langue: Langue = Depends(langue_demandee),
) -> PublicCsvOut:
    """Lit un fichier CSV de positions et rend ses lignes, sans rien écrire.

    Le lecteur est celui de l'application : encodage, séparateur et décimale
    sont déduits des octets, puis rendus dans la réponse. Les lignes sont
    validées contre le catalogue, comme une saisie ; un titre hors base est
    refusé à sa ligne.
    """
    base: Base = request.app.state.base
    t = textes(langue).public

    # Lecture BORNÉE : un octet de plus que la limite suffit à savoir que le
    # fichier la dépasse.
    contenu = file.file.read(SONDE_DU_FICHIER_CSV)
    if len(contenu) > OCTETS_DU_FICHIER_CSV:
        raise unprocessable(t.fichier_trop_volumineux(OCTETS_DU_FICHIER_CSV))
    try:
        lecture = read_csv(contenu, file.filename, langue=langue, redaction=t)
    except CsvError as exc:
        raise unprocessable(_rediger(exc, t)) from exc
    if lecture.problems:
        raise unprocessable(
            _resume(lecture.problems, t.lignes_du_fichier_refusees), lecture.problems
        )

    retenues = _retenir(list(lecture.positions), base, langue, t, t.lignes_du_fichier_refusees)
    return PublicCsvOut(
        positions=[PositionOut.of(ligne) for ligne in retenues],
        source=CsvSourceOut(
            filename=lecture.source.filename,
            encoding=lecture.source.encoding,
            delimiter=lecture.source.delimiter,
            decimal_separator=lecture.source.decimal_separator,
            rows_read=lecture.source.rows_read,
        ),
    )
