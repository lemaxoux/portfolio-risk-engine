/**
 * Bascule de thème — DESIGN.md §4 et §15.
 *
 * LE LIBELLÉ DIT CE QUE LE CLIC FAIT, pas l'état courant (§15, verbes actifs) :
 * « Thème sombre » quand cliquer passe au sombre, « Suivre le système » quand
 * cliquer rend la main au système. Un bouton qui afficherait l'état courant se
 * lirait dans les deux sens et personne ne saurait ce qu'il déclenche.
 */
import { useEffect, useState } from 'react'

import { useLangue } from '../lib/langue'
import {
  appliquerTheme,
  contraire,
  themeDuSysteme,
  themeFige,
  type Theme,
} from '../lib/theme'
import styles from './ThemeToggle.module.css'

export function ThemeToggle() {
  const { libelles } = useLangue()
  const NOM: Record<Theme, string> = { light: libelles.theme.clair, dark: libelles.theme.sombre }
  const [fige, setFige] = useState<Theme | null>(() => themeFige())
  const [systeme, setSysteme] = useState<Theme>(() => themeDuSysteme())

  // Le réglage du système peut changer à tout moment — bascule nocturne
  // automatique, préférence modifiée dans un autre onglet. Le CSS s'y adapte
  // seul ; le LIBELLÉ du bouton, lui, doit être recalculé, sinon il proposerait
  // de passer au sombre sur une page déjà sombre.
  useEffect(() => {
    const requete = window.matchMedia('(prefers-color-scheme: dark)')
    const surChangement = () => setSysteme(requete.matches ? 'dark' : 'light')
    requete.addEventListener('change', surChangement)
    return () => requete.removeEventListener('change', surChangement)
  }, [])

  const affiche = fige ?? systeme
  // Les deux états : « comme le système », et l'autre — figé littéralement.
  const cible: Theme | null = fige === null ? contraire(systeme) : null
  const libelle = cible === null ? libelles.theme.suivreLeSysteme : libelles.theme.vers(NOM[cible])
  const etat =
    fige === null ? libelles.theme.commeLeSysteme(NOM[affiche]) : libelles.theme.fige(NOM[affiche])

  return (
    <button
      type="button"
      className={styles.bascule}
      // Le nom accessible COMMENCE par le libellé visible (WCAG 2.5.3) : un
      // utilisateur de commande vocale doit pouvoir dire ce qu'il lit. L'état
      // courant le complète, parce qu'un bouton qui ne dit que l'action laisse
      // ignorer d'où l'on part.
      aria-label={libelles.theme.nomAccessible(libelle, etat)}
      onClick={() => {
        appliquerTheme(cible)
        setFige(cible)
      }}
    >
      <span>{libelle}</span>
      <span className={styles.etat}>{etat}</span>
    </button>
  )
}
