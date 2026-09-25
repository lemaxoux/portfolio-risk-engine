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

from backend import typography
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
    MIN_ESTIMABLE_SAMPLE,
    MIN_REGRESSION_SAMPLE,
    MIN_SCENARIO_COVERAGE,
    STRONG_CORRELATION,
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


def _points(ecart: float, decimales: int = 1) -> str:
    """Magnitude d'un écart entre deux parts, en points (singulier sous 2).

    L'accord suit le nombre AFFICHÉ, pas la valeur exacte : 1,96 point s'écrit
    « 2,0 points ». Les chiffres, eux, sont ceux de `typography`.
    """
    valeur = abs(ecart) * 100.0
    unite = "points" if round(valeur, decimales) >= 2 else "point"
    return f"{typography.number(valeur, decimales)}{typography.NBSP}{unite}"


def _enumeration(elements: Sequence[str]) -> str:
    if len(elements) <= 1:
        return "".join(elements)
    return f"{', '.join(elements[:-1])} et {elements[-1]}"


def _lignes(nombre: int) -> str:
    return typography.lines(nombre)


def _seances(nombre: int) -> str:
    """« 504 séances », insécable. Un seul endroit pour ce lien-là aussi."""
    return typography.sessions(nombre)


# --------------------------------------------- Taille de l'échantillon --
#
# Deux régimes, parce que ce sont deux problèmes différents.
#
# `_non_estimable` — en deçà de trois observations, le centrage ne laisse qu'une
# seule direction : corrélation, beta et contributions à la variance s'y
# calculent tous à partir d'un unique écart journalier. Ce ne sont plus des
# mesures bruyantes, ce sont des identités arithmétiques. La règle REFUSE alors
# de chiffrer. Y attacher une mention d'échantillon mince ne réparerait rien :
# la phrase affirmerait toujours, sur le portefeuille, quelque chose que le
# nombre ne peut pas porter.
#
# LA MÊME FRONTIÈRE VAUT POUR LES CONTRIBUTIONS À LA VARIANCE, et pour les
# lignes effectives « en risque » qui s'en déduisent. À n = 2 la covariance est
# de rang 1 — Σ ∝ δδᵀ, δ étant l'écart entre les deux rendements — et la
# contribution de i se réduit exactement à `wᵢδᵢ / (wᵀδ)` : la part de chaque
# ligne dans UNE différence journalière, présentée comme une décomposition de
# variance. Vérifié à 1e-16 près.
#
# La singularité de Σ quand n ≤ k (nombre de lignes) ne crée PAS de troisième
# régime, contrairement à ce qu'on pourrait craindre : les contributions n'ont
# besoin que de `wᵀΣw > 0`, jamais d'une inverse. Mesuré sur un modèle à un
# facteur, 7 lignes, 3 000 tirages, contre une vérité connue : l'erreur absolue
# médiane passe de 0,034 à n = 7 (Σ singulière) à 0,031 à n = 8 (Σ inversible),
# sans rupture — là où elle vaut 0,122 à n = 2 contre 0,069 à n = 3. C'est la
# probabilité d'une contribution NÉGATIVE qui dit le mieux la dégénérescence :
# 73 % à n = 2, 50 % à n = 3, 12 % à n = 7, nulle au-delà de vingt.
#
# `_echantillon_mince` — entre trois séances et le seuil de régression, le
# chiffre est une estimation réelle mais fragile. La règle chiffre et le dit,
# exactement comme `crisis_degradation` le fait déjà pour le R² de crise.
#
# Le contrôle porte sur `window.observations` et jamais sur la fenêtre
# DEMANDÉE : le panel aligné se réduit à l'intersection des dates, et une seule
# ligne cotée depuis peu fait tomber une fenêtre de 504 séances à quelques
# dizaines d'observations sans que le paramètre ait changé.


def _non_estimable(seances: int) -> bool:
    return seances < MIN_ESTIMABLE_SAMPLE.value


def _echantillon_mince(seances: int) -> bool:
    return seances < MIN_REGRESSION_SAMPLE.value


def _mention_mince(quoi: str, seances: int) -> str:
    """Phrase ajoutée à une estimation fragile, vide sinon."""
    if not _echantillon_mince(seances):
        return ""
    return (
        f" Estimation mince : {_seances(seances)}, moins que les "
        f"{int(MIN_REGRESSION_SAMPLE.value)} en deçà desquelles quelques "
        f"journées extrêmes suffisent à porter {quoi}."
    )


# ------------------------------------------- 1. Concentration effective --


def effective_concentration(report: RiskReport) -> Observation:
    """« Tes N lignes se comportent comme M lignes effectives », en capital ET en
    risque. Aucun seuil.

    La version en capital (`1/Σwᵢ²`) seule est la plus flatteuse des deux quand
    le risque se concentre davantage que la valeur : un portefeuille équilibré en
    montants peut porter l'essentiel de sa variance sur quelques lignes volatiles
    et corrélées. L'écart entre les deux nombres est l'observation la plus utile
    de la règle — le risque ne se répartit pas comme le capital.
    """
    c = report.concentration
    vc = report.variance_contributions
    en_capital = c.effective_positions
    seances = vc.window.observations
    provenance = (
        f"capital : valorisation au {c.as_of} ; risque : fenêtre d'estimation "
        f"de {vc.window}"
    )

    if _non_estimable(seances):
        # La moitié EN CAPITAL reste dite : c'est une mesure ponctuelle, sans
        # fenêtre d'estimation, que la brièveté de l'historique ne touche pas.
        # Seule la moitié en risque disparaît, et elle dit pourquoi.
        return Observation(
            rule=RuleId.EFFECTIVE_CONCENTRATION,
            subject="portefeuille",
            statement=(
                f"Tes {_lignes(c.n_positions)} se comportent comme "
                f"{typography.number(en_capital, 1)} lignes effectives en capital "
                "(inverse de la somme des carrés des poids) ; l'équipondération "
                f"en donnerait {c.n_positions}. La lecture en risque n'est pas "
                f"disponible : sur {_seances(seances)}, la covariance est de rang "
                "1 et les contributions à la variance s'y ramènent à la part de "
                "chaque ligne dans une seule différence journalière."
            ),
            facts={
                "lignes": c.n_positions,
                "lignes_effectives_capital": en_capital,
                "lignes_effectives_risque": None,
                "hhi": c.hhi,
                "reference_equiponderee": c.equal_weight_reference,
                "seances": seances,
            },
            provenance=provenance,
            thresholds=(MIN_ESTIMABLE_SAMPLE,),
        )

    en_risque = vc.effective_positions

    if c.n_positions == 1:
        texte = (
            "Ton portefeuille compte une seule ligne : il se comporte comme une "
            "seule ligne effective, en capital comme en risque."
        )
    else:
        capital_affiche = typography.number(en_capital, 1)
        risque_affiche = typography.number(en_risque, 1)
        ecart = round(en_risque, 1) - round(en_capital, 1)
        liaison = "mais" if ecart < 0 else "et"
        phrases = [
            f"Tes {_lignes(c.n_positions)} se comportent comme "
            f"{capital_affiche} lignes effectives en capital, {liaison} "
            f"comme {risque_affiche} en risque "
            "(inverse de la somme des carrés des poids, puis des contributions à la "
            "variance)."
        ]
        phrases.append(
            f"En capital, l'équipondération en donnerait {c.n_positions}."
        )
        if ecart < 0:
            phrases.append(
                "Le risque se concentre davantage que le capital : la lecture en "
                "capital seule est la plus flatteuse des deux."
            )
        elif ecart > 0:
            phrases.append("Le risque se répartit plus également que le capital.")
        else:
            phrases.append("Le risque se répartit comme le capital.")
        if vc.has_negative_contribution:
            phrases.append(
                "Une contribution négative à la variance rend la lecture en risque "
                "approximative."
            )
        mince = _mention_mince("la lecture en risque", seances)
        if mince:
            phrases.append(mince.strip())
        texte = " ".join(phrases)

    return Observation(
        rule=RuleId.EFFECTIVE_CONCENTRATION,
        subject="portefeuille",
        statement=texte,
        facts={
            "lignes": c.n_positions,
            "lignes_effectives_capital": en_capital,
            "lignes_effectives_risque": en_risque,
            "hhi": c.hhi,
            "reference_equiponderee": c.equal_weight_reference,
            "seances": seances,
        },
        provenance=provenance,
        thresholds=(
            (MIN_REGRESSION_SAMPLE,) if _echantillon_mince(seances) else ()
        ),
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
            f"{ticker} au résultat du portefeuille a été de "
            f"{typography.signed_points(pire[1])}."
        )
    elif pire[1] < 0 < meilleur[1]:
        phrase = (
            f"Dans les crises rejouées, {ticker} a pesé dans les deux sens : "
            f"{typography.signed_points(pire[1])} ({pire[0].scenario.name}), mais "
            f"{typography.signed_points(meilleur[1])} ({meilleur[0].scenario.name})."
        )
    elif meilleur[1] <= 0:
        phrase = (
            f"Dans les crises rejouées, la contribution de {ticker} au résultat du "
            f"portefeuille a été négative à chaque fois, de "
            f"{typography.signed_points(pire[1])} "
            f"({pire[0].scenario.name}) à {typography.signed_points(meilleur[1])} "
            f"({meilleur[0].scenario.name})."
        )
    else:
        phrase = (
            f"Dans les crises rejouées, la contribution de {ticker} au résultat du "
            f"portefeuille a été positive à chaque fois, de "
            f"{typography.signed_points(pire[1])} "
            f"({pire[0].scenario.name}) à {typography.signed_points(meilleur[1])} "
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
    seances = vc.window.observations
    parcours = _scenario_record(scenarios)
    observations: list[Observation] = []

    if _non_estimable(seances):
        # Une seule observation, et aucun chiffre. Une décomposition par ligne
        # avec des parts nulles laisserait croire à des parts mesurées à zéro.
        return [
            Observation(
                rule=RuleId.VARIANCE_CONTRIBUTION,
                subject="portefeuille",
                statement=(
                    f"Sur {_seances(seances)}, la variance du portefeuille ne se "
                    "décompose pas : la matrice de covariance est de rang 1, et "
                    "la part de chaque ligne s'y ramène à sa part dans une seule "
                    "différence journalière. Aucune contribution n'est donc "
                    "chiffrée ici."
                ),
                facts={"seances": seances, "lignes": len(vc.weights)},
                provenance=f"fenêtre d'estimation : {vc.window}",
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
            )
        ]

    mince = _mention_mince("une part de variance", seances)
    seuils_mince = (MIN_REGRESSION_SAMPLE,) if _echantillon_mince(seances) else ()

    ordre = sorted(vc.contributions, key=lambda t: vc.contributions[t], reverse=True)
    for rang, ticker in enumerate(ordre):
        part = vc.contributions[ticker]
        poids = vc.weights[ticker]
        ecart = part - poids

        phrases = [
            f"{ticker} pèse {typography.percent(poids, 1)} de la valeur du portefeuille et "
            f"{typography.percent(part, 1)} de sa variance."
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

        if mince:
            phrases.append(mince.strip())

        historique = parcours.get(ticker, [])
        if historique:
            phrases.append(_record_sentence(ticker, historique))

        faits: dict[str, float | int | str | None] = {
            "poids": poids,
            "part_de_variance": part,
            "ecart": ecart,
            "seances": seances,
        }
        faits.update({f"scenario:{r.scenario.key}": v for r, v in historique})

        observations.append(
            Observation(
                rule=RuleId.VARIANCE_CONTRIBUTION,
                subject=ticker,
                statement=" ".join(phrases),
                facts=faits,
                provenance=f"fenêtre d'estimation : {vc.window}",
                thresholds=(capital_share(ticker, poids), *seuils_mince),
            )
        )
    return observations


# ----------------------------------------- 3. Diversification apparente --


def apparent_diversification(
    report: RiskReport, threshold: Threshold = STRONG_CORRELATION
) -> list[Observation]:
    """Paires de lignes qui ont largement évolué ensemble sur la fenêtre."""
    correlation = report.matrices.correlation
    seances = report.matrices.window.observations
    provenance = f"fenêtre d'estimation : {report.matrices.window}"

    # Le nombre de lignes se lit sur la matrice quand elle existe, sinon sur la
    # concentration : le moteur rend `correlation` à None sous
    # MIN_ESTIMABLE_OBSERVATIONS, et une règle qui déréférencerait la matrice
    # avant de vérifier la fenêtre tomberait sur un None.
    lignes = (
        len(correlation.columns)
        if correlation is not None
        else report.concentration.n_positions
    )
    if lignes < 2:
        return []

    if correlation is None or _non_estimable(seances):
        return [
            Observation(
                rule=RuleId.APPARENT_DIVERSIFICATION,
                subject="portefeuille",
                statement=(
                    f"Sur {_seances(seances)}, aucune corrélation n'est estimable : "
                    "trois observations sont nécessaires pour qu'un coefficient "
                    "mesure quelque chose. En deçà, la droite d'ajustement passe "
                    "exactement par les points et la corrélation vaut ±1 quelles que "
                    "soient les données — le chiffre serait le même pour deux titres "
                    "pris au hasard. Aucune paire n'est donc décrite ici."
                ),
                facts={"seances": seances, "correlation_max": None},
                provenance=provenance,
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
            )
        ]

    tickers = list(correlation.columns)
    mince = _mention_mince("le coefficient", seances)
    seuils_mince = (MIN_REGRESSION_SAMPLE,) if _echantillon_mince(seances) else ()
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
                    f"{a} et {b} ont une corrélation de {typography.number(rho, 2)} sur "
                    f"{_seances(seances)} : elles ont largement évolué ensemble, et "
                    "apportent moins de diversification que leur nombre ne le "
                    f"suggère.{mince}"
                ),
                facts={"correlation": rho, "seances": seances},
                provenance=provenance,
                thresholds=(threshold, *seuils_mince),
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
                f""
                f"{typography.number(threshold.value, 2)} sur {_seances(seances)}. La paire la "
                f"plus corrélée est {a}–{b}, à {typography.number(rho, 2)}.{mince}"
            ),
            facts={"correlation_max": rho, "paire": f"{a}–{b}", "seances": seances},
            provenance=provenance,
            thresholds=(
                threshold,
                most_correlated_pair(a, b, rho),
                *seuils_mince,
            ),
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
    provenance = f"fenêtre d'estimation : {beta.window}"

    if _non_estimable(seances):
        return [
            Observation(
                rule=RuleId.SYSTEMATIC_SHARE,
                subject="portefeuille",
                statement=(
                    f"Sur {_seances(seances)}, la part systématique n'est pas "
                    "estimable : une régression avec constante n'a plus aucun degré "
                    "de liberté résiduel en deçà de trois observations, et son R² "
                    "vaut 1 quelles que soient les données. Aucune part expliquée "
                    f"par {beta.benchmark} n'est donc avancée ici."
                ),
                facts={
                    "r2": None,
                    "part_propre": None,
                    "benchmark": beta.benchmark,
                    "seances": seances,
                },
                provenance=provenance,
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
            )
        ]

    return [
        Observation(
            rule=RuleId.SYSTEMATIC_SHARE,
            subject="portefeuille",
            statement=(
                f"Sur {_seances(seances)}, "
                f"{typography.percent(r2, 0)} de la variance du portefeuille "
                f"s'explique par les mouvements de {beta.benchmark} "
                f"(R² "
                f"{typography.number(r2, 2)}). Cette part est du risque de marché : elle est "
                "commune aux actions américaines, et en détenir davantage ne la dilue "
                f"pas. Les "
                f"{typography.percent(1.0 - r2, 0)} restants sont propres aux lignes "
                "détenues ; c'est sur eux seuls que la diversification entre lignes a "
                f"prise.{_mention_mince('le R²', seances)}"
            ),
            facts={
                "r2": r2,
                "part_propre": 1.0 - r2,
                "benchmark": beta.benchmark,
                "seances": seances,
            },
            provenance=provenance,
            thresholds=(
                (MIN_REGRESSION_SAMPLE,) if _echantillon_mince(seances) else ()
            ),
        )
    ]


# ------------------------------------------------ 5. Dégradation en crise --


def _hausse(c: RegimeComparison) -> bool:
    return c.systematic_share_change > 0


def _episodes(crises: Sequence[RegimeComparison]) -> str:
    """« l'épisode Krach COVID (23 séances) », ou son pluriel.

    « L'épisode » plutôt qu'un article devant le nom : les noms du catalogue
    n'ont pas tous le même genre.
    """
    noms = [
        f"{c.scenario.name} ({_seances(c.crisis_beta.observations)})" for c in crises
    ]
    return ("l'épisode " if len(crises) == 1 else "les épisodes ") + _enumeration(noms)


def _trop_mince(crises: Sequence[RegimeComparison]) -> str:
    if len(crises) == 1:
        return "l'échantillon est trop mince pour conclure"
    return "leurs échantillons sont trop minces pour conclure"


def _conclusion_des_crises(
    suffisantes: Sequence[RegimeComparison], minces: Sequence[RegimeComparison]
) -> list[str]:
    """Ce que les crises rejouées permettent de conclure, et ce qu'elles ne
    permettent pas.

    Seules les crises estimées sur au moins MIN_REGRESSION_SAMPLE séances
    entrent dans le décompte. Une crise dont la même phrase vient de qualifier
    l'échantillon de trop mince ne peut pas être comptée ensuite comme une
    preuve. Elle est citée à part, avec le sens où elle va. Sans aucune
    estimation suffisante, aucune conclusion générale n'est tirée.
    """
    phrases: list[str] = []
    total = len(suffisantes)
    hausses = sum(1 for c in suffisantes if _hausse(c))
    # Sans crise mince, la portée va de soi ; avec, elle doit se dire.
    portee = "estimée sur assez de séances" if minces else "rejouée"
    portees = "estimées sur assez de séances" if minces else "rejouées"

    if total == 0:
        phrases.append(
            "La crise rejouée n'est pas estimée sur assez de séances : aucune "
            "conclusion n'en est tirée."
            if len(minces) == 1
            else f"Aucune des {len(minces)} crises rejouées n'est estimée sur "
            "assez de séances : aucune conclusion générale n'en est tirée."
        )
    elif hausses == total:
        phrases.append(
            (f"Elle augmente dans la crise {portee}" if total == 1
             else f"Elle augmente dans les {total} crises {portees}")
            + " : la diversification entre lignes s'est affaiblie précisément "
            + ("pendant l'épisode où elle aurait servi." if total == 1
               else "pendant les épisodes où elle aurait servi.")
        )
    elif hausses == 0:
        phrases.append(
            f"Elle n'augmente pas dans la crise {portee}." if total == 1
            else f"Elle n'augmente dans aucune des {total} crises {portees}."
            if minces
            else "Elle n'augmente dans aucune des crises rejouées."
        )
    else:
        crises = "crise" if hausses == 1 else "crises"
        phrases.append(
            f"Elle augmente dans {hausses} {crises} sur {total}"
            + (f" {portees}." if minces else ".")
        )

    if not minces:
        return phrases

    unanime = total > 0 and hausses in (0, total)
    if unanime:
        sens_de_la_conclusion = hausses == total
        memes = [c for c in minces if _hausse(c) == sens_de_la_conclusion]
        contraires = [c for c in minces if _hausse(c) != sens_de_la_conclusion]
        for groupe, sens in ((memes, "dans le même sens"), (contraires, "en sens contraire")):
            if groupe:
                verbe = "va" if len(groupe) == 1 else "vont"
                episodes = _episodes(groupe)
                phrases.append(
                    f"{episodes[0].upper()}{episodes[1:]} {verbe} {sens}, mais "
                    f"{_trop_mince(groupe)}."
                )
    else:
        for groupe, verbe in (
            ([c for c in minces if _hausse(c)], "augmente"),
            ([c for c in minces if not _hausse(c)], "n'augmente pas"),
        ):
            if groupe:
                phrases.append(
                    f"Elle {verbe} pendant {_episodes(groupe)}, mais "
                    f"{_trop_mince(groupe)}."
                )
    return phrases


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
                f""
                f"{typography.percent(c.crisis_beta.r_squared, 0)} ({c.scenario.name}{mince})"
            )
        else:
            morceaux.append(
                f"de {typography.percent(c.calm_beta.r_squared, 0)} à "
                f""
                f"{typography.percent(c.crisis_beta.r_squared, 0)} ({c.scenario.name}{mince})"
            )

    if calme_commun:
        phrases = [
            f"La part systématique du risque passe de "
            f"{typography.percent(calmes[0], 0)} en régime "
            f"calme à {_enumeration(morceaux)} dans les crises rejouées."
        ]
    else:
        phrases = [
            "La part systématique du risque, mesurée sur les lignes couvertes de "
            f"chaque scénario, passe {_enumeration(morceaux)}."
        ]

    suffisantes = [c for c in valides if not c.crisis_beta.sample_too_thin]
    minces = [c for c in valides if c.crisis_beta.sample_too_thin]
    phrases.extend(_conclusion_des_crises(suffisantes, minces))

    exclus = [c for c in regimes if c.unavailable_reason is not None]
    if exclus:
        phrases.append(
            "Sans comparaison possible : "
            + _enumeration([c.scenario.name for c in exclus])
            + "."
        )

    # Les décomptes suivent la phrase : ceux qui fondent la conclusion ne
    # portent que sur les crises estimées sur assez de séances, et les crises
    # sous le seuil sont comptées à part. Un lecteur des faits ne doit pas
    # retrouver le « 3 sur 3 » que la phrase n'a plus le droit d'écrire.
    faits: dict[str, float | int | str | None] = {
        "r2_calme": calmes[0] if calme_commun else None,
        "crises_comparees": len(suffisantes),
        "crises_en_hausse": sum(1 for c in suffisantes if _hausse(c)),
        "crises_comparees_echantillon_mince": len(minces),
        "crises_en_hausse_echantillon_mince": sum(1 for c in minces if _hausse(c)),
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
                f"régime calme : {_seances(calme.observations)}, {calme.start} → "
                f"{calme.end} ; crises : "
                + " ; ".join(
                    f"{c.scenario.name}, {_seances(c.crisis_beta.observations)}"
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
                f"{nom} ne couvre que "
                f"{typography.percent(couverture.value_share, 0)} de la valeur "
                f"du portefeuille ({detail}). En dessous de "
                f"{typography.percent(threshold.value, 0)}, "
                "la partie rejouée est minoritaire dans la valeur : aucun chiffre "
                "principal n'est donné pour ce scénario."
            )
        else:
            texte = (
                f"{nom} couvre "
                f"{typography.percent(couverture.value_share, 0)} de la valeur du "
                f"portefeuille ({detail}). Son résultat de bout en bout "
                f"("
                f"{typography.percent(resultat.end_to_end_return, 1)}) porte sur cette partie "
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


# ------------------------------------------------------------ Évaluation --


def evaluate(
    report: RiskReport,
    scenarios: Sequence[ScenarioResult] = (),
    regimes: Sequence[RegimeComparison] = (),
) -> RulesReport:
    """Applique les six règles aux résultats déjà produits. Fonction pure."""
    observations = [
        effective_concentration(report),
        *variance_contribution(report, scenarios),
        *apparent_diversification(report),
        *systematic_share(report),
        *crisis_degradation(regimes),
        *scenario_coverage(scenarios),
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
