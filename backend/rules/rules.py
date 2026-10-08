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

═══ LES RÈGLES DÉCIDENT, `textes/{fr,en}/regles.py` RÉDIGE ═══

Quelle variante dire, sur quel signe, quelles crises sont assez longues pour
conclure, lesquelles vont dans le même sens : c'est décidé ici, une fois. Les
phrases sont écrites par le module de la langue demandée (chantier 7D), qui
reçoit ces décisions et les faits. Une observation porte sa langue :
l'énoncé, le sujet, la provenance, le libellé de la règle et les lignes de ses
seuils sont dans celle-là.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from backend.langue import Langue
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
from backend.textes import textes

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
    (`rule`) ; la valeur est le libellé français que la page affiche au-dessus
    de l'observation (`rule_label`), en mots courants. `textes/fr/regles.py`
    le lit ici ; l'anglais est rédigé par `textes/en/regles.py`."""

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
    main le dit explicitement. `langue` est celle de ses phrases.
    """

    rule: RuleId
    subject: str
    statement: str
    facts: Mapping[str, float | int | str | None]
    provenance: str
    thresholds: tuple[Threshold, ...] = ()
    langue: Langue = "fr"

    @property
    def uses_chosen_threshold(self) -> bool:
        return any(seuil.chosen for seuil in self.thresholds)

    @property
    def rule_label(self) -> str:
        """Le libellé de la règle, dans la langue de l'observation."""
        return textes(self.langue).regles.libelle(self.rule)

    def render(self) -> str:
        return textes(self.langue).regles.rendu(
            self.rule_label,
            self.subject,
            self.statement,
            [(seuil.etiquette(self.langue), seuil.ligne(self.langue)) for seuil in self.thresholds],
            self.provenance,
        )


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


def _phrases(*phrases: str) -> str:
    """Des phrases à la suite ; une phrase vide (une mention qui ne
    s'applique pas) n'en est pas une."""
    return " ".join(phrase for phrase in phrases if phrase)


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


def _mention_mince(seances: int, langue: Langue) -> str:
    """Phrase ajoutée à une estimation fragile, vide sinon."""
    if not _echantillon_mince(seances):
        return ""
    return textes(langue).regles.mention_mince(
        seances, MIN_REGRESSION_SAMPLE.affiche(langue)
    )


def _refus(seances: int, mesure: str, langue: Langue) -> str:
    """Ce qu'une règle écrit au lieu de chiffrer, sous trois séances.

    La raison algébrique — une seule direction après centrage — est la
    rationale du seuil `MIN_ESTIMABLE_SAMPLE`, publiée avec lui. La phrase dit
    au lecteur ce qu'il lui faut : le calcul n'a pas de sens, et combien de
    jours il faudrait.
    """
    return textes(langue).regles.refus(
        seances, mesure, MIN_ESTIMABLE_SAMPLE.affiche(langue)
    )


# ------------------------------------------- 1. Concentration effective --


def effective_concentration(report: RiskReport, *, langue: Langue = "fr") -> Observation:
    """« Vos N lignes pèsent comme M lignes de même montant », puis ce qu'elles
    font bouger : en capital ET en risque. Aucun seuil.

    La version en capital (`1/Σwᵢ²`) seule est la plus flatteuse des deux quand
    le risque se concentre davantage que la valeur : un portefeuille équilibré en
    montants peut porter l'essentiel de sa variance sur quelques lignes volatiles
    et corrélées. L'écart entre les deux nombres est l'observation la plus utile
    de la règle — le risque ne se répartit pas comme le capital.
    """
    t = textes(langue).regles
    c = report.concentration
    vc = report.variance_contributions
    en_capital = c.effective_positions
    seances = vc.window.observations
    provenance = t.provenance_concentration(c.as_of, vc.window.ecrite(langue))

    if _non_estimable(seances):
        # La moitié EN CAPITAL reste dite : c'est une mesure ponctuelle, sans
        # fenêtre d'estimation, que la brièveté de l'historique ne touche pas.
        # Seule la moitié en risque disparaît, et elle dit pourquoi.
        capital = (
            t.LIGNE_UNIQUE_NON_CHIFFREE
            if c.n_positions == 1
            else t.capital_seul(c.n_positions, en_capital)
        )
        return Observation(
            rule=RuleId.EFFECTIVE_CONCENTRATION,
            subject=t.PORTEFEUILLE,
            statement=_phrases(capital, _refus(seances, "calcul", langue)),
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
            langue=langue,
        )

    en_risque = vc.effective_positions

    if c.n_positions == 1:
        texte = t.LIGNE_UNIQUE
    else:
        # L'écart se lit sur les nombres AFFICHÉS : deux lignes effectives qui
        # s'écrivent pareil se répartissent pareil pour le lecteur.
        ecart = round(en_risque, 1) - round(en_capital, 1)
        if ecart < 0:
            repartition = "plus_concentre"
        elif ecart > 0:
            repartition = "mieux_reparti"
        else:
            repartition = "pareil"
        periode = vc.window.periode(langue)
        texte = _phrases(
            t.concentration(c.n_positions, en_capital, en_risque, repartition, periode),
            t.montants_egaux(c.n_positions),
            t.SURESTIMATION if ecart < 0 else "",
            (
                t.contribution_negative(en_risque, periode)
                if vc.has_negative_contribution
                else ""
            ),
            _mention_mince(seances, langue),
        )

    return Observation(
        rule=RuleId.EFFECTIVE_CONCENTRATION,
        subject=t.PORTEFEUILLE,
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
        langue=langue,
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


def _record_sentence(
    ticker: str, historique: list[tuple[ScenarioResult, float]], langue: Langue
) -> str:
    """Ce que la ligne a coûté ou rapporté au portefeuille dans les crises
    rejouées : dans les deux sens, à chaque fois, ou dans la seule crise."""
    t = textes(langue).regles
    pire = min(historique, key=lambda element: element[1])
    meilleur = max(historique, key=lambda element: element[1])

    if len(historique) == 1:
        resultat, apport = historique[0]
        phrase = t.parcours_d_une_crise(ticker, resultat.scenario.nom(langue), apport)
    else:
        if pire[1] < 0 < meilleur[1]:
            sens = "deux_sens"
        elif meilleur[1] <= 0:
            sens = "cout"
        else:
            sens = "gain"
        phrase = t.parcours_des_crises(
            ticker,
            sens,
            (pire[0].scenario.nom(langue), pire[1]),
            (meilleur[0].scenario.nom(langue), meilleur[1]),
        )

    if any(not resultat.coverage.is_complete for resultat, _ in historique):
        phrase = _phrases(phrase, t.APPORTS_PARTIELS)
    return phrase


def variance_contribution(
    report: RiskReport,
    scenarios: Sequence[ScenarioResult] = (),
    *,
    langue: Langue = "fr",
) -> list[Observation]:
    """Part de chaque ligne dans la variance, face à sa part du capital.

    Présentée dans les deux sens : ce qu'une ligne pèse dans le risque, et —
    quand les scénarios sont fournis — ce qu'elle a réellement apporté ou coûté
    pendant les crises rejouées, pertes comme gains.
    """
    t = textes(langue).regles
    vc = report.variance_contributions
    seances = vc.window.observations
    provenance = t.provenance_fenetre(vc.window.ecrite(langue))
    parcours = _scenario_record(scenarios)
    observations: list[Observation] = []

    if _non_estimable(seances):
        # Une seule observation, et aucun chiffre. Une décomposition par ligne
        # avec des parts nulles laisserait croire à des parts mesurées à zéro.
        return [
            Observation(
                rule=RuleId.VARIANCE_CONTRIBUTION,
                subject=t.PORTEFEUILLE,
                statement=_phrases(_refus(seances, "parts", langue), t.AUCUNE_PART_CHIFFREE),
                facts={"seances": seances, "lignes": len(vc.weights)},
                provenance=provenance,
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
                langue=langue,
            )
        ]

    mince = _mention_mince(seances, langue)
    seuils_mince = (MIN_REGRESSION_SAMPLE,) if _echantillon_mince(seances) else ()
    periode = vc.window.periode(langue)

    ordre = sorted(vc.contributions, key=lambda nom: vc.contributions[nom], reverse=True)
    for rang, ticker in enumerate(ordre):
        part = vc.contributions[ticker]
        poids = vc.weights[ticker]
        ecart = part - poids
        reference = capital_share(ticker, poids)

        if part < 0:
            comparaison = "compense"
        elif math.isclose(part, poids, abs_tol=5e-4):
            comparaison = "egale"
        elif ecart > 0:
            comparaison = "plus"
        else:
            comparaison = "moins"

        historique = parcours.get(ticker, [])
        texte = _phrases(
            t.contribution(
                ticker, reference.affiche(langue), part, ecart, comparaison, periode
            ),
            # Propriété générale, dite une fois, sur la ligne qui pèse le plus.
            t.INFLUENCE if rang == 0 and len(ordre) > 1 else "",
            mince,
            _record_sentence(ticker, historique, langue) if historique else "",
        )

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
                statement=texte,
                facts=faits,
                provenance=provenance,
                thresholds=(reference, *seuils_mince),
                langue=langue,
            )
        )
    return observations


# ----------------------------------------- 3. Diversification apparente --


def apparent_diversification(
    report: RiskReport,
    threshold: Threshold = STRONG_CORRELATION,
    *,
    langue: Langue = "fr",
) -> list[Observation]:
    """Paires de lignes qui ont largement évolué ensemble sur la fenêtre."""
    t = textes(langue).regles
    correlation = report.matrices.correlation
    seances = report.matrices.window.observations
    periode = report.matrices.window.periode(langue)
    provenance = t.provenance_fenetre(report.matrices.window.ecrite(langue))

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
                subject=t.PORTEFEUILLE,
                statement=_phrases(
                    _refus(seances, "correlation", langue), t.AUCUNE_PAIRE_DECRITE
                ),
                facts={"seances": seances, "correlation_max": None},
                provenance=provenance,
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
                langue=langue,
            )
        ]

    tickers = list(correlation.columns)
    mince = _mention_mince(seances, langue)
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
                statement=_phrases(t.paire_forte(periode, a, b, rho), mince),
                facts={"correlation": rho, "seances": seances},
                provenance=provenance,
                thresholds=(threshold, *seuils_mince),
                langue=langue,
            )
            for rho, a, b in fortes
        ]

    rho, a, b = paires[0]
    reference = most_correlated_pair(a, b, rho)
    return [
        Observation(
            rule=RuleId.APPARENT_DIVERSIFICATION,
            subject=t.PORTEFEUILLE,
            statement=_phrases(
                t.aucune_paire_forte(
                    periode, threshold.affiche(langue), a, b, reference.affiche(langue)
                ),
                mince,
            ),
            facts={"correlation_max": rho, "paire": f"{a}–{b}", "seances": seances},
            provenance=provenance,
            thresholds=(threshold, reference, *seuils_mince),
            langue=langue,
        )
    ]


# ----------------------------------------------- 4. Part systématique --


def systematic_share(report: RiskReport, *, langue: Langue = "fr") -> list[Observation]:
    """Part de la variance expliquée par le marché. Aucun seuil."""
    beta = report.beta
    if beta is None:
        return []

    t = textes(langue).regles
    r2 = beta.r_squared
    seances = beta.window.observations
    provenance = t.provenance_fenetre(beta.window.ecrite(langue))

    if _non_estimable(seances):
        return [
            Observation(
                rule=RuleId.SYSTEMATIC_SHARE,
                subject=t.PORTEFEUILLE,
                statement=_phrases(
                    _refus(seances, "part_du_marche", langue), t.AUCUNE_PART_AVANCEE
                ),
                facts={
                    "r2": None,
                    "part_propre": None,
                    "benchmark": beta.benchmark,
                    "seances": seances,
                },
                provenance=provenance,
                thresholds=(MIN_ESTIMABLE_SAMPLE,),
                langue=langue,
            )
        ]

    # Un indice sans nom connu se dit par son ticker.
    nom = benchmark_name(beta.benchmark, langue)
    return [
        Observation(
            rule=RuleId.SYSTEMATIC_SHARE,
            subject=t.PORTEFEUILLE,
            statement=_phrases(
                t.part_systematique(
                    beta.window.periode(langue),
                    r2,
                    1.0 - r2,
                    beta.benchmark,
                    None if nom is None else nom.label,
                ),
                _mention_mince(seances, langue),
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
            langue=langue,
        )
    ]


# ------------------------------------------------ 5. Dégradation en crise --


def _hausse(c: RegimeComparison) -> bool:
    return c.systematic_share_change > 0


def _evolution(
    valides: Sequence[RegimeComparison],
    suffisantes: Sequence[RegimeComparison],
    calme_commun: bool,
    langue: Langue,
) -> str:
    """La première phrase : la part qui suit le marché en temps ordinaire, puis
    dans chaque crise estimée sur assez de jours.

    Les crises trop minces n'y figurent pas : elles sont citées à part, avec
    leur chiffre et la raison pour laquelle rien n'en est conclu.
    """
    t = textes(langue).regles
    if calme_commun:
        reference = valides[0]
        calme = reference.calm_beta.r_squared
        periode = reference.periode_calme(langue)
        if not suffisantes:
            return t.evolution_sans_crise(calme, periode)
        return t.evolution(
            calme,
            periode,
            [(c.crisis_beta.r_squared, c.scenario.avec_article(langue)) for c in suffisantes],
        )

    # Couverture différente d'une crise à l'autre : le temps ordinaire est
    # mesuré sur les lignes rejouées de chacune, et sa part change avec elles.
    # Sa période n'est redite que quand elle change d'une crise à la suivante.
    if not suffisantes:
        return t.MESURE_PAR_CRISE
    etapes = []
    periode_precedente = None
    for c in suffisantes:
        periode = c.periode_calme(langue)
        etapes.append(
            (
                c.calm_beta.r_squared,
                None if periode == periode_precedente else periode,
                c.crisis_beta.r_squared,
                c.scenario.avec_article(langue),
            )
        )
        periode_precedente = periode
    return t.evolution_par_crise(etapes)


def _conclusion_des_crises(
    suffisantes: Sequence[RegimeComparison],
    minces: Sequence[RegimeComparison],
    calme_commun: bool,
    langue: Langue,
) -> list[str]:
    """Ce que les crises rejouées permettent de conclure, et ce qu'elles ne
    permettent pas.

    Seules les crises estimées sur au moins MIN_REGRESSION_SAMPLE séances
    entrent dans la conclusion. Une crise trop mince ne peut pas être comptée
    comme une preuve : elle est citée à part, avec son chiffre, le sens où elle
    va et le nombre de jours qui la fonde. Sans aucune estimation suffisante,
    aucune conclusion générale n'est tirée.
    """
    t = textes(langue).regles
    phrases: list[str] = []
    total = len(suffisantes)
    hausses = sum(1 for c in suffisantes if _hausse(c))

    if total == 0:
        pass
    elif hausses == total:
        phrases.append(t.affaiblie(total))
    elif hausses == 0:
        phrases.append(t.aucune_hausse(total))
    else:
        phrases.append(t.hausse_partielle(hausses, total))

    unanime = total > 0 and hausses in (0, total)
    for c in minces:
        # La part en temps ordinaire n'est redite que quand elle diffère d'une
        # crise à l'autre : « de 45 % à 98 % ».
        calme = None if calme_commun else c.calm_beta.r_squared
        crise = c.scenario.avec_article(langue)
        if unanime:
            # « Même sens » n'a de référent que si les crises suffisantes vont
            # toutes dans le même.
            comme_les_autres = _hausse(c) == (hausses == total)
            phrases.append(
                t.crise_mince_comme_les_autres(
                    crise, comme_les_autres, c.crisis_beta.r_squared, calme,
                    c.crisis_beta.observations,
                )
            )
        else:
            phrases.append(
                t.crise_mince(
                    crise, _hausse(c), c.crisis_beta.r_squared, calme,
                    c.crisis_beta.observations,
                )
            )
    return phrases


def crisis_degradation(
    regimes: Sequence[RegimeComparison], *, langue: Langue = "fr"
) -> list[Observation]:
    """La part des variations qui suit le marché, en temps ordinaire face à
    chaque crise rejouée."""
    valides = [c for c in regimes if c.unavailable_reason is None]
    if not valides:
        return []

    t = textes(langue).regles
    calmes = [c.calm_beta.r_squared for c in valides]
    calme_commun = all(math.isclose(r2, calmes[0], abs_tol=1e-12) for r2 in calmes)

    suffisantes = [c for c in valides if not c.crisis_beta.sample_too_thin]
    minces = [c for c in valides if c.crisis_beta.sample_too_thin]
    phrases = [_evolution(valides, suffisantes, calme_commun, langue)]
    phrases.extend(_conclusion_des_crises(suffisantes, minces, calme_commun, langue))

    exclus = [c for c in regimes if c.unavailable_reason is not None]
    if exclus:
        phrases.append(t.sans_comparaison([c.scenario.avec_article(langue) for c in exclus]))

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
            subject=t.PORTEFEUILLE,
            statement=" ".join(phrases),
            facts=faits,
            provenance=t.provenance_regimes(
                calme.observations,
                calme.start,
                calme.end,
                [(c.scenario.nom(langue), c.crisis_beta.observations) for c in valides],
            ),
            thresholds=(MIN_REGRESSION_SAMPLE,) if minces else (),
            langue=langue,
        )
    ]


# ------------------------------------------ 6. Couverture d'un scénario --


def _tardives(resultat: ScenarioResult) -> bool:
    """Les lignes écartées sont-elles toutes entrées en cotation après le
    début de la crise (`first_available`) ? Une ligne sans cours, ou plus
    cotée avant la fin, n'était pas cotée pendant TOUTE la crise : « pas
    encore » serait faux."""
    return all(
        e.first_available is not None and e.first_available > resultat.scenario.start
        for e in resultat.coverage.excluded
    )


def scenario_coverage(
    scenarios: Sequence[ScenarioResult],
    threshold: Threshold = MIN_SCENARIO_COVERAGE,
    *,
    langue: Langue = "fr",
) -> list[Observation]:
    """Scénarios qui ne couvrent pas tout le portefeuille.

    Sous le seuil de couverture, aucun chiffre principal n'est produit : la
    partie rejouée est minoritaire dans la valeur et ne peut pas tenir lieu du
    portefeuille. Au-dessus, le chiffre est donné avec sa portée. La phrase ne
    dit pas dans quel sens l'ensemble aurait différé : le moteur ne le mesure
    pas.
    """
    t = textes(langue).regles
    observations = []
    for resultat in scenarios:
        couverture = resultat.coverage
        if couverture.is_complete:
            continue

        crise = resultat.scenario.avec_article(langue)
        portee = t.crise_rejouee_en_partie(
            crise, couverture.value_share, couverture.covered_count, couverture.total_count
        )
        faits: dict[str, float | int | str | None] = {
            "part_couverte": couverture.value_share,
            "lignes_couvertes": couverture.covered_count,
            "lignes": couverture.total_count,
        }

        if resultat.end_to_end_return is None:
            # Deux causes, comme dans le moteur : aucune ligne couverte, ou des
            # lignes couvertes sans deux jours de bourse en commun.
            texte = t.impossible(crise, couverture.covered_count == 0)
        elif couverture.value_share < threshold.value:
            texte = t.sous_le_seuil(portee, threshold.affiche(langue))
        else:
            texte = t.couverture_suffisante(
                portee,
                t.lignes_absentes(
                    [e.ticker for e in couverture.excluded], _tardives(resultat)
                ),
                resultat.end_to_end_return,
                resultat.end_to_end_return < 0,
            )
            faits["resultat_partie_couverte"] = resultat.end_to_end_return

        observations.append(
            Observation(
                rule=RuleId.SCENARIO_COVERAGE,
                # Le nom, pas la clé du catalogue : la page affiche le sujet
                # tel quel, à côté du libellé de la règle.
                subject=resultat.scenario.nom(langue),
                statement=texte,
                facts=faits,
                provenance=t.provenance_scenario(
                    resultat.scenario.start, resultat.scenario.end
                ),
                thresholds=(threshold,),
                langue=langue,
            )
        )
    return observations


# ------------------------------------------------------------ Évaluation --


def evaluate(
    report: RiskReport,
    scenarios: Sequence[ScenarioResult] = (),
    regimes: Sequence[RegimeComparison] = (),
    *,
    langue: Langue = "fr",
) -> RulesReport:
    """Applique les six règles aux résultats déjà produits. Fonction pure.

    `langue` choisit la langue des observations et du texte d'acceptation qui
    borne le rapport.
    """
    observations = [
        effective_concentration(report, langue=langue),
        *variance_contribution(report, scenarios, langue=langue),
        *apparent_diversification(report, langue=langue),
        *systematic_share(report, langue=langue),
        *crisis_degradation(regimes, langue=langue),
        *scenario_coverage(scenarios, langue=langue),
    ]
    return RulesReport(
        portfolio_id=report.portfolio_id,
        as_of=report.as_of,
        observations=tuple(observations),
        disclaimer=acceptance_text(report.window.requested, langue=langue),
    )


def evaluate_portfolio(
    conn: sqlite3.Connection,
    portfolio_id: int,
    *,
    window: int = DEFAULT_WINDOW,
    langue: Langue = "fr",
) -> RulesReport:
    """Rassemble les sorties des Phases 4 et 5, puis applique les règles."""
    return evaluate(
        analyse_portfolio(conn, portfolio_id, window=window, langue=langue),
        run_all_scenarios(conn, portfolio_id, langue=langue),
        compare_all_regimes(conn, portfolio_id, window=window, langue=langue),
        langue=langue,
    )
