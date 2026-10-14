/**
 * Le portefeuille saisi sur le site, gardé dans ce navigateur (chantier 9.6).
 *
 * Ce qui est tenu : ce qui se garde (les lignes acceptées, leur date), ce qui
 * se lit (un contenu qui ne se lit pas comme attendu est absent), ce qui se
 * passe sans stockage (la mémoire de la page), la date du jour dans le fuseau
 * du navigateur, et l'analyse gardée le temps de la page, par composition et
 * par langue.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { PublicAnalysis } from '../api/types'

type Module = typeof import('./saisi')

/** Le module neuf, sa mémoire de page vide, sur un stockage donné. */
async function saisiAvec(stockage: Storage | 'bloque'): Promise<Module> {
  if (stockage === 'bloque') {
    const refuser = () => {
      throw new Error('stockage bloqué')
    }
    vi.stubGlobal('localStorage', { getItem: refuser, setItem: refuser, removeItem: refuser })
  } else {
    vi.stubGlobal('localStorage', stockage)
  }
  vi.resetModules()
  return import('./saisi')
}

function stockageEnMemoire(depart: Record<string, string> = {}) {
  const donnees = new Map(Object.entries(depart))
  const stockage = {
    getItem: (cle: string) => donnees.get(cle) ?? null,
    setItem: (cle: string, valeur: string) => void donnees.set(cle, valeur),
    removeItem: (cle: string) => void donnees.delete(cle),
  } as unknown as Storage
  return { donnees, stockage }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
})

const LIGNES = [
  { ticker: 'AAPL', quantity: 40, cost_basis: 185.2, line: 1 },
  { ticker: 'KO', quantity: 120, cost_basis: null, line: 3 },
]

describe('ce qui se garde', () => {
  it('les lignes acceptées, sans leur numéro, et la date de l’envoi', async () => {
    const { donnees, stockage } = stockageEnMemoire()
    const saisi = await saisiAvec(stockage)
    const garde = saisi.garderLeSaisi(LIGNES, '2026-10-14')
    expect(garde).toEqual({
      positions: [
        { ticker: 'AAPL', quantity: 40, cost_basis: 185.2 },
        { ticker: 'KO', quantity: 120, cost_basis: null },
      ],
      modifie: '2026-10-14',
    })
    expect(JSON.parse(donnees.get(saisi.CLE_DU_SAISI) ?? 'null')).toEqual(garde)
    expect(saisi.lireLeSaisi()).toEqual(garde)
  })

  it('effacer le retire du stockage et de la page', async () => {
    const { donnees, stockage } = stockageEnMemoire()
    const saisi = await saisiAvec(stockage)
    saisi.garderLeSaisi(LIGNES, '2026-10-14')
    saisi.effacerLeSaisi()
    expect(donnees.has(saisi.CLE_DU_SAISI)).toBe(false)
    expect(saisi.lireLeSaisi()).toBeNull()
  })

  it('la clé est celle de la proposition, à côté des autres', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    expect(saisi.CLE_DU_SAISI).toBe('mx-risk-portefeuille-saisi')
  })
})

describe('ce qui se lit', () => {
  it('un contenu qui ne se lit pas comme attendu est traité comme absent', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    for (const brut of [
      null,
      '',
      '{',
      'null',
      '[]',
      '{"positions": [], "modifie": "14 octobre"}',
      '{"positions": [{"ticker": "", "quantity": 1, "cost_basis": null}], "modifie": "2026-10-14"}',
      '{"positions": [{"ticker": "KO", "quantity": "1", "cost_basis": null}], "modifie": "2026-10-14"}',
      '{"positions": [{"ticker": "KO", "quantity": 1}], "modifie": "2026-10-14"}',
      '{"positions": {"KO": 1}, "modifie": "2026-10-14"}',
    ]) {
      expect(saisi.lireUnSaisi(brut), String(brut)).toBeNull()
    }
  })

  it('ne garde que les trois champs d’une ligne', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    const lu = saisi.lireUnSaisi(
      '{"positions": [{"ticker": "KO", "quantity": 1, "cost_basis": null, "nom": "x"}], "modifie": "2026-10-14", "autre": 1}',
    )
    expect(lu).toEqual({ positions: [{ ticker: 'KO', quantity: 1, cost_basis: null }], modifie: '2026-10-14' })
  })

  it('un contenu fautif dans le stockage ne lève pas : rien n’est gardé', async () => {
    const { stockage } = stockageEnMemoire({ 'mx-risk-portefeuille-saisi': '{"positions": 3}' })
    const saisi = await saisiAvec(stockage)
    expect(saisi.lireLeSaisi()).toBeNull()
  })
})

describe('sans stockage', () => {
  it('le portefeuille vit dans la mémoire de la page, sans lever', async () => {
    const saisi = await saisiAvec('bloque')
    expect(saisi.stockageDisponible()).toBe(false)
    expect(saisi.lireLeSaisi()).toBeNull()
    const garde = saisi.garderLeSaisi(LIGNES, '2026-10-14')
    expect(saisi.lireLeSaisi()).toEqual(garde)
    saisi.effacerLeSaisi()
    expect(saisi.lireLeSaisi()).toBeNull()
  })

  it('un stockage qui marche se dit disponible, et l’essai ne laisse rien', async () => {
    const { donnees, stockage } = stockageEnMemoire()
    const saisi = await saisiAvec(stockage)
    expect(saisi.stockageDisponible()).toBe(true)
    expect(donnees.size).toBe(0)
  })
})

describe('la date du jour', () => {
  it('est celle du fuseau du navigateur, en ISO', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    // Le 14 octobre 2026 à 23 h 30, heure locale : toujours le 14.
    expect(saisi.aujourdHui(new Date(2026, 9, 14, 23, 30))).toBe('2026-10-14')
    expect(saisi.aujourdHui(new Date(2026, 0, 3, 0, 5))).toBe('2026-01-03')
  })

  it('date l’envoi par défaut', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    expect(saisi.garderLeSaisi(LIGNES).modifie).toBe(saisi.aujourdHui())
  })
})

describe('l’analyse, le temps de la page', () => {
  const ANALYSE = { as_of: '2026-09-09' } as unknown as PublicAnalysis

  it('se retrouve pour la même composition, dans la même langue', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    saisi.deposerLAnalyse(LIGNES, 'fr', ANALYSE)
    // Le numéro des lignes ne fait pas partie de la composition.
    const memes = LIGNES.map(({ ticker, quantity, cost_basis }) => ({ ticker, quantity, cost_basis }))
    expect(saisi.analyseDeposee(memes, 'fr')).toBe(ANALYSE)
  })

  it('pas pour une autre langue, ni pour une autre composition', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    saisi.deposerLAnalyse(LIGNES, 'fr', ANALYSE)
    expect(saisi.analyseDeposee(LIGNES, 'en')).toBeNull()
    expect(saisi.analyseDeposee([{ ...LIGNES[0]!, quantity: 41 }, LIGNES[1]!], 'fr')).toBeNull()
  })

  it('effacer le portefeuille oublie ses analyses', async () => {
    const saisi = await saisiAvec(stockageEnMemoire().stockage)
    saisi.deposerLAnalyse(LIGNES, 'fr', ANALYSE)
    saisi.effacerLeSaisi()
    expect(saisi.analyseDeposee(LIGNES, 'fr')).toBeNull()
  })
})
