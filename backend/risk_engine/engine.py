"""Composition des mesures sur un portefeuille réel.

Cette couche assemble : elle charge (via `portfolio`), construit les séries (via
`returns`), applique les mesures (via `measures`) et rend des résultats qui
portent leur fenêtre d'estimation.

Aucun calcul n'est fait ici — tout ce qui produit un nombre vit dans `measures`,
où il se teste sans base de données.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date

import pandas as pd

from backend import typography
from backend.typography import NARROW_NBSP

from . import covariance, measures, regime, stress, var
from .config import (
    DDOF,
    DEFAULT_BENCHMARK,
    DEFAULT_WINDOW,
    EWMA_LAMBDA,
    MAX_STUDENT_NU,
    MIN_ESTIMABLE_OBSERVATIONS,
    MIN_REGRESSION_OBSERVATIONS,
    TRADING_DAYS_PER_YEAR,
    MONTE_CARLO_SEED,
    MONTE_CARLO_SIMULATIONS,
    daily_risk_free_rate,
    risk_free_observation_date,
    risk_free_rate,
)
from .portfolio import (
    PortfolioError,
    PortfolioWeights,
    load_price_panel,
    market_value_weights,
    price_coverage,
)
from .scenarios import SCENARIOS, Scenario
from .returns import align_panel, portfolio_returns, simple_returns, wealth_curve


@dataclass(frozen=True)
class Window:
    """Fenêtre d'estimation effectivement utilisée.

    Accompagne chaque résultat. Un chiffre de risque sans sa fenêtre n'est pas
    interprétable : une volatilité de 18 % ne veut pas dire la même chose selon
    qu'elle est estimée sur deux ans ou sur vingt, et rien dans le nombre ne
    permet de le deviner. Transporter la fenêtre avec la valeur est ce qui
    empêche qu'on compare deux mesures incomparables — ou qu'on estime un jour
    une VaR sur tout l'historique depuis 2005 sans s'en apercevoir.
    """

    requested: int
    observations: int
    start: date
    end: date

    @property
    def complete(self) -> bool:
        """Vrai si la fenêtre demandée a pu être remplie entièrement."""
        return self.observations >= self.requested

    def __str__(self) -> str:
        etat = "" if self.complete else f" (demandé : {self.requested})"
        return (
            f"{typography.sessions(self.observations)}, "
            f"{self.start} → {self.end}{etat}"
        )


@dataclass(frozen=True)
class VolatilityResult:
    annualised: float
    daily: float
    method: str
    window: Window


@dataclass(frozen=True)
class DrawdownResult:
    value: float
    peak_date: date
    trough_date: date
    window: Window


@dataclass(frozen=True)
class SharpeResult:
    annualised: float
    risk_free_annual: float
    risk_free_daily: float
    window: Window
    # Date d'observation du taux sans risque. Même principe que la fenêtre
    # d'estimation : le chiffre transporte de quoi juger sa fraîcheur, au lieu
    # d'obliger à retrouver la constante. None signifie que la date est
    # réellement inconnue — taux imposé sans provenance fournie — et non
    # qu'elle a été perdue en chemin.
    risk_free_observed_on: date | None = None


@dataclass(frozen=True)
class SortinoResult:
    annualised: float | None
    downside_deviation_daily: float
    target_daily: float
    window: Window
    undefined_reason: str | None = None


@dataclass(frozen=True)
class ConcentrationResult:
    """Concentration des poids. Mesure PONCTUELLE, sans fenêtre d'estimation.

    Contrairement aux autres résultats de ce module, elle ne porte pas de
    `Window` : elle ne s'estime pas sur un historique, elle décrit la structure
    du portefeuille à un instant donné. Lui attacher une fenêtre laisserait
    croire à une moyenne dans le temps.

    Elle porte en revanche sa PROVENANCE, qui est la règle de fond : aucun
    résultat ne doit être ininterprétable isolément. Pour une mesure estimée,
    la provenance est la fenêtre ; pour une mesure ponctuelle, c'est la date de
    valorisation — celle des prix ayant servi à calculer les poids. Un HHI de
    0,18 ne dit pas la même chose s'il décrit le portefeuille d'aujourd'hui ou
    celui d'il y a six mois.

    Le champ s'appelle `as_of`, comme dans `PortfolioWeights` et `RiskReport` :
    un même concept, un seul mot.
    """

    hhi: float
    effective_positions: float
    equal_weight_reference: float
    n_positions: int
    as_of: date


@dataclass(frozen=True)
class CovarianceResult:
    """Matrices de covariance et de corrélation des titres détenus.

    Estimées sur observations COMPLÈTES, jamais paire à paire : toutes les
    cellules reposent sur les mêmes dates, ce qui garantit que la matrice reste
    semi-définie positive et donc utilisable par Cholesky.

    `correlation` vaut None en deçà de `MIN_ESTIMABLE_OBSERVATIONS`, avec sa
    raison — même convention que `SortinoResult.annualised`. À deux
    observations, toutes les cellules hors diagonale valent ±1 par construction,
    quelles que soient les données : une carte de chaleur dessinée là-dessus
    resterait symétrique, de diagonale 1, donc parfaitement plausible, et
    entièrement fausse. Refuser dans la phrase du moteur de règles ne suffirait
    pas — l'interface lit la matrice, pas la phrase.

    `covariance` reste publiée : elle sert au calcul de la volatilité
    paramétrique et de la VaR, dont le dénominateur `wᵀΣw` est la variance de la
    série du portefeuille, elle-même estimable dès deux observations.
    """

    covariance: pd.DataFrame = field(repr=False)
    correlation: pd.DataFrame | None = field(repr=False)
    window: Window
    ddof: int = DDOF
    correlation_undefined_reason: str | None = None


@dataclass(frozen=True)
class VarianceContributionResult:
    """Part de chaque ligne dans la variance du portefeuille, sur la fenêtre.

    `contributions` somme à 1. À lire à côté de `weights` : l'écart entre la
    part du risque et la part du capital est ce que le poids seul ne montre pas.

    `contributions` vaut None en deçà de `MIN_ESTIMABLE_OBSERVATIONS`, avec sa
    raison — même convention que `CovarianceResult.correlation` et
    `SortinoResult.annualised`. À deux observations la covariance est de rang 1
    et la part de chaque ligne s'y ramène exactement à `wᵢδᵢ / (wᵀδ)`, sa part
    dans une seule différence journalière : une identité arithmétique, pas une
    décomposition de variance.

    `weights` reste publié : les poids sont une mesure PONCTUELLE, lue sur la
    dernière valorisation, que la brièveté de l'historique ne touche pas.
    """

    contributions: dict[str, float] | None
    weights: dict[str, float]
    window: Window
    undefined_reason: str | None = None

    def excess_over_weight(self, ticker: str) -> float | None:
        """Part de variance − part de valeur, en points. None si non estimable."""
        if self.contributions is None:
            return None
        return self.contributions[ticker] - self.weights[ticker]

    @property
    def effective_positions(self) -> float | None:
        """Lignes effectives en risque, `1/Σcᵢ²` (voir `covariance.effective_risk_positions`)."""
        if self.contributions is None:
            return None
        return covariance.effective_risk_positions(self.contributions)

    @property
    def has_negative_contribution(self) -> bool | None:
        """None quand les contributions ne sont pas estimables.

        `False` y serait un mensonge tranquille : il affirmerait qu'aucune ligne
        n'a évolué à rebours des autres, alors que rien n'a été mesuré.
        """
        if self.contributions is None:
            return None
        return any(c < 0.0 for c in self.contributions.values())


@dataclass(frozen=True)
class BetaResult:
    """Sensibilité au marché et décomposition du risque.

    `r_squared` est la part de variance du portefeuille expliquée par le
    benchmark : c'est le risque systématique. Son complément à 1 est le risque
    idiosyncratique, celui que la diversification peut encore réduire.

    LA PENTE AUSSI EST INDÉFINIE en deçà de `MIN_ESTIMABLE_OBSERVATIONS`, pas
    seulement le R². À zéro degré de liberté résiduel, la droite passe
    exactement par les points : elle n'a pas d'erreur type, et ce n'est donc
    plus une estimation mais une construction géométrique. Rendre la pente en
    nullifiant le seul R² laisserait croire que la sensibilité au marché a été
    mesurée et que seule sa qualité d'ajustement manque.

    `undefined_reason` accompagne alors les deux, sur le modèle de
    `SortinoResult`. Le résultat garde son benchmark et sa fenêtre : ce qui
    manque est le chiffre, pas la provenance.
    """

    beta: float | None
    r_squared: float | None
    benchmark: str
    basis: str
    window: Window
    undefined_reason: str | None = None

    @property
    def idiosyncratic_share(self) -> float | None:
        return None if self.r_squared is None else 1.0 - self.r_squared


@dataclass(frozen=True)
class VarResult:
    """Value at Risk à horizon une séance, en PERTE POSITIVE.

    Voir la convention de signe en tête de `risk_engine.var` : une valeur de
    0,021 se lit « perte d'au moins 2,1 % », une valeur négative signifie un
    gain à ce niveau de confiance.

    `nu` porte les degrés de liberté quand la VaR repose sur une loi de Student :
    une donnée du résultat, pas une mention noyée dans `detail`.
    """

    value: float
    confidence: float
    method: str
    window: Window
    detail: str = ""
    nu: float | None = None


@dataclass(frozen=True)
class ExpectedShortfallResult:
    """Perte moyenne au-delà du quantile de VaR, en perte positive.

    `tail_observations` est porté par le résultat et non relégué aux logs : le
    CVaR est une moyenne, et le nombre de séances qu'elle moyenne fait partie du
    chiffre.

    `caveat` porte, en PERMANENCE à 99 % et au-delà, l'avertissement qui va avec
    ce chiffre. À 99 %, la queue ne compte que 1 % de la fenêtre — 6 séances sur
    504 à la fenêtre par défaut. Ce n'est pas une anomalie qu'un seuil
    détecterait : c'est la structure même du chiffre. Un seuil « moins de 10
    observations » serait allumé à chaque calcul, et une alerte permanente
    n'informe plus. L'avertissement est donc attaché au chiffre plutôt que
    déclenché par lui.
    """

    value: float
    confidence: float
    tail_observations: int
    threshold: float
    window: Window

    @property
    def caveat(self) -> str | None:
        if self.confidence < 0.99:
            return None
        return (
            f"Moyenne de {typography.sessions(self.tail_observations)} seulement, "
            f"sur une fenêtre de {self.window.observations} : chacune pèse pour "
            f"{typography.percent(1 / self.tail_observations, 0)} du chiffre."
        )

@dataclass(frozen=True)
class LimitingPosition:
    """Ligne dont l'historique borne la fenêtre d'estimation de TOUT le rapport.

    Le panel est aligné sur l'INTERSECTION des dates : une seule ligne cotée
    depuis peu ramène toutes les mesures à son propre historique. Une ligne à
    5 % du portefeuille peut ainsi faire passer la fenêtre de 504 séances à 40,
    et déplacer le beta et la VaR de tout le portefeuille.

    `Window.complete` dit déjà que la fenêtre est courte ; il ne dit pas à cause
    de qui. Sans ce nom, l'utilisateur voit des chiffres qui ont changé sans
    savoir quelle ligne les a changés — et la seule action possible, retirer ou
    conserver cette ligne, lui reste invisible.

    ATTRIBUTION PROUVÉE, PAS DEVINÉE — une ligne n'est nommée que si sa première
    séance disponible est exactement celle où le panel commence. Quand la
    troncature vient d'un trou au milieu d'une série plutôt que d'une entrée en
    cotation tardive, aucune ligne n'est nommée : mieux vaut ne désigner
    personne que de désigner à tort.
    """

    ticker: str
    first_available: date


@dataclass(frozen=True)
class PortfolioSeries:
    """Série de rendements d'un portefeuille et son contexte."""

    returns: pd.Series
    wealth: pd.Series
    weights: PortfolioWeights
    window: Window
    asset_returns: pd.DataFrame = field(repr=False)
    benchmark: str | None = None
    benchmark_returns: pd.Series | None = field(default=None, repr=False)
    limiting_positions: tuple[LimitingPosition, ...] = ()


@dataclass(frozen=True)
class RiskReport:
    """Rapport complet : mesures d'une série (4A) et multi-titres (4B).

    Les VaR et Expected Shortfall sont indexés par niveau de confiance, pour que
    le 95 % et le 99 % soient lisibles côte à côte sans multiplier les champs.

    `returns` et `wealth` sont les séries MÊMES sur lesquelles les mesures ont
    été calculées — `PortfolioSeries.returns` et `.wealth`, transportées telles
    quelles. Un graphique qui les tracerait à partir d'un autre calcul pourrait
    dessiner un creux que le `drawdown` publié ne décrit pas. `wealth` commence
    au point de départ à 1,0, la séance qui précède le premier rendement : sans
    lui, le pic initial disparaît (voir `returns.wealth_curve`).

    `valuation` est la valorisation qui a produit `weights` — prix, valeurs,
    date —, transportée pour que la page affiche les quantités et les prix de
    la MÊME réponse que les mesures, et non d'un second appel qui pourrait lire
    une base rafraîchie entre-temps.
    """

    portfolio_id: int
    as_of: date
    total_value: float
    weights: dict[str, float]
    window: Window
    volatility: VolatilityResult
    ewma_volatility: VolatilityResult
    drawdown: DrawdownResult
    sharpe: SharpeResult
    sortino: SortinoResult
    concentration: ConcentrationResult
    parametric_volatility: VolatilityResult
    matrices: CovarianceResult
    historical_var: dict[float, VarResult]
    parametric_var: dict[float, VarResult]
    expected_shortfall: dict[float, ExpectedShortfallResult]
    variance_contributions: VarianceContributionResult
    returns: pd.Series = field(repr=False)
    wealth: pd.Series = field(repr=False)
    histogram: measures.ReturnHistogram = field(repr=False)
    valuation: PortfolioWeights = field(repr=False)
    beta: BetaResult | None = None
    monte_carlo_var: dict[float, VarResult] | None = None
    student_fit: var.StudentFit | None = None
    student_parametric_var: dict[float, VarResult] | None = None
    student_monte_carlo_var: dict[float, VarResult] | None = None
    limiting_positions: tuple[LimitingPosition, ...] = ()
    # Pourquoi un volet demandé manque, sur le modèle de
    # `CovarianceResult.correlation_undefined_reason` : le moteur produit la
    # raison, l'API la publie. Deux champs, pas un : le Monte Carlo normal et la
    # Student échouent pour des causes différentes, et l'une ne doit pas masquer
    # l'autre. Nuls quand le volet existe, ou quand `monte_carlo=False` : rien
    # n'a été demandé, il n'y a rien à expliquer.
    monte_carlo_unavailable_reason: str | None = None
    student_unavailable_reason: str | None = None


# ------------------------------------------------------------------ Séries --


def build_portfolio_series(
    conn: sqlite3.Connection,
    portfolio_id: int,
    window: int = DEFAULT_WINDOW,
    benchmark: str | None = None,
) -> PortfolioSeries:
    """Construit la série de rendements du portefeuille sur la fenêtre demandée.

    Poids ACTUELS appliqués aux rendements historiques : hypothèse de
    rééquilibrage quotidien, détaillée dans `returns.portfolio_returns`.

    Le benchmark, quand il est demandé, entre dans le MÊME panel aligné que les
    titres détenus. Ce n'est pas un détail d'implémentation : charger sa série
    séparément ferait porter ses rendements sur ses propres séances à lui. Si
    une séance manque à un titre du portefeuille, le rendement du portefeuille
    couvrirait alors j1→j3 pendant que celui du benchmark couvrirait j2→j3, et
    le beta comparérait des intervalles différents sans que rien ne le signale.
    """
    if window < 2:
        raise ValueError(
            f"Fenêtre trop courte : {window} (minimum {typography.sessions(2)})."
        )

    poids = market_value_weights(conn, portfolio_id)
    tickers = poids.tickers
    colonnes = tickers + (
        [benchmark] if benchmark and benchmark not in tickers else []
    )

    panel = load_price_panel(conn, colonnes)

    # `load_price_panel` ne lève que si AUCUN titre n'a de prix ; un benchmark
    # absent alors que les titres détenus sont là passerait donc au travers et
    # ressortirait bien plus loin en KeyError sur une colonne manquante.
    absents = [t for t in colonnes if t not in panel.columns]
    if absents:
        aide = (
            f" Le charger avec `python -m backend.ingestion add {benchmark}`, "
            "ou demander l'analyse sans benchmark (benchmark=None)."
            if benchmark in absents
            else ""
        )
        raise PortfolioError(f"Aucun prix en base pour {absents}.{aide}")

    aligne = align_panel(panel)
    if len(aligne) < 2:
        raise PortfolioError(
            f"Moins de deux séances communes à tous les titres : impossible de "
            "calculer un rendement. Vérifier la couverture avec "
            "`python -m backend.ingestion status`."
        )

    rendements = simple_returns(aligne)
    rendements_titres = rendements[tickers]
    serie_complete = portfolio_returns(rendements_titres, poids.weights)
    serie = serie_complete.tail(window)

    # Le point de départ de la courbe de valeur est la séance qui PRÉCÈDE le
    # premier rendement retenu : sans elle, le sommet initial manquerait et le
    # drawdown serait mesuré depuis un pic trop bas.
    dates_alignees = list(aligne.index)
    depart = dates_alignees[dates_alignees.index(serie.index[0]) - 1]

    return PortfolioSeries(
        returns=serie,
        wealth=wealth_curve(serie, initial_date=depart),
        weights=poids,
        window=Window(
            requested=window,
            observations=len(serie),
            start=serie.index[0],
            end=serie.index[-1],
        ),
        asset_returns=rendements_titres.tail(window),
        benchmark=benchmark,
        benchmark_returns=(
            rendements[benchmark].tail(window) if benchmark else None
        ),
        limiting_positions=_limiting_positions(panel, aligne, window, len(serie)),
    )


def _limiting_positions(
    panel: pd.DataFrame,
    aligned: pd.DataFrame,
    requested: int,
    obtained: int,
) -> tuple[LimitingPosition, ...]:
    """Lignes dont l'entrée en cotation borne la fenêtre. Vide si elle est pleine.

    Une fenêtre pleine n'a pas de ligne limitante : elle a été bornée par la
    demande, pas par l'historique. Nommer une ligne dans ce cas ferait porter à
    quelqu'un la responsabilité d'un choix de paramètre.
    """
    if obtained >= requested:
        return ()

    debut_commun = aligned.index[0]
    limitantes = [
        LimitingPosition(ticker=str(ticker), first_available=premiere)
        for ticker in panel.columns
        # `first_valid_index` est la première séance où CETTE ligne a un cours ;
        # l'égalité prouve qu'elle est ce qui empêche le panel de commencer plus
        # tôt. Une inégalité stricte signifie que la troncature vient d'ailleurs.
        for premiere in (panel[ticker].first_valid_index(),)
        if premiere == debut_commun
    ]
    return tuple(sorted(limitantes, key=lambda ligne: ligne.ticker))


# ---------------------------------------------------------------- Mesures --


def volatility(serie: PortfolioSeries) -> VolatilityResult:
    annualisee = measures.annualised_volatility(serie.returns)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method="écart-type (√252)",
        window=serie.window,
    )


def ewma_volatility(
    serie: PortfolioSeries, lam: float = EWMA_LAMBDA
) -> VolatilityResult:
    annualisee = measures.ewma_volatility(serie.returns, lam=lam)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method=f"EWMA (λ={typography.compact(lam)})",
        window=serie.window,
    )


def drawdown(serie: PortfolioSeries) -> DrawdownResult:
    brut = measures.max_drawdown(serie.wealth)
    return DrawdownResult(
        value=brut.value,
        peak_date=brut.peak_date,
        trough_date=brut.trough_date,
        window=serie.window,
    )


def sharpe(
    serie: PortfolioSeries,
    annual_risk_free: float | None = None,
    risk_free_observed_on: date | None = None,
) -> SharpeResult:
    """Sharpe annualisé du portefeuille.

    `risk_free_observed_on` permet de faire voyager la provenance d'un taux
    imposé : celui qui fournit le taux est le seul à savoir de quand il date.
    Sans lui, un taux surchargé ressort avec une date `None`, qui signifie alors
    « réellement inconnue » et non « perdue par construction ».

    Dater le taux par DÉFAUT est refusé : sa provenance est déjà connue
    (`RISK_FREE_RATE_OBSERVED_ON`), et lui en attribuer une autre reviendrait à
    affirmer sur cette valeur quelque chose qui n'est pas vrai.
    """
    surcharge = annual_risk_free is not None
    if risk_free_observed_on is not None and not surcharge:
        raise ValueError(
            "risk_free_observed_on ne se fournit qu'avec annual_risk_free. "
            "Le taux par défaut porte déjà sa date d'observation "
            "(RISK_FREE_RATE_OBSERVED_ON) ; la remplacer lui attribuerait une "
            "provenance qui n'est pas la sienne."
        )

    taux_annuel = annual_risk_free if surcharge else risk_free_rate()
    taux_quotidien = daily_risk_free_rate(taux_annuel)
    return SharpeResult(
        annualised=measures.sharpe_ratio(serie.returns, risk_free_daily=taux_quotidien),
        risk_free_annual=taux_annuel,
        risk_free_daily=taux_quotidien,
        window=serie.window,
        risk_free_observed_on=(
            risk_free_observed_on if surcharge else risk_free_observation_date()
        ),
    )


def sortino(serie: PortfolioSeries, target_daily: float = 0.0) -> SortinoResult:
    deviation = measures.downside_deviation(serie.returns, target_daily)
    ratio = measures.sortino_ratio(serie.returns, target_daily)
    return SortinoResult(
        annualised=ratio,
        downside_deviation_daily=deviation,
        target_daily=target_daily,
        window=serie.window,
        undefined_reason=(
            None
            if ratio is not None
            else "aucun rendement sous la cible sur la fenêtre : "
            "la déviation à la baisse est nulle et le ratio indéfini"
        ),
    )


def concentration(poids: PortfolioWeights) -> ConcentrationResult:
    hhi = measures.herfindahl_index(poids.weights)
    n = len(poids.weights)
    return ConcentrationResult(
        hhi=hhi,
        effective_positions=1.0 / hhi,
        equal_weight_reference=measures.equal_weight_reference(n),
        n_positions=n,
        as_of=poids.as_of,
    )


# ------------------------------------------------------- Mesures multi-titres --


# Conséquence PROPRE À CHAQUE MESURE de la dégénérescence de l'échantillon.
#
# Les trois mesures refusent sous le même SEUIL, pas pour la même RAISON, et un
# texte commun affirmerait de chacune ce qui n'est vrai que d'une seule :
#
#   * « le coefficient vaut ±1 » est vrai d'une corrélation et FAUX d'une pente —
#     à deux séances un beta vaut n'importe quoi, 11,84 puis 8,65 sur deux
#     fenêtres de la base réelle ;
#   * « une régression avec constante a n − 2 degrés de liberté » est hors sujet
#     pour une décomposition de variance, où il n'y a aucune régression.
#
# Une explication fausse attachée à un refus juste est pire qu'un refus sans
# explication : le lecteur en tire une conclusion sur ses données.
#
# La partie commune est donc réduite à ce qui vaut des trois — à deux
# observations, le centrage ne laisse qu'une seule direction —, et chaque
# conséquence porte sa propre justification.
CONSEQUENCES_NON_ESTIMABLE: dict[str, str] = {
    "correlation": (
        "Deux points centrés sont colinéaires : le coefficient vaut alors ±1 par "
        "construction, quelles que soient les données."
    ),
    # Ce texte ne mentionne PAS « ±1 », pas même pour le nier : ce serait
    # répondre à une objection que le lecteur d'un beta ne se pose pas, et
    # remettre en circulation le mot qui n'a rien à faire ici.
    "beta": (
        "Une régression avec constante a n − 2 degrés de liberté résiduels ; à "
        "deux points il n'en reste aucun, et la pente n'a pas d'erreur type. "
        "Elle prend alors n'importe quelle valeur, ce qui ne la rend pas "
        "davantage estimée."
    ),
    "contributions": (
        "Une covariance d'échantillon sur n observations est de rang au plus "
        "n − 1, le centrage retirant une dimension : à deux observations elle est "
        "de rang 1, Σ ∝ δδᵀ, et la part de chaque ligne s'y ramène à "
        "wᵢδᵢ / (wᵀδ) — sa part dans ce seul écart."
    ),
}


def _non_estimable(window: Window, quoi: str, mesure: str) -> str | None:
    """Raison du refus d'estimer, ou None si la fenêtre le permet.

    Une partie commune — le seuil, et le fait dont les trois mesures découlent —
    puis la justification propre à `mesure`. Le partage s'arrête exactement là où
    les mesures cessent de dégénérer de la même façon : la corrélation par
    colinéarité, le beta par absence de résidu, les contributions par perte de
    rang.
    """
    if window.observations >= MIN_ESTIMABLE_OBSERVATIONS:
        return None
    return (
        f"{typography.sessions(window.observations)} seulement : {quoi} n'est "
        "pas estimable "
        f"en deçà de {MIN_ESTIMABLE_OBSERVATIONS} observations. À deux "
        "observations, le centrage ne laisse qu'une seule direction : tout se "
        "calcule à partir d'un unique écart journalier. "
        f"{CONSEQUENCES_NON_ESTIMABLE[mesure]}"
    )


def covariance_matrices(serie: PortfolioSeries) -> CovarianceResult:
    """Covariance et corrélation des titres détenus, sur la fenêtre."""
    refus = _non_estimable(serie.window, "une corrélation", "correlation")
    return CovarianceResult(
        covariance=covariance.covariance_matrix(serie.asset_returns),
        correlation=(
            None if refus else covariance.correlation_matrix(serie.asset_returns)
        ),
        window=serie.window,
        correlation_undefined_reason=refus,
    )


def variance_contributions(serie: PortfolioSeries) -> VarianceContributionResult:
    """Contribution de chaque ligne à la variance, sur la fenêtre d'estimation."""
    refus = _non_estimable(
        serie.window, "une décomposition de la variance", "contributions"
    )
    if refus:
        return VarianceContributionResult(
            contributions=None,
            weights=dict(serie.weights.weights),
            window=serie.window,
            undefined_reason=refus,
        )

    matrice = covariance.covariance_matrix(serie.asset_returns)
    return VarianceContributionResult(
        contributions=covariance.variance_contributions(serie.weights.weights, matrice),
        weights=dict(serie.weights.weights),
        window=serie.window,
    )


def parametric_volatility(serie: PortfolioSeries) -> VolatilityResult:
    """Volatilité annualisée par la matrice : `√(wᵀΣw) × √252`.

    Égale à `volatility(serie)` à la tolérance flottante près — identité
    algébrique, pas approximation, garantie par la convention `DDOF` partagée.
    """
    matrice = covariance.covariance_matrix(serie.asset_returns)
    annualisee = covariance.parametric_volatility(serie.weights.weights, matrice)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method="matrice de covariance (√(wᵀΣw))",
        window=serie.window,
    )


def beta_vs_benchmark(serie: PortfolioSeries) -> BetaResult:
    """Beta et R² contre le benchmark chargé avec la série."""
    if serie.benchmark is None or serie.benchmark_returns is None:
        raise ValueError(
            "Aucun benchmark dans cette série. La construire avec "
            "`build_portfolio_series(..., benchmark=\"SPY\")`."
        )
    base = "rendements bruts (non excédentaires)"
    refus = _non_estimable(serie.window, "un beta", "beta")
    if refus:
        return BetaResult(
            beta=None,
            r_squared=None,
            benchmark=serie.benchmark,
            basis=base,
            window=serie.window,
            undefined_reason=refus,
        )

    brut = covariance.beta(serie.returns, serie.benchmark_returns)
    return BetaResult(
        beta=brut.beta,
        r_squared=brut.r_squared,
        benchmark=serie.benchmark,
        basis=base,
        window=serie.window,
    )


# ------------------------------------------------------------------- VaR --


def historical_var(
    serie: PortfolioSeries, confidence: float = 0.95
) -> VarResult:
    return VarResult(
        value=var.historical_var(serie.returns, confidence),
        confidence=confidence,
        method="historique",
        window=serie.window,
        detail=f"quantile empirique, interpolation {var.QUANTILE_METHOD!r}",
    )


def parametric_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    include_mean: bool = False,
) -> VarResult:
    """VaR sous hypothèse de normalité, à partir de `√(wᵀΣw)`.

    `include_mean=False` par défaut : voir `var.parametric_var` pour le
    raisonnement sur l'erreur type de la moyenne.
    """
    matrice = covariance.covariance_matrix(serie.asset_returns)
    sigma_quotidien = covariance.parametric_volatility(
        serie.weights.weights, matrice, periods_per_year=1
    )
    moyenne = float(serie.returns.mean()) if include_mean else 0.0
    return VarResult(
        value=var.parametric_var(sigma_quotidien, confidence, moyenne),
        confidence=confidence,
        method="paramétrique",
        window=serie.window,
        detail=(
            "normalité, μ estimée" if include_mean else "normalité, μ = 0"
        ),
    )


def expected_shortfall(
    serie: PortfolioSeries, confidence: float = 0.95
) -> ExpectedShortfallResult:
    brut = var.expected_shortfall(serie.returns, confidence)
    return ExpectedShortfallResult(
        value=brut.value,
        confidence=confidence,
        tail_observations=brut.tail_observations,
        threshold=brut.threshold,
        window=serie.window,
    )


def monte_carlo_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
) -> VarResult:
    matrice = covariance.covariance_matrix(serie.asset_returns)
    brut = var.monte_carlo_var(
        serie.weights.weights,
        matrice,
        confidence=confidence,
        simulations=simulations,
        seed=seed,
    )
    return VarResult(
        value=brut.value,
        confidence=confidence,
        method="Monte Carlo",
        window=serie.window,
        detail=(
            f"{typography.grouped(brut.simulations, 'tirage')} "
            f"normaux corrélés, graine {brut.seed}"
        ),
    )


def student_fit(serie: PortfolioSeries) -> var.StudentFit:
    """ν par maximum de vraisemblance sur la série du portefeuille (voir
    `var.fit_student_t` pour le choix de l'estimateur).

    Lève `ValueError` quand ν dépasse `MAX_STUDENT_NU`, seuil choisi à la
    main : la Student ne se distingue plus de la normale, et un ν de 10¹⁵ n'est
    pas une mesure de la queue. L'estimateur rend son maximum tel quel ; c'est
    ici que le moteur refuse de s'en servir. `analyse_portfolio` range la
    raison dans `RiskReport.student_unavailable_reason`, et sert le reste du
    rapport, Monte Carlo normal compris.

    La phrase décrit un RÉSULTAT, pas une panne : sur cette fenêtre, les
    rendements ne montrent pas de queues plus épaisses que la normale. Elle
    n'écrit jamais ν — au-delà du seuil, sa valeur ne mesure plus rien, et
    l'écrire rendrait plausible un nombre qui peut valoir 10¹⁵.
    """
    ajustement = var.fit_student_t(serie.returns)
    if ajustement.nu > MAX_STUDENT_NU:
        raise ValueError(
            f"Sur cette fenêtre de {typography.sessions(ajustement.observations)}, "
            "la loi de Student ne se distingue pas de la normale (ν estimé "
            f"supérieur à {typography.number(MAX_STUDENT_NU, 0)}, seuil choisi à "
            "la main) : les rendements ne montrent pas de queues plus épaisses "
            "que la normale. "
            "Sur une fenêtre courte, cela peut aussi signifier qu'aucun choc "
            "extrême n'y figure."
        )
    return ajustement


def student_parametric_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    fit: var.StudentFit | None = None,
) -> VarResult:
    """VaR Student à variance ajustée, forme fermée : la cible du Monte Carlo."""
    ajustement = fit or student_fit(serie)
    matrice = covariance.covariance_matrix(serie.asset_returns)
    sigma_quotidien = covariance.parametric_volatility(
        serie.weights.weights, matrice, periods_per_year=1
    )
    return VarResult(
        value=var.student_t_var(sigma_quotidien, ajustement.nu, confidence),
        confidence=confidence,
        method="Student paramétrique",
        window=serie.window,
        detail=(
            f"ν = {typography.number(ajustement.nu, 2)} (MLE sur "
            f"{typography.sessions(ajustement.observations)}), variance ajustée sur Σ"
        ),
        nu=ajustement.nu,
    )


def student_monte_carlo_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    fit: var.StudentFit | None = None,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
) -> VarResult:
    """VaR par simulation Student multivariée, covariance simulée égale à Σ."""
    ajustement = fit or student_fit(serie)
    matrice = covariance.covariance_matrix(serie.asset_returns)
    brut = var.monte_carlo_student_var(
        serie.weights.weights,
        matrice,
        ajustement.nu,
        confidence=confidence,
        simulations=simulations,
        seed=seed,
    )
    return VarResult(
        value=brut.value,
        confidence=confidence,
        method="Monte Carlo Student",
        window=serie.window,
        detail=(
            f"ν = {typography.number(ajustement.nu, 2)} (MLE sur "
            f"{typography.sessions(ajustement.observations)}), échelle S = Σ·(ν−2)/ν, "
            f"{typography.grouped(brut.simulations, 'tirage')}, "
            f"graine {brut.seed}"
        ),
        nu=ajustement.nu,
    )


# --------------------------------------------------- Scénarios de stress --


@dataclass(frozen=True)
class ExcludedPosition:
    """Ligne écartée d'un scénario, et pourquoi."""

    ticker: str
    reason: str
    value: float
    weight: float
    first_available: date | None = None


@dataclass(frozen=True)
class ScenarioCoverage:
    """Quelle part du portefeuille le scénario a réellement pu couvrir.

    Trois comportements étaient possibles face à une ligne sans historique sur
    la fenêtre : faire échouer tout le scénario, l'exclure en silence, ou
    déclarer la couverture. Le premier est trop fragile — un seul titre récent
    priverait de tout rejeu 2008. Le second est dangereux : la perte est
    mécaniquement sous-estimée et rien ne le signale. D'où le troisième.

    `value_share` est la fraction de la VALEUR du portefeuille couverte, et non
    la fraction des lignes : écarter une ligne à 1 % et une ligne à 40 % n'ont
    pas la même portée, alors que « 5 lignes sur 6 » se dirait pareil.
    """

    covered: tuple[str, ...]
    excluded: tuple[ExcludedPosition, ...]
    covered_value: float
    total_value: float

    @property
    def value_share(self) -> float:
        return self.covered_value / self.total_value if self.total_value else 0.0

    @property
    def is_complete(self) -> bool:
        return not self.excluded

    @property
    def has_any(self) -> bool:
        return bool(self.covered)

    @property
    def covered_count(self) -> int:
        return len(self.covered)

    @property
    def total_count(self) -> int:
        return len(self.covered) + len(self.excluded)

    def __str__(self) -> str:
        if self.is_complete:
            return f"{typography.lines(self.covered_count)}, 100{NARROW_NBSP}% de la valeur"
        return (
            f"{self.covered_count}/{typography.lines(self.total_count)}, "
            f"{typography.percent(self.value_share, 1)} de la valeur "
            f"(exclues : {', '.join(e.ticker for e in self.excluded)})"
        )


@dataclass(frozen=True)
class ScenarioResult:
    """Rejeu d'un épisode historique sur le portefeuille actuel.

    Deux mesures distinctes, à ne pas confondre :

    * `end_to_end_return` — ce que vaudrait le portefeuille à la SORTIE de
      l'épisode ;
    * `max_drawdown` — le pire moment TRAVERSÉ en cours de route, qui peut être
      nettement plus profond.

    Le drawdown est celui de la trajectoire du PORTEFEUILLE, jamais la somme des
    pires points de chaque ligne : ce dernier composerait un scénario fictif où
    toutes les lignes toucheraient leur plancher le même jour, ce qui n'arrive
    jamais et surestime la perte.

    COUVERTURE PARTIELLE — les chiffres portent sur la seule partie couverte,
    dont les poids actuels sont renormalisés à 1. La portée du chiffre est
    donnée par `coverage`, et `summary()` la rappelle systématiquement.

    DIRECTION DU BIAIS — les deux options disponibles sous-estiment la perte,
    par des mécanismes différents, et il faut le savoir en lisant le chiffre :

    * supposer les lignes exclues stables DILUE la perte dans une valeur qui n'a
      pas été rejouée ;
    * les exclure et renormaliser, option retenue, décrit la partie la plus
      ÉTABLIE du portefeuille. Une ligne absente de l'historique d'une crise est
      par construction cotée depuis moins longtemps : en moyenne plus jeune,
      plus spéculative, précisément le profil qui aurait le plus souffert. Le
      chiffre décrit donc les lignes les plus résistantes, et le biais
      s'aggrave à mesure que la couverture baisse.

    La renormalisation reste le bon choix — elle ne fabrique aucun rendement —
    mais la perte réelle aurait vraisemblablement été plus lourde que le chiffre
    affiché, d'autant plus que `coverage.value_share` est faible.

    Les deux valent None quand aucune ligne n'est couverte : il n'y a alors pas
    de chiffre à donner, et en fabriquer un serait pire que de n'en donner aucun.
    """

    scenario: Scenario
    coverage: ScenarioCoverage
    end_to_end_return: float | None
    max_drawdown: measures.Drawdown | None
    contributions: tuple[stress.PositionContribution, ...]
    observations: int
    unavailable_reason: str | None = None

    def summary(self) -> str:
        """Une ligne qui ne peut pas laisser croire à une couverture totale."""
        if self.end_to_end_return is None:
            return f"{self.scenario.name} : non calculable — {self.unavailable_reason}"
        portee = (
            "portefeuille complet"
            if self.coverage.is_complete
            else (
                f"{typography.percent(self.coverage.value_share, 1)} de la valeur "
                "seulement, "
                "perte probablement sous-estimée"
            )
        )
        return (
            f"{self.scenario.name} : "
            f"{typography.percent(self.end_to_end_return, 1, signed=True)} "
            f"de bout en bout, pire moment "
            f"{typography.percent(self.max_drawdown.value, 1, signed=True)} "
            f"({typography.sessions(self.observations)}, {portee})"
        )


def assess_scenario_coverage(
    conn: sqlite3.Connection, portfolio_id: int, scenario: Scenario
) -> ScenarioCoverage:
    """Quelles lignes ont un historique couvrant toute la fenêtre.

    Une ligne est couverte si sa première séance en base précède le début du
    scénario et sa dernière le suit. Le critère est volontairement strict : un
    titre introduit en bourse trois jours après le sommet de 2007 n'a pas
    traversé l'épisode, et lui prêter une trajectoire partielle reviendrait à
    inventer la partie manquante.
    """
    return _coverage_for(conn, market_value_weights(conn, portfolio_id), scenario)


def _coverage_for(
    conn: sqlite3.Connection, poids: PortfolioWeights, scenario: Scenario
) -> ScenarioCoverage:
    disponible = price_coverage(conn, poids.tickers)

    couverts: list[str] = []
    exclus: list[ExcludedPosition] = []

    for ticker in poids.tickers:
        bornes = disponible.get(ticker)
        if bornes is None:
            exclus.append(
                ExcludedPosition(
                    ticker=ticker,
                    reason="aucun historique en base",
                    value=poids.values[ticker],
                    weight=poids.weights[ticker],
                )
            )
            continue

        debut, fin = bornes
        if debut > scenario.start:
            exclus.append(
                ExcludedPosition(
                    ticker=ticker,
                    reason=(
                        f"historique débutant le {debut}, après l'ouverture du "
                        f"scénario ({scenario.start})"
                    ),
                    value=poids.values[ticker],
                    weight=poids.weights[ticker],
                    first_available=debut,
                )
            )
        elif fin < scenario.end:
            exclus.append(
                ExcludedPosition(
                    ticker=ticker,
                    reason=(
                        f"historique s'arrêtant le {fin}, avant la clôture du "
                        f"scénario ({scenario.end})"
                    ),
                    value=poids.values[ticker],
                    weight=poids.weights[ticker],
                    first_available=debut,
                )
            )
        else:
            couverts.append(ticker)

    return ScenarioCoverage(
        covered=tuple(couverts),
        excluded=tuple(exclus),
        covered_value=sum(poids.values[t] for t in couverts),
        total_value=poids.total_value,
    )


def run_scenario(
    conn: sqlite3.Connection, portfolio_id: int, scenario: Scenario
) -> ScenarioResult:
    """Rejoue un épisode sur le portefeuille actuel.

    Le portefeuille entre dans la fenêtre avec ses poids ACTUELS en valeur de
    marché ; les quantités qui en découlent restent ensuite figées jusqu'à la
    fin (achat-conservation), et les poids dérivent. Voir l'en-tête de
    `risk_engine.stress` pour la rupture assumée avec la Phase 4.
    """
    poids = market_value_weights(conn, portfolio_id)
    couverture = _coverage_for(conn, poids, scenario)
    vide = ScenarioResult(
        scenario=scenario,
        coverage=couverture,
        end_to_end_return=None,
        max_drawdown=None,
        contributions=(),
        observations=0,
    )

    if not couverture.has_any:
        return replace(
            vide,
            unavailable_reason=(
                "aucune ligne du portefeuille n'a d'historique couvrant "
                f"{scenario.start} → {scenario.end}"
            ),
        )

    # Poids actuels des seules lignes couvertes ; `stress` les renormalise à 1.
    poids_couverts = {t: poids.weights[t] for t in couverture.covered}
    panel = align_panel(
        load_price_panel(conn, list(poids_couverts), scenario.start, scenario.end)
    )

    if len(panel) < 2:
        return replace(
            vide,
            unavailable_reason=(
                f"moins de deux séances communes sur {scenario.start} → "
                f"{scenario.end} pour les lignes couvertes"
            ),
        )

    trajectoire = stress.buy_and_hold_value(panel, poids_couverts)
    return ScenarioResult(
        scenario=scenario,
        coverage=couverture,
        end_to_end_return=stress.end_to_end_return(trajectoire),
        max_drawdown=measures.max_drawdown(trajectoire),
        contributions=tuple(stress.position_contributions(panel, poids_couverts)),
        observations=len(panel),
    )


def run_all_scenarios(
    conn: sqlite3.Connection,
    portfolio_id: int,
    scenarios: tuple[Scenario, ...] = SCENARIOS,
) -> list[ScenarioResult]:
    """Rejoue tous les scénarios du catalogue, du plus ancien au plus récent."""
    return [run_scenario(conn, portfolio_id, s) for s in scenarios]


# ------------------------------------------ Régime calme / régime de crise --


@dataclass(frozen=True)
class RegressedBeta:
    """Beta RÉGRESSÉ sur une fenêtre datée, avec son incertitude.

    Porte son nombre d'observations et son erreur type, comme toute estimation du
    moteur. `sample_too_thin` signale une fenêtre trop courte pour une pente
    stable : le chiffre reste rendu, mais il ne doit pas être lu comme solide.
    Sur les 23 rendements du krach COVID, trois ou quatre séances extrêmes
    dictent la pente à elles seules.
    """

    beta: float
    r_squared: float
    standard_error: float | None
    observations: int
    start: date
    end: date
    min_observations: int = MIN_REGRESSION_OBSERVATIONS

    @property
    def sample_too_thin(self) -> bool:
        return self.observations < self.min_observations

    def __str__(self) -> str:
        incertitude = (
            ""
            if self.standard_error is None
            else f" ± {typography.number(self.standard_error, 2)}"
        )
        texte = (
            f"{typography.number(self.beta, 2)}{incertitude}, "
            f"R² {typography.number(self.r_squared, 2)} "
            f"({typography.sessions(self.observations)})"
        )
        if self.sample_too_thin:
            texte += (
                f" — ÉCHANTILLON TROP MINCE (< "
                f"{typography.sessions(self.min_observations)}), "
                "non fiable"
            )
        return texte


@dataclass(frozen=True)
class RegimeComparison:
    """Le beta de régime calme a-t-il prédit la perte subie pendant la crise ?

    Quatre grandeurs, à ne pas confondre (voir `risk_engine.regime`) :

    * `amplification_ratio` — `ln(1 + R_p)/ln(1 + R_b)`, rapport de deux
      rendements cumulés. PAS un beta : ni régression, ni résidu, ni erreur type ;
    * `crisis_beta` — beta réellement régressé sur les rendements quotidiens de
      la fenêtre, avec R², erreur type et nombre d'observations ;
    * `calm_beta` — beta de la fenêtre d'estimation récente, convention Phase 4
      (poids constants) ;
    * `predicted_return` — `exp(β_calme · ln(1 + R_b)) − 1`, ce que le beta calme
      aurait annoncé face au mouvement réel du benchmark.

    `prediction_gap` (réalisé − prédit) est le livrable : négatif, la crise a
    coûté plus que ce que la gestion courante laissait attendre.
    `ratio_beta_divergence` (ratio − beta de crise) est un résultat en soi, pas
    une anomalie : il mesure la part du résultat cumulé que la co-variation
    quotidienne avec le marché n'explique pas. `systematic_share_change` (R² de
    crise − R² calme) mesure la dégradation de la diversification.

    Convention de portefeuille, dans la crise comme en 5A : poids actuels au
    départ, quantités figées ensuite ; les rendements quotidiens régressés sont
    ceux de cette trajectoire. En couverture partielle, TOUT — perte, ratio,
    beta de crise ET beta calme — porte sur les mêmes lignes couvertes, poids
    renormalisés, pour que l'écart ne mélange pas un effet de couverture à un
    effet de régime.
    """

    scenario: Scenario
    coverage: ScenarioCoverage
    benchmark: str
    portfolio_return: float | None = None
    benchmark_return: float | None = None
    amplification_ratio: float | None = None
    crisis_beta: RegressedBeta | None = None
    calm_beta: RegressedBeta | None = None
    predicted_return: float | None = None
    unavailable_reason: str | None = None

    @property
    def prediction_gap(self) -> float | None:
        """Réalisé − prédit par le beta calme, en points de rendement."""
        if self.portfolio_return is None or self.predicted_return is None:
            return None
        return self.portfolio_return - self.predicted_return

    @property
    def ratio_beta_divergence(self) -> float | None:
        if self.amplification_ratio is None or self.crisis_beta is None:
            return None
        return self.amplification_ratio - self.crisis_beta.beta

    @property
    def systematic_share_change(self) -> float | None:
        """R² de crise − R² de régime calme.

        La lecture la plus directe de la dégradation de la diversification : le
        R² est la part de la variance du portefeuille expliquée par le marché,
        c'est-à-dire la part de risque qui ne se diversifie pas. Positif, la
        crise a rendu le portefeuille plus dépendant du marché qu'en temps calme.
        """
        if self.crisis_beta is None or self.calm_beta is None:
            return None
        return self.crisis_beta.r_squared - self.calm_beta.r_squared

    def summary(self) -> str:
        if self.unavailable_reason is not None:
            return (
                f"{self.scenario.name} : comparaison impossible — "
                f"{self.unavailable_reason}"
            )
        ratio = (
            "indéfini (benchmark quasi immobile)"
            if self.amplification_ratio is None
            else typography.number(self.amplification_ratio, 2)
        )
        lignes = [
            f"{self.scenario.name} : portefeuille "
            f"{typography.percent(self.portfolio_return, 1, signed=True)}, "
            f"{self.benchmark} "
            f"{typography.percent(self.benchmark_return, 1, signed=True)}",
            f"  ratio d'amplification réalisé : {ratio} "
            "(rapport de rendements log, pas un beta)",
            f"  beta régressé dans la fenêtre : {self.crisis_beta}",
            f"  beta de régime calme : {self.calm_beta}",
            f"  part de risque systématique (R²) : "
            f"{typography.number(self.calm_beta.r_squared, 2)} en régime calme → "
            f"{typography.number(self.crisis_beta.r_squared, 2)} en crise "
            f"({typography.number(self.systematic_share_change, 2, signed=True)})"
            + (" — échantillon de crise trop mince" if self.crisis_beta.sample_too_thin else ""),
            f"  le beta calme prédisait "
            f"{typography.percent(self.predicted_return, 1, signed=True)}, "
            f"perte réelle "
            f"{typography.percent(self.portfolio_return, 1, signed=True)} : écart "
            f"{typography.signed_points(self.prediction_gap)}",
        ]
        if not self.coverage.is_complete:
            lignes.append(
                f"  portée : {typography.percent(self.coverage.value_share, 1)} "
                "de la valeur "
                "seulement, perte probablement sous-estimée"
            )
        return "\n".join(lignes)


def _regressed(
    brut: covariance.Beta, rendements: pd.Series | pd.DataFrame
) -> RegressedBeta:
    return RegressedBeta(
        beta=brut.beta,
        r_squared=brut.r_squared,
        standard_error=brut.standard_error,
        observations=brut.observations,
        start=rendements.index[0],
        end=rendements.index[-1],
    )


def compare_regimes(
    conn: sqlite3.Connection,
    portfolio_id: int,
    scenario: Scenario,
    *,
    window: int = DEFAULT_WINDOW,
) -> RegimeComparison:
    """Confronte le beta de régime calme à la perte réellement subie en crise."""
    poids = market_value_weights(conn, portfolio_id)
    couverture = _coverage_for(conn, poids, scenario)
    benchmark = scenario.benchmark
    base = RegimeComparison(scenario=scenario, coverage=couverture, benchmark=benchmark)

    if not couverture.has_any:
        return replace(
            base,
            unavailable_reason=(
                "aucune ligne du portefeuille n'a d'historique couvrant "
                f"{scenario.start} → {scenario.end}"
            ),
        )

    # Poids renormalisés sur les lignes couvertes. Indispensable pour le beta :
    # une série construite avec des poids sommant à 0,5 aurait une pente deux
    # fois trop faible.
    total = sum(poids.weights[t] for t in couverture.covered)
    poids_couverts = {t: poids.weights[t] / total for t in couverture.covered}
    tickers = list(poids_couverts)
    colonnes = tickers + ([benchmark] if benchmark not in poids_couverts else [])

    # ---- Crise : benchmark aligné dans le MÊME panel que les lignes détenues.
    brut_crise = load_price_panel(conn, colonnes, scenario.start, scenario.end)
    if benchmark not in brut_crise.columns:
        return replace(
            base,
            unavailable_reason=f"aucun cours du benchmark {benchmark} sur la fenêtre",
        )
    crise = align_panel(brut_crise)
    if len(crise) < 4:
        return replace(
            base,
            unavailable_reason=(
                f"{typography.sessions(len(crise))} communes seulement sur la "
                "fenêtre : "
                "trop peu pour une régression"
            ),
        )

    trajectoire = stress.buy_and_hold_value(crise[tickers], poids_couverts)
    rendement_portefeuille = stress.end_to_end_return(trajectoire)
    rendement_benchmark = float(crise[benchmark].iloc[-1] / crise[benchmark].iloc[0] - 1.0)

    quotidiens_portefeuille = simple_returns(trajectoire)
    beta_crise = _regressed(
        covariance.beta(quotidiens_portefeuille, simple_returns(crise[benchmark])),
        quotidiens_portefeuille,
    )

    # ---- Régime calme : fenêtre d'estimation récente, poids constants (Phase 4).
    calme = align_panel(load_price_panel(conn, colonnes))
    rendements_calmes = simple_returns(calme).tail(window)
    serie_calme = portfolio_returns(rendements_calmes[tickers], poids_couverts)
    beta_calme = _regressed(
        covariance.beta(serie_calme, rendements_calmes[benchmark]),
        serie_calme,
    )

    return replace(
        base,
        portfolio_return=rendement_portefeuille,
        benchmark_return=rendement_benchmark,
        amplification_ratio=regime.amplification_ratio(
            rendement_portefeuille, rendement_benchmark
        ),
        crisis_beta=beta_crise,
        calm_beta=beta_calme,
        predicted_return=regime.beta_implied_return(beta_calme.beta, rendement_benchmark),
    )


def compare_all_regimes(
    conn: sqlite3.Connection,
    portfolio_id: int,
    scenarios: tuple[Scenario, ...] = SCENARIOS,
    *,
    window: int = DEFAULT_WINDOW,
) -> list[RegimeComparison]:
    """Comparaison calme / crise pour chaque scénario du catalogue."""
    return [
        compare_regimes(conn, portfolio_id, s, window=window) for s in scenarios
    ]


# ----------------------------------------------------------------- Rapport --


def analyse_portfolio(
    conn: sqlite3.Connection,
    portfolio_id: int,
    *,
    window: int = DEFAULT_WINDOW,
    annual_risk_free: float | None = None,
    risk_free_observed_on: date | None = None,
    sortino_target_daily: float = 0.0,
    benchmark: str | None = DEFAULT_BENCHMARK,
    confidence_levels: tuple[float, ...] = (0.95, 0.99),
    monte_carlo: bool = False,
) -> RiskReport:
    """Toutes les mesures des blocs 4A et 4B sur un portefeuille.

    `benchmark=None` désactive le beta, pour un portefeuille dont l'indice de
    référence n'est pas en base.

    `monte_carlo=True` ajoute les simulations — normale et Student — ainsi que
    l'ajustement de ν par maximum de vraisemblance et la VaR Student en forme
    fermée. Désactivé par défaut : les simulations sont déterministes (graine
    fixe), mais restent un calcul qu'on ne paie que si on le demande.

    Les deux volets sont INDÉPENDANTS, et aucun ne fait tomber le rapport. Le
    Monte Carlo normal ne dépend pas de ν : un refus de la Student — moins de
    30 séances, ν au-delà de 30, ν ≤ 2 — ne l'emporte pas. Chaque volet
    indisponible porte sa propre raison (`monte_carlo_unavailable_reason`,
    `student_unavailable_reason`) : une covariance singulière et une série
    trop courte sont deux faits, et l'un ne masque pas l'autre.
    """
    serie = build_portfolio_series(
        conn, portfolio_id, window=window, benchmark=benchmark
    )

    # Une série d'un seul rendement est un objet valide — l'alignement des
    # dates se vérifie dessus —, mais aucun RAPPORT ne peut en sortir : une
    # dispersion d'échantillon demande DDOF + 1 rendements. En deçà, c'est
    # l'ÉTAT de la base qui manque, pas la requête qui est fautive, d'où
    # `PortfolioError`, que l'API rend en 409. Sans cette garde, `_sample_std`
    # levait une `ValueError`, que l'API rendait en 422.
    #
    # `window >= 2` est garanti par `build_portfolio_series` : moins de deux
    # observations veut donc dire que tout le panel aligné a servi, et qu'il
    # compte une séance de plus que de rendements.
    rendements_minimaux = DDOF + 1
    if serie.window.observations < rendements_minimaux:
        raise PortfolioError(
            "Les titres n'ont que "
            f"{typography.sessions(serie.window.observations + 1)} en commun, "
            f"il en faut au moins {rendements_minimaux + 1} : une dispersion "
            "d'échantillon demande "
            f"{typography.counted(rendements_minimaux, 'rendement')}. Vérifier "
            "la couverture avec `python -m backend.ingestion status`."
        )

    simulation_normale: dict[float, VarResult] | None = None
    raison_normale: str | None = None
    ajustement: var.StudentFit | None = None
    student_forme_fermee: dict[float, VarResult] | None = None
    student_simulee: dict[float, VarResult] | None = None
    raison_student: str | None = None
    if monte_carlo:
        # Deux blocs séparés, parce que leurs refus n'ont pas la même cause. Le
        # Monte Carlo normal ne tombe que sur une covariance non définie
        # positive — moins de séances que de lignes, une ligne en double. Le
        # volet Student tombe sur l'ajustement (séances, série constante, ν
        # au-delà de 30) ou sur ν ≤ 2, que refusent les VaR Student elles-mêmes.
        # Les graines sont propres à chaque simulation : l'ordre des blocs ne
        # change aucun chiffre.
        try:
            simulation_normale = {
                c: monte_carlo_var(serie, c) for c in confidence_levels
            }
        except ValueError as exc:
            raison_normale = str(exc)
        try:
            ajustement = student_fit(serie)
            student_forme_fermee = {
                c: student_parametric_var(serie, c, ajustement)
                for c in confidence_levels
            }
            student_simulee = {
                c: student_monte_carlo_var(serie, c, ajustement)
                for c in confidence_levels
            }
        except ValueError as exc:
            # Tout le volet ou rien : un ν ≤ 2 ajusté n'est pas publié seul.
            ajustement = student_forme_fermee = student_simulee = None
            raison_student = str(exc)

    return RiskReport(
        portfolio_id=portfolio_id,
        as_of=serie.weights.as_of,
        total_value=serie.weights.total_value,
        weights=serie.weights.weights,
        window=serie.window,
        volatility=volatility(serie),
        ewma_volatility=ewma_volatility(serie),
        drawdown=drawdown(serie),
        sharpe=sharpe(serie, annual_risk_free, risk_free_observed_on),
        sortino=sortino(serie, sortino_target_daily),
        concentration=concentration(serie.weights),
        parametric_volatility=parametric_volatility(serie),
        matrices=covariance_matrices(serie),
        historical_var={c: historical_var(serie, c) for c in confidence_levels},
        parametric_var={c: parametric_var(serie, c) for c in confidence_levels},
        expected_shortfall={
            c: expected_shortfall(serie, c) for c in confidence_levels
        },
        variance_contributions=variance_contributions(serie),
        returns=serie.returns,
        wealth=serie.wealth,
        histogram=measures.return_histogram(serie.returns),
        valuation=serie.weights,
        limiting_positions=serie.limiting_positions,
        beta=beta_vs_benchmark(serie) if benchmark else None,
        monte_carlo_var=simulation_normale,
        student_fit=ajustement,
        student_parametric_var=student_forme_fermee,
        student_monte_carlo_var=student_simulee,
        monte_carlo_unavailable_reason=raison_normale,
        student_unavailable_reason=raison_student,
    )
