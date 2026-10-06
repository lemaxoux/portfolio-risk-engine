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
 *
 * ═══ LA DIAGONALE NE PREND PAS LA COULEUR DE +1 ═══
 *
 * La corrélation d'une ligne avec elle-même vaut 1 par définition. Peinte à la
 * teinte la plus forte de l'échelle, la diagonale attirait l'œil sans rien
 * apprendre. Elle est posée sur `--surface-1`, la surface surélevée, et son
 * « 1,00 » est écrit en `--text-2` : la valeur reste lisible, discrète. Pas sur
 * `--surface-2`, trop proche en thème clair du gris `--div-zero` qui code une
 * corrélation NULLE (#E7E5DE contre #DFDEDB) : la diagonale se serait lue
 * « corrélation ≈ 0 ». L'échelle, elle, ne change pas : son domaine est fixé,
 * pas déduit des cellules qu'elle colore.
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

/** La cellule d'une ligne avec elle-même : 1 par définition, rien à apprendre. */
export function estDiagonale(cellule: Cellule): boolean {
  return cellule.ligne === cellule.colonne
}

/*
 * Géométrie de la carte, en px : la marge des tickers à gauche et au-dessus de
 * la grille, et le côté de ses cellules carrées.
 */
const MARGE_GAUCHE = 52
const MARGE_DROITE = 8
const MARGE_BASSE = 8
const COTE_MIN = 36
const COTE_MAX = 64

/** La hauteur des tickers au-dessus de la grille : la grille commence là. */
export const MARGE_HAUTE_CARTE = 32

/** Le retrait de chaque cellule dans sa bande : le filet entre deux cellules. */
const RETRAIT_CELLULE = 1

/**
 * Le haut de la première rangée de cellules, en px depuis le haut du tracé.
 *
 * Lu dans l'échelle verticale du tracé DESSINÉ, et non recalculé : Plot
 * arrondit la position de ses bandes, et ce haut varie de quelques px avec le
 * nombre de lignes et la place (38 à 42 px pour 6 ou 7 lignes, de 900 à
 * 1280 px de large). C'est sur lui que la lecture de l'échelle s'aligne, à
 * droite de la carte (`SectionRisque`).
 */
export function hautDeGrille(trace: Plot.Plot, matrice: Matrix): number {
  const premiere = matrice.tickers[0]
  const y = trace.scale('y')
  if (premiere === undefined || y === undefined) return MARGE_HAUTE_CARTE
  return Number(y.apply(premiere)) + RETRAIT_CELLULE
}

/** Côté d'une cellule : carrée, entre 36 et 64 px selon la place. */
function coteDeCellule(nombre: number, largeur: number, marge: number): number {
  return Math.max(COTE_MIN, Math.min(COTE_MAX, Math.floor((largeur - marge) / Math.max(nombre, 1))))
}

/**
 * La largeur de la carte quand la place ne manque pas : des cellules de 64 px.
 * Au-delà, la colonne restait vide à droite de la carte ; à partir de 900 px,
 * la lecture de l'échelle y prend place (`SectionRisque`).
 */
export function largeurMaxCarte(nombre: number): number {
  return MARGE_GAUCHE + COTE_MAX * nombre + MARGE_DROITE
}

export function optionsCarteCorrelation(
  matrice: Matrix,
  { couleurs, largeur }: ContexteGraphique,
): Plot.PlotOptions {
  const cellules = cellulesDe(matrice)
  const diagonale = cellules.filter(estDiagonale)
  const horsDiagonale = cellules.filter((c) => !estDiagonale(c))
  // Une marque de texte par encre, de couleur CONSTANTE : une couleur donnée
  // par fonction serait un canal, et Plot la ferait passer par l'échelle de
  // corrélation de la carte.
  const encres = [couleurs.texte1, couleurs.surface0]
  const parEncre = encres.map((encre) =>
    horsDiagonale.filter((c) => encreDeCellule(couleurs, c.valeur) === encre),
  )
  const marge = MARGE_GAUCHE
  const cote = coteDeCellule(matrice.tickers.length, largeur, marge)
  const cote_total = cote * matrice.tickers.length

  return {
    width: marge + cote_total + MARGE_DROITE,
    height: cote_total + MARGE_HAUTE_CARTE + MARGE_BASSE,
    marginLeft: marge,
    marginTop: MARGE_HAUTE_CARTE,
    marginRight: MARGE_DROITE,
    marginBottom: MARGE_BASSE,
    x: { axis: 'top', domain: matrice.tickers, label: null, tickSize: 0 },
    y: { domain: matrice.tickers, label: null, tickSize: 0 },
    color: echelleDeCorrelation(couleurs),
    marks: [
      Plot.cell(horsDiagonale, {
        x: 'colonne',
        y: 'ligne',
        fill: 'valeur',
        inset: RETRAIT_CELLULE,
        ariaDescription: 'corrélations',
      }),
      Plot.cell(diagonale, {
        x: 'colonne',
        y: 'ligne',
        fill: couleurs.surface1,
        inset: RETRAIT_CELLULE,
        ariaDescription: 'diagonale',
      }),
      Plot.text(diagonale, {
        x: 'colonne',
        y: 'ligne',
        text: (c: Cellule) => decimal(c.valeur, 2),
        fill: couleurs.texte2,
        ariaDescription: 'valeurs de la diagonale',
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
