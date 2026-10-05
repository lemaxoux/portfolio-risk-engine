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

═══ LE TEXTE RÉDIGÉ EST COMPOSÉ À LA PUBLICATION ═══

Un champ de PROSE — raison, phrase, réserve, provenance — est typé `Texte` :
`typography.prose` y rend insécables les espaces avant « : » et dans les
guillemets. Seules les espaces changent. Les identifiants et les données de
l'utilisateur (ticker, nom d'un portefeuille, nom de fichier, exemple de CSV)
restent des `str` : on ne retouche pas ce que quelqu'un a saisi.

`allow_inf_nan=False` : un NaN ou un infini est refusé à la construction du
schéma, avec le nom du champ fautif. Sans lui, la panne se produirait plus loin,
au moment d'écrire les octets, avec un message qui ne dit pas d'où vient la
valeur. (Starlette refuse de son côté d'écrire du NaN : les deux gardes se
complètent, l'une nomme, l'autre garantit.)
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from backend import typography

from backend.db.portfolios import PortfolioRow, PositionRow
from backend.risk_engine.engine import (
    BetaResult,
    ConcentrationResult,
    CovarianceResult,
    DrawdownResult,
    ExcludedPosition,
    ExpectedShortfallResult,
    LimitingPosition,
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
    WorstDayResult,
)
from backend.risk_engine.measures import Drawdown
from backend.risk_engine.portfolio import PortfolioWeights, Security
from backend.risk_engine.scenarios import Scenario
from backend.risk_engine.stress import PositionContribution
from backend.risk_engine.var import StudentFit
from backend.risk_engine.config import DEFAULT_WINDOW, PRICE_CURRENCY
from backend.rules.disclaimer import (
    ACCEPTANCE_CONFIRMATION,
    ACCEPTANCE_TITLE,
    DisclaimerSection,
    acceptance_sections,
    acceptance_text,
)
from backend.rules.rules import Observation, RulesReport
from backend.rules.thresholds import Threshold


class Schema(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")


# Un texte RÉDIGÉ par le moteur, les règles ou le bandeau, composé à la
# publication (voir l'en-tête de ce module).
Texte = Annotated[str, AfterValidator(typography.prose)]

# Le libellé de période voyage À CÔTÉ de la fenêtre qu'il décrit, dans l'objet
# de la mesure, et non dans `WindowOut` : la forme d'une fenêtre est figée par
# les tests (cinq champs, partout dans la réponse).
DESCRIPTION_PERIODE = (
    "La période de `window`, dite pour un lecteur : « ces deux dernières "
    "années ». Rédigée par le moteur (`engine.period_label`), d'après les "
    "séances obtenues."
)
DESCRIPTION_MONTANT = (
    "`value` appliqué à la valeur du portefeuille au jour de la valorisation, "
    "dans la devise de `valuation.currency`, même signe que `value`. Une "
    "conversion d'échelle, pas une perte reconstituée."
)


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
    price_currency: str = Field(
        description=(
            "Code ISO 4217 de la devise de tous les prix en base. Hypothèse du "
            "périmètre v1 (titres cotés aux États-Unis, cours Tiingo), pas une "
            "donnée lue ligne à ligne : aucune conversion n'est faite."
        )
    )


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
    line: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Numéro de la ligne telle que l'utilisateur la voit — le rang dans "
            "un tableau de saisie, par exemple. Facultatif, jamais interprété : "
            "renvoyé tel quel dans `problems[].line`, comme l'est le numéro de "
            "ligne d'un fichier CSV."
        ),
    )


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


class PositionOut(Schema):
    """Une ligne TELLE QU'ELLE EST STOCKÉE : ni prix, ni valeur, ni poids.

    Distincte de `ValuedPositionOut` parce qu'elle existe même quand la
    valorisation échoue. `cost_basis` est le prix de revient saisi, facultatif,
    qui ne sert à aucune mesure.
    """

    ticker: str
    quantity: float
    cost_basis: float | None

    @classmethod
    def of(cls, row: PositionRow) -> PositionOut:
        return cls(ticker=row.ticker, quantity=row.quantity, cost_basis=row.cost_basis)


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
    name: str
    quantity: float
    cost_basis: float | None
    price: float
    value: float
    weight: float


class ValuationOut(Schema):
    as_of: date
    total_value: float
    currency: str = Field(
        description=(
            "Code ISO 4217 des prix et des valeurs. Jamais un symbole : « $ » "
            "sans qualificatif se lit dollar canadien à Montréal."
        )
    )
    positions: list[ValuedPositionOut]

    @classmethod
    def of(
        cls,
        weights: PortfolioWeights,
        positions: Sequence[PositionRow],
        names: Mapping[str, str],
        order: Sequence[str] | None = None,
    ) -> ValuationOut:
        """Croise les poids du moteur et les positions stockées, par ticker.

        La quantité est RELUE en base ; elle n'est pas retrouvée en divisant la
        valeur par le prix. Le résultat serait presque toujours le même, et
        « presque » est le problème : ce serait un calcul de la couche API, donc
        une quantité affichée que rien n'a testée.

        Le nom vient du catalogue (`securities.name`), tel qu'il a été ingéré.
        `order` impose l'ordre des lignes : dans `/analysis`, celui de
        `tickers`, pour qu'un tableau et une carte de chaleur ne s'étiquettent
        pas différemment.
        """
        quantites = {p.ticker: p for p in positions}
        return cls(
            as_of=weights.as_of,
            total_value=weights.total_value,
            currency=PRICE_CURRENCY,
            positions=[
                ValuedPositionOut(
                    ticker=ticker,
                    name=names[ticker],
                    quantity=quantites[ticker].quantity,
                    cost_basis=quantites[ticker].cost_basis,
                    price=weights.prices[ticker],
                    value=weights.values[ticker],
                    weight=weights.weights[ticker],
                )
                for ticker in (weights.tickers if order is None else order)
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

    `positions` rend les lignes telles qu'elles sont stockées, valorisables ou
    non, dans l'ordre des tickers. Un portefeuille vide se reconnaît à sa liste
    vide, et non au texte de `valuation_error` ; un portefeuille dont une ligne
    a perdu ses prix reste lisible, donc réparable depuis l'écran de saisie.
    """

    id: int
    name: str
    owner: str
    updated_at: date | None
    positions: list[PositionOut] = Field(
        description=(
            "Positions telles que stockées — ticker, quantité, prix de revient —, "
            "présentes même quand la valorisation échoue. Liste vide pour un "
            "portefeuille sans position."
        )
    )
    valuation: ValuationOut | None
    valuation_error: Texte | None


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
    comprend un résultat inattendu au lieu de le subir. Ces choix sont devinés à
    partir des octets : ils doivent donc être affichables.
    """

    filename: str | None
    encoding: Literal["utf-8", "utf-8-sig", "cp1252"]
    delimiter: Literal[",", ";"]
    decimal_separator: Literal[".", ",", "mixte", "aucune"] = Field(
        description=(
            "Séparateur décimal OBSERVÉ dans les nombres du fichier, et non "
            "celui qui était admis : un fichier `;` dont les quantités sont "
            "entières rend `aucune`, et non `,`. `mixte` quand le fichier "
            "mélange les deux écritures."
        )
    )
    rows_read: int


class CsvImportOut(PositionsWrittenOut):
    source: CsvSourceOut


class CsvDelimiterOut(Schema):
    """Un séparateur de champs, et les séparateurs décimaux qu'il admet.

    La règle tient en une table parce qu'elle dépend du séparateur : avec `;`,
    la virgule est une décimale ; avec `,`, elle termine une colonne.
    """

    delimiter: Literal[",", ";"]
    decimal_separators: list[str]


class CsvFormatOut(Schema):
    """Le format que lit l'import CSV, publié par le lecteur lui-même.

    Chaque champ est lu dans `csv_import` ou `validation`, là où le lecteur
    prend ses décisions : la règle affichée à l'utilisateur est celle qui est
    appliquée. Une description embarquée dans le frontend deviendrait le format
    affiché le jour où le lecteur changerait — même raison que pour
    `GET /api/disclaimer`.

    `expected_header` est l'écriture que citent les messages de refus ;
    `example` est un fichier complet, que les tests font lire au vrai lecteur.
    """

    expected_header: str
    required_columns: list[str]
    optional_columns: list[str]
    delimiters: list[CsvDelimiterOut]
    thousands_separators: list[str] = Field(
        description=(
            "Espaces admises dans un nombre et retirées avant lecture : celles "
            "qu'un tableur glisse entre les milliers."
        )
    )
    encodings: list[str] = Field(
        description=(
            "Encodages reconnus, tels que `source.encoding` les annonce après "
            "un import. `utf-8-sig` désigne un UTF-8 précédé de sa marque "
            "d'ordre des octets."
        )
    )
    max_bytes: int
    max_positions: int = Field(
        description="Nombre maximal de lignes, le même pour une saisie et un import."
    )
    example: str


class VolatilityOut(Schema):
    """Volatilité, publiée même sur une fenêtre courte — et alors marquée.

    `caveat` est la phrase du moteur sous 30 séances (seuil choisi) : le
    chiffre bouge avec les données, il n'est donc pas refusé, mais il est
    signalé comme estimation mince et n'entre dans aucune observation.
    """

    annualised: float
    daily: float
    method: Texte
    caveat: Texte | None
    window: WindowOut
    period_label: Texte = Field(description=DESCRIPTION_PERIODE)

    @classmethod
    def of(cls, result: VolatilityResult) -> VolatilityOut:
        return cls(
            annualised=result.annualised,
            daily=result.daily,
            method=result.method,
            caveat=result.caveat,
            window=WindowOut.of(result.window),
            period_label=result.window.period_label,
        )

    @classmethod
    def optional(cls, result: VolatilityResult | None) -> VolatilityOut | None:
        return None if result is None else cls.of(result)


class DrawdownOut(Schema):
    """Creux maximal de la fenêtre, et le retour au pic qui l'a effacé.

    `recovery_date` et `recovery_sessions` valent `null` ensemble quand la
    baisse n'est pas effacée à la fin de la fenêtre, ou quand il n'y a pas eu
    de baisse (`value` nul) : rien n'est alors à retrouver.
    """

    value: float
    peak_date: date
    trough_date: date
    window: WindowOut
    amount: float = Field(description=DESCRIPTION_MONTANT)
    recovery_date: date | None = Field(
        description=(
            "Première séance, après le creux, où la valeur retrouve son pic. "
            "`null` sans retour avant la fin de la fenêtre."
        )
    )
    recovery_sessions: int | None = Field(
        description="Séances écoulées du creux au retour au pic."
    )
    period_label: Texte = Field(description=DESCRIPTION_PERIODE)

    @classmethod
    def of(cls, result: DrawdownResult) -> DrawdownOut:
        return cls(
            value=result.value,
            peak_date=result.peak_date,
            trough_date=result.trough_date,
            window=WindowOut.of(result.window),
            amount=result.amount,
            recovery_date=result.recovery_date,
            recovery_sessions=result.recovery_sessions,
            period_label=result.window.period_label,
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
    undefined_reason: Texte | None
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
    """Covariance et corrélation, la seconde pouvant manquer avec sa raison.

    Sous trois observations, toutes les cellules hors diagonale de la
    corrélation valent ±1 par construction. La matrice sort donc `null` avec
    `correlation_undefined_reason`, sur le modèle de `SortinoResult` : le refus
    vit dans la MESURE et non seulement dans la phrase du moteur de règles,
    parce qu'une carte de chaleur lit la matrice et non la phrase — et qu'une
    carte de chaleur de ±1 reste symétrique, de diagonale 1, donc plausible.

    `covariance` reste publiée : `wᵀΣw` est la variance de la série du
    portefeuille, estimable dès deux observations, et c'est elle qui porte la
    volatilité paramétrique et la VaR.
    """

    covariance: MatrixOut
    correlation: MatrixOut | None
    correlation_undefined_reason: Texte | None
    ddof: int
    window: WindowOut

    @classmethod
    def of(cls, result: CovarianceResult) -> MatricesOut:
        return cls(
            covariance=MatrixOut.of(result.covariance),
            correlation=(
                None
                if result.correlation is None
                else MatrixOut.of(result.correlation)
            ),
            correlation_undefined_reason=result.correlation_undefined_reason,
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
    """Décomposition de la variance, qui peut manquer avec sa raison.

    Sous trois observations la covariance est de rang 1 et la part de chaque
    ligne s'y ramène à `wᵢδᵢ / (wᵀδ)`, sa part dans une seule différence
    journalière. Le refus vit donc dans la MESURE : en 7B un graphe à barres
    lira `contributions`, pas la phrase du moteur de règles, et des parts qui
    somment à 1 auront l'air d'une décomposition quel que soit leur contenu.

    `has_negative_contribution` vaut `null` et non `false` dans ce cas : `false`
    affirmerait qu'aucune ligne n'a évolué à rebours des autres, alors que rien
    n'a été mesuré.
    """

    tickers: list[str]
    contributions: list[ContributionOut] | None
    undefined_reason: Texte | None
    effective_positions: float | None
    has_negative_contribution: bool | None
    window: WindowOut

    @classmethod
    def of(
        cls, result: VarianceContributionResult, tickers: list[str]
    ) -> VarianceContributionsOut:
        return cls(
            tickers=tickers,
            contributions=(
                None
                if result.contributions is None
                else [
                    ContributionOut(
                        ticker=ticker,
                        contribution=result.contributions[ticker],
                        weight=result.weights[ticker],
                        excess_over_weight=result.excess_over_weight(ticker),
                    )
                    for ticker in tickers
                ]
            ),
            undefined_reason=result.undefined_reason,
            effective_positions=result.effective_positions,
            has_negative_contribution=result.has_negative_contribution,
            window=WindowOut.of(result.window),
        )


class BetaOut(Schema):
    """Sensibilité au marché, éventuellement indéfinie — et alors elle le dit.

    LA PENTE AUSSI est `null` sous trois observations, pas seulement le R². À
    zéro degré de liberté résiduel la droite passe exactement par les points :
    elle n'a pas d'erreur type, ce n'est plus une estimation. Publier la pente
    en nullifiant le seul R² laisserait croire que la sensibilité au marché a
    été mesurée et que seule sa qualité d'ajustement manque.

    Le résultat garde son `benchmark` et sa `window` : ce qui manque est le
    chiffre, pas la provenance. Distinct de `risk.beta` valant `null`, qui
    signifie « aucun benchmark demandé ».
    """

    beta: float | None
    r_squared: float | None
    idiosyncratic_share: float | None
    undefined_reason: Texte | None
    benchmark: str
    basis: Texte
    window: WindowOut

    @classmethod
    def of(cls, result: BetaResult) -> BetaOut:
        return cls(
            beta=result.beta,
            r_squared=result.r_squared,
            idiosyncratic_share=result.idiosyncratic_share,
            undefined_reason=result.undefined_reason,
            benchmark=result.benchmark,
            basis=result.basis,
            window=WindowOut.of(result.window),
        )


class VarOut(Schema):
    """VaR à horizon une séance, en PERTE POSITIVE et en FRACTION.

    `0.0138` se lit « perte d'au moins 1,38 % ». Une valeur négative signifie un
    gain à ce niveau de confiance. `nu` est `null` hors loi de Student : c'est
    une donnée du résultat, pas une mention noyée dans `detail`. `caveat` marque
    une VaR paramétrique normale estimée sur moins de 30 séances, comme
    `VolatilityOut.caveat`.
    """

    value: float
    confidence: float
    method: Texte
    detail: Texte
    nu: float | None
    caveat: Texte | None
    window: WindowOut
    amount: float = Field(description=DESCRIPTION_MONTANT)
    period_label: Texte = Field(description=DESCRIPTION_PERIODE)

    @classmethod
    def of(cls, result: VarResult) -> VarOut:
        return cls(
            value=result.value,
            confidence=result.confidence,
            method=result.method,
            detail=result.detail,
            nu=result.nu,
            caveat=result.caveat,
            window=WindowOut.of(result.window),
            amount=result.amount,
            period_label=result.window.period_label,
        )

    @classmethod
    def optional(cls, result: VarResult | None) -> VarOut | None:
        return None if result is None else cls.of(result)


class HistoricalVarOut(Schema):
    """VaR historique, éventuellement refusée — et alors elle le dit.

    Sous 1/(1 − α) séances (20 à 95 %, 100 à 99 %), aucune séance ne tombe
    dans la queue : le quantile ne serait que le minimum de la fenêtre.
    `value` vaut alors `null` avec `undefined_reason`, sur le modèle de
    `SortinoOut`. Un type à part de `VarOut` : les autres VaR — paramétriques,
    simulées — ne sont jamais refusées ainsi, et leur `value` reste requise.
    """

    value: float | None
    confidence: float
    method: Texte
    detail: Texte
    nu: float | None
    caveat: Texte | None
    undefined_reason: Texte | None
    window: WindowOut
    amount: float | None = Field(
        description=f"{DESCRIPTION_MONTANT} `null` avec `value`."
    )
    period_label: Texte = Field(description=DESCRIPTION_PERIODE)

    @classmethod
    def of(cls, result: VarResult) -> HistoricalVarOut:
        return cls(
            value=result.value,
            confidence=result.confidence,
            method=result.method,
            detail=result.detail,
            nu=result.nu,
            caveat=result.caveat,
            undefined_reason=result.undefined_reason,
            window=WindowOut.of(result.window),
            amount=result.amount,
            period_label=result.window.period_label,
        )


class ExpectedShortfallOut(Schema):
    """CVaR, avec la taille de la queue qu'il moyenne et son avertissement.

    `caveat` est une `@property` du moteur, allumée en PERMANENCE à 99 % et
    au-delà : à ce niveau la queue ne compte que 1 % de la fenêtre, ce n'est pas
    une anomalie mais la structure du chiffre. Un convertisseur générique
    l'aurait perdue sans rien signaler.

    ═══ DEUX CONVENTIONS DE SIGNE DANS LE MÊME OBJET ═══

    `value` est une PERTE POSITIVE (0,0300 = perte moyenne de 3 %), `threshold`
    est un RENDEMENT (−0,0173 = le quantile sous lequel se trouve la queue).
    Les deux décrivent le même événement par les deux bouts, et l'en-tête de
    `risk_engine.var` annonce pourtant que « toutes les valeurs de ce module
    sont des pertes positives ».

    L'écart est dans le moteur, pas ici : `expected_shortfall` rend
    `value=-queue.mean()` mais `threshold=seuil`, le quantile brut. Le
    sérialiser tel quel est le choix retenu — le retourner dans la couche API
    serait de l'arithmétique, et surtout publierait un nombre que le moteur n'a
    jamais produit. Le champ porte donc sa convention dans sa description.

    Relation exacte, vérifiée par un test : `threshold` vaut l'opposé de
    `historical_var.value` du même niveau de confiance, les deux sortant du même
    quantile empirique.

    Refusée AVEC cette VaR, sous 1/(1 − α) séances : `value`, `threshold` et
    `tail_observations` valent alors `null`, et `undefined_reason` dit pourquoi.
    """

    value: float | None = Field(
        description=(
            "Perte moyenne au-delà du quantile, en PERTE POSITIVE et en "
            "fraction : 0.03 se lit « perte moyenne de 3 % »."
        )
    )
    confidence: float
    tail_observations: int | None
    threshold: float | None = Field(
        description=(
            "Quantile qui borne la queue, en convention de RENDEMENT et non de "
            "perte : négatif pour une perte. Signe opposé à `value`, qui est "
            "une perte positive. Vaut l'opposé de `historical_var.value` au "
            "même niveau de confiance."
        )
    )
    caveat: Texte | None
    undefined_reason: Texte | None
    window: WindowOut
    amount: float | None = Field(
        description=f"{DESCRIPTION_MONTANT} `null` avec `value`."
    )
    period_label: Texte = Field(description=DESCRIPTION_PERIODE)

    @classmethod
    def of(cls, result: ExpectedShortfallResult) -> ExpectedShortfallOut:
        return cls(
            value=result.value,
            confidence=result.confidence,
            tail_observations=result.tail_observations,
            threshold=result.threshold,
            caveat=result.caveat,
            undefined_reason=result.undefined_reason,
            window=WindowOut.of(result.window),
            amount=result.amount,
            period_label=result.window.period_label,
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
    `TailRiskOut.student_unavailable_reason` dit pourquoi, en toutes lettres ;
    quand le Monte Carlo normal l'est, `TailRiskOut.monte_carlo_unavailable_reason`.
    """

    confidence: float
    historical_var: HistoricalVarOut
    parametric_var: VarOut
    monte_carlo_var: VarOut | None
    student_parametric_var: VarOut | None
    student_monte_carlo_var: VarOut | None
    expected_shortfall: ExpectedShortfallOut


class TailRiskOut(Schema):
    """Les niveaux de confiance, l'ajustement de Student, et pourquoi un volet
    simulé manque.

    Deux raisons, pas une : le Monte Carlo normal et le volet Student sont
    indépendants et tombent pour des causes différentes — une covariance non
    définie positive pour le premier, une série trop courte ou une Student
    indiscernable de la normale pour le second. Chacune vaut `null` quand son
    volet existe ; sinon elle dit pourquoi, et l'une ne tient jamais lieu de
    l'autre. Même règle que `correlation_undefined_reason` : le moteur rédige
    la raison, l'API la publie.
    """

    levels: list[TailRiskLevelOut]
    student_fit: StudentFitOut | None
    student_unavailable_reason: Texte | None
    monte_carlo_unavailable_reason: Texte | None

    @classmethod
    def of(cls, report: RiskReport) -> TailRiskOut:
        def _niveau(confiance: float, source: dict | None) -> VarResult | None:
            return None if source is None else source.get(confiance)

        return cls(
            levels=[
                TailRiskLevelOut(
                    confidence=confiance,
                    historical_var=HistoricalVarOut.of(
                        report.historical_var[confiance]
                    ),
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
            student_unavailable_reason=report.student_unavailable_reason,
            monte_carlo_unavailable_reason=report.monte_carlo_unavailable_reason,
        )


class WorstDayOut(Schema):
    """La pire séance de la fenêtre, en PERTE POSITIVE comme la VaR.

    Une séance qui a eu lieu, pas un quantile : à côté de la VaR, elle dit que
    le seuil n'est pas un plafond.
    """

    date: date
    loss: float = Field(
        description="Perte de la séance, en fraction et en perte positive : 0.0587 se lit « 5,87 % »."
    )
    amount: float = Field(description=DESCRIPTION_MONTANT.replace("`value`", "`loss`"))
    window: WindowOut

    @classmethod
    def of(cls, result: WorstDayResult) -> WorstDayOut:
        return cls(
            date=result.date,
            loss=result.loss,
            amount=result.amount,
            window=WindowOut.of(result.window),
        )


class WeightOut(Schema):
    ticker: str
    weight: float


class LimitingPositionOut(Schema):
    """Ligne dont l'historique borne la fenêtre de TOUT le rapport.

    Le panel est aligné sur l'INTERSECTION des dates : une ligne à 5 % du
    portefeuille, cotée depuis quarante séances, ramène toutes les mesures à son
    propre historique et déplace le beta et la VaR de l'ensemble.
    `window.complete` dit déjà que la fenêtre est courte ; il ne dit pas à cause
    de qui, et c'est la seule information sur laquelle l'utilisateur peut agir.

    Liste vide quand la fenêtre est pleine : elle a alors été bornée par la
    demande et non par l'historique, et nommer une ligne ferait porter à
    quelqu'un la responsabilité d'un choix de paramètre. Vide aussi quand la
    troncature vient d'un trou au milieu d'une série plutôt que d'une entrée en
    cotation tardive — mieux vaut ne désigner personne que désigner à tort.
    """

    ticker: str
    first_available: date

    @classmethod
    def of(cls, position: LimitingPosition) -> LimitingPositionOut:
        return cls(
            ticker=position.ticker, first_available=position.first_available
        )


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
    benchmark_volatility: VolatilityOut | None = Field(
        description=(
            "Volatilité de l'indice de référence, sur les mêmes séances que le "
            "portefeuille et par la même méthode : un repère pour lire "
            "`volatility`. `null` sans indice de référence."
        )
    )
    worst_day: WorstDayOut

    @classmethod
    def of(cls, report: RiskReport, tickers: list[str]) -> RiskOut:
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
            tail_risk=TailRiskOut.of(report),
            benchmark_volatility=VolatilityOut.optional(report.benchmark_volatility),
            worst_day=WorstDayOut.of(report.worst_day),
        )


# ═══════════════════════════════════════════════════════════════ Séries ══


class PointOut(Schema):
    """Un point daté d'une série : la date en ISO, la valeur telle quelle."""

    date: date
    value: float


class PortfolioSeriesOut(Schema):
    """Les séries sur lesquelles les mesures du régime courant ont été calculées.

    Publiées pour être TRACÉES, pas recalculées : un histogramme ou une courbe
    de richesse dessinés à partir d'autre chose que ces points pourraient
    montrer un creux que `risk.drawdown` ne décrit pas.

    `wealth` commence au point de départ à 1,0, daté de la séance qui PRÉCÈDE
    le premier rendement. Il a donc un point de plus que `returns`. Sans lui,
    le pic initial disparaît, et le creux dessiné ne correspond plus au
    `max_drawdown` publié quand la série baisse dès sa première séance.
    """

    returns: list[PointOut] = Field(
        description=(
            "Rendements quotidiens simples du portefeuille, en fraction, poids "
            "actuels constants. Autant de points que `window.observations`."
        )
    )
    wealth: list[PointOut] = Field(
        description=(
            "Valeur cumulée d'une unité investie, base 1. Le premier point vaut "
            "1,0 et précède le premier rendement d'une séance."
        )
    )
    window: WindowOut

    @classmethod
    def of(cls, report: RiskReport) -> PortfolioSeriesOut:
        return cls(
            returns=[
                PointOut(date=jour, value=float(valeur))
                for jour, valeur in report.returns.items()
            ],
            wealth=[
                PointOut(date=jour, value=float(valeur))
                for jour, valeur in report.wealth.items()
            ],
            window=WindowOut.of(report.window),
        )


class HistogramBinOut(Schema):
    lower: float
    upper: float
    count: int


class ReturnHistogramOut(Schema):
    """Les rendements quotidiens comptés par classes, PAR LE MOTEUR.

    Le client dessine ces classes telles quelles ; il ne les recalcule pas.
    Laissé à la bibliothèque de graphiques (`binX`), le découpage s'ajusterait
    à chaque portefeuille, et deux portefeuilles ne se liraient plus sur la
    même grille — comme une carte de corrélation dont l'échelle suivrait les
    données.
    """

    bin_width: float = Field(
        description=(
            "Largeur de classe, en fraction : 0.0025 se lit 0,25 point. "
            "Paramètre CHOISI (`HISTOGRAM_BIN_WIDTH`), le même pour tous les "
            "portefeuilles ; les bornes sont des multiples de cette largeur, "
            "donc zéro est toujours une borne."
        )
    )
    closed: Literal["left"] = Field(
        description="Chaque classe contient les rendements r tels que lower ≤ r < upper."
    )
    bins: list[HistogramBinOut] = Field(
        description=(
            "Classes contiguës, vides comprises, du minimum au maximum observés "
            "et au moins jusqu'à zéro. La somme des `count` vaut "
            "`window.observations`."
        )
    )
    window: WindowOut

    @classmethod
    def of(cls, report: RiskReport) -> ReturnHistogramOut:
        return cls(
            bin_width=report.histogram.bin_width,
            closed="left",
            bins=[
                HistogramBinOut(lower=c.lower, upper=c.upper, count=c.count)
                for c in report.histogram.bins
            ],
            window=WindowOut.of(report.window),
        )


# ═══════════════════════════════════════════════════════════════ Scénarios ══


class ScenarioDefOut(Schema):
    key: str
    name: Texte
    start: date
    end: date
    benchmark: str
    description: Texte
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
    reason: Texte
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
    que « 5 lignes sur 6 » se dirait pareil. Les lignes exclues n'ont pas été
    rejouées : la perte de l'ensemble a pu être différente, et le chiffre décrit
    d'autant moins le portefeuille que `value_share` baisse.
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
    unavailable_reason: Texte | None
    summary: Texte
    end_to_end_amount: float | None = Field(
        description=(
            "`end_to_end_return` appliqué à la valeur d'aujourd'hui des lignes "
            "couvertes, dans la devise de `valuation.currency`. `null` avec le "
            "rendement. Le pire moment traversé n'a pas de montant : il se "
            "mesure depuis un plus haut atteint pendant l'épisode."
        )
    )
    coverage_sufficient: bool = Field(
        description=(
            "La partie rejouée atteint-elle le seuil choisi de couverture "
            "(80 % de la valeur) ? En deçà, le moteur de règles ne donne pas de "
            "chiffre principal pour le portefeuille."
        )
    )

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
            end_to_end_amount=result.end_to_end_amount,
            coverage_sufficient=result.coverage.sufficient,
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
    unavailable_reason: Texte | None
    summary: Texte
    benchmark_label: Texte | None = Field(
        description=(
            "Ce que suit l'indice de référence, pour une phrase : « le S&P 500 ». "
            "`null` pour un indice sans nom connu, cité alors par son ticker."
        )
    )
    calm_period_label: Texte | None = Field(
        description=(
            "La période du régime calme, dite pour un lecteur : « ces deux "
            "dernières années ». Celle du régime de crise n'en a pas : elle se "
            "termine dans le passé."
        )
    )

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
            benchmark_label=result.benchmark_label,
            calm_period_label=result.calm_period_label,
        )


# ═══════════════════════════════════════════════════════════ Observations ══


class ThresholdOut(Schema):
    """Un seuil et sa provenance, lisible par une machine.

    `kind` est un champ MACHINE, pas une chaîne à analyser : le client distingue
    un seuil choisi à la main d'un seuil dérivé sans chercher le mot « CHOISI »
    dans du texte français. `rendered` reste disponible pour l'affichage, mais
    aucune décision d'interface ne doit dépendre de son contenu.

    `role` dit ce que la valeur EST : `threshold`, une frontière posée d'avance
    (choisie ou démontrée) ; `reference`, une valeur calculée sur ce
    portefeuille, à laquelle la mesure se compare. Le client en tire
    l'étiquette « Seuil » ou « Référence » (DESIGN.md §9.2). `kind` ne suffit
    pas : `derived` couvre les deux.
    """

    name: Texte
    kind: Literal["derived", "portfolio_relative", "chosen"]
    role: Literal["threshold", "reference"]
    value: float
    rationale: Texte
    percent: bool
    chosen: bool
    rendered: Texte

    @classmethod
    def of(cls, threshold: Threshold) -> ThresholdOut:
        return cls(
            name=threshold.name,
            kind=threshold.kind.name.lower(),
            role=threshold.role.name.lower(),
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
    rule_label: Texte
    subject: str
    statement: Texte
    facts: dict[str, int | float | str | None]
    provenance: Texte
    thresholds: list[ThresholdOut]
    uses_chosen_threshold: bool
    rendered: Texte

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
    title: Texte
    body: Texte

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

    title: Texte
    sections: list[DisclaimerSectionOut]
    confirmation: Texte
    text: Texte

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

    @classmethod
    def seul(cls, window: int = DEFAULT_WINDOW) -> DisclaimerOut:
        """Le même bandeau, sans rapport d'analyse — pour `GET /api/disclaimer`.

        L'écran d'acceptation est traversé AVANT le premier accès, donc avant
        qu'un portefeuille existe : le texte doit être disponible sans analyse.
        Le servir seulement dans `/analysis` obligerait le client à en garder
        une copie, et cette copie serait le vrai texte affiché le jour où le
        bandeau changerait.

        `rules_report.disclaimer` vaut `acceptance_text(window)` — c'est
        exactement ce que le moteur de règles y met. Les deux routes servent
        donc le même texte pour la même fenêtre, et un test le vérifie plutôt
        que de le supposer.
        """
        return cls(
            title=ACCEPTANCE_TITLE,
            sections=[
                DisclaimerSectionOut.of(s) for s in acceptance_sections(window)
            ],
            confirmation=ACCEPTANCE_CONFIRMATION,
            text=acceptance_text(window),
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
    benchmark_label: Texte | None = Field(
        description=(
            "Ce que suit l'indice demandé, pour une phrase : « le S&P 500 ». "
            "`null` sans indice, ou pour un indice sans nom connu."
        )
    )
    benchmark_description: Texte | None = Field(
        description=(
            "L'indice présenté à sa première apparition : « l'indice de 500 "
            "grandes entreprises américaines ». `null` avec `benchmark_label`."
        )
    )


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

    `estimation_window` est la fenêtre du PANEL de régime courant
    (`PortfolioSeries.window`). Ce n'est pas une fenêtre hissée au niveau du
    document : c'est un objet du moteur, avec son propre nom et son propre sens.
    Les mesures calculées sur ce panel la partagent par construction ; chacune
    continue de porter la sienne, et une mesure peut en avoir une autre — le
    beta est régressé sous une contrainte d'échantillon qui lui est propre, un
    scénario a ses propres dates. Un client qui l'afficherait à la place des
    fenêtres de mesure mentirait sur celles-là ; publier le panel sous son vrai
    nom vaut mieux que de le laisser déduire d'une mesure choisie au hasard.

    `limiting_positions` nomme la ou les lignes dont l'historique a borné la
    fenêtre de TOUTES les mesures. Vide quand la fenêtre est pleine.

    CONVENTION v1, ASSUMÉE — une ligne sans historique suffisant est traitée
    différemment selon l'endroit, et les deux traitements sont honnêtes à
    condition d'être dits. Les SCÉNARIOS l'EXCLUENT et déclarent leur couverture
    (`coverage.value_share`) ; le RÉGIME COURANT TRONQUE toute l'analyse à
    l'historique commun. La troncature est retenue en v1 parce qu'elle n'écarte
    aucune ligne détenue — tout le portefeuille est décrit, sur une période plus
    courte. L'exclusion avec renormalisation, qui décrirait la période complète
    sur une partie du portefeuille, est au backlog v2.
    """

    portfolio_id: int
    portfolio: PortfolioOut
    as_of: date
    total_value: float
    tickers: list[str]
    weights: list[WeightOut]
    valuation: ValuationOut = Field(
        description=(
            "Valorisation ligne à ligne qui a produit `weights` : quantité "
            "stockée, dernière clôture brute, valeur, nom du titre. Dans la même "
            "réponse que les mesures, pour décrire le même état de la base."
        )
    )
    estimation_window: WindowOut = Field(
        description=(
            "Fenêtre du panel de régime courant. Les mesures calculées sur ce "
            "panel la partagent ; chacune porte néanmoins la sienne, et une "
            "mesure peut en avoir une autre."
        )
    )
    estimation_period_label: Texte = Field(
        description=(
            "La période de `estimation_window`, dite pour un lecteur : « ces "
            "deux dernières années »."
        )
    )
    limiting_positions: list[LimitingPositionOut]
    parameters: ParametersOut
    risk: RiskOut
    series: PortfolioSeriesOut
    histogram: ReturnHistogramOut
    scenarios: list[ScenarioOut]
    regimes: list[RegimeOut]
    observations: list[ObservationOut]
    disclaimer: DisclaimerOut
