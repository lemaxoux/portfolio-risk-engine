/**
 * Les libellés de l'interface, en anglais américain (chantier 7D) :
 * ponctuation de Chicago, casse phrase, aucune contraction, « you » pour le
 * vouvoiement. Les termes sont ceux du glossaire (`anglais-proposition.md`,
 * §c.2, hors dépôt) ; un terme nouveau est listé dans le rapport de la
 * session.
 */
import type { Libelles } from './libelles'

export const LIBELLES_EN: Libelles = {
  langue: {
    explication: '(the site switches to French)',
  },
  acceptation: {
    ouvrir: {
      analyse: 'Open the analysis',
      positions: 'Open the positions',
      portefeuilles: 'Open the portfolios',
      methodologie: 'Open the methodology',
      page: 'Open the requested page',
    },
    condition: {
      analyse: 'The box must be checked to open the analysis.',
      positions: 'The box must be checked to open the positions.',
      portefeuilles: 'The box must be checked to open the portfolios.',
      methodologie: 'The box must be checked to open the methodology.',
      page: 'The box must be checked to open the requested page.',
    },
  },
}
