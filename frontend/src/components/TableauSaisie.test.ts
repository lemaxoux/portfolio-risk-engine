/**
 * L'ordre des colonnes du tableau de saisie suit la largeur — même mécanisme
 * que la section 1 (`useEtroit`).
 */
import { describe, expect, it } from 'vitest'

import { ORDRE_ETROIT, ORDRE_LARGE, ordreDesColonnes } from './TableauSaisie'

describe("tableau de saisie — l'ordre des colonnes suit la largeur", () => {
  it("en large, l'ordre de lecture : ticker, nom, historique, quantité, prix", () => {
    expect(ordreDesColonnes(false)).toEqual(['ticker', 'nom', 'historique', 'quantite', 'prix'])
  })

  it('sous 900 px, la quantité suit le ticker, et aucune colonne ne se perd', () => {
    // À 390 px, l'ordre large rejetait la quantité hors du cadre.
    expect(ordreDesColonnes(true)).toEqual(['ticker', 'quantite', 'nom', 'historique', 'prix'])
    expect([...ORDRE_ETROIT].sort()).toEqual([...ORDRE_LARGE].sort())
  })
})
