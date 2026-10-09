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
 *
 * ═══ SES VALEURS, EN TABLEAU, REPLIÉES (chantier 7E, §9.4, §13) ═══
 *
 * Le tracé est une image (`role="img"`) que nomme sa conclusion. Ses valeurs,
 * elles, ne se lisent qu'au survol, à la souris. Sous le tracé, un
 * `<details>` natif, fermé, les donne en tableau : les mêmes valeurs que le
 * dessin, lues dans la réponse de l'API et écrites par `lib/format`, toutes et
 * dans l'ordre publié. Son libellé visible est le même sous chaque graphique ;
 * le titre du graphique le suit en texte masqué, pour qu'un lecteur d'écran
 * sache lequel il ouvre, le nom commençant par le texte visible (WCAG 2.5.3).
 * Un graphique dont le tableau suit déjà la figure n'en reçoit pas de second :
 * il le désigne (`decritPar`).
 */
import * as Plot from '@observablehq/plot'
import { useEffect, useRef, useState, type ReactNode } from 'react'

import type { Window } from '../../api/types'
import type { Methode } from '../../contenu/methodes'
import { useLangue, type Langue } from '../../lib/langue'
import { provenanceDeGraphique } from '../../lib/provenance'
import { DataTable, type Colonne } from '../DataTable'
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

/**
 * Les valeurs d'un graphique, en tableau : sa légende, ses colonnes, ses
 * rangées, faites des données publiées sans rien calculer ni choisir.
 */
export interface ValeursDuGraphique<T> {
  readonly legende: string
  readonly colonnes: readonly Colonne<T>[]
  readonly lignes: readonly T[]
  readonly cleDeLigne: (ligne: T) => string
  /** Ce que le dessin porte en plus de ses valeurs (traits, zone ombrée), déjà écrit. */
  readonly note?: string | null
}

interface Props<T> {
  readonly titre: string
  /** Ce que mesure l'axe des valeurs : « rendement quotidien, en % ». */
  readonly unite: string
  /** La fenêtre de la série tracée, telle que l'API la publie. */
  readonly fenetre: Window
  /** Date de valorisation de la réponse (`analysis.as_of`). */
  readonly asOf: string
  /**
   * Le lien vers sa méthode, la dernière paire des conditions (chantier 7E,
   * §9.4). Obligatoire comme l'unité, la fenêtre et la date.
   */
  readonly methode: Methode
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
  /** Les valeurs du dessin, en tableau replié sous lui. */
  readonly valeurs?: ValeursDuGraphique<T>
  /**
   * L'identifiant de ce qui décrit le tracé, quand ses valeurs sont déjà dans
   * le tableau qui suit la figure : la légende de ce tableau.
   */
  readonly decritPar?: string
}

export function Graphique<T>({
  titre,
  unite,
  fenetre,
  asOf,
  methode,
  description,
  options,
  proprietesDuTrace,
  children,
  valeurs,
  decritPar,
}: Props<T>) {
  const { langue, libelles } = useLangue()
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
          methode={methode}
        />
      </figcaption>
      <div
        ref={conteneur}
        className={styles.trace}
        role="img"
        aria-label={description}
        aria-describedby={decritPar}
      />
      {children}
      {valeurs !== undefined && (
        <details className={styles.valeurs}>
          <summary className={styles.ouvrir}>
            {libelles.graphiques.valeursEnTableau}
            <span className="visuellement-cache"> ({titre})</span>
          </summary>
          <DataTable
            legende={valeurs.legende}
            largeur="contenu"
            colonnes={valeurs.colonnes}
            lignes={valeurs.lignes}
            cleDeLigne={valeurs.cleDeLigne}
          />
          {valeurs.note != null && <p className={styles.note}>{valeurs.note}</p>}
        </details>
      )}
    </figure>
  )
}
