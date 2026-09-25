/**
 * Ce que tous les graphiques partagent — DESIGN.md §9.4.
 */
import type { Couleurs } from './couleurs'

/**
 * Une étiquette posée SUR le tracé reste lisible au-dessus d'une barre ou
 * d'une courbe : un liseré de la couleur de la page l'en détache (Plot peint
 * le contour sous le texte). L'encre reste un token de texte, jamais la
 * couleur de la série (§12).
 */
export function halo(couleurs: Couleurs, encre: string) {
  return { fill: encre, stroke: couleurs.surface0, strokeWidth: 3 }
}
