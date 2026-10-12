/**
 * L'écriture de la couverture d'une crise rejouée — DESIGN.md §11.2.
 *
 * La part de la valeur que le rejeu couvre, puis le nombre de lignes, et le
 * point de réserve DÈS que la couverture est incomplète, pas seulement sous
 * le seuil : le seuil déclenche l'observation du moteur de règles,
 * l'affichage signale le fait.
 *
 * Une seule fonction, pour les deux endroits qui l'écrivent : le bloc d'une
 * crise, en section 5, et le bloc du résultat de la page de présentation
 * (§19.3), où la couverture suit la phrase à sa taille. Les deux lisent le
 * même objet publié et l'écrivent de même, sans calcul.
 */
import type { Coverage } from '../api/types'
import { LIBELLES } from '../contenu/libelles'
import { pourcentage } from './format'
import type { Langue } from './langue'

export interface EcritureDeLaCouverture {
  /** La part de la valeur couverte : « 100 % ». */
  readonly part: string
  /** Les lignes couvertes : « 6 lignes sur 6 ». */
  readonly lignes: string
  /** Sous 100 % : la couverture porte le point de réserve. */
  readonly partielle: boolean
}

export function ecrireLaCouverture(couverture: Coverage, langue: Langue): EcritureDeLaCouverture {
  return {
    part: pourcentage(couverture.value_share, 0, langue),
    lignes: LIBELLES[langue].crise.couvertes(couverture.covered_count, couverture.total_count),
    partielle: !couverture.is_complete,
  }
}
