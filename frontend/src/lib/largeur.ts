/**
 * La page est-elle étroite ? Le même point de rupture que le CSS : sous
 * 900 px, la barre latérale s'escamote (DESIGN.md §7) et la colonne de lecture
 * se réduit à l'écran.
 *
 * Pour ce que le CSS ne sait pas faire : l'ORDRE des colonnes d'un tableau.
 * Une cellule de tableau ne se déplace pas par `order`, et dupliquer une
 * colonne pour en masquer une copie selon la largeur doublerait le contenu
 * dans le document.
 *
 * `false` hors navigateur (rendu côté serveur, tests) : l'ordre large, celui
 * de DESIGN.md §8.2, est l'ordre de référence.
 */
import { useSyncExternalStore } from 'react'

export const REQUETE_ETROITE = '(width < 900px)'

function abonner(prevenir: () => void): () => void {
  const requete = window.matchMedia(REQUETE_ETROITE)
  requete.addEventListener('change', prevenir)
  return () => requete.removeEventListener('change', prevenir)
}

export function useEtroit(): boolean {
  return useSyncExternalStore(
    abonner,
    () => window.matchMedia(REQUETE_ETROITE).matches,
    () => false,
  )
}
