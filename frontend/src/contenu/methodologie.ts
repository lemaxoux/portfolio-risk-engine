/**
 * Le texte de la page méthodologie, un fichier par langue (chantier 7B.3b,
 * puis 7D). C'est le seul endroit qui choisit le fichier : ni le lecteur
 * (`lib/contenu.ts`) ni la vue n'en savent rien.
 *
 * Un fichier par langue (`methodologie.fr.md`, `methodologie.en.md`), importé
 * brut : un texte n'est pas du code, il se relit et se traduit tel quel. Les
 * deux langues sont dans le bundle, sans chargement à la demande (décision du
 * 2026-10-08). Les ancres (`{#cvar}`) sont les mêmes dans toutes les langues :
 * ce sont des identifiants, que viseront les liens d'une mesure vers sa
 * méthode.
 */
import type { Langue } from '../lib/langue'
import methodologieEn from './methodologie.en.md?raw'
import methodologieFr from './methodologie.fr.md?raw'

/** Le texte de la page méthodologie, par langue. */
export const METHODOLOGIE: Readonly<Record<Langue, string>> = {
  fr: methodologieFr,
  en: methodologieEn,
}
