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
import { provenanceDeGraphique } from '../../lib/provenance'
import { Provenance } from '../Provenance'
import type { Couleurs } from './couleurs'
import { useCouleurs } from './useCouleurs'
import styles from './Graphique.module.css'

export interface ContexteGraphique {
  readonly couleurs: Couleurs
  readonly largeur: number
}

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
  children,
}: Props) {
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
    const demande = options({ couleurs, largeur })
    const trace = Plot.plot({
      ...demande,
      width: Math.min(demande.width ?? largeur, largeur),
      style: { color: couleurs.texte2, background: 'transparent', overflow: 'visible' },
    })
    noeud.replaceChildren(trace)
    return () => trace.remove()
  }, [options, couleurs, largeur])

  return (
    <figure className={styles.graphique}>
      <figcaption className={styles.entete}>
        <span className={styles.titre}>{titre}</span>
        <Provenance
          lignes={provenanceDeGraphique(unite, fenetre, asOf)}
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
