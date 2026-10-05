/**
 * `<Absent>` : une valeur absente. DESIGN.md §6.3 et §9.1, règle 3.
 *
 * Une mesure refusée, une cellule sans donnée : jamais « 0 », jamais « ∞ ».
 * L'œil voit un tiret court ; un lecteur d'écran, qui ne dirait rien d'un
 * tiret seul, lit « non disponible ». La RAISON de l'absence s'affiche à
 * côté, elle n'est pas de ce composant.
 *
 * C'est le seul tiret isolé de l'interface, et le seul endroit qui l'écrit :
 * une cellule ou un chiffre qui reçoit `TIRET_INDEFINI` passe par
 * `avecAbsence`.
 */
import type { ReactNode } from 'react'

import { TIRET_INDEFINI } from '../lib/format'

/** Ce qu'un lecteur d'écran lit à la place du tiret. */
export const TEXTE_ABSENT = 'non disponible'

export function Absent() {
  return (
    <>
      <span aria-hidden="true">{TIRET_INDEFINI}</span>
      <span className="visuellement-cache">{TEXTE_ABSENT}</span>
    </>
  )
}

/**
 * Le contenu d'un chiffre ou d'une cellule, déjà écrit par `lib/format` : le
 * tiret d'indéfini y reçoit son texte, tout autre contenu passe tel quel.
 */
export function avecAbsence(contenu: ReactNode): ReactNode {
  return contenu === TIRET_INDEFINI ? <Absent /> : contenu
}
