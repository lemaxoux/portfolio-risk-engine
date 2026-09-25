/**
 * Les couleurs des graphiques viennent des tokens, et d'eux seuls.
 *
 * Ce qui est vérifié : chaque nom lu par un graphique est déclaré dans
 * `tokens.css` ; un token introuvable fait échouer le tracé au lieu de laisser
 * Plot choisir une couleur ; le choix d'encre sur une cellule colorée prend la
 * plus contrastée.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { JETONS, contraste, encreLisible, lireCouleurs } from './couleurs'

const TOKENS = readFileSync(
  fileURLToPath(new URL('../../styles/tokens.css', import.meta.url)),
  'utf-8',
)

describe('les couleurs d’un graphique sont des tokens déclarés', () => {
  it('chaque nom lu par un graphique est déclaré dans tokens.css', () => {
    for (const nom of Object.values(JETONS)) {
      expect(TOKENS, nom).toMatch(new RegExp(`^\\s*${nom}:`, 'm'))
    }
  })

  it('aucune couleur de perte ou de gain : elles sont réservées au tableau de stress (§5.3)', () => {
    expect(Object.values(JETONS)).not.toContain('--loss')
    expect(Object.values(JETONS)).not.toContain('--gain')
  })

  it('un token introuvable fait échouer la lecture', () => {
    // Plot remplacerait une chaîne vide par sa couleur par défaut : un
    // graphique juste, dans une couleur que personne n'a choisie.
    const lire = (nom: string) => (nom === '--series-1' ? '' : '#123456')
    expect(() => lireCouleurs(lire)).toThrow('--series-1')
  })

  it('rend chaque token sous son nom de code', () => {
    const couleurs = lireCouleurs((nom) => ` valeur-de${nom} `)
    expect(couleurs.serie1).toBe('valeur-de--series-1')
    expect(couleurs.divZero).toBe('valeur-de--div-zero')
  })
})

describe('encre d’une valeur écrite sur une cellule', () => {
  it('calcule le contraste WCAG', () => {
    expect(contraste('#000000', '#ffffff')).toBeCloseTo(21, 5)
    expect(contraste('rgb(255, 255, 255)', '#ffffff')).toBeCloseTo(1, 5)
  })

  it('choisit l’encre la plus lisible parmi les candidates', () => {
    expect(encreLisible('#1870a1', ['#22252a', '#fbfaf7'])).toBe('#fbfaf7')
    expect(encreLisible('#dfdedb', ['#22252a', '#fbfaf7'])).toBe('#22252a')
  })
})
