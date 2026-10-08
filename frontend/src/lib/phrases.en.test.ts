/**
 * Les phrases de l'interface dans les deux langues (chantier 7D, session 2).
 *
 * `phrases.test.ts` fixe le français. Ici : les deux modules ont les mêmes
 * noms ; chaque phrase est EXERCÉE dans les deux langues sur un catalogue de
 * cas (signes, niveaux hors table, refus, couverture partielle, échantillon
 * mince, fenêtre réduite), et une phrase sans cas échoue ; chaque sortie
 * anglaise diffère de la française, suit les règles de l'anglais, et cite les
 * mêmes nombres. Les phrases de référence de l'échantillon validé
 * (`anglais-proposition.md` §e.4, hors dépôt) sont fixées mot pour mot.
 *
 * Les espaces sont écrites par leurs constantes ou leurs échappements, jamais
 * en caractères.
 */
import { describe, expect, it } from 'vitest'

import type {
  Contribution,
  Drawdown,
  ExpectedShortfall,
  HistoricalVar,
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
import type { Phrases } from './phrases'
import { PHRASES_EN } from './phrases.en'
import { PHRASES_FR } from './phrases.fr'

const NB = ESPACE_INSECABLE
const PHRASES: Record<Langue, Phrases> = { fr: PHRASES_FR, en: PHRASES_EN }

// ═══════════════════════════════════════════════════════════ Les cas ══

const PLEINE: Window = { requested: 504, observations: 504, start: '2024-09-23', end: '2026-09-25', complete: true }
const REDUITE: Window = { requested: 2520, observations: 40, start: '2026-07-15', end: '2026-09-09', complete: false }

/** Ce que le moteur publie dans chaque langue : la période, l'indice. */
const PUBLIE = {
  fr: {
    periode: `ces deux${NB}dernières années`,
    indice: 'le S&P 500',
    description: "l'indice de 500 grandes entreprises américaines",
    refus: 'Refus du moteur.',
  },
  en: {
    periode: 'the past two years',
    indice: 'the S&P 500',
    description: 'an index of 500 large US companies',
    refus: 'Refused by the engine.',
  },
} as const

function cas(langue: Langue) {
  const { periode, indice, description, refus } = PUBLIE[langue]
  const varHistorique = (valeur: number | null, confiance: number, montant: number | null): HistoricalVar => ({
    value: valeur,
    confidence: confiance,
    method: 'historique',
    detail: '',
    nu: null,
    caveat: null,
    undefined_reason: valeur === null ? refus : null,
    window: PLEINE,
    amount: montant,
    period_label: periode,
  })
  const varParametrique = (valeur: number, confiance: number, montant: number): Var => ({
    value: valeur,
    confidence: confiance,
    method: 'paramétrique',
    detail: '',
    nu: null,
    caveat: null,
    window: PLEINE,
    amount: montant,
    period_label: periode,
  })
  const cvar = (valeur: number | null, confiance: number, montant: number | null, reserve: string | null = null): ExpectedShortfall => ({
    value: valeur,
    confidence: confiance,
    tail_observations: valeur === null ? null : 26,
    threshold: valeur === null ? null : -0.0106,
    caveat: reserve,
    undefined_reason: valeur === null ? refus : null,
    window: PLEINE,
    amount: montant,
    period_label: periode,
  })
  const pireJour: WorstDay = { date: '2025-04-04', loss: 0.058697760059279264, amount: 4935.07, window: PLEINE }
  const volatilite: Volatility = {
    annualised: 0.16484879985150658,
    daily: 0.0104,
    method: '',
    caveat: null,
    window: PLEINE,
    period_label: periode,
  }
  const parametres: Parameters = {
    window: 504,
    benchmark: 'SPY',
    confidence_levels: [0.95, 0.99],
    benchmark_label: indice,
    benchmark_description: description,
  }
  const creux: Drawdown = {
    value: -0.1484731090683823,
    peak_date: '2025-02-19',
    trough_date: '2025-04-08',
    window: PLEINE,
    amount: -12483.03,
    recovery_date: '2025-06-23',
    recovery_sessions: 51,
    period_label: periode,
  }
  const contribution = (ecart: number): Contribution => ({
    ticker: 'JPM',
    weight: 0.245,
    contribution: 0.245 + ecart,
    excess_over_weight: ecart,
  } as Contribution)
  const scenario = (surcharges: Partial<Scenario> = {}): Scenario => ({
    scenario: {
      key: 'gfc_2008',
      name: 'Crise financière 2008',
      start: '2007-10-09',
      end: '2009-03-09',
      benchmark: 'SPY',
      description: '',
      calendar_days: 517,
    },
    coverage: {
      covered: ['AAPL', 'JNJ', 'JPM', 'KO', 'MSFT', 'XOM'],
      excluded: [],
      covered_value: 84076.05,
      total_value: 84076.05,
      value_share: 1,
      is_complete: true,
      covered_count: 6,
      total_count: 6,
    },
    end_to_end_return: -0.4396520285739852,
    max_drawdown: {
      value: -0.47656527856992026,
      peak_date: '2007-12-26',
      trough_date: '2009-03-09',
      peak_level: 1.0705,
      trough_level: 0.5603,
    },
    contributions: [],
    observations: 356,
    unavailable_reason: null,
    summary: '',
    end_to_end_amount: -36964.2,
    coverage_sufficient: true,
    ...surcharges,
  })
  const partielle = (couvertes: number, part: number, suffisante: boolean) =>
    scenario({
      coverage: { ...scenario().coverage, is_complete: false, covered_count: couvertes, value_share: part },
      end_to_end_amount: -31315,
      coverage_sufficient: suffisante,
    })
  const beta = { standard_error: 0.025, start: '2024-09-23', end: '2026-09-25', min_observations: 60 }
  const regime = (surcharges: Partial<Regime> = {}): Regime => ({
    scenario: scenario().scenario,
    coverage: scenario().coverage,
    benchmark: 'SPY',
    portfolio_return: -0.4396520285739852,
    benchmark_return: -0.5520110457214169,
    amplification_ratio: 0.72,
    crisis_beta: { ...beta, beta: 0.9523710425089222, r_squared: 0.8586766340633383, observations: 355, sample_too_thin: false },
    calm_beta: { ...beta, beta: 0.569315879361862, r_squared: 0.49922384183274154, observations: 504, sample_too_thin: false },
    predicted_return: -0.3669165801762958,
    prediction_gap: -0.07273544839768942,
    ratio_beta_divergence: -0.23,
    systematic_share_change: 0.36,
    unavailable_reason: null,
    summary: '',
    benchmark_label: indice,
    calm_period_label: periode,
    ...surcharges,
  })
  const niveau = (confiance: number, seuil: number | null): TailRiskLevel =>
    ({ confidence: confiance, expected_shortfall: { threshold: seuil } }) as unknown as TailRiskLevel
  const histogramme = { window: PLEINE, bin_width: 0.0025 } as unknown as ReturnHistogram
  return {
    varHistorique,
    varParametrique,
    cvar,
    pireJour,
    volatilite,
    parametres,
    creux,
    contribution,
    scenario,
    partielle,
    regime,
    niveau,
    histogramme,
    periode,
  }
}

/** Chaque phrase sur ses cas, dans une langue : `nom/variante` → sortie. */
function catalogue(langue: Langue): Map<string, string | null> {
  const p = PHRASES[langue]
  const c = cas(langue)
  const sorties: [string, string | null][] = [
    ['lectureDuNiveau/0.95', JSON.stringify(p.lectureDuNiveau(0.95))],
    ['lectureDuNiveau/0.85', p.lectureDuNiveau(0.85) === null ? null : 'lu'],
    ['frequenceLue/0.99', p.frequenceLue(0.99)],
    ['NE_DIT_PAS_GAIN', p.NE_DIT_PAS_GAIN],
    ['NE_DIT_PAS_REFUS', p.NE_DIT_PAS_REFUS],
    ['introJourOrdinaire', p.introJourOrdinaire(c.periode)],
    ['lectureVarHistorique/95', p.lectureVarHistorique(c.varHistorique(0.010614380677865524, 0.95, 892.4152), 2, 'USD')],
    ['lectureVarHistorique/99', p.lectureVarHistorique(c.varHistorique(0.016923453504909765, 0.99, 1422.857), 2, 'USD')],
    ['lectureVarHistorique/85', p.lectureVarHistorique(c.varHistorique(0.02, 0.85, 1680), 2, 'USD')],
    ['lectureVarHistorique/gain', p.lectureVarHistorique(c.varHistorique(-0.0021, 0.95, -18), 2, 'USD')],
    ['lectureVarHistorique/gain85', p.lectureVarHistorique(c.varHistorique(-0.0021, 0.85, -18), 2, 'USD')],
    ['lectureVarHistorique/sansMontant', p.lectureVarHistorique(c.varHistorique(0.0106, 0.99, null), 2, 'USD')],
    ['neDitPasVarHistorique/plafond', p.neDitPasVarHistorique(c.varHistorique(0.0106, 0.95, 890), c.pireJour, 26)],
    ['neDitPasVarHistorique/queue', p.neDitPasVarHistorique(c.varHistorique(0.0169, 0.99, 1420), c.pireJour, 6)],
    ['neDitPasVarHistorique/sansPireJour', p.neDitPasVarHistorique(c.varHistorique(0.0106, 0.95, 890), { ...c.pireJour, loss: 0 }, 26)],
    ['lectureVarParametrique/normale', p.lectureVarParametrique(c.varParametrique(0.013849, 0.95, 1164.4), 'normale', 'USD')],
    ['lectureVarParametrique/student', p.lectureVarParametrique(c.varParametrique(0.022147593904450813, 0.99, 1862.08), 'de Student', 'USD')],
    ['lectureVarParametrique/85', p.lectureVarParametrique(c.varParametrique(0.0138, 0.85, 1160), 'normale', 'USD')],
    ['lectureVarParametrique/gain', p.lectureVarParametrique(c.varParametrique(-0.001, 0.95, -8), 'normale', 'USD')],
    ['NE_DIT_PAS_COURBES', p.NE_DIT_PAS_COURBES],
    ['lectureVolatilite/indice', p.lectureVolatilite(c.volatilite, c.parametres)],
    ['lectureVolatilite/sansIndice', p.lectureVolatilite(null, { ...c.parametres, benchmark: null })],
    ['lectureVolatilite/sansNom', p.lectureVolatilite(c.volatilite, { ...c.parametres, benchmark: 'QQQ', benchmark_label: null, benchmark_description: null })],
    ['NE_DIT_PAS_VOLATILITE', p.NE_DIT_PAS_VOLATILITE],
    ['lectureCVaR/95', p.lectureCVaR(c.cvar(0.016923453504909765, 0.95, 1422.86), 'USD')],
    ['lectureCVaR/85', p.lectureCVaR(c.cvar(0.02, 0.85, null), 'USD')],
    ['lectureCVaR/gain', p.lectureCVaR(c.cvar(-0.001, 0.95, -8), 'USD')],
    ['lectureCVaR/refus', p.lectureCVaR(c.cvar(null, 0.99, null), 'USD')],
    ['neDitPasCVaR/95', p.neDitPasCVaR(c.cvar(0.0169, 0.95, 1420))],
    ['neDitPasCVaR/reserve', p.neDitPasCVaR(c.cvar(0.03, 0.99, 2520, 'Réserve.'))],
    ['legendeHistogramme/deux', p.legendeHistogramme([0.95, 0.99], [], 0.0025)],
    ['legendeHistogramme/un', p.legendeHistogramme([0.95], [0.99], 0.0025)],
    ['legendeHistogramme/99', p.legendeHistogramme([0.99], [], 0.0025)],
    ['legendeHistogramme/aucun', p.legendeHistogramme([], [0.95, 0.99], 0.0025)],
    ['legendeHistogramme/hors', p.legendeHistogramme([0.9], [], 0.0025)],
    ['descriptionHistogramme/deux', p.descriptionHistogramme(c.histogramme, [c.niveau(0.95, -0.0106), c.niveau(0.99, -0.0169)])],
    ['descriptionHistogramme/aucun', p.descriptionHistogramme(c.histogramme, [c.niveau(0.95, null)])],
    ['descriptionHistogramme/hors', p.descriptionHistogramme(c.histogramme, [c.niveau(0.9, -0.012)])],
    ['introAuPire', p.introAuPire(c.periode)],
    ['lectureCreux/retour', p.lectureCreux(c.creux, 'USD')],
    ['lectureCreux/sansRetour', p.lectureCreux({ ...c.creux, recovery_date: null, recovery_sessions: null }, 'USD')],
    ['lectureCreux/zero', p.lectureCreux({ ...c.creux, value: 0 }, 'USD')],
    ['neDitPasCreux', p.neDitPasCreux(c.creux)],
    ['neDitPasCreux/zero', p.neDitPasCreux({ ...c.creux, value: 0 })],
    ['chapeauLignesEffectives/6', p.chapeauLignesEffectives(6)],
    ['chapeauLignesEffectives/1', p.chapeauLignesEffectives(1)],
    ['lectureLignesEnCapital/6', p.lectureLignesEnCapital(6, 5.72)],
    ['lectureLignesEnCapital/1', p.lectureLignesEnCapital(1, 1)],
    ['NE_DIT_PAS_CAPITAL', p.NE_DIT_PAS_CAPITAL],
    ['lectureLignesEnRisque/6', p.lectureLignesEnRisque(6, 4.53)],
    ['lectureLignesEnRisque/1', p.lectureLignesEnRisque(1, 1)],
    ['NE_DIT_PAS_RISQUE', p.NE_DIT_PAS_RISQUE],
    ['lectureContribution/plus', p.lectureContribution(c.contribution(0.082))],
    ['lectureContribution/moins', p.lectureContribution(c.contribution(-0.05))],
    ['NE_DIT_PAS_CONTRIBUTIONS', p.NE_DIT_PAS_CONTRIBUTIONS],
    ['PHRASE_CONTRIBUTION_NEGATIVE', p.PHRASE_CONTRIBUTION_NEGATIVE],
    ['NE_DIT_PAS_CORRELATION', p.NE_DIT_PAS_CORRELATION],
    ['phraseCouverturePartielle/2', p.phraseCouverturePartielle(2, 4, 6)],
    ['phraseCouverturePartielle/1', p.phraseCouverturePartielle(1, 1, 2)],
    ['lectureScenario/complet', p.lectureScenario(c.scenario(), c.regime(), 'USD')],
    ['lectureScenario/gain', p.lectureScenario(c.scenario({ end_to_end_return: 0.597, end_to_end_amount: 50193 }), c.regime({ benchmark_return: 0.1 }), 'USD')],
    ['lectureScenario/creuxNul', p.lectureScenario(c.scenario({ max_drawdown: { ...c.scenario().max_drawdown!, value: 0 } }), undefined, 'USD')],
    ['lectureScenario/partielle', p.lectureScenario(c.partielle(5, 0.8472, true), c.regime(), 'USD')],
    ['lectureScenario/partielleUne', p.lectureScenario(c.partielle(1, 0.85, true), c.regime(), 'USD')],
    ['lectureScenario/partielleGain', p.lectureScenario({ ...c.partielle(5, 0.85, true), end_to_end_return: 0.05 }, c.regime(), 'USD')],
    ['lectureScenario/insuffisante', p.lectureScenario(c.partielle(4, 0.734, false), c.regime(), 'USD')],
    ['lectureScenario/insuffisanteUne', p.lectureScenario(c.partielle(1, 0.2, false), c.regime(), 'USD')],
    ['lectureScenario/sansResultat', p.lectureScenario(c.scenario({ end_to_end_return: null }), undefined, 'USD')],
    ['NE_DIT_PAS_SCENARIO', p.NE_DIT_PAS_SCENARIO],
    ['lectureRegime/suffisant', p.lectureRegime(c.regime())],
    ['lectureRegime/mince', p.lectureRegime(c.regime({ crisis_beta: { ...c.regime().crisis_beta!, beta: 1.07, observations: 23, sample_too_thin: true } }))],
    ['lectureRegime/inverse', p.lectureRegime(c.regime({ crisis_beta: { ...c.regime().crisis_beta!, beta: -0.3 } }))],
    ['lectureRegime/sansPeriode', p.lectureRegime(c.regime({ calm_period_label: null }))],
    ['lectureRegime/indisponible', p.lectureRegime(c.regime({ unavailable_reason: 'Raison.' }))],
    ['NE_DIT_PAS_REGIME', p.NE_DIT_PAS_REGIME],
    ['lecturePrediction/plus', p.lecturePrediction(c.regime())],
    ['lecturePrediction/moins', p.lecturePrediction(c.regime({ portfolio_return: -0.2, prediction_gap: 0.1669 }))],
    ['lecturePrediction/mieux', p.lecturePrediction(c.regime({ portfolio_return: 0.05, prediction_gap: 0.4169 }))],
    ['lecturePrediction/moinsBien', p.lecturePrediction(c.regime({ predicted_return: 0.02, portfolio_return: -0.1, prediction_gap: -0.12 }))],
    ['lecturePrediction/gainPlus', p.lecturePrediction(c.regime({ predicted_return: 0.02, portfolio_return: 0.05, prediction_gap: 0.03 }))],
    ['phraseEchantillonMince', p.phraseEchantillonMince(23, 60)],
    ['introPortefeuille', p.introPortefeuille('2026-09-25')],
    ['phraseFraicheurPositions/date', p.phraseFraicheurPositions('2026-09-23')],
    ['phraseFraicheurPositions/jamais', p.phraseFraicheurPositions(null)],
    ['phraseFenetreReduite/complete', p.phraseFenetreReduite(PLEINE, [])],
    ['phraseFenetreReduite/sansLigne', p.phraseFenetreReduite(REDUITE, [])],
    ['phraseFenetreReduite/lignes', p.phraseFenetreReduite(REDUITE, [{ ticker: 'NEWCO', first_available: '2026-07-14' }, { ticker: 'ASBH', first_available: '2026-09-16' }])],
  ]
  return new Map(sorties)
}

// ═══════════════════════════════════════ Les règles de l'anglais ══

const ESPACE_AVANT_PONCTUATION = /\s[:;?!](?=\s|$)/
const ACCENT_FRANCAIS = /[àâçéèêëîïôùûüÿœæ]/i
const MOT_FRANCAIS =
  /\b(le|la|les|des|du|une|est|sont|sur|pour|avec|sans|aucun|aucune|séances?|portefeuilles?|jours? de bourse)\b/i
const CONTRACTION = /\b\w+n't\b|\b(it|that|there|what|here)'s\b|'(re|ll|ve|d)\b/i
/**
 * Ce que la garde prescriptive lit comme une consigne et qui n'en est pas
 * une, déclaré mot pour mot : « Window reduced » (glossaire) dit la fenêtre
 * obtenue, pas un geste à faire.
 */
const NON_PRESCRIPTIFS = ['Window reduced']

const PRESCRIPTIF =
  /\b(should|shall|must|ought|needs? to|needed to|ha(ve|s|d) to|recommend\w*|advis\w*|suggest\w*|consider(s|ed|ing)?|reduc\w*|trim\w*|lighten\w*|sell(s|ing)?|buy(s|ing)?|purchas\w*|strengthen\w*|favou?r\w*|prefer\w*|avoid\w*|rebalanc\w*|diversif(y|ies|ying))\b/i

function fautesAnglaises(texte: string): string[] {
  const fautes: string[] = []
  if (ESPACE_AVANT_PONCTUATION.test(texte)) fautes.push('espace avant la ponctuation')
  if (/[«»]/.test(texte)) fautes.push('guillemet français')
  if (/\u2014/.test(texte)) fautes.push('tiret cadratin')
  // Les données citées (« Crise financière 2008 », « Réserve. », « Raison. »)
  // viennent des cas, pas du texte anglais.
  const propre = texte.replace(/Crise financière 2008|Réserve\.|Raison\.|Refus du moteur\./g, '')
  if (ACCENT_FRANCAIS.test(propre)) fautes.push('accent français')
  if (MOT_FRANCAIS.test(propre)) fautes.push('mot français')
  if (CONTRACTION.test(texte)) fautes.push('contraction')
  if (PRESCRIPTIF.test(NON_PRESCRIPTIFS.reduce((t, e) => t.replaceAll(e, ''), texte))) {
    fautes.push('prescriptif')
  }
  if (/score/i.test(texte)) fautes.push('note globale')
  if (/\bexpected loss\b/i.test(texte)) fautes.push('perte attendue')
  return fautes
}

/** Les nombres d'un texte, dans une écriture commune aux deux langues. */
function nombres(texte: string, langue: Langue): string[] {
  const sansLiaison = texte.replaceAll('\u2060', '').replaceAll('\u2212', '-')
  const dates = sansLiaison.match(/\d{4}-\d{2}-\d{2}/g) ?? []
  const reste = sansLiaison.replace(/\d{4}-\d{2}-\d{2}/g, ' ')
  const motif = langue === 'fr' ? /-?\d{1,3}(?:[\u202f\u00a0]\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?/g : /-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?/g
  const trouves = (reste.match(motif) ?? []).map((n) =>
    langue === 'fr' ? n.replace(/[\u202f\u00a0]/g, '').replace(',', '.') : n.replaceAll(',', ''),
  )
  return [...dates, ...trouves].sort()
}

describe('les phrases, dans les deux langues', () => {
  const fr = catalogue('fr')
  const en = catalogue('en')

  it('les deux modules ont les mêmes noms, de même nature', () => {
    const nature = (p: Phrases) =>
      Object.entries(p)
        .map(([nom, valeur]) => `${nom}:${typeof valeur}`)
        .sort()
    expect(nature(PHRASES_EN)).toEqual(nature(PHRASES_FR))
  })

  it('chaque phrase a au moins un cas', () => {
    const exercees = new Set([...fr.keys()].map((cle) => cle.split('/')[0]))
    expect(Object.keys(PHRASES_FR).filter((nom) => !exercees.has(nom))).toEqual([])
  })

  it('chaque sortie anglaise diffère de la française : aucune traduction oubliée', () => {
    const oubliees = [...fr].filter(([cle, texte]) => texte !== null && en.get(cle) === texte)
    expect(oubliees.map(([cle, texte]) => `${cle} : ${texte}`)).toEqual([])
  })

  it('les mêmes cas rendent une phrase, ou n’en rendent aucune, dans les deux langues', () => {
    const differents = [...fr].filter(([cle, texte]) => (texte === null) !== (en.get(cle) === null))
    expect(differents.map(([cle]) => cle)).toEqual([])
  })

  it('chaque sortie anglaise suit les règles de l’anglais', () => {
    const fautes = [...en].flatMap(([cle, texte]) =>
      texte === null ? [] : fautesAnglaises(texte).map((faute) => `${cle} : ${faute} : ${texte.slice(0, 70)}`),
    )
    expect(fautes).toEqual([])
  })

  it('les mêmes nombres des deux côtés', () => {
    const ecarts = [...fr].filter(([cle, texte]) => {
      const anglais = en.get(cle)
      if (texte === null || anglais === null || anglais === undefined) return false
      return nombres(anglais, 'en').join(' ') !== nombres(texte, 'fr').join(' ')
    })
    expect(ecarts.map(([cle, texte]) => [cle, texte, en.get(cle)])).toEqual([])
  })

  it('la garde des règles voit ce qu’elle doit voir', () => {
    expect(fautesAnglaises('Threshold : 1.06%')).not.toEqual([])
    expect(fautesAnglaises("It doesn't move.")).not.toEqual([])
    expect(fautesAnglaises('You should sell JPM.')).not.toEqual([])
    expect(fautesAnglaises('the expected loss is 1.06%')).not.toEqual([])
    expect(fautesAnglaises('les jours de bourse')).not.toEqual([])
    expect(fautesAnglaises("On its value today, 1.06% represents about 890 USD.")).toEqual([])
    expect(fautesAnglaises('Window reduced to 40 sessions.')).toEqual([])
    expect(fautesAnglaises('You could reduce JPM.')).not.toEqual([])
    expect(nombres(`1\u202f420,5\u00a0USD le 2026-09-25`, 'fr')).toEqual(nombres('1,420.5 USD on 2026-09-25', 'en'))
  })
})

// ═══════════════════════════════════════ Les phrases de référence (§e.4) ══

describe('les phrases anglaises de référence', () => {
  const p = PHRASES_EN
  const c = cas('en')

  it('VaR historique à 95 % et à 99 %', () => {
    expect(p.lectureVarHistorique(c.varHistorique(0.010614380677865524, 0.95, 892.4152), 2, 'USD')).toBe(
      'Over the past two years, on about one trading day in twenty, roughly once a month, your ' +
        'portfolio would have lost 1.06% or more. On its value today, 1.06% represents about ' +
        `890${NB}USD. On the other days, it would have lost less, or gained.`,
    )
    expect(p.lectureVarHistorique(c.varHistorique(0.016923453504909765, 0.99, 1422.857), 2, 'USD')).toBe(
      'Over the past two years, on about one trading day in a hundred, two to three times a ' +
        'year, your portfolio would have lost 1.69% or more. On its value today, 1.69% ' +
        `represents about 1,420${NB}USD.`,
    )
  })

  it('ce qu’elle ne dit pas : le pire jour, la queue', () => {
    expect(p.neDitPasVarHistorique(c.varHistorique(0.0106, 0.95, 890), c.pireJour, 26)).toBe(
      `This is not a ceiling: on the worst day, April${NB}4,${NB}2025, it would have lost 5.87%.`,
    )
    expect(p.neDitPasVarHistorique(c.varHistorique(0.0169, 0.99, 1420), c.pireJour, 6)).toBe(
      `This threshold rests on only 6${NB}days: from one period to the next, it can change a lot.`,
    )
  })

  it('le seuil qui est un gain, le refus', () => {
    expect(p.lectureVarHistorique(c.varHistorique(-0.0021, 0.95, -18), 2, 'USD')).toBe(
      `This threshold is a gain, not a loss: on about 19${NB}trading days out of 20, your ` +
        'portfolio would have done at least as well. On the other days, it would have gained ' +
        'less, or lost.',
    )
    expect(p.NE_DIT_PAS_GAIN).toBe('A gain over this period promises nothing for the next.')
    expect(p.NE_DIT_PAS_REFUS).toBe(
      'This is not an absence of risk: the period is only too short to measure it.',
    )
  })

  it('la VaR paramétrique, la volatilité, la CVaR', () => {
    expect(p.lectureVarParametrique(c.varParametrique(0.013849, 0.95, 1164.4), 'normale', 'USD')).toBe(
      'Under a normal distribution fitted to the past two years, on about one trading day in ' +
        `twenty, the loss would reach or exceed 1.38%, about 1,160${NB}USD on today's value.`,
    )
    expect(p.lectureVolatilite(c.volatilite, c.parametres)).toBe(
      'The usual size of the changes in value, up as well as down, scaled to one year. The ' +
        'higher the figure, the more the value moves. For comparison: 16.5% for the S&P 500, ' +
        'an index of 500 large US companies, over the same period.',
    )
    expect(p.lectureCVaR(c.cvar(0.016923453504909765, 0.95, 1422.86), 'USD')).toBe(
      'Over the past two years, on its worst trading days (about one in twenty), your ' +
        `portfolio would have lost 1.69% on average, about 1,420${NB}USD on its value today.`,
    )
  })

  it('la légende et la description de l’histogramme', () => {
    expect(p.legendeHistogramme([0.95, 0.99], [], 0.0025)).toBe(
      'Each bar counts the trading days whose change falls in the same bin of ' +
        `0.25${NB}points; left of zero, the down days. The lines mark the one-day-in-twenty ` +
        'threshold and the one-day-in-a-hundred threshold; the shaded area, the days beyond ' +
        'the first (see “The worst days”). The bins are the same for every portfolio: ' +
        'a portfolio that moves more spreads out further.',
    )
    expect(p.descriptionHistogramme(c.histogramme, [c.niveau(0.95, -0.0106), c.niveau(0.99, -0.0169)])).toBe(
      `Changes over 504${NB}trading days, in bins of 0.25${NB}points: one day in twenty at ` +
        '\u22121.06% or less, one day in a hundred at \u22121.69% or less.',
    )
  })

  it('une crise rejouée, et la sensibilité au marché', () => {
    expect(p.lectureScenario(c.scenario(), c.regime(), 'USD')).toBe(
      'Replayed on your current portfolio, this crisis would have made it lose 44.0%, about ' +
        `36,960${NB}USD on its value today. At the worst point, it would have been 47.7% below ` +
        `its high, reached on December${NB}26,${NB}2007. The S&P 500, for its part, lost ` +
        '55.2% in this crisis.',
    )
    expect(p.lectureRegime(c.regime())).toBe(
      'Over the past two years, when the S&P 500 moved by 1%, your portfolio would have moved ' +
        'by 0.57% on average, in the same direction. During this crisis, it would have moved ' +
        'by 0.95%. The share of its fluctuations that followed the market would have gone ' +
        'from 50% to 86%.',
    )
    expect(p.lecturePrediction(c.regime())).toBe(
      'Based on its behavior over the past two years, a loss of about 36.7% would have been ' +
        `expected; it would have lost 44.0%, 7.3${NB}points more.`,
    )
  })

  it('le bandeau : fraîcheur et fenêtre réduite', () => {
    expect(p.phraseFraicheurPositions(null)).toBe('Positions never changed in the app')
    expect(p.phraseFenetreReduite(REDUITE, [{ ticker: 'NEWCO', first_available: '2026-07-14' }])).toBe(
      `Window reduced to 40${NB}sessions of the 2,520 requested: NEWCO is listed only since ` +
        '2026-07-14.',
    )
  })
})
