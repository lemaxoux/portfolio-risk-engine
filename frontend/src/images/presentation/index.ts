/**
 * Les captures de la page de présentation — DESIGN.md §19.4.
 *
 * Une figure, du portefeuille « Démo » : un bloc de mesure de l'analyse, pris
 * sur le build de démonstration. Quatre fichiers : une langue, un thème.
 * Capturés dans une fenêtre de 390 px de large, à l'échelle 2, passés en
 * palette, jamais retouchés ni agrandis. La seconde figure, le tableau de
 * saisie de l'application, a été retirée au chantier 9.6 : le site a
 * désormais sa propre saisie.
 *
 * La page n'en charge qu'un par visite : celui de sa langue, dans son thème
 * (`components/Capture`). Importés ici, ils reçoivent de Vite une empreinte
 * dans leur nom.
 *
 * Les dimensions sont celles de l'affichage, la moitié de celles du fichier :
 * `captures.test.ts` les tient égales à l'en-tête de chaque PNG.
 *
 * `apercu.png`, dans ce dossier, est l'image de prévisualisation des liens
 * partagés (§19.7). Aucune page ne l'affiche : le greffon du build de
 * démonstration l'émet (`api/demoAuBuild.ts`).
 */
import type { Langue } from '../../lib/langue'
import mesureEnClair from './mesure-en-clair.png'
import mesureEnSombre from './mesure-en-sombre.png'
import mesureFrClair from './mesure-fr-clair.png'
import mesureFrSombre from './mesure-fr-sombre.png'

/** Une figure dans une langue : ses deux fichiers, et sa taille d'affichage. */
export interface FichiersDUneCapture {
  readonly claire: string
  readonly sombre: string
  readonly largeur: number
  readonly hauteur: number
}

/** La largeur de la fenêtre des captures : celle d'un téléphone (§19.4). */
const LARGEUR = 390

export const CAPTURES: Record<'mesure', Record<Langue, FichiersDUneCapture>> = {
  mesure: {
    fr: { claire: mesureFrClair, sombre: mesureFrSombre, largeur: LARGEUR, hauteur: 461 },
    en: { claire: mesureEnClair, sombre: mesureEnSombre, largeur: LARGEUR, hauteur: 461 },
  },
}
