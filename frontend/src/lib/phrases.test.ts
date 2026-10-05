/**
 * Les phrases du bandeau et des textes de lecture.
 *
 * Ce qui est vérifié : les formulations validées le 2026-10-05
 * (`textes-lecture.md`, hors dépôt), sur les chiffres réels du portefeuille
 * Démo au 2026-09-25 ; le fait qu'aucune lecture de niveau de confiance ne
 * soit DÉRIVÉE ; le changement de phrase quand une perte est un gain ; et les
 * variantes — fenêtre courte, mesure refusée, couverture partielle.
 *
 * Les espaces sont écrites par leurs constantes, jamais en caractères : un
 * test qui contiendrait l'espace littérale ne dirait pas laquelle il attend.
 */
import { describe, expect, it } from 'vitest'

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
import { ESPACE_FINE, ESPACE_INSECABLE } from './format'
import {
  NE_DIT_PAS_GAIN,
  NE_DIT_PAS_REFUS,
  chapeauLignesEffectives,
  cite,
  frequenceLue,
  introAuPire,
  introJourOrdinaire,
  introPortefeuille,
  lectureContribution,
  lectureCreux,
  lectureCVaR,
  lectureLignesEnCapital,
  lectureLignesEnRisque,
  lecturePrediction,
  lectureRegime,
  lectureScenario,
  lectureVarHistorique,
  lectureVarParametrique,
  lectureVolatilite,
  legendeHistogramme,
  majuscule,
  neDitPasCreux,
  neDitPasCVaR,
  neDitPasVarHistorique,
  phraseEchantillonMince,
  phraseFenetreReduite,
  phraseFraicheurPositions,
} from './phrases'

const NB = ESPACE_INSECABLE
const NF = ESPACE_FINE

const PLEINE: Window = {
  requested: 504,
  observations: 504,
  start: '2024-09-23',
  end: '2026-09-25',
  complete: true,
}

const REDUITE: Window = {
  requested: 504,
  observations: 40,
  start: '2026-07-15',
  end: '2026-09-09',
  complete: false,
}

const NEWCO: LimitingPosition = {
  ticker: 'NEWCO',
  first_available: '2026-07-14',
}

/** Le libellé que publie le moteur pour 504 séances (`engine.period_label`). */
const DEUX_ANS = `ces deux${NB}dernières années`

function varHistorique(valeur: number | null, confiance: number, montant: number | null): HistoricalVar {
  return {
    value: valeur,
    confidence: confiance,
    method: 'historique',
    detail: "quantile empirique, interpolation 'lower'",
    nu: null,
    caveat: null,
    undefined_reason: valeur === null ? `Sur 7${NB}jours de bourse, aucun ne tombe…` : null,
    window: PLEINE,
    amount: montant,
    period_label: DEUX_ANS,
  }
}

function varParametrique(valeur: number, confiance: number, montant: number): Var {
  return {
    value: valeur,
    confidence: confiance,
    method: 'paramétrique',
    detail: 'normalité, μ = 0',
    nu: null,
    caveat: null,
    window: PLEINE,
    amount: montant,
    period_label: DEUX_ANS,
  }
}

function cvar(
  valeur: number | null,
  confiance: number,
  montant: number | null,
  reserve: string | null = null,
): ExpectedShortfall {
  return {
    value: valeur,
    confidence: confiance,
    tail_observations: valeur === null ? null : 26,
    threshold: valeur === null ? null : -0.0106,
    caveat: reserve,
    undefined_reason: valeur === null ? 'Refusée.' : null,
    window: PLEINE,
    amount: montant,
    period_label: DEUX_ANS,
  }
}

const PIRE_JOUR: WorstDay = {
  date: '2025-04-04',
  loss: 0.058697760059279264,
  amount: 4935.075809631967,
  window: PLEINE,
}

// ═══════════════════════════════════════════ Lecture d'un niveau de confiance ══

describe('lecture d’un niveau de confiance', () => {
  it('traduit les niveaux que l’API publie, par une table', () => {
    expect(frequenceLue(0.95)).toBe('un jour de bourse sur vingt')
    expect(frequenceLue(0.99)).toBe('un jour de bourse sur cent')
  })

  it('n’invente pas de traduction pour un niveau inconnu', () => {
    // Une table, pas une division : 1/(1−0,85) vaudrait 6,67, et il faudrait
    // décider comment l'écrire — c'est-à-dire inventer une lecture.
    expect(frequenceLue(0.85)).toBeNull()
    expect(lectureVarHistorique(varHistorique(0.02, 0.85, 1680), 2, 'USD')).toContain(
      `au niveau de confiance 85${NF}%`,
    )
  })
})

// ═══════════════════════════════════════════════ Section 2 — VaR historique ══

describe('VaR historique : le calendrier, le montant, la période', () => {
  it('à 95 %, la phrase validée, sur les chiffres du Démo', () => {
    expect(lectureVarHistorique(varHistorique(0.010614380677865524, 0.95, 892.4152), 2, 'USD')).toBe(
      `Ces deux${NB}dernières années, environ un jour de bourse sur vingt, soit à peu près ` +
        `une fois par mois, votre portefeuille aurait perdu 1,06${NF}% ou plus. Sur sa ` +
        `valeur d'aujourd'hui, 1,06${NF}% représente environ 890${NB}USD. Les autres jours, ` +
        'il aurait perdu moins, ou gagné.',
    )
  })

  it('à 99 %, deux à trois fois par an, sans la phrase des autres jours', () => {
    expect(lectureVarHistorique(varHistorique(0.016923453504909765, 0.99, 1422.857), 2, 'USD')).toBe(
      `Ces deux${NB}dernières années, environ un jour de bourse sur cent, soit deux à trois ` +
        `fois par an, votre portefeuille aurait perdu 1,69${NF}% ou plus. Sur sa valeur ` +
        `d'aujourd'hui, 1,69${NF}% représente environ 1${NF}420${NB}USD.`,
    )
  })

  it('dit un SEUIL dépassé, jamais une perte attendue (§15)', () => {
    for (const confiance of [0.95, 0.99, 0.85]) {
      const phrase = lectureVarHistorique(varHistorique(0.0138, confiance, 1150), 2, 'USD')
      expect(phrase).toContain('ou plus')
      expect(phrase).not.toContain('attendue')
      expect(phrase).not.toContain('moyenne')
    }
  })

  it('au conditionnel : la composition d’aujourd’hui rejouée sur le passé', () => {
    const phrase = lectureVarHistorique(varHistorique(0.0106, 0.95, 890), 2, 'USD')
    expect(phrase).toContain('aurait perdu')
    expect(phrase).not.toMatch(/votre portefeuille a perdu/)
  })

  it('écrit le seuil avec les décimales du chiffre affiché au-dessus', () => {
    expect(lectureVarHistorique(varHistorique(0.013849, 0.95, 1150), 2, 'USD')).toContain(
      `1,38${NF}% ou plus`,
    )
    expect(lectureVarHistorique(varHistorique(0.013849, 0.95, 1150), 1, 'USD')).toContain(
      `1,4${NF}% ou plus`,
    )
  })

  it('reprend la période publiée, celle de la fenêtre obtenue', () => {
    const courte = { ...varHistorique(0.0106, 0.95, 890), period_label: `ces trois${NB}derniers mois` }
    expect(lectureVarHistorique(courte, 2, 'USD')).toMatch(/^Ces trois/)
  })

  it('refusée, laisse la place à la raison du moteur', () => {
    const refusee = varHistorique(null, 0.95, null)
    expect(lectureVarHistorique(refusee, 2, 'USD')).toBe(refusee.undefined_reason)
    expect(neDitPasVarHistorique(refusee, PIRE_JOUR, null)).toBe(NE_DIT_PAS_REFUS)
  })
})

describe('convention de signe (§9.1, règle 2)', () => {
  it('change la PHRASE quand le seuil est un gain', () => {
    const phrase = lectureVarHistorique(varHistorique(-0.0021, 0.95, -18), 2, 'USD')
    expect(phrase).toContain('gain')
    expect(phrase).not.toContain('aurait perdu')
  })

  it('ne retourne pas le signe du chiffre affiché, et ne promet pas l’absence de perte', () => {
    // Le chiffre s'affiche tel que le moteur l'a rendu, « −0,21 % » ; la
    // phrase n'en écrit pas une deuxième version, positive, ni de montant. Et
    // les jours sous un seuil de gain peuvent être des pertes.
    const phrase = lectureVarHistorique(varHistorique(-0.0021, 0.95, -18), 2, 'USD')
    expect(phrase).not.toContain('0,21')
    expect(phrase).not.toContain('USD')
    expect(phrase).not.toContain('ne perd pas')
    expect(phrase).toContain('ou perdu')
    expect(lectureVarHistorique(varHistorique(-0.0021, 0.85, -18), 2, 'USD')).toContain(`85${NF}%`)
    expect(neDitPasVarHistorique(varHistorique(-0.0021, 0.95, -18), PIRE_JOUR, 26)).toBe(NE_DIT_PAS_GAIN)
  })

  it('garde la phrase de perte pour une valeur nulle', () => {
    expect(lectureVarHistorique(varHistorique(0, 0.95, 0), 2, 'USD')).toContain(`0,00${NF}% ou plus`)
  })
})

describe('ce que la VaR historique ne dit pas', () => {
  it('à 95 % : ce n’est pas un plafond, la pire séance le prouve', () => {
    expect(neDitPasVarHistorique(varHistorique(0.0106, 0.95, 890), PIRE_JOUR, 26)).toBe(
      `Ce n'est pas un plafond${NB}: le pire jour, le 4${NB}avril${NB}2025, il aurait perdu ` +
        `5,87${NF}%.`,
    )
  })

  it('à 99 % : elle ne repose que sur les jours de sa queue', () => {
    expect(neDitPasVarHistorique(varHistorique(0.0169, 0.99, 1420), PIRE_JOUR, 6)).toBe(
      `Ce seuil ne repose que sur 6${NB}jours${NB}: d'une période à l'autre, il peut beaucoup changer.`,
    )
  })
})

// ════════════════════════════════════════ Section 2 — courbes, volatilité, CVaR ══

describe('VaR paramétriques : la même question, posée à une courbe', () => {
  it('loi normale et loi de Student, chacune son montant', () => {
    expect(lectureVarParametrique(varParametrique(0.013763168102816217, 0.95, 1157.15), 'normale', 'USD')).toBe(
      `Selon une loi normale ajustée sur ces deux${NB}dernières années, environ un jour de ` +
        `bourse sur vingt, la perte atteindrait ou dépasserait 1,38${NF}%, soit environ ` +
        `1${NF}160${NB}USD sur la valeur d'aujourd'hui.`,
    )
    expect(
      lectureVarParametrique(varParametrique(0.022147593904450813, 0.99, 1862.08), 'de Student', 'USD'),
    ).toContain(`Selon une loi de Student ajustée sur ces deux${NB}dernières années, environ un jour de bourse sur cent`)
  })
})

describe('volatilité et son repère', () => {
  const indice: Volatility = {
    annualised: 0.16484879985150658,
    daily: 0.0104,
    method: 'écart-type (√252)',
    caveat: null,
    window: PLEINE,
    period_label: DEUX_ANS,
  }
  const parametres: Parameters = {
    window: 504,
    benchmark: 'SPY',
    confidence_levels: [0.95, 0.99],
    benchmark_label: 'le S&P 500',
    benchmark_description: "l'indice de 500 grandes entreprises américaines",
  }

  it('compare au S&P 500, présenté à sa première apparition', () => {
    expect(lectureVolatilite(indice, parametres)).toBe(
      "L'ampleur habituelle des variations de valeur, à la hausse comme à la baisse, ramenée " +
        'à une année. Plus le chiffre est élevé, plus la valeur bouge. Pour comparer' +
        `${NB}: 16,5${NF}% pour le S&P 500, l'indice de 500 grandes entreprises américaines, ` +
        'sur la même période.',
    )
  })

  it('cite le ticker d’un indice sans nom connu, et rien sans indice', () => {
    const inconnu = { ...parametres, benchmark: 'QQQ', benchmark_label: null, benchmark_description: null }
    expect(lectureVolatilite(indice, inconnu)).toContain(`pour QQQ sur la même période.`)
    expect(lectureVolatilite(null, { ...parametres, benchmark: null })).not.toContain('Pour comparer')
  })
})

describe('CVaR : ce qu’elle MOYENNE, pas un quantile', () => {
  it('à 95 %, la phrase validée', () => {
    expect(lectureCVaR(cvar(0.016942772029536576, 0.95, 1424.48), 'USD')).toBe(
      `Ces deux${NB}dernières années, lors de ses plus mauvais jours de bourse (environ un ` +
        `sur vingt), votre portefeuille aurait perdu en moyenne 1,69${NF}%, soit environ ` +
        `1${NF}420${NB}USD sur sa valeur d'aujourd'hui.`,
    )
    expect(neDitPasCVaR(cvar(0.0169, 0.95, 1420))).toBe(
      `C'est une moyenne du passé${NB}: un prochain mauvais jour peut être plus dur.`,
    )
  })

  it('ne cite pas le seuil de la VaR : la phrase reste juste si ce seuil est un gain', () => {
    expect(lectureCVaR(cvar(0.0169, 0.95, 1420), 'USD')).not.toContain('1,06')
  })

  it('la réserve du moteur tient lieu de « ne dit pas » à 99 %', () => {
    expect(neDitPasCVaR(cvar(0.03, 0.99, 2520, 'Moyenne de 6 séances seulement…'))).toBeNull()
  })

  it('gain, refus : leurs propres phrases', () => {
    expect(lectureCVaR(cvar(-0.001, 0.95, -8), 'USD')).toBe(
      'Même lors de ses plus mauvais jours de bourse (environ un sur vingt), votre ' +
        'portefeuille aurait en moyenne gagné.',
    )
    const refusee = cvar(null, 0.99, null)
    expect(lectureCVaR(refusee, 'USD')).toBe('Refusée.')
    expect(neDitPasCVaR(refusee)).toBe(NE_DIT_PAS_REFUS)
  })
})

describe('légende de l’histogramme : ce qui est tracé, et seulement cela', () => {
  const barres =
    'Chaque barre compte les jours de bourse dont la variation tombe dans une même ' +
    `tranche de 0,25${NB}point${NB}; à gauche de zéro, les jours de baisse.`
  const tranches =
    `Les tranches sont les mêmes pour tout portefeuille${NB}: un portefeuille plus agité ` +
    "s'étale davantage."

  it('les deux niveaux tracés : les traits et la zone des pires jours', () => {
    expect(legendeHistogramme([0.95, 0.99], [], 0.0025)).toBe(
      `${barres} Les traits marquent le seuil d'un jour sur vingt et celui d'un jour sur ` +
        `cent${NB}; la zone ombrée, les jours au-delà du premier (voir ${cite('Les pires jours')}). ` +
        tranches,
    )
  })

  it('le 99 % refusé : le seul trait est nommé, l’absence est dite', () => {
    expect(legendeHistogramme([0.95], [0.99], 0.0025)).toBe(
      `${barres} Le trait marque le seuil d'un jour sur vingt${NB}; la zone ombrée, les jours ` +
        `au-delà (voir ${cite('Les pires jours')}). Le seuil d'un jour sur cent n'est pas ` +
        `tracé${NB}: la période est trop courte pour qu'un jour y tombe. ${tranches}`,
    )
  })

  it('aucun niveau tracé : ni trait ni zone annoncés', () => {
    const legende = legendeHistogramme([], [0.95, 0.99], 0.0025)
    expect(legende).toBe(
      `${barres} Aucun seuil n'est tracé${NB}: la période est trop courte pour qu'un jour y ` +
        `tombe. ${tranches}`,
    )
    expect(legende).not.toContain('marque')
    expect(legende).not.toContain('ombrée')
  })
})

// ═══════════════════════════════════════════════════ Section 3 — au pire ══

describe('le creux maximal', () => {
  const creux: Drawdown = {
    value: -0.1484731090683823,
    peak_date: '2025-02-19',
    trough_date: '2025-04-08',
    window: PLEINE,
    amount: -12483.032541688763,
    recovery_date: '2025-06-23',
    recovery_sessions: 51,
    period_label: DEUX_ANS,
  }

  it('la chute, ses dates en toutes lettres, le retour au pic, le montant', () => {
    expect(lectureCreux(creux, 'USD')).toBe(
      `Ces deux${NB}dernières années, la pire chute de votre portefeuille aurait été de ` +
        `14,8${NF}%, de son plus haut du 19${NB}février${NB}2025 à son plus bas du ` +
        `8${NB}avril${NB}2025. Il aurait retrouvé ce plus haut le 23${NB}juin${NB}2025. Sur sa ` +
        `valeur d'aujourd'hui, une telle baisse représente environ 12${NF}480${NB}USD.`,
    )
    expect(neDitPasCreux(creux)).toBe(
      `Ce n'est que la pire baisse de ces deux${NB}dernières années${NB}: une prochaine peut ` +
        'être plus forte. Les crises passées sont en section 5.',
    )
  })

  it('sans retour avant la fin de la fenêtre, il le dit', () => {
    const encours = { ...creux, recovery_date: null, recovery_sessions: null }
    expect(lectureCreux(encours, 'USD')).toContain(
      `Au 25${NB}septembre${NB}2026, il n'avait pas encore retrouvé ce plus haut.`,
    )
  })

  it('sans baisse, ni chute ni montant', () => {
    const plat = { ...creux, value: 0, amount: 0, recovery_date: null, recovery_sessions: null }
    expect(lectureCreux(plat, 'USD')).toBe(
      `Ces deux${NB}dernières années, la valeur n'est jamais repassée sous un plus haut précédent.`,
    )
  })
})

// ═══════════════════════════════════════════ Section 4 — qui porte le risque ══

describe('lignes effectives et part du risque', () => {
  it('en capital et en risque, sans affirmer des montants inégaux', () => {
    expect(lectureLignesEnCapital(6, 5.71762643068057)).toBe(
      `Comptées en montants, vos 6${NB}lignes pèsent comme 5,7${NB}lignes de même montant.`,
    )
    expect(lectureLignesEnRisque(6, 4.532514527420627)).toBe(
      `Côté variations, elles se comportent comme 4,5${NB}lignes qui feraient chacune autant ` +
        'bouger le portefeuille.',
    )
    expect(chapeauLignesEffectives(6)).toContain(`6${NB}lignes ne comptent pas pour 6`)
  })

  it('une seule ligne : ni pluriel ni comparaison', () => {
    expect(lectureLignesEnCapital(1, 1)).toBe('Votre seule ligne pèse pour tout le portefeuille.')
    expect(lectureLignesEnRisque(1, 1)).not.toContain('1,0')
    expect(chapeauLignesEffectives(1)).not.toContain('1 ligne')
  })

  it('la ligne qui fait le plus bouger : « mais » si son risque dépasse sa valeur', () => {
    const jpm: Contribution = {
      ticker: 'JPM',
      contribution: 0.3272,
      weight: 0.2448,
      excess_over_weight: 0.0824,
    }
    expect(lectureContribution(jpm)).toBe(
      `JPM représente 24,5${NF}% de la valeur de votre portefeuille, mais 32,7${NF}% de ses ` +
        `variations${NB}: c'est la ligne qui le fait le plus bouger.`,
    )
    expect(lectureContribution({ ...jpm, contribution: 0.2, excess_over_weight: -0.0448 })).toContain(
      `de votre portefeuille, et 20,0${NF}%`,
    )
  })
})

// ═══════════════════════════════════════════════════ Section 5 — en crise ══

function scenario2008(surcharges: Partial<Scenario> = {}): Scenario {
  return {
    scenario: {
      key: 'gfc_2008',
      name: 'Crise financière 2008',
      start: '2007-10-09',
      end: '2009-03-09',
      benchmark: 'SPY',
      description: 'Du sommet au creux.',
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
    end_to_end_amount: -36964.20593698781,
    coverage_sufficient: true,
    ...surcharges,
  }
}

const BETA = {
  standard_error: 0.025,
  start: '2024-09-23',
  end: '2026-09-25',
  min_observations: 60,
}

function regime2008(surcharges: Partial<Regime> = {}): Regime {
  const s = scenario2008()
  return {
    scenario: s.scenario,
    coverage: s.coverage,
    benchmark: 'SPY',
    portfolio_return: -0.4396520285739852,
    benchmark_return: -0.5520110457214169,
    amplification_ratio: 0.72,
    crisis_beta: { ...BETA, beta: 0.9523710425089222, r_squared: 0.8586766340633383, observations: 355, sample_too_thin: false },
    calm_beta: { ...BETA, beta: 0.569315879361862, r_squared: 0.49922384183274154, observations: 504, sample_too_thin: false },
    predicted_return: -0.3669165801762958,
    prediction_gap: -0.07273544839768942,
    ratio_beta_divergence: -0.23,
    systematic_share_change: 0.36,
    unavailable_reason: null,
    summary: '',
    benchmark_label: 'le S&P 500',
    calm_period_label: DEUX_ANS,
    ...surcharges,
  }
}

describe('une crise rejouée', () => {
  it('la perte au point bas du marché, le pire moment depuis le plus haut, le S&P 500', () => {
    expect(lectureScenario(scenario2008(), regime2008(), 'USD')).toBe(
      `Rejouée sur votre portefeuille actuel, cette crise lui aurait fait perdre 44,0${NF}%, ` +
        `soit environ 36${NF}960${NB}USD sur sa valeur d'aujourd'hui. Au pire moment, il ` +
        `aurait été 47,7${NF}% sous son plus haut, atteint le 26${NB}décembre${NB}2007. Le ` +
        `S&P 500, lui, a perdu 55,2${NF}%.`,
    )
  })

  it('aucun montant pour le pire moment traversé', () => {
    // 47,7 % de la valeur d'aujourd'hui ne correspondrait à aucune perte : le
    // pire moment se mesure depuis un plus haut atteint pendant l'épisode.
    const phrase = lectureScenario(scenario2008(), regime2008(), 'USD')
    expect(phrase).not.toContain(`40${NF}070`)
    expect(phrase).not.toContain(`42${NF}890`)
  })

  it('un gain se dit, pour le portefeuille comme pour l’indice', () => {
    const gain = scenario2008({ end_to_end_return: 0.597, end_to_end_amount: 50193 })
    const phrase = lectureScenario(gain, regime2008({ benchmark_return: 0.1 }), 'USD')
    expect(phrase).toContain(`lui aurait fait gagner 59,7${NF}%`)
    expect(phrase).toContain(`lui, a gagné 10,0${NF}%`)
  })

  it('couverture partielle au-dessus du seuil : la partie rejouée, sans généralité', () => {
    const partielle = scenario2008({
      coverage: {
        ...scenario2008().coverage,
        covered: ['AAPL', 'JNJ', 'JPM', 'KO', 'MSFT'],
        covered_value: 71228.85,
        value_share: 0.8472,
        is_complete: false,
        covered_count: 5,
      },
      end_to_end_amount: -31315,
    })
    expect(lectureScenario(partielle, regime2008(), 'USD')).toBe(
      `Rejouée sur les 5${NB}lignes qui existaient alors (85${NF}% de la valeur), cette crise ` +
        `leur aurait fait perdre 44,0${NF}%, soit environ 31${NF}320${NB}USD sur leur valeur ` +
        `d'aujourd'hui. Les lignes absentes n'ont pas été rejouées${NB}: la perte de l'ensemble ` +
        'a pu être différente.',
    )
  })

  it('sous le seuil de couverture, aucune perte n’est citée', () => {
    const mince = scenario2008({
      coverage: {
        ...scenario2008().coverage,
        covered: ['AAPL', 'JNJ'],
        covered_value: 27203.8,
        value_share: 0.3236,
        is_complete: false,
        covered_count: 2,
      },
      coverage_sufficient: false,
    })
    const phrase = lectureScenario(mince, regime2008(), 'USD')
    expect(phrase).toBe(
      `Seules 2${NB}lignes sur 6 existaient alors (32${NF}% de la valeur)${NB}: trop peu pour ` +
        "dire ce qu'aurait perdu l'ensemble.",
    )
    expect(phrase).not.toContain('44,0')
  })

  it('sans résultat, la raison du moteur suffit : pas de phrase', () => {
    expect(lectureScenario(scenario2008({ end_to_end_return: null, end_to_end_amount: null }), undefined, 'USD')).toBeNull()
  })
})

describe('temps ordinaire et crise, appariés (§11.6)', () => {
  it('la sensibilité en temps ordinaire puis en crise, et la part qui suit le marché', () => {
    expect(lectureRegime(regime2008())).toBe(
      `Ces deux${NB}dernières années, quand le S&P 500 bougeait de 1${NF}%, votre ` +
        `portefeuille aurait bougé en moyenne de 0,57${NF}% dans le même sens. Pendant cette ` +
        `crise, de 0,95${NF}%. La part de ses variations qui suivait le marché serait passée ` +
        `de 50${NF}% à 86${NF}%.`,
    )
  })

  it('une crise estimée sur trop peu de jours : le chiffre, et aucune conclusion', () => {
    const covid = regime2008({
      crisis_beta: { ...BETA, beta: 1.0684866904643726, r_squared: 0.98, observations: 23, sample_too_thin: true },
    })
    const phrase = lectureRegime(covid)
    expect(phrase).toContain(
      `Pendant cette crise, de 1,07${NF}%, mais sur 23${NB}jours de bourse seulement${NB}: ` +
        'trop peu pour en tirer une règle.',
    )
    expect(phrase).not.toContain('part de ses variations')
  })

  it('un bêta négatif se dit « en sens inverse »', () => {
    const inverse = regime2008({
      calm_beta: { ...BETA, beta: -0.2, r_squared: 0.04, observations: 504, sample_too_thin: false },
    })
    expect(lectureRegime(inverse)).toContain(`de 0,20${NF}% en sens inverse.`)
  })

  it('ce que son comportement laissait attendre, sans citer la variation de l’indice', () => {
    const phrase = lecturePrediction(regime2008())
    expect(phrase).toBe(
      `D'après son comportement de ces deux${NB}dernières années, on se serait attendu à une ` +
        `perte d'environ 36,7${NF}%${NB}; il aurait perdu 44,0${NF}%, soit 7,3${NB}points de plus.`,
    )
    // 0,57 × 55,2 % = 31,5 % : le lecteur croirait à une erreur, le moteur
    // composant les rendements.
    expect(phrase).not.toContain('55,2')
  })

  it('les variantes de signe', () => {
    const moinsQuePrevu = regime2008({
      predicted_return: -0.1478,
      portfolio_return: -0.0909,
      prediction_gap: 0.0569,
    })
    expect(lecturePrediction(moinsQuePrevu)).toContain(`il aurait perdu 9,1${NF}%, soit 5,7${NB}points de moins.`)
    const mieux = regime2008({ predicted_return: -0.03, portfolio_return: 0.01, prediction_gap: 0.04 })
    expect(lecturePrediction(mieux)).toContain(`il aurait gagné 1,0${NF}%, soit 4,0${NB}points de mieux.`)
    const moinsBien = regime2008({ predicted_return: 0.02, portfolio_return: -0.01, prediction_gap: -0.03 })
    expect(lecturePrediction(moinsBien)).toContain(
      `un gain d'environ 2,0${NF}%${NB}; il aurait perdu 1,0${NF}%, soit 3,0${NB}points de moins bien.`,
    )
  })

  it('la réserve d’échantillon mince, en jours de bourse, seuil choisi à la main', () => {
    expect(phraseEchantillonMince(23, 60)).toBe(
      `Sensibilité de crise estimée sur 23${NB}jours de bourse seulement, moins que les 60 ` +
        `retenus pour une estimation stable (seuil choisi à la main)${NB}: quelques jours ` +
        'extrêmes suffisent à la faire varier.',
    )
  })
})

// ═══════════════════════════════════════════════════════ Introductions ══

describe('les introductions de section', () => {
  it('disent à quelle question la section répond', () => {
    expect(introPortefeuille('2026-09-25')).toBe(
      "Ce que contient votre portefeuille et ce qu'il vaut, au cours de clôture du " +
        `25${NB}septembre${NB}2026. Toutes les sections suivantes partent de cette composition.`,
    )
    expect(introJourOrdinaire(DEUX_ANS)).toBe(
      `Combien votre portefeuille peut-il perdre en une journée${NB}? On rejoue ces ` +
        `deux${NB}dernières années sur sa composition d'aujourd'hui${NB}: c'est le passé, pas ` +
        'une prévision.',
    )
    expect(introAuPire(DEUX_ANS)).toContain(`pire chute de votre portefeuille ces deux${NB}dernières années`)
  })

  it('un libellé publié prend sa majuscule en tête de phrase, et rien d’autre', () => {
    expect(majuscule(DEUX_ANS)).toBe(`Ces deux${NB}dernières années`)
    expect(majuscule('le S&P 500')).toBe('Le S&P 500')
  })
})

// ═══════════════════════════════════════════════════════════ Bandeau ══

describe('fraîcheur des positions (§8.1)', () => {
  it('dit quand les positions ont été modifiées', () => {
    expect(phraseFraicheurPositions('2026-09-21')).toBe(
      'Positions modifiées le 2026-09-21',
    )
  })

  it('dit explicitement qu’elles ne l’ont jamais été', () => {
    // `updated_at` nul est une information, pas un blanc : l'`as_of` date les
    // prix, pas les quantités.
    expect(phraseFraicheurPositions(null)).toBe(
      "Positions jamais modifiées depuis l'application",
    )
  })
})

describe('fenêtre réduite (§8.1)', () => {
  it('ne dit rien quand la fenêtre est pleine', () => {
    expect(phraseFenetreReduite(PLEINE, [])).toBeNull()
  })

  it('nomme la ligne limitante et la date depuis laquelle elle est cotée', () => {
    expect(phraseFenetreReduite(REDUITE, [NEWCO])).toBe(
      `Fenêtre réduite à 40${NB}séances ` +
        `sur 504${NB}demandées${NB}: ` +
        "NEWCO n'est coté que depuis le 2026-07-14.",
    )
  })

  it('ne nomme personne quand le backend n’a nommé personne', () => {
    // Liste vide : la troncature vient d'un trou au milieu d'une série plutôt
    // que d'une entrée en cotation tardive. Mieux vaut ne désigner personne que
    // désigner à tort.
    const phrase = phraseFenetreReduite(REDUITE, [])
    expect(phrase).toBe(
      `Fenêtre réduite à 40${NB}séances ` +
        `sur 504${NB}demandées (historique incomplet).`,
    )
    expect(phrase).not.toContain('NEWCO')
  })

  it('énumère plusieurs lignes limitantes sans en oublier', () => {
    const phrase = phraseFenetreReduite(REDUITE, [
      NEWCO,
      { ticker: 'ACME', first_available: '2026-06-02' },
    ])
    expect(phrase).toContain('NEWCO')
    expect(phrase).toContain('ACME, depuis le 2026-06-02')
  })

  it('est le SEUL endroit du bandeau qui cite la fenêtre demandée', () => {
    // Partout ailleurs le bandeau annonce la fenêtre OBTENUE : annoncer 504
    // quand le calcul a tourné sur 40 promettrait une profondeur d'historique
    // que le rapport n'a pas.
    expect(phraseFenetreReduite(REDUITE, [NEWCO])).toContain('504')
    expect(phraseFenetreReduite(REDUITE, [NEWCO])).toContain('40')
  })
})

describe('cite', () => {
  it('relie les guillemets au nom par des espaces insécables', () => {
    expect(cite('Démo')).toBe('«\u00A0Démo\u00A0»')
  })
})
