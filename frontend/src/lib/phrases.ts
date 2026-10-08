/**
 * Les phrases que l'interface COMPOSE — DESIGN.md §8.1, §9.1 et §15, et les
 * textes de lecture validés le 2026-10-05 (`textes-lecture.md`, hors dépôt).
 *
 * Elles sont dans `lib/`, et pas dans les composants, pour deux raisons :
 * elles sont testables sans rendu, et les avoir au même endroit rend visible
 * le peu qu'il y en a. Tout le reste de ce que le produit affirme est RÉDIGÉ
 * PAR LE BACKEND — observations du moteur de règles, raisons de refus,
 * réserves, libellés de période, nom de l'indice de référence, bandeau
 * d'acceptation — et s'affiche tel quel.
 *
 * ═══ UN MODULE COMMUN, UN MODULE PAR LANGUE (chantier 7D) ═══
 *
 * Ce module garde ce qui ne dépend pas de la langue : citer un nom, mettre une
 * capitale, et les DÉCISIONS que les deux langues partagent — ce qu'un niveau
 * de confiance oppose à son seuil, ce que le rejeu d'une crise compare.
 * `phrases.fr.ts` et `phrases.en.ts` rédigent, avec les mêmes noms et les
 * mêmes signatures (`Phrases`) ; les composants les reçoivent par
 * `useLangue()`. Aucune décision n'est écrite deux fois.
 *
 * ═══ LE LECTEUR PART DE ZÉRO ═══
 *
 * Il n'a jamais entendu parler de VaR, de volatilité ni de bêta. Chaque mesure
 * reçoit donc une phrase concrète — la fréquence dite en calendrier, le montant
 * en dollars à la valeur d'aujourd'hui, la période — et une ligne courte sur ce
 * que le chiffre ne dit pas. Le terme technique reste dans le libellé (§15).
 *
 * Le passé est rejoué sur la composition D'AUJOURD'HUI, d'où le conditionnel :
 * « aurait perdu », « would have lost ». Le portefeuille n'a pas forcément été
 * détenu tel quel, et il ne valait pas sa valeur d'aujourd'hui le jour d'une
 * perte passée : un montant « représente » une part de la valeur d'aujourd'hui,
 * il ne dit jamais ce qui a été perdu en dollars.
 *
 * ═══ AUCUNE DE CES PHRASES NE CALCULE ═══
 *
 * Chaque nombre cité est un champ publié : montant, période, pire séance,
 * retour au pic, nom de l'indice viennent du moteur. La lecture d'un niveau de
 * confiance passe par une TABLE et non par une division : « un jour de bourse
 * sur vingt » n'est pas dérivé de 0,95, il y est associé. Une phrase choisit sa
 * tournure sur le SIGNE d'un champ publié — perte ou gain, même sens ou sens
 * inverse —, jamais sur une comparaison entre deux mesures.
 */
import type {
  Contribution,
  Drawdown,
  ExpectedShortfall,
  HistoricalVar,
  LimitingPosition,
  Parameters,
  Regime,
  ReturnHistogram,
  Scenario,
  TailRiskLevel,
  Var,
  Volatility,
  Window,
  WorstDay,
} from '../api/types'
import { ESPACE_INSECABLE } from './format'
import type { Langue } from './langue'

/**
 * Un nom cité entre guillemets français : « Démo ». Les espaces qui les
 * séparent du nom sont INSÉCABLES, sinon le « » » part seul en début de ligne
 * — le même défaut que le « % » que `format.ts` retient par une espace fine.
 *
 * En anglais (chantier 7D), des guillemets doubles sans espace : “Démo”.
 */
export function cite(texte: string, langue: Langue = 'fr'): string {
  if (langue === 'en') return `“${texte}”`
  return `«${ESPACE_INSECABLE}${texte}${ESPACE_INSECABLE}»`
}

/** La première lettre en capitale : un libellé publié placé en tête de phrase. */
export function majuscule(texte: string): string {
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

/**
 * Un message placé après un deux-points : sa première lettre passe en
 * minuscule. Seul un mot écrit Capitale puis minuscule est touché : un ticker
 * en tête (MSFT apparaît deux fois) garde ses capitales.
 */
export function apresDeuxPoints(message: string): string {
  return /^\p{Lu}\p{Ll}/u.test(message)
    ? message.charAt(0).toLowerCase() + message.slice(1)
    : message
}

/**
 * Le refus d'une ligne de saisie ou d'un fichier, précédé de son numéro. Sans
 * numéro, le message passe tel quel. « Line 4: » en anglais.
 */
export function messageDeLigne(ligne: number | null, message: string, langue: Langue = 'fr'): string {
  if (ligne === null) return message
  if (langue === 'en') return `Line ${ligne}: ${apresDeuxPoints(message)}`
  return `Ligne ${ligne}${ESPACE_INSECABLE}: ${apresDeuxPoints(message)}`
}

// ═══════════════════════════════════════════ Lecture d'un niveau de confiance ══

/**
 * Ce qu'un niveau de confiance veut dire, en mots : une TABLE, pas un calcul.
 *
 * Écrire `1 / (1 − confiance)` produirait 20 pour 0,95 et 100 pour 0,99, mais
 * aussi 6,67 pour 0,85 — et il faudrait alors décider comment l'écrire,
 * c'est-à-dire inventer une lecture que personne n'a validée. Un niveau absent
 * de la table n'a pas de traduction : la phrase cite le niveau publié, ce qui
 * est moins parlant mais jamais faux. Contrôle de la table : 21 jours de
 * bourse par mois et 252 par an, soit 1,05 fois par mois pour un jour sur
 * vingt, 2,5 fois par an pour un jour sur cent.
 *
 * Les clés sont les niveaux que `routes/analysis.CONFIDENCE_LEVELS` publie.
 * Ce qui est DÉCIDÉ pour un niveau — ce que la ligne « ne dit pas » oppose au
 * seuil, et si la lecture se clôt sur les autres jours — est ici, une fois ;
 * chaque langue n'en écrit que les mots.
 */
export const DECISIONS_DE_NIVEAU: Readonly<
  Record<string, { readonly neDitPas: 'pire jour' | 'queue'; readonly autresJours: boolean }>
> = {
  '0.95': { neDitPas: 'pire jour', autresJours: true },
  '0.99': { neDitPas: 'queue', autresJours: false },
}

/** Les mots d'un niveau, dans une langue. */
export interface MotsDeNiveau {
  /** « un jour de bourse sur vingt » */
  readonly frequence: string
  /** « à peu près une fois par mois » */
  readonly calendrier: string
  /** La variante gain : « 19 jours de bourse sur 20 ». */
  readonly complement: string
  /** Entre parenthèses, après « jours de bourse » : « un sur vingt ». */
  readonly part: string
  /** Dans la légende de l'histogramme : « un jour sur vingt ». */
  readonly jour: string
  /** Le trait de l'histogramme : « le seuil d'un jour sur vingt ». */
  readonly seuil: string
  /**
   * La phrase qui clôt la lecture de la VaR historique, pour un niveau dont
   * la décision commune en veut une ; absente sinon.
   */
  readonly autresJours?: string
}

export interface LectureDeNiveau extends Omit<MotsDeNiveau, 'autresJours'> {
  /** La phrase qui clôt la lecture de la VaR historique, s'il y en a une. */
  readonly autresJours: string | null
  /** Ce que la ligne « ne dit pas » de la VaR historique oppose au seuil. */
  readonly neDitPas: 'pire jour' | 'queue'
}

/** La lecture d'un niveau : ses mots dans une langue, ses décisions communes. */
export function lectureDe(
  mots: Readonly<Record<string, MotsDeNiveau>>,
  confiance: number,
): LectureDeNiveau | null {
  const cle = String(confiance)
  const decision = DECISIONS_DE_NIVEAU[cle]
  const texte = mots[cle]
  if (decision === undefined || texte === undefined) return null
  return {
    ...texte,
    autresJours: decision.autresJours ? (texte.autresJours ?? null) : null,
    neDitPas: decision.neDitPas,
  }
}

// ═══════════════════════════════════════════════════ Les décisions communes ══

/**
 * Ce que le rejeu d'une crise dit de l'attendu. Même sens — perte attendue et
 * perte rejouée, gain et gain — : « de plus » ou « de moins » se lit sur la
 * perte ou sur le gain. Sens contraires : « de mieux » ou « de moins bien ».
 * `ecart` est le rejoué moins l'attendu, publié (`prediction_gap`).
 */
export type Comparatif = 'mieux' | 'moinsBien' | 'plus' | 'moins'

export function comparatifDuRejeu(
  pertePrevue: boolean,
  perteRejouee: boolean,
  ecart: number,
): Comparatif {
  if (pertePrevue !== perteRejouee) return ecart > 0 ? 'mieux' : 'moinsBien'
  const davantage = perteRejouee ? ecart < 0 : ecart > 0
  return davantage ? 'plus' : 'moins'
}

/** Le bêta de crise va-t-il en sens inverse de celui du temps ordinaire ? */
export function sensChangeEnCrise(calme: number, crise: number): boolean {
  return crise < 0 !== calme < 0
}

// ═══════════════════════════════════════════════════════════ Les phrases ══

/**
 * Ce que chaque langue rédige, avec les mêmes noms et les mêmes signatures.
 * `loi` reste la clé française de la loi (« normale », « de Student ») : c'est
 * un identifiant, que chaque langue écrit à sa façon.
 */
export interface Phrases {
  readonly lectureDuNiveau: (confiance: number) => LectureDeNiveau | null
  readonly frequenceLue: (confiance: number) => string | null
  readonly NE_DIT_PAS_GAIN: string
  readonly NE_DIT_PAS_REFUS: string
  readonly introJourOrdinaire: (periode: string) => string
  readonly lectureVarHistorique: (resultat: HistoricalVar, decimales: number, devise: string) => string
  readonly neDitPasVarHistorique: (
    resultat: HistoricalVar,
    pireJour: WorstDay,
    joursDansLaQueue: number | null,
  ) => string
  readonly lectureVarParametrique: (resultat: Var, loi: 'normale' | 'de Student', devise: string) => string
  readonly NE_DIT_PAS_COURBES: string
  readonly lectureVolatilite: (indice: Volatility | null, parametres: Parameters) => string
  readonly NE_DIT_PAS_VOLATILITE: string
  readonly lectureCVaR: (resultat: ExpectedShortfall, devise: string) => string
  readonly neDitPasCVaR: (resultat: ExpectedShortfall) => string | null
  readonly legendeHistogramme: (
    traces: readonly number[],
    refuses: readonly number[],
    largeur: number,
  ) => string
  readonly descriptionHistogramme: (
    histogramme: ReturnHistogram,
    niveaux: readonly TailRiskLevel[],
  ) => string
  readonly introAuPire: (periode: string) => string
  readonly lectureCreux: (creux: Drawdown, devise: string) => string
  readonly neDitPasCreux: (creux: Drawdown) => string
  readonly chapeauLignesEffectives: (n: number) => string
  readonly lectureLignesEnCapital: (n: number, effectives: number) => string
  readonly NE_DIT_PAS_CAPITAL: string
  readonly lectureLignesEnRisque: (n: number, effectives: number) => string
  readonly NE_DIT_PAS_RISQUE: string
  readonly lectureContribution: (ligne: Contribution) => string
  readonly NE_DIT_PAS_CONTRIBUTIONS: string
  readonly PHRASE_CONTRIBUTION_NEGATIVE: string
  readonly NE_DIT_PAS_CORRELATION: string
  readonly phraseCouverturePartielle: (exclues: number, couvertes: number, total: number) => string
  readonly lectureScenario: (scenario: Scenario, regime: Regime | undefined, devise: string) => string | null
  readonly NE_DIT_PAS_SCENARIO: string
  readonly lectureRegime: (regime: Regime) => string | null
  readonly NE_DIT_PAS_REGIME: string
  readonly lecturePrediction: (regime: Regime) => string | null
  readonly phraseEchantillonMince: (observations: number, minimum: number) => string
  readonly introPortefeuille: (asOf: string) => string
  readonly phraseFraicheurPositions: (updatedAt: string | null) => string
  readonly phraseFenetreReduite: (
    fenetre: Window,
    limitantes: readonly LimitingPosition[],
  ) => string | null
}
