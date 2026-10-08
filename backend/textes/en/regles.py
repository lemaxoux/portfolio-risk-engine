"""Les observations du moteur de règles, en anglais américain (chantier 7D).

Les mêmes noms et les mêmes signatures que `fr/regles.py`, traduits avec le
glossaire validé (`anglais-proposition.md`, §c, hors dépôt) : « holding »
pour une ligne, « fluctuations » pour les variations, « trading day » dans
les phrases, « session » dans les provenances, « Small-sample estimate » pour
une estimation mince. Aucune espace avant « : », virgule de série.

LE TEMPS DU PASSÉ REJOUÉ (question 9). Le prétérit ou le présent ne
s'écrivent que dans une phrase qui porte elle-même son cadre de rejeu :
« In the replayed crises, … », « Over the past two years, … ». Une phrase
sans ce cadre dirait « would have ». Là où le français chiffre la fenêtre
sans la nommer (« font bouger le portefeuille comme 4,4 »), l'anglais la
nomme, d'où la période que reçoivent certaines fonctions ; une phrase qui en
suit une autre dans la même observation dit « Over the same period ». Les
phrases générales (« The more a holding weighs… ») et ce que le moteur ne
chiffre pas restent au présent.

Le verbe « diversify » ne s'écrit sous aucune forme : « they provide less
diversification ».
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import Enum

from backend import typography

from .moteur import ensemble_non_rejoue, jours_de_bourse

# ═══════════════════════════════════════════════════ Libellés et rendu ══

_LIBELLES = {
    "EFFECTIVE_CONCENTRATION": "How many holdings, really",
    "VARIANCE_CONTRIBUTION": "Weight in the fluctuations",
    "APPARENT_DIVERSIFICATION": "Holdings that move together",
    "SYSTEMATIC_SHARE": "Share that follows the market",
    "CRISIS_DEGRADATION": "The portfolio in a crisis",
    "SCENARIO_COVERAGE": "Crisis partly replayed",
}


def libelle(regle: Enum) -> str:
    """Le libellé d'une règle, par le nom de son membre de `RuleId`."""
    return _LIBELLES[regle.name]


PORTEFEUILLE = "portfolio"

AUCUN_SEUIL = "No threshold: the measure speaks for itself."


def rendu(
    titre: str,
    sujet: str,
    enonce: str,
    seuils: Sequence[tuple[str, str]],
    provenance: str,
) -> str:
    lignes = [f"[{titre}: {sujet}] {enonce}"]
    if seuils:
        lignes += [f"  {etiquette}: {ligne}" for etiquette, ligne in seuils]
    else:
        lignes.append(f"  {AUCUN_SEUIL}")
    lignes.append(f"  Provenance: {provenance}")
    return "\n".join(lignes)


# ═══════════════════════════════════════════════════════ Mise en forme ══


def _points(ecart: float, decimales: int = 1) -> str:
    """« 9.8 points » ; le singulier suit l'écriture : « 1 point » seulement."""
    valeur = abs(ecart) * 100.0
    return typography.counted(
        valeur,
        "point",
        affiche=typography.number(valeur, decimales, langue="en"),
        langue="en",
    )


def _enumeration(elements: Sequence[str]) -> str:
    """« A and B », « A, B, and C » : la virgule de série."""
    if len(elements) <= 1:
        return "".join(elements)
    if len(elements) == 2:
        return f"{elements[0]} and {elements[1]}"
    return f"{', '.join(elements[:-1])}, and {elements[-1]}"


def _lignes_effectives(valeur: float) -> str:
    """« 5.7 equal-sized holdings » ; le pluriel suit l'écriture."""
    return typography.counted(
        valeur,
        "equal-sized holding",
        affiche=typography.number(valeur, 1, langue="en"),
        langue="en",
    )


def _majuscule(texte: str) -> str:
    return texte[:1].upper() + texte[1:]


def _une(nombre: int) -> str:
    return typography.cardinal(nombre, langue="en")


def _ces_crises(total: int) -> str:
    if total == 1:
        return "this crisis"
    return f"these {typography.cardinal(total, langue='en')} crises"


# ═════════════════════════════════════════════ Taille de l'échantillon ══


def mention_mince(seances: int, minimum: str) -> str:
    return (
        f"Small-sample estimate: over {jours_de_bourse(seances)}, fewer than "
        f"the {minimum} required (threshold chosen by hand), a few extreme days "
        "are enough to produce this figure."
    )


_MESURES_REFUSEES = {
    "calcul": "this calculation",
    "parts": "the share of each holding in the fluctuations",
    "correlation": "a correlation",
    "part_du_marche": "the share of the fluctuations that follows the market",
}


def refus(seances: int, mesure: str, minimum: str) -> str:
    return (
        f"Over {jours_de_bourse(seances)}, {_MESURES_REFUSEES[mesure]} is "
        f"meaningless: it takes at least {minimum}."
    )


AUCUNE_PART_CHIFFREE = "None is therefore quantified here."

AUCUNE_PAIRE_DECRITE = "No pair is therefore described here."

AUCUNE_PART_AVANCEE = "No share is therefore put forward here."


# ═════════════════════════════════════════════ Provenance d'une règle ══


def provenance_concentration(valorisation: date, fenetre: str) -> str:
    return (
        f"capital: valuation as of {valorisation}; risk: estimation window "
        f"of {fenetre}"
    )


def provenance_fenetre(fenetre: str) -> str:
    return f"estimation window: {fenetre}"


# ═══════════════════════════════════════════ 1. Concentration effective ══

LIGNE_UNIQUE_NON_CHIFFREE = (
    "Your portfolio has a single holding: it carries the entire amount. How "
    "it moves the portfolio is not quantified."
)


def capital_seul(lignes: int, en_capital: float) -> str:
    return (
        f"Your {typography.lines(lignes, langue='en')} weigh like "
        f"{_lignes_effectives(en_capital)}; with equal amounts, they would "
        f"count as {lignes}. How they move the portfolio is not quantified."
    )


LIGNE_UNIQUE = (
    "Your portfolio has a single holding: it carries the entire amount and "
    "all the fluctuations."
)


def concentration(
    lignes: int, en_capital: float, en_risque: float, repartition: str, periode: str
) -> str:
    risque = typography.number(en_risque, 1, langue="en")
    suite = {
        "plus_concentre": (
            f"but over {periode} they moved the portfolio like only {risque}: "
            "the risk was more concentrated than the money"
        ),
        "mieux_reparti": (
            f"and over {periode} they moved the portfolio like {risque}: the "
            "risk was more evenly spread than the money"
        ),
        "pareil": (
            f"and over {periode} they moved the portfolio like {risque}: the "
            "risk was spread the same way as the money"
        ),
    }[repartition]
    return (
        f"Your {typography.lines(lignes, langue='en')} weigh like "
        f"{_lignes_effectives(en_capital)}, {suite}."
    )


def montants_egaux(lignes: int) -> str:
    return f"With equal amounts, they would count as {lignes}."


SURESTIMATION = (
    "Looking only at the amounts would therefore overstate the diversification."
)


def contribution_negative(en_risque: float, periode: str) -> str:
    return (
        f"Over {periode}, at least one holding moved against the others: the "
        f"figure of {typography.number(en_risque, 1, langue='en')} is only an "
        "approximation."
    )


# ══════════════════════════════════════════ 2. Contribution à la variance ══


def contribution(
    ticker: str,
    part_du_capital: str,
    part: float,
    ecart: float,
    comparaison: str,
    periode: str,
) -> str:
    tete = (
        f"{ticker} accounts for {part_du_capital} of the portfolio's value and, "
        f"over {periode}, for {typography.percent(part, 1, langue='en')} of its "
        "fluctuations"
    )
    suite = {
        "compense": (
            ": on average, its movements offset those of the other holdings."
        ),
        "egale": ", the same share.",
        "plus": f", {_points(ecart)} more.",
        "moins": f", {_points(ecart)} less.",
    }[comparaison]
    return tete + suite


INFLUENCE = (
    "The more a holding weighs in the fluctuations, the more it weighs on the "
    "result, on the way down as on the way up."
)


def parcours_d_une_crise(ticker: str, crise: str, apport: float) -> str:
    if apport == 0:
        effet = "neither cost nor added anything to the portfolio"
    elif apport < 0:
        effet = f"cost the portfolio {_points(apport)}"
    else:
        effet = f"added {_points(apport)} to the portfolio"
    return f"In the replayed crisis ({crise}), {ticker} {effet}."


def parcours_des_crises(
    ticker: str, sens: str, pire: tuple[str, float], meilleur: tuple[str, float]
) -> str:
    (nom_pire, apport_pire), (nom_meilleur, apport_meilleur) = pire, meilleur
    if sens == "deux_sens":
        return (
            f"In the replayed crises, {ticker} cut both ways: it cost "
            f"{_points(apport_pire)} ({nom_pire}), but added "
            f"{_points(apport_meilleur)} ({nom_meilleur})."
        )
    verbe = {"cout": "cost the portfolio", "gain": "added to the portfolio"}[sens]
    return (
        f"In the replayed crises, {ticker} {verbe} every time, from "
        f"{_points(apport_pire)} ({nom_pire}) to "
        f"{_points(apport_meilleur)} ({nom_meilleur})."
    )


APPORTS_PARTIELS = "These contributions cover only the replayed part of the portfolio."


# ═════════════════════════════════════════ 3. Diversification apparente ══


def paire_forte(periode: str, premier: str, second: str, correlation: float) -> str:
    return (
        f"Over {periode}, {premier} and {second} largely moved together "
        f"(correlation of {typography.number(correlation, 2, langue='en')}): "
        "between them, they provide less diversification than their number "
        "would lead one to think."
    )


def aucune_paire_forte(
    periode: str, seuil: str, premier: str, second: str, reference: str
) -> str:
    return (
        f"Over {periode}, no pair of holdings moved closely together: no "
        f"correlation reaches {seuil}. Over the same period, the most closely "
        f"linked pair is {premier}–{second}, at {reference}."
    )


# ═══════════════════════════════════════════════════ 4. Part systématique ══


def part_systematique(
    periode: str, part: float, propre: float, indice: str, nom_de_l_indice: str | None
) -> str:
    celles = (
        f"those of {indice}"
        if nom_de_l_indice is None
        else f"those of the market, {nom_de_l_indice}"
    )
    return (
        f"Over {periode}, {typography.percent(part, 0, langue='en')} of your "
        f"portfolio's fluctuations followed {celles}. This share is not "
        "diluted by adding other US stocks. Over the same period, the "
        f"remaining {typography.percent(propre, 0, langue='en')} were specific "
        "to your holdings: diversification acts on them alone."
    )


# ═══════════════════════════════════════════════ 5. Dégradation en crise ══

_SUJET = "the share of the fluctuations that follows the market"


def _pourcentage(valeur: float) -> str:
    return typography.percent(valeur, 0, langue="en")


def _parts(crise: float, calme: float | None) -> str:
    if calme is None:
        return _pourcentage(crise)
    return f"from {_pourcentage(calme)} to {_pourcentage(crise)}"


def evolution_sans_crise(calme: float, periode: str) -> str:
    return f"{_majuscule(_SUJET)} is {_pourcentage(calme)} over {periode}."


def evolution(calme: float, periode: str, etapes: Sequence[tuple[float, str]]) -> str:
    ecrites = [f"to {_pourcentage(crise)} during {nom}" for crise, nom in etapes]
    return (
        f"{_majuscule(_SUJET)} goes from {_pourcentage(calme)} over {periode} "
        f"{_enumeration(ecrites)}."
    )


MESURE_PAR_CRISE = (
    f"{_majuscule(_SUJET)} is measured here on the replayed holdings of each "
    "crisis."
)


def evolution_par_crise(etapes: Sequence[tuple[float, str | None, float, str]]) -> str:
    ecrites = [
        f"from {_pourcentage(calme)}{'' if periode is None else f' over {periode}'} "
        f"to {_pourcentage(crise)} during {nom}"
        for calme, periode, crise, nom in etapes
    ]
    return (
        f"Measured on the replayed holdings of each crisis, {_SUJET} goes "
        f"{_enumeration(ecrites)}."
    )


def affaiblie(total: int) -> str:
    return (
        f"In {_ces_crises(total)}, the diversification between your holdings "
        "weakened at the very moment it would have helped."
    )


def aucune_hausse(total: int) -> str:
    if total == 1:
        return "It does not increase in this crisis."
    return f"It increases in none of {_ces_crises(total)}."


def hausse_partielle(hausses: int, total: int) -> str:
    return f"It increases in {_une(hausses)} of {_ces_crises(total)}."


def _trop_peu(jours: int) -> str:
    return f"but over only {jours_de_bourse(jours)}: too few to draw a conclusion."


def crise_mince_comme_les_autres(
    crise: str, meme_sens: bool, part_de_crise: float, part_calme: float | None, jours: int
) -> str:
    sens = "the same way" if meme_sens else "the opposite way"
    return (
        f"{_majuscule(crise)} points {sens} ({_parts(part_de_crise, part_calme)}), "
        f"{_trop_peu(jours)}"
    )


def crise_mince(
    crise: str, hausse: bool, part_de_crise: float, part_calme: float | None, jours: int
) -> str:
    verbe = "increases" if hausse else "does not increase"
    return (
        f"During {crise}, it {verbe} ({_parts(part_de_crise, part_calme)}), "
        f"{_trop_peu(jours)}"
    )


def sans_comparaison(crises: Sequence[str]) -> str:
    return f"No comparison possible for {_enumeration(crises)}."


def provenance_regimes(
    seances_calmes: int, debut: date, fin: date, crises: Sequence[tuple[str, int]]
) -> str:
    return (
        f"calm regime: {typography.sessions(seances_calmes, langue='en')}, "
        f"{debut} → {fin}; crises: "
        + "; ".join(
            f"{nom}, {typography.sessions(seances, langue='en')}" for nom, seances in crises
        )
    )


# ═════════════════════════════════════════ 6. Couverture d'un scénario ══


def lignes_absentes(tickers: Sequence[str], tardives: bool) -> str:
    noms = _enumeration(tickers)
    etat = "were" if len(tickers) > 1 else "was"
    if tardives:
        return f"{noms} {etat} not yet listed"
    return f"{noms} {etat} not listed throughout the crisis"


def crise_rejouee_en_partie(crise: str, part: float, couvertes: int, total: int) -> str:
    return (
        f"{_majuscule(crise)} is replayed on only "
        f"{typography.percent(part, 0, langue='en')} of your portfolio "
        f"({typography.lines(couvertes, langue='en')} out of {total})"
    )


def impossible(crise: str, aucune_couverte: bool) -> str:
    cause = (
        "none of your holdings was listed throughout this crisis"
        if aucune_couverte
        else "the holdings listed throughout this crisis have fewer than two "
        "trading days in common"
    )
    return f"{_majuscule(crise)} cannot be replayed: {cause}."


def sous_le_seuil(portee: str, seuil: str) -> str:
    return f"{portee}: less than {seuil}, too little to give a figure for the whole."


def couverture_suffisante(portee: str, absentes: str, resultat: float, perte: bool) -> str:
    return (
        f"{portee}: {absentes}. Its replayed result "
        f"({typography.percent(resultat, 1, langue='en')}) covers only this "
        "part. The missing holdings were not replayed: "
        f"{ensemble_non_rejoue(perte)}."
    )


def provenance_scenario(debut: date, fin: date) -> str:
    return f"scenario {debut} → {fin}; share of the current market value"
