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
 *
 * LE BOUTON DIT LA PAGE OÙ IL MÈNE (chantier 7D) : celle de l'adresse
 * d'arrivée, « Ouvrir la méthodologie » pour un lien partagé vers elle, et
 * son message dit le même geste. Le bouton de langue est en tête : un
 * visiteur arrivé dans la mauvaise langue peut changer avant de lire.
 *
 * LE CLAVIER (chantier 7E, §13). Le lien « Aller au contenu » est le premier
 * arrêt, comme sur toute autre page : il mène au titre du texte, après le
 * bouton de langue. Quand l'écran remplace une page après un changement de
 * langue, son titre reçoit le focus ; à l'arrivée, rien ne bouge. Accepter
 * est un geste décidé : la page qui s'ouvre ensuite part de son haut, son
 * titre focalisé.
 */
import { useEffect, useRef, useState } from 'react'

import type { Disclaimer } from '../api/types'
import { BoutonLangue } from '../components/BoutonLangue'
import cadre from '../components/Cadre.module.css'
import type { Destination } from '../contenu/libelles'
import { memoriserAcceptation } from '../lib/acceptation'
import { useLangue } from '../lib/langue'
import { marquerGesteDecide, useRoute, type Route } from '../lib/route'
import styles from './Acceptation.module.css'

/** L'identifiant du titre du texte : la cible du lien d'évitement. */
const TITRE = 'texte-acceptation'

/** La page où mène l'adresse d'arrivée ; `/` rouvre une analyse. */
export function destinationDe(route: Route): Destination {
  switch (route.vue) {
    case 'accueil':
    case 'analyse':
      return 'analyse'
    case 'positions':
      return 'positions'
    case 'portefeuilles':
      return 'portefeuilles'
    case 'methodologie':
      return 'methodologie'
    case 'inconnue':
      return 'page'
  }
}

interface Props {
  bandeau: Disclaimer
  onAccepte: () => void
  /** L'écran remplace une page après un geste : son titre prend le focus. */
  focaliser?: boolean
}

export function Acceptation({ bandeau, onAccepte, focaliser = false }: Props) {
  const { langue, libelles } = useLangue()
  const destination = destinationDe(useRoute())
  const [coche, setCoche] = useState(false)
  const titre = useRef<HTMLHeadingElement>(null)

  // L'onglet dit où l'on est, comme sur toute autre page. Le titre de cet
  // écran nomme déjà le produit : il n'est pas répété entre parenthèses.
  useEffect(() => {
    document.title = bandeau.title
  }, [bandeau.title])

  useEffect(() => {
    if (focaliser) titre.current?.focus()
  }, [focaliser])

  return (
    <>
      <a className={cadre.evitement} href={`#${TITRE}`}>
        {libelles.cadre.allerAuContenu}
      </a>
      <main className={styles.page} id="contenu">
        <div className={styles.langue}>
          <BoutonLangue />
        </div>
        <article className={styles.colonne}>
          <h1 ref={titre} id={TITRE} tabIndex={-1} className={styles.titre}>
            {bandeau.title}
          </h1>

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
                memoriserAcceptation(bandeau.text, langue)
                marquerGesteDecide()
                onAccepte()
              }}
            >
              {libelles.acceptation.ouvrir[destination]}
            </button>

            {/* Un bouton désactivé ne dit pas POURQUOI il l'est. La phrase est
                toujours là, elle ne surgit pas après coup comme un reproche. */}
            <p className={styles.condition}>{libelles.acceptation.condition[destination]}</p>
          </div>
        </article>
      </main>
    </>
  )
}
