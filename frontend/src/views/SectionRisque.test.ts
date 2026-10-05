/**
 * Section 4 — rendue côté serveur. Les graphiques n'y sont pas tracés (il n'y
 * a pas de document) ; ce qui est vérifié est ce qui les entoure : la légende
 * exacte, le refus écrit à la place d'une carte vide, la contribution négative
 * qui se voit, et le comportement en scénario posé dans le même bloc (§11.4).
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type {
  Concentration,
  Matrices,
  Scenario,
  VarianceContributions,
  Window,
} from '../api/types'
import { PHRASE_CONTRIBUTION_NEGATIVE } from '../lib/phrases'
import { LEGENDE_CONTRIBUTIONS, SectionRisque } from './SectionRisque'
import styles from './SectionRisque.module.css'

const FENETRE: Window = {
  requested: 504,
  observations: 504,
  start: '2024-09-05',
  end: '2026-09-09',
  complete: true,
}

const VARIANCE: VarianceContributions = {
  tickers: ['XOM', 'JPM'],
  contributions: [
    { ticker: 'XOM', contribution: 0.139, weight: 0.158, excess_over_weight: -0.019 },
    { ticker: 'JPM', contribution: 0.861, weight: 0.842, excess_over_weight: 0.019 },
  ],
  undefined_reason: null,
  effective_positions: 1.3,
  has_negative_contribution: false,
  window: FENETRE,
}

const CONCENTRATION: Concentration = {
  hhi: 0.73,
  effective_positions: 1.37,
  equal_weight_reference: 0.5,
  n_positions: 2,
  as_of: '2026-09-09',
}

const MATRICES: Matrices = {
  covariance: { tickers: ['XOM', 'JPM'], values: [[1, 0], [0, 1]] },
  correlation: { tickers: ['XOM', 'JPM'], values: [[1, 0.3], [0.3, 1]] },
  correlation_undefined_reason: null,
  ddof: 1,
  window: FENETRE,
}

const SCENARIO_2022: Scenario = {
  scenario: {
    key: 'resserrement_2022',
    name: 'Resserrement 2022',
    start: '2022-01-03',
    end: '2022-10-12',
    benchmark: 'SPY',
    description: '',
    calendar_days: 282,
  },
  coverage: {
    covered: ['XOM'],
    excluded: [
      { ticker: 'JPM', reason: 'historique débutant plus tard', value: 1, weight: 0.842, first_available: '2023-01-03' },
    ],
    covered_value: 1,
    total_value: 2,
    value_share: 0.158,
    is_complete: false,
    covered_count: 1,
    total_count: 2,
  },
  end_to_end_return: 0.597,
  max_drawdown: { value: -0.05, peak_date: '2022-01-10', trough_date: '2022-02-01', peak_level: 1.02, trough_level: 0.97 },
  contributions: [
    {
      ticker: 'XOM',
      start_value: 1,
      end_value: 1.597,
      own_return: 0.597,
      contribution: 0.597,
      start_weight: 1,
      end_weight: 1,
      pnl: 0.597,
      weight_drift: 0,
    },
  ],
  observations: 196,
  unavailable_reason: null,
  summary: '',
  end_to_end_amount: 0.597,
  coverage_sufficient: false,
}

function rendu(surcharges: Partial<Parameters<typeof SectionRisque>[0]> = {}): string {
  return renderToStaticMarkup(
    createElement(SectionRisque, {
      variance: VARIANCE,
      concentration: CONCENTRATION,
      matrices: MATRICES,
      scenarios: [SCENARIO_2022],
      asOf: '2026-09-09',
      ...surcharges,
    }),
  ).replaceAll('&#x27;', "'")
}

describe('part de la variance contre part du capital (§5.4)', () => {
  it('porte la légende exacte de §5.4', () => {
    expect(LEGENDE_CONTRIBUTIONS).toBe(
      'barre\u00a0: part dans les variations — trait\u00a0: part dans la valeur',
    )
    const html = rendu().replace(/<span[^>]*><\/span>/g, '')
    expect(html).toContain(LEGENDE_CONTRIBUTIONS)
  })

  it('pose le comportement réalisé en scénario dans le MÊME bloc (§11.4)', () => {
    const html = rendu()
    expect(html).toContain('Resserrement 2022')
    // XOM : moins de risque que de capital, et un apport POSITIF en 2022.
    expect(html).toContain('+59,7')
    expect(html).toContain(styles.gain)
    // JPM n'était pas couverte par ce scénario : elle le dit, sans chiffre.
    expect(html).toContain('non couverte')
  })

  it('montre une contribution négative quand le moteur la signale', () => {
    expect(rendu()).not.toContain(PHRASE_CONTRIBUTION_NEGATIVE)
    expect(
      rendu({ variance: { ...VARIANCE, has_negative_contribution: true } }),
    ).toContain(PHRASE_CONTRIBUTION_NEGATIVE)
  })

  it('écrit la raison du refus à la place des barres', () => {
    const html = rendu({
      variance: {
        ...VARIANCE,
        contributions: null,
        effective_positions: null,
        has_negative_contribution: null,
        undefined_reason: 'Deux séances seulement : décomposition non estimable.',
      },
    })
    expect(html).toContain('Deux séances seulement : décomposition non estimable.')
    expect(html).not.toContain('Part de chaque ligne dans les variations')
  })
})

describe('carte de corrélation', () => {
  it('écrit la raison en texte quand la corrélation est nulle, sans grille vide', () => {
    const html = rendu({
      matrices: {
        ...MATRICES,
        correlation: null,
        correlation_undefined_reason: 'Deux points centrés sont colinéaires.',
      },
    })
    expect(html).toContain('Deux points centrés sont colinéaires.')
    expect(html).not.toContain('Corrélation des variations quotidiennes')
  })

  it('annonce son échelle fixe sous la carte', () => {
    expect(rendu()).toContain('échelle fixe')
  })
})
