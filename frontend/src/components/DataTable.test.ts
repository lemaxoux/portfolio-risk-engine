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
import { describe, expect, it } from 'vitest'

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
