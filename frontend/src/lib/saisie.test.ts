import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import type { Position } from '../api/types'
import {
  ecrireNombreSaisi,
  empreinteDesLignes,
  lignesDepuisPositions,
  ligneVide,
  lireNombreSaisi,
  preparerEnvoi,
  rangerRefus,
  type LigneSaisie,
} from './saisie'

/** La liste de cas que `tests/test_nombres_saisis.py` fait lire au lecteur CSV. */
const CAS = JSON.parse(
  readFileSync(fileURLToPath(new URL('./nombres-saisis.json', import.meta.url)), 'utf-8'),
) as { acceptes: [string, number][]; refuses: string[] }

describe('lireNombreSaisi — les mêmes entrées que le lecteur CSV', () => {
  it('lit la liste partagée (témoin : elle n’est pas vide)', () => {
    expect(CAS.acceptes.length).toBeGreaterThanOrEqual(10)
    expect(CAS.refuses.length).toBeGreaterThanOrEqual(10)
  })

  it.each(CAS.acceptes)('accepte %j', (texte, attendu) => {
    expect(lireNombreSaisi(texte)).toBe(attendu)
  })

  it.each(CAS.refuses.map((texte) => [texte]))('refuse %j', (texte) => {
    expect(lireNombreSaisi(texte)).toBeNull()
  })
})

function ligne(ticker: string, quantite: string, prixRevient = ''): LigneSaisie {
  return { ...ligneVide(), ticker, quantite, prixRevient }
}

describe('aller-retour : positions stockées → tableau → envoi', () => {
  // Ce qu'un import CSV « AAPL;40;185,20 » laisse en base, puis ce que la
  // liste rend. Enregistrer le tableau sans y toucher doit renvoyer les
  // mêmes nombres, prix de revient compris.
  const stockees: Position[] = [
    { ticker: 'AAPL', quantity: 40, cost_basis: 185.2 },
    { ticker: 'JPM', quantity: 12.5, cost_basis: 0.1 },
    { ticker: 'KO', quantity: 1250, cost_basis: 1234.5678 },
    { ticker: 'MSFT', quantity: 25, cost_basis: null },
  ]

  it('le prix de revient survit, sans arrondi ni perte', () => {
    const { positions, refus } = preparerEnvoi(lignesDepuisPositions(stockees))
    expect(refus).toEqual([])
    expect(positions.map(({ ticker, quantity, cost_basis }) => ({ ticker, quantity, cost_basis }))).toEqual(
      stockees,
    )
  })

  it('les nombres s’écrivent en français, milliers groupés', () => {
    const [aapl, , ko] = lignesDepuisPositions(stockees)
    expect(aapl?.prixRevient).toBe('185,2')
    expect(ko?.quantite).toBe('1\u202F250')
    expect(ko?.prixRevient).toBe('1\u202F234,5678')
  })

  it('chaque valeur écrite se relit à l’identique', () => {
    for (const valeur of [185.2, 0.1, 1e-6, 1234.5678, 40, 0.30000000000000004]) {
      expect(lireNombreSaisi(ecrireNombreSaisi(valeur))).toBe(valeur)
    }
  })

  it('un portefeuille vide ouvre sur une ligne vierge', () => {
    const lignes = lignesDepuisPositions([])
    expect(lignes).toHaveLength(1)
    expect(empreinteDesLignes(lignes)).toBe('[]')
  })
})

describe('preparerEnvoi', () => {
  it('numérote comme l’écran, et ne compte pas les lignes vides', () => {
    const { positions } = preparerEnvoi([ligne('AAPL', '40'), ligneVide(), ligne('KO', '12,5')])
    expect(positions.map((p) => [p.ticker, p.line])).toEqual([
      ['AAPL', 1],
      ['KO', 3],
    ])
  })

  it('refuse sur place ce qui ne se lit pas, et seulement cela', () => {
    const { refus } = preparerEnvoi([
      ligne('AAPL', ''),
      ligne('KO', '12,5,3'),
      ligne('MSFT', '10', 'abc'),
      // Quantité négative, ticker inconnu : le SERVEUR le dit, pas le client.
      ligne('XYZ', '-5'),
      ligne('', '3'),
    ])
    expect(refus.map((r) => [r.ligne, r.champ])).toEqual([
      [1, 'quantity'],
      [2, 'quantity'],
      [3, 'cost_basis'],
    ])
    expect(refus[0]?.message).toBe('Quantité manquante.')
  })

  it('un prix de revient vide part à null', () => {
    const { positions } = preparerEnvoi([ligne('AAPL', '40', '  ')])
    expect(positions[0]?.cost_basis).toBeNull()
  })
})

describe('rangerRefus', () => {
  it('range chaque refus du serveur à sa ligne et à son champ', () => {
    const { parCellule, generaux } = rangerRefus([
      { line: 2, field: 'ticker', value: 'XYZ', problem: 'Ticker inconnu : XYZ.' },
      { line: 3, field: 'quantity', value: '-5.0', problem: 'Quantité nulle ou négative.' },
      { line: 4, field: null, value: null, problem: 'Ligne refusée.' },
      { line: null, field: null, value: null, problem: 'Aucune position soumise.' },
    ])
    expect(parCellule.map((r) => [r.ligne, r.champ])).toEqual([
      [2, 'ticker'],
      [3, 'quantity'],
      [4, 'ticker'],
    ])
    expect(generaux).toEqual(['Aucune position soumise.'])
  })
})

describe('empreinteDesLignes', () => {
  it('une ligne vide ajoutée n’est pas une modification', () => {
    const avant = [ligne('AAPL', '40')]
    expect(empreinteDesLignes([...avant, ligneVide()])).toBe(empreinteDesLignes(avant))
  })

  it('une quantité changée en est une', () => {
    expect(empreinteDesLignes([ligne('AAPL', '41')])).not.toBe(
      empreinteDesLignes([ligne('AAPL', '40')]),
    )
  })
})
