/**
 * Navigation entre les sections d'une page — DESIGN.md §7, §8.2.
 *
 * DEUX FORMES, UNE SEULE LISTE. Au-dessus de 900 px, un rail de 220 px à
 * gauche de la colonne de lecture, qui suit le défilement et signale la
 * section en cours en `--accent` (§5.3 : l'état actif, et rien d'autre). En
 * dessous, le rail s'escamote — il coûterait plus de place qu'il n'en fait
 * gagner — et une liste d'ancres prend sa place EN TÊTE de page : sur un
 * téléphone, on choisit où aller avant de défiler, pas pendant.
 *
 * Deux pages ont des sections : l'analyse, numérotées de 1 à 6 (`SECTIONS`),
 * et la méthodologie, dont les parties viennent de son texte, sans numéro
 * (§12 réserve la numérotation aux six sections de l'analyse). Seules les
 * sections qui existent sont listées : pas d'entrée grisée, pas de « bientôt ».
 *
 * ═══ LES PAGES, SOUS UN SÉPARATEUR ═══
 *
 * Sous les sections, comme « Importer » dans la maquette de §8.2 : les autres
 * pages de l'application. Une liste distincte, dans son propre `<nav>`, parce
 * que ce ne sont pas des sections de la page. La page courante porte
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
 * montrer. La méthodologie l'est toujours, en dernier : elle ne dépend
 * d'aucun portefeuille.
 */
export function pagesApplication(
  courante: 'analyse' | 'positions' | 'portefeuilles' | 'methodologie',
  id: number | null,
): PageApplication[] {
  const pages: PageApplication[] = []
  if (id !== null) {
    pages.push(
      {
        vers: cheminDe({ vue: 'analyse', id }),
        libelle: 'Analyse',
        courante: courante === 'analyse',
      },
      {
        vers: cheminDe({ vue: 'positions', id }),
        libelle: 'Positions et import',
        courante: courante === 'positions',
      },
    )
  }
  pages.push(
    {
      vers: cheminDe({ vue: 'portefeuilles' }),
      libelle: 'Portefeuilles',
      courante: courante === 'portefeuilles',
    },
    {
      vers: cheminDe({ vue: 'methodologie' }),
      libelle: 'Méthodologie',
      courante: courante === 'methodologie',
    },
  )
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

/** Une section d'une page, telle que le rail et la liste d'ancres la proposent. */
export interface SectionDeNavigation {
  readonly ancre: string
  readonly libelle: string
  /** Le numéro affiché devant le libellé : les seules sections de l'analyse. */
  readonly numero?: number
}

export const SECTIONS = [
  { ancre: 'portefeuille', numero: 1, libelle: 'Le portefeuille' },
  { ancre: 'jour-ordinaire', numero: 2, libelle: 'Un jour ordinaire' },
  { ancre: 'au-pire', numero: 3, libelle: 'Au pire' },
  { ancre: 'qui-porte', numero: 4, libelle: 'Qui porte le risque' },
  { ancre: 'en-crise', numero: 5, libelle: 'En crise' },
  { ancre: 'moteur', numero: 6, libelle: 'Ce que le moteur en dit' },
] as const

const SECTIONS_DE_L_ANALYSE = "Sections de l'analyse"

/**
 * La section en cours de lecture : la dernière dont le haut est passé sous
 * le premier tiers de l'écran. Présentation seulement — rien ne change dans
 * la page selon elle, sinon l'indicateur du rail.
 *
 * Ce qui est observé est la `<section>` qui contient l'ancre : la section
 * elle-même sur l'analyse, celle qu'ouvre le titre de la partie sur la
 * méthodologie, où l'ancre est portée par le titre.
 */
function useSectionEnCours(sections: readonly SectionDeNavigation[]): string | null {
  const [enCours, setEnCours] = useState<string | null>(null)
  const ancres = sections.map((section) => section.ancre).join(' ')

  useEffect(() => {
    const liste = ancres.split(' ')
    const visibles = new Set<string>()
    const observateur = new IntersectionObserver(
      (entrees) => {
        for (const entree of entrees) {
          const ancre = (entree.target as HTMLElement).dataset['ancre'] ?? ''
          if (entree.isIntersecting) visibles.add(ancre)
          else visibles.delete(ancre)
        }
        const premiere = liste.find((ancre) => visibles.has(ancre))
        if (premiere !== undefined) setEnCours(premiere)
      },
      { rootMargin: '-25% 0px -65% 0px' },
    )
    for (const ancre of liste) {
      const noeud = document.getElementById(ancre)?.closest('section')
      if (noeud === null || noeud === undefined) continue
      noeud.dataset['ancre'] = ancre
      observateur.observe(noeud)
    }
    return () => observateur.disconnect()
  }, [ancres])

  return enCours
}

function Numero({ section }: { section: SectionDeNavigation }) {
  if (section.numero === undefined) return null
  return (
    <>
      <span className={styles.numero}>{section.numero}.</span>{' '}
    </>
  )
}

/**
 * Le rail d'une page à sections, au-dessus de 900 px : les sections, puis les
 * pages. Sans `sections`, celles de l'analyse.
 */
export function RailSections({
  pages,
  sections = SECTIONS,
  etiquette = SECTIONS_DE_L_ANALYSE,
}: {
  pages: readonly PageApplication[]
  sections?: readonly SectionDeNavigation[]
  etiquette?: string
}) {
  const enCours = useSectionEnCours(sections)
  return (
    <div className={styles.rail}>
      <nav aria-label={etiquette}>
        <ol>
          {sections.map((section) => (
            <li key={section.ancre}>
              <a
                href={`#${section.ancre}`}
                className={section.ancre === enCours ? styles.actif : undefined}
                aria-current={section.ancre === enCours ? 'location' : undefined}
              >
                <Numero section={section} />
                {section.libelle}
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

/**
 * Sous 900 px, en tête de page : les ancres des sections, s'il y en a, puis
 * les pages. Sans `liste`, les sections de l'analyse.
 */
export function AncresSections({
  pages,
  sections = true,
  liste = SECTIONS,
  etiquette = SECTIONS_DE_L_ANALYSE,
}: {
  pages: readonly PageApplication[]
  sections?: boolean
  liste?: readonly SectionDeNavigation[]
  etiquette?: string
}) {
  return (
    <div className={styles.ancres}>
      {sections && (
        <nav aria-label={etiquette}>
          <ol>
            {liste.map((section) => (
              <li key={section.ancre}>
                <a href={`#${section.ancre}`}>
                  <Numero section={section} />
                  {section.libelle}
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
