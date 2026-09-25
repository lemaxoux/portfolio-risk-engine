/**
 * Navigation entre les sections de la page d'analyse — DESIGN.md §7, §8.2.
 *
 * DEUX FORMES, UNE SEULE LISTE. Au-dessus de 900 px, un rail de 220 px à
 * gauche de la colonne de lecture, qui suit le défilement et signale la
 * section en cours en `--accent` (§5.3 : l'état actif, et rien d'autre). En
 * dessous, le rail s'escamote — il coûterait plus de place qu'il n'en fait
 * gagner — et une liste d'ancres prend sa place EN TÊTE de page : sur un
 * téléphone, on choisit où aller avant de défiler, pas pendant.
 *
 * Seules les sections qui existent sont listées : pas d'entrée grisée, pas de
 * « bientôt ». La saisie, l'import et la méthodologie viendront avec leurs
 * écrans.
 */
import { useEffect, useState } from 'react'

import styles from './Navigation.module.css'

export const SECTIONS = [
  { ancre: 'portefeuille', numero: 1, libelle: 'Le portefeuille' },
  { ancre: 'jour-ordinaire', numero: 2, libelle: 'Un jour ordinaire' },
  { ancre: 'au-pire', numero: 3, libelle: 'Au pire' },
  { ancre: 'qui-porte', numero: 4, libelle: 'Qui porte le risque' },
  { ancre: 'en-crise', numero: 5, libelle: 'En crise' },
  { ancre: 'moteur', numero: 6, libelle: 'Ce que le moteur en dit' },
] as const

type Ancre = (typeof SECTIONS)[number]['ancre']

/**
 * La section en cours de lecture : la dernière dont le haut est passé sous
 * le premier tiers de l'écran. Présentation seulement — rien ne change dans
 * la page selon elle, sinon l'indicateur du rail.
 */
function useSectionEnCours(): Ancre | null {
  const [enCours, setEnCours] = useState<Ancre | null>(null)

  useEffect(() => {
    const visibles = new Set<string>()
    const observateur = new IntersectionObserver(
      (entrees) => {
        for (const entree of entrees) {
          if (entree.isIntersecting) visibles.add(entree.target.id)
          else visibles.delete(entree.target.id)
        }
        const premiere = SECTIONS.find((section) => visibles.has(section.ancre))
        if (premiere !== undefined) setEnCours(premiere.ancre)
      },
      { rootMargin: '-25% 0px -65% 0px' },
    )
    for (const section of SECTIONS) {
      const noeud = document.getElementById(section.ancre)
      if (noeud !== null) observateur.observe(noeud)
    }
    return () => observateur.disconnect()
  }, [])

  return enCours
}

/** Le rail, au-dessus de 900 px. */
export function RailSections() {
  const enCours = useSectionEnCours()
  return (
    <nav className={styles.rail} aria-label="Sections de l'analyse">
      <ol>
        {SECTIONS.map((section) => (
          <li key={section.ancre}>
            <a
              href={`#${section.ancre}`}
              className={section.ancre === enCours ? styles.actif : undefined}
              aria-current={section.ancre === enCours ? 'location' : undefined}
            >
              <span className={styles.numero}>{section.numero}.</span> {section.libelle}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}

/** La liste d'ancres en tête de page, sous 900 px. */
export function AncresSections() {
  return (
    <nav className={styles.ancres} aria-label="Sections de l'analyse">
      <ol>
        {SECTIONS.map((section) => (
          <li key={section.ancre}>
            <a href={`#${section.ancre}`}>
              <span className={styles.numero}>{section.numero}.</span> {section.libelle}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}
