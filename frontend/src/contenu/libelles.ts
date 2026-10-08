/**
 * Les libellés de l'interface, un objet par langue (chantier 7D) : sans
 * bibliothèque, une interface typée que `libelles.fr.ts` et `libelles.en.ts`
 * remplissent. TypeScript refuse une clé manquante dans une langue, et
 * `libelles.test.ts` une traduction oubliée.
 *
 * Ce module ne décide rien : quel libellé afficher se décide dans les
 * composants, sur des champs publiés ; ici, chaque langue l'écrit.
 */
import { LIBELLES_EN } from './libelles.en'
import { LIBELLES_FR } from './libelles.fr'
import type { Langue } from '../lib/langue'

/**
 * La page où mène l'écran d'acceptation : celle de l'adresse d'arrivée. `/`
 * rouvre une analyse ; une adresse inconnue, la page qu'elle demandait.
 */
export type Destination = 'analyse' | 'positions' | 'portefeuilles' | 'methodologie' | 'page'

export interface Libelles {
  /** Le bouton qui passe à l'autre langue. */
  readonly langue: {
    /** Lu par un lecteur d'écran après le nom de l'autre langue. */
    readonly explication: string
  }
  readonly acceptation: {
    /** Le bouton dit la page où il mène, comme son message. */
    readonly ouvrir: Readonly<Record<Destination, string>>
    readonly condition: Readonly<Record<Destination, string>>
  }
}

export const LIBELLES: Readonly<Record<Langue, Libelles>> = { fr: LIBELLES_FR, en: LIBELLES_EN }

/** Le nom de chaque langue, dans cette langue : le libellé du bouton. */
export const NOMS_DES_LANGUES: Readonly<Record<Langue, string>> = {
  fr: 'Français',
  en: 'English',
}
