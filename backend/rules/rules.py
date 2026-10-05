"""Moteur de règles : observations chiffrées sur les sorties des Phases 4 et 5.

═══ LE MOTEUR DÉCRIT, IL NE PRESCRIT PAS ═══

« Cette ligne pèse 35 % des variations de votre portefeuille » est un fait
vérifiable. « Vous devriez l'alléger » est un conseil en investissement, que
rien dans ce projet ne permet de donner : le moteur ignore l'horizon de
placement, les objectifs, la fiscalité et le reste du patrimoine. Chaque règle
est donc formulée comme une observation chiffrée, jamais comme une action à
mener.

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

═══ POUR UN LECTEUR QUI PART DE ZÉRO ═══

Les observations s'affichent telles quelles, en section 6, devant un lecteur
qui n'a jamais entendu parler de variance ni de R² (textes de lecture validés
le 2026-10-05). Elles le vouvoient, disent « variations » pour la variance,
« la part qui suit le marché » pour la part systématique, « jours de bourse »
pour les séances, et la période en mots (`Window.period_label`). Le terme exact
et la formule restent dans les seuils, les provenances et la méthodologie.
Sous trois séances, une règle dit que le calcul n'a pas de sens, et combien de
jours il faudrait ; la raison algébrique est celle du seuil qu'elle publie
(`MIN_ESTIMABLE_SAMPLE`).
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
    benchmark_name,
    compare_all_regimes,
    run_all_scenarios,
)
from backend.risk_engine.scenarios import Scenario

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
    """Les six règles. Le nom du membre est l'identifiant machine publié
    (`rule`) ; la valeur est le libellé que la page affiche au-dessus de
    l'observation (`rule_label`), en mots courants."""

    EFFECTIVE_CONCENTRATION = "Combien de lignes, en réalité"
    VARIANCE_CONTRIBUTION = "Poids dans les variations"
    APPARENT_DIVERSIFICATION = "Lignes qui bougent ensemble"
    SYSTEMATIC_SHARE = "Part qui suit le marché"
    CRISIS_DEGRADATION = "Le portefeuille en crise"
    SCENARIO_COVERAGE = "Crise rejouée en partie"


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
            lignes += [f"  {seuil.role.value} : {seuil}" for seuil in self.thresholds]
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


def _lignes_effectives(valeur: float) -> str:
    """« 5,7 lignes », l'accord suivant le nombre affiché, comme `_points`."""
    return typography.counted(
        round(valeur, 1), "ligne", affiche=typography.number(valeur, 1)
    )


def _seances(nombre: int) -> str:
    """« 504 séances », insécable : le mot des provenances."""
    return typography.sessions(nombre)


def _jours(nombre: int) -> str:
    """« 23 jours de bourse », insécable : le mot des phrases.

    Une observation se lit comme une phrase de lecture, où l'interface dit
    « jour de bourse ». « Séance » reste le mot des provenances et des seuils.
    """
    return typography.counted(nombre, "jour de bourse", "jours de bourse")


def _majuscule(texte: str) -> str:
    """La première lettre en capitale : un libellé placé en tête de phrase."""
    return texte[:1].upper() + texte[1:]


def _crise(scenario: Scenario, *, en_tete: bool = False) -> str:
    """« la Crise financière 2008 », avec l'article que déclare le catalogue.

    Aucune phrase ne fait accorder un participe avec ce nom : l'article dit le
    genre de « la Crise », pas celui de « l'épisode » ou d'un nom élidé.
    """
    nom = scenario.with_article
    return _majuscule(nom) if en_tete else nom


def _une(nombre: int) -> str:
    """Un nombre de crises, en lettres jusqu'à dix et au féminin : « une »."""
    return "une" if nombre == 1 else typography.cardinal(nombre)


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


def _mention_mince(seances: int) -> str:
    """Phrase ajoutée à une estimation fragile, vide sinon."""
    if not _echantillon_mince(seances):
        return ""
    return (
        f" Estimation mince : sur {_jours(seances)}, moins que les "
        f"{MIN_REGRESSION_SAMPLE.displayed} retenus (seuil choisi à la main), "
        "quelques jours extrêmes suffisent à faire ce chiffre."
    )


def _refus(seances: int, sujet: str) -> str:
    """Ce qu'une règle écrit au lieu de chiffrer, sous trois séances.

    La raison algébrique — une seule direction après centrage — est la
    rationale du seuil `MIN_ESTIMABLE_SAMPLE`, publiée avec lui. La phrase dit
    au lecteur ce qu'il lui faut : le calcul n'a pas de sens, et combien de
    jours il faudrait.
    """
    return (
        f"Sur {_jours(seances)}, {sujet} n'a pas de sens : il en faut au moins "
        f"{MIN_ESTIMABLE_SAMPLE.displayed}."
    )


# ------------------------------------------- 1. Concentration effective --


def effective_concentration(report: RiskReport) -> Observation:
    """« Vos N lignes pèsent comme M lignes de même montant », puis ce qu'elles
    font bouger : en capital ET en risque. Aucun seuil.

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
        if c.n_positions == 1:
            capital = (
                "Votre portefeuille compte une seule ligne : elle en porte tout le "
                "montant. Ce qu'elle fait bouger n'est pas chiffré."
            )
        else:
            capital = (
                f"Vos {_lignes(c.n_positions)} pèsent comme "
                f"{_lignes_effectives(en_capital)} de même montant ; avec des "
                f"montants égaux, elles compteraient pour {c.n_positions}. Ce "
                "qu'elles font bouger n'est pas chiffré."
            )
        return Observation(
            rule=RuleId.EFFECTIVE_CONCENTRATION,
            subject="portefeuille",
            statement=f"{capital} {_refus(seances, 'ce calcul')}",
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
            "Votre portefeuille compte une seule ligne : elle en porte tout le "
            "montant et toutes les variations."
        )
    else:
        risque_affiche = typography.number(en_risque, 1)
        ecart = round(en_risque, 1) - round(en_capital, 1)
        if ecart < 0:
            suite = (
                f"mais font bouger le portefeuille comme {risque_affiche} seulement "
                ": le risque est plus concentré que l'argent"
            )
        elif ecart > 0:
            suite = (
                f"et font bouger le portefeuille comme {risque_affiche} : le risque "
                "est mieux réparti que l'argent"
            )
        else:
            suite = (
                f"et font bouger le portefeuille comme {risque_affiche} : le risque "
                "se répartit comme l'argent"
            )
        phrases = [
            f"Vos {_lignes(c.n_positions)} pèsent comme "
            f"{_lignes_effectives(en_capital)} de même montant, {suite}.",
            f"Avec des montants égaux, elles compteraient pour {c.n_positions}.",
        ]
        if ecart < 0:
            phrases.append(
                "À ne regarder que les montants, on surestime donc la diversification."
            )
        if vc.has_negative_contribution:
            phrases.append(
                "Au moins une ligne a bougé à rebours des autres : le chiffre de "
                f"{risque_affiche} n'est qu'une approximation."
            )
        mince = _mention_mince(seances)
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
    """Ce que la ligne a coûté ou rapporté au portefeuille dans les crises
    rejouées. Le verbe porte le signe ; les points sont des magnitudes."""
    pire = min(historique, key=lambda element: element[1])
    meilleur = max(historique, key=lambda element: element[1])

    if len(historique) == 1:
        resultat, apport = historique[0]
        if apport == 0:
            effet = "n'a rien coûté ni rapporté au portefeuille"
        else:
            verbe = "a coûté" if apport < 0 else "a rapporté"
            effet = f"{verbe} {_points(apport)} au portefeuille"
        phrase = f"Dans la crise rejouée ({resultat.scenario.name}), {ticker} {effet}."
    elif pire[1] < 0 < meilleur[1]:
        phrase = (
            f"Dans les crises rejouées, {ticker} a joué dans les deux sens : il a "
            f"coûté {_points(pire[1])} ({pire[0].scenario.name}), mais rapporté "
            f"{_points(meilleur[1])} ({meilleur[0].scenario.name})."
        )
    elif meilleur[1] <= 0:
        phrase = (
            f"Dans les crises rejouées, {ticker} a coûté au portefeuille à chaque "
            f"fois, de {_points(pire[1])} ({pire[0].scenario.name}) à "
            f"{_points(meilleur[1])} ({meilleur[0].scenario.name})."
        )
    else:
        phrase = (
            f"Dans les crises rejouées, {ticker} a rapporté au portefeuille à "
            f"chaque fois, de {_points(pire[1])} ({pire[0].scenario.name}) à "
            f"{_points(meilleur[1])} ({meilleur[0].scenario.name})."
        )

    if any(not resultat.coverage.is_complete for resultat, _ in historique):
        phrase += " Ces apports ne portent que sur la partie rejouée du portefeuille."
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
                    f"{_refus(seances, 'la part de chaque ligne dans les variations')} "
                    "Aucune n'est donc chiffrée ici."
                ),
                facts={"seances": seances, "lignes": len(vc.weights)},
                provenance=f"fenêtre d'estimation : {vc.window}",
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
            )
        ]

    mince = _mention_mince(seances)
    seuils_mince = (MIN_REGRESSION_SAMPLE,) if _echantillon_mince(seances) else ()

    ordre = sorted(vc.contributions, key=lambda t: vc.contributions[t], reverse=True)
    for rang, ticker in enumerate(ordre):
        part = vc.contributions[ticker]
        poids = vc.weights[ticker]
        ecart = part - poids
        reference = capital_share(ticker, poids)

        tete = (
            f"{ticker} représente {reference.displayed} de la valeur du portefeuille "
            f"et {typography.percent(part, 1)} de ses variations"
        )
        if part < 0:
            phrases = [
                f"{tete} : {vc.window.period_label}, ses mouvements ont en moyenne "
                "compensé ceux des autres lignes."
            ]
        elif math.isclose(part, poids, abs_tol=5e-4):
            phrases = [f"{tete}, soit la même part."]
        elif ecart > 0:
            phrases = [f"{tete}, soit {_points(ecart)} de plus."]
        else:
            phrases = [f"{tete}, soit {_points(ecart)} de moins."]

        if rang == 0 and len(ordre) > 1:
            # Propriété générale, dite une fois, sur la ligne qui pèse le plus.
            phrases.append(
                "Plus une ligne pèse dans les variations, plus elle pèse sur le "
                "résultat, à la baisse comme à la hausse."
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
                thresholds=(reference, *seuils_mince),
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
    periode = _majuscule(report.matrices.window.period_label)
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
                    f"{_refus(seances, 'une corrélation')} Aucune paire n'est donc "
                    "décrite ici."
                ),
                facts={"seances": seances, "correlation_max": None},
                provenance=provenance,
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
            )
        ]

    tickers = list(correlation.columns)
    mince = _mention_mince(seances)
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
                    f"{periode}, {a} et {b} ont largement évolué ensemble "
                    f"(corrélation de {typography.number(rho, 2)}) : à elles deux, "
                    "elles diversifient moins que leur nombre ne le laisse "
                    f"penser.{mince}"
                ),
                facts={"correlation": rho, "seances": seances},
                provenance=provenance,
                thresholds=(threshold, *seuils_mince),
            )
            for rho, a, b in fortes
        ]

    rho, a, b = paires[0]
    reference = most_correlated_pair(a, b, rho)
    return [
        Observation(
            rule=RuleId.APPARENT_DIVERSIFICATION,
            subject="portefeuille",
            statement=(
                f"{periode}, aucune paire de lignes n'a évolué étroitement "
                "ensemble : aucune corrélation n'atteint "
                f"{threshold.displayed}. La paire la plus liée est {a}–{b}, à "
                f"{reference.displayed}.{mince}"
            ),
            facts={"correlation_max": rho, "paire": f"{a}–{b}", "seances": seances},
            provenance=provenance,
            thresholds=(threshold, reference, *seuils_mince),
        )
    ]


# ----------------------------------------------- 4. Part systématique --


def _celles_du_marche(benchmark: str) -> str:
    """« celles du marché, le S&P 500 » ; un indice sans nom connu, par son
    ticker : « celles de QQQ »."""
    nom = benchmark_name(benchmark)
    return f"celles de {benchmark}" if nom is None else f"celles du marché, {nom.label}"


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
                    f"{_refus(seances, 'la part des variations qui suit le marché')} "
                    "Aucune part n'est donc avancée ici."
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
                f"{_majuscule(beta.window.period_label)}, "
                f"{typography.percent(r2, 0)} des variations de votre portefeuille "
                f"ont suivi {_celles_du_marche(beta.benchmark)}. Cette part ne se "
                "dilue pas en ajoutant d'autres actions américaines. Les "
                f"{typography.percent(1.0 - r2, 0)} restants sont propres à vos "
                "lignes : c'est sur eux seuls que la diversification "
                f"agit.{_mention_mince(seances)}"
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


def _parts(c: RegimeComparison, calme_commun: bool) -> str:
    """« 98 % », ou « de 45 % à 98 % » quand le temps ordinaire diffère d'une
    crise à l'autre."""
    crise = typography.percent(c.crisis_beta.r_squared, 0)
    if calme_commun:
        return crise
    return f"de {typography.percent(c.calm_beta.r_squared, 0)} à {crise}"


def _evolution(
    valides: Sequence[RegimeComparison],
    suffisantes: Sequence[RegimeComparison],
    calme_commun: bool,
) -> str:
    """La première phrase : la part qui suit le marché en temps ordinaire, puis
    dans chaque crise estimée sur assez de jours.

    Les crises trop minces n'y figurent pas : elles sont citées à part, avec
    leur chiffre et la raison pour laquelle rien n'en est conclu.
    """
    sujet = "la part des variations qui suit le marché"
    if calme_commun:
        reference = valides[0]
        calme = (
            f"{typography.percent(reference.calm_beta.r_squared, 0)} "
            f"{reference.calm_period_label}"
        )
        if not suffisantes:
            return f"{_majuscule(sujet)} est de {calme}."
        etapes = [
            f"à {typography.percent(c.crisis_beta.r_squared, 0)} pendant "
            f"{_crise(c.scenario)}"
            for c in suffisantes
        ]
        return f"{_majuscule(sujet)} passe de {calme} {_enumeration(etapes)}."

    # Couverture différente d'une crise à l'autre : le temps ordinaire est
    # mesuré sur les lignes rejouées de chacune, et sa part change avec elles.
    if not suffisantes:
        return (
            f"{_majuscule(sujet)} se mesure ici sur les lignes rejouées de chaque "
            "crise."
        )
    etapes = []
    periode_precedente = None
    for c in suffisantes:
        periode = c.calm_period_label
        dite = "" if periode == periode_precedente else f" {periode}"
        etapes.append(
            f"de {typography.percent(c.calm_beta.r_squared, 0)}{dite} à "
            f"{typography.percent(c.crisis_beta.r_squared, 0)} pendant "
            f"{_crise(c.scenario)}"
        )
        periode_precedente = periode
    return (
        f"Mesurée sur les lignes rejouées de chaque crise, {sujet} passe "
        f"{_enumeration(etapes)}."
    )


def _conclusion_des_crises(
    suffisantes: Sequence[RegimeComparison],
    minces: Sequence[RegimeComparison],
    calme_commun: bool,
) -> list[str]:
    """Ce que les crises rejouées permettent de conclure, et ce qu'elles ne
    permettent pas.

    Seules les crises estimées sur au moins MIN_REGRESSION_SAMPLE séances
    entrent dans la conclusion. Une crise trop mince ne peut pas être comptée
    comme une preuve : elle est citée à part, avec son chiffre, le sens où elle
    va et le nombre de jours qui la fonde. Sans aucune estimation suffisante,
    aucune conclusion générale n'est tirée.
    """
    phrases: list[str] = []
    total = len(suffisantes)
    hausses = sum(1 for c in suffisantes if _hausse(c))
    ces = "cette crise" if total == 1 else f"ces {typography.cardinal(total)} crises"

    if total == 0:
        pass
    elif hausses == total:
        phrases.append(
            f"Dans {ces}, la diversification entre vos lignes s'est affaiblie au "
            "moment où elle aurait servi."
        )
    elif hausses == 0:
        phrases.append(
            "Elle n'augmente pas dans cette crise."
            if total == 1
            else f"Elle n'augmente dans aucune de {ces}."
        )
    else:
        phrases.append(f"Elle augmente dans {_une(hausses)} de {ces}.")

    unanime = total > 0 and hausses in (0, total)
    for c in minces:
        trop_peu = (
            f"mais sur {_jours(c.crisis_beta.observations)} seulement : trop peu "
            "pour conclure."
        )
        if unanime:
            comme_les_autres = _hausse(c) == (hausses == total)
            sens = "dans le même sens" if comme_les_autres else "en sens contraire"
            phrases.append(
                f"{_crise(c.scenario, en_tete=True)} va {sens} "
                f"({_parts(c, calme_commun)}), {trop_peu}"
            )
        else:
            verbe = "augmente" if _hausse(c) else "n'augmente pas"
            phrases.append(
                f"Pendant {_crise(c.scenario)}, elle {verbe} "
                f"({_parts(c, calme_commun)}), {trop_peu}"
            )
    return phrases


def crisis_degradation(regimes: Sequence[RegimeComparison]) -> list[Observation]:
    """La part des variations qui suit le marché, en temps ordinaire face à
    chaque crise rejouée."""
    valides = [c for c in regimes if c.unavailable_reason is None]
    if not valides:
        return []

    calmes = [c.calm_beta.r_squared for c in valides]
    calme_commun = all(math.isclose(r2, calmes[0], abs_tol=1e-12) for r2 in calmes)

    suffisantes = [c for c in valides if not c.crisis_beta.sample_too_thin]
    minces = [c for c in valides if c.crisis_beta.sample_too_thin]
    phrases = [_evolution(valides, suffisantes, calme_commun)]
    phrases.extend(_conclusion_des_crises(suffisantes, minces, calme_commun))

    exclus = [c for c in regimes if c.unavailable_reason is not None]
    if exclus:
        phrases.append(
            "Pas de comparaison possible pour "
            + _enumeration([_crise(c.scenario) for c in exclus])
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


def _absentes(resultat: ScenarioResult) -> str:
    """« A et B n'étaient pas encore cotés » : ce qui a écarté les lignes.

    « Pas encore » seulement quand toutes sont entrées en cotation après le
    début de la crise (`first_available`) ; une ligne sans cours, ou plus
    cotée avant la fin, n'était pas cotée pendant TOUTE la crise.
    """
    exclues = resultat.coverage.excluded
    noms = _enumeration([e.ticker for e in exclues])
    plusieurs = len(exclues) > 1
    etat = "n'étaient pas" if plusieurs else "n'était pas"
    cote = "cotés" if plusieurs else "coté"
    tardives = all(
        e.first_available is not None and e.first_available > resultat.scenario.start
        for e in exclues
    )
    if tardives:
        return f"{noms} {etat} encore {cote}"
    return f"{noms} {etat} {cote} pendant toute la crise"


def scenario_coverage(
    scenarios: Sequence[ScenarioResult], threshold: Threshold = MIN_SCENARIO_COVERAGE
) -> list[Observation]:
    """Scénarios qui ne couvrent pas tout le portefeuille.

    Sous le seuil de couverture, aucun chiffre principal n'est produit : la
    partie rejouée est minoritaire dans la valeur et ne peut pas tenir lieu du
    portefeuille. Au-dessus, le chiffre est donné avec sa portée. La phrase ne
    dit pas dans quel sens l'ensemble aurait différé : le moteur ne le mesure
    pas.
    """
    observations = []
    for resultat in scenarios:
        couverture = resultat.coverage
        if couverture.is_complete:
            continue

        crise = _crise(resultat.scenario, en_tete=True)
        portee = (
            f"{crise} ne se rejoue que sur "
            f"{typography.percent(couverture.value_share, 0)} de votre portefeuille "
            f"({_lignes(couverture.covered_count)} sur {couverture.total_count})"
        )
        faits: dict[str, float | int | str | None] = {
            "part_couverte": couverture.value_share,
            "lignes_couvertes": couverture.covered_count,
            "lignes": couverture.total_count,
        }

        if resultat.end_to_end_return is None:
            # Deux causes, comme dans le moteur : aucune ligne couverte, ou des
            # lignes couvertes sans deux jours de bourse en commun.
            cause = (
                "aucune de vos lignes n'était cotée pendant toute cette crise"
                if couverture.covered_count == 0
                else "les lignes cotées pendant toute cette crise ont moins de deux "
                "jours de bourse en commun"
            )
            texte = f"Impossible de rejouer {_crise(resultat.scenario)} : {cause}."
        elif couverture.value_share < threshold.value:
            texte = (
                f"{portee} : moins de {threshold.displayed}, trop peu pour donner un "
                "chiffre pour l'ensemble."
            )
        else:
            ensemble = (
                "la perte de l'ensemble a pu être différente"
                if resultat.end_to_end_return < 0
                else "le résultat de l'ensemble a pu être différent"
            )
            texte = (
                f"{portee} : {_absentes(resultat)}. Son résultat "
                f"({typography.percent(resultat.end_to_end_return, 1)}) ne porte que "
                "sur cette partie. Les lignes absentes n'ont pas été rejouées : "
                f"{ensemble}."
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
