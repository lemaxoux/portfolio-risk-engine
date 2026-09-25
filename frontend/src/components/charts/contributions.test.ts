/**
 * Barre : part de la variance — trait : part du capital, sur le même axe.
 */
import type * as Plot from '@observablehq/plot'
import { describe, expect, it } from 'vitest'

import type { Contribution } from '../../api/types'
import { ESPACE_INSECABLE, SIGNE_MOINS } from '../../lib/format'
import type { Couleurs } from './couleurs'
import { lignesParContribution, optionsContributions } from './contributions'

const COULEURS = new Proxy({} as Couleurs, { get: (_, cle) => `couleur-${String(cle)}` })

const LIGNES: Contribution[] = [
  { ticker: 'KO', contribution: -0.02, weight: 0.13, excess_over_weight: -0.15 },
  { ticker: 'JPM', contribution: 0.354, weight: 0.256, excess_over_weight: 0.098 },
]

interface MarqueInspectee {
  data: unknown
  ariaDescription?: string
  channels: Record<string, { value: unknown } | undefined>
}

const options = optionsContributions(LIGNES, { couleurs: COULEURS, largeur: 700 })
const marques = (options.marks ?? []) as unknown as MarqueInspectee[]
const marque = (description: string) => marques.find((m) => m.ariaDescription === description)

describe('part de variance et part de capital', () => {
  it('la barre lit la contribution, le trait lit le poids, sur le même axe x', () => {
    expect(marque('part de la variance')?.channels.x1?.value).toBe(0)
    expect(marque('part de la variance')?.channels.x2?.value).toBe('contribution')
    expect(marque('part du capital')?.channels.x?.value).toBe('weight')
  })

  it('l’axe contient zéro : une contribution négative part à gauche', () => {
    expect((options.x as Plot.ScaleOptions).zero).toBe(true)
  })

  it('écrit l’écart publié en points, sans le recalculer', () => {
    const texte = marque('écart en points')?.channels.text?.value as (l: Contribution) => string
    expect(texte(LIGNES[1]!)).toBe(`+9,8${ESPACE_INSECABLE}pts`)
    expect(texte(LIGNES[0]!)).toBe(`${SIGNE_MOINS}15,0${ESPACE_INSECABLE}pts`)
  })

  it('range la part de variance la plus lourde en tête', () => {
    expect(lignesParContribution(LIGNES).map((l) => l.ticker)).toEqual(['JPM', 'KO'])
  })
})
