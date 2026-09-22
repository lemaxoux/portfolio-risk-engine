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
