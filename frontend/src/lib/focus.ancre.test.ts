/**
 * Une adresse à fragment, à l'ouverture d'une page (chantier 9.4, DESIGN.md
 * §13).
 *
 * Une section de l'analyse n'existe qu'une fois l'analyse lue : la page qui
 * s'ouvre sur `/portefeuilles/1#en-crise` attend donc son titre, au lieu de
 * s'ouvrir en haut. La règle est ici ; l'effet, le défilement et le focus, se
 * prouve dans Chrome.
 */
import { describe, expect, it } from 'vitest'

import { ancreALOuverture, idDuTitreVise } from './focus'

describe('une adresse à fragment, à l’ouverture de la page', () => {
  it('vise le titre quand il est déjà là, que la page charge ou non', () => {
    expect(ancreALOuverture('cvar', true, false)).toBe('viser')
    expect(ancreALOuverture('cvar', true, true)).toBe('viser')
  })

  it('l’attend quand il n’est pas là et que la page charge encore', () => {
    expect(ancreALOuverture('en-crise', false, true)).toBe('attendre')
  })

  it('n’attend rien d’une page prête : le fragment ne désigne aucun titre', () => {
    expect(ancreALOuverture('rien', false, false)).toBe('ignorer')
  })

  it('sans fragment, il n’y a rien à viser ni à attendre', () => {
    expect(ancreALOuverture('', false, true)).toBe('ignorer')
    expect(ancreALOuverture('', false, false)).toBe('ignorer')
    expect(ancreALOuverture('', true, true)).toBe('ignorer')
  })

  it('le titre attendu d’une section est le sien, pas la section', () => {
    expect(idDuTitreVise('en-crise', ['portefeuille', 'en-crise'])).toBe('en-crise-titre')
  })
})
