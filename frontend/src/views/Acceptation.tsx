/**
 * Écran d'acceptation — DESIGN.md §15.
 *
 * UNE PAGE ENTIÈRE, PAS UNE MODALE, et la différence est le point : une modale
 * se clique sans lire, une page qu'on traverse une fois, délibérément, non. Il
 * n'y a donc ni fond assombri, ni croix de fermeture, ni « plus tard » — on ne
 * peut pas passer à côté de cet écran sans le traverser.
 *
 * LE TEXTE VIENT DU BACKEND, en entier. Rien n'est écrit ici : ni le titre, ni
 * les sections, ni la phrase de confirmation. Ce texte a une portée
 * quasi juridique, et une copie dans le bundle serait le texte réellement lu
 * le jour où le serveur change le sien.
 */
import { useEffect, useState } from 'react'

import type { Disclaimer } from '../api/types'
import { memoriserAcceptation } from '../lib/acceptation'
import styles from './Acceptation.module.css'

interface Props {
  bandeau: Disclaimer
  onAccepte: () => void
}

export function Acceptation({ bandeau, onAccepte }: Props) {
  const [coche, setCoche] = useState(false)

  // L'onglet dit où l'on est, comme sur toute autre page.
  useEffect(() => {
    document.title = `${bandeau.title} (Mx Risk MGT)`
  }, [bandeau.title])

  return (
    <main className={styles.page} id="contenu">
      <article className={styles.colonne}>
        <h1 className={styles.titre}>{bandeau.title}</h1>

        {bandeau.sections.map((section) => (
          <section key={section.title} className={styles.section}>
            <h2 className={styles.sousTitre}>{section.title}</h2>
            <p className={styles.corps}>{section.body}</p>
          </section>
        ))}

        <div className={styles.confirmation}>
          {/*
            La phrase de confirmation EST l'étiquette de la case. La lier par
            `<label>` plutôt que de la poser à côté agrandit la cible au texte
            entier et donne son nom accessible à la case.
          */}
          <label className={styles.case}>
            <input
              type="checkbox"
              checked={coche}
              onChange={(evenement) => setCoche(evenement.target.checked)}
            />
            <span>{bandeau.confirmation}</span>
          </label>

          <button
            type="button"
            className={styles.bouton}
            disabled={!coche}
            onClick={() => {
              // L'empreinte est prise sur le texte À PLAT tel qu'il a été servi,
              // celui-là même que l'utilisateur vient de lire. Si le serveur le
              // change, l'écran reviendra.
              memoriserAcceptation(bandeau.text)
              onAccepte()
            }}
          >
            Ouvrir l'analyse
          </button>

          {/* Un bouton désactivé ne dit pas POURQUOI il l'est. La phrase est
              toujours là, elle ne surgit pas après coup comme un reproche. */}
          <p className={styles.condition}>
            La case doit être cochée pour ouvrir l'analyse.
          </p>
        </div>
      </article>
    </main>
  )
}
