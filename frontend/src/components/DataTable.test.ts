/**
 * `<DataTable>` — ce que la feuille de style garantit (DESIGN.md §9.3).
 *
 * L'en-tête n'est pas collant : dans le cadre qui défile à l'horizontale, il
 * collerait au cadre et non à la page, donc jamais. La première colonne, elle,
 * reste collante à l'horizontale. Le test lit le FICHIER, commentaires
 * blanchis, comme `styles/tokens.test.ts` : une règle qui cite `sticky` pour
 * expliquer qu'elle ne l'est pas ne doit pas se faire prendre pour lui.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DataTable, attributsDuCadre, type Colonne } from './DataTable'

const CSS = readFileSync(
  fileURLToPath(new URL('./DataTable.module.css', import.meta.url)),
  'utf-8',
).replace(/\/\*[\s\S]*?\*\//g, '')

/** Le corps de la première règle dont le sélecteur est exactement `selecteur`. */
function regle(selecteur: string): string {
  for (const [, tete, corps] of CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (tete?.trim() === selecteur) return corps ?? ''
  }
  throw new Error(`Règle introuvable : ${selecteur}`)
}

const COLLANT = /position\s*:\s*sticky/

describe('DataTable.module.css — §9.3', () => {
  it("l'en-tête n'est pas collant", () => {
    expect(regle('.entete')).not.toMatch(COLLANT)
  })

  it('la première colonne reste collante (témoin : la lecture voit un sticky quand il y en a un)', () => {
    expect(regle('.tableau tr > :first-child')).toMatch(COLLANT)
  })
})

describe('le cadre qui défile, au clavier (chantier 7E, §9.3, §13)', () => {
  it('un cadre qui déborde est une région nommée par la légende, que la tabulation prend', () => {
    expect(attributsDuCadre(true, 'legende')).toEqual({
      role: 'region',
      'aria-labelledby': 'legende',
      tabIndex: 0,
    })
  })

  it("un cadre qui tient dans sa colonne n'est ni une région ni un arrêt", () => {
    expect(attributsDuCadre(false, 'legende')).toEqual({})
  })

  it('la légende porte l’identifiant que la région cite, celui que donne l’appelant s’il en donne un', () => {
    const colonnes: Colonne<{ nom: string }>[] = [
      { cle: 'nom', titre: 'Nom', nature: 'texte', cellule: (l) => l.nom },
    ]
    const rendu = (idLegende?: string) =>
      renderToStaticMarkup(
        createElement(DataTable<{ nom: string }>, {
          legende: 'Une légende',
          colonnes,
          lignes: [{ nom: 'A' }],
          cleDeLigne: (l: { nom: string }) => l.nom,
          ...(idLegende === undefined ? {} : { idLegende }),
        }),
      )
    expect(rendu()).toMatch(/<caption id="[^"]+"/)
    expect(rendu('tableau-risque')).toContain('<caption id="tableau-risque"')
  })
})
