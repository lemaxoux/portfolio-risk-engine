/**
 * Bascule de thème — DESIGN.md §4 et §15.
 *
 * LE LIBELLÉ DIT CE QUE LE CLIC FAIT, pas l'état courant (§15, verbes actifs) :
 * « Thème sombre » quand cliquer passe au sombre, « Suivre le système » quand
 * cliquer rend la main au système. Un bouton qui afficherait l'état courant se
 * lirait dans les deux sens et personne ne saurait ce qu'il déclenche.
 */
import { useEffect, useState } from 'react'

import {
  appliquerTheme,
  contraire,
  themeDuSysteme,
  themeFige,
  type Theme,
} from '../lib/theme'
import styles from './ThemeToggle.module.css'

const NOM: Record<Theme, string> = { light: 'clair', dark: 'sombre' }

export function ThemeToggle() {
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
  const libelle =
    cible === null ? 'Suivre le système' : `Thème ${NOM[cible]}`

  return (
    <button
      type="button"
      className={styles.bascule}
      onClick={() => {
        appliquerTheme(cible)
        setFige(cible)
      }}
      aria-describedby="bascule-theme-etat"
    >
      {libelle}
      <span id="bascule-theme-etat" className={styles.etat}>
        {fige === null
          ? `thème ${NOM[affiche]}, comme le système`
          : `thème ${NOM[affiche]}, figé`}
      </span>
    </button>
  )
}
