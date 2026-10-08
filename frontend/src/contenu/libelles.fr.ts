/**
 * Les libellés de l'interface, en français : la langue par défaut. Chaque
 * libellé y est celui d'avant le chantier 7D, sauf les trois exceptions
 * décidées le 2026-10-08 : le bouton de langue, le bouton de l'écran
 * d'acceptation selon la page d'arrivée, et « Bêta » dans le tableau de la
 * section 5.
 */
import type { Libelles } from './libelles'

export const LIBELLES_FR: Libelles = {
  langue: {
    explication: '(le site passe en anglais)',
  },
  acceptation: {
    ouvrir: {
      analyse: "Ouvrir l'analyse",
      positions: 'Ouvrir les positions',
      portefeuilles: 'Ouvrir les portefeuilles',
      methodologie: 'Ouvrir la méthodologie',
      page: 'Ouvrir la page demandée',
    },
    condition: {
      analyse: "La case doit être cochée pour ouvrir l'analyse.",
      positions: 'La case doit être cochée pour ouvrir les positions.',
      portefeuilles: 'La case doit être cochée pour ouvrir les portefeuilles.',
      methodologie: 'La case doit être cochée pour ouvrir la méthodologie.',
      page: 'La case doit être cochée pour ouvrir la page demandée.',
    },
  },
}
