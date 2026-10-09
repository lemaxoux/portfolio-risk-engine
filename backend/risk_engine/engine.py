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

from backend.langue import Langue
from backend.textes import ValeurRefusee, texte_d_erreur, textes

from . import covariance, measures, regime, stress, var
from .config import (
    DDOF,
    DEFAULT_BENCHMARK,
    DEFAULT_WINDOW,
    EWMA_LAMBDA,
    MAX_STUDENT_NU,
    MIN_DISTRIBUTION_OBSERVATIONS,
    MIN_ESTIMABLE_OBSERVATIONS,
    MIN_REGRESSION_OBSERVATIONS,
    MIN_SCENARIO_COVERAGE_SHARE,
    TRADING_DAYS_PER_MONTH,
    TRADING_DAYS_PER_YEAR,
    MONTE_CARLO_SEED,
    MONTE_CARLO_SIMULATIONS,
    daily_risk_free_rate,
    historical_var_min_observations,
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


def period_label(observations: int, langue: Langue = "fr") -> str:
    """La période couverte par `observations` séances, dite pour un lecteur :
    « ces deux dernières années », « ces trois derniers mois », « the past two
    years ».

    Convertir des séances en années est un calcul : il vit ici, et le client ne
    fait que citer le libellé. La règle, validée avec les textes de lecture :

    * à partir de 252 séances, et à moins d'un vingtième d'année d'un nombre
      entier d'années : en années ;
    * sinon, à partir de 21 séances : en mois arrondis ;
    * en deçà : en jours de bourse, le compte exact.

    C'est la règle de `rules.disclaimer._duree`, sauf en deçà d'un mois, où
    celle-ci écrirait « environ 0 mois ». Les nombres s'écrivent en lettres
    jusqu'à dix (`typography.cardinal`), suivis d'une espace insécable.

    La décision — années, mois ou jours, et combien — est ici ; l'écriture est
    dans le module de la langue (`backend/textes/<langue>/moteur.py`).
    """
    if observations < 1:
        raise ValueError(f"Au moins une séance (reçu : {observations}).")
    moteur = textes(langue).moteur
    annees = observations / TRADING_DAYS_PER_YEAR
    entieres = round(annees)
    if observations >= TRADING_DAYS_PER_YEAR and abs(annees - entieres) < 0.05:
        return moteur.periode_en_annees(entieres)
    if observations >= TRADING_DAYS_PER_MONTH:
        return moteur.periode_en_mois(round(observations / TRADING_DAYS_PER_MONTH))
    return moteur.periode_en_jours(observations)


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

    @property
    def period_label(self) -> str:
        """La période OBTENUE, dite pour un lecteur (voir `period_label`).

        Celle des séances réellement utilisées, jamais celle de la fenêtre
        demandée : une ligne cotée depuis peu ramène « ces deux dernières
        années » à « ces sept derniers jours de bourse ».
        """
        return self.periode("fr")

    def periode(self, langue: Langue = "fr") -> str:
        """La période obtenue, dans la langue demandée."""
        return period_label(self.observations, langue)

    def ecrite(self, langue: Langue = "fr") -> str:
        """La fenêtre d'une provenance : « 504 séances, 2024-09-23 → 2026-09-25 »,
        et le nombre demandé quand elle n'a pas pu être remplie."""
        return textes(langue).moteur.fenetre(
            self.observations, self.start, self.end, None if self.complete else self.requested
        )

    def __str__(self) -> str:
        return self.ecrite("fr")


@dataclass(frozen=True)
class VolatilityResult:
    """Volatilité, et sa réserve quand la fenêtre est trop courte.

    `caveat` est rédigé par `_estimation_mince` sous
    `MIN_DISTRIBUTION_OBSERVATIONS` séances : le chiffre reste publié — il
    bouge avec les données, ce n'est pas une identité —, mais il est marqué, et
    aucune règle n'en tire de conclusion.
    """

    annualised: float
    daily: float
    method: str
    window: Window
    caveat: str | None = None


@dataclass(frozen=True)
class DrawdownResult:
    """Creux maximal de la fenêtre, et ce qu'il a fallu pour s'en remettre.

    `amount` est `value` appliqué à la valeur du portefeuille au jour de la
    valorisation (`measures.amount`) : une conversion d'échelle, négative
    comme le creux, pas la perte en devise subie à l'époque.

    `recovery_date` est la première séance, après le creux, où la valeur
    retrouve son pic ; `recovery_sessions` le nombre de séances écoulées depuis
    le creux. Les deux valent None si la baisse n'est pas effacée à la fin de la
    fenêtre, ou s'il n'y a pas eu de baisse (voir `measures.recovery_after`).
    """

    value: float
    peak_date: date
    trough_date: date
    window: Window
    amount: float
    recovery_date: date | None = None
    recovery_sessions: int | None = None


@dataclass(frozen=True)
class SharpeResult:
    """Ratio de Sharpe annualisé de la série, et le taux sans risque qui le
    porte.

    `annualised` est sans unité (`measures.sharpe_ratio`, METHODOLOGY.md,
    « Sharpe and Sortino ratios ») ; `risk_free_annual` est le taux annuel
    retenu, en fraction, et `risk_free_daily` son équivalent quotidien,
    converti géométriquement (`config.daily_risk_free_rate`). Aucun champ de
    refus : sur une série dont les rendements excédentaires ont un écart-type
    nul, `measures.sharpe_ratio` lève au lieu de rendre une valeur.
    """

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
    """Ratio de Sortino annualisé de la série, ou la raison de son absence.

    `annualised` vaut None quand aucun rendement de la fenêtre ne passe sous la
    cible : la déviation à la baisse est nulle, et le ratio indéfini, pas
    infini (`measures.sortino_ratio`). `undefined_reason` le dit alors, dans
    la langue du rapport. `downside_deviation_daily` est la déviation à la
    baisse quotidienne, en fraction, non annualisée ; `target_daily` est la
    cible, un rendement quotidien (METHODOLOGY.md, « Sharpe and Sortino
    ratios »).
    """

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
        """Part de la variance du portefeuille que le benchmark n'explique
        pas : le complément à 1 de `r_squared`, en fraction. None avec lui,
        sous `MIN_ESTIMABLE_OBSERVATIONS` séances."""
        return None if self.r_squared is None else 1.0 - self.r_squared


@dataclass(frozen=True)
class VarResult:
    """Value at Risk à horizon une séance, en PERTE POSITIVE.

    Voir la convention de signe en tête de `risk_engine.var` : une valeur de
    0,021 se lit « perte d'au moins 2,1 % », une valeur négative signifie un
    gain à ce niveau de confiance.

    `nu` porte les degrés de liberté quand la VaR repose sur une loi de Student :
    une donnée du résultat, pas une mention noyée dans `detail`.

    `caveat` marque une VaR paramétrique normale estimée sur moins de
    `MIN_DISTRIBUTION_OBSERVATIONS` séances, comme `VolatilityResult.caveat`.

    `value` vaut None pour une VaR historique sur moins de 1/(1 − α) séances,
    avec `undefined_reason` : aucune séance ne tombe dans la queue, et le
    chiffre ne serait que le minimum de la fenêtre (voir
    `config.historical_var_min_observations`).

    `amount` est `value` appliqué à la valeur du portefeuille au jour de la
    valorisation (`measures.amount`), perte positive comme `value`, et None
    avec lui.
    """

    value: float | None
    confidence: float
    method: str
    window: Window
    detail: str = ""
    nu: float | None = None
    caveat: str | None = None
    undefined_reason: str | None = None
    amount: float | None = None


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

    value: float | None
    confidence: float
    tail_observations: int | None
    threshold: float | None
    window: Window
    # Refusée avec la VaR historique du même niveau, sous 1/(1 − α) séances :
    # elle moyenne une queue qui ne contient alors aucune séance.
    undefined_reason: str | None = None
    # `value` appliqué à la valeur du portefeuille (`measures.amount`), perte
    # positive comme lui, et None avec lui.
    amount: float | None = None

    @property
    def caveat(self) -> str | None:
        """La réserve permanente, en français (`reserve("fr")`) ; None sous
        99 % de confiance, ou quand la CVaR est refusée."""
        return self.reserve("fr")

    def reserve(self, langue: Langue = "fr") -> str | None:
        """La réserve permanente à 99 % et au-delà, dans la langue demandée.
        « Jours de bourse » : elle s'affiche sous une phrase de lecture qui dit
        ce mot (textes de lecture, D6 b)."""
        if self.confidence < 0.99 or self.tail_observations is None:
            return None
        return textes(langue).moteur.moyenne_de_la_queue(
            self.tail_observations, self.window.observations, 1 / self.tail_observations
        )

@dataclass(frozen=True)
class WorstDayResult:
    """La pire séance de la fenêtre, en PERTE POSITIVE comme la VaR.

    Ce n'est pas un quantile, c'est un jour qui a eu lieu. À côté de la VaR,
    il dit que le seuil n'est pas un plafond. `amount` est la perte appliquée à
    la valeur du portefeuille au jour de la valorisation (`measures.amount`).
    """

    date: date
    loss: float
    amount: float
    window: Window


@dataclass(frozen=True)
class BenchmarkName:
    """Ce que suit un indice de référence, pour une phrase de lecture.

    `label` se place après une préposition sans contraction : « pour le
    S&P 500 », « quand le S&P 500 bougeait ». `description` le présente à sa
    première apparition.
    """

    label: str
    description: str


def benchmark_name(ticker: str | None, langue: Langue = "fr") -> BenchmarkName | None:
    """Le nom lisible d'un indice de référence connu, dans la langue demandée,
    ou None.

    Un ticker absent de `universe.BENCHMARK_NAMES` n'a pas de nom inventé : la
    phrase le cite par son ticker.
    """
    noms = textes(langue).moteur.NOMS_D_INDICE
    if ticker is None or ticker not in noms:
        return None
    label, description = noms[ticker]
    return BenchmarkName(label=label, description=description)


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
    # Volatilité de l'indice de référence, sur les MÊMES séances que le
    # portefeuille (le benchmark entre dans le même panel aligné) et par la
    # même méthode. None sans indice de référence. C'est un repère pour lire
    # la volatilité du portefeuille, pas une mesure de son risque.
    benchmark_volatility: VolatilityResult | None = None
    worst_day: WorstDayResult | None = None


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
        # Un garde-fou interne : l'API ne demande jamais moins de 60 séances.
        raise ValueError(f"Fenêtre trop courte : {window} (minimum 2\u00a0séances).")

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
        raise PortfolioError(
            "prix_absents_du_panel", absents, benchmark if benchmark in absents else None
        )

    aligne = align_panel(panel)
    if len(aligne) < 2:
        raise PortfolioError("MOINS_DE_DEUX_SEANCES_COMMUNES")

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


def _estimation_mince(window: Window, langue: Langue = "fr") -> str | None:
    """Réserve d'une volatilité ou d'une VaR paramétrique sur trop peu de
    séances, ou None.

    Le chiffre n'est pas refusé : il bouge avec les données (METHODOLOGY.md,
    « Where refusal stops »). Il est MARQUÉ, et la phrase dit les deux choses
    que le lecteur doit savoir — sur combien de séances, contre quel seuil,
    CHOISI — et qu'aucune conclusion du moteur de règles n'en dépend.
    """
    if window.observations >= MIN_DISTRIBUTION_OBSERVATIONS:
        return None
    # « Jours de bourse », « courbe », « l'outil » : la réserve s'affiche à côté
    # d'une phrase de lecture, devant un lecteur qui ne connaît ni la loi
    # normale ni le moteur de règles (textes de lecture, D6 b).
    return textes(langue).moteur.estimation_mince(
        window.observations, MIN_DISTRIBUTION_OBSERVATIONS
    )


def volatility(serie: PortfolioSeries, *, langue: Langue = "fr") -> VolatilityResult:
    """Volatilité de la série du portefeuille : l'écart-type des rendements
    quotidiens, annualisé (`measures.annualised_volatility`, METHODOLOGY.md,
    « Volatility »).

    `annualised` et `daily` sont des fractions ; `daily` est la valeur
    annualisée ramenée à une séance. Sous `MIN_DISTRIBUTION_OBSERVATIONS`
    séances, le chiffre est publié et marqué (`caveat`), pas refusé.
    """
    annualisee = measures.annualised_volatility(serie.returns)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method=textes(langue).moteur.METHODE_ECART_TYPE,
        window=serie.window,
        caveat=_estimation_mince(serie.window, langue),
    )


def ewma_volatility(
    serie: PortfolioSeries, lam: float = EWMA_LAMBDA, *, langue: Langue = "fr"
) -> VolatilityResult:
    """Volatilité de la série par lissage exponentiel, convention RiskMetrics,
    annualisée (`measures.ewma_volatility`, METHODOLOGY.md, « Volatility »).

    Une prévision pour la séance qui suit la fenêtre, pas une description de
    la fenêtre. `lam` est le facteur de décroissance, `EWMA_LAMBDA` par
    défaut, écrit dans la méthode publiée. Même marque d'estimation mince que
    `volatility`.
    """
    annualisee = measures.ewma_volatility(serie.returns, lam=lam)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method=textes(langue).moteur.methode_ewma(lam),
        window=serie.window,
        caveat=_estimation_mince(serie.window, langue),
    )


def benchmark_volatility(
    serie: PortfolioSeries, *, langue: Langue = "fr"
) -> VolatilityResult | None:
    """Volatilité de l'indice de référence, sur les séances du portefeuille.

    Même méthode, même fenêtre, même réserve sous 30 séances que
    `volatility(serie)` : les deux chiffres se comparent, et rien d'autre ne
    les distingue que la série mesurée.
    """
    if serie.benchmark_returns is None:
        return None
    annualisee = measures.annualised_volatility(serie.benchmark_returns)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method=textes(langue).moteur.METHODE_ECART_TYPE,
        window=serie.window,
        caveat=_estimation_mince(serie.window, langue),
    )


def drawdown(serie: PortfolioSeries) -> DrawdownResult:
    """Creux maximal de la courbe de valeur sur la fenêtre, et le retour au
    pic.

    Mesuré sur `serie.wealth`, qui vaut 1 à la séance précédant le premier
    rendement (METHODOLOGY.md, « Maximum drawdown »). `value` est négatif ou
    nul, en fraction du plus haut atteint jusque-là ; `amount` l'applique à la
    valeur du portefeuille au jour de la valorisation, négatif comme lui. Le
    retour vaut None si la baisse n'est pas effacée à la fin de la fenêtre, ou
    s'il n'y a pas eu de baisse (`measures.recovery_after`).
    """
    brut = measures.max_drawdown(serie.wealth)
    retour = measures.recovery_after(serie.wealth, brut)
    return DrawdownResult(
        value=brut.value,
        peak_date=brut.peak_date,
        trough_date=brut.trough_date,
        window=serie.window,
        amount=measures.amount(brut.value, serie.weights.total_value),
        recovery_date=None if retour is None else retour.date,
        recovery_sessions=None if retour is None else retour.sessions,
    )


def worst_day(serie: PortfolioSeries) -> WorstDayResult:
    """La pire séance de la fenêtre, en perte positive, et son montant.

    `loss` est l'opposé du plus bas rendement de la série
    (`measures.worst_session`), en fraction ; en cas d'égalité, la première
    des séances ex æquo. `amount` l'applique à la valeur du portefeuille au
    jour de la valorisation : une conversion d'échelle, pas une perte subie ce
    jour-là (`measures.amount`).
    """
    pire = measures.worst_session(serie.returns)
    return WorstDayResult(
        date=pire.date,
        loss=pire.loss,
        amount=measures.amount(pire.loss, serie.weights.total_value),
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


def sortino(
    serie: PortfolioSeries, target_daily: float = 0.0, *, langue: Langue = "fr"
) -> SortinoResult:
    """Ratio de Sortino annualisé de la série, contre une cible quotidienne.

    `target_daily` est un rendement quotidien en fraction, zéro par défaut.
    Quand aucun rendement ne passe sous la cible, le ratio vaut None et porte
    sa raison, dans la langue demandée (METHODOLOGY.md, « Sharpe and Sortino
    ratios »).
    """
    deviation = measures.downside_deviation(serie.returns, target_daily)
    ratio = measures.sortino_ratio(serie.returns, target_daily)
    return SortinoResult(
        annualised=ratio,
        downside_deviation_daily=deviation,
        target_daily=target_daily,
        window=serie.window,
        undefined_reason=(
            None if ratio is not None else textes(langue).moteur.SORTINO_INDEFINI
        ),
    )


def concentration(poids: PortfolioWeights) -> ConcentrationResult:
    """Concentration des poids en valeur : l'indice de Herfindahl-Hirschman,
    les lignes effectives (son inverse) et la référence d'un portefeuille
    équipondéré.

    Une mesure ponctuelle, sans fenêtre, datée par `poids.as_of`
    (METHODOLOGY.md, « Concentration and effective holdings »). Lève, comme
    `measures.herfindahl_index`, sur un poids négatif ou sur des poids qui ne
    somment pas à 1.
    """
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


# Ce que chaque mesure devient sous `MIN_ESTIMABLE_OBSERVATIONS`, dit pour un
# lecteur : la raison s'affiche à la place du chiffre.
#
# Les trois mesures refusent sous le même SEUIL, pas pour la même RAISON, et une
# explication commune affirmerait de chacune ce qui n'est vrai que d'une seule :
# « le coefficient vaut ±1 » est vrai d'une corrélation et FAUX d'une pente — à
# deux séances un beta vaut n'importe quoi, 11,84 puis 8,65 sur deux fenêtres
# de la base réelle. Une explication fausse attachée à un refus juste est pire
# qu'un refus sans explication : le lecteur en tire une conclusion sur ses
# données.
#
# La raison publiée nomme donc SA mesure et le seuil, et seule la corrélation
# garde une conséquence, parce qu'elle se dit sans formule et qu'elle est
# vraie d'elle seule ; rien sur ±1 pour un beta, pas même pour le nier : ce
# serait répondre à une objection que son lecteur ne se pose pas. Les phrases
# sont dans `backend/textes/<langue>/moteur.py` (`refus_non_estimable`). La
# démonstration — à deux observations, le centrage ne laisse qu'une seule
# direction — et ses conséquences propres à chaque mesure (colinéarité,
# absence de résidu, covariance de rang 1) sont dans METHODOLOGY.md, « Two
# sample-size regimes ».


def _non_estimable(window: Window, mesure: str, langue: Langue = "fr") -> str | None:
    """Raison du refus d'estimer, ou None si la fenêtre le permet.

    Ce qui a été reçu, ce que la mesure n'est pas, et ce qu'il faut — puis la
    conséquence propre à `mesure`, quand elle se dit sans formule.
    """
    if window.observations >= MIN_ESTIMABLE_OBSERVATIONS:
        return None
    return textes(langue).moteur.refus_non_estimable(
        window.observations, mesure, MIN_ESTIMABLE_OBSERVATIONS
    )


def covariance_matrices(serie: PortfolioSeries, *, langue: Langue = "fr") -> CovarianceResult:
    """Covariance et corrélation des titres détenus, sur la fenêtre."""
    refus = _non_estimable(serie.window, "correlation", langue)
    return CovarianceResult(
        covariance=covariance.covariance_matrix(serie.asset_returns),
        correlation=(
            None if refus else covariance.correlation_matrix(serie.asset_returns)
        ),
        window=serie.window,
        correlation_undefined_reason=refus,
    )


def variance_contributions(
    serie: PortfolioSeries, *, langue: Langue = "fr"
) -> VarianceContributionResult:
    """Contribution de chaque ligne à la variance, sur la fenêtre d'estimation."""
    refus = _non_estimable(serie.window, "contributions", langue)
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


def parametric_volatility(serie: PortfolioSeries, *, langue: Langue = "fr") -> VolatilityResult:
    """Volatilité annualisée par la matrice : `√(wᵀΣw) × √252`.

    Égale à `volatility(serie)` à la tolérance flottante près — identité
    algébrique, pas approximation, garantie par la convention `DDOF` partagée.
    """
    matrice = covariance.covariance_matrix(serie.asset_returns)
    annualisee = covariance.parametric_volatility(serie.weights.weights, matrice)
    return VolatilityResult(
        annualised=annualisee,
        daily=annualisee / TRADING_DAYS_PER_YEAR**0.5,
        method=textes(langue).moteur.METHODE_MATRICE,
        window=serie.window,
        caveat=_estimation_mince(serie.window, langue),
    )


def beta_vs_benchmark(serie: PortfolioSeries, *, langue: Langue = "fr") -> BetaResult:
    """Beta et R² contre le benchmark chargé avec la série."""
    if serie.benchmark is None or serie.benchmark_returns is None:
        raise ValueError(
            "Aucun benchmark dans cette série. La construire avec "
            "`build_portfolio_series(..., benchmark=\"SPY\")`."
        )
    base = textes(langue).moteur.BASE_DU_BETA
    refus = _non_estimable(serie.window, "beta", langue)
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


def _queue_vide(window: Window, confidence: float, langue: Langue = "fr") -> str | None:
    """Raison du refus d'une mesure de queue historique, ou None.

    Sous 1/(1 − α) séances, aucune ne tombe dans la queue : le quantile n'est
    que le minimum de la fenêtre (voir `config.historical_var_min_observations`).
    La phrase dit ce qui a été reçu, ce que la queue aurait dû contenir, et ce
    qu'il faut — sans formule, en jours de bourse : elle s'affiche à la place de
    la phrase de lecture. Le même texte sert à la VaR historique et à la CVaR
    du même niveau, refusées ensemble.
    """
    minimum = historical_var_min_observations(confidence)
    if window.observations >= minimum:
        return None
    return textes(langue).moteur.refus_queue_vide(
        window.observations, 1.0 - confidence, minimum
    )


def historical_var(
    serie: PortfolioSeries, confidence: float = 0.95, *, langue: Langue = "fr"
) -> VarResult:
    """Quantile empirique, ou refus sous 1/(1 − α) séances."""
    moteur = textes(langue).moteur
    detail = moteur.detail_historique(var.QUANTILE_METHOD)
    refus = _queue_vide(serie.window, confidence, langue)
    if refus:
        return VarResult(
            value=None,
            confidence=confidence,
            method=moteur.METHODE_HISTORIQUE,
            window=serie.window,
            detail=detail,
            undefined_reason=refus,
        )
    valeur = var.historical_var(serie.returns, confidence)
    return VarResult(
        value=valeur,
        confidence=confidence,
        method=moteur.METHODE_HISTORIQUE,
        window=serie.window,
        detail=detail,
        amount=measures.amount(valeur, serie.weights.total_value),
    )


def parametric_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    include_mean: bool = False,
    *,
    langue: Langue = "fr",
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
    valeur = var.parametric_var(sigma_quotidien, confidence, moyenne)
    return VarResult(
        value=valeur,
        confidence=confidence,
        method=textes(langue).moteur.METHODE_PARAMETRIQUE,
        window=serie.window,
        detail=textes(langue).moteur.detail_normale(include_mean),
        caveat=_estimation_mince(serie.window, langue),
        amount=measures.amount(valeur, serie.weights.total_value),
    )


def expected_shortfall(
    serie: PortfolioSeries, confidence: float = 0.95, *, langue: Langue = "fr"
) -> ExpectedShortfallResult:
    """Perte moyenne de la queue, refusée avec la VaR historique du même
    niveau : elle moyenne la queue que ce quantile borne."""
    refus = _queue_vide(serie.window, confidence, langue)
    if refus:
        return ExpectedShortfallResult(
            value=None,
            confidence=confidence,
            tail_observations=None,
            threshold=None,
            window=serie.window,
            undefined_reason=refus,
        )
    brut = var.expected_shortfall(serie.returns, confidence)
    return ExpectedShortfallResult(
        value=brut.value,
        confidence=confidence,
        tail_observations=brut.tail_observations,
        threshold=brut.threshold,
        window=serie.window,
        amount=measures.amount(brut.value, serie.weights.total_value),
    )


def monte_carlo_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
    *,
    langue: Langue = "fr",
) -> VarResult:
    """VaR par simulation de rendements normaux corrélés, en perte positive :
    la vérification croisée de la VaR paramétrique (`var.monte_carlo_var`,
    METHODOLOGY.md, « Monte Carlo cross-check »).

    Graine fixe par défaut : deux appels identiques rendent le même chiffre, et
    `detail` écrit le nombre de tirages et la graine. Lève `ValeurRefusee`
    quand la covariance n'est pas définie positive ; `analyse_portfolio` en
    tire `monte_carlo_unavailable_reason`.
    """
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
        method=textes(langue).moteur.METHODE_MONTE_CARLO,
        window=serie.window,
        detail=textes(langue).moteur.detail_monte_carlo(brut.simulations, brut.seed),
        amount=measures.amount(brut.value, serie.weights.total_value),
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
    n'écrit jamais la valeur de ν — au-delà du seuil, elle ne mesure plus rien,
    et l'écrire rendrait plausible un nombre qui peut valoir 10¹⁵. Elle n'écrit
    pas non plus le caractère : Spectral, la police des phrases du moteur, n'a
    aucun glyphe grec, et le « ν » de repli se lit « v ».
    """
    ajustement = var.fit_student_t(serie.returns)
    if ajustement.nu > MAX_STUDENT_NU:
        # Une `ValueError` comme avant, dont le message est rédigé dans
        # `moteur` : `_raison_student` le rédige dans la langue de la réponse.
        raise ValeurRefusee("student_proche_de_la_normale", ajustement.observations)
    return ajustement


def student_parametric_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    fit: var.StudentFit | None = None,
    *,
    langue: Langue = "fr",
) -> VarResult:
    """VaR Student à variance ajustée, forme fermée : la cible du Monte Carlo."""
    ajustement = fit or student_fit(serie)
    matrice = covariance.covariance_matrix(serie.asset_returns)
    sigma_quotidien = covariance.parametric_volatility(
        serie.weights.weights, matrice, periods_per_year=1
    )
    valeur = var.student_t_var(sigma_quotidien, ajustement.nu, confidence)
    return VarResult(
        value=valeur,
        confidence=confidence,
        method=textes(langue).moteur.METHODE_STUDENT,
        window=serie.window,
        detail=textes(langue).moteur.detail_student(ajustement.nu, ajustement.observations),
        nu=ajustement.nu,
        amount=measures.amount(valeur, serie.weights.total_value),
    )


def student_monte_carlo_var(
    serie: PortfolioSeries,
    confidence: float = 0.95,
    fit: var.StudentFit | None = None,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
    *,
    langue: Langue = "fr",
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
        method=textes(langue).moteur.METHODE_STUDENT_MONTE_CARLO,
        window=serie.window,
        detail=textes(langue).moteur.detail_student_monte_carlo(
            ajustement.nu, ajustement.observations, brut.simulations, brut.seed
        ),
        nu=ajustement.nu,
        amount=measures.amount(brut.value, serie.weights.total_value),
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
    priverait de tout rejeu 2008. Le second est dangereux : le chiffre ne
    décrit plus qu'une partie du portefeuille et rien ne le signale. D'où le
    troisième.

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
        """Part de la valeur d'aujourd'hui que portent les lignes rejouées, en
        fraction ; zéro si la valeur totale est nulle."""
        return self.covered_value / self.total_value if self.total_value else 0.0

    @property
    def is_complete(self) -> bool:
        """Vrai si aucune ligne n'est écartée : le scénario rejoue tout le
        portefeuille."""
        return not self.excluded

    @property
    def has_any(self) -> bool:
        """Vrai si au moins une ligne est rejouée. Sinon, ni le scénario ni la
        comparaison de régimes n'ont de chiffre."""
        return bool(self.covered)

    @property
    def sufficient(self) -> bool:
        """La partie rejouée pèse-t-elle assez pour donner un chiffre principal ?

        Au moins `MIN_SCENARIO_COVERAGE_SHARE` (80 %, seuil choisi à la main,
        déclaré dans `rules.thresholds.MIN_SCENARIO_COVERAGE`) de la valeur.
        En deçà, le moteur de règles ne donne pas de chiffre pour le
        portefeuille, et une phrase de lecture ne doit pas en citer un.
        """
        return self.value_share >= MIN_SCENARIO_COVERAGE_SHARE

    @property
    def covered_count(self) -> int:
        """Nombre de lignes rejouées."""
        return len(self.covered)

    @property
    def total_count(self) -> int:
        """Nombre de lignes du portefeuille, rejouées et écartées."""
        return len(self.covered) + len(self.excluded)

    def ecrite(self, langue: Langue = "fr") -> str:
        """La portée en une ligne, dans la langue demandée."""
        return textes(langue).moteur.couverture(
            self.covered_count,
            self.total_count,
            None if self.is_complete else self.value_share,
            tuple(e.ticker for e in self.excluded),
        )

    def __str__(self) -> str:
        return self.ecrite("fr")


@dataclass(frozen=True)
class ScenarioResult:
    """Rejeu d'un épisode historique sur le portefeuille actuel.

    Deux mesures distinctes, à ne pas confondre :

    * `end_to_end_return` — ce que vaudrait le portefeuille le dernier jour de
      l'épisode, au POINT BAS du marché, qui n'est pas la sortie de la crise
      (décision D8 des textes de lecture) ;
    * `max_drawdown` — le pire moment TRAVERSÉ en cours de route, qui peut être
      nettement plus profond.

    Le drawdown est celui de la trajectoire du PORTEFEUILLE, jamais la somme des
    pires points de chaque ligne : ce dernier composerait un scénario fictif où
    toutes les lignes toucheraient leur plancher le même jour, ce qui n'arrive
    jamais et surestime la perte.

    COUVERTURE PARTIELLE — les chiffres portent sur la seule partie couverte,
    dont les poids actuels sont renormalisés à 1. La portée du chiffre est
    donnée par `coverage`, et `summary()` la rappelle systématiquement.

    CE QUE LE CHIFFRE NE DIT PAS — la perte du portefeuille ENTIER. Les lignes
    exclues n'ont pas été rejouées, et rien ici ne mesure ce qu'elles auraient
    fait : la perte de l'ensemble a pu être plus lourde ou plus légère. Deux
    traitements étaient possibles, et aucun ne comble ce manque :

    * supposer les lignes exclues stables DILUERAIT la perte dans une valeur
      qui n'a pas été rejouée ;
    * les exclure et renormaliser, option retenue, ne fabrique aucun rendement,
      mais ne décrit que la partie couverte.

    Le chiffre décrit d'autant moins le portefeuille que
    `coverage.value_share` est faible. Sous `MIN_SCENARIO_COVERAGE_SHARE`, la
    partie rejouée ne représente plus assez l'ensemble pour en tirer un chiffre
    (`ScenarioCoverage.sufficient`). Aucun texte n'affirme dans quel sens
    l'ensemble aurait différé : ce serait une généralité sur les titres
    récents, que le moteur ne mesure pas.

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
    # `end_to_end_return` appliqué à la valeur d'aujourd'hui des lignes
    # COUVERTES (`measures.amount`) : celle du portefeuille entier quand la
    # couverture est complète. Négatif pour une perte, None avec le rendement.
    # Le pire moment traversé n'a pas de montant : il se mesure depuis un plus
    # haut atteint pendant l'épisode, et le multiplier par la valeur de départ
    # ne donnerait aucune perte réelle.
    end_to_end_amount: float | None = None

    def summary(self, langue: Langue = "fr") -> str:
        """Une ligne qui ne peut pas laisser croire à une couverture totale."""
        moteur = textes(langue).moteur
        nom = self.scenario.nom(langue)
        if self.end_to_end_return is None:
            return moteur.resume_scenario_non_calculable(nom, self.unavailable_reason)
        return moteur.resume_scenario(
            nom,
            self.end_to_end_return,
            self.max_drawdown.value,
            self.observations,
            None if self.coverage.is_complete else self.coverage.value_share,
            self.end_to_end_return < 0,
        )


def assess_scenario_coverage(
    conn: sqlite3.Connection, portfolio_id: int, scenario: Scenario, *, langue: Langue = "fr"
) -> ScenarioCoverage:
    """Quelles lignes ont un historique couvrant toute la fenêtre.

    Une ligne est couverte si sa première séance en base précède le début du
    scénario et sa dernière le suit. Le critère est volontairement strict : un
    titre introduit en bourse trois jours après le sommet de 2007 n'a pas
    traversé l'épisode, et lui prêter une trajectoire partielle reviendrait à
    inventer la partie manquante.
    """
    return _coverage_for(conn, market_value_weights(conn, portfolio_id), scenario, langue)


def _coverage_for(
    conn: sqlite3.Connection,
    poids: PortfolioWeights,
    scenario: Scenario,
    langue: Langue = "fr",
) -> ScenarioCoverage:
    disponible = price_coverage(conn, poids.tickers)
    moteur = textes(langue).moteur

    couverts: list[str] = []
    exclus: list[ExcludedPosition] = []

    for ticker in poids.tickers:
        bornes = disponible.get(ticker)
        if bornes is None:
            exclus.append(
                ExcludedPosition(
                    ticker=ticker,
                    reason=moteur.EXCLUSION_SANS_COURS,
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
                    reason=moteur.exclusion_cotee_depuis(debut),
                    value=poids.values[ticker],
                    weight=poids.weights[ticker],
                    first_available=debut,
                )
            )
        elif fin < scenario.end:
            exclus.append(
                ExcludedPosition(
                    ticker=ticker,
                    reason=moteur.exclusion_plus_cotee(fin),
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
    conn: sqlite3.Connection, portfolio_id: int, scenario: Scenario, *, langue: Langue = "fr"
) -> ScenarioResult:
    """Rejoue un épisode sur le portefeuille actuel.

    Le portefeuille entre dans la fenêtre avec ses poids ACTUELS en valeur de
    marché ; les quantités qui en découlent restent ensuite figées jusqu'à la
    fin (achat-conservation), et les poids dérivent. Voir l'en-tête de
    `risk_engine.stress` pour la rupture assumée avec la Phase 4.
    """
    poids = market_value_weights(conn, portfolio_id)
    couverture = _coverage_for(conn, poids, scenario, langue)
    moteur = textes(langue).moteur
    vide = ScenarioResult(
        scenario=scenario,
        coverage=couverture,
        end_to_end_return=None,
        max_drawdown=None,
        contributions=(),
        observations=0,
    )

    # Aucune ligne n'a traversé l'épisode : la même raison pour le scénario
    # et pour la comparaison de régimes, qui s'affichent dans le même bloc.
    if not couverture.has_any:
        return replace(vide, unavailable_reason=moteur.AUCUNE_LIGNE_COTEE)

    # Poids actuels des seules lignes couvertes ; `stress` les renormalise à 1.
    poids_couverts = {t: poids.weights[t] for t in couverture.covered}
    panel = align_panel(
        load_price_panel(conn, list(poids_couverts), scenario.start, scenario.end)
    )

    if len(panel) < 2:
        return replace(vide, unavailable_reason=moteur.MOINS_DE_DEUX_JOURS_COMMUNS)

    trajectoire = stress.buy_and_hold_value(panel, poids_couverts)
    rendement = stress.end_to_end_return(trajectoire)
    return ScenarioResult(
        scenario=scenario,
        coverage=couverture,
        end_to_end_return=rendement,
        max_drawdown=measures.max_drawdown(trajectoire),
        contributions=tuple(stress.position_contributions(panel, poids_couverts)),
        observations=len(panel),
        end_to_end_amount=measures.amount(rendement, couverture.covered_value),
    )


def run_all_scenarios(
    conn: sqlite3.Connection,
    portfolio_id: int,
    scenarios: tuple[Scenario, ...] = SCENARIOS,
    *,
    langue: Langue = "fr",
) -> list[ScenarioResult]:
    """Rejoue tous les scénarios du catalogue, du plus ancien au plus récent."""
    return [run_scenario(conn, portfolio_id, s, langue=langue) for s in scenarios]


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
        """Vrai sous `min_observations` observations
        (`MIN_REGRESSION_OBSERVATIONS` par défaut, seuil choisi à la main) : la
        pente reste rendue, marquée. Le moteur de règles le lit sur le beta de
        crise : une crise ainsi marquée est citée à part et n'entre dans aucune
        conclusion (METHODOLOGY.md, « Thin crisis samples »)."""
        return self.observations < self.min_observations

    def ecrit(self, langue: Langue = "fr") -> str:
        """« 0,96 ± 0,02, R² 0,86 (355 séances) », dans la langue demandée."""
        return textes(langue).moteur.beta_regresse(
            self.beta,
            self.standard_error,
            self.r_squared,
            self.observations,
            self.min_observations if self.sample_too_thin else None,
        )

    def __str__(self) -> str:
        return self.ecrit("fr")


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
    def benchmark_label(self) -> str | None:
        """« le S&P 500 » pour SPY ; None pour un indice sans nom connu."""
        return self.nom_de_l_indice("fr")

    def nom_de_l_indice(self, langue: Langue = "fr") -> str | None:
        """Le nom lisible de l'indice de référence, dans la langue demandée
        (`benchmark_name`) ; None pour un indice sans nom connu."""
        nom = benchmark_name(self.benchmark, langue)
        return None if nom is None else nom.label

    @property
    def calm_period_label(self) -> str | None:
        """La période du régime calme, en français (`periode_calme("fr")`)."""
        return self.periode_calme("fr")

    def periode_calme(self, langue: Langue = "fr") -> str | None:
        """La période du régime calme, dite pour un lecteur (`period_label`).

        Seulement celle du régime CALME : elle se termine à la dernière séance
        en base, et « ces deux dernières années » la décrit. Une fenêtre de
        crise se termine dans le passé ; « ces 17 derniers mois » y serait
        faux.

        Ce n'est pas toujours la fenêtre d'estimation du rapport : en
        couverture partielle, le régime calme porte sur les seules lignes
        couvertes, sur leur propre historique.
        """
        return (
            None
            if self.calm_beta is None
            else period_label(self.calm_beta.observations, langue)
        )

    @property
    def prediction_gap(self) -> float | None:
        """Réalisé − prédit par le beta calme, en points de rendement."""
        if self.portfolio_return is None or self.predicted_return is None:
            return None
        return self.portfolio_return - self.predicted_return

    @property
    def ratio_beta_divergence(self) -> float | None:
        """Le ratio d'amplification moins la pente de crise, sans unité ; None
        si l'un des deux manque.

        Un écart qui n'est pas une anomalie : la pente mesure la co-variation
        quotidienne autour des moyennes, le ratio le rendement cumulé, qu'une
        dérive propre au portefeuille peut changer sans changer la pente
        (METHODOLOGY.md, « Three quantities »).
        """
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

    def summary(self, langue: Langue = "fr") -> str:
        """Le résumé de la comparaison, sur plusieurs lignes, dans la langue
        demandée : rendements du portefeuille et de l'indice, ratio, betas de
        crise et de régime calme, parts systématiques, prédiction du beta calme
        et écart, avec la mention d'un échantillon de crise trop mince. Une
        raison à la place des chiffres quand la comparaison est impossible ; la
        portée quand la couverture est partielle. Publié sous `summary`."""
        moteur = textes(langue).moteur
        nom = self.scenario.nom(langue)
        if self.unavailable_reason is not None:
            return moteur.resume_regime_impossible(nom, self.unavailable_reason)
        return moteur.resume_regime(
            nom,
            self.portfolio_return,
            self.benchmark,
            self.benchmark_return,
            self.amplification_ratio,
            self.crisis_beta.ecrit(langue),
            self.calm_beta.ecrit(langue),
            self.calm_beta.r_squared,
            self.crisis_beta.r_squared,
            self.systematic_share_change,
            self.crisis_beta.sample_too_thin,
            self.predicted_return,
            self.prediction_gap,
            None if self.coverage.is_complete else self.coverage.value_share,
            self.portfolio_return < 0,
        )


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
    langue: Langue = "fr",
) -> RegimeComparison:
    """Confronte le beta de régime calme à la perte réellement subie en crise."""
    poids = market_value_weights(conn, portfolio_id)
    couverture = _coverage_for(conn, poids, scenario, langue)
    benchmark = scenario.benchmark
    base = RegimeComparison(scenario=scenario, coverage=couverture, benchmark=benchmark)
    moteur = textes(langue).moteur

    if not couverture.has_any:
        return replace(base, unavailable_reason=moteur.AUCUNE_LIGNE_COTEE)

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
        nom = benchmark_name(benchmark, langue)
        return replace(
            base,
            unavailable_reason=moteur.pas_de_cours_de_l_indice(
                benchmark, None if nom is None else nom.label
            ),
        )
    crise = align_panel(brut_crise)
    if len(crise) < 4:
        return replace(base, unavailable_reason=moteur.jours_communs_seulement(len(crise)))

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
    langue: Langue = "fr",
) -> list[RegimeComparison]:
    """Comparaison calme / crise pour chaque scénario du catalogue."""
    return [
        compare_regimes(conn, portfolio_id, s, window=window, langue=langue)
        for s in scenarios
    ]


# ----------------------------------------------------------------- Rapport --


def _raison_monte_carlo(
    serie: PortfolioSeries, exc: ValueError, langue: Langue = "fr"
) -> str:
    """Pourquoi le Monte Carlo normal manque, dans les mots d'un particulier.

    La cause la plus fréquente est une fenêtre trop courte : n séances pour k
    lignes donnent une covariance de rang n − 1 au plus, donc singulière dès
    que n ≤ k. C'est une certitude algébrique, pas une supposition sur le
    message : dans ce cas, la raison le dit en clair. Pour toute autre cause —
    deux lignes aux rendements identiques, une variance nulle —, le message
    technique du moteur reste, parce qu'il nomme ce qu'il faut vérifier.
    """
    seances = serie.window.observations
    lignes = len(serie.weights.weights)
    if seances <= lignes:
        return textes(langue).moteur.monte_carlo_fenetre_trop_courte(seances, lignes)
    return texte_d_erreur(exc, langue)


def _raison_student(
    serie: PortfolioSeries,
    ajustement: var.StudentFit | None,
    exc: ValueError,
    langue: Langue = "fr",
) -> str:
    """Pourquoi le volet Student manque, en clair et sans écrire ν.

    Même principe que `_raison_monte_carlo`. Deux causes sont des CERTITUDES,
    lues sur la fenêtre ou sur l'ajustement et non devinées dans le message :

    * moins de `STUDENT_MIN_OBSERVATIONS` séances — le moteur ne tente pas
      l'ajustement, la longueur de la fenêtre suffit à l'expliquer ;
    * un ajustement à ν ≤ 2 — la loi n'a pas de variance finie, et la VaR
      Student à variance ajustée refuse de s'en servir.

    Le message de `var` nomme ν, en grec. Il reste tel quel pour qui appelle
    `var` directement ; publié, il passerait dans une police sans glyphe grec
    (Spectral), où le « ν » de repli se lit « v ». Toute autre cause — série
    constante, covariance d'échelle non définie positive — garde le message du
    moteur, qui n'écrit pas ν.
    """
    moteur = textes(langue).moteur
    seances = serie.window.observations
    if seances < var.STUDENT_MIN_OBSERVATIONS:
        return moteur.student_trop_peu_de_jours(var.STUDENT_MIN_OBSERVATIONS, seances)
    if ajustement is not None and ajustement.nu <= 2.0:
        return moteur.student_sans_variance_finie(seances, ajustement.nu)
    return texte_d_erreur(exc, langue)


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
    langue: Langue = "fr",
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

    `langue` est celle des textes que le rapport porte : méthodes, détails,
    réserves, raisons de refus (chantier 7D).
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
            "seances_communes_insuffisantes",
            serie.window.observations + 1,
            rendements_minimaux + 1,
            rendements_minimaux,
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
                c: monte_carlo_var(serie, c, langue=langue) for c in confidence_levels
            }
        except ValueError as exc:
            raison_normale = _raison_monte_carlo(serie, exc, langue)
        try:
            ajustement = student_fit(serie)
            student_forme_fermee = {
                c: student_parametric_var(serie, c, ajustement, langue=langue)
                for c in confidence_levels
            }
            student_simulee = {
                c: student_monte_carlo_var(serie, c, ajustement, langue=langue)
                for c in confidence_levels
            }
        except ValueError as exc:
            # La raison se lit AVANT d'effacer l'ajustement : c'est lui qui dit
            # si ν ≤ 2. Tout le volet ou rien : un ν ≤ 2 n'est pas publié seul.
            raison_student = _raison_student(serie, ajustement, exc, langue)
            ajustement = student_forme_fermee = student_simulee = None

    return RiskReport(
        portfolio_id=portfolio_id,
        as_of=serie.weights.as_of,
        total_value=serie.weights.total_value,
        weights=serie.weights.weights,
        window=serie.window,
        volatility=volatility(serie, langue=langue),
        ewma_volatility=ewma_volatility(serie, langue=langue),
        drawdown=drawdown(serie),
        sharpe=sharpe(serie, annual_risk_free, risk_free_observed_on),
        sortino=sortino(serie, sortino_target_daily, langue=langue),
        concentration=concentration(serie.weights),
        parametric_volatility=parametric_volatility(serie, langue=langue),
        matrices=covariance_matrices(serie, langue=langue),
        historical_var={
            c: historical_var(serie, c, langue=langue) for c in confidence_levels
        },
        parametric_var={
            c: parametric_var(serie, c, langue=langue) for c in confidence_levels
        },
        expected_shortfall={
            c: expected_shortfall(serie, c, langue=langue) for c in confidence_levels
        },
        variance_contributions=variance_contributions(serie, langue=langue),
        returns=serie.returns,
        wealth=serie.wealth,
        histogram=measures.return_histogram(serie.returns),
        valuation=serie.weights,
        limiting_positions=serie.limiting_positions,
        beta=beta_vs_benchmark(serie, langue=langue) if benchmark else None,
        monte_carlo_var=simulation_normale,
        student_fit=ajustement,
        student_parametric_var=student_forme_fermee,
        student_monte_carlo_var=student_simulee,
        monte_carlo_unavailable_reason=raison_normale,
        student_unavailable_reason=raison_student,
        benchmark_volatility=benchmark_volatility(serie, langue=langue),
        worst_day=worst_day(serie),
    )
