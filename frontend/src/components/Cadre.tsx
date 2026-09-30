/**
 * La mise en page commune à toutes les pages — DESIGN.md §7, §8, §13.
 *
 * Le lien « aller au contenu », le bandeau, le rail à gauche de la colonne de
 * lecture, et le contenu. Chaque page fournit son bandeau et son rail ; le
 * cadre ne sait rien de ce qu'elles montrent.
 *
 * ═══ UNE SEULE RÉGION D'ANNONCE ═══
 *
 * Ce qu'une action vient de faire — « Portefeuille « Démo » supprimé. » — est
 * écrit dans UNE région `role="status"`, en tête du contenu, présente dans le
 * document même vide : une région qui apparaîtrait avec son texte ne serait
 * pas annoncée par tous les lecteurs d'écran. Le chargement, lui, n'est pas
 * annoncé : un « Chargement… » lu à chaque page est du bruit.
 *
 * ═══ LE FOCUS À CHAQUE CHANGEMENT DE PAGE ═══
 *
 * Sans rechargement, le navigateur laisse le focus sur le lien cliqué, qui
 * n'existe plus, ou au début du document. Le titre de la nouvelle page
 * (`<h1 tabIndex={-1}>`) le reçoit, ou à défaut le contenu : la tabulation
 * suivante part de la nouvelle page, et un lecteur d'écran lit son titre. Pas
 * au premier affichage, où rien n'a encore été quitté. L'anneau de focus
 * reste visible (§13) : il montre où l'on est arrivé.
 */
import { useEffect, useRef, type ReactNode } from 'react'

import { aDejaNavigue } from '../lib/route'
import styles from './Cadre.module.css'

interface Props {
  /** Le titre de l'onglet, sans le nom de l'application. */
  readonly titre: string
  readonly entete: ReactNode
  readonly rail?: ReactNode
  readonly annonce?: string | null
  /** Le contenu arrive : `aria-busy`, et rien n'est annoncé. */
  readonly occupe?: boolean
  /** Change à chaque page : le focus revient au contenu quand elle change. */
  readonly page: string
  readonly children: ReactNode
}

const APPLICATION = 'Mx Risk MGT'

export function Cadre({ titre, entete, rail, annonce, occupe, page, children }: Props) {
  const contenu = useRef<HTMLElement>(null)

  useEffect(() => {
    document.title = `${titre} — ${APPLICATION}`
  }, [titre])

  useEffect(() => {
    // Le chargement de l'application change de page lui aussi (démarrage,
    // redirection de `/`) : seul un changement DÉCIDÉ par l'utilisateur
    // déplace le focus.
    if (!aDejaNavigue()) return
    const titrePage = contenu.current?.querySelector<HTMLElement>('h1[tabindex="-1"]')
    ;(titrePage ?? contenu.current)?.focus()
    window.scrollTo({ top: 0 })
  }, [page])

  return (
    <>
      <a className={styles.evitement} href="#contenu">
        Aller au contenu
      </a>

      {entete}

      <div className={styles.page}>
        {rail}

        <main
          ref={contenu}
          id="contenu"
          tabIndex={-1}
          className={styles.contenu}
          aria-busy={occupe ? true : undefined}
        >
          <p className={styles.annonce} role="status">
            {annonce ?? ''}
          </p>
          {children}
        </main>
      </div>
    </>
  )
}
