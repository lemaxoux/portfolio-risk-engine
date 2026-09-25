/**
 * Carte de corrélation — DESIGN.md §5.4.
 *
 * ═══ DOMAINE FIXÉ À [−1, +1], NON NÉGOCIABLE ═══
 *
 * L'échelle ne s'adapte JAMAIS aux données. Auto-ajustée, elle ferait paraître
 * identiques un portefeuille dont la corrélation maximale est 0,55 et un autre
 * où elle est 0,97 — exactement la comparaison que l'outil existe pour
 * permettre. `echelleDeCorrelation` ne reçoit donc aucune donnée : elle ne le
 * PEUT pas.
 *
 * Interpolation en Lab entre les cinq points de §5.4 : bleu diversifiant à
 * −1, gris neutre à 0 (distinct de la surface : une cellule nulle reste une
 * cellule), brique à +1, bras symétriques en luminosité.
 *
 * ═══ LA VALEUR EST ÉCRITE DANS CHAQUE CELLULE ═══
 *
 * Deux décimales. C'est le canal de secours : la couleur n'est qu'une lecture
 * rapide. L'encre de la valeur est choisie PAR CONTRASTE avec la cellule —
 * voir `encreDeCellule`.
 */
import * as Plot from '@observablehq/plot'

import type { Matrix } from '../../api/types'
import { decimal } from '../../lib/format'
import { encreLisible, type Couleurs } from './couleurs'
import type { ContexteGraphique } from './Graphique'

/** Les cinq points de §5.4, et le domaine qui leur correspond. */
export const DOMAINE_CORRELATION = [-1, -0.5, 0, 0.5, 1] as const

export function echelleDeCorrelation(couleurs: Couleurs): Plot.ScaleOptions {
  return {
    type: 'linear',
    domain: [...DOMAINE_CORRELATION],
    range: [
      couleurs.divNegFort,
      couleurs.divNegMoyen,
      couleurs.divZero,
      couleurs.divPosMoyen,
      couleurs.divPosFort,
    ],
    interpolate: 'lab',
    clamp: true,
  }
}

export interface Cellule {
  readonly ligne: string
  readonly colonne: string
  readonly valeur: number
}

/** La matrice publiée, cellule par cellule — un changement de forme, pas un calcul. */
export function cellulesDe(matrice: Matrix): Cellule[] {
  return matrice.tickers.flatMap((ligne, i) =>
    matrice.tickers.map((colonne, j) => ({
      ligne,
      colonne,
      valeur: matrice.values[i]?.[j] ?? Number.NaN,
    })),
  )
}

/**
 * L'encre d'une valeur écrite sur sa cellule : `--text-1` ou `--surface-0`,
 * la plus contrastée.
 *
 * DESIGN.md §5.4 prévoit `--text-1` ou `--text-2`. Le calcul montre que ni
 * l'un ni l'autre ne suffit aux extrémités de l'échelle : sur la brique de +1
 * en thème clair, `--text-1` ne donne que 2,6:1 ; sur la brique du thème
 * sombre, 2,8:1. Sur ces cellules saturées, il faut l'encre INVERSE — la
 * surface de la page, claire en thème clair et foncée en thème sombre.
 */
export function encreDeCellule(couleurs: Couleurs, valeur: number): string {
  const fond = Plot.scale({ color: echelleDeCorrelation(couleurs) }).apply(valeur) as string
  return encreLisible(fond, [couleurs.texte1, couleurs.surface0])
}

/** Côté d'une cellule : carrée, entre 36 et 64 px selon la place. */
function coteDeCellule(nombre: number, largeur: number, marge: number): number {
  return Math.max(36, Math.min(64, Math.floor((largeur - marge) / Math.max(nombre, 1))))
}

export function optionsCarteCorrelation(
  matrice: Matrix,
  { couleurs, largeur }: ContexteGraphique,
): Plot.PlotOptions {
  const cellules = cellulesDe(matrice)
  // Une marque de texte par encre, de couleur CONSTANTE : une couleur donnée
  // par fonction serait un canal, et Plot la ferait passer par l'échelle de
  // corrélation de la carte.
  const encres = [couleurs.texte1, couleurs.surface0]
  const parEncre = encres.map((encre) =>
    cellules.filter((c) => encreDeCellule(couleurs, c.valeur) === encre),
  )
  const marge = 52
  const cote = coteDeCellule(matrice.tickers.length, largeur, marge)
  const cote_total = cote * matrice.tickers.length

  return {
    width: marge + cote_total + 8,
    height: cote_total + 40,
    marginLeft: marge,
    marginTop: 32,
    marginRight: 8,
    marginBottom: 8,
    x: { axis: 'top', domain: matrice.tickers, label: null, tickSize: 0 },
    y: { domain: matrice.tickers, label: null, tickSize: 0 },
    color: echelleDeCorrelation(couleurs),
    marks: [
      Plot.cell(cellules, {
        x: 'colonne',
        y: 'ligne',
        fill: 'valeur',
        inset: 1,
        ariaDescription: 'corrélations',
      }),
      ...encres.map((encre, rang) =>
        Plot.text(parEncre[rang] ?? [], {
          x: 'colonne',
          y: 'ligne',
          text: (c: Cellule) => decimal(c.valeur, 2),
          fill: encre,
          ariaDescription: 'valeurs',
        }),
      ),
      Plot.tip(
        cellules,
        Plot.pointer({
          x: 'colonne',
          y: 'ligne',
          title: (c: Cellule) =>
            `${c.ligne} et ${c.colonne}\ncorrélation ${decimal(c.valeur, 2)}`,
          fill: couleurs.surface1,
          stroke: couleurs.bordureForte,
        }),
      ),
    ],
  }
}
