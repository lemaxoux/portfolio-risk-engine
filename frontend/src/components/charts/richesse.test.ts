/**
 * La courbe de richesse trace les points publiés, et le creux qu'elle ombre
 * est celui que `risk.drawdown` publie.
 */
import { describe, expect, it } from 'vitest'

import type { Drawdown, Point } from '../../api/types'
import type { Couleurs } from './couleurs'
import { optionsRichesse, pointA, pointsDuCreux } from './richesse'

const COULEURS = new Proxy({} as Couleurs, { get: (_, cle) => `couleur-${String(cle)}` })

// Le portefeuille baisse DÈS la première séance : le pic est le point de
// départ à 1,0, la séance qui précède le premier rendement.
const RICHESSE: Point[] = [
  { date: '2026-01-02', value: 1.0 },
  { date: '2026-01-05', value: 0.95 },
  { date: '2026-01-06', value: 0.9 },
  { date: '2026-01-07', value: 0.97 },
  { date: '2026-01-08', value: 1.02 },
]

const CREUX: Drawdown = {
  value: -0.1,
  peak_date: '2026-01-02',
  trough_date: '2026-01-06',
  window: { requested: 504, observations: 4, start: '2026-01-05', end: '2026-01-08', complete: false },
  amount: -8400,
  recovery_date: '2026-01-08',
  recovery_sessions: 2,
  period_label: 'ces quatre derniers jours de bourse',
}

interface MarqueInspectee {
  data: unknown
  ariaDescription?: string
  channels: Record<string, { value: unknown } | undefined>
}

function marques(): MarqueInspectee[] {
  const options = optionsRichesse(
    { richesse: RICHESSE, creux: CREUX },
    { couleurs: COULEURS, largeur: 700 },
  )
  return (options.marks ?? []) as unknown as MarqueInspectee[]
}

function marque(description: string): MarqueInspectee {
  const trouvee = marques().find((m) => m.ariaDescription === description)
  if (trouvee === undefined) throw new Error(`marque « ${description} » absente`)
  return trouvee
}

describe('la courbe publiée, point de départ compris', () => {
  it('trace chaque point publié, dans l’ordre, le point à 1,0 en tête', () => {
    const courbe = marque('courbe de richesse').data as { iso: string; value: number }[]
    expect(courbe.map((p) => p.iso)).toEqual(RICHESSE.map((p) => p.date))
    expect(courbe[0]?.value).toBe(1.0)
  })
})

describe('le creux ombré est celui publié', () => {
  it('ombre exactement les points du pic au creux, bornes incluses', () => {
    expect(pointsDuCreux(RICHESSE, CREUX).map((p) => p.date)).toEqual([
      '2026-01-02',
      '2026-01-05',
      '2026-01-06',
    ])
    const zone = marque('creux maximal').data as { iso: string }[]
    expect(zone.map((p) => p.iso)).toEqual(['2026-01-02', '2026-01-05', '2026-01-06'])
  })

  it('le haut de l’aire est le niveau publié au pic, lu et non calculé', () => {
    expect(marque('creux maximal').channels.y1?.value).toBe(1.0)
  })

  it('refuse une date absente de la courbe plutôt que d’inventer un point', () => {
    expect(() => pointA(RICHESSE, '2026-01-03')).toThrow('2026-01-03')
  })
})
