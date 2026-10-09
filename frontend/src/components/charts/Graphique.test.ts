/**
 * `<Graphique>` et ses valeurs, rendus côté serveur (chantier 7E, DESIGN.md
 * §9.4, §13).
 *
 * Le tracé n'est pas dessiné ici, il n'y a pas de document. Ce qui est
 * vérifié l'entoure : le repli fermé qui donne ses valeurs en tableau, après
 * le tracé ; son libellé, le même sous chaque graphique, suivi du titre du
 * graphique en texte masqué ; la légende et les en-têtes du tableau ; une
 * rangée par valeur publiée, dans l'ordre. Et, pour les parts dans les
 * variations, dont le tableau suit déjà la figure : le tracé désigne la
 * légende de ce tableau, et ne reçoit pas de second tableau.
 */
import { createElement, type ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type {
  Concentration,
  HistogramBin,
  Matrices,
  VarianceContributions,
  Window,
} from '../../api/types'
import { ContexteDeLangue, langueDuSite, type Langue } from '../../lib/langue'
import { SectionRisque } from '../../views/SectionRisque'
import { Graphique } from './Graphique'
import { colonnesHistogramme } from './histogramme'

const FENETRE: Window = {
  requested: 504,
  observations: 504,
  start: '2024-09-23',
  end: '2026-09-25',
  complete: true,
}

const CLASSES: HistogramBin[] = [
  { lower: -0.005, upper: -0.0025, count: 1 },
  { lower: -0.0025, upper: 0, count: 0 },
  { lower: 0, upper: 0.0025, count: 3 },
]

function enLangue(langue: Langue, element: ReactElement): string {
  return renderToStaticMarkup(
    createElement(ContexteDeLangue.Provider, { value: langueDuSite(langue, () => undefined) }, element),
  ).replaceAll('&#x27;', "'")
}

function histogramme(langue: Langue = 'fr', avecValeurs = true): string {
  return enLangue(
    langue,
    createElement(Graphique<HistogramBin>, {
      titre: 'Variations de valeur, jour par jour',
      unite: 'séances par classe',
      fenetre: FENETRE,
      asOf: '2026-09-25',
      description: 'Une conclusion.',
      options: () => ({ marks: [] }),
      ...(avecValeurs
        ? {
            valeurs: {
              legende: 'Séances par tranche',
              colonnes: colonnesHistogramme(langue),
              lignes: CLASSES,
              cleDeLigne: (classe: HistogramBin) => String(classe.lower),
              note: 'Ce que le dessin porte en plus.',
            },
          }
        : {}),
    }),
  )
}

describe('les valeurs du graphique, repliées sous lui', () => {
  it('un repli natif, fermé, après le tracé', () => {
    const html = histogramme()
    const trace = html.indexOf('role="img"')
    const repli = html.indexOf('<details')
    expect(trace).toBeGreaterThan(-1)
    expect(repli).toBeGreaterThan(trace)
    expect(html.slice(repli, html.indexOf('>', repli))).not.toContain('open')
  })

  it('son libellé visible, puis le titre du graphique en texte masqué', () => {
    const html = histogramme()
    const resume = html.slice(html.indexOf('<summary'), html.indexOf('</summary>'))
    expect(resume).toContain(
      'Les valeurs du graphique, en tableau<span class="visuellement-cache"> (Variations de valeur, jour par jour)</span>',
    )
  })

  it('en anglais, le même libellé partout', () => {
    expect(histogramme('en')).toContain("The chart's values, as a table<span")
  })

  it('le tableau a sa légende, ses en-têtes de colonne et de rangée', () => {
    const html = histogramme()
    const repli = html.slice(html.indexOf('<details'))
    expect(repli).toContain('<caption')
    expect(repli).toContain('Séances par tranche')
    expect(repli).toContain('<th scope="col"')
    expect(repli).toContain('<th scope="row"')
  })

  it('une rangée par valeur publiée, dans l’ordre publié, et la phrase du dessin après le tableau', () => {
    const html = histogramme()
    const corps = html.slice(html.indexOf('<tbody>'), html.indexOf('</tbody>'))
    expect(corps.match(/<tr/g)).toHaveLength(CLASSES.length)
    const premiere = corps.indexOf('0,50')
    const derniere = corps.indexOf('0,25\u202f%</th>', corps.lastIndexOf('<tr'))
    expect(premiere).toBeGreaterThan(-1)
    expect(derniere).toBeGreaterThan(premiere)
    expect(html.indexOf('Ce que le dessin porte en plus.')).toBeGreaterThan(html.indexOf('</table>'))
  })

  it('sans valeurs, aucun repli', () => {
    expect(histogramme('fr', false)).not.toContain('<details')
  })
})

describe('les parts dans les variations : le tracé désigne le tableau qui le suit', () => {
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
    as_of: '2026-09-25',
  }
  const MATRICES: Matrices = {
    covariance: { tickers: ['XOM', 'JPM'], values: [[1, 0], [0, 1]] },
    correlation: { tickers: ['XOM', 'JPM'], values: [[1, 0.3], [0.3, 1]] },
    correlation_undefined_reason: null,
    ddof: 1,
    window: FENETRE,
  }

  const html = enLangue(
    'fr',
    createElement(SectionRisque, {
      variance: VARIANCE,
      concentration: CONCENTRATION,
      matrices: MATRICES,
      scenarios: [],
      asOf: '2026-09-25',
    }),
  )

  it('aria-describedby du tracé vise la légende du tableau qui suit la figure', () => {
    const trace = html.match(/role="img" aria-label="Parts des variations[^"]*" aria-describedby="([^"]+)"/)
    expect(trace).not.toBeNull()
    const id = trace?.[1] ?? ''
    const legende = html.indexOf(`<caption id="${id}"`)
    expect(legende).toBeGreaterThan(html.indexOf(trace?.[0] ?? ''))
    expect(html.slice(legende)).toMatch(/^<caption[^>]*>Part de chaque ligne dans les variations/)
  })

  it('ce graphique ne reçoit pas de second tableau ; la carte de corrélation, elle, a le sien', () => {
    const barres = html.indexOf('Parts des variations')
    const legende = html.indexOf('Part de chaque ligne dans les variations')
    expect(html.slice(barres, legende)).not.toContain('<details')
    expect(html.slice(legende)).toContain('<details')
  })

  it("l'étiquette des barres écrit les points en toutes lettres", () => {
    // « 1,9 » prend le singulier, comme partout (points, format.ts).
    expect(html).toContain('JPM +1,9\u00a0point, XOM \u22121,9\u00a0point')
    expect(html).not.toMatch(/aria-label="Parts des variations[^"]*pts/)
  })
})
