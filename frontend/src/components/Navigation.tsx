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
 * « bientôt ». La méthodologie viendra avec son écran.
 *
 * ═══ LES PAGES, SOUS UN SÉPARATEUR ═══
 *
 * Sous les sections, comme « Importer » dans la maquette de §8.2 : les autres
 * pages de l'application. Une liste distincte, dans son propre `<nav>`, parce
 * que ce ne sont pas des sections de l'analyse. La page courante porte
 * `aria-current="page"`, et le filet en `--accent` le montre (§5.3).
 */
import { useEffect, useState } from 'react'

import { cheminDe } from '../lib/route'
import { Lien } from './Lien'
import styles from './Navigation.module.css'

/** Une page de l'application, telle que la navigation la propose. */
export interface PageApplication {
  readonly vers: string
  readonly libelle: string
  readonly courante: boolean
}

/**
 * Les pages que la navigation propose, depuis `courante`. L'analyse n'est
 * proposée que lorsqu'un portefeuille est en vue : sans lui, elle n'a rien à
 * montrer.
 */
export function pagesApplication(
  courante: 'analyse' | 'portefeuilles',
  id: number | null,
): PageApplication[] {
  const pages: PageApplication[] = []
  if (id !== null) {
    pages.push({
      vers: cheminDe({ vue: 'analyse', id }),
      libelle: 'Analyse',
      courante: courante === 'analyse',
    })
  }
  pages.push({
    vers: cheminDe({ vue: 'portefeuilles' }),
    libelle: 'Portefeuilles',
    courante: courante === 'portefeuilles',
  })
  return pages
}

function ListePages({
  pages,
  classe,
}: {
  pages: readonly PageApplication[]
  classe: string | undefined
}) {
  return (
    <nav className={classe} aria-label="Pages">
      <ul>
        {pages.map((page) => (
          <li key={page.vers}>
            <Lien
              vers={page.vers}
              className={page.courante ? styles.actif : undefined}
              aria-current={page.courante ? 'page' : undefined}
            >
              {page.libelle}
            </Lien>
          </li>
        ))}
      </ul>
    </nav>
  )
}

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

/** Le rail de l'analyse, au-dessus de 900 px : les sections, puis les pages. */
export function RailSections({ pages }: { pages: readonly PageApplication[] }) {
  const enCours = useSectionEnCours()
  return (
    <div className={styles.rail}>
      <nav aria-label="Sections de l'analyse">
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
      <ListePages pages={pages} classe={styles.pages} />
    </div>
  )
}

/** Le rail des autres pages, au-dessus de 900 px : les pages seules. */
export function RailPages({ pages }: { pages: readonly PageApplication[] }) {
  return (
    <div className={styles.rail}>
      <ListePages pages={pages} classe={styles.pagesSeules} />
    </div>
  )
}

/** Sous 900 px, en tête de page : les ancres des sections, s'il y en a, puis les pages. */
export function AncresSections({
  pages,
  sections = true,
}: {
  pages: readonly PageApplication[]
  sections?: boolean
}) {
  return (
    <div className={styles.ancres}>
      {sections && (
        <nav aria-label="Sections de l'analyse">
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
      )}
      <ListePages pages={pages} classe={styles.pagesEtroites} />
    </div>
  )
}
