/**
 * La langue des contenus rédigés, choisie en UN SEUL endroit (chantier
 * 7B.3b). Le français seul aujourd'hui ; le chantier 7D ajoutera l'anglais,
 * son fichier et le choix de la langue, sans toucher au lecteur
 * (`lib/contenu.ts`) ni à la vue.
 *
 * Un fichier par langue (`methodologie.fr.md`), importé brut : un texte n'est
 * pas du code, il se relit et se traduit tel quel. Les ancres (`{#cvar}`) sont
 * les mêmes dans toutes les langues : ce sont des identifiants, que viseront
 * les liens d'une mesure vers sa méthode.
 */
import methodologieFr from './methodologie.fr.md?raw'

export type Langue = 'fr'

/** La langue affichée. */
export const LANGUE: Langue = 'fr'

/** Le texte de la page méthodologie, par langue. */
export const METHODOLOGIE: Readonly<Record<Langue, string>> = { fr: methodologieFr }
