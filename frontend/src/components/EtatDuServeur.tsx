/**
 * Où en est le serveur de calcul du site (chantier 9.6) : il se réveille, ou
 * il calcule. Pendant un envoi, sur la page des positions, et pendant que
 * l'analyse du portefeuille saisi se demande, sur sa page.
 *
 * ═══ AUCUN SAUT DE MISE EN PAGE ═══
 *
 * Les deux phrases sont posées l'une sur l'autre, dans la même case : la case
 * a la hauteur de la plus longue dès qu'elle paraît, et passer de l'une à
 * l'autre ne déplace rien. Tant que rien n'est encore observé, aucune n'est
 * dite, et la place est déjà prise. La phrase qui n'est pas dite est
 * invisible, donc absente pour un lecteur d'écran.
 *
 * Aucune durée n'est écrite : le client ne sait pas distinguer un serveur qui
 * démarre d'un serveur en panne avant la fin de l'attente, et une analyse
 * prend le temps qu'elle prend.
 *
 * Une région `role="status"` : un lecteur d'écran entend la phrase quand elle
 * change, sans que le focus bouge (DESIGN.md §13).
 */
import { useLangue } from '../lib/langue'
import styles from './EtatDuServeur.module.css'

/** Ce qui est observé : le serveur ne répond pas encore, ou il calcule. */
export type EtapeDuServeur = 'reveil' | 'calcul'

const ETAPES: readonly EtapeDuServeur[] = ['reveil', 'calcul']

export function EtatDuServeur({ etape }: { etape: EtapeDuServeur | null }) {
  const { libelles } = useLangue()
  return (
    <div className={styles.etat} role="status">
      {ETAPES.map((candidate) => (
        <p
          key={candidate}
          className={candidate === etape ? styles.phrase : `${styles.phrase} ${styles.tue}`}
          aria-hidden={candidate === etape ? undefined : true}
        >
          {libelles.serveur[candidate]}
        </p>
      ))}
    </div>
  )
}
