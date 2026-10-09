/**
 * Les décisions de focus qui n'ont pas besoin d'un document (chantier 7E,
 * DESIGN.md §13).
 *
 * Où va le focus après un geste est une règle ; le déplacer est un effet.
 * Les règles sont ici, en fonctions pures que Vitest garde dans le dépôt ;
 * l'effet se prouve dans Chrome (`docs/outils/clavier.mjs`, hors dépôt),
 * Vitest tournant sans document.
 */

/**
 * L'identifiant du titre que vise une ancre de l'adresse.
 *
 * Une section de l'analyse porte son ancre sur la `<section>` (`#qui-porte`) :
 * c'est son titre, `qui-porte-titre`, qui reçoit le focus, comme le titre
 * d'une partie de la méthodologie, qui porte lui-même son ancre (`#cvar`).
 */
export function idDuTitreVise(ancre: string, sections: readonly string[]): string {
  return sections.includes(ancre) ? `${ancre}-titre` : ancre
}

/**
 * La rangée du tableau de saisie qui reçoit le focus après « Retirer », par
 * son rang dans le tableau d'après.
 *
 * Celle qui prend la place de la rangée retirée ; si la rangée retirée était
 * la dernière, la nouvelle dernière ; s'il n'en restait qu'une, la rangée
 * vierge qui la remplace. Le focus ne tombe jamais au début du document.
 */
export function rangeeApresRetrait(rangRetire: number, nombreAvant: number): number {
  if (nombreAvant <= 1) return 0
  return Math.min(rangRetire, nombreAvant - 2)
}

// ═══════════════════════════════════════════ Le retour depuis la méthode ══

/**
 * La clé d'un lien vers la méthode : son bloc ET son ancre. Les deux liens
 * « La VaR historique » de la section 2, l'un sous la VaR à 95 %, l'autre
 * sous la VaR à 99 %, restent distincts. Elle ne dépend pas de la langue :
 * une langue changée sur la méthodologie retrouve le même lien au retour.
 */
export function cleDeRetour(bloc: string, ancre: string): string {
  return `${bloc}#${ancre}`
}

/**
 * Ce qu'une page note dans son entrée d'historique quand un lien vers la
 * méthode la quitte : la clé du lien suivi, et la position de la page, qui
 * ne sert que si la clé est introuvable au retour.
 */
export interface NoteDeRetour {
  readonly cle: string
  readonly y: number
}

/** La note lue dans l'état d'une entrée d'historique, si elle est bien formée. */
export function noteDeRetour(etat: unknown): NoteDeRetour | null {
  if (typeof etat !== 'object' || etat === null || !('retour' in etat)) return null
  const retour: unknown = etat.retour
  if (typeof retour !== 'object' || retour === null) return null
  if (!('cle' in retour) || !('y' in retour)) return null
  const { cle, y } = retour
  return typeof cle === 'string' && typeof y === 'number' ? { cle, y } : null
}

/** Ce que fait la page au retour : le focus sur le lien suivi, sinon la position notée. */
export type Retour = { readonly focus: string } | { readonly y: number }

/**
 * Au retour sur une page que quittait un lien vers la méthode : le lien
 * suivi reprend le focus s'il est sur la page, quelle que soit sa position,
 * qu'un changement de langue ou de thème sur la méthodologie a pu déplacer.
 * La position notée ne sert que si la clé est introuvable. Sans note, rien.
 */
export function resoudreRetour(note: NoteDeRetour | null, clesPresentes: readonly string[]): Retour | null {
  if (note === null) return null
  return clesPresentes.includes(note.cle) ? { focus: note.cle } : { y: note.y }
}
