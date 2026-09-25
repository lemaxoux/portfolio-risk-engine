/**
 * Part de la variance contre part du capital — DESIGN.md §5.4, §11.4.
 *
 * Une barre par ligne en `--series-1` pour la part de variance ; un trait
 * vertical fin en `--text-1` à la position de la part de capital, sur le MÊME
 * axe. L'écart entre le bout de la barre et le trait EST le message ; il est
 * aussi écrit en points à droite (« +9,8 pts »), depuis `excess_over_weight`
 * que le moteur publie — aucune soustraction ici. Pas de barres appariées de
 * deux couleurs.
 *
 * L'axe contient toujours zéro : une contribution NÉGATIVE (une ligne qui a
 * évolué à rebours du reste) part vers la gauche, et doit pouvoir se voir.
 */
import * as Plot from '@observablehq/plot'

import type { Contribution } from '../../api/types'
import { pourcentage, pointsSignes } from '../../lib/format'
import type { ContexteGraphique } from './Graphique'

/** Hauteur d'une ligne de barre : lisible, et bien au-dessus d'une cible tactile. */
const HAUTEUR_LIGNE = 34

/** L'ordre d'affichage : la part de variance la plus lourde en tête. */
export function lignesParContribution(lignes: readonly Contribution[]): Contribution[] {
  return [...lignes].sort((a, b) => b.contribution - a.contribution)
}

export function texteDeContribution(ligne: Contribution): string {
  return (
    `${ligne.ticker}\n` +
    `part de la variance ${pourcentage(ligne.contribution, 1)}\n` +
    `part du capital ${pourcentage(ligne.weight, 1)}\n` +
    `écart ${pointsSignes(ligne.excess_over_weight, 1)}`
  )
}

export function optionsContributions(
  lignes: readonly Contribution[],
  { couleurs }: ContexteGraphique,
): Plot.PlotOptions {
  const ordre = lignesParContribution(lignes)

  return {
    height: ordre.length * HAUTEUR_LIGNE + 40,
    marginLeft: 52,
    marginRight: 76,
    marginBottom: 28,
    x: {
      zero: true,
      label: null,
      tickFormat: (valeur: number) => pourcentage(valeur, 0),
    },
    y: {
      domain: ordre.map((ligne) => ligne.ticker),
      label: null,
      padding: 0.3,
    },
    marks: [
      Plot.gridX({ stroke: couleurs.bordure, strokeOpacity: 1 }),
      // Bornes explicites, de zéro à la part : sans elles, `barX` empilerait
      // les valeurs (transformation implicite), ce qui revient au même ici
      // mais ne se lit plus dans la marque.
      Plot.barX(ordre, {
        x1: 0,
        x2: 'contribution',
        y: 'ticker',
        fill: couleurs.serie1,
        ariaDescription: 'part de la variance',
      }),
      Plot.tickX(ordre, {
        x: 'weight',
        y: 'ticker',
        stroke: couleurs.texte1,
        strokeWidth: 2,
        ariaDescription: 'part du capital',
      }),
      Plot.ruleX([0], { stroke: couleurs.bordureForte }),
      Plot.text(ordre, {
        y: 'ticker',
        frameAnchor: 'right',
        dx: 72,
        textAnchor: 'end',
        text: (ligne: Contribution) => pointsSignes(ligne.excess_over_weight, 1),
        fill: couleurs.texte1,
        ariaDescription: 'écart en points',
      }),
      Plot.tip(
        ordre,
        Plot.pointerY({
          x: 'contribution',
          y: 'ticker',
          title: texteDeContribution,
          fill: couleurs.surface1,
          stroke: couleurs.bordureForte,
        }),
      ),
    ],
  }
}
