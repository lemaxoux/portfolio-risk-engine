/**
 * Histogramme des rendements quotidiens — DESIGN.md §8.2 (section 2), §9.4.
 *
 * ═══ LES CLASSES SONT CELLES DU MOTEUR ═══
 *
 * Chaque barre est une classe PUBLIÉE (`histogram.bins`), dessinée par ses
 * bornes et son compte, telle quelle : `Plot.rect` sur `lower`, `upper` et
 * `count`, sans aucune transformation. Pas de `binX` — le découpage de Plot
 * s'ajusterait à chaque portefeuille, et deux portefeuilles ne se liraient
 * plus sur la même grille (voir `HISTOGRAM_BIN_WIDTH` côté moteur).
 *
 * ═══ LES QUANTILES SONT CEUX DU MOTEUR, DANS LA CONVENTION DE L'AXE ═══
 *
 * L'axe porte des RENDEMENTS ; une VaR est une PERTE POSITIVE. Placer la VaR
 * sur l'axe demanderait d'en retourner le signe, ce que l'interface ne fait
 * jamais (§9.1). Le moteur publie le même quantile dans la convention de
 * l'axe : `expected_shortfall.threshold`, dont un test backend vérifie qu'il
 * vaut exactement l'opposé de la VaR historique du même niveau. C'est lui qui
 * place les traits ; l'étiquette, elle, écrit la VaR telle que publiée.
 *
 * ═══ LA QUEUE OMBRÉE ═══
 *
 * La CVaR 95 % est la perte moyenne des séances situées sous le quantile à
 * 95 %. Ces séances sont ombrées — une aire à 0,15 d'opacité, sans dégradé
 * (§9.4) — et leur nombre, `tail_observations`, est écrit dans l'aire : ce
 * sont les barres qu'on voit, comptées par le moteur.
 */
import * as Plot from '@observablehq/plot'

import type { HistogramBin, ReturnHistogram, TailRiskLevel } from '../../api/types'
import { decimal, pourcentage, seances } from '../../lib/format'
import type { ContexteGraphique } from './Graphique'
import { halo } from './habillage'

export const HAUTEUR_HISTOGRAMME = 260

/** Ce que dit une barre au survol : son compte exact et ses bornes (§8.2). */
export function texteDeClasse(classe: HistogramBin): string {
  return (
    `${seances(classe.count)}\n` +
    `de ${pourcentage(classe.lower, 2)} inclus à ${pourcentage(classe.upper, 2)} exclu`
  )
}

/**
 * Graduations de l'axe des rendements : des multiples ronds d'un pas, qui
 * contiennent toujours zéro. Le pas s'élargit quand la place manque, pour que
 * les étiquettes ne se chevauchent pas à 390 px.
 */
export function graduationsDeRendement(
  debut: number,
  fin: number,
  largeur: number,
): number[] {
  const pas = largeur >= 640 ? 0.01 : largeur >= 420 ? 0.02 : 0.03
  const graduations: number[] = []
  for (let rang = Math.ceil(debut / pas); rang * pas <= fin + 1e-12; rang += 1) {
    graduations.push(Math.round(rang * pas * 1e6) / 1e6)
  }
  return graduations
}

interface Donnees {
  readonly histogramme: ReturnHistogram
  /** Les niveaux de confiance publiés, du moins au plus exigeant. */
  readonly niveaux: readonly TailRiskLevel[]
}

export function optionsHistogramme(
  { histogramme, niveaux }: Donnees,
  { couleurs, largeur }: ContexteGraphique,
): Plot.PlotOptions {
  const classes = histogramme.bins
  const debut = classes[0]?.lower ?? 0
  const fin = classes[classes.length - 1]?.upper ?? 0
  const niveau95 = niveaux.find((niveau) => niveau.confidence === 0.95)

  const marques: Plot.Markish[] = [
    Plot.gridY({ stroke: couleurs.bordure, strokeOpacity: 1 }),
  ]

  if (niveau95 !== undefined) {
    const queue = niveau95.expected_shortfall
    marques.push(
      // Sans canal y, le rectangle couvre toute la hauteur du cadre : aucune
      // hauteur n'est calculée ici.
      Plot.rect([queue], {
        x1: debut,
        x2: queue.threshold,
        fill: couleurs.texte1,
        fillOpacity: 0.15,
        ariaDescription: 'queue de la CVaR à 95 %',
      }),
      // À mi-hauteur, à gauche : la zone la plus vide du graphique, loin des
      // étiquettes de quantile posées en haut.
      Plot.text([queue], {
        x: debut,
        frameAnchor: 'left',
        dx: 4,
        text: (q: typeof queue) =>
          `queue à ${pourcentage(q.confidence, 0)} :\n${seances(q.tail_observations)}`,
        textAnchor: 'start',
        lineAnchor: 'middle',
        ...halo(couleurs, couleurs.texte2),
      }),
    )
  }

  marques.push(
    Plot.rect(classes, {
      x1: 'lower',
      x2: 'upper',
      y1: 0,
      y2: 'count',
      inset: 0.5,
      fill: couleurs.serie1,
      ariaDescription: 'classes de rendements',
    }),
    Plot.ruleX([0], { stroke: couleurs.bordureForte }),
    Plot.ruleY([0], { stroke: couleurs.bordureForte }),
  )

  // Les quantiles. L'étiquette du niveau le plus proche de zéro se pose à
  // DROITE de son trait, celle du plus lointain à GAUCHE du sien : elles
  // s'écartent l'une de l'autre au lieu de traverser le trait voisin.
  niveaux.forEach((niveau, rang) => {
    const quantile = niveau.expected_shortfall.threshold
    const aDroite = rang === 0
    marques.push(
      Plot.ruleX([quantile], { stroke: couleurs.texte1, strokeWidth: 1.5 }),
      Plot.text([quantile], {
        x: (x: number) => x,
        frameAnchor: 'top',
        dy: 4,
        dx: aDroite ? 4 : -4,
        textAnchor: aDroite ? 'start' : 'end',
        lineAnchor: 'top',
        ...halo(couleurs, couleurs.texte1),
        text: () =>
          `VaR ${pourcentage(niveau.confidence, 0)}\n${pourcentage(niveau.historical_var.value, 2)}`,
      }),
    )
  })

  marques.push(
    Plot.tip(
      classes,
      Plot.pointerX({
        x1: 'lower',
        x2: 'upper',
        y: 'count',
        title: texteDeClasse,
        fill: couleurs.surface1,
        stroke: couleurs.bordureForte,
      }),
    ),
  )

  return {
    height: HAUTEUR_HISTOGRAMME,
    marginLeft: 40,
    marginRight: 12,
    marginBottom: 32,
    x: {
      domain: [debut, fin],
      ticks: graduationsDeRendement(debut, fin, largeur),
      tickFormat: (valeur: number) => pourcentage(valeur, 0),
      label: null,
    },
    y: {
      label: null,
      // Des séances : un compte entier, écrit par lib/format. Une graduation
      // fractionnaire (2,5 séances) n'a pas de sens et reste muette.
      tickFormat: (valeur: number) => (Number.isInteger(valeur) ? decimal(valeur, 0) : ''),
    },
    marks: marques,
  }
}
