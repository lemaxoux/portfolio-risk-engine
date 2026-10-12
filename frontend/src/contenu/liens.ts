/**
 * Les adresses et les noms propres de la page de présentation — DESIGN.md
 * §19.1 (chantier 9.4).
 *
 * Des noms propres et des adresses, et rien d'autre : jamais de prose. Ils
 * s'écrivent de même dans les deux langues, et ne sont donc pas des
 * libellés ; les textes des liens, eux, sont dans les fichiers de libellés.
 *
 * Chaque adresse est écrite en entier, sans la composer : une constante
 * composée laisse une trace dans le build de l'application, qui n'a pas
 * cette page. Les documents sont ceux que GitHub rend sur la branche
 * principale. `contenu/presentation.test.ts` tient chaque adresse.
 *
 * Aucune adresse électronique, sur aucune page.
 */
export const ADRESSES = {
  /** Le dépôt public du projet. */
  depot: 'https://github.com/lemaxoux/portfolio-risk-engine',
  /** L'installation : la section « Getting started » du README. */
  installation:
    'https://github.com/lemaxoux/portfolio-risk-engine/blob/main/README.md#getting-started',
  methodologieTechnique:
    'https://github.com/lemaxoux/portfolio-risk-engine/blob/main/METHODOLOGY.md',
  architecture: 'https://github.com/lemaxoux/portfolio-risk-engine/blob/main/ARCHITECTURE.md',
  /** Le profil de l'auteur ; le dépôt, lui, est dans la liste des liens. */
  auteurSurGitHub: 'https://github.com/lemaxoux',
  /** Le tiret final fait partie de l'adresse. */
  auteurSurLinkedIn: 'https://www.linkedin.com/in/maxence-champlong-',
} as const

export const NOMS = {
  gitHub: 'GitHub',
  linkedIn: 'LinkedIn',
} as const
