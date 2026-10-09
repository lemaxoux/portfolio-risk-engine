/**
 * Les valeurs des graphiques, en tableau (chantier 7E, DESIGN.md §9.4).
 *
 * Ce qui est vérifié : chaque tableau reprend les valeurs PUBLIÉES, toutes et
 * dans l'ordre publié, écrites par `lib/format`, sans rien calculer ni
 * choisir. Les classes vides de l'histogramme restent ; la phrase des traits
 * ne nomme que les niveaux que le dessin trace, par le même filtre ; le repère
 * de la courbe se pose sur les dates publiées du pic et du creux, et nulle
 * part ailleurs. Les espaces sont écrites par leurs constantes.
 */
import { describe, expect, it } from 'vitest'

import type { Drawdown, Matrix, Point, TailRiskLevel, Window } from '../../api/types'
import { ESPACE_FINE, ESPACE_INSECABLE, SIGNE_MOINS } from '../../lib/format'
import type { Colonne } from '../DataTable'
import { colonnesCorrelation, rangeesCorrelation } from './correlation'
import { colonnesHistogramme, niveauxTraces, noteHistogramme } from './histogramme'
import { colonnesCourbe, rangeesCourbe } from './richesse'

const NB = ESPACE_INSECABLE
const NF = ESPACE_FINE
const M = SIGNE_MOINS

/** Les textes d'une rangée, tels que le tableau les écrit. */
function rangee<T>(colonnes: readonly Colonne<T>[], ligne: T): string[] {
  return colonnes.map((colonne) => String(colonne.cellule(ligne)))
}

const FENETRE: Window = {
  requested: 504,
  observations: 504,
  start: '2024-09-23',
  end: '2026-09-25',
  complete: true,
}

/** Un niveau publié : sa VaR historique, le quantile en rendement, sa queue. */
function niveau(
  confiance: number,
  varHistorique: number | null,
  seuil: number | null,
  queue: number | null,
): TailRiskLevel {
  const vr = {
    value: varHistorique ?? 0,
    confidence: confiance,
    method: 'historique',
    detail: '',
    nu: null,
    caveat: null,
    window: FENETRE,
    amount: 1000,
    period_label: 'ces deux dernières années',
  }
  return {
    confidence: confiance,
    historical_var: { ...vr, value: varHistorique, undefined_reason: varHistorique === null ? 'Refusée.' : null },
    parametric_var: vr,
    monte_carlo_var: null,
    student_parametric_var: null,
    student_monte_carlo_var: null,
    expected_shortfall: {
      value: varHistorique,
      confidence: confiance,
      tail_observations: queue,
      threshold: seuil,
      caveat: null,
      undefined_reason: varHistorique === null ? 'Refusée.' : null,
      window: FENETRE,
      amount: 1000,
      period_label: 'ces deux dernières années',
    },
  }
}

const NIVEAUX = [niveau(0.95, 0.0106, -0.0106, 26), niveau(0.99, 0.0169, -0.0169, 6)]

describe("l'histogramme, en tableau", () => {
  const CLASSES = [
    { lower: -0.0075, upper: -0.005, count: 1 },
    { lower: -0.005, upper: -0.0025, count: 0 },
    { lower: -0.0025, upper: 0, count: 4 },
    { lower: 0, upper: 0.0025, count: 1234 },
  ]

  it('écrit chaque classe publiée, ses bornes et son compte, vides comprises', () => {
    const colonnes = colonnesHistogramme('fr')
    expect(CLASSES.map((classe) => rangee(colonnes, classe))).toEqual([
      [`${M}0,75${NF}% à ${M}0,50${NF}%`, '1'],
      [`${M}0,50${NF}% à ${M}0,25${NF}%`, '0'],
      [`${M}0,25${NF}% à 0,00${NF}%`, '4'],
      [`0,00${NF}% à 0,25${NF}%`, `1${NF}234`],
    ])
  })

  it('en anglais aussi', () => {
    const colonnes = colonnesHistogramme('en')
    expect(colonnes.map((colonne) => colonne.titre)).toEqual(['Bin', 'Sessions'])
    expect(rangee(colonnes, CLASSES[0]!)).toEqual([`${M}0.75% to ${M}0.50%`, '1'])
    expect(rangee(colonnes, CLASSES[3]!)).toEqual(['0.00% to 0.25%', '1,234'])
  })

  it('la phrase des traits nomme les niveaux tracés, leur VaR, leur quantile et la queue', () => {
    expect(noteHistogramme(NIVEAUX, 'fr')).toBe(
      `Traits du graphique${NB}: VaR 95${NF}% (1,06${NF}%), au rendement de ${M}1,06${NF}%${NB}; ` +
        `VaR 99${NF}% (1,69${NF}%), au rendement de ${M}1,69${NF}%. ` +
        `Zone ombrée${NB}: la queue à 95${NF}%, 26${NB}séances.`,
    )
    expect(noteHistogramme(NIVEAUX, 'en')).toBe(
      `Lines on the chart: VaR 95% (1.06%), at a return of ${M}1.06%; ` +
        `VaR 99% (1.69%), at a return of ${M}1.69%. ` +
        `Shaded area: the tail at 95%, 26${NB}sessions.`,
    )
  })

  it("un niveau refusé n'a ni trait ni mention, par le même filtre que le dessin", () => {
    const refuse = niveau(0.99, null, null, null)
    expect(niveauxTraces([NIVEAUX[0]!, refuse]).map((n) => n.confidence)).toEqual([0.95])
    expect(noteHistogramme([NIVEAUX[0]!, refuse], 'fr')).toBe(
      `Trait du graphique${NB}: VaR 95${NF}% (1,06${NF}%), au rendement de ${M}1,06${NF}%. ` +
        `Zone ombrée${NB}: la queue à 95${NF}%, 26${NB}séances.`,
    )
  })

  it('sans niveau tracé, aucune phrase', () => {
    expect(noteHistogramme([niveau(0.95, null, null, null), niveau(0.99, null, null, null)], 'fr')).toBeNull()
  })

  it("la zone ombrée n'est nommée que là où le dessin l'ombre : à 95 %, queue publiée", () => {
    const sansQueue = niveau(0.95, 0.0106, -0.0106, null)
    expect(noteHistogramme([sansQueue], 'fr')).not.toContain('Zone ombrée')
    expect(noteHistogramme([NIVEAUX[1]!], 'fr')).not.toContain('Zone ombrée')
  })
})

describe('la courbe de valeur, en tableau', () => {
  const POINTS: Point[] = [
    { date: '2025-02-18', value: 1.02 },
    { date: '2025-02-19', value: 1.0412 },
    { date: '2025-03-10', value: 0.97 },
    { date: '2025-04-08', value: 0.887 },
    { date: '2025-06-23', value: 1.05 },
  ]
  const CREUX: Drawdown = {
    value: -0.1481,
    peak_date: '2025-02-19',
    trough_date: '2025-04-08',
    window: FENETRE,
    amount: -12480,
    recovery_date: '2025-06-23',
    recovery_sessions: 51,
    period_label: 'ces deux dernières années',
  }

  it('une rangée par point publié, dans l’ordre, la valeur à trois décimales', () => {
    const rangees = rangeesCourbe(POINTS, CREUX)
    expect(rangees.map((r) => r.date)).toEqual(POINTS.map((p) => p.date))
    const colonnes = colonnesCourbe(CREUX, 'fr')
    expect(colonnes.map((colonne) => colonne.titre)).toEqual(['Séance', 'Valeur', 'Repère'])
    expect(rangees.map((r) => rangee(colonnes, r))).toEqual([
      ['2025-02-18', '1,020', ''],
      ['2025-02-19', '1,041', 'pic'],
      ['2025-03-10', '0,970', ''],
      ['2025-04-08', '0,887', `creux ${M}14,8${NF}%`],
      ['2025-06-23', '1,050', ''],
    ])
  })

  it('en anglais aussi', () => {
    const colonnes = colonnesCourbe(CREUX, 'en')
    expect(colonnes.map((colonne) => colonne.titre)).toEqual(['Session', 'Value', 'Marker'])
    expect(rangee(colonnes, rangeesCourbe(POINTS, CREUX)[3]!)).toEqual([
      '2025-04-08',
      '0.887',
      `trough ${M}14.8%`,
    ])
  })

  it('sans baisse, le pic et le creux publiés au premier jour, là où le dessin pose ses deux annotations', () => {
    const plate: Point[] = [
      { date: '2025-01-02', value: 1 },
      { date: '2025-01-03', value: 1.01 },
      { date: '2025-01-06', value: 1.02 },
    ]
    const aucunCreux: Drawdown = {
      ...CREUX,
      value: 0,
      peak_date: '2025-01-02',
      trough_date: '2025-01-02',
      recovery_date: null,
      recovery_sessions: null,
    }
    const rangees = rangeesCourbe(plate, aucunCreux)
    expect(rangees.map((r) => r.reperes)).toEqual([['pic', 'creux'], [], []])
    expect(rangee(colonnesCourbe(aucunCreux, 'fr'), rangees[0]!)[2]).toBe(`pic, creux 0,0${NF}%`)
  })

  it("aucun repère n'est posé ni aucun point ajouté pour une date absente de la courbe publiée", () => {
    const ailleurs: Drawdown = { ...CREUX, peak_date: '2024-01-02', trough_date: '2024-02-01' }
    const rangees = rangeesCourbe(POINTS, ailleurs)
    expect(rangees).toHaveLength(POINTS.length)
    expect(rangees.every((r) => r.reperes.length === 0)).toBe(true)
  })
})

describe('la carte de corrélation, en tableau', () => {
  const MATRICE: Matrix = {
    tickers: ['JNJ', 'KO', 'XOM'],
    values: [
      [1, 0.4151, -0.05],
      [0.4151, 1, 0.12],
      [-0.05, 0.12, 1],
    ],
  }

  it('une rangée et une colonne par ligne, dans l’ordre publié, deux décimales, la diagonale écrite', () => {
    const colonnes = colonnesCorrelation(MATRICE, 'fr')
    expect(colonnes.map((colonne) => colonne.titre)).toEqual(['Ticker', 'JNJ', 'KO', 'XOM'])
    expect(rangeesCorrelation(MATRICE).map((r) => rangee(colonnes, r))).toEqual([
      ['JNJ', '1,00', '0,42', `${M}0,05`],
      ['KO', '0,42', '1,00', '0,12'],
      ['XOM', `${M}0,05`, '0,12', '1,00'],
    ])
  })

  it('en anglais aussi', () => {
    const colonnes = colonnesCorrelation(MATRICE, 'en')
    expect(rangee(colonnes, rangeesCorrelation(MATRICE)[0]!)).toEqual(['JNJ', '1.00', '0.42', `${M}0.05`])
  })
})
