"""Les textes du moteur de risque, en français.

Déplacés tels quels (chantier 7D) de `risk_engine/engine.py`,
`risk_engine/scenarios.py`, `risk_engine/portfolio.py` et `risk_engine/var.py`,
qui gardent leurs décisions : quelle variante, sur quelle fenêtre, pour quelle
crise. Ce module ne décide que ce qui ne se décide qu'en rédigeant, la
grammaire française : « dans le 1 % » ou « parmi les 5 % », « du S&P 500 »,
« la Crise financière 2008 ».

Les phrases s'écrivent avec des espaces ordinaires avant « : » : la
publication (`typography.prose`) les rend insécables. Les méthodes et les
détails s'affichent dans la provenance d'une mesure, en IBM Plex Sans : eux
seuls citent des lettres grecques.
"""

from __future__ import annotations

from datetime import date

from backend import typography
from backend.indice import BENCHMARK_NAMES
from backend.typography import MINUS, NARROW_NBSP, NBSP

# ════════════════════════════════════════════════ Périodes et fenêtres ══


def periode_en_annees(annees: int) -> str:
    """« ces deux dernières années », « cette dernière année »."""
    if annees == 1:
        return "cette dernière année"
    return f"ces {typography.cardinal(annees)}{NBSP}dernières années"


def periode_en_mois(mois: int) -> str:
    """« ces trois derniers mois », « ce dernier mois »."""
    if mois == 1:
        return "ce dernier mois"
    return f"ces {typography.cardinal(mois)}{NBSP}derniers mois"


def periode_en_jours(jours: int) -> str:
    """« ces sept derniers jours de bourse », « ce dernier jour de bourse »."""
    if jours == 1:
        return "ce dernier jour de bourse"
    return f"ces {typography.cardinal(jours)}{NBSP}derniers jours de bourse"


def fenetre(observations: int, debut: date, fin: date, demandees: int | None) -> str:
    """La fenêtre d'une provenance : « 504 séances, 2024-09-23 → 2026-09-25 »,
    et le nombre demandé quand elle n'a pas pu être remplie."""
    etat = "" if demandees is None else f" (demandé : {demandees})"
    return f"{typography.sessions(observations)}, {debut} → {fin}{etat}"


def jours_de_bourse(nombre: int) -> str:
    """« 7 jours de bourse », insécable : le mot d'une raison publiée.

    Les raisons de refus s'affichent à la place d'une phrase de lecture, où
    l'interface dit « jour de bourse ». « Séance » reste le mot des détails
    techniques (fenêtre, provenance).
    """
    return typography.counted(nombre, "jour de bourse", "jours de bourse")


# ═══════════════════════════════════════════ Méthodes et détails (provenance) ══

METHODE_ECART_TYPE = "écart-type (√252)"

METHODE_MATRICE = "matrice de covariance (√(wᵀΣw))"

METHODE_HISTORIQUE = "historique"

METHODE_PARAMETRIQUE = "paramétrique"

METHODE_MONTE_CARLO = "Monte Carlo"

METHODE_STUDENT = "Student paramétrique"

METHODE_STUDENT_MONTE_CARLO = "Monte Carlo Student"

BASE_DU_BETA = "rendements bruts (non excédentaires)"


def methode_ewma(lam: float) -> str:
    return f"EWMA (λ={typography.compact(lam)})"


def detail_historique(interpolation: str) -> str:
    return f"quantile empirique, interpolation {interpolation!r}"


def detail_normale(moyenne_estimee: bool) -> str:
    return "normalité, μ estimée" if moyenne_estimee else "normalité, μ = 0"


def detail_monte_carlo(simulations: int, graine: int) -> str:
    return (
        f"{typography.grouped(simulations, 'tirage')} "
        f"normaux corrélés, graine {graine}"
    )


def detail_student(nu: float, observations: int) -> str:
    return (
        f"ν = {typography.number(nu, 2)} (MLE sur "
        f"{typography.sessions(observations)}), variance ajustée sur Σ"
    )


def detail_student_monte_carlo(
    nu: float, observations: int, simulations: int, graine: int
) -> str:
    return (
        f"ν = {typography.number(nu, 2)} (MLE sur "
        f"{typography.sessions(observations)}), échelle S = Σ·(ν\u22122)/ν, "
        f"{typography.grouped(simulations, 'tirage')}, "
        f"graine {graine}"
    )


# ════════════════════════════════════════════════════ Réserves et refus ══

SORTINO_INDEFINI = (
    "aucun rendement sous la cible sur la fenêtre : "
    "la déviation à la baisse est nulle et le ratio indéfini"
)


def estimation_mince(observations: int, minimum: int) -> str:
    """Réserve d'une volatilité ou d'une VaR paramétrique sur trop peu de
    séances : « jours de bourse », « courbe », « l'outil », pour un lecteur qui
    ne connaît ni la loi normale ni le moteur de règles."""
    return (
        f"Estimation mince : {jours_de_bourse(observations)} seulement, "
        f"moins que les {minimum} retenus pour estimer une "
        "courbe (seuil choisi à la main). Quelques jours suffisent à déplacer ce "
        "chiffre, et l'outil n'en tire aucune conclusion."
    )


def moyenne_de_la_queue(queue: int, total: int, part: float) -> str:
    """La réserve permanente de la CVaR à 99 % : `part` est le poids d'un jour
    dans la moyenne, calculé par le moteur."""
    return (
        f"Moyenne de {jours_de_bourse(queue)} seulement, "
        f"sur {typography.thousands(total)} : chacun pèse "
        f"pour {typography.percent(part, 0)} du chiffre."
    )


# Ce que chaque mesure devient sous le seuil des séances estimables : la
# raison nomme SA mesure, et seule la corrélation garde une conséquence, vraie
# d'elle seule (voir `engine._non_estimable`).
_SUJETS_NON_ESTIMABLES = {
    "correlation": "une corrélation",
    "beta": "la sensibilité au marché",
    "contributions": "la part de chaque ligne dans les variations",
}

_CONSEQUENCES_NON_ESTIMABLES = {
    "correlation": (
        f" Avec deux jours, elle vaudrait +1 ou {MINUS}1 quels que soient les "
        "titres."
    ),
    "beta": "",
    "contributions": "",
}


def refus_non_estimable(observations: int, mesure: str, minimum: int) -> str:
    return (
        f"Sur {jours_de_bourse(observations)}, "
        f"{_SUJETS_NON_ESTIMABLES[mesure]} n'a pas de sens : il en faut au moins "
        f"{minimum}.{_CONSEQUENCES_NON_ESTIMABLES[mesure]}"
    )


def refus_queue_vide(observations: int, part: float, minimum: int) -> str:
    """La VaR historique et la CVaR d'un niveau, refusées ensemble : `part` est
    la part des jours dans la queue (1 − α)."""
    # « dans le 1 % le plus mauvais », « parmi les 5 % les plus mauvais » : le
    # singulier en deçà de deux, comme `typography.counted`.
    queue = (
        f"dans le {typography.percent(part, 0)} le plus mauvais"
        if part * 100.0 < 2.0
        else f"parmi les {typography.percent(part, 0)} les plus mauvais"
    )
    return (
        f"Sur {jours_de_bourse(observations)}, aucun ne tombe {queue} : "
        f"il en faut au moins {minimum} pour ce calcul."
    )


def student_proche_de_la_normale(observations: int) -> str:
    """Le moteur refuse une Student au-delà du ν maximal : un RÉSULTAT, pas une
    panne. La phrase n'écrit jamais ν."""
    return (
        f"Sur ces {jours_de_bourse(observations)}, vos variations "
        "ne s'écartent pas de la loi normale : la loi de Student donnerait le "
        "même chiffre (seuil choisi à la main). Sur une période courte, cela "
        "peut aussi vouloir dire qu'aucun jour extrême n'y figure."
    )


def monte_carlo_fenetre_trop_courte(seances: int, lignes: int) -> str:
    return (
        f"La fenêtre compte {typography.sessions(seances)} pour "
        f"{typography.lines(lignes)} : il en faut davantage que de lignes "
        "pour simuler le portefeuille."
    )


def student_trop_peu_de_jours(minimum: int, seances: int) -> str:
    return (
        "Pas assez de jours pour ajuster la loi de Student : il en faut au "
        f"moins {minimum}, la période en compte "
        f"{seances}."
    )


def student_sans_variance_finie(seances: int, nu: float) -> str:
    return (
        f"Sur ces {jours_de_bourse(seances)}, la loi de Student ne "
        "s'ajuste pas à vos variations (degrés de liberté estimés à "
        f"{typography.number(nu, 2)}, il en faut plus de 2) : "
        "aucun chiffre n'en sort."
    )


# Les trois refus de `risk_engine/var.py` qu'une réponse 200 peut publier,
# comme raison d'un volet simulé indisponible.
COVARIANCE_NON_DEFINIE_POSITIVE = (
    "Matrice de covariance non définie positive : la décomposition de "
    "Cholesky ne donnerait pas un facteur exploitable. Causes habituelles : "
    "deux titres parfaitement corrélés (une ligne en double dans le "
    "portefeuille), un titre à variance nulle, ou moins de séances que de "
    "titres dans la fenêtre. Vérifier le panel avant de simuler."
)

SIMULATION_STUDENT_IMPOSSIBLE = (
    "Matrice de covariance non définie positive : simulation Student "
    "impossible. Voir monte_carlo_var pour les causes habituelles."
)

SERIE_CONSTANTE = "Série constante : aucune loi de Student n'est ajustable."


# ═══════════════════════════════════════════════════ L'indice de référence ══

# Ce que suit un indice de référence, pour une phrase de lecture : lu dans
# `backend/indice.py`, où il est déclaré, et que `ingestion.universe`
# réexporte pour les tests. Un seul endroit pour le français.
NOMS_D_INDICE = BENCHMARK_NAMES


def _de_l_indice(ticker: str, nom: str | None) -> str:
    """« du S&P 500 » pour SPY, « de QQQ » pour un indice sans nom connu."""
    if nom is None:
        return f"de {ticker}"
    if nom.startswith("le "):
        return f"du {nom[3:]}"
    if nom.startswith("les "):
        return f"des {nom[4:]}"
    return f"de {nom}"


# ═════════════════════════════════════════════════ Les crises rejouées ══


def crise_avec_article(nom: str, article: str | None) -> str:
    """« la Crise financière 2008 », avec l'article que déclare le catalogue ;
    sans article déclaré, « l'épisode Choc bref », correct quel que soit le
    nom. Une élision s'écrit sans espace : « l'Éclatement de la bulle »."""
    if article is None:
        return f"l'épisode {nom}"
    if article.endswith("'"):
        return f"{article}{nom}"
    return f"{article} {nom}"


def du_sommet_au_point_bas(sommet: date, point_bas: date) -> str:
    """La phrase qui borne une crise. Ses dates passent par `long_date` : le
    jour, le mois et l'année ne se séparent pas. Écrites à la main, « (3 »
    finissait une ligne que « janvier 2022) » commençait."""
    return (
        f"Du sommet de clôture du S&P 500 ({typography.long_date(sommet)}) à son point bas "
        f"de clôture ({typography.long_date(point_bas)})."
    )


EXCLUSION_SANS_COURS = "aucun cours en base"


def exclusion_cotee_depuis(debut: date) -> str:
    return (
        f"cotée depuis le {typography.long_date(debut)} "
        "seulement, après le début de la crise"
    )


def exclusion_plus_cotee(fin: date) -> str:
    return (
        f"plus cotée après le {typography.long_date(fin)}, "
        "avant la fin de la crise"
    )


def couverture(
    couvertes: int, total: int, part: float | None, exclues: tuple[str, ...]
) -> str:
    """La portée d'un scénario en une ligne ; `part` vaut None quand la
    couverture est complète."""
    if part is None:
        return f"{typography.lines(couvertes)}, 100{NARROW_NBSP}% de la valeur"
    return (
        f"{couvertes}/{typography.lines(total)}, "
        f"{typography.percent(part, 1)} de la valeur "
        f"(exclues : {', '.join(exclues)})"
    )


# Aucune ligne n'a traversé l'épisode : la même raison pour le scénario et
# pour la comparaison de régimes, qui s'affichent dans le même bloc.
AUCUNE_LIGNE_COTEE = (
    "Aucune de vos lignes n'était cotée pendant toute cette crise : elle ne "
    "peut pas être rejouée."
)

MOINS_DE_DEUX_JOURS_COMMUNS = (
    "Moins de deux jours de bourse communs à vos lignes pendant "
    "cette crise : elle ne peut pas être rejouée."
)


def ensemble_non_rejoue(perte: bool) -> str:
    """Ce qu'un résultat en couverture partielle ne dit pas : la perte du
    portefeuille entier. Le moteur ne mesure pas dans quel sens l'ensemble
    aurait différé."""
    if perte:
        return "la perte de l'ensemble a pu être différente"
    return "le résultat de l'ensemble a pu être différent"


def resume_scenario_non_calculable(nom: str, raison: str | None) -> str:
    return f"{nom} : non calculable. {raison}"


def resume_scenario(
    nom: str,
    rendement: float,
    pire_moment: float,
    seances: int,
    part_couverte: float | None,
    perte: bool,
) -> str:
    """Une ligne qui ne peut pas laisser croire à une couverture totale :
    `part_couverte` vaut None quand elle l'est."""
    portee = (
        "portefeuille complet"
        if part_couverte is None
        else (
            f"{typography.percent(part_couverte, 1)} de la valeur "
            f"seulement, {ensemble_non_rejoue(perte)}"
        )
    )
    return (
        f"{nom} : "
        f"{typography.percent(rendement, 1, signed=True)} "
        f"de bout en bout, pire moment "
        f"{typography.percent(pire_moment, 1, signed=True)} "
        f"({typography.sessions(seances)}, {portee})"
    )


# ═══════════════════════════════════════════ Régime calme, régime de crise ══


def beta_regresse(
    beta: float,
    erreur_type: float | None,
    r2: float,
    observations: int,
    minimum_non_atteint: int | None,
) -> str:
    """« 0,96 ± 0,02, R² 0,86 (355 séances) » ; `minimum_non_atteint` est le
    minimum de séances quand l'échantillon est trop mince, None sinon."""
    incertitude = "" if erreur_type is None else f" ± {typography.number(erreur_type, 2)}"
    texte = (
        f"{typography.number(beta, 2)}{incertitude}, "
        f"R² {typography.number(r2, 2)} "
        f"({typography.sessions(observations)})"
    )
    if minimum_non_atteint is not None:
        texte += (
            f". ÉCHANTILLON TROP MINCE (< "
            f"{typography.sessions(minimum_non_atteint)}), "
            "non fiable"
        )
    return texte


def pas_de_cours_de_l_indice(ticker: str, nom: str | None) -> str:
    return (
        f"Pas de cours {_de_l_indice(ticker, nom)} sur cette période : "
        "comparaison impossible."
    )


def jours_communs_seulement(jours: int) -> str:
    return (
        f"{typography.counted(jours, 'jour de bourse commun', 'jours de bourse communs')}"
        " seulement : trop peu pour mesurer la sensibilité au marché."
    )


def resume_regime_impossible(nom: str, raison: str) -> str:
    return f"{nom} : comparaison impossible. {raison}"


def resume_regime(
    nom: str,
    rendement_portefeuille: float,
    indice: str,
    rendement_indice: float,
    ratio: float | None,
    beta_crise: str,
    beta_calme: str,
    r2_calme: float,
    r2_crise: float,
    variation: float,
    crise_mince: bool,
    predit: float,
    ecart: float,
    part_couverte: float | None,
    perte: bool,
) -> str:
    """Le résumé d'une comparaison, publié et jamais affiché. `beta_crise` et
    `beta_calme` sont déjà écrits (`beta_regresse`) ; `part_couverte` vaut None
    quand la couverture est complète."""
    ecrit_ratio = (
        "indéfini (benchmark quasi immobile)"
        if ratio is None
        else typography.number(ratio, 2)
    )
    lignes = [
        f"{nom} : portefeuille "
        f"{typography.percent(rendement_portefeuille, 1, signed=True)}, "
        f"{indice} "
        f"{typography.percent(rendement_indice, 1, signed=True)}",
        f"  ratio d'amplification réalisé : {ecrit_ratio} "
        "(rapport de rendements log, pas un beta)",
        f"  beta régressé dans la fenêtre : {beta_crise}",
        f"  beta de régime calme : {beta_calme}",
        f"  part de risque systématique (R²) : "
        f"{typography.number(r2_calme, 2)} en régime calme → "
        f"{typography.number(r2_crise, 2)} en crise "
        f"({typography.number(variation, 2, signed=True)})"
        + (", échantillon de crise trop mince" if crise_mince else ""),
        f"  le beta calme prédisait "
        f"{typography.percent(predit, 1, signed=True)}, "
        f"perte réelle "
        f"{typography.percent(rendement_portefeuille, 1, signed=True)} : écart "
        f"{typography.signed_points(ecart)}",
    ]
    if part_couverte is not None:
        lignes.append(
            f"  portée : {typography.percent(part_couverte, 1)} "
            f"de la valeur seulement, {ensemble_non_rejoue(perte)}"
        )
    return "\n".join(lignes)


# ═══════════════════════════════════════════════ Erreurs du portefeuille ══
#
# Rédigées pour une `PortfolioError` (409) : l'erreur garde le nom de la
# fonction et ses arguments, et l'API la rédige dans la langue demandée.


def portefeuille_introuvable(portefeuille: int) -> str:
    return f"Portefeuille {portefeuille} introuvable."


def portefeuille_sans_position(portefeuille: int) -> str:
    return f"Portefeuille {portefeuille} sans position."


def prix_absents(tickers: list[str]) -> str:
    return (
        f"Aucun prix en base pour {tickers}. "
        "Lancer : python -m backend.ingestion add <TICKER>"
    )


def valeur_totale_non_positive(total: float) -> str:
    return (
        f"Valeur de marché totale nulle ou négative "
        f"({typography.number(total, 2)}) : "
        "les poids ne sont pas définis."
    )


AUCUN_TITRE_DEMANDE = "Aucun titre demandé."


def prix_absents_sur_la_periode(tickers: list[str]) -> str:
    return f"Aucun prix en base pour {tickers} sur la période demandée."


def prix_absents_du_panel(absents: list[str], indice_absent: str | None) -> str:
    """`indice_absent` : l'indice de référence demandé, quand c'est lui qui
    manque ; la phrase dit alors comment le charger, ou s'en passer."""
    aide = (
        f" Le charger avec `python -m backend.ingestion add {indice_absent}`, "
        "ou demander l'analyse sans benchmark (benchmark=None)."
        if indice_absent is not None
        else ""
    )
    return f"Aucun prix en base pour {absents}.{aide}"


MOINS_DE_DEUX_SEANCES_COMMUNES = (
    "Moins de deux séances communes à tous les titres : impossible de "
    "calculer un rendement. Vérifier la couverture avec "
    "`python -m backend.ingestion status`."
)


def seances_communes_insuffisantes(communes: int, minimum: int, rendements: int) -> str:
    return (
        "Les titres n'ont que "
        f"{typography.sessions(communes)} en commun, "
        f"il en faut au moins {minimum} : une dispersion "
        "d'échantillon demande "
        f"{typography.counted(rendements, 'rendement')}. Vérifier "
        "la couverture avec `python -m backend.ingestion status`."
    )
