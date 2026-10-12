/**
 * La page de l'avertissement — DESIGN.md §19.6 (chantier 9.4).
 *
 * La démonstration ne pose pas l'écran d'acceptation : il a été décidé pour
 * quelqu'un qui analyse son propre portefeuille, et elle n'en montre aucun.
 * Son texte reste lisible ici, à un clic au plus de chaque page : le lien qui
 * termine la mention (`components/Cadre`) et la dernière entrée de la liste
 * des pages y mènent.
 *
 * LE TEXTE VIENT DU FICHIER EXPORTÉ, en entier : le titre et les sections de
 * `<langue>/disclaimer.json`, sans copie dans le client, comme sur l'écran
 * d'acceptation. La phrase de confirmation n'est pas affichée : il n'y a ni
 * case ni bouton, et une phrase à la première personne sans rien à cocher ne
 * dit rien. Sous le titre, une phrase du client dit pourquoi la page n'a rien
 * à accepter.
 *
 * LE TITRE EXISTE TOUT DE SUITE, pour recevoir le focus après une navigation
 * (§13). Il dit le nom de la page tant que le fichier n'est pas là, ou s'il
 * manque, puis le titre du fichier, dans le même élément. L'onglet suit ; le
 * titre du fichier nomme déjà le produit, et s'y lit seul (§6.3).
 *
 * Un changement de langue relit le texte en place : celui d'avant reste
 * affiché, occupé (`aria-busy`), jusqu'au nouveau.
 *
 * Cette page n'existe que dans la démonstration. Dans l'application, son
 * adresse rend « Page introuvable » (`App.tsx`), et l'acceptation reste une
 * page à traverser.
 */
import { useEffect, useState } from 'react'

import { ApiErreur, getDisclaimer, versApiErreur } from '../api/client'
import type { Disclaimer, PortfolioDetail } from '../api/types'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { MessageErreur } from '../components/MessageErreur'
import { AncresSections, pagesApplication, RailPages } from '../components/Navigation'
import { SqueletteTexte } from '../components/Squelette'
import { useLangue } from '../lib/langue'
import { cheminDe } from '../lib/route'
import controles from '../styles/controles.module.css'
import styles from './Avertissement.module.css'
import communs from './Pages.module.css'

type Etat =
  | { phase: 'chargement'; precedent: Disclaimer | null }
  | { phase: 'erreur'; erreur: ApiErreur }
  | { phase: 'lu'; texte: Disclaimer }

const PAGE = cheminDe({ vue: 'avertissement' })

/** Le texte à montrer : le nouveau, ou, pendant qu'il se relit, le précédent. */
function texteDe(etat: Etat): Disclaimer | null {
  return etat.phase === 'lu' ? etat.texte : etat.phase === 'chargement' ? etat.precedent : null
}

interface Props {
  /** Le dernier portefeuille consulté, s'il existe encore : le bandeau le nomme. */
  readonly portefeuille: PortfolioDetail | null
}

export function VueAvertissement({ portefeuille }: Props) {
  const { langue, libelles } = useLangue()
  const [etat, setEtat] = useState<Etat>({ phase: 'chargement', precedent: null })

  useEffect(() => {
    let vivant = true
    setEtat((avant) => ({ phase: 'chargement', precedent: texteDe(avant) }))
    getDisclaimer(langue).then(
      (texte) => {
        if (vivant) setEtat({ phase: 'lu', texte })
      },
      (cause: unknown) => {
        if (vivant) setEtat({ phase: 'erreur', erreur: versApiErreur(cause, langue) })
      },
    )
    return () => {
      vivant = false
    }
  }, [langue])

  const texte = texteDe(etat)
  const titre = texte?.title ?? libelles.navigation.pages.avertissement
  const pages = pagesApplication('avertissement', portefeuille?.id ?? null, langue)

  return (
    <Cadre
      titre={titre}
      titreSeul={texte !== null}
      page={PAGE}
      occupe={etat.phase === 'chargement'}
      entete={<BandeauSimple portefeuille={portefeuille?.name ?? null} />}
      rail={<RailPages pages={pages} />}
    >
      <AncresSections pages={pages} sections={false} />
      <h1 tabIndex={-1} className={communs.titre}>
        {titre}
      </h1>
      {etat.phase === 'erreur' ? (
        <MessageErreur
          erreur={etat.erreur}
          action={
            <button
              type="button"
              className={controles.bouton}
              onClick={() => window.location.reload()}
            >
              {libelles.application.rechargerLaPage}
            </button>
          }
        />
      ) : (
        <>
          <p className={communs.texte}>{libelles.avertissement.pourquoi}</p>
          <div className={styles.texteDuFichier}>
            {texte === null ? (
              <SqueletteTexte />
            ) : (
              texte.sections.map((section) => (
                <section key={section.title} className={styles.section}>
                  <h2 className={styles.sousTitre}>{section.title}</h2>
                  <p className={communs.texte}>{section.body}</p>
                </section>
              ))
            )}
          </div>
        </>
      )}
    </Cadre>
  )
}
