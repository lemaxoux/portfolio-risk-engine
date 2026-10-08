/**
 * Les langues du site (chantier 7D, décidé le 2026-10-07) : le français,
 * langue par défaut, et l'anglais américain.
 *
 * Le formateur (`format.ts`) prend la langue en dernier argument, « fr » par
 * défaut : un appel sans langue écrit exactement ce qu'il écrivait. Le choix
 * de la langue par l'utilisateur viendra en session 2 du chantier
 * (`contenu/langue.ts`, qui ne connaît encore que le français).
 */
export type Langue = 'fr' | 'en'

export const LANGUES: readonly Langue[] = ['fr', 'en']
