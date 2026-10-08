/**
 * `<Graphique>` — l'enveloppe de tout graphique, DESIGN.md §9.4.
 *
 * ═══ AUCUN GRAPHIQUE SANS SES CONDITIONS ═══
 *
 * Modèle FRED : directement sous le titre, sans clic, l'unité, la fenêtre et
 * la date `as_of`. Ce ne sont pas des champs facultatifs d'une légende, ce
 * sont des PROPRIÉTÉS OBLIGATOIRES de ce composant : un graphique qui ne les
 * fournit pas ne compile pas. La discipline de `<Measure>` (§9.1), appliquée
 * au tracé.
 *
 * ═══ CE QUE L'ENVELOPPE FAIT, ET CE QU'ELLE LAISSE À CHAQUE GRAPHIQUE ═══
 *
 * Elle monte le SVG de Plot, le démonte au démontage, le redessine quand la
 * largeur change (ResizeObserver) et quand le THÈME change (`useCouleurs`) —
 * Plot écrit des valeurs de couleur, pas des variables, et un SVG dessiné en
 * sombre resterait sombre sur une page devenue claire. Chaque graphique ne
 * fournit que ses marques, construites par une fonction PURE de ses données,
 * des couleurs et de la largeur : c'est elle que les tests exercent.
 *
 * La police et sa taille sont imposées par la feuille de style, pas par Plot :
 * Plot écrit `font-size="10"` en attribut de présentation, qu'une règle CSS
 * surcharge. Aucune taille n'est donc écrite ici.
 */
import * as Plot from '@observablehq/plot'
import { useEffect, useRef, useState, type ReactNode } from 'react'

import type { Window } from '../../api/types'
import { useLangue, type Langue } from '../../lib/langue'
import { provenanceDeGraphique } from '../../lib/provenance'
import { Provenance } from '../Provenance'
import type { Couleurs } from './couleurs'
import { useCouleurs } from './useCouleurs'
import styles from './Graphique.module.css'

export interface ContexteGraphique {
  readonly couleurs: Couleurs
  readonly largeur: number
  /** La langue des annotations et des infobulles ; le français sans elle. */
  readonly langue?: Langue
}

/** Le tracé tel que Plot le rend : l'élément, et ses échelles (`scale`). */
export type Trace = ReturnType<typeof Plot.plot>

/** Des propriétés CSS, par nom : `{ '--haut-de-grille': '42px' }`. */
export type ProprietesCss = Readonly<Record<string, string>>

interface Props {
  readonly titre: string
  /** Ce que mesure l'axe des valeurs : « rendement quotidien, en % ». */
  readonly unite: string
  /** La fenêtre de la série tracée, telle que l'API la publie. */
  readonly fenetre: Window
  /** Date de valorisation de la réponse (`analysis.as_of`). */
  readonly asOf: string
  /**
   * Ce que le graphique MONTRE, en une phrase (§13) : la conclusion, pas la
   * forme. C'est l'`aria-label` du tracé.
   */
  readonly description: string
  readonly options: (contexte: ContexteGraphique) => Plot.PlotOptions
  /**
   * Ce que la mise en page autour du tracé doit savoir de lui, et qui n'est
   * connu qu'une fois Plot passé : des propriétés CSS, posées sur la figure à
   * chaque dessin et retirées avec lui. La carte de corrélation y donne le
   * haut de sa grille, sur lequel sa légende s'aligne.
   */
  readonly proprietesDuTrace?: (trace: Trace) => ProprietesCss
  /** Légende ou mention placée sous le tracé. */
  readonly children?: ReactNode
}

export function Graphique({
  titre,
  unite,
  fenetre,
  asOf,
  description,
  options,
  proprietesDuTrace,
  children,
}: Props) {
  const { langue } = useLangue()
  const conteneur = useRef<HTMLDivElement>(null)
  const couleurs = useCouleurs()
  const [largeur, setLargeur] = useState(0)

  useEffect(() => {
    const noeud = conteneur.current
    if (noeud === null) return
    const observateur = new ResizeObserver(([entree]) => {
      if (entree) setLargeur(Math.floor(entree.contentRect.width))
    })
    observateur.observe(noeud)
    return () => observateur.disconnect()
  }, [])

  useEffect(() => {
    const noeud = conteneur.current
    if (noeud === null || largeur === 0 || couleurs === null) return
    // La largeur de la colonne par défaut ; un graphique peut en demander
    // MOINS (une carte de chaleur garde ses cellules carrées), jamais plus.
    const demande = options({ couleurs, largeur, langue })
    const trace = Plot.plot({
      ...demande,
      width: Math.min(demande.width ?? largeur, largeur),
      style: { color: couleurs.texte2, background: 'transparent', overflow: 'visible' },
    })
    noeud.replaceChildren(trace)
    const figure = noeud.parentElement
    const proprietes = Object.entries(proprietesDuTrace?.(trace) ?? {})
    for (const [nom, valeur] of proprietes) figure?.style.setProperty(nom, valeur)
    return () => {
      trace.remove()
      for (const [nom] of proprietes) figure?.style.removeProperty(nom)
    }
  }, [options, couleurs, largeur, langue, proprietesDuTrace])

  return (
    <figure className={styles.graphique}>
      <figcaption className={styles.entete}>
        <span className={styles.titre}>{titre}</span>
        <Provenance
          lignes={provenanceDeGraphique(unite, fenetre, asOf, langue)}
          disposition="ligne"
        />
      </figcaption>
      <div
        ref={conteneur}
        className={styles.trace}
        role="img"
        aria-label={description}
      />
      {children}
    </figure>
  )
}
