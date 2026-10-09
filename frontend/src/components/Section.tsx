/**
 * Une section numérotée de la page d'analyse — DESIGN.md §8.2.
 *
 * Les six sections SONT une séquence de raisonnement : c'est l'unique
 * numérotation que §12 autorise. Le numéro reste discret, le titre calme
 * (§3.3) ; l'ancre sert la navigation latérale et la liste d'ancres en tête
 * de page sur un écran étroit.
 *
 * Les classes communes aux sections (sous-titre, chapeau, rangée de blocs)
 * sont exportées par `Section.module.css`, pour qu'aucune section ne
 * redéfinisse à sa façon ce qu'est un chapeau.
 *
 * Le titre reçoit le focus quand un lien du rail ou de la liste d'ancres
 * mène à la section (`tabIndex={-1}`, `components/Cadre`, chantier 7E) : il
 * n'est pas un arrêt de tabulation, mais la tabulation suivante part de lui.
 */
import type { ReactNode } from 'react'

import styles from './Section.module.css'

interface Props {
  readonly ancre: string
  readonly numero: number
  readonly titre: string
  /** La question à laquelle la section répond, en deux lignes. */
  readonly introduction: ReactNode
  readonly children: ReactNode
}

export function Section({ ancre, numero, titre, introduction, children }: Props) {
  return (
    <section className={styles.section} id={ancre} aria-labelledby={`${ancre}-titre`}>
      <h2 id={`${ancre}-titre`} tabIndex={-1} className={styles.titre}>
        <span className={styles.numero}>{numero}.</span> {titre}
      </h2>
      <p className={styles.introduction}>{introduction}</p>
      {children}
    </section>
  )
}
