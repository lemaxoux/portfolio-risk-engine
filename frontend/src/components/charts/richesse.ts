/**
 * Courbe de richesse et creux maximal — DESIGN.md §8.2 (section 3), §9.4.
 *
 * ═══ LA COURBE PUBLIÉE, ET RIEN D'AUTRE ═══
 *
 * Les points sont `series.wealth`, tels que le moteur les a calculés, point de
 * départ à 1,0 compris : sans lui, un portefeuille qui baisse dès sa première
 * séance perdrait le sommet d'où part son creux. Un test backend vérifie que
 * le creux recalculé sur ces points est exactement `risk.drawdown`.
 *
 * ═══ LE CREUX EST OMBRÉ, SES DATES SONT SUR LA COURBE ═══
 *
 * L'aire entre le niveau du pic et la courbe, du pic au creux, à 0,15
 * d'opacité, sans dégradé (§9.4). Le pic et le creux sont marqués d'un point
 * SUR la courbe, leurs dates écrites à côté — pas dans une légende détachée.
 * Le niveau du pic n'est pas calculé : c'est le point publié à `peak_date`.
 */
import * as Plot from '@observablehq/plot'

import type { Drawdown, Point } from '../../api/types'
import { dateDepuisISO, dateISO, decimal, moisISO, pourcentage } from '../../lib/format'
import type { ContexteGraphique } from './Graphique'
import { halo } from './habillage'

export const HAUTEUR_RICHESSE = 280

interface PointDate {
  readonly date: Date
  readonly iso: string
  readonly value: number
}

function enDates(points: readonly Point[]): PointDate[] {
  return points.map((point) => ({
    date: dateDepuisISO(point.date),
    iso: point.date,
    value: point.value,
  }))
}

/** Les points publiés entre le pic et le creux, bornes incluses. */
export function pointsDuCreux(richesse: readonly Point[], creux: Drawdown): Point[] {
  return richesse.filter(
    (point) => point.date >= creux.peak_date && point.date <= creux.trough_date,
  )
}

/** Le point publié à une date donnée — une lecture, pas un calcul. */
export function pointA(richesse: readonly Point[], date: string): Point {
  const point = richesse.find((candidat) => candidat.date === date)
  if (point === undefined) {
    throw new Error(`Aucun point de la courbe publiée au ${date}.`)
  }
  return point
}

interface Donnees {
  readonly richesse: readonly Point[]
  readonly creux: Drawdown
}

export function optionsRichesse(
  { richesse, creux }: Donnees,
  { couleurs, largeur }: ContexteGraphique,
): Plot.PlotOptions {
  const courbe = enDates(richesse)
  const pic = pointA(richesse, creux.peak_date)
  const fond = pointA(richesse, creux.trough_date)
  const zone = enDates(pointsDuCreux(richesse, creux))
  const annotations = enDates([pic, fond])

  return {
    height: HAUTEUR_RICHESSE,
    marginLeft: 44,
    marginRight: 16,
    marginBottom: 32,
    x: {
      type: 'utc',
      label: null,
      ticks: largeur >= 640 ? 8 : 4,
      tickFormat: (date: Date) => moisISO(date),
    },
    y: {
      label: null,
      tickFormat: (valeur: number) => decimal(valeur, 2),
      // De la place DANS le cadre, sous le point le plus bas et au-dessus du
      // plus haut : l'annotation du creux, posée sous lui, ne doit pas
      // déborder sur les dates de l'axe.
      insetBottom: 40,
      insetTop: 12,
    },
    marks: [
      Plot.gridY({ stroke: couleurs.bordure, strokeOpacity: 1 }),
      // Le niveau de départ : ce qu'on avait investi.
      Plot.ruleY([1], { stroke: couleurs.bordureForte }),
      Plot.areaY(zone, {
        x: 'date',
        y1: pic.value,
        y2: 'value',
        fill: couleurs.serie1,
        fillOpacity: 0.15,
        ariaDescription: 'creux maximal',
      }),
      Plot.lineY(courbe, {
        x: 'date',
        y: 'value',
        stroke: couleurs.serie1,
        strokeWidth: 2,
        ariaDescription: 'courbe de richesse',
      }),
      Plot.dot(annotations, {
        x: 'date',
        y: 'value',
        r: 4,
        fill: couleurs.texte1,
        stroke: couleurs.surface0,
        strokeWidth: 2,
      }),
      Plot.text([annotations[0]], {
        x: 'date',
        y: 'value',
        dy: -10,
        lineAnchor: 'bottom',
        text: (p: PointDate) => `pic\n${dateISO(p.iso)}`,
        ...halo(couleurs, couleurs.texte1),
      }),
      Plot.text([annotations[1]], {
        x: 'date',
        y: 'value',
        dy: 10,
        lineAnchor: 'top',
        text: (p: PointDate) =>
          `creux ${pourcentage(creux.value, 1)}\n${dateISO(p.iso)}`,
        ...halo(couleurs, couleurs.texte1),
      }),
      Plot.tip(
        courbe,
        Plot.pointerX({
          x: 'date',
          y: 'value',
          title: (p: PointDate) => `${dateISO(p.iso)}\n${decimal(p.value, 3)}`,
          fill: couleurs.surface1,
          stroke: couleurs.bordureForte,
        }),
      ),
    ],
  }
}
