/**
 * Les décisions de focus, sans document (chantier 7E, DESIGN.md §13).
 *
 * Où va le focus après un geste est une règle : elle est vérifiée ici.
 * L'effet, le focus réellement posé et visible, se vérifie dans Chrome
 * (`docs/outils/clavier.mjs`, hors dépôt).
 */
import { describe, expect, it } from 'vitest'

import { SECTIONS } from '../components/Navigation'
import { cleDeRetour, idDuTitreVise, noteDeRetour, rangeeApresRetrait, resoudreRetour } from './focus'

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

describe('le retour depuis la méthode', () => {
  it('la clé d’un lien est son bloc ET son ancre : deux liens vers la même entrée restent distincts', () => {
    expect(cleDeRetour('var-historique-0.95', 'var-historique')).toBe('var-historique-0.95#var-historique')
    expect(cleDeRetour('var-historique-0.95', 'var-historique')).not.toBe(
      cleDeRetour('var-historique-0.99', 'var-historique'),
    )
  })

  it('la note se lit dans l’état d’une entrée d’historique, si elle est bien formée', () => {
    expect(noteDeRetour({ retour: { cle: 'cvar-0.95#cvar', y: 4757 } })).toEqual({
      cle: 'cvar-0.95#cvar',
      y: 4757,
    })
    expect(noteDeRetour(null)).toBeNull()
    expect(noteDeRetour({ retour: null })).toBeNull()
    expect(noteDeRetour({ retour: { cle: 'x' } })).toBeNull()
    expect(noteDeRetour({ retour: { cle: 3, y: 0 } })).toBeNull()
    expect(noteDeRetour('retour')).toBeNull()
  })

  it('au retour, le lien suivi reprend le focus s’il est sur la page, quelle que soit sa position', () => {
    const note = { cle: 'cvar-0.99#cvar', y: 4757 }
    expect(resoudreRetour(note, ['cvar-0.95#cvar', 'cvar-0.99#cvar'])).toEqual({ focus: 'cvar-0.99#cvar' })
  })

  it('la position notée ne sert que si la clé est introuvable', () => {
    expect(resoudreRetour({ cle: 'crise-x#couverture', y: 4757 }, ['cvar-0.95#cvar'])).toEqual({ y: 4757 })
  })

  it('sans note, rien : la page fait comme pour toute autre navigation', () => {
    expect(resoudreRetour(null, ['cvar-0.95#cvar'])).toBeNull()
  })
})
