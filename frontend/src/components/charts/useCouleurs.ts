/**
 * Les couleurs du thème courant, et un nouveau jeu à chaque changement.
 *
 * Le thème change par DEUX chemins, et un graphique doit suivre les deux :
 *
 * * la bascule manuelle, qui pose ou retire `data-theme` sur `<html>` ;
 * * le système, quand on suit le système (`prefers-color-scheme`) — bascule
 *   nocturne automatique, réglage changé dans un autre onglet.
 *
 * Le CSS suit seul ; un graphique Plot, lui, a écrit des VALEURS de couleur
 * dans son SVG et doit être retracé. D'où ce crochet : il relit les tokens
 * quand l'un ou l'autre bouge, et le composant qui s'en sert se redessine.
 */
import { useEffect, useState } from 'react'

import { couleursDuDocument, type Couleurs } from './couleurs'

/**
 * `null` hors navigateur — rendu côté serveur, dans les tests : il n'y a
 * alors ni document ni thème, et rien à tracer.
 */
export function useCouleurs(): Couleurs | null {
  const [couleurs, setCouleurs] = useState<Couleurs | null>(() =>
    typeof document === 'undefined' ? null : couleursDuDocument(),
  )

  useEffect(() => {
    const relire = () => setCouleurs(couleursDuDocument())

    const observateur = new MutationObserver(relire)
    observateur.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })

    const systeme = window.matchMedia('(prefers-color-scheme: dark)')
    systeme.addEventListener('change', relire)

    return () => {
      observateur.disconnect()
      systeme.removeEventListener('change', relire)
    }
  }, [])

  return couleurs
}
