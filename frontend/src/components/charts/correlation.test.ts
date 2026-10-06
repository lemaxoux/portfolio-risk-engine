/**
 * La carte de corrélation se lit sur un domaine FIXE, [−1, +1] (§5.4).
 */
import * as Plot from '@observablehq/plot'
import { describe, expect, it } from 'vitest'

import type { Matrix } from '../../api/types'
import type { Couleurs } from './couleurs'
import {
  DOMAINE_CORRELATION,
  MARGE_HAUTE_CARTE,
  type Cellule,
  cellulesDe,
  echelleDeCorrelation,
  encreDeCellule,
  estDiagonale,
  hautDeGrille,
  largeurMaxCarte,
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

interface MarqueInspectee {
  data: readonly Cellule[]
  ariaDescription?: string
  fill?: unknown
  channels: Record<string, { value: unknown } | undefined>
}

describe('la diagonale ne prend pas la couleur de +1', () => {
  const marques = (options(SERRE).marks ?? []) as unknown as MarqueInspectee[]
  const marque = (description: string) => marques.find((m) => m.ariaDescription === description)

  it("les cellules colorées par l'échelle ne comptent aucune cellule de la diagonale", () => {
    const colorees = marque('corrélations')!
    expect(colorees.channels.fill?.value).toBe('valeur')
    expect(colorees.data).toHaveLength(6)
    expect(colorees.data.some(estDiagonale)).toBe(false)
  })

  it('la diagonale est posée sur la surface surélevée, couleur constante hors échelle', () => {
    const diagonale = marque('diagonale')!
    expect(diagonale.data).toHaveLength(3)
    expect(diagonale.data.every(estDiagonale)).toBe(true)
    expect(diagonale.channels.fill).toBeUndefined()
    expect(diagonale.fill).toBe(CLAIR.surface1)
    // Pas --surface-2 : en thème clair, il se confond avec le gris d'une
    // corrélation nulle.
    expect(diagonale.fill).not.toBe(CLAIR.divZero)
  })

  it('sa valeur reste écrite, en encre discrète', () => {
    const valeurs = marque('valeurs de la diagonale')!
    expect(valeurs.fill).toBe(CLAIR.texte2)
    const texte = valeurs.channels.text?.value as (c: Cellule) => string
    expect(valeurs.data.map(texte)).toEqual(['1,00', '1,00', '1,00'])
  })

  it('les valeurs hors diagonale gardent leur encre de contraste, et elles seules', () => {
    const ecrites = marques
      .filter((m) => m.ariaDescription === 'valeurs')
      .flatMap((m) => m.data)
    expect(ecrites).toHaveLength(6)
    expect(ecrites.some(estDiagonale)).toBe(false)
  })

  it("le domaine reste [−1, +1] : l'échelle ne dépend pas des cellules qu'elle colore", () => {
    const echelle = options(SERRE).color as Plot.ScaleOptions
    expect(echelle.domain).toEqual([-1, -0.5, 0, 0.5, 1])
    expect(echelle).toEqual(options(CALME).color)
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

describe('la place de la carte, sur laquelle sa légende se règle', () => {
  const SIX: Matrix = {
    tickers: ['A', 'B', 'C', 'D', 'E', 'F'],
    values: Array.from({ length: 6 }, (_, i) =>
      Array.from({ length: 6 }, (_, j) => (i === j ? 1 : 0.2)),
    ),
  }

  it('quand la place ne manque pas, la carte a sa largeur maximale : des cellules de 64 px', () => {
    // C'est la largeur que la mise en page réserve à la carte à partir de
    // 900 px ; la lecture de l'échelle prend la place qui reste à droite.
    const large = optionsCarteCorrelation(SIX, { couleurs: CLAIR, largeur: 2000 })
    expect(large.width).toBe(largeurMaxCarte(6))
    expect(largeurMaxCarte(6)).toBe(52 + 6 * 64 + 8)
  })

  it('la grille commence sous la marge des tickers', () => {
    expect(options(SERRE).marginTop).toBe(MARGE_HAUTE_CARTE)
  })

  it('le haut de la grille est lu dans l’échelle du tracé dessiné, retrait de la cellule compris', () => {
    // Plot arrondit la position de ses bandes : le haut de la première
    // rangée se lit sur le tracé, il ne se recalcule pas.
    const trace = {
      scale: (nom: string) => (nom === 'y' ? { apply: (t: string) => (t === 'A' ? 41 : NaN) } : undefined),
    }
    expect(hautDeGrille(trace as unknown as Plot.Plot, SERRE)).toBe(42)
    const sansEchelle = { scale: () => undefined }
    expect(hautDeGrille(sansEchelle as unknown as Plot.Plot, SERRE)).toBe(MARGE_HAUTE_CARTE)
  })
})
