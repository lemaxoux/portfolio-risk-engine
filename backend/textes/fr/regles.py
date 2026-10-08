"""Les observations du moteur de règles, en français.

Déplacées telles quelles (chantier 7D) de `rules/rules.py`, qui garde ses
décisions : quelle variante, sur quel signe, quelles crises sont assez
longues pour conclure, lesquelles vont dans le même sens. Ce module ne décide
que ce qui ne se décide qu'en rédigeant, la grammaire française : l'accord de
« lignes » sur le nombre affiché, « une » au féminin, l'article d'une crise,
« du marché ».

Les observations vouvoient le lecteur, disent « variations » pour la
variance, « la part qui suit le marché » pour la part systématique, « jour de
bourse » dans les phrases et « séance » dans les provenances. Les phrases
s'écrivent avec des espaces ordinaires avant « : » : la publication
(`typography.prose`) les rend insécables.

Quelques fonctions reçoivent la période de la fenêtre sans la dire : c'est
l'anglais qui la nomme, pour situer dans le passé rejoué une phrase que le
français écrit au présent (question 9 du chantier, voir `en/regles.py`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import Enum

from backend import typography
from backend.typography import NBSP

from .moteur import ensemble_non_rejoue, jours_de_bourse

# ═══════════════════════════════════════════════════ Libellés et rendu ══


def libelle(regle: Enum) -> str:
    """Le libellé d'une règle, que la page affiche au-dessus de l'observation :
    la valeur de `RuleId`, où il est déclaré (des tests l'y lisent)."""
    return regle.value


# Le sujet d'une observation qui porte sur tout le portefeuille.
PORTEFEUILLE = "portefeuille"

AUCUN_SEUIL = "Aucun seuil : la mesure parle d'elle-même."


def rendu(
    titre: str,
    sujet: str,
    enonce: str,
    seuils: Sequence[tuple[str, str]],
    provenance: str,
) -> str:
    """L'observation à plat (`rendered`) : le libellé et le sujet, la phrase,
    une ligne par seuil (« Seuil : … », « Référence : … ») et la provenance."""
    lignes = [f"[{titre} : {sujet}] {enonce}"]
    if seuils:
        lignes += [f"  {etiquette} : {ligne}" for etiquette, ligne in seuils]
    else:
        lignes.append(f"  {AUCUN_SEUIL}")
    lignes.append(f"  Provenance : {provenance}")
    return "\n".join(lignes)


# ═══════════════════════════════════════════════════════ Mise en forme ══


def _points(ecart: float, decimales: int = 1) -> str:
    """Magnitude d'un écart entre deux parts, en points (singulier sous 2).

    L'accord suit le nombre AFFICHÉ, pas la valeur exacte : 1,96 point s'écrit
    « 2,0 points ». Les chiffres, eux, sont ceux de `typography`.
    """
    valeur = abs(ecart) * 100.0
    unite = "points" if round(valeur, decimales) >= 2 else "point"
    return f"{typography.number(valeur, decimales)}{NBSP}{unite}"


def _enumeration(elements: Sequence[str]) -> str:
    if len(elements) <= 1:
        return "".join(elements)
    return f"{', '.join(elements[:-1])} et {elements[-1]}"


def _lignes_effectives(valeur: float) -> str:
    """« 5,7 lignes », l'accord suivant le nombre affiché, comme `_points`."""
    return typography.counted(
        round(valeur, 1), "ligne", affiche=typography.number(valeur, 1)
    )


def _majuscule(texte: str) -> str:
    """La première lettre en capitale : un libellé placé en tête de phrase."""
    return texte[:1].upper() + texte[1:]


def _une(nombre: int) -> str:
    """Un nombre de crises, en lettres jusqu'à dix et au féminin : « une »."""
    return "une" if nombre == 1 else typography.cardinal(nombre)


def _ces_crises(total: int) -> str:
    return "cette crise" if total == 1 else f"ces {typography.cardinal(total)} crises"


# ═════════════════════════════════════════════ Taille de l'échantillon ══


def mention_mince(seances: int, minimum: str) -> str:
    """La phrase ajoutée à une estimation fragile, entre trois séances et le
    seuil de régression (`minimum`, écrit comme le seuil)."""
    return (
        f"Estimation mince : sur {jours_de_bourse(seances)}, moins que les "
        f"{minimum} retenus (seuil choisi à la main), "
        "quelques jours extrêmes suffisent à faire ce chiffre."
    )


_MESURES_REFUSEES = {
    "calcul": "ce calcul",
    "parts": "la part de chaque ligne dans les variations",
    "correlation": "une corrélation",
    "part_du_marche": "la part des variations qui suit le marché",
}


def refus(seances: int, mesure: str, minimum: str) -> str:
    """Ce qu'une règle écrit au lieu de chiffrer, sous trois séances : le
    calcul n'a pas de sens, et combien de jours il faudrait. La raison
    algébrique est la justification du seuil, publiée avec lui."""
    return (
        f"Sur {jours_de_bourse(seances)}, {_MESURES_REFUSEES[mesure]} n'a pas de "
        f"sens : il en faut au moins {minimum}."
    )


AUCUNE_PART_CHIFFREE = "Aucune n'est donc chiffrée ici."

AUCUNE_PAIRE_DECRITE = "Aucune paire n'est donc décrite ici."

AUCUNE_PART_AVANCEE = "Aucune part n'est donc avancée ici."


# ═════════════════════════════════════════════ Provenance d'une règle ══


def provenance_concentration(valorisation: date, fenetre: str) -> str:
    return (
        f"capital : valorisation au {valorisation} ; risque : fenêtre "
        f"d'estimation de {fenetre}"
    )


def provenance_fenetre(fenetre: str) -> str:
    return f"fenêtre d'estimation : {fenetre}"


# ═══════════════════════════════════════════ 1. Concentration effective ══

LIGNE_UNIQUE_NON_CHIFFREE = (
    "Votre portefeuille compte une seule ligne : elle en porte tout le "
    "montant. Ce qu'elle fait bouger n'est pas chiffré."
)


def capital_seul(lignes: int, en_capital: float) -> str:
    """La moitié EN CAPITAL, seule dite sous trois séances : une mesure
    ponctuelle, sans fenêtre d'estimation."""
    return (
        f"Vos {typography.lines(lignes)} pèsent comme "
        f"{_lignes_effectives(en_capital)} de même montant ; avec des "
        f"montants égaux, elles compteraient pour {lignes}. Ce "
        "qu'elles font bouger n'est pas chiffré."
    )


LIGNE_UNIQUE = (
    "Votre portefeuille compte une seule ligne : elle en porte tout le "
    "montant et toutes les variations."
)


def concentration(
    lignes: int, en_capital: float, en_risque: float, repartition: str, periode: str
) -> str:
    """En capital puis en risque. `repartition` : `plus_concentre`,
    `mieux_reparti` ou `pareil`, décidé sur les nombres affichés."""
    risque = typography.number(en_risque, 1)
    suite = {
        "plus_concentre": (
            f"mais font bouger le portefeuille comme {risque} seulement "
            ": le risque est plus concentré que l'argent"
        ),
        "mieux_reparti": (
            f"et font bouger le portefeuille comme {risque} : le risque "
            "est mieux réparti que l'argent"
        ),
        "pareil": (
            f"et font bouger le portefeuille comme {risque} : le risque "
            "se répartit comme l'argent"
        ),
    }[repartition]
    return (
        f"Vos {typography.lines(lignes)} pèsent comme "
        f"{_lignes_effectives(en_capital)} de même montant, {suite}."
    )


def montants_egaux(lignes: int) -> str:
    return f"Avec des montants égaux, elles compteraient pour {lignes}."


SURESTIMATION = "À ne regarder que les montants, on surestime donc la diversification."


def contribution_negative(en_risque: float, periode: str) -> str:
    return (
        "Au moins une ligne a bougé à rebours des autres : le chiffre de "
        f"{typography.number(en_risque, 1)} n'est qu'une approximation."
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
    """Part du capital (écrite comme la référence), part des variations, et
    leur écart. `comparaison` : `compense` (part négative), `egale`, `plus`
    ou `moins`."""
    tete = (
        f"{ticker} représente {part_du_capital} de la valeur du portefeuille "
        f"et {typography.percent(part, 1)} de ses variations"
    )
    suite = {
        "compense": (
            f" : {periode}, ses mouvements ont en moyenne compensé ceux des "
            "autres lignes."
        ),
        "egale": ", soit la même part.",
        "plus": f", soit {_points(ecart)} de plus.",
        "moins": f", soit {_points(ecart)} de moins.",
    }[comparaison]
    return tete + suite


# Propriété générale, dite une fois, sur la ligne qui pèse le plus.
INFLUENCE = (
    "Plus une ligne pèse dans les variations, plus elle pèse sur le "
    "résultat, à la baisse comme à la hausse."
)


def parcours_d_une_crise(ticker: str, crise: str, apport: float) -> str:
    """Ce que la ligne a coûté ou rapporté dans la seule crise rejouée. Le
    verbe porte le signe ; les points sont des magnitudes."""
    if apport == 0:
        effet = "n'a rien coûté ni rapporté au portefeuille"
    else:
        verbe = "a coûté" if apport < 0 else "a rapporté"
        effet = f"{verbe} {_points(apport)} au portefeuille"
    return f"Dans la crise rejouée ({crise}), {ticker} {effet}."


def parcours_des_crises(
    ticker: str, sens: str, pire: tuple[str, float], meilleur: tuple[str, float]
) -> str:
    """Le parcours dans plusieurs crises rejouées, de la pire à la meilleure.
    `sens` : `deux_sens`, `cout` (à chaque fois) ou `gain` (à chaque fois)."""
    (nom_pire, apport_pire), (nom_meilleur, apport_meilleur) = pire, meilleur
    if sens == "deux_sens":
        return (
            f"Dans les crises rejouées, {ticker} a joué dans les deux sens : il a "
            f"coûté {_points(apport_pire)} ({nom_pire}), mais rapporté "
            f"{_points(apport_meilleur)} ({nom_meilleur})."
        )
    verbe = {"cout": "a coûté", "gain": "a rapporté"}[sens]
    return (
        f"Dans les crises rejouées, {ticker} {verbe} au portefeuille à "
        f"chaque fois, de {_points(apport_pire)} ({nom_pire}) à "
        f"{_points(apport_meilleur)} ({nom_meilleur})."
    )


APPORTS_PARTIELS = "Ces apports ne portent que sur la partie rejouée du portefeuille."


# ═════════════════════════════════════════ 3. Diversification apparente ══


def paire_forte(periode: str, premier: str, second: str, correlation: float) -> str:
    return (
        f"{_majuscule(periode)}, {premier} et {second} ont largement évolué ensemble "
        f"(corrélation de {typography.number(correlation, 2)}) : à elles deux, "
        "elles diversifient moins que leur nombre ne le laisse "
        "penser."
    )


def aucune_paire_forte(
    periode: str, seuil: str, premier: str, second: str, reference: str
) -> str:
    """`seuil` et `reference` sont écrits comme leurs lignes de seuil."""
    return (
        f"{_majuscule(periode)}, aucune paire de lignes n'a évolué étroitement "
        "ensemble : aucune corrélation n'atteint "
        f"{seuil}. La paire la plus liée est {premier}–{second}, à "
        f"{reference}."
    )


# ═══════════════════════════════════════════════════ 4. Part systématique ══


def part_systematique(
    periode: str, part: float, propre: float, indice: str, nom_de_l_indice: str | None
) -> str:
    """« celles du marché, le S&P 500 » ; un indice sans nom connu, par son
    ticker : « celles de QQQ »."""
    celles = (
        f"celles de {indice}"
        if nom_de_l_indice is None
        else f"celles du marché, {nom_de_l_indice}"
    )
    return (
        f"{_majuscule(periode)}, "
        f"{typography.percent(part, 0)} des variations de votre portefeuille "
        f"ont suivi {celles}. Cette part ne se "
        "dilue pas en ajoutant d'autres actions américaines. Les "
        f"{typography.percent(propre, 0)} restants sont propres à vos "
        "lignes : c'est sur eux seuls que la diversification "
        "agit."
    )


# ═══════════════════════════════════════════════ 5. Dégradation en crise ══

_SUJET = "la part des variations qui suit le marché"


def _parts(crise: float, calme: float | None) -> str:
    """« 98 % », ou « de 45 % à 98 % » quand le temps ordinaire diffère d'une
    crise à l'autre."""
    ecrite = typography.percent(crise, 0)
    if calme is None:
        return ecrite
    return f"de {typography.percent(calme, 0)} à {ecrite}"


def evolution_sans_crise(calme: float, periode: str) -> str:
    """La part en temps ordinaire, quand aucune crise n'a assez de jours."""
    return f"{_majuscule(_SUJET)} est de {typography.percent(calme, 0)} {periode}."


def evolution(calme: float, periode: str, etapes: Sequence[tuple[float, str]]) -> str:
    """La part en temps ordinaire, puis dans chaque crise assez longue :
    `etapes`, la part de crise et le nom de la crise avec son article."""
    ecrites = [
        f"à {typography.percent(crise, 0)} pendant {nom}" for crise, nom in etapes
    ]
    return (
        f"{_majuscule(_SUJET)} passe de {typography.percent(calme, 0)} {periode} "
        f"{_enumeration(ecrites)}."
    )


# Couverture différente d'une crise à l'autre : le temps ordinaire est mesuré
# sur les lignes rejouées de chacune, et sa part change avec elles.
MESURE_PAR_CRISE = (
    f"{_majuscule(_SUJET)} se mesure ici sur les lignes rejouées de chaque crise."
)


def evolution_par_crise(etapes: Sequence[tuple[float, str | None, float, str]]) -> str:
    """`etapes` : la part en temps ordinaire, sa période quand elle change
    d'une crise à la précédente (None sinon), la part de crise et le nom de la
    crise avec son article."""
    ecrites = [
        f"de {typography.percent(calme, 0)}{'' if periode is None else f' {periode}'} "
        f"à {typography.percent(crise, 0)} pendant {nom}"
        for calme, periode, crise, nom in etapes
    ]
    return (
        f"Mesurée sur les lignes rejouées de chaque crise, {_SUJET} passe "
        f"{_enumeration(ecrites)}."
    )


def affaiblie(total: int) -> str:
    return (
        f"Dans {_ces_crises(total)}, la diversification entre vos lignes s'est "
        "affaiblie au moment où elle aurait servi."
    )


def aucune_hausse(total: int) -> str:
    if total == 1:
        return "Elle n'augmente pas dans cette crise."
    return f"Elle n'augmente dans aucune de {_ces_crises(total)}."


def hausse_partielle(hausses: int, total: int) -> str:
    return f"Elle augmente dans {_une(hausses)} de {_ces_crises(total)}."


def _trop_peu(jours: int) -> str:
    return f"mais sur {jours_de_bourse(jours)} seulement : trop peu pour conclure."


def crise_mince_comme_les_autres(
    crise: str, meme_sens: bool, part_de_crise: float, part_calme: float | None, jours: int
) -> str:
    """Une crise trop courte pour conclure, quand les crises suffisantes vont
    toutes dans le même sens : elle dit si elle va dans le leur."""
    sens = "dans le même sens" if meme_sens else "en sens contraire"
    return (
        f"{_majuscule(crise)} va {sens} ({_parts(part_de_crise, part_calme)}), "
        f"{_trop_peu(jours)}"
    )


def crise_mince(
    crise: str, hausse: bool, part_de_crise: float, part_calme: float | None, jours: int
) -> str:
    """Une crise trop courte pour conclure, sans sens commun auquel se
    comparer : son sens dit en clair."""
    verbe = "augmente" if hausse else "n'augmente pas"
    return (
        f"Pendant {crise}, elle {verbe} ({_parts(part_de_crise, part_calme)}), "
        f"{_trop_peu(jours)}"
    )


def sans_comparaison(crises: Sequence[str]) -> str:
    return f"Pas de comparaison possible pour {_enumeration(crises)}."


def provenance_regimes(
    seances_calmes: int, debut: date, fin: date, crises: Sequence[tuple[str, int]]
) -> str:
    return (
        f"régime calme : {typography.sessions(seances_calmes)}, {debut} → "
        f"{fin} ; crises : "
        + " ; ".join(f"{nom}, {typography.sessions(seances)}" for nom, seances in crises)
    )


# ═════════════════════════════════════════ 6. Couverture d'un scénario ══


def lignes_absentes(tickers: Sequence[str], tardives: bool) -> str:
    """« A et B n'étaient pas encore cotés » quand toutes sont entrées en
    cotation après le début de la crise ; sinon, elles n'étaient pas cotées
    pendant TOUTE la crise."""
    noms = _enumeration(tickers)
    plusieurs = len(tickers) > 1
    etat = "n'étaient pas" if plusieurs else "n'était pas"
    cote = "cotés" if plusieurs else "coté"
    if tardives:
        return f"{noms} {etat} encore {cote}"
    return f"{noms} {etat} {cote} pendant toute la crise"


def crise_rejouee_en_partie(crise: str, part: float, couvertes: int, total: int) -> str:
    return (
        f"{_majuscule(crise)} ne se rejoue que sur "
        f"{typography.percent(part, 0)} de votre portefeuille "
        f"({typography.lines(couvertes)} sur {total})"
    )


def impossible(crise: str, aucune_couverte: bool) -> str:
    """Deux causes, comme dans le moteur : aucune ligne couverte, ou des
    lignes couvertes sans deux jours de bourse en commun."""
    cause = (
        "aucune de vos lignes n'était cotée pendant toute cette crise"
        if aucune_couverte
        else "les lignes cotées pendant toute cette crise ont moins de deux "
        "jours de bourse en commun"
    )
    return f"Impossible de rejouer {crise} : {cause}."


def sous_le_seuil(portee: str, seuil: str) -> str:
    return (
        f"{portee} : moins de {seuil}, trop peu pour donner un "
        "chiffre pour l'ensemble."
    )


def couverture_suffisante(portee: str, absentes: str, resultat: float, perte: bool) -> str:
    """Le chiffre avec sa portée. La phrase ne dit pas dans quel sens
    l'ensemble aurait différé : le moteur ne le mesure pas."""
    return (
        f"{portee} : {absentes}. Son résultat "
        f"({typography.percent(resultat, 1)}) ne porte que "
        "sur cette partie. Les lignes absentes n'ont pas été rejouées : "
        f"{ensemble_non_rejoue(perte)}."
    )


def provenance_scenario(debut: date, fin: date) -> str:
    return f"scénario {debut} → {fin} ; part de la valeur de marché actuelle"
