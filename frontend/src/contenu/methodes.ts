/**
 * Le lien de chaque mesure vers son entrée de la méthodologie (chantier 7E,
 * DESIGN.md §9.1 ; annexe A de `methodologie-proposition.md`, hors dépôt).
 *
 * ═══ UNE SEULE TABLE ═══
 *
 * `METHODES` dit quelles entrées explique chaque bloc de l'analyse, selon
 * l'annexe A à la lettre. Les sections la lisent ; aucune n'écrit une ancre
 * à la main. Les ancres sont les mêmes dans toutes les langues
 * (`methodologie.test.ts` en fixe la liste).
 *
 * ═══ LE TEXTE D'UN LIEN EST LE TITRE DE SON ENTRÉE ═══
 *
 * Lu dans le fichier de méthodologie de la langue de la page : un seul texte
 * par langue, et le lien nomme exactement ce qu'il ouvre. Dans une même
 * paire, les entrées qui suivent la première prennent une minuscule
 * initiale, sauf un sigle : « Les trois chiffres d'une crise, la
 * couverture », « La CVaR ».
 */
import { lireContenu, texteDe } from '../lib/contenu'
import type { Langue } from '../lib/langue'
import { METHODOLOGIE } from './methodologie'

/** Les entrées de la méthodologie qu'un bloc de l'analyse peut viser. */
export type Ancre =
  | 'donnees'
  | 'conventions'
  | 'valeur-et-poids'
  | 'var-historique'
  | 'histogramme'
  | 'var-parametrique'
  | 'volatilite'
  | 'cvar'
  | 'perte-maximale'
  | 'courbe-de-valeur'
  | 'lignes-effectives'
  | 'part-des-variations'
  | 'correlation'
  | 'trois-chiffres'
  | 'couverture'
  | 'sensibilite'
  | 'attendu'
  | 'constats'
  | 'seuils-choisis'
  | 'seuils-demontres'
  | 'references'
  | 'refus'

/** Les entrées de chaque bloc de l'analyse, dans l'ordre où la paire les cite. */
export const METHODES = {
  /** Section 1 : la date de valorisation et les cours, la fenêtre, la valeur et le poids. */
  portefeuille: ['donnees', 'conventions', 'valeur-et-poids'],
  varHistorique: ['var-historique'],
  histogramme: ['histogramme'],
  varParametrique: ['var-parametrique'],
  volatilite: ['volatilite'],
  cvar: ['cvar'],
  perteMaximale: ['perte-maximale'],
  courbe: ['courbe-de-valeur'],
  lignesEffectives: ['lignes-effectives'],
  partsDesVariations: ['part-des-variations'],
  /** Le tableau de la section 4 : ce que chaque ligne a apporté dans chaque crise. */
  apportsEnCrise: ['trois-chiffres'],
  correlation: ['correlation'],
  /** Le bloc d'une crise rejouée : ses trois chiffres, dont la couverture. */
  crise: ['trois-chiffres', 'couverture'],
  /** La sensibilité au marché, en temps ordinaire et en crise, et ce qu'elle laissait attendre. */
  regime: ['sensibilite', 'attendu'],
  /** Les constats de la section 6 et leurs lignes de seuil. */
  moteur: ['constats', 'seuils-choisis', 'seuils-demontres', 'references'],
} as const satisfies Readonly<Record<string, readonly Ancre[]>>

/** L'entrée qu'ajoute un refus (le tiret et sa raison) aux entrées de son bloc. */
export const REFUS: Ancre = 'refus'

/** Les entrées d'un bloc, et `refus` quand le bloc affiche un refus. */
export function avecRefus(ancres: readonly Ancre[], refuse: boolean): readonly Ancre[] {
  return refuse ? [...ancres, REFUS] : ancres
}

/**
 * Le lien d'un bloc vers sa méthode : le bloc, par un identifiant qui ne
 * dépend pas de la langue (`var-historique-0.95`), et ses entrées. La clé du
 * retour arrière en est faite (`lib/focus.ts`).
 */
export interface Methode {
  readonly bloc: string
  readonly ancres: readonly Ancre[]
}

const TITRES = new Map<Langue, ReadonlyMap<string, string>>()

/** Le titre de chaque partie et de chaque entrée de la méthodologie, par ancre. */
export function titresDesEntrees(langue: Langue): ReadonlyMap<string, string> {
  const connus = TITRES.get(langue)
  if (connus !== undefined) return connus
  const titres = new Map<string, string>()
  for (const bloc of lireContenu(METHODOLOGIE[langue]).blocs) {
    if (bloc.type === 'titre' && bloc.ancre !== null) titres.set(bloc.ancre, texteDe(bloc.contenu))
  }
  TITRES.set(langue, titres)
  return titres
}

export function titreDeLEntree(ancre: Ancre, langue: Langue): string {
  const titre = titresDesEntrees(langue).get(ancre)
  if (titre === undefined) throw new Error(`Aucune entrée #${ancre} dans la méthodologie (${langue}).`)
  return titre
}

/**
 * Le titre d'une entrée qui en suit une autre dans la même paire : minuscule
 * initiale, sauf quand son premier mot est un sigle, une majuscule après sa
 * première lettre (« CVaR », « VaR »).
 */
export function enSuite(titre: string): string {
  const [premier = ''] = titre.split(' ')
  const sigle = [...premier.slice(1)].some((lettre) => lettre !== lettre.toLowerCase())
  return sigle ? titre : titre.charAt(0).toLowerCase() + titre.slice(1)
}
