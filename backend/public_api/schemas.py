"""Les schémas du serveur public : ce qu'il reçoit, ce qu'il rend.

═══ LA RÉPONSE D'ANALYSE A SON PROPRE SCHÉMA ═══

`PublicAnalysisOut` porte les champs d'`AnalysisOut`, la réponse de
l'application, MOINS TROIS :

* `portfolio_id` et `portfolio` : le serveur public ne stocke aucun
  portefeuille. Il n'y a ni numéro ni nom à rendre, et le nom que le visiteur
  donne à son portefeuille ne lui est jamais envoyé ;
* `series` : aucune série d'un titre en ligne, ni rien qui permette d'en
  reconstruire une. Une composition d'une seule ligne a pour série celle de
  son titre ; deux compositions des mêmes titres à des poids différents
  redonnent les deux séries. La réponse publique ne porte donc aucune liste
  de points datés, quelle que soit la composition.

Chaque champ est écrit ici, un par un, plutôt que retiré d'`AnalysisOut` par
une exclusion : un champ ajouté demain à la réponse de l'application n'entre
pas dans celle du serveur public sans qu'on l'y écrive.
`tests/test_serveur_public.py` tient les deux listes égales aux trois champs
près, et refuse toute liste de points datés dans le modèle comme dans les
réponses.

Les sous-objets (`RiskOut`, `ScenarioOut`, `ValuationOut`…) sont ceux de
l'application, importés tels quels : la même mesure se publie de la même
façon des deux côtés.

Aucun calcul ici, comme dans `api/schemas.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from backend.api.schemas import (
    CsvSourceOut,
    DisclaimerOut,
    LimitingPositionOut,
    ObservationOut,
    ParametersOut,
    PositionIn,
    PositionOut,
    RegimeOut,
    ReturnHistogramOut,
    RiskOut,
    ScenarioOut,
    Schema,
    Texte,
    ValuationOut,
    WeightOut,
    WindowOut,
)

# Les champs d'`AnalysisOut` que la réponse publique ne porte pas. Le test les
# lit ici : la liste et sa raison sont au même endroit.
CHAMPS_RETIRES = ("portfolio_id", "portfolio", "series")


class HealthOut(Schema):
    """Ce que rend `GET /health` : que le serveur répond, et ce qu'il sert.

    Les quatre valeurs sont établies une fois, au démarrage. `freeze_date` est
    la dernière séance de la base. Les deux empreintes se comparent à celles
    que l'on calcule de son côté : `database_sha256` à celle que l'outil a
    écrite en bâtissant la base, `code_sha256` à celle du commit public servi.
    """

    status: Literal["ready"]
    freeze_date: date
    database_sha256: str
    code_sha256: str


class PublicAnalysisIn(Schema):
    """Une composition à analyser : les lignes du tableau de saisie.

    `PositionIn` est celui de l'application, numéro de ligne compris : un refus
    le renvoie dans `problems[].line`.
    """

    positions: list[PositionIn]


class PublicAnalysisOut(Schema):
    """L'analyse d'une composition : UNE réponse, UN `as_of`, aucune série.

    Voir l'en-tête du module pour les trois champs que cette réponse n'a pas.
    """

    as_of: date
    total_value: float
    tickers: list[str]
    weights: list[WeightOut]
    valuation: ValuationOut
    estimation_window: WindowOut
    estimation_period_label: Texte
    limiting_positions: list[LimitingPositionOut]
    parameters: ParametersOut
    risk: RiskOut
    histogram: ReturnHistogramOut
    scenarios: list[ScenarioOut]
    regimes: list[RegimeOut]
    observations: list[ObservationOut]
    disclaimer: DisclaimerOut


class PublicCsvOut(Schema):
    """Un fichier CSV lu : ses lignes, validées, et comment il a été lu.

    Rien n'est écrit nulle part : le client garde ces lignes dans le
    navigateur. `source` est la provenance de l'import de l'application.
    """

    positions: list[PositionOut]
    source: CsvSourceOut
