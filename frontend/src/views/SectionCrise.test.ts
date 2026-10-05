/**
 * Section 5 — trois chiffres par scénario, à la même taille (§11.2), et des
 * régimes appariés, jamais moyennés (§11.6). Rendu côté serveur.
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Regime, Scenario } from '../api/types'
import { ESPACE_FINE, SIGNE_MOINS } from '../lib/format'
import { BlocScenario, SectionCrise } from './SectionCrise'
import styles from './SectionCrise.module.css'

function scenario(cle: string, nom: string, sortie: number | null, creux: number | null, part = 1): Scenario {
  const complete = part === 1
  return {
    scenario: {
      key: cle,
      name: nom,
      start: '2007-10-09',
      end: '2009-03-09',
      benchmark: 'SPY',
      description: 'Du sommet au creux.',
      calendar_days: 517,
    },
    coverage: {
      covered: complete ? ['AAA', 'BBB'] : ['AAA'],
      excluded: complete
        ? []
        : [{ ticker: 'BBB', reason: 'historique débutant le 2010-01-04', value: 1, weight: 1 - part, first_available: '2010-01-04' }],
      covered_value: part,
      total_value: 1,
      value_share: part,
      is_complete: complete,
      covered_count: complete ? 2 : 1,
      total_count: 2,
    },
    end_to_end_return: sortie,
    max_drawdown:
      creux === null
        ? null
        : { value: creux, peak_date: '2007-10-09', trough_date: '2009-03-09', peak_level: 1, trough_level: 1 + creux },
    contributions: [],
    observations: 356,
    unavailable_reason: sortie === null ? "aucune ligne du portefeuille n'a d'historique couvrant la période" : null,
    summary: '',
    end_to_end_amount: sortie === null ? null : sortie * part,
    coverage_sufficient: part >= 0.8,
  }
}

/** Le HTML rendu, apostrophes décodées : React écrit « ' » en « &#x27; ». */
function rendreBloc(s: Scenario, regime?: Regime): string {
  return renderToStaticMarkup(
    createElement(BlocScenario, { scenario: s, regime, asOf: '2026-09-09', devise: 'USD' }),
  ).replaceAll('&#x27;', "'")
}

/** Les valeurs portées par la classe `chiffre`, dans l'ordre. */
function chiffres(html: string): string[] {
  const motif = new RegExp(`<dd class="${styles.chiffre}">([^<]*)</dd>`, 'g')
  return [...html.matchAll(motif)].map((m) => m[1] ?? '')
}

describe('trois chiffres, à la même taille (§11.2)', () => {
  it('la sortie, le pire moment traversé et la couverture portent la MÊME classe', () => {
    const html = rendreBloc(scenario('gfc', 'Crise financière 2008', -0.44, -0.475))
    expect(chiffres(html)).toEqual([
      `${SIGNE_MOINS}44,0${ESPACE_FINE}%`,
      `${SIGNE_MOINS}47,5${ESPACE_FINE}%`,
      `100${ESPACE_FINE}%`,
    ])
    // Aucune autre classe de taille sur l'un d'eux : la perte n'a pas le
    // droit d'être plus grosse que sa couverture.
    expect(html.match(/<dd class="[^"]*">[^<]*%<\/dd>/g)).toHaveLength(3)
  })

  it('la section affiche les trois chiffres de CHAQUE scénario', () => {
    const html = renderToStaticMarkup(
      createElement(SectionCrise, {
        scenarios: [
          scenario('gfc', 'Crise financière 2008', -0.44, -0.475),
          scenario('covid', 'Krach COVID', -0.358, -0.358),
          scenario('taux', 'Resserrement 2022', -0.087, -0.131),
        ],
        regimes: [],
        asOf: '2026-09-09',
        devise: 'USD',
      }),
    )
    expect(chiffres(html)).toHaveLength(9)
    expect(chiffres(html)).toContain(`${SIGNE_MOINS}13,1${ESPACE_FINE}%`)
  })

  it('un gain de scénario porte son « + »', () => {
    expect(chiffres(rendreBloc(scenario('x', 'X', 0.05, -0.02)))[0]).toBe(`+5,0${ESPACE_FINE}%`)
  })
})

describe('couverture partielle', () => {
  it('pose le point de réserve DÈS que la couverture est sous 100 %, pas seulement sous 80 %', () => {
    const html = rendreBloc(scenario('gfc', 'Crise financière 2008', -0.44, -0.475, 0.99))
    expect(html).toContain(styles.point)
    expect(chiffres(html)[2]).toBe(`99${ESPACE_FINE}%`)
    // Les lignes exclues sont nommées, avec la raison du moteur, telle quelle.
    expect(html).toContain('BBB')
    expect(html).toContain('historique débutant le 2010-01-04')
  })

  it('ne pose aucun point quand la couverture est complète', () => {
    expect(rendreBloc(scenario('gfc', 'Crise financière 2008', -0.44, -0.475))).not.toContain(styles.point)
  })
})

describe('scénario indisponible', () => {
  it('écrit la raison du moteur, sans fabriquer de chiffre', () => {
    const html = rendreBloc(scenario('gfc', 'Crise financière 2008', null, null, 0))
    expect(html).toContain("aucune ligne du portefeuille n'a d'historique couvrant la période")
    expect(chiffres(html).slice(0, 2)).toEqual(['\u2014', '\u2014'])
  })
})

describe('régimes appariés, jamais moyennés (§11.6)', () => {
  const regime: Regime = {
    scenario: scenario('covid', 'Krach COVID', -0.358, -0.358).scenario,
    coverage: scenario('covid', 'Krach COVID', -0.358, -0.358).coverage,
    benchmark: 'SPY',
    portfolio_return: -0.358,
    benchmark_return: -0.337,
    amplification_ratio: 1.07,
    crisis_beta: { beta: 1.07, r_squared: 0.98, standard_error: 0.03, observations: 23, start: '2020-02-20', end: '2020-03-23', min_observations: 60, sample_too_thin: true },
    calm_beta: { beta: 0.57, r_squared: 0.49, standard_error: 0.03, observations: 504, start: '2024-09-05', end: '2026-09-09', min_observations: 60, sample_too_thin: false },
    predicted_return: -0.207,
    prediction_gap: -0.148,
    ratio_beta_divergence: 0,
    systematic_share_change: 0.49,
    unavailable_reason: null,
    summary: '',
    benchmark_label: 'le S&P 500',
    calm_period_label: 'ces deux dernières années',
  }

  it('pose le beta calme et le beta de crise côte à côte, sans moyenne', () => {
    const html = rendreBloc(scenario('covid', 'Krach COVID', -0.358, -0.358), regime)
    expect(html).toContain('0,57 ± 0,03')
    expect(html).toContain('1,07 ± 0,03')
    // La moyenne de 0,57 et 1,07 serait 0,82 : elle n'est écrite nulle part.
    expect(html).not.toContain('0,82')
  })

  it('dit quand l’échantillon de crise est mince', () => {
    const html = rendreBloc(scenario('covid', 'Krach COVID', -0.358, -0.358), regime)
    expect(html).toContain('23\u00a0séances')
    expect(html).toContain('seuil choisi')
  })

  it('sans libellé de période, la colonne et la phrase nomment la période d’estimation', () => {
    const html = rendreBloc(scenario('covid', 'Krach COVID', -0.358, -0.358), {
      ...regime,
      calm_period_label: null,
    })
    expect(html).toContain("Période d'estimation")
    expect(html).toContain("Sur la période d'estimation, quand le")
    expect(html).not.toContain('Régime calme')
    expect(html).not.toContain('En temps ordinaire')
  })
})
