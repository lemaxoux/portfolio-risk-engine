"""Les textes du moteur de risque, en anglais américain (chantier 7D).

Les mêmes noms et les mêmes signatures que `fr/moteur.py`, traduits avec le
glossaire validé (`anglais-proposition.md`, §c, hors dépôt) : « trading day »
dans les phrases, « session » dans les détails, « holding » pour une ligne,
« fluctuations » pour les variations, « Small-sample estimate » pour une
estimation mince. Aucune espace avant « : », « 1.06% », virgule des milliers.
"""

from __future__ import annotations

from datetime import date

from backend import typography
from backend.typography import MINUS, NBSP

# ════════════════════════════════════════════════ Périodes et fenêtres ══


def periode_en_annees(annees: int) -> str:
    """« the past two years », « the past year »."""
    if annees == 1:
        return "the past year"
    return f"the past {typography.cardinal(annees, langue='en')}{NBSP}years"


def periode_en_mois(mois: int) -> str:
    """« the past three months », « the past month »."""
    if mois == 1:
        return "the past month"
    return f"the past {typography.cardinal(mois, langue='en')}{NBSP}months"


def periode_en_jours(jours: int) -> str:
    """« the past seven trading days », « the past trading day »."""
    if jours == 1:
        return "the past trading day"
    return f"the past {typography.cardinal(jours, langue='en')}{NBSP}trading days"


def fenetre(observations: int, debut: date, fin: date, demandees: int | None) -> str:
    etat = "" if demandees is None else f" (requested: {demandees})"
    return f"{typography.sessions(observations, langue='en')}, {debut} → {fin}{etat}"


def jours_de_bourse(nombre: int) -> str:
    """« 7 trading days », insécable."""
    return typography.counted(nombre, "trading day", "trading days", langue="en")


# ═══════════════════════════════════════════ Méthodes et détails (provenance) ══

METHODE_ECART_TYPE = "standard deviation (√252)"

METHODE_MATRICE = "covariance matrix (√(wᵀΣw))"

METHODE_HISTORIQUE = "historical"

METHODE_PARAMETRIQUE = "parametric"

METHODE_MONTE_CARLO = "Monte Carlo"

METHODE_STUDENT = "parametric Student's t"

METHODE_STUDENT_MONTE_CARLO = "Student's t Monte Carlo"

BASE_DU_BETA = "raw returns (not excess)"


def methode_ewma(lam: float) -> str:
    return f"EWMA (λ={typography.compact(lam, langue='en')})"


def detail_historique(interpolation: str) -> str:
    return f"empirical quantile, {interpolation!r} interpolation"


def detail_normale(moyenne_estimee: bool) -> str:
    return "normality, μ estimated" if moyenne_estimee else "normality, μ = 0"


def detail_monte_carlo(simulations: int, graine: int) -> str:
    return (
        f"{typography.grouped(simulations, 'correlated normal draw', langue='en')}, "
        f"seed {graine}"
    )


def detail_student(nu: float, observations: int) -> str:
    return (
        f"ν = {typography.number(nu, 2, langue='en')} (MLE over "
        f"{typography.sessions(observations, langue='en')}), variance matched to Σ"
    )


def detail_student_monte_carlo(
    nu: float, observations: int, simulations: int, graine: int
) -> str:
    return (
        f"ν = {typography.number(nu, 2, langue='en')} (MLE over "
        f"{typography.sessions(observations, langue='en')}), scale S = Σ·(ν\u22122)/ν, "
        f"{typography.grouped(simulations, 'draw', langue='en')}, "
        f"seed {graine}"
    )


# ════════════════════════════════════════════════════ Réserves et refus ══

SORTINO_INDEFINI = (
    "no return below the target over the window: "
    "the downside deviation is zero and the ratio undefined"
)


def estimation_mince(observations: int, minimum: int) -> str:
    return (
        f"Small-sample estimate: only {jours_de_bourse(observations)}, "
        f"fewer than the {minimum} required to fit a "
        "curve (threshold chosen by hand). A few days are enough to move this "
        "figure, and the tool draws no conclusion from it."
    )


def moyenne_de_la_queue(queue: int, total: int, part: float) -> str:
    return (
        f"An average of only {jours_de_bourse(queue)}, "
        f"out of {typography.thousands(total, langue='en')}: each one accounts "
        f"for {typography.percent(part, 0, langue='en')} of the figure."
    )


_SUJETS_NON_ESTIMABLES = {
    "correlation": "a correlation",
    "beta": "market sensitivity",
    "contributions": "the share of each holding in the fluctuations",
}

_CONSEQUENCES_NON_ESTIMABLES = {
    "correlation": (
        f" With two days, it would be +1 or {MINUS}1 whatever the "
        "securities."
    ),
    "beta": "",
    "contributions": "",
}


def refus_non_estimable(observations: int, mesure: str, minimum: int) -> str:
    return (
        f"Over {jours_de_bourse(observations)}, "
        f"{_SUJETS_NON_ESTIMABLES[mesure]} is meaningless: it takes at least "
        f"{minimum}.{_CONSEQUENCES_NON_ESTIMABLES[mesure]}"
    )


def refus_queue_vide(observations: int, part: float, minimum: int) -> str:
    return (
        f"Over {jours_de_bourse(observations)}, none falls among the worst "
        f"{typography.percent(part, 0, langue='en')}: this calculation needs at "
        f"least {minimum}."
    )


def student_proche_de_la_normale(observations: int) -> str:
    return (
        f"Over these {jours_de_bourse(observations)}, your fluctuations "
        "do not depart from the normal distribution: Student's t-distribution "
        "would give the same figure (threshold chosen by hand). Over a short "
        "period, this can also mean that no extreme day is included."
    )


def monte_carlo_fenetre_trop_courte(seances: int, lignes: int) -> str:
    return (
        f"The window has {typography.sessions(seances, langue='en')} for "
        f"{typography.lines(lignes, langue='en')}: it needs more sessions than "
        "holdings to simulate the portfolio."
    )


def student_trop_peu_de_jours(minimum: int, seances: int) -> str:
    return (
        "Not enough days to fit Student's t-distribution: it takes at least "
        f"{minimum}, the period has "
        f"{seances}."
    )


def student_sans_variance_finie(seances: int, nu: float) -> str:
    return (
        f"Over these {jours_de_bourse(seances)}, Student's t-distribution "
        "does not fit your fluctuations (degrees of freedom estimated at "
        f"{typography.number(nu, 2, langue='en')}, more than 2 are needed): "
        "no figure comes out of it."
    )


COVARIANCE_NON_DEFINIE_POSITIVE = (
    "Covariance matrix not positive definite: the Cholesky decomposition "
    "would not give a usable factor. Usual causes: two perfectly correlated "
    "securities (a duplicated holding in the portfolio), a security with zero "
    "variance, or fewer sessions than securities in the window. Check the "
    "panel before simulating."
)

SIMULATION_STUDENT_IMPOSSIBLE = (
    "Covariance matrix not positive definite: Student's t simulation "
    "impossible. See monte_carlo_var for the usual causes."
)

SERIE_CONSTANTE = "Constant series: no Student's t-distribution can be fitted."


# ═══════════════════════════════════════════════════ L'indice de référence ══

NOMS_D_INDICE: dict[str, tuple[str, str]] = {
    "SPY": ("the S&P 500", "an index of 500 large US companies"),
}


# ═════════════════════════════════════════════════ Les crises rejouées ══


def crise_avec_article(nom: str, article: str | None) -> str:
    """« the 2008 Financial Crisis » ; sans nom anglais déclaré au catalogue,
    « the episode X »."""
    if article is None:
        return f"the episode {nom}"
    return f"{article} {nom}"


def du_sommet_au_point_bas(sommet: date, point_bas: date) -> str:
    return (
        f"From the S&P 500's closing peak ({typography.long_date(sommet, langue='en')}) "
        f"to its closing low ({typography.long_date(point_bas, langue='en')})."
    )


EXCLUSION_SANS_COURS = "no price in the database"


def exclusion_cotee_depuis(debut: date) -> str:
    return (
        f"listed only since {typography.long_date(debut, langue='en')}, "
        "after the start of the crisis"
    )


def exclusion_plus_cotee(fin: date) -> str:
    return (
        f"no longer listed after {typography.long_date(fin, langue='en')}, "
        "before the end of the crisis"
    )


def couverture(
    couvertes: int, total: int, part: float | None, exclues: tuple[str, ...]
) -> str:
    if part is None:
        return f"{typography.lines(couvertes, langue='en')}, 100% of the value"
    return (
        f"{couvertes}/{typography.lines(total, langue='en')}, "
        f"{typography.percent(part, 1, langue='en')} of the value "
        f"(excluded: {', '.join(exclues)})"
    )


AUCUNE_LIGNE_COTEE = (
    "None of your holdings was listed throughout this crisis: it cannot be "
    "replayed."
)

MOINS_DE_DEUX_JOURS_COMMUNS = (
    "Fewer than two trading days common to your holdings during this "
    "crisis: it cannot be replayed."
)


def ensemble_non_rejoue(perte: bool) -> str:
    if perte:
        return "the loss of the whole may have been different"
    return "the result of the whole may have been different"


def resume_scenario_non_calculable(nom: str, raison: str | None) -> str:
    return f"{nom}: cannot be computed. {raison}"


def resume_scenario(
    nom: str,
    rendement: float,
    pire_moment: float,
    seances: int,
    part_couverte: float | None,
    perte: bool,
) -> str:
    portee = (
        "full portfolio"
        if part_couverte is None
        else (
            f"{typography.percent(part_couverte, 1, langue='en')} of the value "
            f"only, {ensemble_non_rejoue(perte)}"
        )
    )
    return (
        f"{nom}: "
        f"{typography.percent(rendement, 1, signed=True, langue='en')} "
        "end to end, worst point "
        f"{typography.percent(pire_moment, 1, signed=True, langue='en')} "
        f"({typography.sessions(seances, langue='en')}, {portee})"
    )


# ═══════════════════════════════════════════ Régime calme, régime de crise ══


def beta_regresse(
    beta: float,
    erreur_type: float | None,
    r2: float,
    observations: int,
    minimum_non_atteint: int | None,
) -> str:
    incertitude = (
        "" if erreur_type is None else f" ± {typography.number(erreur_type, 2, langue='en')}"
    )
    texte = (
        f"{typography.number(beta, 2, langue='en')}{incertitude}, "
        f"R² {typography.number(r2, 2, langue='en')} "
        f"({typography.sessions(observations, langue='en')})"
    )
    if minimum_non_atteint is not None:
        texte += (
            ". SAMPLE TOO SMALL (< "
            f"{typography.sessions(minimum_non_atteint, langue='en')}), "
            "unreliable"
        )
    return texte


def pas_de_cours_de_l_indice(ticker: str, nom: str | None) -> str:
    return (
        f"No prices for {ticker if nom is None else nom} over this period: "
        "comparison impossible."
    )


def jours_communs_seulement(jours: int) -> str:
    return (
        f"Only {typography.counted(jours, 'common trading day', langue='en')}: "
        "too few to measure market sensitivity."
    )


def resume_regime_impossible(nom: str, raison: str) -> str:
    return f"{nom}: comparison impossible. {raison}"


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
    ecrit_ratio = (
        "undefined (benchmark almost flat)"
        if ratio is None
        else typography.number(ratio, 2, langue="en")
    )
    lignes = [
        f"{nom}: portfolio "
        f"{typography.percent(rendement_portefeuille, 1, signed=True, langue='en')}, "
        f"{indice} "
        f"{typography.percent(rendement_indice, 1, signed=True, langue='en')}",
        f"  realized amplification ratio: {ecrit_ratio} "
        "(ratio of log returns, not a beta)",
        f"  beta regressed within the window: {beta_crise}",
        f"  calm-regime beta: {beta_calme}",
        "  systematic risk share (R²): "
        f"{typography.number(r2_calme, 2, langue='en')} in the calm regime → "
        f"{typography.number(r2_crise, 2, langue='en')} in the crisis "
        f"({typography.number(variation, 2, signed=True, langue='en')})"
        + (", crisis sample too small" if crise_mince else ""),
        "  the calm beta predicted "
        f"{typography.percent(predit, 1, signed=True, langue='en')}, "
        "replayed loss "
        f"{typography.percent(rendement_portefeuille, 1, signed=True, langue='en')}: gap "
        f"{typography.signed_points(ecart, langue='en')}",
    ]
    if part_couverte is not None:
        lignes.append(
            f"  scope: {typography.percent(part_couverte, 1, langue='en')} "
            f"of the value only, {ensemble_non_rejoue(perte)}"
        )
    return "\n".join(lignes)


# ═══════════════════════════════════════════════ Erreurs du portefeuille ══


def portefeuille_introuvable(portefeuille: int) -> str:
    return f"Portfolio {portefeuille} not found."


def portefeuille_sans_position(portefeuille: int) -> str:
    return f"Portfolio {portefeuille} has no positions."


def prix_absents(tickers: list[str]) -> str:
    return (
        f"No price in the database for {tickers}. "
        "Run: python -m backend.ingestion add <TICKER>"
    )


def valeur_totale_non_positive(total: float) -> str:
    return (
        "Total market value zero or negative "
        f"({typography.number(total, 2, langue='en')}): "
        "the weights are not defined."
    )


AUCUN_TITRE_DEMANDE = "No security requested."


def prix_absents_sur_la_periode(tickers: list[str]) -> str:
    return f"No price in the database for {tickers} over the requested period."


def prix_absents_du_panel(absents: list[str], indice_absent: str | None) -> str:
    aide = (
        f" Load it with `python -m backend.ingestion add {indice_absent}`, "
        "or request the analysis without a benchmark (benchmark=None)."
        if indice_absent is not None
        else ""
    )
    return f"No price in the database for {absents}.{aide}"


MOINS_DE_DEUX_SEANCES_COMMUNES = (
    "Fewer than two sessions common to all securities: no return can be "
    "computed. Check coverage with `python -m backend.ingestion status`."
)


def seances_communes_insuffisantes(communes: int, minimum: int, rendements: int) -> str:
    return (
        "The securities have only "
        f"{typography.sessions(communes, langue='en')} in common, "
        f"at least {minimum} are needed: a sample dispersion requires "
        f"{typography.counted(rendements, 'return', langue='en')}. Check "
        "coverage with `python -m backend.ingestion status`."
    )
