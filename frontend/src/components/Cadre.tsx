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
 */
import { useEffect, useRef, type ReactNode } from 'react'

import { idDuTitreVise } from '../lib/focus'
import { useLangue } from '../lib/langue'
import { aDejaNavigue } from '../lib/route'
import { SECTIONS } from './Navigation'
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
 * dix secondes au plus. Rend de quoi arrêter.
 */
function garderEnVue(titre: HTMLElement): () => void {
  const observateur = new ResizeObserver(() => titre.scrollIntoView({ block: 'start' }))
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

export function Cadre({ titre, entete, rail, annonce, occupe, page, children }: Props) {
  const { libelles } = useLangue()
  const contenu = useRef<HTMLElement>(null)

  useEffect(() => {
    document.title = `${titre} (${APPLICATION})`
  }, [titre])

  useEffect(() => {
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
  }, [page])

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
          <p className={styles.annonce} role="status">
            {annonce ?? ''}
          </p>
          {children}
        </main>
      </div>
    </>
  )
}
