/**
 * Alias de lecture sur les types ENGENDRÉS.
 *
 * `schema.ts` est produit par `openapi-typescript` depuis `openapi.json`, lui-
 * même produit par `python -m tools.openapi_schema`. Ni l'un ni l'autre ne
 * s'écrit à la main, et un test Python interdit qu'ils prennent du retard sur
 * l'application.
 *
 * Ce fichier ne DÉCLARE aucun champ : il ne fait que nommer des types déjà
 * engendrés, parce que `components['schemas']['TailRiskLevelOut']` est
 * illisible partout où on s'en sert. Écrire ici la moindre forme à la main
 * rouvrirait exactement la porte que la génération ferme — un type recopié qui
 * survit à la disparition du champ qu'il décrit.
 */
import type { components } from './schema'

type S = components['schemas']

export type Analysis = S['AnalysisOut']
export type Window = S['WindowOut']
export type Portfolio = S['PortfolioOut']
export type Parameters = S['ParametersOut']
export type LimitingPosition = S['LimitingPositionOut']

export type Risk = S['RiskOut']
export type Volatility = S['VolatilityOut']
export type TailRisk = S['TailRiskOut']
export type TailRiskLevel = S['TailRiskLevelOut']
export type Var = S['VarOut']
export type ExpectedShortfall = S['ExpectedShortfallOut']
export type StudentFit = S['StudentFitOut']

export type Disclaimer = S['DisclaimerOut']
export type DisclaimerSection = S['DisclaimerSectionOut']

export type Meta = S['MetaOut']
export type PortfolioDetail = S['PortfolioDetailOut']
export type Security = S['SecurityOut']
export type Position = S['PositionOut']
export type PositionIn = S['PositionIn']
export type PositionsWritten = S['PositionsWrittenOut']
export type CsvImport = S['CsvImportOut']
export type CsvSource = S['CsvSourceOut']
export type CsvFormat = S['CsvFormatOut']
export type CsvDelimiter = S['CsvDelimiterOut']

export type Valuation = S['ValuationOut']
export type ValuedPosition = S['ValuedPositionOut']

export type PortfolioSeries = S['PortfolioSeriesOut']
export type Point = S['PointOut']
export type ReturnHistogram = S['ReturnHistogramOut']
export type HistogramBin = S['HistogramBinOut']
export type Drawdown = S['DrawdownOut']

export type Matrices = S['MatricesOut']
export type Matrix = S['MatrixOut']
export type VarianceContributions = S['VarianceContributionsOut']
export type Contribution = S['ContributionOut']
export type Concentration = S['ConcentrationOut']
export type Beta = S['BetaOut']

export type Scenario = S['ScenarioOut']
export type ScenarioDef = S['ScenarioDefOut']
export type Coverage = S['CoverageOut']
export type ExcludedPosition = S['ExcludedPositionOut']
export type PositionContribution = S['PositionContributionOut']
export type TrajectoryDrawdown = S['TrajectoryDrawdownOut']
export type Regime = S['RegimeOut']
export type RegressedBeta = S['RegressedBetaOut']

export type Observation = S['ObservationOut']
export type Threshold = S['ThresholdOut']
