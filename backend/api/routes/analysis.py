"""`GET /api/portfolios/{id}/analysis` — le rapport complet, en UNE réponse.

═══ POURQUOI UN SEUL ENDPOINT, PAS QUATRE ═══

Si la base est rafraîchie entre deux appels, une section « volatilité » et une
section « scénarios » obtenues séparément décriraient deux dates différentes
sans que rien ne le signale. Une seule réponse = un seul `as_of` pour toute la
page. Le coût mesuré est négligeable : analyse avec Monte Carlo 0,28 s,
scénarios 0,05 s, régimes 0,25 s sur six titres — moins d'une seconde pour la
page entière, ce qui ne justifie pas de découper.

═══ LE VOLET STUDENT ═══

Le moteur a `monte_carlo=False` par défaut ; cette route passe `True`.
Divergence VOLONTAIRE, écrite ici pour qu'elle ne ressemble pas à un oubli dans
six mois : la VaR normale et la VaR Student se lisent en couple, l'écart entre
les deux chiffrant le coût de l'hypothèse de normalité. Publier la normale seule
la ferait passer pour le dernier mot.

Quand le moteur refuse d'ajuster une Student — ν ≤ 2, série trop courte, série
constante, ou ν au-delà de 30, où elle ne se distingue plus de la normale —,
le volet sort à `null` avec la raison du moteur, mot pour mot, et
le reste du rapport est servi, Monte Carlo normal compris : il ne dépend pas
de ν. Le moteur rédige la raison et la range dans le rapport
(`RiskReport.student_unavailable_reason`) ; la route la publie, elle ne la
reformule pas. Le Monte Carlo normal porte la sienne, de la même façon.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace

from fastapi import APIRouter, Depends, Query, status

from backend.db import portfolios as store
from backend.langue import Langue
from backend.risk_engine.config import (
    DEFAULT_BENCHMARK,
    DEFAULT_WINDOW,
    MIN_REGRESSION_OBSERVATIONS,
)
from backend.risk_engine.engine import (
    RiskReport,
    analyse_portfolio,
    benchmark_name,
    compare_all_regimes,
    run_all_scenarios,
)
from backend.risk_engine.portfolio import PortfolioError, load_securities
from backend.rules.rules import evaluate

from ..dependencies import get_connection
from ..errors import ApiError, not_found, unprocessable
from ..langue import langue_demandee
from ..validation import normalise_ticker
from ..schemas import (
    AnalysisOut,
    DisclaimerOut,
    LimitingPositionOut,
    ObservationOut,
    ParametersOut,
    PortfolioOut,
    PortfolioSeriesOut,
    RegimeOut,
    ReturnHistogramOut,
    RiskOut,
    ScenarioOut,
    ValuationOut,
    WeightOut,
    WindowOut,
)

router = APIRouter(prefix="/portfolios", tags=["analyse"])

# Niveaux publiés. Le défaut du moteur, repris explicitement pour que la réponse
# puisse les annoncer dans `parameters` sans les deviner.
CONFIDENCE_LEVELS: tuple[float, ...] = (0.95, 0.99)


def _analyse(
    conn: sqlite3.Connection,
    portfolio_id: int,
    window: int,
    benchmark: str | None,
) -> RiskReport:
    """Rapport avec ses simulations, chacune présente ou accompagnée de sa raison.

    Le moteur absorbe lui-même les refus qu'il connaît — volet Student,
    Monte Carlo normal sur une covariance singulière — et range leurs raisons
    dans le rapport. Rien à faire ici dans ce cas : le rapport est servi tel
    quel.

    LE RÉESSAI RESTE UN FILET, pour une `ValueError` que le moteur n'aurait
    pas prévue dans ses simulations. Rejouer sans Monte Carlo la sépare d'une
    erreur de paramètres (fenêtre trop courte) sans avoir à lire le message :
    si elle disparaît, elle venait des simulations, et les deux volets sortent
    à `null` avec ce message pour raison — jamais un blanc sans raison. Si
    elle persiste, elle remonte à la route qui la traduira en 422.
    """
    arguments = {"window": window, "benchmark": benchmark}
    try:
        return analyse_portfolio(conn, portfolio_id, monte_carlo=True, **arguments)
    except ValueError as exc:
        return replace(
            analyse_portfolio(conn, portfolio_id, monte_carlo=False, **arguments),
            monte_carlo_unavailable_reason=str(exc),
            student_unavailable_reason=str(exc),
        )


@router.get("/{portfolio_id}/analysis", response_model=AnalysisOut)
def analyse(
    portfolio_id: int,
    window: int = Query(
        DEFAULT_WINDOW,
        # Le plancher vient du moteur (`MIN_REGRESSION_OBSERVATIONS`), pas d'un
        # littéral : deux séances suffisaient à obtenir un rapport en 200 où le
        # R² valait 1 et toutes les corrélations ±1, par construction.
        #
        # Ce n'est PAS ce plancher qui protège. La fenêtre effective est celle
        # de l'intersection des dates : une ligne cotée depuis peu fait tomber
        # une demande de 504 séances à quelques dizaines d'observations sans
        # qu'aucun paramètre ait changé. Le contrôle qui compte porte sur
        # `window.observations`, dans le moteur de règles. Celui-ci évite
        # seulement qu'un rapport à moitié dégénéré soit demandé exprès.
        ge=MIN_REGRESSION_OBSERVATIONS,
        le=10_000,
        description=(
            "Fenêtre d'estimation demandée, en séances. Le nombre réellement "
            "obtenu se lit sur `window.observations` de chaque mesure, et peut "
            "être bien inférieur si une ligne a un historique court."
        ),
    ),
    benchmark: str | None = Query(
        DEFAULT_BENCHMARK,
        description=(
            "Indice de référence du beta, insensible à la casse. Chaîne vide "
            "pour désactiver le beta, lorsque l'indice n'est pas en base."
        ),
    ),
    conn: sqlite3.Connection = Depends(get_connection),
    langue: Langue = Depends(langue_demandee),
) -> AnalysisOut:
    """Rapport de risque, scénarios, régimes, observations et bandeau."""
    row = store.get(conn, portfolio_id)
    if row is None:
        raise not_found(portfolio_id)

    # Même normalisation que pour les tickers des positions. Sans elle,
    # `?benchmark=spy` répondait 409 « aucun prix en base pour ['spy'] » alors
    # que `spy` dans un CSV s'importe sans broncher : deux portes d'entrée de la
    # même API, deux exigences différentes sur la même donnée.
    indice = normalise_ticker(benchmark) if benchmark else None

    try:
        report = _analyse(conn, portfolio_id, window, indice)
        scenarios = run_all_scenarios(conn, portfolio_id)
        regimes = compare_all_regimes(conn, portfolio_id, window=window)
    except PortfolioError as exc:
        # Le portefeuille existe mais n'est pas analysable en l'état. Le message
        # du moteur dit quoi faire — « Lancer : python -m backend.ingestion add
        # SPY » — et il est relayé tel quel.
        raise ApiError(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise unprocessable(str(exc)) from exc

    rules_report = evaluate(report, scenarios, regimes, langue=langue)

    # Ordre canonique de toute la réponse : celui des colonnes de la matrice de
    # COVARIANCE. Les poids sont relus par ce même ordre plutôt que publiés dans
    # le leur, de sorte qu'une carte de chaleur et une barre de poids ne puissent
    # pas s'étiqueter différemment.
    #
    # La covariance et non la corrélation : les deux sortent du même panel, donc
    # du même ordre, mais la corrélation vaut None sous
    # MIN_ESTIMABLE_OBSERVATIONS. Faire dépendre l'étiquetage de toute la
    # réponse d'une matrice qui peut manquer priverait le client de son ordre
    # de référence précisément quand il en a le plus besoin.
    tickers = [str(colonne) for colonne in report.matrices.covariance.columns]
    nom_indice = benchmark_name(indice)

    return AnalysisOut(
        portfolio_id=portfolio_id,
        portfolio=PortfolioOut.of(row),
        as_of=report.as_of,
        total_value=report.total_value,
        tickers=tickers,
        weights=[
            WeightOut(ticker=ticker, weight=report.weights[ticker])
            for ticker in tickers
        ],
        valuation=ValuationOut.of(
            report.valuation,
            store.load_positions(conn, portfolio_id),
            {titre.ticker: titre.name for titre in load_securities(conn)},
            order=tickers,
        ),
        # La fenêtre du PANEL, telle que le moteur la porte — pas celle d'une
        # mesure promue en fenêtre du document. `report.window` est
        # littéralement `PortfolioSeries.window` : la relire sur la volatilité
        # donnerait aujourd'hui le même nombre et inventerait une convention
        # que rien ne garantirait demain.
        estimation_window=WindowOut.of(report.window),
        estimation_period_label=report.window.period_label,
        limiting_positions=[
            LimitingPositionOut.of(position)
            for position in report.limiting_positions
        ],
        parameters=ParametersOut(
            window=window,
            benchmark=indice,
            confidence_levels=list(CONFIDENCE_LEVELS),
            benchmark_label=None if nom_indice is None else nom_indice.label,
            benchmark_description=None if nom_indice is None else nom_indice.description,
        ),
        risk=RiskOut.of(report, tickers),
        series=PortfolioSeriesOut.of(report),
        histogram=ReturnHistogramOut.of(report),
        scenarios=[ScenarioOut.of(s) for s in scenarios],
        regimes=[RegimeOut.of(r) for r in regimes],
        observations=[ObservationOut.of(o) for o in rules_report.observations],
        disclaimer=DisclaimerOut.of(rules_report, report.window.requested, langue),
    )
