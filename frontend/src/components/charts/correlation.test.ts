/**
 * La carte de corrélation se lit sur un domaine FIXE, [−1, +1] (§5.4).
 */
import * as Plot from '@observablehq/plot'
import { describe, expect, it } from 'vitest'

import type { Matrix } from '../../api/types'
import type { Couleurs } from './couleurs'
import {
  DOMAINE_CORRELATION,
  cellulesDe,
  echelleDeCorrelation,
  encreDeCellule,
  optionsCarteCorrelation,
} from './correlation'

// Les couleurs du thème CLAIR de DESIGN.md §5.2 : ce test porte sur des
// contrastes réels, pas sur des noms.
const CLAIR: Couleurs = {
  surface0: '#f2f1ec',
  surface1: '#fbfaf7',
  surface2: '#e7e5de',
  bordure: '#cbc7bc',
  bordureForte: '#868276',
  texte1: '#22252a',
  texte2: '#585e65',
  reserve: '#7e6110',
  serie1: '#058d85',
  divNegFort: '#1870a1',
  divNegMoyen: '#7fb2d6',
  divZero: '#dfdedb',
  divPosMoyen: '#d6998f',
  divPosFort: '#a74639',
}

const CALME: Matrix = {
  tickers: ['A', 'B'],
  values: [
    [1, 0.55],
    [0.55, 1],
  ],
}

const SERRE: Matrix = {
  tickers: ['A', 'B', 'C'],
  values: [
    [1, 0.97, 0.9],
    [0.97, 1, 0.95],
    [0.9, 0.95, 1],
  ],
}

function options(matrice: Matrix) {
  return optionsCarteCorrelation(matrice, { couleurs: CLAIR, largeur: 700 })
}

describe('domaine fixe, indépendant des données', () => {
  it('deux matrices différentes ont exactement la même échelle', () => {
    // Auto-ajustée, l'échelle ferait paraître identiques une corrélation
    // maximale de 0,55 et une de 0,97.
    expect(options(CALME).color).toEqual(options(SERRE).color)
  })

  it('le domaine est [−1, +1], en cinq points, interpolé en Lab', () => {
    const echelle = echelleDeCorrelation(CLAIR)
    expect(echelle.domain).toEqual([-1, -0.5, 0, 0.5, 1])
    expect([...DOMAINE_CORRELATION]).toEqual([-1, -0.5, 0, 0.5, 1])
    expect(echelle.interpolate).toBe('lab')
  })

  it('une même valeur prend la même couleur dans les deux cartes', () => {
    const couleurDans = (matrice: Matrix) =>
      Plot.scale({ color: options(matrice).color as Plot.ScaleOptions }).apply(0.9)
    expect(couleurDans(CALME)).toBe(couleurDans(SERRE))
  })

  it('les extrémités et le milieu tombent sur les tokens de §5.4', () => {
    const echelle = Plot.scale({ color: echelleDeCorrelation(CLAIR) })
    const rgb = (hexa: string) => {
      const [r, v, b] = [1, 3, 5].map((i) => parseInt(hexa.slice(i, i + 2), 16))
      return `rgb(${r}, ${v}, ${b})`
    }
    expect(echelle.apply(-1)).toBe(rgb(CLAIR.divNegFort))
    expect(echelle.apply(0)).toBe(rgb(CLAIR.divZero))
    expect(echelle.apply(1)).toBe(rgb(CLAIR.divPosFort))
  })
})

describe('la valeur est écrite dans chaque cellule', () => {
  it('une cellule par couple, avec la valeur publiée', () => {
    const cellules = cellulesDe(SERRE)
    expect(cellules).toHaveLength(9)
    expect(cellules).toContainEqual({ ligne: 'B', colonne: 'C', valeur: 0.95 })
  })

  it('l’encre choisie reste lisible aux extrémités de l’échelle', () => {
    // Sur la brique de +1 en thème clair, --text-1 ne donne que 2,6:1 : c'est
    // l'encre inverse, la surface, qui est choisie.
    expect(encreDeCellule(CLAIR, 1)).toBe(CLAIR.surface0)
    expect(encreDeCellule(CLAIR, 0)).toBe(CLAIR.texte1)
  })
})
