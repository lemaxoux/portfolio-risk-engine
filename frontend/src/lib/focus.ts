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
