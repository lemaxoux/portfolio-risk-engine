/**
 * L'histogramme dessine EXACTEMENT les classes reçues du moteur.
 *
 * Vérifié sur les marques Plot elles-mêmes, sans DOM : la marque des barres
 * porte le tableau `bins` reçu — le même objet, pas une copie retravaillée —,
 * lit `lower`, `upper` et `count` tels quels, et n'a aucune transformation
 * (ni `binX`, ni empilement). Le rendu réel a été contrôlé dans le navigateur :
 * autant de rectangles que de classes publiées.
 */
import * as Plot from '@observablehq/plot'
import { describe, expect, it } from 'vitest'

import type { ReturnHistogram, TailRiskLevel } from '../../api/types'
import { ESPACE_FINE, ESPACE_INSECABLE, SIGNE_MOINS } from '../../lib/format'
import type { Couleurs } from './couleurs'
import { graduationsDeRendement, optionsHistogramme, texteDeClasse } from './histogramme'

const COULEURS = new Proxy({} as Couleurs, { get: (_, cle) => `couleur-${String(cle)}` })

const FENETRE = {
  requested: 504,
  observations: 6,
  start: '2026-09-01',
  end: '2026-09-09',
  complete: false,
}

const HISTOGRAMME: ReturnHistogram = {
  bin_width: 0.0025,
  closed: 'left',
  window: FENETRE,
  bins: [
    { lower: -0.005, upper: -0.0025, count: 1 },
    { lower: -0.0025, upper: 0, count: 2 },
    { lower: 0, upper: 0.0025, count: 3 },
  ],
}

function niveau(confiance: number, var_: number, seuil: number, queue: number): TailRiskLevel {
  const vr = {
    value: var_,
    confidence: confiance,
    method: 'historique',
    detail: '',
    nu: null,
    caveat: null,
    window: FENETRE,
    amount: 1000,
    period_label: 'ces deux dernières années',
  }
  const historique = { ...vr, undefined_reason: null }
  return {
    confidence: confiance,
    historical_var: historique,
    parametric_var: vr,
    monte_carlo_var: null,
    student_parametric_var: null,
    student_monte_carlo_var: null,
    expected_shortfall: {
      value: var_,
      confidence: confiance,
      tail_observations: queue,
      threshold: seuil,
      caveat: null,
      undefined_reason: null,
      window: FENETRE,
      amount: 1000,
      period_label: 'ces deux dernières années',
    },
  }
}

/** Un niveau que le moteur a refusé : VaR historique et CVaR sans valeur. */
function niveauRefuse(confiance: number): TailRiskLevel {
  const base = niveau(confiance, 0.004, -0.004, 1)
  const raison = 'Sur 6 séances, aucune ne tombe dans la queue.'
  return {
    ...base,
    historical_var: { ...base.historical_var, value: null, undefined_reason: raison },
    expected_shortfall: {
      ...base.expected_shortfall,
      value: null,
      threshold: null,
      tail_observations: null,
      undefined_reason: raison,
    },
  }
}

const NIVEAUX = [niveau(0.95, 0.004, -0.004, 2), niveau(0.99, 0.0049, -0.0049, 1)]

interface MarqueInspectee {
  data: unknown
  ariaDescription?: string
  transform?: unknown
  channels: Record<string, { value: unknown } | undefined>
}

function marques(): MarqueInspectee[] {
  const options = optionsHistogramme(
    { histogramme: HISTOGRAMME, niveaux: NIVEAUX },
    { couleurs: COULEURS, largeur: 700 },
  )
  return (options.marks ?? []) as unknown as MarqueInspectee[]
}

function barres(): MarqueInspectee {
  const trouvee = marques().find((marque) => marque.data === HISTOGRAMME.bins)
  if (trouvee === undefined) throw new Error('aucune marque ne porte les classes reçues')
  return trouvee
}

describe('les barres sont les classes publiées', () => {
  it('une marque porte le tableau reçu, le même objet', () => {
    expect(barres().data).toBe(HISTOGRAMME.bins)
  })

  it('lit les bornes et le compte tels quels, sans transformation', () => {
    const { channels, transform } = barres()
    expect(channels.x1?.value).toBe('lower')
    expect(channels.x2?.value).toBe('upper')
    expect(channels.y1?.value).toBe(0)
    expect(channels.y2?.value).toBe('count')
    // Pas de `binX` ni d'empilement : Plot ne redécoupe ni ne recompte rien.
    expect(transform).toBeUndefined()
  })

  it('aucune marque ne recompte les rendements', () => {
    for (const marque of marques()) expect(marque.transform).toBeUndefined()
  })

  it('témoin : une marque qui redécoupe porte bien une transformation', () => {
    // Sans ce témoin, l'assertion ci-dessus pourrait être vraie de toute
    // marque, y compris d'un `binX` — et ne rien prouver.
    const redecoupee = Plot.rectY(
      [0.001, 0.002],
      Plot.binX({ y: 'count' }, { x: (v: number) => v }),
    ) as unknown as MarqueInspectee
    expect(redecoupee.transform).toBeDefined()
  })
})

describe('quantiles et queue', () => {
  it('place les traits sur les quantiles publiés en convention de rendement', () => {
    // `threshold` est publié par le moteur : aucun signe n'est retourné ici.
    const traits = marques()
      .map((marque) => marque.data)
      .filter((data): data is number[] => Array.isArray(data) && typeof data[0] === 'number')
      .flat()
    expect(traits).toEqual(expect.arrayContaining([-0.004, -0.0049, 0]))
  })

  it('un niveau refusé n’a ni trait ni étiquette', () => {
    const options = optionsHistogramme(
      { histogramme: HISTOGRAMME, niveaux: [niveau(0.95, 0.004, -0.004, 2), niveauRefuse(0.99)] },
      { couleurs: COULEURS, largeur: 700 },
    )
    const traits = ((options.marks ?? []) as unknown as MarqueInspectee[])
      .map((marque) => marque.data)
      .filter((data): data is unknown[] => Array.isArray(data) && data.length === 1)
      .flat()
    // Le trait de 95 % et l'axe zéro ; aucun pour 99 %, ni nul ni ailleurs.
    expect(traits.filter((x) => typeof x === 'number')).toEqual(
      expect.arrayContaining([-0.004, 0]),
    )
    expect(traits).not.toContain(null)
  })

  it('une queue à 95 % refusée n’est pas ombrée', () => {
    const options = optionsHistogramme(
      { histogramme: HISTOGRAMME, niveaux: [niveauRefuse(0.95), niveauRefuse(0.99)] },
      { couleurs: COULEURS, largeur: 700 },
    )
    const descriptions = ((options.marks ?? []) as unknown as MarqueInspectee[]).map(
      (marque) => marque.ariaDescription,
    )
    expect(descriptions).not.toContain('queue de la CVaR à 95 %')
  })

  it('l’axe des rendements contient toujours zéro', () => {
    const options = optionsHistogramme(
      { histogramme: HISTOGRAMME, niveaux: NIVEAUX },
      { couleurs: COULEURS, largeur: 700 },
    )
    const domaine = (options.x as Plot.ScaleOptions).domain as number[]
    expect(domaine[0]).toBeLessThanOrEqual(0)
    expect(domaine[1]).toBeGreaterThanOrEqual(0)
    expect(graduationsDeRendement(-0.059, 0.072, 390)).toContain(0)
    expect(graduationsDeRendement(-0.059, 0.072, 1000)).toContain(0)
  })
})

describe('survol d’une barre', () => {
  it('dit son compte exact et ses bornes, écrits par lib/format', () => {
    expect(texteDeClasse({ lower: -0.0125, upper: -0.01, count: 12 })).toBe(
      `12${ESPACE_INSECABLE}séances\n` +
        `de ${SIGNE_MOINS}1,25${ESPACE_FINE}% inclus à ${SIGNE_MOINS}1,00${ESPACE_FINE}% exclu`,
    )
  })
})
