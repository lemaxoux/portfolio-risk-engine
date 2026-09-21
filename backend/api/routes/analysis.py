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
constante —, le volet sort à `null` avec la raison du moteur, mot pour mot, et
le reste du rapport est servi. Le refus est relayé, pas reformulé.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query, status

from backend.db import portfolios as store
from backend.risk_engine.config import (
    DEFAULT_BENCHMARK,
    DEFAULT_WINDOW,
    MIN_REGRESSION_OBSERVATIONS,
)
from backend.risk_engine.engine import (
    RiskReport,
    analyse_portfolio,
    compare_all_regimes,
    run_all_scenarios,
)
from backend.risk_engine.portfolio import PortfolioError
from backend.rules.rules import evaluate

from ..dependencies import get_connection
from ..errors import ApiError, not_found, unprocessable
from ..schemas import (
    AnalysisOut,
    DisclaimerOut,
    ObservationOut,
    ParametersOut,
    PortfolioOut,
    RegimeOut,
    RiskOut,
    ScenarioOut,
    WeightOut,
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
) -> tuple[RiskReport, str | None]:
    """Rapport avec le volet Student, ou sans lui et avec la raison du refus.

    LE RÉESSAI EST LE DISCRIMINANT. `analyse_portfolio` lève `ValueError` pour
    deux familles de causes : l'ajustement de Student (ν ≤ 2, moins de 30
    séances, série constante) et les paramètres eux-mêmes (fenêtre trop courte).
    Rejouer sans Monte Carlo les sépare sans avoir à lire le message : si
    l'erreur persiste, elle ne venait pas du volet Student, et elle remonte à la
    route qui la traduira en 422.
    """
    arguments = {"window": window, "benchmark": benchmark}
    try:
        return (
            analyse_portfolio(conn, portfolio_id, monte_carlo=True, **arguments),
            None,
        )
    except ValueError as exc:
        return (
            analyse_portfolio(conn, portfolio_id, monte_carlo=False, **arguments),
            str(exc),
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
            "Indice de référence du beta. Chaîne vide pour désactiver le beta, "
            "lorsque l'indice n'est pas en base."
        ),
    ),
    conn: sqlite3.Connection = Depends(get_connection),
) -> AnalysisOut:
    """Rapport de risque, scénarios, régimes, observations et bandeau."""
    row = store.get(conn, portfolio_id)
    if row is None:
        raise not_found(portfolio_id)

    indice = benchmark or None

    try:
        report, student_reason = _analyse(conn, portfolio_id, window, indice)
        scenarios = run_all_scenarios(conn, portfolio_id)
        regimes = compare_all_regimes(conn, portfolio_id, window=window)
    except PortfolioError as exc:
        # Le portefeuille existe mais n'est pas analysable en l'état. Le message
        # du moteur dit quoi faire — « Lancer : python -m backend.ingestion add
        # SPY » — et il est relayé tel quel.
        raise ApiError(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValueError as exc:
        raise unprocessable(str(exc)) from exc

    rules_report = evaluate(report, scenarios, regimes)

    # Ordre canonique de toute la réponse : celui des colonnes de la matrice.
    # Les poids sont relus PAR CE MÊME ordre plutôt que publiés dans le leur, de
    # sorte qu'une carte de chaleur et une barre de poids ne puissent pas
    # s'étiqueter différemment.
    tickers = [str(colonne) for colonne in report.matrices.correlation.columns]

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
        parameters=ParametersOut(
            window=window,
            benchmark=indice,
            confidence_levels=list(CONFIDENCE_LEVELS),
        ),
        risk=RiskOut.of(report, tickers, student_reason),
        scenarios=[ScenarioOut.of(s) for s in scenarios],
        regimes=[RegimeOut.of(r) for r in regimes],
        observations=[ObservationOut.of(o) for o in rules_report.observations],
        disclaimer=DisclaimerOut.of(rules_report, report.window.requested),
    )
