/**
 * Les phrases que l'interface COMPOSE — DESIGN.md §8.1, §9.1 et §15, et les
 * textes de lecture validés le 2026-10-05 (`textes-lecture.md`, hors dépôt).
 *
 * Elles sont ici, et pas dans les composants, pour deux raisons : elles sont
 * testables sans rendu, et les avoir au même endroit rend visible le peu qu'il
 * y en a. Tout le reste de ce que le produit affirme est RÉDIGÉ PAR LE
 * BACKEND — observations du moteur de règles, raisons de refus, réserves,
 * libellés de période, nom de l'indice de référence, bandeau d'acceptation —
 * et s'affiche tel quel.
 *
 * ═══ LE LECTEUR PART DE ZÉRO ═══
 *
 * Il n'a jamais entendu parler de VaR, de volatilité ni de bêta. Chaque mesure
 * reçoit donc une phrase concrète — la fréquence dite en calendrier, le montant
 * en dollars à la valeur d'aujourd'hui, la période — et une ligne courte sur ce
 * que le chiffre ne dit pas. Le terme technique reste dans le libellé (§15).
 *
 * Le passé est rejoué sur la composition D'AUJOURD'HUI, d'où le conditionnel :
 * « aurait perdu ». Le portefeuille n'a pas forcément été détenu tel quel, et
 * il ne valait pas sa valeur d'aujourd'hui le jour d'une perte passée : un
 * montant « représente » une part de la valeur d'aujourd'hui, il ne dit jamais
 * ce qui a été perdu en dollars.
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
  Scenario,
  Var,
  Volatility,
  Window,
  WorstDay,
} from '../api/types'
import {
  ESPACE_FINE,
  ESPACE_INSECABLE,
  compte,
  dateEnToutesLettres,
  dateISO,
  decimal,
  lignes,
  montantArrondi,
  points,
  pointsAbsolus,
  pourcentage,
  pourcentageAbsolu,
  seances,
} from './format'

/**
 * Un nom cité entre guillemets français : « Démo ». Les espaces qui les
 * séparent du nom sont INSÉCABLES, sinon le « » » part seul en début de ligne
 * — le même défaut que le « % » que `format.ts` retient par une espace fine.
 */
export function cite(texte: string): string {
  return `«${ESPACE_INSECABLE}${texte}${ESPACE_INSECABLE}»`
}

/** La première lettre en capitale : un libellé publié placé en tête de phrase. */
export function majuscule(texte: string): string {
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

/** Ce qu'une mesure non calculée affiche quand le moteur n'a pas dit pourquoi. */
const NON_CALCULEE = 'Non calculée, sans raison publiée.'

function joursDeBourse(nombre: number): string {
  return compte(nombre, 'jour de bourse', 'jours de bourse')
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
 */
interface LectureDeNiveau {
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
  /** La phrase qui clôt la lecture de la VaR historique, s'il y en a une. */
  readonly autresJours: string | null
  /** Ce que la ligne « ne dit pas » de la VaR historique oppose au seuil. */
  readonly neDitPas: 'pire jour' | 'queue'
}

const LECTURE_CONFIANCE: Record<string, LectureDeNiveau> = {
  '0.95': {
    frequence: 'un jour de bourse sur vingt',
    calendrier: 'à peu près une fois par mois',
    complement: `19${ESPACE_INSECABLE}jours de bourse sur 20`,
    part: 'un sur vingt',
    jour: 'un jour sur vingt',
    autresJours: 'Les autres jours, il aurait perdu moins, ou gagné.',
    neDitPas: 'pire jour',
  },
  '0.99': {
    frequence: 'un jour de bourse sur cent',
    calendrier: 'deux à trois fois par an',
    complement: `99${ESPACE_INSECABLE}jours de bourse sur 100`,
    part: 'un sur cent',
    jour: 'un jour sur cent',
    autresJours: null,
    neDitPas: 'queue',
  },
}

export function lectureDuNiveau(confiance: number): LectureDeNiveau | null {
  return LECTURE_CONFIANCE[String(confiance)] ?? null
}

/** « un jour de bourse sur vingt » : la fréquence d'un niveau, ou null. */
export function frequenceLue(confiance: number): string | null {
  return lectureDuNiveau(confiance)?.frequence ?? null
}

/**
 * Un seuil qui est un GAIN (valeur négative, §9.1 règle 2) : la phrase change,
 * et ne cite AUCUN chiffre. Elle devrait sinon retourner le signe de celui qui
 * est affiché juste au-dessus d'elle. Elle ne promet pas non plus l'absence de
 * perte : les jours sous le seuil peuvent en être.
 */
function phraseDeGain(niveau: LectureDeNiveau | null, confiance: number): string {
  if (niveau === null) {
    return `Ce seuil est un gain, pas une perte, au niveau de confiance ${pourcentage(confiance, 0)}.`
  }
  return (
    `Ce seuil est un gain, pas une perte${ESPACE_INSECABLE}: environ ${niveau.complement}, ` +
    'votre portefeuille aurait fait au moins aussi bien. Les autres jours, il aurait ' +
    'gagné moins, ou perdu.'
  )
}

export const NE_DIT_PAS_GAIN = 'Un gain sur cette période ne promet rien pour la suivante.'

export const NE_DIT_PAS_REFUS =
  `Ce n'est pas l'absence de risque${ESPACE_INSECABLE}: la période est seulement trop ` +
  'courte pour le mesurer.'

// ═════════════════════════════════════════════════ Section 2 — un jour ordinaire ══

export function introJourOrdinaire(periode: string): string {
  return (
    `Combien votre portefeuille peut-il perdre en une journée${ESPACE_INSECABLE}? ` +
    `On rejoue ${periode} sur sa composition d'aujourd'hui${ESPACE_INSECABLE}: c'est le ` +
    'passé, pas une prévision.'
  )
}

/**
 * La phrase de lecture d'une VaR historique — « Ces deux dernières années,
 * environ un jour de bourse sur vingt… ».
 *
 * UNE VaR EST UN SEUIL DÉPASSÉ, PAS UNE PERTE ATTENDUE (§15) : « 1,06 % ou
 * plus ». Ce qu'elle vaut en moyenne ces jours-là est la CVaR, avec sa propre
 * phrase. `decimales` est celui du chiffre affiché au-dessus : les deux
 * écritures du même nombre sont identiques. Refusée, la VaR laisse la place à
 * la raison du moteur.
 */
export function lectureVarHistorique(
  resultat: HistoricalVar,
  decimales: number,
  devise: string,
): string {
  if (resultat.value === null) return resultat.undefined_reason ?? NON_CALCULEE
  const niveau = lectureDuNiveau(resultat.confidence)
  if (resultat.value < 0) return phraseDeGain(niveau, resultat.confidence)

  const seuil = pourcentage(resultat.value, decimales)
  const frequence =
    niveau === null
      ? `au niveau de confiance ${pourcentage(resultat.confidence, 0)}`
      : `environ ${niveau.frequence}, soit ${niveau.calendrier}`
  const phrases = [
    `${majuscule(resultat.period_label)}, ${frequence}, votre portefeuille aurait perdu ${seuil} ou plus.`,
  ]
  if (resultat.amount !== null) {
    phrases.push(
      `Sur sa valeur d'aujourd'hui, ${seuil} représente environ ${montantArrondi(resultat.amount, devise)}.`,
    )
  }
  if (niveau?.autresJours) phrases.push(niveau.autresJours)
  return phrases.join(' ')
}

/**
 * Ce que la VaR historique ne dit pas. À 95 % : que ce n'est pas un plafond,
 * preuve à l'appui — la pire séance de la fenêtre. À 99 % : qu'elle repose sur
 * très peu de jours, ceux que moyenne la CVaR du même niveau.
 */
export function neDitPasVarHistorique(
  resultat: HistoricalVar,
  pireJour: WorstDay,
  joursDansLaQueue: number | null,
): string {
  if (resultat.value === null) return NE_DIT_PAS_REFUS
  if (resultat.value < 0) return NE_DIT_PAS_GAIN
  const niveau = lectureDuNiveau(resultat.confidence)
  if (niveau?.neDitPas === 'queue' && joursDansLaQueue !== null) {
    return (
      `Ce seuil ne repose que sur ${compte(joursDansLaQueue, 'jour')}${ESPACE_INSECABLE}: ` +
      "d'une période à l'autre, il peut beaucoup changer."
    )
  }
  if (niveau?.neDitPas === 'pire jour' && pireJour.loss > 0) {
    return (
      `Ce n'est pas un plafond${ESPACE_INSECABLE}: le pire jour, le ` +
      `${dateEnToutesLettres(pireJour.date)}, il aurait perdu ${pourcentage(pireJour.loss, 2)}.`
    )
  }
  return (
    `Ce n'est pas un plafond${ESPACE_INSECABLE}: ces jours-là, la perte peut être bien ` +
    `plus forte (voir ${cite('Les pires jours')}).`
  )
}

/**
 * La phrase de lecture d'une VaR paramétrique — la même question, posée à une
 * courbe. `loi` est écrite telle quelle : « normale », « de Student ».
 */
export function lectureVarParametrique(
  resultat: Var,
  loi: 'normale' | 'de Student',
  devise: string,
): string {
  const niveau = lectureDuNiveau(resultat.confidence)
  if (resultat.value < 0) return phraseDeGain(niveau, resultat.confidence)
  const frequence =
    niveau === null
      ? `au niveau de confiance ${pourcentage(resultat.confidence, 0)}`
      : `environ ${niveau.frequence}`
  return (
    `Selon une loi ${loi} ajustée sur ${resultat.period_label}, ${frequence}, la perte ` +
    `atteindrait ou dépasserait ${pourcentage(resultat.value, 2)}, soit environ ` +
    `${montantArrondi(resultat.amount, devise)} sur la valeur d'aujourd'hui.`
  )
}

/** Une ligne pour les deux couples : le couple se lit comme une mesure (§11.5). */
export const NE_DIT_PAS_COURBES =
  `Une courbe reste une hypothèse${ESPACE_INSECABLE}: chaque chiffre vaut ce que vaut la ` +
  "forme supposée. L'écart entre les deux courbes montre combien ce choix compte."

/**
 * La phrase de lecture de la volatilité, et son repère : celle de l'indice de
 * référence, sur les mêmes séances. Sans indice, la phrase s'arrête avant.
 */
export function lectureVolatilite(indice: Volatility | null, parametres: Parameters): string {
  const base =
    "L'ampleur habituelle des variations de valeur, à la hausse comme à la baisse, " +
    'ramenée à une année. Plus le chiffre est élevé, plus la valeur bouge.'
  if (indice === null || parametres.benchmark === null) return base
  const nom = parametres.benchmark_label ?? parametres.benchmark
  const presentation =
    parametres.benchmark_description === null ? '' : `, ${parametres.benchmark_description},`
  return (
    `${base} Pour comparer${ESPACE_INSECABLE}: ${pourcentage(indice.annualised, 1)} pour ` +
    `${nom}${presentation} sur la même période.`
  )
}

export const NE_DIT_PAS_VOLATILITE =
  `Ne dit pas dans quel sens${ESPACE_INSECABLE}: une forte volatilité, ce sont aussi de ` +
  'fortes hausses.'

/** La phrase de lecture d'une CVaR : ce qu'elle MOYENNE, pas un quantile. */
export function lectureCVaR(resultat: ExpectedShortfall, devise: string): string {
  if (resultat.value === null) return resultat.undefined_reason ?? NON_CALCULEE
  const niveau = lectureDuNiveau(resultat.confidence)
  const part =
    niveau === null
      ? `au-delà du seuil à ${pourcentage(resultat.confidence, 0)}`
      : `environ ${niveau.part}`
  if (resultat.value < 0) {
    return `Même lors de ses plus mauvais jours de bourse (${part}), votre portefeuille aurait en moyenne gagné.`
  }
  const montant =
    resultat.amount === null
      ? ''
      : `, soit environ ${montantArrondi(resultat.amount, devise)} sur sa valeur d'aujourd'hui`
  return (
    `${majuscule(resultat.period_label)}, lors de ses plus mauvais jours de bourse (${part}), ` +
    `votre portefeuille aurait perdu en moyenne ${pourcentage(resultat.value, 2)}${montant}.`
  )
}

/**
 * Ce que la CVaR ne dit pas. Quand le moteur attache une réserve au chiffre —
 * en permanence à 99 % —, c'est elle qui le dit : pas de deuxième ligne.
 */
export function neDitPasCVaR(resultat: ExpectedShortfall): string | null {
  if (resultat.value === null) return NE_DIT_PAS_REFUS
  if (resultat.value < 0) return NE_DIT_PAS_GAIN
  if (resultat.caveat !== null) return null
  return `C'est une moyenne du passé${ESPACE_INSECABLE}: un prochain mauvais jour peut être plus dur.`
}

/**
 * La légende de l'histogramme des rendements (section 2) : ce qui est TRACÉ,
 * et seulement cela.
 *
 * Sous 1/(1 − α) séances, le moteur refuse la VaR historique et la CVaR d'un
 * niveau — aucune séance ne tombe dans sa queue — et l'histogramme n'en trace
 * ni le trait ni l'ombre. Une légende fixe décrirait alors des traits absents ;
 * celle-ci dit lesquels manquent, et pourquoi. `traces` et `refuses` sont les
 * niveaux de confiance publiés, triés ; `largeur` est celle des classes,
 * publiée avec l'histogramme.
 */
export function legendeHistogramme(
  traces: readonly number[],
  refuses: readonly number[],
  largeur: number,
): string {
  // « le seuil d'un jour sur vingt » ; un niveau hors de la table garde son nom
  // technique, « le quantile à 90 % ».
  const seuilDe = (confiance: number): string => {
    const niveau = lectureDuNiveau(confiance)
    return niveau === null ? `le quantile à ${pourcentage(confiance, 0)}` : `le seuil d'${niveau.jour}`
  }
  const voir = `(voir ${cite('Les pires jours')})`
  const morceaux = [
    'Chaque barre compte les jours de bourse dont la variation tombe dans une même ' +
      `tranche de ${points(largeur, 2)}${ESPACE_INSECABLE}; à gauche de zéro, les jours de baisse.`,
  ]
  const [premier] = traces
  if (traces.length === 1 && premier !== undefined) {
    const ombre =
      premier === 0.95 ? `${ESPACE_INSECABLE}; la zone ombrée, les jours au-delà ${voir}` : ''
    morceaux.push(`Le trait marque ${seuilDe(premier)}${ombre}.`)
  } else if (traces.length > 1) {
    const seuils = traces.map((confiance, rang) =>
      rang === 0 ? seuilDe(confiance) : seuilDe(confiance).replace(/^le seuil/, 'celui'),
    )
    const ombre = traces.includes(0.95)
      ? `${ESPACE_INSECABLE}; la zone ombrée, les jours au-delà du premier ${voir}`
      : ''
    morceaux.push(`Les traits marquent ${seuils.join(' et ')}${ombre}.`)
  }
  const [refuse] = refuses
  if (refuses.length === 1 && refuse !== undefined) {
    morceaux.push(
      `${majuscule(seuilDe(refuse))} n'est pas tracé${ESPACE_INSECABLE}: la période est trop ` +
        "courte pour qu'un jour y tombe.",
    )
  } else if (refuses.length > 1) {
    morceaux.push(
      `Aucun seuil n'est tracé${ESPACE_INSECABLE}: la période est trop courte pour qu'un jour y tombe.`,
    )
  }
  morceaux.push(
    `Les tranches sont les mêmes pour tout portefeuille${ESPACE_INSECABLE}: un portefeuille ` +
      "plus agité s'étale davantage.",
  )
  return morceaux.join(' ')
}

// ════════════════════════════════════════════════════ Section 3 — au pire ══

export function introAuPire(periode: string): string {
  return (
    `Quelle a été la pire chute de votre portefeuille ${periode}, et combien de temps ` +
    `a-t-il mis à s'en remettre${ESPACE_INSECABLE}? Toujours avec sa composition d'aujourd'hui.`
  )
}

/**
 * La phrase de lecture du creux maximal (section 3) : la chute, ses dates en
 * toutes lettres (§6.3), le retour au pic — ou son absence —, et ce que la
 * baisse représente sur la valeur d'aujourd'hui.
 */
export function lectureCreux(creux: Drawdown, devise: string): string {
  const periode = majuscule(creux.period_label)
  if (creux.value === 0) {
    return `${periode}, la valeur n'est jamais repassée sous un plus haut précédent.`
  }
  const retour =
    creux.recovery_date === null
      ? `Au ${dateEnToutesLettres(creux.window.end)}, il n'avait pas encore retrouvé ce plus haut.`
      : `Il aurait retrouvé ce plus haut le ${dateEnToutesLettres(creux.recovery_date)}.`
  return (
    `${periode}, la pire chute de votre portefeuille aurait été de ` +
    `${pourcentageAbsolu(creux.value, 1)}, de son plus haut du ` +
    `${dateEnToutesLettres(creux.peak_date)} à son plus bas du ` +
    `${dateEnToutesLettres(creux.trough_date)}. ${retour} Sur sa valeur d'aujourd'hui, une ` +
    `telle baisse représente environ ${montantArrondi(creux.amount, devise)}.`
  )
}

export function neDitPasCreux(creux: Drawdown): string {
  if (creux.value === 0) {
    return 'Une période sans baisse ne promet rien pour la suivante. Les crises passées sont en section 5.'
  }
  return (
    `Ce n'est que la pire baisse de ${creux.period_label}${ESPACE_INSECABLE}: une prochaine ` +
    'peut être plus forte. Les crises passées sont en section 5.'
  )
}

// ═══════════════════════════════════════════ Section 4 — qui porte le risque ══

export function chapeauLignesEffectives(n: number): string {
  if (n === 1) return 'Avec une seule ligne, tout le portefeuille bouge avec elle.'
  return (
    `Avec des montants inégaux, ${lignes(n)} ne comptent pas pour ${n}. Et côté risque, ` +
    "certaines font plus bouger le portefeuille que d'autres."
  )
}

export function lectureLignesEnCapital(n: number, effectives: number): string {
  if (n === 1) return 'Votre seule ligne pèse pour tout le portefeuille.'
  return (
    `Comptées en montants, vos ${lignes(n)} pèsent comme ` +
    `${decimal(effectives, 1)}${ESPACE_INSECABLE}lignes de même montant.`
  )
}

export const NE_DIT_PAS_CAPITAL =
  `Ne parle que des montants${ESPACE_INSECABLE}: pour les variations, voir le chiffre suivant.`

export function lectureLignesEnRisque(n: number, effectives: number): string {
  if (n === 1) return 'Elle fait seule bouger le portefeuille.'
  return (
    `Côté variations, elles se comportent comme ${decimal(effectives, 1)}${ESPACE_INSECABLE}lignes ` +
    'qui feraient chacune autant bouger le portefeuille.'
  )
}

export const NE_DIT_PAS_RISQUE =
  "Plus ce chiffre est bas, plus quelques lignes font l'essentiel des variations" +
  `${ESPACE_INSECABLE}; lesquelles, c'est plus bas.`

/**
 * La ligne qui fait le plus bouger le portefeuille, dite en une phrase.
 * `ligne` est la première de `lignesParContribution` — un TRI, pas un calcul.
 * « mais » quand sa part du risque dépasse sa part de la valeur, « et »
 * sinon : le signe de `excess_over_weight`, publié.
 */
export function lectureContribution(ligne: Contribution): string {
  const liaison = ligne.excess_over_weight > 0 ? 'mais' : 'et'
  return (
    `${ligne.ticker} représente ${pourcentage(ligne.weight, 1)} de la valeur de votre ` +
    `portefeuille, ${liaison} ${pourcentage(ligne.contribution, 1)} de ses variations` +
    `${ESPACE_INSECABLE}: c'est la ligne qui le fait le plus bouger.`
  )
}

export const NE_DIT_PAS_CONTRIBUTIONS =
  `Faire bouger ne veut pas dire faire perdre${ESPACE_INSECABLE}: une ligne peut peser lourd ` +
  'dans les variations et rapporter en crise. Le tableau montre ce que chacune a apporté ' +
  'dans chaque crise rejouée.'

/**
 * Une contribution NÉGATIVE à la variance (section 4) : elle doit se voir
 * quand le moteur la signale (`has_negative_contribution`), et elle se dit
 * sans en faire un défaut. Une ligne qui évolue à rebours du reste RÉDUIT le
 * risque ; c'est la lecture « en lignes effectives » qui en devient
 * approximative, comme le moteur de règles l'écrit.
 */
export const PHRASE_CONTRIBUTION_NEGATIVE =
  `Au moins une ligne a bougé à rebours des autres${ESPACE_INSECABLE}: elle réduit les ` +
  'variations du portefeuille. Sa barre part à gauche de zéro, et le nombre de lignes ' +
  `${cite('en risque')} n'est plus qu'une approximation.`

export const NE_DIT_PAS_CORRELATION =
  'Un lien mesuré en temps ordinaire peut se renforcer en crise (voir section 5).'

// ═══════════════════════════════════════════════ Section 5 — en crise ══

/**
 * Couverture partielle d'un scénario (§11.2) — ce que la perte ne couvre pas.
 *
 * La phrase ne dit que ce que le moteur publie : combien de lignes manquent,
 * sur combien, et que la perte porte sur les autres, renormalisées. La raison
 * de chaque exclusion est le texte du moteur, affiché à côté, tel quel.
 */
export function phraseCouverturePartielle(
  exclues: number,
  couvertes: number,
  total: number,
): string {
  return (
    `${lignes(exclues)} sur ${total} sans historique sur toute la période${ESPACE_INSECABLE}; ` +
    `la perte porte sur ${couvertes === 1 ? "l'autre" : `les ${couvertes} autres`}, renormalisées.`
  )
}

/**
 * La phrase de lecture d'une crise rejouée.
 *
 * Le « pire moment traversé » se mesure depuis le plus haut atteint PENDANT
 * l'épisode, souvent au-dessus du point de départ : la phrase le dit « sous son
 * plus haut », avec sa date, et ne lui donne pas de montant. Seul le résultat
 * de bout en bout en reçoit un, puisqu'il part de la valeur d'aujourd'hui.
 *
 * Sous le seuil de couverture, aucune perte n'est citée : le moteur de règles
 * ne donne pas de chiffre principal pour le portefeuille
 * (`coverage_sufficient`). Sans résultat, la raison du moteur s'affiche déjà :
 * la fonction rend null.
 */
export function lectureScenario(
  scenario: Scenario,
  regime: Regime | undefined,
  devise: string,
): string | null {
  const rendement = scenario.end_to_end_return
  if (rendement === null) return null
  const couverture = scenario.coverage

  if (!scenario.coverage_sufficient) {
    const seules = couverture.covered_count > 1 ? 'Seules' : 'Seule'
    const existaient = couverture.covered_count > 1 ? 'existaient' : 'existait'
    return (
      `${seules} ${lignes(couverture.covered_count)} sur ${couverture.total_count} ` +
      `${existaient} alors (${pourcentage(couverture.value_share, 0)} de la valeur)` +
      `${ESPACE_INSECABLE}: trop peu pour dire ce qu'aurait perdu l'ensemble.`
    )
  }

  const perte = rendement < 0
  const verbe = perte ? 'perdre' : 'gagner'
  const ampleur = pourcentageAbsolu(rendement, 1)
  const environ = (sur: string) =>
    scenario.end_to_end_amount === null
      ? ''
      : `, soit environ ${montantArrondi(scenario.end_to_end_amount, devise)} sur ${sur}`

  if (!couverture.is_complete) {
    const ensemble = perte
      ? "la perte de l'ensemble a pu être différente"
      : "le résultat de l'ensemble a pu être différent"
    const sujet =
      couverture.covered_count === 1
        ? 'la seule ligne qui existait alors'
        : `les ${lignes(couverture.covered_count)} qui existaient alors`
    const pronom = couverture.covered_count === 1 ? 'lui' : 'leur'
    return (
      `Rejouée sur ${sujet} (${pourcentage(couverture.value_share, 0)} de la valeur), ` +
      `cette crise ${pronom} aurait fait ${verbe} ${ampleur}` +
      `${environ(couverture.covered_count === 1 ? "sa valeur d'aujourd'hui" : "leur valeur d'aujourd'hui")}. ` +
      `Les lignes absentes n'ont pas été rejouées${ESPACE_INSECABLE}: ${ensemble}.`
    )
  }

  const morceaux = [
    `Rejouée sur votre portefeuille actuel, cette crise lui aurait fait ${verbe} ${ampleur}` +
      `${environ("sa valeur d'aujourd'hui")}.`,
  ]
  const creux = scenario.max_drawdown
  if (creux !== null) {
    morceaux.push(
      creux.value === 0
        ? "Il ne serait jamais repassé sous un plus haut pendant l'épisode."
        : `Au pire moment, il aurait été ${pourcentageAbsolu(creux.value, 1)} sous son plus ` +
            `haut, atteint le ${dateEnToutesLettres(creux.peak_date)}.`,
    )
  }
  if (regime !== undefined && regime.benchmark_return !== null) {
    const indice = majuscule(regime.benchmark_label ?? regime.benchmark)
    const sens = regime.benchmark_return < 0 ? 'perdu' : 'gagné'
    morceaux.push(`${indice}, lui, a ${sens} ${pourcentageAbsolu(regime.benchmark_return, 1)}.`)
  }
  return morceaux.join(' ')
}

export const NE_DIT_PAS_SCENARIO = 'Une prochaine crise ne ressemblera pas forcément à celle-ci.'

/** « 0,57 % » : de combien bouge le portefeuille quand l'indice bouge de 1 %. */
function reponseAUnPourcent(beta: number): string {
  return `${decimal(Math.abs(beta), 2)}${ESPACE_FINE}%`
}

function sensDu(beta: number): string {
  return beta < 0 ? 'en sens inverse' : 'dans le même sens'
}

/**
 * La sensibilité au marché, en temps ordinaire puis en crise (§11.6 :
 * appariées, jamais moyennées). Un bêta de crise estimé sur trop peu de jours
 * est donné, mais rien n'en est conclu — ni la part qui suit le marché.
 */
export function lectureRegime(regime: Regime): string | null {
  const calme = regime.calm_beta
  const crise = regime.crisis_beta
  if (regime.unavailable_reason !== null || calme === null || crise === null) return null
  const indice = regime.benchmark_label ?? regime.benchmark
  // Sans libellé publié, la phrase nomme la période d'estimation, jamais le
  // « calme » : cette période contient aussi des chutes.
  const periode = majuscule(regime.calm_period_label ?? "sur la période d'estimation")
  const sensDeCrise = (crise.beta < 0) !== (calme.beta < 0) ? ` ${sensDu(crise.beta)}` : ''
  const morceaux = [
    `${periode}, quand ${indice} bougeait de 1${ESPACE_FINE}%, votre portefeuille aurait ` +
      `bougé en moyenne de ${reponseAUnPourcent(calme.beta)} ${sensDu(calme.beta)}.`,
  ]
  if (crise.sample_too_thin) {
    morceaux.push(
      `Pendant cette crise, de ${reponseAUnPourcent(crise.beta)}${sensDeCrise}, mais sur ` +
        `${joursDeBourse(crise.observations)} seulement${ESPACE_INSECABLE}: trop peu pour en ` +
        'tirer une règle.',
    )
  } else {
    morceaux.push(
      `Pendant cette crise, de ${reponseAUnPourcent(crise.beta)}${sensDeCrise}. La part de ses ` +
        `variations qui suivait le marché serait passée de ${pourcentage(calme.r_squared, 0)} ` +
        `à ${pourcentage(crise.r_squared, 0)}.`,
    )
  }
  return morceaux.join(' ')
}

export const NE_DIT_PAS_REGIME =
  'Ce sont des tendances moyennes, pas des règles valables chaque jour.'

/**
 * Ce que son comportement de temps ordinaire laissait attendre, face à ce qu'il
 * aurait fait. La phrase ne cite PAS la variation de l'indice : multiplier le
 * bêta par elle ne redonne pas la perte attendue, parce que le moteur compose
 * les rendements, et le lecteur croirait à une erreur.
 *
 * « de plus » ou « de moins » se lit sur la perte ou sur le gain quand
 * l'attendu et le rejoué vont dans le même sens ; sinon, « de mieux » ou « de
 * moins bien ». Tous les signes lus sont publiés, `prediction_gap` compris.
 */
export function lecturePrediction(regime: Regime): string | null {
  const attendu = regime.predicted_return
  const realise = regime.portfolio_return
  const ecart = regime.prediction_gap
  if (attendu === null || realise === null || ecart === null || regime.calm_period_label === null) {
    return null
  }
  const pertePrevue = attendu < 0
  const perteRejouee = realise < 0
  const comparatif = comparatifDuRejeu(pertePrevue, perteRejouee, ecart)
  return (
    `D'après son comportement de ${regime.calm_period_label}, on se serait attendu à ` +
    `${pertePrevue ? 'une perte' : 'un gain'} d'environ ${pourcentageAbsolu(attendu, 1)}` +
    `${ESPACE_INSECABLE}; il aurait ${perteRejouee ? 'perdu' : 'gagné'} ` +
    `${pourcentageAbsolu(realise, 1)}, soit ${pointsAbsolus(ecart, 1)} ${comparatif}.`
  )
}

/**
 * Même sens — perte attendue et perte rejouée, gain et gain — : « de plus »
 * ou « de moins » se lit sur la perte ou sur le gain. Sens contraires : « de
 * mieux » ou « de moins bien ». `ecart` est le rejoué moins l'attendu, publié.
 */
function comparatifDuRejeu(pertePrevue: boolean, perteRejouee: boolean, ecart: number): string {
  if (pertePrevue !== perteRejouee) return ecart > 0 ? 'de mieux' : 'de moins bien'
  const davantage = perteRejouee ? ecart < 0 : ecart > 0
  return davantage ? 'de plus' : 'de moins'
}

/**
 * Bêta de crise sur un échantillon mince (§11.6) : le chiffre est rendu, et
 * la phrase dit sur combien de jours de bourse, contre quel seuil — CHOISI.
 */
export function phraseEchantillonMince(observations: number, minimum: number): string {
  return (
    `Sensibilité de crise estimée sur ${joursDeBourse(observations)} seulement, moins que ` +
    `les ${minimum} retenus pour une estimation stable (seuil choisi à la main)` +
    `${ESPACE_INSECABLE}: quelques jours extrêmes suffisent à la faire varier.`
  )
}

// ═══════════════════════════════════════════════ Sections 1 et bandeau ══

export function introPortefeuille(asOf: string): string {
  return (
    "Ce que contient votre portefeuille et ce qu'il vaut, au cours de clôture du " +
    `${dateEnToutesLettres(asOf)}. Toutes les sections suivantes partent de cette composition.`
  )
}

/** Fraîcheur des positions (§8.1) : l'`as_of` date les prix, pas les quantités. */
export function phraseFraicheurPositions(updatedAt: string | null): string {
  return updatedAt === null
    ? "Positions jamais modifiées depuis l'application"
    : `Positions modifiées le ${dateISO(updatedAt)}`
}

/**
 * Fenêtre réduite (§8.1).
 *
 * C'est le SEUL endroit du bandeau où le nombre de séances DEMANDÉ apparaît :
 * partout ailleurs le bandeau annonce la fenêtre obtenue, sous peine de
 * promettre une profondeur d'historique que le calcul n'a pas eue.
 *
 * Quand `limitantes` est vide, aucune ligne n'est nommée. Ce n'est pas une
 * négligence : le backend ne remplit cette liste que lorsqu'il a PROUVÉ qu'une
 * entrée en cotation tardive borne la fenêtre. Une troncature venue d'un trou
 * au milieu d'une série ne désigne personne, et mieux vaut ne nommer personne
 * que nommer à tort.
 */
export function phraseFenetreReduite(
  fenetre: Window,
  limitantes: readonly LimitingPosition[],
): string | null {
  if (fenetre.complete) return null

  const tete =
    `Fenêtre réduite à ${seances(fenetre.observations)} ` +
    `sur ${compte(fenetre.requested, 'demandée')}`

  if (limitantes.length === 0) {
    return `${tete} (historique incomplet).`
  }

  const [premiere, ...suivantes] = limitantes
  if (premiere === undefined) return `${tete} (historique incomplet).`

  const morceaux = [
    `${premiere.ticker} n'est coté que depuis le ${dateISO(premiere.first_available)}`,
    ...suivantes.map(
      (ligne) => `${ligne.ticker}, depuis le ${dateISO(ligne.first_available)}`,
    ),
  ]
  return `${tete}${ESPACE_INSECABLE}: ${morceaux.join(`${ESPACE_INSECABLE}; `)}.`
}
