/**
 * Section 1 et `<DataTable>` — rendus côté serveur, sans DOM simulé.
 *
 * `renderToStaticMarkup` produit le HTML que React enverrait : assez pour
 * vérifier la structure (§9.3, §13), les chiffres écrits et l'ordre, sans
 * imiter un navigateur. Ce qui tient au rendu visuel se vérifie dans un vrai.
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Valuation } from '../api/types'
import tableau from '../components/DataTable.module.css'
import { lignesTriees } from '../components/DataTable'
import { ESPACE_FINE } from '../lib/format'
import { SectionPortefeuille, colonnesDuPortefeuille } from './SectionPortefeuille'

const VALORISATION: Valuation = {
  as_of: '2026-09-09',
  total_value: 1500,
  currency: 'USD',
  positions: [
    { ticker: 'BBB', name: 'Bravo Corp', quantity: 10, cost_basis: null, price: 50, value: 500, weight: 1 / 3 },
    { ticker: 'AAA', name: 'Alpha Inc', quantity: 20, cost_basis: null, price: 50, value: 1000, weight: 2 / 3 },
  ],
}

function rendu(valorisation: Valuation = VALORISATION): string {
  return renderToStaticMarkup(createElement(SectionPortefeuille, { valorisation }))
}

describe('section 1 — le portefeuille', () => {
  it('écrit la devise publiée dans les en-têtes, jamais un symbole', () => {
    const html = rendu()
    expect(html).toContain('Prix (USD)')
    expect(html).toContain('Valeur (USD)')
    expect(html).not.toContain('$')
  })

  it('trie par poids décroissant au départ, sans changer les lignes reçues', () => {
    const html = rendu()
    expect(html.indexOf('AAA')).toBeLessThan(html.indexOf('BBB'))
    expect(VALORISATION.positions[0]?.ticker).toBe('BBB')
  })

  it('écrit des quantités entières sans décimale, et toute la colonne pareil', () => {
    const colonne = colonnesDuPortefeuille(VALORISATION).find((c) => c.cle === 'quantite')
    expect(colonne?.cellule(VALORISATION.positions[0]!)).toBe('10')

    const fractionnaire: Valuation = {
      ...VALORISATION,
      positions: [
        { ...VALORISATION.positions[0]!, quantity: 10.5 },
        VALORISATION.positions[1]!,
      ],
    }
    const colonneFr = colonnesDuPortefeuille(fractionnaire).find((c) => c.cle === 'quantite')
    expect(colonneFr?.cellule(fractionnaire.positions[1]!)).toBe('20,0')
  })

  it('dessine la barre de poids sur une échelle fixe de 0 à 100 %', () => {
    // Un tiers du portefeuille occupe un tiers de la piste, quel que soit le
    // poids le plus lourd : l'échelle ne s'étire pas aux données.
    const html = rendu()
    expect(html).toContain('inline-size:33.33333333333333%')
    expect(html).toContain('inline-size:66.66666666666666%')
    expect(html).toContain(`33,3${ESPACE_FINE}%`)
  })

  it('porte en pied la valeur totale PUBLIÉE, et aucune somme de poids', () => {
    const html = rendu({ ...VALORISATION, total_value: 1234.5 })
    const pied = html.slice(html.indexOf('<tfoot>'))
    expect(pied).toContain(`1${ESPACE_FINE}234,50`)
    expect(pied).not.toContain('%')
  })

  it('date la valorisation sous le titre', () => {
    expect(rendu()).toContain('2026-09-09')
  })
})

describe("section 1 — l'ordre des colonnes suit la largeur", () => {
  const cles = (etroit: boolean) => colonnesDuPortefeuille(VALORISATION, etroit).map((c) => c.cle)

  it("en large, l'ordre de DESIGN.md §8.2", () => {
    expect(cles(false)).toEqual(['ticker', 'nom', 'quantite', 'prix', 'valeur', 'poids'])
  })

  it('sous 900 px, ticker, valeur et poids en tête, et aucune colonne perdue', () => {
    // À 390 px, l'ordre large rejetait Valeur et Poids hors du cadre.
    expect(cles(true)).toEqual(['ticker', 'valeur', 'poids', 'nom', 'quantite', 'prix'])
    expect([...cles(true)].sort()).toEqual([...cles(false)].sort())
  })

  it("rendu hors navigateur dans l'ordre large, pied compris", () => {
    const html = rendu({ ...VALORISATION, total_value: 1234.5 })
    const entetes = html.slice(html.indexOf('<thead>'), html.indexOf('</thead>'))
    expect(entetes.indexOf('Nom')).toBeLessThan(entetes.indexOf('Valeur'))
    const pied = html.slice(html.indexOf('<tfoot>'))
    const cellules = pied.split('<td').slice(1)
    expect(cellules[0]).toContain('Total')
    expect(cellules[4]).toContain(`1${ESPACE_FINE}234,50`)
  })
})

describe('<DataTable> (§9.3, §13)', () => {
  it('a une légende, des en-têtes de colonne et de ligne', () => {
    const html = rendu()
    expect(html).toContain('<caption')
    expect(html.match(/scope="col"/g)).toHaveLength(6)
    expect(html.match(/scope="row"/g)).toHaveLength(2)
  })

  it('aligne les colonnes de chiffres à droite, et elles seules', () => {
    const html = rendu()
    const entetes = [...html.matchAll(/<th scope="col" class="([^"]*)"[^>]*>(?:<button[^>]*>)?([^<]*)/g)]
    const nombres = entetes
      .filter(([, classes]) => classes?.includes(tableau.nombre ?? 'absente'))
      .map(([, , titre]) => titre)
    expect(nombres).toEqual(['Quantité', 'Prix (USD)', 'Valeur (USD)', 'Poids'])
  })

  it('dit le tri par aria-sort, pas seulement par la couleur', () => {
    const html = rendu()
    expect(html).toContain('aria-sort="descending"')
    expect(html).toContain('▼')
  })

  it('trie une copie, par nombre ou par texte', () => {
    const lignes = [{ v: 2, t: 'b' }, { v: 10, t: 'a' }]
    const parNombre = {
      cle: 'v',
      titre: 'v',
      nature: 'nombre' as const,
      cellule: () => '',
      tri: (l: { v: number }) => l.v,
    }
    expect(lignesTriees(lignes, parNombre, 'croissant').map((l) => l.v)).toEqual([2, 10])
    expect(lignesTriees(lignes, parNombre, 'decroissant').map((l) => l.v)).toEqual([10, 2])
    expect(lignes.map((l) => l.v)).toEqual([2, 10])
  })
})
