/**
 * Les phrases de l'interface, en anglais américain (chantier 7D, session 2).
 *
 * Les mêmes noms et les mêmes signatures que `phrases.fr.ts`, les mêmes
 * décisions (`phrases.ts`), les mêmes champs publiés : une phrase anglaise ne
 * dit ni plus ni plus fort que la française, et cite les mêmes nombres.
 *
 * LE PASSÉ REJOUÉ. « Would have » pour ce que le portefeuille d'aujourd'hui
 * aurait fait ; le prétérit ou le présent seulement dans une phrase qui porte
 * elle-même son cadre (« Over the past two years, … », « In this crisis, … »)
 * ou qui suit une phrase de la même lecture qui le pose. Une période publiée
 * par le moteur (« the past two years ») s'écrit « Over … » en tête de phrase.
 *
 * Une VaR se lit « … or more », jamais « expected loss » ; un montant
 * « represents about … on its value today ». « Trading day » dans les
 * phrases ; « session » reste aux détails du calcul. Aucune contraction,
 * aucune espace avant « : », guillemets doubles (`cite(…, 'en')`).
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
import {
  ESPACE_INSECABLE,
  compte,
  dateEnToutesLettres,
  dateISOLiee,
  decimal,
  lignes as lignesFr,
  montantArrondi,
  pointsAbsolus,
  pointsEnAdjectif,
  pourcentage as pourcentageFr,
  pourcentageAbsolu,
  seances,
} from './format'
import {
  cite,
  comparatifDuRejeu,
  lectureDe,
  majuscule,
  sensChangeEnCrise,
  type Comparatif,
  type LectureDeNiveau,
  type MotsDeNiveau,
  type Phrases,
} from './phrases'

const EN = 'en' as const

/** Les écritures de `format.ts`, toujours en anglais ici. */
const pourcentage = (fraction: number, decimales: number) => pourcentageFr(fraction, decimales, EN)
const ampleur = (fraction: number, decimales: number) => pourcentageAbsolu(fraction, decimales, EN)
const lignes = (nombre: number) => lignesFr(nombre, EN)
const montant = (valeur: number, devise: string) => montantArrondi(valeur, devise, EN)
const date = (iso: string) => dateEnToutesLettres(iso, EN)

/** Ce qu'une mesure non calculée affiche quand le moteur n'a pas dit pourquoi. */
const NON_CALCULEE = 'Not computed, no reason published.'

function joursDeBourse(nombre: number): string {
  return compte(nombre, 'trading day', 'trading days', EN)
}

/** « Over the past two years » : une période publiée, en tête de phrase. */
function sur(periode: string): string {
  return `Over ${periode}`
}

// ═══════════════════════════════════════════ Lecture d'un niveau de confiance ══

const MOTS: Record<string, MotsDeNiveau> = {
  '0.95': {
    frequence: 'one trading day in twenty',
    calendrier: 'roughly once a month',
    complement: `19${ESPACE_INSECABLE}trading days out of 20`,
    part: 'one in twenty',
    jour: 'one day in twenty',
    seuil: 'the one-day-in-twenty threshold',
    autresJours: 'On the other days, it would have lost less, or gained.',
  },
  '0.99': {
    frequence: 'one trading day in a hundred',
    calendrier: 'two to three times a year',
    complement: `99${ESPACE_INSECABLE}trading days out of 100`,
    part: 'one in a hundred',
    jour: 'one day in a hundred',
    seuil: 'the one-day-in-a-hundred threshold',
  },
}

export function lectureDuNiveau(confiance: number): LectureDeNiveau | null {
  return lectureDe(MOTS, confiance)
}

/** « one trading day in twenty » : la fréquence d'un niveau, ou null. */
export function frequenceLue(confiance: number): string | null {
  return lectureDuNiveau(confiance)?.frequence ?? null
}

/** « at the 85% confidence level » : un niveau hors de la table garde son nom. */
function auNiveau(confiance: number): string {
  return `at the ${pourcentage(confiance, 0)} confidence level`
}

/**
 * Un seuil qui est un GAIN (valeur négative, §9.1 règle 2) : la phrase change,
 * et ne cite AUCUN chiffre, comme en français.
 */
function phraseDeGain(niveau: LectureDeNiveau | null, confiance: number): string {
  if (niveau === null) {
    return `This threshold is a gain, not a loss, ${auNiveau(confiance)}.`
  }
  return (
    `This threshold is a gain, not a loss: on about ${niveau.complement}, your portfolio ` +
    'would have done at least as well. On the other days, it would have gained less, or lost.'
  )
}

export const NE_DIT_PAS_GAIN = 'A gain over this period promises nothing for the next.'

export const NE_DIT_PAS_REFUS =
  'This is not an absence of risk: the period is only too short to measure it.'

// ═════════════════════════════════════════════════ Section 2 — an ordinary day ══

export function introJourOrdinaire(periode: string): string {
  return (
    "How much can your portfolio lose in a single day? Today's composition is replayed " +
    `over ${periode}: this is the past, not a forecast.`
  )
}

/**
 * La phrase de lecture d'une VaR historique. UNE VaR EST UN SEUIL DÉPASSÉ, PAS
 * UNE PERTE ATTENDUE (§15) : « 1.06% or more ».
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
      ? auNiveau(resultat.confidence)
      : `on about ${niveau.frequence}, ${niveau.calendrier}`
  const phrases = [
    `${sur(resultat.period_label)}, ${frequence}, your portfolio would have lost ${seuil} or more.`,
  ]
  if (resultat.amount !== null) {
    phrases.push(`On its value today, ${seuil} represents about ${montant(resultat.amount, devise)}.`)
  }
  if (niveau?.autresJours) phrases.push(niveau.autresJours)
  return phrases.join(' ')
}

/**
 * Ce que la VaR historique ne dit pas : à 95 %, que ce n'est pas un plafond,
 * preuve à l'appui ; à 99 %, qu'elle repose sur très peu de jours.
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
      `This threshold rests on only ${compte(joursDansLaQueue, 'day', undefined, EN)}: ` +
      'from one period to the next, it can change a lot.'
    )
  }
  if (niveau?.neDitPas === 'pire jour' && pireJour.loss > 0) {
    return (
      `This is not a ceiling: on the worst day, ${date(pireJour.date)}, it would have lost ` +
      `${pourcentage(pireJour.loss, 2)}.`
    )
  }
  return (
    'This is not a ceiling: on those days, the loss can be much larger ' +
    `(see ${cite('The worst days', EN)}).`
  )
}

/** La loi d'une VaR paramétrique, par sa clé. */
const LOIS: Record<'normale' | 'de Student', string> = {
  normale: 'a normal distribution',
  'de Student': "a Student's t-distribution",
}

/** La phrase de lecture d'une VaR paramétrique : la même question, posée à une courbe. */
export function lectureVarParametrique(
  resultat: Var,
  loi: 'normale' | 'de Student',
  devise: string,
): string {
  const niveau = lectureDuNiveau(resultat.confidence)
  if (resultat.value < 0) return phraseDeGain(niveau, resultat.confidence)
  const frequence = niveau === null ? auNiveau(resultat.confidence) : `on about ${niveau.frequence}`
  return (
    `Under ${LOIS[loi]} fitted to ${resultat.period_label}, ${frequence}, the loss would ` +
    `reach or exceed ${pourcentage(resultat.value, 2)}, about ` +
    `${montant(resultat.amount, devise)} on today's value.`
  )
}

export const NE_DIT_PAS_COURBES =
  'A curve remains an assumption: each figure is only as good as the assumed shape. The ' +
  'gap between the two curves shows how much this choice matters.'

/** La volatilité, et son repère : celle de l'indice, sur les mêmes séances. */
export function lectureVolatilite(indice: Volatility | null, parametres: Parameters): string {
  const base =
    'The usual size of the changes in value, up as well as down, scaled to one year. ' +
    'The higher the figure, the more the value moves.'
  if (indice === null || parametres.benchmark === null) return base
  const nom = parametres.benchmark_label ?? parametres.benchmark
  const presentation =
    parametres.benchmark_description === null ? '' : `, ${parametres.benchmark_description},`
  return (
    `${base} For comparison: ${pourcentage(indice.annualised, 1)} for ${nom}${presentation} ` +
    'over the same period.'
  )
}

export const NE_DIT_PAS_VOLATILITE =
  'Does not say in which direction: high volatility also means large rises.'

/** La phrase de lecture d'une CVaR : ce qu'elle MOYENNE, pas un quantile. */
export function lectureCVaR(resultat: ExpectedShortfall, devise: string): string {
  if (resultat.value === null) return resultat.undefined_reason ?? NON_CALCULEE
  const niveau = lectureDuNiveau(resultat.confidence)
  const part =
    niveau === null
      ? `beyond the threshold at ${pourcentage(resultat.confidence, 0)}`
      : `about ${niveau.part}`
  if (resultat.value < 0) {
    return `Even on its worst trading days (${part}), your portfolio would have gained on average.`
  }
  const somme =
    resultat.amount === null ? '' : `, about ${montant(resultat.amount, devise)} on its value today`
  return (
    `${sur(resultat.period_label)}, on its worst trading days (${part}), your portfolio would ` +
    `have lost ${pourcentage(resultat.value, 2)} on average${somme}.`
  )
}

/** Ce que la CVaR ne dit pas ; la réserve du moteur, quand il y en a une, le dit à sa place. */
export function neDitPasCVaR(resultat: ExpectedShortfall): string | null {
  if (resultat.value === null) return NE_DIT_PAS_REFUS
  if (resultat.value < 0) return NE_DIT_PAS_GAIN
  if (resultat.caveat !== null) return null
  return 'This is an average of the past: a future bad day can be harder.'
}

/** La légende de l'histogramme : ce qui est TRACÉ, et seulement cela. */
export function legendeHistogramme(
  traces: readonly number[],
  refuses: readonly number[],
  largeur: number,
): string {
  const seuilDe = (confiance: number): string =>
    lectureDuNiveau(confiance)?.seuil ?? `the quantile at ${pourcentage(confiance, 0)}`
  const voir = `(see ${cite('The worst days', EN)})`
  const morceaux = [
    'Each bar counts the trading days whose change falls in the same ' +
      `${pointsEnAdjectif(largeur, 2)} bin; left of zero, the down days.`,
  ]
  const [premier] = traces
  if (traces.length === 1 && premier !== undefined) {
    const ombre = premier === 0.95 ? `; the shaded area, the days beyond it ${voir}` : ''
    morceaux.push(`The line marks ${seuilDe(premier)}${ombre}.`)
  } else if (traces.length > 1) {
    const ombre = traces.includes(0.95) ? `; the shaded area, the days beyond the first ${voir}` : ''
    morceaux.push(`The lines mark ${traces.map(seuilDe).join(' and ')}${ombre}.`)
  }
  const [refuse] = refuses
  if (refuses.length === 1 && refuse !== undefined) {
    morceaux.push(
      `${majuscule(seuilDe(refuse))} is not drawn: the period is too short for a day to fall there.`,
    )
  } else if (refuses.length > 1) {
    morceaux.push('No threshold is drawn: the period is too short for a day to fall there.')
  }
  morceaux.push(
    'The bins are the same for every portfolio: a portfolio that moves more spreads out further.',
  )
  return morceaux.join(' ')
}

/** Ce que lit un lecteur d'écran à la place de l'histogramme : la conclusion, pas la forme. */
export function descriptionHistogramme(
  histogramme: ReturnHistogram,
  niveaux: readonly TailRiskLevel[],
): string {
  const seuils = niveaux.flatMap((niveau) => {
    const seuil = niveau.expected_shortfall.threshold
    const jour =
      lectureDuNiveau(niveau.confidence)?.jour ?? `the ${pourcentage(niveau.confidence, 0)} quantile`
    return seuil === null ? [] : [`${jour} at ${pourcentage(seuil, 2)} or less`]
  })
  const debut =
    `Changes over ${joursDeBourse(histogramme.window.observations)}, ` +
    `in ${pointsEnAdjectif(histogramme.bin_width, 2)} bins`
  return seuils.length === 0 ? `${debut}.` : `${debut}: ${seuils.join(', ')}.`
}

// ════════════════════════════════════════════════════ Section 3 — at worst ══

export function introAuPire(periode: string): string {
  return (
    `What would have been the worst fall of your portfolio over ${periode}, and how long ` +
    "would it have taken to recover? Still with today's composition."
  )
}

/** Le creux maximal : la chute, ses dates en toutes lettres, le retour au pic, le montant. */
export function lectureCreux(creux: Drawdown, devise: string): string {
  const periode = sur(creux.period_label)
  if (creux.value === 0) {
    return `${periode}, the value would never have fallen back below a previous high.`
  }
  const retour =
    creux.recovery_date === null
      ? `On ${date(creux.window.end)}, it would not yet have regained this high.`
      : `It would have regained this high on ${date(creux.recovery_date)}.`
  return (
    `${periode}, the worst fall of your portfolio would have been ` +
    `${ampleur(creux.value, 1)}, from its high of ${date(creux.peak_date)} to its low of ` +
    `${date(creux.trough_date)}. ${retour} On its value today, such a fall represents about ` +
    `${montant(creux.amount, devise)}.`
  )
}

export function neDitPasCreux(creux: Drawdown): string {
  if (creux.value === 0) {
    return 'A period with no fall promises nothing for the next. The past crises are in section 5.'
  }
  return (
    `This is only the worst fall of ${creux.period_label}: a future one can be deeper. ` +
    'The past crises are in section 5.'
  )
}

// ═══════════════════════════════════════════ Section 4 — what carries the risk ══

export function chapeauLignesEffectives(n: number): string {
  if (n === 1) return 'With a single holding, the whole portfolio moves with it.'
  return (
    `With unequal amounts, ${lignes(n)} do not count as ${n}. And on the risk side, some ` +
    'move the portfolio more than others.'
  )
}

export function lectureLignesEnCapital(n: number, effectives: number): string {
  if (n === 1) return 'Your only holding weighs for the whole portfolio.'
  return (
    `Counted in amounts, your ${lignes(n)} weigh like ` +
    `${decimal(effectives, 1, EN)}${ESPACE_INSECABLE}equal-sized holdings.`
  )
}

export const NE_DIT_PAS_CAPITAL = 'Speaks only of the amounts: for the fluctuations, see the next figure.'

export function lectureLignesEnRisque(n: number, effectives: number): string {
  if (n === 1) return 'It alone would have moved the portfolio.'
  return (
    `On the fluctuations side, they would have behaved like ` +
    `${decimal(effectives, 1, EN)}${ESPACE_INSECABLE}holdings each moving the portfolio as much.`
  )
}

export const NE_DIT_PAS_RISQUE =
  'The lower this figure, the more a few holdings make up most of the fluctuations; which ' +
  'ones is shown below.'

/**
 * La ligne qui fait le plus bouger le portefeuille. « but » quand sa part du
 * risque dépasse sa part de la valeur, « and » sinon : le signe de
 * `excess_over_weight`, publié. La part de la valeur est celle d'aujourd'hui ;
 * celle des variations, rejouée sur une période que la phrase ne nomme pas :
 * « would have ».
 */
export function lectureContribution(ligne: Contribution): string {
  const liaison = ligne.excess_over_weight > 0 ? 'but' : 'and'
  return (
    `${ligne.ticker} accounts for ${pourcentage(ligne.weight, 1)} of your portfolio's value, ` +
    `${liaison} would have accounted for ${pourcentage(ligne.contribution, 1)} of its ` +
    'fluctuations: it is the holding that would have moved it the most.'
  )
}

export const NE_DIT_PAS_CONTRIBUTIONS =
  'Moving the portfolio does not mean making it lose: a holding can weigh heavily in the ' +
  'fluctuations and gain in a crisis. The table shows what each one contributed in each ' +
  'replayed crisis.'

export const PHRASE_CONTRIBUTION_NEGATIVE =
  'At least one holding would have moved against the others: it would have dampened the ' +
  "portfolio's fluctuations. Its bar starts left of zero, and the number of holdings " +
  `${cite('by risk', EN)} is only an approximation.`

export const NE_DIT_PAS_CORRELATION =
  'A link measured in ordinary times can become stronger in a crisis (see section 5).'

// ═══════════════════════════════════════════════ Section 5 — in a crisis ══

/** Couverture partielle d'un scénario (§11.2) : ce que la perte ne couvre pas. */
export function phraseCouverturePartielle(
  exclues: number,
  couvertes: number,
  total: number,
): string {
  return (
    `${lignes(exclues)} out of ${total} without history over the whole period; ` +
    `the loss covers ${couvertes === 1 ? 'the other one' : `the other ${couvertes}`}, reweighted.`
  )
}

/** La phrase de lecture d'une crise rejouée (voir `phrases.fr.ts`, mêmes décisions). */
export function lectureScenario(
  scenario: Scenario,
  regime: Regime | undefined,
  devise: string,
): string | null {
  const rendement = scenario.end_to_end_return
  if (rendement === null) return null
  const couverture = scenario.coverage

  if (!scenario.coverage_sufficient) {
    return (
      `Only ${lignes(couverture.covered_count)} out of ${couverture.total_count} existed then ` +
      `(${pourcentage(couverture.value_share, 0)} of the value): too few to say what the ` +
      'whole would have lost.'
    )
  }

  const perte = rendement < 0
  const verbe = perte ? 'lose' : 'gain'
  const taille = ampleur(rendement, 1)
  const environ = (sur: string) =>
    scenario.end_to_end_amount === null
      ? ''
      : `, about ${montant(scenario.end_to_end_amount, devise)} on ${sur}`

  if (!couverture.is_complete) {
    const ensemble = perte
      ? 'the loss of the whole may have been different'
      : 'the result of the whole may have been different'
    const seule = couverture.covered_count === 1
    const sujet = seule
      ? 'the only holding that existed then'
      : `the ${lignes(couverture.covered_count)} that existed then`
    const pronom = seule ? 'it' : 'them'
    return (
      `Replayed on ${sujet} (${pourcentage(couverture.value_share, 0)} of the value), ` +
      `this crisis would have made ${pronom} ${verbe} ${taille}` +
      `${environ(seule ? 'its value today' : 'their value today')}. ` +
      `The missing holdings were not replayed: ${ensemble}.`
    )
  }

  const morceaux = [
    `Replayed on your current portfolio, this crisis would have made it ${verbe} ${taille}` +
      `${environ('its value today')}.`,
  ]
  const creux = scenario.max_drawdown
  if (creux !== null) {
    morceaux.push(
      creux.value === 0
        ? 'It would never have fallen back below a high during the episode.'
        : `At the worst point, it would have been ${ampleur(creux.value, 1)} below its high, ` +
            `reached on ${date(creux.peak_date)}.`,
    )
  }
  if (regime !== undefined && regime.benchmark_return !== null) {
    const indice = majuscule(regime.benchmark_label ?? regime.benchmark)
    const sens = regime.benchmark_return < 0 ? 'lost' : 'gained'
    morceaux.push(
      `${indice}, for its part, ${sens} ${ampleur(regime.benchmark_return, 1)} in this crisis.`,
    )
  }
  return morceaux.join(' ')
}

export const NE_DIT_PAS_SCENARIO = 'A future crisis will not necessarily resemble this one.'

/** « 0.57% » : de combien bouge le portefeuille quand l'indice bouge de 1 %. */
function reponseAUnPourcent(beta: number): string {
  return `${decimal(Math.abs(beta), 2, EN)}%`
}

function sensDu(beta: number): string {
  return beta < 0 ? 'in the opposite direction' : 'in the same direction'
}

/**
 * La sensibilité au marché, en temps ordinaire puis en crise (§11.6) : un
 * bêta de crise estimé sur trop peu de jours est donné, mais rien n'en est
 * conclu.
 */
export function lectureRegime(regime: Regime): string | null {
  const calme = regime.calm_beta
  const crise = regime.crisis_beta
  if (regime.unavailable_reason !== null || calme === null || crise === null) return null
  const indice = regime.benchmark_label ?? regime.benchmark
  // Sans libellé publié, la phrase nomme la période d'estimation, jamais le
  // « calme » : cette période contient aussi des chutes.
  const periode =
    regime.calm_period_label === null ? 'Over the estimation period' : sur(regime.calm_period_label)
  const sensDeCrise = sensChangeEnCrise(calme.beta, crise.beta) ? ` ${sensDu(crise.beta)}` : ''
  const morceaux = [
    `${periode}, when ${indice} moved by 1%, your portfolio would have moved by ` +
      `${reponseAUnPourcent(calme.beta)} on average, ${sensDu(calme.beta)}.`,
  ]
  if (crise.sample_too_thin) {
    morceaux.push(
      `During this crisis, it would have moved by ${reponseAUnPourcent(crise.beta)}${sensDeCrise}, ` +
        `but over only ${joursDeBourse(crise.observations)}: too few to draw a rule from it.`,
    )
  } else {
    morceaux.push(
      `During this crisis, it would have moved by ${reponseAUnPourcent(crise.beta)}${sensDeCrise}. ` +
        'The share of its fluctuations that followed the market would have gone from ' +
        `${pourcentage(calme.r_squared, 0)} to ${pourcentage(crise.r_squared, 0)}.`,
    )
  }
  return morceaux.join(' ')
}

export const NE_DIT_PAS_REGIME = 'These are average tendencies, not rules that hold every day.'

/** Les mots du comparatif ; la décision est `comparatifDuRejeu`, commune. */
const COMPARATIFS: Record<Comparatif, string> = {
  mieux: 'better',
  moinsBien: 'worse',
  plus: 'more',
  moins: 'less',
}

/**
 * Ce que son comportement de temps ordinaire laissait attendre, face à ce
 * qu'il aurait fait. La variation de l'indice n'est pas citée, comme en
 * français.
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
  const comparatif = COMPARATIFS[comparatifDuRejeu(pertePrevue, perteRejouee, ecart)]
  return (
    `Based on its behavior over ${regime.calm_period_label}, ${pertePrevue ? 'a loss' : 'a gain'} ` +
    `of about ${ampleur(attendu, 1)} would have been expected; it would have ` +
    `${perteRejouee ? 'lost' : 'gained'} ${ampleur(realise, 1)}, ` +
    `${pointsAbsolus(ecart, 1, EN)} ${comparatif}.`
  )
}

/** Bêta de crise sur un échantillon mince (§11.6) : le seuil est CHOISI, et la phrase le dit. */
export function phraseEchantillonMince(observations: number, minimum: number): string {
  return (
    `Crisis sensitivity estimated over only ${joursDeBourse(observations)}, fewer than the ` +
    `${minimum} required for a stable estimate (threshold chosen by hand): a few extreme ` +
    'days are enough to make it vary.'
  )
}

// ═══════════════════════════════════════════════ Section 1 and the banner ══

export function introPortefeuille(asOf: string): string {
  return (
    'What your portfolio holds and what it is worth, at the closing price of ' +
    `${date(asOf)}. All the following sections start from this composition.`
  )
}

/** Fraîcheur des positions (§8.1) : l'`as_of` date les prix, pas les quantités. */
export function phraseFraicheurPositions(updatedAt: string | null): string {
  return updatedAt === null
    ? 'Positions never changed in the app'
    : `Positions changed on ${dateISOLiee(updatedAt)}`
}

/**
 * Fenêtre réduite (§8.1) : le seul endroit du bandeau où le nombre de séances
 * DEMANDÉ apparaît. Sans ligne limitante prouvée, aucune n'est nommée.
 */
export function phraseFenetreReduite(
  fenetre: Window,
  limitantes: readonly LimitingPosition[],
): string | null {
  if (fenetre.complete) return null

  const tete =
    `Window reduced to ${seances(fenetre.observations, EN)} ` +
    `of the ${decimal(fenetre.requested, 0, EN)} requested`

  if (limitantes.length === 0) {
    return `${tete} (incomplete history).`
  }

  const [premiere, ...suivantes] = limitantes
  if (premiere === undefined) return `${tete} (incomplete history).`

  const morceaux = [
    `${premiere.ticker} is listed only since ${dateISOLiee(premiere.first_available)}`,
    ...suivantes.map((ligne) => `${ligne.ticker}, since ${dateISOLiee(ligne.first_available)}`),
  ]
  return `${tete}: ${morceaux.join('; ')}.`
}

// ═══════════════════════════════════════════════════════════ L'ensemble ══

/** Les phrases anglaises, pour le contexte de langue (`lib/langue.ts`). */
export const PHRASES_EN: Phrases = {
  lectureDuNiveau,
  frequenceLue,
  NE_DIT_PAS_GAIN,
  NE_DIT_PAS_REFUS,
  introJourOrdinaire,
  lectureVarHistorique,
  neDitPasVarHistorique,
  lectureVarParametrique,
  NE_DIT_PAS_COURBES,
  lectureVolatilite,
  NE_DIT_PAS_VOLATILITE,
  lectureCVaR,
  neDitPasCVaR,
  legendeHistogramme,
  descriptionHistogramme,
  introAuPire,
  lectureCreux,
  neDitPasCreux,
  chapeauLignesEffectives,
  lectureLignesEnCapital,
  NE_DIT_PAS_CAPITAL,
  lectureLignesEnRisque,
  NE_DIT_PAS_RISQUE,
  lectureContribution,
  NE_DIT_PAS_CONTRIBUTIONS,
  PHRASE_CONTRIBUTION_NEGATIVE,
  NE_DIT_PAS_CORRELATION,
  phraseCouverturePartielle,
  lectureScenario,
  NE_DIT_PAS_SCENARIO,
  lectureRegime,
  NE_DIT_PAS_REGIME,
  lecturePrediction,
  phraseEchantillonMince,
  introPortefeuille,
  phraseFraicheurPositions,
  phraseFenetreReduite,
}
