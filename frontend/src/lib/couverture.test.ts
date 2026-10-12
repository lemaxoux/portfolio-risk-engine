/**
 * L'écriture de la couverture d'une crise — DESIGN.md §11.2, §19.3 (chantier
 * 9.4).
 *
 * Le bloc d'une crise, en section 5, et le bloc du résultat de la page de
 * présentation écrivent la couverture par la même fonction : même part, mêmes
 * lignes, et le point de réserve dès qu'elle est sous 100 %.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import type { Coverage } from '../api/types'
import { ecrireLaCouverture } from './couverture'
import { ESPACE_FINE, ESPACE_INSECABLE } from './format'

function couverture(couvertes: number, total: number, part: number): Coverage {
  return {
    covered: [],
    excluded: [],
    covered_value: part,
    total_value: 1,
    value_share: part,
    is_complete: couvertes === total,
    covered_count: couvertes,
    total_count: total,
  }
}

describe('l’écriture de la couverture', () => {
  it('complète : la part, les lignes, aucun point', () => {
    expect(ecrireLaCouverture(couverture(6, 6, 1), 'fr')).toEqual({
      part: `100${ESPACE_FINE}%`,
      lignes: `6${ESPACE_INSECABLE}lignes sur 6`,
      partielle: false,
    })
    expect(ecrireLaCouverture(couverture(6, 6, 1), 'en')).toEqual({
      part: '100%',
      lignes: `6${ESPACE_INSECABLE}holdings out of 6`,
      partielle: false,
    })
  })

  it('porte le point dès qu’elle est sous 100 %, pas seulement sous le seuil', () => {
    expect(ecrireLaCouverture(couverture(5, 6, 0.93), 'fr')).toEqual({
      part: `93${ESPACE_FINE}%`,
      lignes: `5${ESPACE_INSECABLE}lignes sur 6`,
      partielle: true,
    })
    expect(ecrireLaCouverture(couverture(4, 6, 0.73), 'fr').partielle).toBe(true)
  })

  it('lit ce que le moteur publie, sans le recalculer', () => {
    // `is_complete` décide, pas une comparaison de la part à 1 ni des comptes.
    const publiee = { ...couverture(6, 6, 0.9999), is_complete: true }
    expect(ecrireLaCouverture(publiee, 'fr').partielle).toBe(false)
    expect(ecrireLaCouverture({ ...couverture(6, 6, 1), is_complete: false }, 'fr').partielle).toBe(true)
  })
})

describe('un seul code pour les deux blocs', () => {
  const VUES = join(import.meta.dirname, '..', 'views')
  const section5 = readFileSync(join(VUES, 'SectionCrise.tsx'), 'utf-8')
  const presentation = readFileSync(join(VUES, 'Presentation.tsx'), 'utf-8')

  it('la section 5 et la page de présentation appellent la même fonction', () => {
    expect(section5).toContain('ecrireLaCouverture(')
    expect(presentation).toContain('ecrireLaCouverture(')
  })

  it('aucune des deux n’écrit la couverture elle-même', () => {
    for (const source of [section5, presentation]) {
      expect(source).not.toContain('.couvertes(')
      expect(source).not.toContain('value_share')
    }
  })
})
