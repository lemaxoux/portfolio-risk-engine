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
 *
 * ═══ UNE ADRESSE QUI VISE UN TITRE ═══
 *
 * `/methodologie#cvar` mène à un titre de la page, pas à son haut. Quand le
 * fragment de l'adresse désigne un titre du contenu qui porte `tabIndex={-1}`,
 * la page défile jusqu'à lui et c'est lui qui reçoit le focus ; au premier
 * affichage, elle défile seulement. Un fragment changé sur la même page, par
 * un lien du rail ou par un retour arrière d'une ancre à l'autre, y porte le
 * focus. Une section de l'analyse porte son ancre sur la `<section>` : c'est
 * son titre qui reçoit le focus (chantier 7E, `lib/focus.ts`), et l'anneau
 * entoure son texte. Avant, le focus restait sur le corps de la page, sans
 * anneau, et le Tab suivant repartait du haut quand la section n'avait rien
 * de focalisable.
 *
 * ═══ LE RETOUR DEPUIS LA MÉTHODE (chantier 7E) ═══
 *
 * Un lien vers la méthode note sa clé dans l'entrée d'historique qu'il quitte
 * (`naviguer`, `lib/route.ts`). Au retour arrière, une fois la page prête (ni
 * occupée, ni en chargement), le lien suivi reprend le focus, amené sous le
 * bandeau comme une ancre, et gardé en vue pendant que la page s'installe.
 * La clé, et non la position : une langue ou un thème changés sur la
 * méthodologie déplacent tout. La position notée ne sert que si la clé est
 * introuvable. Avant, la page revenait en haut, le focus sur son titre.
 *
 * ═══ LA MENTION DE LA DÉMONSTRATION (chantier 9.2) ═══
 *
 * Dans le build de démonstration, chaque page dit d'abord ce qu'est le site :
 * des portefeuilles fixes, valorisés à une date. En tête du contenu, sous le
 * bandeau, en texte courant qui défile avec la page ; le visiteur arrive le
 * plus souvent sur une analyse, pas sur la liste. Le build ordinaire ne la
 * contient pas. Elle se termine par un lien vers l'avertissement (chantier
 * 9.4, DESIGN.md §19.6) : la démonstration ne pose pas l'écran
 * d'acceptation, et son texte reste ainsi à un clic de chaque page, pages
 * introuvables comprises. Le lien est un libellé à part, la phrase ne change
 * pas.
 *
 * ═══ LA PAGE D'ATTENTE NE PREND RIEN (chantier 9.4) ═══
 *
 * L'analyse se charge à la demande (`views/AnalyseALaDemande`). Tant que son
 * fichier n'est pas arrivé, une page d'attente tient sa place : même titre,
 * même cadre, le squelette, `aria-busy`. Avec `attente`, ce cadre ne déplace
 * ni le focus ni le défilement, et ne lit pas la note d'un retour : la page
 * attendue le fait en s'installant, une seule fois par navigation
 * (DESIGN.md §19.9).
 */
import { useEffect, useRef, type ReactNode } from 'react'

import { DEMO } from '../api/client'
import { DATE_DE_LA_DEMO, PORTEFEUILLES_DE_LA_DEMO } from '../contenu/demo'
import { idDuTitreVise, resoudreRetour, type NoteDeRetour } from '../lib/focus'
import { useLangue } from '../lib/langue'
import {
  aDejaNavigue,
  cheminDe,
  navigationParHistorique,
  noteDeRetourCourante,
} from '../lib/route'
import { Lien } from './Lien'
import { SECTIONS } from './Navigation'
import styles from './Cadre.module.css'

interface Props {
  /** Le titre de l'onglet, sans le nom de l'application. */
  readonly titre: string
  /**
   * Le titre nomme déjà le produit : l'onglet le porte seul, sans le répéter
   * entre parenthèses (§6.3), comme sur l'écran d'acceptation.
   */
  readonly titreSeul?: boolean
  readonly entete: ReactNode
  readonly rail?: ReactNode
  readonly annonce?: string | null
  /** Le contenu arrive : `aria-busy`, et rien n'est annoncé. */
  readonly occupe?: boolean
  /** Une page d'attente : la page attendue prendra le focus et le défilement. */
  readonly attente?: boolean
  /** Change à chaque page : le focus revient au contenu quand elle change. */
  readonly page: string
  readonly children: ReactNode
}

const APPLICATION = 'Portfolio Risk Engine'

/** La page de l'avertissement, où mène le lien de la mention. */
const AVERTISSEMENT = cheminDe({ vue: 'avertissement' })

/** Les ancres des sections de l'analyse, portées par la `<section>`. */
const ANCRES_DES_SECTIONS = SECTIONS.map((section) => section.ancre)

/** Le titre du contenu que vise le fragment de l'adresse, s'il en est un. */
function titreVise(contenu: HTMLElement | null): HTMLElement | null {
  const ancre = window.location.hash.slice(1)
  if (contenu === null || ancre === '') return null
  const cible = document.getElementById(idDuTitreVise(ancre, ANCRES_DES_SECTIONS))
  if (cible === null || !contenu.contains(cible)) return null
  return /^H[1-3]$/.test(cible.tagName) && cible.getAttribute('tabindex') === '-1' ? cible : null
}

/** Ce qui rend la main à l'utilisateur : il fait défiler, touche, clique ou tape. */
const GESTES = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const

/**
 * Fait défiler jusqu'au titre, sous le bandeau, et l'y garde pendant que la
 * page s'installe, comme le navigateur le fait d'une ancre au chargement. Les
 * polices qui arrivent allongent le texte au-dessus du titre (mesuré : 790 px
 * au chargement de `/methodologie#cvar`), et le navigateur ne compense pas ce
 * déplacement ; le bandeau collant s'allonge quand la liste des portefeuilles
 * arrive, et le titre passe dessous. Chaque changement de taille de la page
 * ramène donc le titre, jusqu'au premier geste de l'utilisateur ou pendant
 * dix secondes au plus. Rend de quoi arrêter. Un lien rendu au retour est
 * gardé de même : les graphiques, dessinés après le texte, allongent la page
 * au-dessus de lui.
 */
function garderEnVue(element: HTMLElement): () => void {
  const observateur = new ResizeObserver(() => element.scrollIntoView({ block: 'start' }))
  const arreter = () => {
    observateur.disconnect()
    window.clearTimeout(delai)
    for (const geste of GESTES) window.removeEventListener(geste, arreter)
  }
  const delai = window.setTimeout(arreter, 10_000)
  for (const geste of GESTES) window.addEventListener(geste, arreter, { passive: true })
  // Le premier rapport, à l'image suivante, fait le premier défilement.
  observateur.observe(document.body)
  return arreter
}

export function Cadre({
  titre,
  titreSeul,
  entete,
  rail,
  annonce,
  occupe,
  attente,
  page,
  children,
}: Props) {
  const { libelles } = useLangue()
  const contenu = useRef<HTMLElement>(null)
  // La note d'un lien vers la méthode, en attente que la page soit prête.
  const retourEnAttente = useRef<NoteDeRetour | null>(null)

  useEffect(() => {
    document.title = titreSeul ? titre : `${titre} (${APPLICATION})`
  }, [titre, titreSeul])

  useEffect(() => {
    if (attente) return
    // Un retour arrière vers une page que quittait un lien vers la méthode :
    // le lien suivi sera rendu quand la page sera prête (effet suivant).
    const note = navigationParHistorique() ? noteDeRetourCourante() : null
    if (note !== null) {
      retourEnAttente.current = note
      return
    }
    // Le chargement de l'application change de page lui aussi (démarrage,
    // redirection de `/`) : seul un changement DÉCIDÉ par l'utilisateur
    // déplace le focus.
    const decide = aDejaNavigue()
    const vise = titreVise(contenu.current)
    if (vise !== null) {
      if (decide) vise.focus({ preventScroll: true })
      return garderEnVue(vise)
    }
    if (!decide) return
    const titrePage = contenu.current?.querySelector<HTMLElement>('h1[tabindex="-1"]')
    ;(titrePage ?? contenu.current)?.focus()
    window.scrollTo({ top: 0 })
  }, [page, attente])

  useEffect(() => {
    const note = retourEnAttente.current
    if (note === null || occupe) return
    retourEnAttente.current = null
    const liens = [...(contenu.current?.querySelectorAll<HTMLElement>('[data-retour]') ?? [])]
    const retour = resoudreRetour(
      note,
      liens.map((lien) => lien.dataset['retour'] ?? ''),
    )
    if (retour === null) return
    if ('focus' in retour) {
      const lien = liens.find((candidat) => candidat.dataset['retour'] === retour.focus)
      if (lien === undefined) return
      lien.focus({ preventScroll: true })
      return garderEnVue(lien)
    }
    window.scrollTo({ top: retour.y })
  }, [occupe, page])

  useEffect(() => {
    // Un lien suivi sur la page a déjà fait défiler ; il n'a posé le focus
    // que sur un titre qui porte lui-même l'ancre. Un retour arrière d'une
    // ancre à l'autre rend sa position, pas le focus. Dans les deux cas, le
    // titre visé le reçoit, sans défiler davantage.
    const surFragment = () => titreVise(contenu.current)?.focus({ preventScroll: true })
    window.addEventListener('hashchange', surFragment)
    return () => window.removeEventListener('hashchange', surFragment)
  }, [])

  return (
    <>
      <a className={styles.evitement} href="#contenu">
        {libelles.cadre.allerAuContenu}
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
          {DEMO && (
            <p className={styles.mention}>
              {libelles.demo.mention(PORTEFEUILLES_DE_LA_DEMO, DATE_DE_LA_DEMO)}{' '}
              <Lien
                vers={AVERTISSEMENT}
                aria-current={page === AVERTISSEMENT ? 'page' : undefined}
              >
                {libelles.demo.lireLAvertissement}
              </Lien>
            </p>
          )}
          <p className={styles.annonce} role="status">
            {annonce ?? ''}
          </p>
          {children}
        </main>
      </div>
    </>
  )
}
