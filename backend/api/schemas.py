"""Schémas de réponse, écrits champ par champ, délibérément.

═══ POURQUOI PAS `dataclasses.asdict()` ═══

`asdict()` copie les CHAMPS d'une dataclass. Il ignore les `@property` et les
méthodes — silencieusement, sans lever quoi que ce soit. Publier le moteur à
travers un convertisseur générique produirait donc une API d'où manqueraient,
sans la moindre erreur :

* `ExpectedShortfallResult.caveat` — l'avertissement permanent du CVaR à 99 % ;
* `RegimeComparison.prediction_gap` — décrit dans sa propre docstring comme
  « le livrable » de la comparaison de régimes ;
* `RegimeComparison.systematic_share_change` — la dégradation de la
  diversification ;
* `RegimeComparison.ratio_beta_divergence` ;
* `PositionContribution.pnl` et `weight_drift` ;
* `Threshold.chosen` — le fait qu'un seuil a été choisi à la main ;
* `VarianceContributionResult.effective_positions` et
  `has_negative_contribution` ;
* `BetaResult.idiosyncratic_share` ;
* `RegressedBeta.sample_too_thin` ;
* `ScenarioCoverage.value_share`, `is_complete`, `covered_count`,
  `total_count` ;
* `Window.complete` ;
* `ScenarioResult.summary()` et `Observation.render()`, qui sont des méthodes.

Chaque schéma ci-dessous énumère donc ses champs, et un `from_*` les remplit un
à un. C'est plus long à écrire et ça se voit quand quelque chose manque.

═══ CE QUE CES SCHÉMAS NE FONT PAS ═══

Aucun calcul. Chaque nombre sort d'un attribut, d'une propriété ou d'une méthode
du moteur, déjà testés. Aucun formatage non plus : les valeurs restent des
FRACTIONS — une VaR de 1,38 % se sérialise `0.0138`. Le pourcentage, la virgule
décimale et l'arrondi sont décidés à un seul endroit, côté frontend (voir
`frontend/DESIGN.md` §6).

`allow_inf_nan=False` : un NaN ou un infini est refusé à la construction du
schéma, avec le nom du champ fautif. Sans lui, la panne se produirait plus loin,
au moment d'écrire les octets, avec un message qui ne dit pas d'où vient la
valeur. (Starlette refuse de son côté d'écrire du NaN : les deux gardes se
complètent, l'une nomme, l'autre garantit.)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.db.portfolios import PortfolioRow, PositionRow
from backend.risk_engine.engine import (
    BetaResult,
    ConcentrationResult,
    CovarianceResult,
    DrawdownResult,
    ExcludedPosition,
    ExpectedShortfallResult,
    RegimeComparison,
    RegressedBeta,
    RiskReport,
    ScenarioCoverage,
    ScenarioResult,
    SharpeResult,
    SortinoResult,
    VarianceContributionResult,
    VarResult,
    VolatilityResult,
    Window,
)
from backend.risk_engine.measures import Drawdown
from backend.risk_engine.portfolio import PortfolioWeights, Security
from backend.risk_engine.scenarios import Scenario
from backend.risk_engine.stress import PositionContribution
from backend.risk_engine.var import StudentFit
from backend.rules.disclaimer import (
    ACCEPTANCE_CONFIRMATION,
    ACCEPTANCE_TITLE,
    DisclaimerSection,
    acceptance_sections,
)
from backend.rules.rules import Observation, RulesReport
from backend.rules.thresholds import Threshold


class Schema(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


# ═══════════════════════════════════════════════════════ Provenance commune ══


class WindowOut(Schema):
    """Fenêtre d'estimation d'UNE mesure.

    Répétée sur chaque mesure, jamais hissée en tête de réponse. Le beta est
    régressé sous une contrainte d'échantillon minimal qui lui est propre, un
    scénario à couverture partielle a sa propre portée : une fenêtre unique au
    niveau du document serait un mensonge pour toute mesure qui n'utilise pas
    celle-là.
    """

    requested: int
    observations: int
    start: date
    end: date
    complete: bool = Field(
        description="Fenêtre demandée entièrement remplie (propriété du moteur)."
    )

    @classmethod
    def of(cls, window: Window) -> WindowOut:
        return cls(
            requested=window.requested,
            observations=window.observations,
            start=window.start,
            end=window.end,
            complete=window.complete,
        )


class MatrixOut(Schema):
    """Matrice carrée étiquetée : `tickers` gouverne l'ordre des `values`.

    `values[i][j]` est la cellule (tickers[i], tickers[j]). Une matrice de
    corrélation est symétrique et sa diagonale vaut 1 : si les libellés et les
    valeurs se désalignaient, la carte de chaleur resterait plausible et
    deviendrait fausse en silence. D'où l'extraction cellule par cellule, par
    COUPLE D'ÉTIQUETTES, dans `of` — l'alignement n'est pas vérifié, il est
    impossible à rater.
    """

    tickers: list[str]
    values: list[list[float]]

    @classmethod
    def of(cls, frame) -> MatrixOut:
        tickers = [str(colonne) for colonne in frame.columns]
        return cls(
            tickers=tickers,
            values=[
                [float(frame.at[ligne, colonne]) for colonne in tickers]
                for ligne in tickers
            ],
        )


# ═══════════════════════════════════════════════════════════════ Catalogue ══


class MetaOut(Schema):
    """État de la base, pas de l'horloge.

    `as_of` est la dernière séance PRÉSENTE EN BASE. Ce n'est pas la date du
    jour : un week-end, un jour férié ou une ingestion en panne la laissent en
    arrière, et c'est précisément cet écart qu'il faut pouvoir voir.

    À ne pas confondre avec l'`as_of` d'une analyse, qui est la date de
    valorisation d'un portefeuille donné — la plus ancienne des dernières
    clôtures de ses lignes — et peut donc être antérieure à celle-ci.
    """

    as_of: date | None
    securities_count: int


class SecurityOut(Schema):
    ticker: str
    name: str
    sector: str | None
    first_price_date: date | None
    last_price_date: date | None
    has_prices: bool

    @classmethod
    def of(cls, security: Security) -> SecurityOut:
        return cls(
            ticker=security.ticker,
            name=security.name,
            sector=security.sector,
            first_price_date=security.first_price_date,
            last_price_date=security.last_price_date,
            has_prices=security.has_prices,
        )


# ═══════════════════════════════════════════════════════════ Portefeuilles ══


class PortfolioCreate(Schema):
    name: str = Field(min_length=1, max_length=120, default="Portefeuille")
    owner: str = Field(min_length=1, max_length=120, default="local")


class PositionIn(Schema):
    ticker: str = Field(min_length=1, max_length=20)
    quantity: float
    cost_basis: float | None = None


class PositionsReplace(Schema):
    positions: list[PositionIn]


class PortfolioOut(Schema):
    """Le portefeuille tel qu'il est stocké.

    `updated_at` date le dernier remplacement des POSITIONS, jamais la création.
    `null` se lit « jamais modifié depuis l'application » — ce qui est vrai d'un
    portefeuille encore vide, et vrai des lignes antérieures à la migration,
    pour lesquelles la date est réellement inconnue.
    """

    id: int
    name: str
    owner: str
    updated_at: date | None

    @classmethod
    def of(cls, row: PortfolioRow) -> PortfolioOut:
        return cls(
            id=row.id, name=row.name, owner=row.owner, updated_at=row.updated_at
        )


class ValuedPositionOut(Schema):
    """Une ligne valorisée à la dernière clôture connue.

    `price` est la clôture BRUTE (`close`) et non la clôture ajustée : c'est un
    prix auquel on peut traiter, là où `adj_close` est un indice de performance
    totale rebasé à chaque dividende, réservé aux rendements. Voir
    `risk_engine.portfolio.latest_closes`.

    Aucune plus-value n'est publiée ici, bien que `cost_basis` soit disponible :
    la calculer serait de l'arithmétique dans la couche API. Si elle devient
    utile, elle sera ajoutée au moteur avec son test.
    """

    ticker: str
    quantity: float
    cost_basis: float | None
    price: float
    value: float
    weight: float


class ValuationOut(Schema):
    as_of: date
    total_value: float
    positions: list[ValuedPositionOut]

    @classmethod
    def of(
        cls, weights: PortfolioWeights, positions: Sequence[PositionRow]
    ) -> ValuationOut:
        """Croise les poids du moteur et les positions stockées, par ticker.

        La quantité est RELUE en base ; elle n'est pas retrouvée en divisant la
        valeur par le prix. Le résultat serait presque toujours le même, et
        « presque » est le problème : ce serait un calcul de la couche API, donc
        une quantité affichée que rien n'a testée.
        """
        quantites = {p.ticker: p for p in positions}
        return cls(
            as_of=weights.as_of,
            total_value=weights.total_value,
            positions=[
                ValuedPositionOut(
                    ticker=ticker,
                    quantity=quantites[ticker].quantity,
                    cost_basis=quantites[ticker].cost_basis,
                    price=weights.prices[ticker],
                    value=weights.values[ticker],
                    weight=weights.weights[ticker],
                )
                for ticker in weights.tickers
            ],
        )


class PortfolioDetailOut(Schema):
    """Portefeuille et sa valorisation.

    `valuation` est `null` quand le portefeuille existe mais n'est pas
    valorisable — aucune position, aucun prix pour une ligne. `valuation_error`
    porte alors le message du moteur, qui dit quoi faire. Les deux champs
    voyagent ensemble : un `null` seul serait un blanc inexpliqué.

    Cette tolérance vaut pour la LISTE, où un portefeuille cassé ne doit pas
    priver des autres. Interrogé seul, un portefeuille non valorisable répond en
    409 : c'est la ressource demandée qui est en cause.
    """

    id: int
    name: str
    owner: str
    updated_at: date | None
    valuation: ValuationOut | None
    valuation_error: str | None


class PositionsWrittenOut(Schema):
    portfolio_id: int
    positions_count: int
    updated_at: date
    replaced: bool = Field(
        default=True,
        description=(
            "L'écriture remplace TOUTES les positions du portefeuille ; "
            "elle n'ajoute jamais aux lignes existantes."
        ),
    )


class CsvSourceOut(Schema):
    """Comment le fichier a été lu. C'est de la provenance, pas du décor.

    Un utilisateur qui voit « lu en cp1252, séparateur `;`, décimale `,` »
    comprend un résultat inattendu au lieu de le subir. Ces trois choix sont
    devinés à partir des octets : ils doivent donc être affichables.
    """

    filename: str | None
    encoding: Literal["utf-8", "utf-8-sig", "cp1252"]
    delimiter: Literal[",", ";"]
    decimal_separator: Literal[".", ","]
    rows_read: int


class CsvImportOut(PositionsWrittenOut):
    source: CsvSourceOut


# ═══════════════════════════════════════════════════════════════ Mesures ══


class VolatilityOut(Schema):
    annualised: float
    daily: float
    method: str
    window: WindowOut

    @classmethod
    def of(cls, result: VolatilityResult) -> VolatilityOut:
        return cls(
            annualised=result.annualised,
            daily=result.daily,
            method=result.method,
            window=WindowOut.of(result.window),
        )


class DrawdownOut(Schema):
    value: float
    peak_date: date
    trough_date: date
    window: WindowOut

    @classmethod
    def of(cls, result: DrawdownResult) -> DrawdownOut:
        return cls(
            value=result.value,
            peak_date=result.peak_date,
            trough_date=result.trough_date,
            window=WindowOut.of(result.window),
        )


class TrajectoryDrawdownOut(Schema):
    """Drawdown d'une trajectoire de scénario : pas de fenêtre d'estimation.

    Il ne s'estime sur rien — c'est la lecture directe du pire moment traversé
    par une trajectoire bornée par le scénario. Les niveaux sont en base 1 au
    premier jour de l'épisode (voir `risk_engine.stress`).
    """

    value: float
    peak_date: date
    trough_date: date
    peak_level: float
    trough_level: float

    @classmethod
    def of(cls, drawdown: Drawdown) -> TrajectoryDrawdownOut:
        return cls(
            value=drawdown.value,
            peak_date=drawdown.peak_date,
            trough_date=drawdown.trough_date,
            peak_level=drawdown.peak_level,
            trough_level=drawdown.trough_level,
        )


class SharpeOut(Schema):
    annualised: float
    risk_free_annual: float
    risk_free_daily: float
    risk_free_observed_on: date | None
    window: WindowOut

    @classmethod
    def of(cls, result: SharpeResult) -> SharpeOut:
        return cls(
            annualised=result.annualised,
            risk_free_annual=result.risk_free_annual,
            risk_free_daily=result.risk_free_daily,
            risk_free_observed_on=result.risk_free_observed_on,
            window=WindowOut.of(result.window),
        )


class SortinoOut(Schema):
    """Sortino, éventuellement indéfini — et alors il le DIT.

    `annualised: null` accompagné de `undefined_reason` : jamais un champ
    absent, jamais un zéro. Un zéro se lirait « ratio nul », c'est-à-dire un
    portefeuille sans excédent de rendement, alors que l'indéfinition dit
    l'inverse — aucun rendement sous la cible sur la fenêtre. C'est la raison
    pour laquelle `response_model_exclude_none` est banni de cette API : il
    supprimerait exactement le champ qui explique le blanc.
    """

    annualised: float | None
    downside_deviation_daily: float
    target_daily: float
    undefined_reason: str | None
    window: WindowOut

    @classmethod
    def of(cls, result: SortinoResult) -> SortinoOut:
        return cls(
            annualised=result.annualised,
            downside_deviation_daily=result.downside_deviation_daily,
            target_daily=result.target_daily,
            undefined_reason=result.undefined_reason,
            window=WindowOut.of(result.window),
        )


class ConcentrationOut(Schema):
    """Mesure PONCTUELLE : porte une date de valorisation, pas une fenêtre.

    Lui attacher une fenêtre laisserait croire à une moyenne dans le temps. Sa
    provenance est `as_of` — la date des prix qui ont produit les poids.
    """

    hhi: float
    effective_positions: float
    equal_weight_reference: float
    n_positions: int
    as_of: date

    @classmethod
    def of(cls, result: ConcentrationResult) -> ConcentrationOut:
        return cls(
            hhi=result.hhi,
            effective_positions=result.effective_positions,
            equal_weight_reference=result.equal_weight_reference,
            n_positions=result.n_positions,
            as_of=result.as_of,
        )


class MatricesOut(Schema):
    covariance: MatrixOut
    correlation: MatrixOut
    ddof: int
    window: WindowOut

    @classmethod
    def of(cls, result: CovarianceResult) -> MatricesOut:
        return cls(
            covariance=MatrixOut.of(result.covariance),
            correlation=MatrixOut.of(result.correlation),
            ddof=result.ddof,
            window=WindowOut.of(result.window),
        )


class ContributionOut(Schema):
    """Part de variance d'une ligne, à côté de sa part de capital.

    Les trois nombres voyagent dans le MÊME objet plutôt qu'en tableaux
    parallèles : un objet par ligne ne peut pas se désaligner. `excess_over_weight`
    vient de la méthode du moteur, pas d'une soustraction faite ici.
    """

    ticker: str
    contribution: float
    weight: float
    excess_over_weight: float


class VarianceContributionsOut(Schema):
    tickers: list[str]
    contributions: list[ContributionOut]
    effective_positions: float
    has_negative_contribution: bool
    window: WindowOut

    @classmethod
    def of(
        cls, result: VarianceContributionResult, tickers: list[str]
    ) -> VarianceContributionsOut:
        return cls(
            tickers=tickers,
            contributions=[
                ContributionOut(
                    ticker=ticker,
                    contribution=result.contributions[ticker],
                    weight=result.weights[ticker],
                    excess_over_weight=result.excess_over_weight(ticker),
                )
                for ticker in tickers
            ],
            effective_positions=result.effective_positions,
            has_negative_contribution=result.has_negative_contribution,
            window=WindowOut.of(result.window),
        )


class BetaOut(Schema):
    beta: float
    r_squared: float
    idiosyncratic_share: float
    benchmark: str
    basis: str
    window: WindowOut

    @classmethod
    def of(cls, result: BetaResult) -> BetaOut:
        return cls(
            beta=result.beta,
            r_squared=result.r_squared,
            idiosyncratic_share=result.idiosyncratic_share,
            benchmark=result.benchmark,
            basis=result.basis,
            window=WindowOut.of(result.window),
        )


class VarOut(Schema):
    """VaR à horizon une séance, en PERTE POSITIVE et en FRACTION.

    `0.0138` se lit « perte d'au moins 1,38 % ». Une valeur négative signifie un
    gain à ce niveau de confiance. `nu` est `null` hors loi de Student : c'est
    une donnée du résultat, pas une mention noyée dans `detail`.
    """

    value: float
    confidence: float
    method: str
    detail: str
    nu: float | None
    window: WindowOut

    @classmethod
    def of(cls, result: VarResult) -> VarOut:
        return cls(
            value=result.value,
            confidence=result.confidence,
            method=result.method,
            detail=result.detail,
            nu=result.nu,
            window=WindowOut.of(result.window),
        )

    @classmethod
    def optional(cls, result: VarResult | None) -> VarOut | None:
        return None if result is None else cls.of(result)


class ExpectedShortfallOut(Schema):
    """CVaR, avec la taille de la queue qu'il moyenne et son avertissement.

    `caveat` est une `@property` du moteur, allumée en PERMANENCE à 99 % et
    au-delà : à ce niveau la queue ne compte que 1 % de la fenêtre, ce n'est pas
    une anomalie mais la structure du chiffre. Un convertisseur générique
    l'aurait perdue sans rien signaler.
    """

    value: float
    confidence: float
    tail_observations: int
    threshold: float
    caveat: str | None
    window: WindowOut

    @classmethod
    def of(cls, result: ExpectedShortfallResult) -> ExpectedShortfallOut:
        return cls(
            value=result.value,
            confidence=result.confidence,
            tail_observations=result.tail_observations,
            threshold=result.threshold,
            caveat=result.caveat,
            window=WindowOut.of(result.window),
        )


class StudentFitOut(Schema):
    nu: float
    loc: float
    scale: float
    log_likelihood: float
    observations: int

    @classmethod
    def of(cls, fit: StudentFit) -> StudentFitOut:
        return cls(
            nu=fit.nu,
            loc=fit.loc,
            scale=fit.scale,
            log_likelihood=fit.log_likelihood,
            observations=fit.observations,
        )


class TailRiskLevelOut(Schema):
    """Toutes les mesures de queue d'UN niveau de confiance, dans un seul objet.

    La VaR normale et sa contrepartie Student sont voisines de champ, parce que
    l'écart entre les deux chiffre le coût de l'hypothèse de normalité : afficher
    la normale seule la ferait passer pour le dernier mot. Quand le volet Student
    est indisponible, ces champs valent `null` et
    `TailRiskOut.student_unavailable_reason` dit pourquoi, en toutes lettres.
    """

    confidence: float
    historical_var: VarOut
    parametric_var: VarOut
    monte_carlo_var: VarOut | None
    student_parametric_var: VarOut | None
    student_monte_carlo_var: VarOut | None
    expected_shortfall: ExpectedShortfallOut


class TailRiskOut(Schema):
    levels: list[TailRiskLevelOut]
    student_fit: StudentFitOut | None
    student_unavailable_reason: str | None

    @classmethod
    def of(cls, report: RiskReport, student_reason: str | None) -> TailRiskOut:
        def _niveau(confiance: float, source: dict | None) -> VarResult | None:
            return None if source is None else source.get(confiance)

        return cls(
            levels=[
                TailRiskLevelOut(
                    confidence=confiance,
                    historical_var=VarOut.of(report.historical_var[confiance]),
                    parametric_var=VarOut.of(report.parametric_var[confiance]),
                    monte_carlo_var=VarOut.optional(
                        _niveau(confiance, report.monte_carlo_var)
                    ),
                    student_parametric_var=VarOut.optional(
                        _niveau(confiance, report.student_parametric_var)
                    ),
                    student_monte_carlo_var=VarOut.optional(
                        _niveau(confiance, report.student_monte_carlo_var)
                    ),
                    expected_shortfall=ExpectedShortfallOut.of(
                        report.expected_shortfall[confiance]
                    ),
                )
                for confiance in sorted(report.historical_var)
            ],
            student_fit=(
                None
                if report.student_fit is None
                else StudentFitOut.of(report.student_fit)
            ),
            student_unavailable_reason=student_reason,
        )


class WeightOut(Schema):
    ticker: str
    weight: float


class RiskOut(Schema):
    volatility: VolatilityOut
    ewma_volatility: VolatilityOut
    parametric_volatility: VolatilityOut
    drawdown: DrawdownOut
    sharpe: SharpeOut
    sortino: SortinoOut
    concentration: ConcentrationOut
    matrices: MatricesOut
    variance_contributions: VarianceContributionsOut
    beta: BetaOut | None
    tail_risk: TailRiskOut

    @classmethod
    def of(
        cls, report: RiskReport, tickers: list[str], student_reason: str | None
    ) -> RiskOut:
        return cls(
            volatility=VolatilityOut.of(report.volatility),
            ewma_volatility=VolatilityOut.of(report.ewma_volatility),
            parametric_volatility=VolatilityOut.of(report.parametric_volatility),
            drawdown=DrawdownOut.of(report.drawdown),
            sharpe=SharpeOut.of(report.sharpe),
            sortino=SortinoOut.of(report.sortino),
            concentration=ConcentrationOut.of(report.concentration),
            matrices=MatricesOut.of(report.matrices),
            variance_contributions=VarianceContributionsOut.of(
                report.variance_contributions, tickers
            ),
            beta=None if report.beta is None else BetaOut.of(report.beta),
            tail_risk=TailRiskOut.of(report, student_reason),
        )


# ═══════════════════════════════════════════════════════════════ Scénarios ══


class ScenarioDefOut(Schema):
    key: str
    name: str
    start: date
    end: date
    benchmark: str
    description: str
    calendar_days: int

    @classmethod
    def of(cls, scenario: Scenario) -> ScenarioDefOut:
        return cls(
            key=scenario.key,
            name=scenario.name,
            start=scenario.start,
            end=scenario.end,
            benchmark=scenario.benchmark,
            description=scenario.description,
            calendar_days=scenario.calendar_days,
        )


class ExcludedPositionOut(Schema):
    ticker: str
    reason: str
    value: float
    weight: float
    first_available: date | None

    @classmethod
    def of(cls, excluded: ExcludedPosition) -> ExcludedPositionOut:
        return cls(
            ticker=excluded.ticker,
            reason=excluded.reason,
            value=excluded.value,
            weight=excluded.weight,
            first_available=excluded.first_available,
        )


class CoverageOut(Schema):
    """Quelle part du portefeuille le scénario a réellement pu couvrir.

    `value_share` est une fraction de la VALEUR, pas une fraction des lignes :
    écarter une ligne à 1 % et une ligne à 40 % n'ont pas la même portée, alors
    que « 5 lignes sur 6 » se dirait pareil. Le biais est orienté — la partie
    exclue est plus récente, donc en moyenne plus spéculative —, ce qui rend la
    perte affichée vraisemblablement optimiste à mesure que `value_share` baisse.
    """

    covered: list[str]
    excluded: list[ExcludedPositionOut]
    covered_value: float
    total_value: float
    value_share: float
    is_complete: bool
    covered_count: int
    total_count: int

    @classmethod
    def of(cls, coverage: ScenarioCoverage) -> CoverageOut:
        return cls(
            covered=list(coverage.covered),
            excluded=[ExcludedPositionOut.of(e) for e in coverage.excluded],
            covered_value=coverage.covered_value,
            total_value=coverage.total_value,
            value_share=coverage.value_share,
            is_complete=coverage.is_complete,
            covered_count=coverage.covered_count,
            total_count=coverage.total_count,
        )


class PositionContributionOut(Schema):
    ticker: str
    start_value: float
    end_value: float
    own_return: float
    contribution: float
    start_weight: float
    end_weight: float
    pnl: float
    weight_drift: float

    @classmethod
    def of(cls, contribution: PositionContribution) -> PositionContributionOut:
        return cls(
            ticker=contribution.ticker,
            start_value=contribution.start_value,
            end_value=contribution.end_value,
            own_return=contribution.own_return,
            contribution=contribution.contribution,
            start_weight=contribution.start_weight,
            end_weight=contribution.end_weight,
            pnl=contribution.pnl,
            weight_drift=contribution.weight_drift,
        )


class ScenarioOut(Schema):
    """Un scénario, c'est trois chiffres indissociables.

    `end_to_end_return` (ce que vaudrait le portefeuille à la SORTIE),
    `max_drawdown` (le pire moment TRAVERSÉ, souvent plus profond) et
    `coverage.value_share` (la portée du chiffre) sont trois champs requis du
    même objet. Aucun ne peut être servi sans les autres, et les deux premiers
    valent `null` ensemble quand aucune ligne n'est couverte —
    `unavailable_reason` dit alors pourquoi.
    """

    scenario: ScenarioDefOut
    coverage: CoverageOut
    end_to_end_return: float | None
    max_drawdown: TrajectoryDrawdownOut | None
    contributions: list[PositionContributionOut]
    observations: int
    unavailable_reason: str | None
    summary: str

    @classmethod
    def of(cls, result: ScenarioResult) -> ScenarioOut:
        return cls(
            scenario=ScenarioDefOut.of(result.scenario),
            coverage=CoverageOut.of(result.coverage),
            end_to_end_return=result.end_to_end_return,
            max_drawdown=(
                None
                if result.max_drawdown is None
                else TrajectoryDrawdownOut.of(result.max_drawdown)
            ),
            contributions=[
                PositionContributionOut.of(c) for c in result.contributions
            ],
            observations=result.observations,
            unavailable_reason=result.unavailable_reason,
            summary=result.summary(),
        )


# ═══════════════════════════════════════════════════════════════ Régimes ══


class RegressedBetaOut(Schema):
    """Beta régressé sur une fenêtre datée, avec son incertitude.

    Porte `observations`, `start` et `end` directement plutôt qu'un objet
    `Window` : le moteur ne lui en attache pas, et en fabriquer un ici
    inventerait une fenêtre « demandée » qui n'a jamais été demandée.
    """

    beta: float
    r_squared: float
    standard_error: float | None
    observations: int
    start: date
    end: date
    min_observations: int
    sample_too_thin: bool

    @classmethod
    def of(cls, result: RegressedBeta) -> RegressedBetaOut:
        return cls(
            beta=result.beta,
            r_squared=result.r_squared,
            standard_error=result.standard_error,
            observations=result.observations,
            start=result.start,
            end=result.end,
            min_observations=result.min_observations,
            sample_too_thin=result.sample_too_thin,
        )

    @classmethod
    def optional(cls, result: RegressedBeta | None) -> RegressedBetaOut | None:
        return None if result is None else cls.of(result)


class RegimeOut(Schema):
    """Le beta de régime calme a-t-il prédit la perte subie pendant la crise ?

    `prediction_gap` (réalisé − prédit) est LE LIVRABLE de cette comparaison,
    d'après la docstring du moteur, et c'est une `@property` : un convertisseur
    générique aurait publié cette section sans elle, sans erreur.
    `systematic_share_change` et `ratio_beta_divergence` sont dans le même cas.
    """

    scenario: ScenarioDefOut
    coverage: CoverageOut
    benchmark: str
    portfolio_return: float | None
    benchmark_return: float | None
    amplification_ratio: float | None
    crisis_beta: RegressedBetaOut | None
    calm_beta: RegressedBetaOut | None
    predicted_return: float | None
    prediction_gap: float | None
    ratio_beta_divergence: float | None
    systematic_share_change: float | None
    unavailable_reason: str | None
    summary: str

    @classmethod
    def of(cls, result: RegimeComparison) -> RegimeOut:
        return cls(
            scenario=ScenarioDefOut.of(result.scenario),
            coverage=CoverageOut.of(result.coverage),
            benchmark=result.benchmark,
            portfolio_return=result.portfolio_return,
            benchmark_return=result.benchmark_return,
            amplification_ratio=result.amplification_ratio,
            crisis_beta=RegressedBetaOut.optional(result.crisis_beta),
            calm_beta=RegressedBetaOut.optional(result.calm_beta),
            predicted_return=result.predicted_return,
            prediction_gap=result.prediction_gap,
            ratio_beta_divergence=result.ratio_beta_divergence,
            systematic_share_change=result.systematic_share_change,
            unavailable_reason=result.unavailable_reason,
            summary=result.summary(),
        )


# ═══════════════════════════════════════════════════════════ Observations ══


class ThresholdOut(Schema):
    """Un seuil et sa provenance, lisible par une machine.

    `kind` est un champ MACHINE, pas une chaîne à analyser : le client distingue
    un seuil choisi à la main d'un seuil dérivé sans chercher le mot « CHOISI »
    dans du texte français. `rendered` reste disponible pour l'affichage, mais
    aucune décision d'interface ne doit dépendre de son contenu.
    """

    name: str
    kind: Literal["derived", "portfolio_relative", "chosen"]
    value: float
    rationale: str
    percent: bool
    chosen: bool
    rendered: str

    @classmethod
    def of(cls, threshold: Threshold) -> ThresholdOut:
        return cls(
            name=threshold.name,
            kind=threshold.kind.name.lower(),
            value=threshold.value,
            rationale=threshold.rationale,
            percent=threshold.percent,
            chosen=threshold.chosen,
            rendered=str(threshold),
        )


class ObservationOut(Schema):
    """Une propriété chiffrée du portefeuille. Elle décrit, elle ne prescrit pas.

    `rule` est l'identifiant machine, `rule_label` le libellé français.
    `facts` porte les mêmes chiffres que `statement`, sous forme exploitable.
    `thresholds` est vide quand la mesure parle d'elle-même — ce n'est pas un
    oubli, c'est une absence de seuil assumée par le moteur de règles.
    """

    rule: str
    rule_label: str
    subject: str
    statement: str
    facts: dict[str, int | float | str | None]
    provenance: str
    thresholds: list[ThresholdOut]
    uses_chosen_threshold: bool
    rendered: str

    @classmethod
    def of(cls, observation: Observation) -> ObservationOut:
        return cls(
            rule=observation.rule.name.lower(),
            rule_label=observation.rule.value,
            subject=observation.subject,
            statement=observation.statement,
            facts=dict(observation.facts),
            provenance=observation.provenance,
            thresholds=[ThresholdOut.of(s) for s in observation.thresholds],
            uses_chosen_threshold=observation.uses_chosen_threshold,
            rendered=observation.render(),
        )


class DisclaimerSectionOut(Schema):
    title: str
    body: str

    @classmethod
    def of(cls, section: DisclaimerSection) -> DisclaimerSectionOut:
        return cls(title=section.title, body=section.body)


class DisclaimerOut(Schema):
    """Le bandeau d'acceptation, structuré ET à plat.

    Les sections servent à la mise en page ; `text` est le même contenu en un
    bloc, tel que le moteur de règles l'attache à son rapport. La fenêtre citée
    dans le texte est celle qui a été DEMANDÉE pour cette analyse : le texte ne
    peut donc pas annoncer une durée que le calcul n'a pas utilisée.
    """

    title: str
    sections: list[DisclaimerSectionOut]
    confirmation: str
    text: str

    @classmethod
    def of(cls, rules_report: RulesReport, window: int) -> DisclaimerOut:
        return cls(
            title=ACCEPTANCE_TITLE,
            sections=[
                DisclaimerSectionOut.of(s) for s in acceptance_sections(window)
            ],
            confirmation=ACCEPTANCE_CONFIRMATION,
            text=rules_report.disclaimer,
        )


# ═══════════════════════════════════════════════════════════════ Analyse ══


class ParametersOut(Schema):
    """Ce qui a été DEMANDÉ, pas ce qui a été utilisé.

    Aucune fenêtre effective ici : chaque mesure porte la sienne, et une fenêtre
    hissée en tête de document serait fausse pour toute mesure qui n'utilise pas
    celle-là. `window` est le nombre de séances demandé au moteur ; le nombre
    réellement obtenu se lit sur `window.observations` de chaque mesure.
    """

    window: int
    benchmark: str | None
    confidence_levels: list[float]


class AnalysisOut(Schema):
    """Rapport complet d'un portefeuille : UNE réponse, UN `as_of`.

    Découper l'analyse en quatre endpoints ferait décrire deux dates différentes
    à la section « volatilité » et à la section « scénarios » si la base était
    rafraîchie entre deux appels, sans que rien ne le signale. Une seule réponse
    garantit que toute la page parle du même instant.

    `as_of` est la date de VALORISATION de ce portefeuille : la plus ancienne des
    dernières clôtures de ses lignes, jamais la date du jour. Elle peut être
    antérieure à l'`as_of` de la base (`GET /api/meta`) si une ligne a cessé
    d'être mise à jour.

    `tickers` est l'ordre canonique de la réponse : celui des matrices, des poids
    et des contributions à la variance.
    """

    portfolio_id: int
    portfolio: PortfolioOut
    as_of: date
    total_value: float
    tickers: list[str]
    weights: list[WeightOut]
    parameters: ParametersOut
    risk: RiskOut
    scenarios: list[ScenarioOut]
    regimes: list[RegimeOut]
    observations: list[ObservationOut]
    disclaimer: DisclaimerOut
