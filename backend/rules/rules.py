"""Moteur de règles : observations chiffrées sur les sorties des Phases 4 et 5.

═══ LE MOTEUR DÉCRIT, IL NE PRESCRIT PAS ═══

« Cette ligne pèse 35 % de la variance de ton portefeuille » est un fait
vérifiable. « Tu devrais l'alléger » est un conseil en investissement, que rien
dans ce projet ne permet de donner : le moteur ignore l'horizon de placement, les
objectifs, la fiscalité et le reste du patrimoine. Chaque règle est donc formulée
comme une observation chiffrée, jamais comme une action à mener.

La preuve que ça compte est dans les chiffres du projet. Une règle « réduis la
ligne énergie » aurait visé précisément la ligne qui, en 2022, a apporté environ
9 points au portefeuille pendant que le marché perdait un quart de sa valeur. La
concentration amplifie la variance dans les deux sens : les observations disent
les deux.

═══ PAS DE SCORE GLOBAL ═══

Aucun « score de risque sur 100 ». Il comprimerait des grandeurs non
commensurables — une concentration, une part systématique, une fragilité de
queue — en un nombre dont l'échelle ne veut rien dire, et il inviterait
exactement à la lecture prescriptive qu'on évite. Un tel chiffre fonctionne quand
un conseiller humain l'interprète ; sans cet intermédiaire, il a l'air d'une
autorité sans en être une. Le résultat du moteur est une liste d'observations,
et rien d'autre.

═══ LE MOTEUR NE RECALCULE RIEN ═══

Chaque règle lit un résultat déjà produit par le moteur de risque — rapport de la
Phase 4, scénarios et comparaisons de régimes de la Phase 5 — et le met en mots.
Aucune mesure n'est estimée ici ; un test vérifie que ce module n'importe aucun
module de calcul.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from backend.risk_engine.config import DEFAULT_WINDOW
from backend.risk_engine.engine import (
    RegimeComparison,
    RiskReport,
    ScenarioResult,
    analyse_portfolio,
    compare_all_regimes,
    run_all_scenarios,
)

from .disclaimer import acceptance_text
from .thresholds import (
    MIN_REGRESSION_SAMPLE,
    MIN_SCENARIO_COVERAGE,
    STRONG_CORRELATION,
    THIN_TAIL,
    Threshold,
    capital_share,
    most_correlated_pair,
)


class RuleId(Enum):
    EFFECTIVE_CONCENTRATION = "concentration effective"
    VARIANCE_CONTRIBUTION = "contribution à la variance"
    APPARENT_DIVERSIFICATION = "diversification apparente"
    SYSTEMATIC_SHARE = "part systématique"
    CRISIS_DEGRADATION = "dégradation en crise"
    SCENARIO_COVERAGE = "couverture d'un scénario"
    TAIL_FRAGILITY = "fragilité de la queue"


@dataclass(frozen=True)
class Observation:
    """Une propriété du portefeuille, chiffrée, avec sa provenance.

    `statement` est la phrase destinée à l'utilisateur ; `facts` porte les mêmes
    chiffres sous forme exploitable. `thresholds` est vide quand la mesure parle
    d'elle-même ; sinon chaque seuil dit d'où il vient, et un seuil choisi à la
    main le dit explicitement.
    """

    rule: RuleId
    subject: str
    statement: str
    facts: Mapping[str, float | int | str | None]
    provenance: str
    thresholds: tuple[Threshold, ...] = ()

    @property
    def uses_chosen_threshold(self) -> bool:
        return any(seuil.chosen for seuil in self.thresholds)

    def render(self) -> str:
        lignes = [f"[{self.rule.value} — {self.subject}] {self.statement}"]
        if self.thresholds:
            lignes += [f"  Seuil : {seuil}" for seuil in self.thresholds]
        else:
            lignes.append("  Aucun seuil : la mesure parle d'elle-même.")
        lignes.append(f"  Provenance : {self.provenance}")
        return "\n".join(lignes)


@dataclass(frozen=True)
class RulesReport:
    """Les observations d'un portefeuille, et le texte d'acceptation qui les borne."""

    portfolio_id: int
    as_of: date
    observations: tuple[Observation, ...]
    disclaimer: str

    def of_rule(self, rule: RuleId) -> tuple[Observation, ...]:
        return tuple(o for o in self.observations if o.rule is rule)

    def render(self) -> str:
        return "\n\n".join(o.render() for o in self.observations)


# ----------------------------------------------------------- Mise en forme --


def _decimal(valeur: float, decimales: int) -> str:
    return f"{valeur:.{decimales}f}".replace(".", ",").replace("-", "−")


def _pct(valeur: float, decimales: int = 1) -> str:
    return f"{_decimal(valeur * 100.0, decimales)} %"


def _points(ecart: float, decimales: int = 1) -> str:
    """Magnitude d'un écart entre deux parts, en points (singulier sous 2)."""
    valeur = abs(ecart) * 100.0
    unite = "points" if round(valeur, decimales) >= 2 else "point"
    return f"{_decimal(valeur, decimales)} {unite}"


def _signed_points(valeur: float, decimales: int = 1) -> str:
    signe = "+" if valeur > 0 else ("−" if valeur < 0 else "")
    return f"{signe}{_decimal(abs(valeur) * 100.0, decimales)} pts"


def _enumeration(elements: Sequence[str]) -> str:
    if len(elements) <= 1:
        return "".join(elements)
    return f"{', '.join(elements[:-1])} et {elements[-1]}"


def _lignes(nombre: int) -> str:
    return f"{nombre} ligne" if nombre == 1 else f"{nombre} lignes"


# ------------------------------------------- 1. Concentration effective --


def effective_concentration(report: RiskReport) -> Observation:
    """« Tes N lignes se comportent comme M lignes effectives. » Aucun seuil."""
    c = report.concentration
    if c.n_positions == 1:
        texte = (
            "Ton portefeuille compte une seule ligne : il se comporte comme une "
            "seule ligne effective."
        )
    else:
        texte = (
            f"Tes {c.n_positions} lignes se comportent comme "
            f"{_decimal(c.effective_positions, 1)} lignes effectives en valeur "
            f"(inverse de l'indice de Herfindahl-Hirschman, {_decimal(c.hhi, 3)}). "
            f"À poids égaux, elles en vaudraient {c.n_positions}."
        )
    return Observation(
        rule=RuleId.EFFECTIVE_CONCENTRATION,
        subject="portefeuille",
        statement=texte,
        facts={
            "lignes": c.n_positions,
            "lignes_effectives": c.effective_positions,
            "hhi": c.hhi,
            "reference_equiponderee": c.equal_weight_reference,
        },
        provenance=f"valorisation au {c.as_of}",
    )


# ------------------------------------------ 2. Contribution à la variance --


def _scenario_record(
    scenarios: Sequence[ScenarioResult],
) -> dict[str, list[tuple[ScenarioResult, float]]]:
    """Contribution de chaque ligne à chaque scénario exploitable.

    Un scénario sous le seuil de couverture ne fournit pas de chiffre principal
    (règle 6) ; ses contributions ne sont pas reprises ici non plus.
    """
    parcours: dict[str, list[tuple[ScenarioResult, float]]] = {}
    for resultat in scenarios:
        if resultat.end_to_end_return is None:
            continue
        if resultat.coverage.value_share < MIN_SCENARIO_COVERAGE.value:
            continue
        for ligne in resultat.contributions:
            parcours.setdefault(ligne.ticker, []).append((resultat, ligne.contribution))
    return parcours


def _record_sentence(ticker: str, historique: list[tuple[ScenarioResult, float]]) -> str:
    pire = min(historique, key=lambda element: element[1])
    meilleur = max(historique, key=lambda element: element[1])

    if len(historique) == 1:
        phrase = (
            f"Dans la crise rejouée ({pire[0].scenario.name}), la contribution de "
            f"{ticker} au résultat du portefeuille a été de {_signed_points(pire[1])}."
        )
    elif pire[1] < 0 < meilleur[1]:
        phrase = (
            f"Dans les crises rejouées, {ticker} a pesé dans les deux sens : "
            f"{_signed_points(pire[1])} ({pire[0].scenario.name}), mais "
            f"{_signed_points(meilleur[1])} ({meilleur[0].scenario.name})."
        )
    elif meilleur[1] <= 0:
        phrase = (
            f"Dans les crises rejouées, la contribution de {ticker} au résultat du "
            f"portefeuille a été négative à chaque fois, de {_signed_points(pire[1])} "
            f"({pire[0].scenario.name}) à {_signed_points(meilleur[1])} "
            f"({meilleur[0].scenario.name})."
        )
    else:
        phrase = (
            f"Dans les crises rejouées, la contribution de {ticker} au résultat du "
            f"portefeuille a été positive à chaque fois, de {_signed_points(pire[1])} "
            f"({pire[0].scenario.name}) à {_signed_points(meilleur[1])} "
            f"({meilleur[0].scenario.name})."
        )

    if any(not resultat.coverage.is_complete for resultat, _ in historique):
        phrase += " Contributions calculées sur la partie couverte du portefeuille."
    return phrase


def variance_contribution(
    report: RiskReport, scenarios: Sequence[ScenarioResult] = ()
) -> list[Observation]:
    """Part de chaque ligne dans la variance, face à sa part du capital.

    Présentée dans les deux sens : ce qu'une ligne pèse dans le risque, et —
    quand les scénarios sont fournis — ce qu'elle a réellement apporté ou coûté
    pendant les crises rejouées, pertes comme gains.
    """
    vc = report.variance_contributions
    parcours = _scenario_record(scenarios)
    observations = []

    ordre = sorted(vc.contributions, key=lambda t: vc.contributions[t], reverse=True)
    for rang, ticker in enumerate(ordre):
        part = vc.contributions[ticker]
        poids = vc.weights[ticker]
        ecart = part - poids

        phrases = [
            f"{ticker} pèse {_pct(poids)} de la valeur du portefeuille et "
            f"{_pct(part)} de sa variance."
        ]
        if part < 0:
            phrases.append(
                "Sa contribution est négative : sur la fenêtre, ses mouvements ont "
                "en moyenne compensé ceux des autres lignes."
            )
        elif math.isclose(part, poids, abs_tol=5e-4):
            phrases.append("Sa part du risque correspond à sa part du capital.")
        elif ecart > 0:
            phrases.append(
                f"Sa part du risque dépasse sa part du capital de {_points(ecart)}."
            )
        else:
            phrases.append(
                f"Sa part du risque est inférieure à sa part du capital de "
                f"{_points(ecart)}."
            )

        if rang == 0 and len(ordre) > 1:
            # Propriété générale, dite une fois, sur la ligne qui pèse le plus.
            phrases.append(
                "Plus une ligne pèse dans la variance, plus elle pèse sur le résultat "
                "du portefeuille, dans les deux sens : à la baisse comme à la hausse."
            )

        historique = parcours.get(ticker, [])
        if historique:
            phrases.append(_record_sentence(ticker, historique))

        faits: dict[str, float | int | str | None] = {
            "poids": poids,
            "part_de_variance": part,
            "ecart": ecart,
        }
        faits.update({f"scenario:{r.scenario.key}": v for r, v in historique})

        observations.append(
            Observation(
                rule=RuleId.VARIANCE_CONTRIBUTION,
                subject=ticker,
                statement=" ".join(phrases),
                facts=faits,
                provenance=f"fenêtre d'estimation : {vc.window}",
                thresholds=(capital_share(ticker, poids),),
            )
        )
    return observations


# ----------------------------------------- 3. Diversification apparente --


def apparent_diversification(
    report: RiskReport, threshold: Threshold = STRONG_CORRELATION
) -> list[Observation]:
    """Paires de lignes qui ont largement évolué ensemble sur la fenêtre."""
    correlation = report.matrices.correlation
    tickers = list(correlation.columns)
    if len(tickers) < 2:
        return []

    seances = report.matrices.window.observations
    provenance = f"fenêtre d'estimation : {report.matrices.window}"
    paires = sorted(
        (
            (float(correlation.loc[a, b]), a, b)
            for i, a in enumerate(tickers)
            for b in tickers[i + 1 :]
        ),
        reverse=True,
    )
    fortes = [paire for paire in paires if paire[0] >= threshold.value]

    if fortes:
        return [
            Observation(
                rule=RuleId.APPARENT_DIVERSIFICATION,
                subject=f"{a}–{b}",
                statement=(
                    f"{a} et {b} ont une corrélation de {_decimal(rho, 2)} sur "
                    f"{seances} séances : elles ont largement évolué ensemble, et "
                    "apportent moins de diversification que leur nombre ne le suggère."
                ),
                facts={"correlation": rho, "seances": seances},
                provenance=provenance,
                thresholds=(threshold,),
            )
            for rho, a, b in fortes
        ]

    rho, a, b = paires[0]
    return [
        Observation(
            rule=RuleId.APPARENT_DIVERSIFICATION,
            subject="portefeuille",
            statement=(
                "Aucune paire de lignes n'atteint une corrélation de "
                f"{_decimal(threshold.value, 2)} sur {seances} séances. La paire la "
                f"plus corrélée est {a}–{b}, à {_decimal(rho, 2)}."
            ),
            facts={"correlation_max": rho, "paire": f"{a}–{b}", "seances": seances},
            provenance=provenance,
            thresholds=(threshold, most_correlated_pair(a, b, rho)),
        )
    ]


# ----------------------------------------------- 4. Part systématique --


def systematic_share(report: RiskReport) -> list[Observation]:
    """Part de la variance expliquée par le marché. Aucun seuil."""
    beta = report.beta
    if beta is None:
        return []

    r2 = beta.r_squared
    seances = beta.window.observations
    return [
        Observation(
            rule=RuleId.SYSTEMATIC_SHARE,
            subject="portefeuille",
            statement=(
                f"Sur {seances} séances, {_pct(r2, 0)} de la variance du portefeuille "
                f"s'explique par les mouvements de {beta.benchmark} "
                f"(R² {_decimal(r2, 2)}). Cette part est du risque de marché : elle est "
                "commune aux actions américaines, et en détenir davantage ne la dilue "
                f"pas. Les {_pct(1.0 - r2, 0)} restants sont propres aux lignes "
                "détenues ; c'est sur eux seuls que la diversification entre lignes a "
                "prise."
            ),
            facts={
                "r2": r2,
                "part_propre": 1.0 - r2,
                "benchmark": beta.benchmark,
                "seances": seances,
            },
            provenance=f"fenêtre d'estimation : {beta.window}",
        )
    ]


# ------------------------------------------------ 5. Dégradation en crise --


def crisis_degradation(regimes: Sequence[RegimeComparison]) -> list[Observation]:
    """Part systématique en régime calme face à chaque crise rejouée."""
    valides = [c for c in regimes if c.unavailable_reason is None]
    if not valides:
        return []

    calmes = [c.calm_beta.r_squared for c in valides]
    calme_commun = all(math.isclose(r2, calmes[0], abs_tol=1e-12) for r2 in calmes)

    morceaux = []
    for c in valides:
        mince = " — échantillon trop mince" if c.crisis_beta.sample_too_thin else ""
        if calme_commun:
            morceaux.append(
                f"{_pct(c.crisis_beta.r_squared, 0)} ({c.scenario.name}{mince})"
            )
        else:
            morceaux.append(
                f"de {_pct(c.calm_beta.r_squared, 0)} à "
                f"{_pct(c.crisis_beta.r_squared, 0)} ({c.scenario.name}{mince})"
            )

    if calme_commun:
        phrases = [
            f"La part systématique du risque passe de {_pct(calmes[0], 0)} en régime "
            f"calme à {_enumeration(morceaux)} dans les crises rejouées."
        ]
    else:
        phrases = [
            "La part systématique du risque, mesurée sur les lignes couvertes de "
            f"chaque scénario, passe {_enumeration(morceaux)}."
        ]

    hausses = sum(1 for c in valides if c.systematic_share_change > 0)
    total = len(valides)
    if hausses == total:
        phrases.append(
            ("Elle augmente dans la crise rejouée" if total == 1
             else f"Elle augmente dans les {total} crises rejouées")
            + " : la diversification entre lignes s'est affaiblie précisément "
            "pendant les épisodes où elle aurait servi."
        )
    elif hausses == 0:
        phrases.append("Elle n'augmente dans aucune des crises rejouées.")
    else:
        phrases.append(f"Elle augmente dans {hausses} crises sur {total}.")

    minces = [c for c in valides if c.crisis_beta.sample_too_thin]
    if minces:
        phrases.append(
            f"Un R² de crise estimé sur moins de {int(MIN_REGRESSION_SAMPLE.value)} "
            "séances repose sur un échantillon trop mince ("
            + _enumeration([c.scenario.name for c in minces])
            + ")."
        )

    exclus = [c for c in regimes if c.unavailable_reason is not None]
    if exclus:
        phrases.append(
            "Sans comparaison possible : "
            + _enumeration([c.scenario.name for c in exclus])
            + "."
        )

    faits: dict[str, float | int | str | None] = {
        "r2_calme": calmes[0] if calme_commun else None,
        "crises_en_hausse": hausses,
        "crises_comparees": total,
    }
    for c in valides:
        faits[f"r2_crise:{c.scenario.key}"] = c.crisis_beta.r_squared
        faits[f"variation:{c.scenario.key}"] = c.systematic_share_change

    calme = valides[0].calm_beta
    return [
        Observation(
            rule=RuleId.CRISIS_DEGRADATION,
            subject="portefeuille",
            statement=" ".join(phrases),
            facts=faits,
            provenance=(
                f"régime calme : {calme.observations} séances, {calme.start} → "
                f"{calme.end} ; crises : "
                + " ; ".join(
                    f"{c.scenario.name}, {c.crisis_beta.observations} séances"
                    for c in valides
                )
            ),
            thresholds=(MIN_REGRESSION_SAMPLE,) if minces else (),
        )
    ]


# ------------------------------------------ 6. Couverture d'un scénario --


def scenario_coverage(
    scenarios: Sequence[ScenarioResult], threshold: Threshold = MIN_SCENARIO_COVERAGE
) -> list[Observation]:
    """Scénarios qui ne couvrent pas tout le portefeuille.

    Sous le seuil de couverture, aucun chiffre principal n'est produit : la
    partie rejouée est minoritaire dans la valeur et ne peut pas tenir lieu du
    portefeuille. Au-dessus, le chiffre est donné avec sa portée et la direction
    de son biais.
    """
    observations = []
    for resultat in scenarios:
        couverture = resultat.coverage
        if couverture.is_complete:
            continue

        nom = resultat.scenario.name
        absentes = _enumeration([e.ticker for e in couverture.excluded])
        detail = (
            f"{_lignes(couverture.covered_count)} sur {couverture.total_count} ; "
            f"sans historique sur la fenêtre : {absentes}"
        )
        faits: dict[str, float | int | str | None] = {
            "part_couverte": couverture.value_share,
            "lignes_couvertes": couverture.covered_count,
            "lignes": couverture.total_count,
        }

        if resultat.end_to_end_return is None:
            texte = (
                f"{nom} : aucune ligne du portefeuille n'a d'historique couvrant la "
                "fenêtre du scénario. Aucun chiffre n'est produit."
            )
        elif couverture.value_share < threshold.value:
            texte = (
                f"{nom} ne couvre que {_pct(couverture.value_share, 0)} de la valeur "
                f"du portefeuille ({detail}). En dessous de {_pct(threshold.value, 0)}, "
                "la partie rejouée est minoritaire dans la valeur : aucun chiffre "
                "principal n'est donné pour ce scénario."
            )
        else:
            texte = (
                f"{nom} couvre {_pct(couverture.value_share, 0)} de la valeur du "
                f"portefeuille ({detail}). Son résultat de bout en bout "
                f"({_pct(resultat.end_to_end_return)}) porte sur cette partie "
                "seulement et sous-estime probablement celui de l'ensemble : une "
                "ligne absente de l'historique d'une crise est cotée plus récemment, "
                "en moyenne plus jeune et plus spéculative."
            )
            faits["resultat_partie_couverte"] = resultat.end_to_end_return

        observations.append(
            Observation(
                rule=RuleId.SCENARIO_COVERAGE,
                subject=resultat.scenario.key,
                statement=texte,
                facts=faits,
                provenance=(
                    f"scénario {resultat.scenario.start} → {resultat.scenario.end} ; "
                    "part de la valeur de marché actuelle"
                ),
                thresholds=(threshold,),
            )
        )
    return observations


# ------------------------------------------------- 7. Fragilité de la queue --


def tail_fragility(report: RiskReport) -> list[Observation]:
    """CVaR moyennés sur une poignée d'observations de queue."""
    observations = []
    for niveau in sorted(report.expected_shortfall):
        es = report.expected_shortfall[niveau]
        if not es.thin_tail:
            continue
        observations.append(
            Observation(
                rule=RuleId.TAIL_FRAGILITY,
                subject=f"CVaR {_pct(niveau, 0)}",
                statement=(
                    f"Le CVaR à {_pct(niveau, 0)} ({_pct(es.value, 2)} de perte moyenne "
                    "au-delà du quantile de VaR) est la moyenne de "
                    f"{es.tail_observations} séances seulement, sur une fenêtre de "
                    f"{es.window.observations}. Le chiffre reste calculable, mais "
                    f"chacune de ces journées y pèse pour {_pct(1.0 / es.tail_observations, 0)}."
                ),
                facts={
                    "niveau": niveau,
                    "cvar": es.value,
                    "observations_de_queue": es.tail_observations,
                    "seances": es.window.observations,
                },
                provenance=f"fenêtre d'estimation : {es.window}",
                thresholds=(THIN_TAIL,),
            )
        )
    return observations


# ------------------------------------------------------------ Évaluation --


def evaluate(
    report: RiskReport,
    scenarios: Sequence[ScenarioResult] = (),
    regimes: Sequence[RegimeComparison] = (),
) -> RulesReport:
    """Applique les sept règles aux résultats déjà produits. Fonction pure."""
    observations = [
        effective_concentration(report),
        *variance_contribution(report, scenarios),
        *apparent_diversification(report),
        *systematic_share(report),
        *crisis_degradation(regimes),
        *scenario_coverage(scenarios),
        *tail_fragility(report),
    ]
    return RulesReport(
        portfolio_id=report.portfolio_id,
        as_of=report.as_of,
        observations=tuple(observations),
        disclaimer=acceptance_text(report.window.requested),
    )


def evaluate_portfolio(
    conn: sqlite3.Connection, portfolio_id: int, *, window: int = DEFAULT_WINDOW
) -> RulesReport:
    """Rassemble les sorties des Phases 4 et 5, puis applique les règles."""
    return evaluate(
        analyse_portfolio(conn, portfolio_id, window=window),
        run_all_scenarios(conn, portfolio_id),
        compare_all_regimes(conn, portfolio_id, window=window),
    )
