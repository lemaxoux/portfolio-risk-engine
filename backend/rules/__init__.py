"""Moteur de règles (Phase 6).

Transforme les sorties du moteur de risque en observations chiffrées. Il décrit
des propriétés du portefeuille, il ne prescrit jamais d'action, il ne produit
aucun score global, et il ne recalcule rien.

* `thresholds` — les seuils et leur provenance (calculée, relative, ou choisie) ;
* `rules` — les six règles et l'évaluation d'un portefeuille ;
* `disclaimer` — le texte du bandeau d'acceptation.
"""

from __future__ import annotations

from .disclaimer import (
    ACCEPTANCE_CONFIRMATION,
    ACCEPTANCE_TEXT,
    ACCEPTANCE_TITLE,
    DisclaimerSection,
    acceptance_sections,
    acceptance_text,
)
from .rules import (
    Observation,
    RuleId,
    RulesReport,
    apparent_diversification,
    crisis_degradation,
    effective_concentration,
    evaluate,
    evaluate_portfolio,
    scenario_coverage,
    systematic_share,
    variance_contribution,
)
from .thresholds import (
    MIN_ESTIMABLE_OBSERVATIONS,
    MIN_REGRESSION_SAMPLE,
    MIN_SCENARIO_COVERAGE,
    STRONG_CORRELATION,
    Threshold,
    ThresholdKind,
)

__all__ = [
    "ACCEPTANCE_CONFIRMATION",
    "ACCEPTANCE_TEXT",
    "ACCEPTANCE_TITLE",
    "MIN_ESTIMABLE_OBSERVATIONS",
    "MIN_REGRESSION_SAMPLE",
    "MIN_SCENARIO_COVERAGE",
    "STRONG_CORRELATION",
    "DisclaimerSection",
    "Observation",
    "RuleId",
    "RulesReport",
    "Threshold",
    "ThresholdKind",
    "acceptance_sections",
    "acceptance_text",
    "apparent_diversification",
    "crisis_degradation",
    "effective_concentration",
    "evaluate",
    "evaluate_portfolio",
    "scenario_coverage",
    "systematic_share",
    "variance_contribution",
]
