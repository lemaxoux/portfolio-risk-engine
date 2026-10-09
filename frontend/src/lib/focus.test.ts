/**
 * Les décisions de focus, sans document (chantier 7E, DESIGN.md §13).
 *
 * Où va le focus après un geste est une règle : elle est vérifiée ici.
 * L'effet, le focus réellement posé et visible, se vérifie dans Chrome
 * (`docs/outils/clavier.mjs`, hors dépôt).
 */
import { describe, expect, it } from 'vitest'

import { SECTIONS } from '../components/Navigation'
import { idDuTitreVise, rangeeApresRetrait } from './focus'

const ANCRES = SECTIONS.map((section) => section.ancre)

describe('le titre que vise une ancre', () => {
  it('une section de l’analyse : son titre, qui porte `-titre`', () => {
    expect(idDuTitreVise('qui-porte', ANCRES)).toBe('qui-porte-titre')
    expect(ANCRES.map((ancre) => idDuTitreVise(ancre, ANCRES))).toEqual([
      'portefeuille-titre',
      'jour-ordinaire-titre',
      'au-pire-titre',
      'qui-porte-titre',
      'en-crise-titre',
      'moteur-titre',
    ])
  })

  it('ailleurs, le titre qui porte l’ancre lui-même : une entrée de la méthodologie', () => {
    expect(idDuTitreVise('cvar', ANCRES)).toBe('cvar')
    expect(idDuTitreVise('var-historique', ANCRES)).toBe('var-historique')
  })
})

describe('la rangée qui reçoit le focus après « Retirer »', () => {
  it('celle qui prend la place de la rangée retirée', () => {
    expect(rangeeApresRetrait(0, 6)).toBe(0)
    expect(rangeeApresRetrait(2, 6)).toBe(2)
  })

  it('la nouvelle dernière, quand la rangée retirée était la dernière', () => {
    expect(rangeeApresRetrait(5, 6)).toBe(4)
    expect(rangeeApresRetrait(1, 2)).toBe(0)
  })

  it('la rangée vierge qui remplace la seule rangée retirée', () => {
    expect(rangeeApresRetrait(0, 1)).toBe(0)
  })

  it('toujours une rangée du tableau d’après, jamais au-delà', () => {
    for (let nombre = 1; nombre <= 8; nombre++) {
      const apres = Math.max(nombre - 1, 1)
      for (let rang = 0; rang < nombre; rang++) {
        const cible = rangeeApresRetrait(rang, nombre)
        expect(cible).toBeGreaterThanOrEqual(0)
        expect(cible).toBeLessThan(apres)
      }
    }
  })
})
