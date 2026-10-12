/**
 * Les captures de la page de présentation — DESIGN.md §19.4.
 *
 * Deux figures, toutes deux du portefeuille « Démo » : un bloc de mesure de
 * l'analyse, pris sur le build de démonstration, et la page de saisie de
 * l'application. Quatre fichiers chacune : une langue, un thème. Capturées à
 * 390 px de large et à l'échelle 2, passées en palette, jamais retouchées.
 *
 * La page n'en charge que deux par visite : celles de sa langue, dans son
 * thème (`components/Capture`). Importées ici, elles reçoivent de Vite une
 * empreinte dans leur nom.
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
import saisieEnClair from './saisie-en-clair.png'
import saisieEnSombre from './saisie-en-sombre.png'
import saisieFrClair from './saisie-fr-clair.png'
import saisieFrSombre from './saisie-fr-sombre.png'

/** Une figure dans une langue : ses deux fichiers, et sa taille d'affichage. */
export interface FichiersDUneCapture {
  readonly claire: string
  readonly sombre: string
  readonly largeur: number
  readonly hauteur: number
}

/** La largeur de la fenêtre des captures : celle d'un téléphone (§19.4). */
const LARGEUR = 390

export const CAPTURES: Record<'mesure' | 'saisie', Record<Langue, FichiersDUneCapture>> = {
  mesure: {
    fr: { claire: mesureFrClair, sombre: mesureFrSombre, largeur: LARGEUR, hauteur: 461 },
    en: { claire: mesureEnClair, sombre: mesureEnSombre, largeur: LARGEUR, hauteur: 461 },
  },
  saisie: {
    fr: { claire: saisieFrClair, sombre: saisieFrSombre, largeur: LARGEUR, hauteur: 988 },
    en: { claire: saisieEnClair, sombre: saisieEnSombre, largeur: LARGEUR, hauteur: 968 },
  },
}
