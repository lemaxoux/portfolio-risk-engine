"""Les seuils du moteur de règles, en anglais américain (chantier 7D).

Les mêmes noms et les mêmes signatures que `fr/seuils.py`. Le français d'un
seuil est écrit une seule fois, dans `rules/thresholds.py` ; l'anglais est
rédigé ici à partir de sa clé (`Threshold.key`, le nom de la déclaration qui
le pose) et de ses paramètres (`Threshold.params` : le ticker d'une part de
capital, la paire, le niveau d'une VaR). Termes du glossaire validé :
« chosen by hand (not derived from the data) », « proven (the same for every
portfolio) », « calculated from this portfolio » ; l'anglais n'accorde pas.

Les nombres d'une justification sont ceux du français, écrits à l'anglaise ;
`tests/test_textes_symetriques.py` compare les nombres de chaque ligne de
seuil dans les deux langues. Les lettres grecques d'un nom ou d'une
justification (« ν », « α ») sont celles du français, et seulement celles-là.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from backend import typography

if TYPE_CHECKING:
    from backend.rules.thresholds import Threshold


def _pourcentage(valeur: float, decimales: int) -> str:
    return typography.percent(valeur, decimales, langue="en")


def _seances(nombre: int) -> str:
    return typography.sessions(nombre, langue="en")


def nom(seuil: Threshold) -> str:
    match seuil.key:
        case "STRONG_CORRELATION":
            return "strong correlation"
        case "MIN_SCENARIO_COVERAGE":
            return "minimum coverage of a scenario"
        case "MIN_REGRESSION_SAMPLE":
            return "minimum sessions for a regression"
        case "STUDENT_NU_CEILING":
            return "maximum ν of a Student's t-distribution"
        case "MIN_DISTRIBUTION_SAMPLE":
            return "minimum sessions to estimate a distribution"
        case "MIN_ESTIMABLE_SAMPLE":
            return "minimum estimable sessions"
        case "historical_var_sample":
            (confiance,) = seuil.params
            return f"minimum sessions for a historical VaR at {_pourcentage(confiance, 0)}"
        case "capital_share":
            (ticker,) = seuil.params
            return f"{ticker}'s share of the value"
        case "most_correlated_pair":
            premier, second = seuil.params
            return f"{premier}–{second} correlation"
    raise KeyError(seuil.key)


def justification(seuil: Threshold) -> str:
    match seuil.key:
        case "STRONG_CORRELATION":
            return (
                "usual convention for calling a correlation strong; no "
                "calculation on the portfolio produces it"
            )
        case "MIN_SCENARIO_COVERAGE":
            return (
                f"below {_pourcentage(seuil.value, 0)} of the value, the replayed "
                "part no longer represents the whole well enough to draw a figure "
                f"from it; at {_pourcentage(seuil.value, 0)}, even if the excluded "
                "part had lost twice as much as the covered part, the loss of the "
                "whole would exceed the displayed figure by only a fifth, compared "
                f"with a half at {_pourcentage(0.50, 0)}"
            )
        case "MIN_REGRESSION_SAMPLE":
            return (
                "about three months; below that, a few extreme days dictate the "
                "slope on their own"
            )
        case "STUDENT_NU_CEILING":
            return (
                "above it, Student's t-distribution cannot be distinguished from "
                "the normal distribution: at equal variance, its VaR departs from "
                f"it by at most {_pourcentage(0.0205, 2)} at {_pourcentage(0.99, 0)} "
                f"and by at most {_pourcentage(0.0031, 2)} at "
                f"{_pourcentage(0.95, 0)}, far less than the standard error of a "
                "sample standard deviation, about 1/√(2n) under normality "
                f"({_pourcentage(0.09, 0)} over {_seances(60)}, "
                f"{_pourcentage(0.032, 1)} over {_seances(504)}) and more with "
                "fat tails"
            )
        case "MIN_DISTRIBUTION_SAMPLE":
            return (
                "usual “large sample” convention, which no calculation on the "
                "portfolio produces; under normality, the sample standard "
                "deviation behind the volatility and the parametric VaR varies by "
                "about 1/√(2n) from one window to the next "
                f"({_pourcentage(0.13, 0)} over {_seances(30)}, "
                f"{_pourcentage(0.27, 0)} over {_seances(7)}), and fitting a "
                "Student's t-distribution rests on one or two sessions in the tail"
            )
        case "MIN_ESTIMABLE_SAMPLE":
            return (
                "with two observations, centering leaves only one direction: "
                "correlation, beta, and contributions to variance are all "
                "computed from a single daily difference and carry no information "
                "it does not already carry. They are no longer noisy statistics "
                "but arithmetic identities"
            )
        case "historical_var_sample":
            return (
                "the tail beyond the quantile counts n·(1 \u2212 α) sessions; "
                "below one, none falls into it, and the figure would be only the "
                "worst return of the window, not a quantile. The CVaR, which "
                "averages this tail, would come down to the same minimum"
            )
        case "capital_share":
            return (
                "above it, the holding weighs more in the risk than in the "
                "capital; below it, less"
            )
        case "most_correlated_pair":
            return "correlation of the most correlated pair in the portfolio"
    raise KeyError(seuil.key)


_ETIQUETTES = {"THRESHOLD": "Threshold", "REFERENCE": "Reference"}


def etiquette(role: Enum) -> str:
    """« Threshold » ou « Reference », par le nom du membre de `ThresholdRole`."""
    return _ETIQUETTES[role.name]


CHOISI = "chosen by hand (not derived from the data)"


def origine(choisi: bool, reference: bool, feminin: bool) -> str:
    if choisi:
        return CHOISI
    if reference:
        return "calculated from this portfolio"
    return "proven (the same for every portfolio)"


def ligne(intitule: str, valeur: str, provenance: str, raison: str) -> str:
    return f"{intitule} = {valeur}, {provenance}. {_phrase(raison)}"


def _phrase(texte: str) -> str:
    return texte[0].upper() + texte[1:] + "."
