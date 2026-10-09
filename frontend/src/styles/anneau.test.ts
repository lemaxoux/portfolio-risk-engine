/**
 * L'anneau de focus se voit sur chaque fond où il se pose (chantier 7E,
 * DESIGN.md §13, WCAG 1.4.11 : 3:1 au moins pour un élément d'interface).
 *
 * L'anneau est `--accent`, 2 px, décalé de 2 px (`styles/reset.css`). Il se
 * pose sur la page (`--surface-0`), sur un bloc surélevé et le bandeau
 * (`--surface-1`), et sur l'en-tête d'un tableau (`--surface-2`). La colonne
 * collante d'un tableau prend `--fond-tableau` : la page par défaut, un bloc
 * surélevé dans une crise rejouée, et `--surface-2` pour sa cellule
 * d'en-tête. Les valeurs sont lues dans `tokens.css`, pour les deux thèmes.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { contraste } from '../components/charts/couleurs'

const TOKENS = readFileSync(fileURLToPath(new URL('./tokens.css', import.meta.url)), 'utf-8')
const RESET = readFileSync(fileURLToPath(new URL('./reset.css', import.meta.url)), 'utf-8')

/** La valeur d'une couleur de la palette : `--sombre-accent: #4fa69f`. */
function couleur(nom: string): string {
  const trouvee = new RegExp(nom + ':[ ]*(#[0-9a-fA-F]{6})').exec(TOKENS)
  if (trouvee === null || trouvee[1] === undefined) throw new Error(`Couleur introuvable : ${nom}`)
  return trouvee[1]
}

const FONDS = ['surface-0', 'surface-1', 'surface-2'] as const

describe("l'anneau de focus", () => {
  it('est --accent, 2 px, décalé de 2 px', () => {
    const regle = /:focus-visible\s*\{([^}]*)\}/.exec(RESET)?.[1] ?? ''
    expect(regle).toMatch(/outline:\s*2px solid var\(--accent\)/)
    expect(regle).toMatch(/outline-offset:\s*2px/)
  })

  it.each(['sombre', 'clair'])('contraste à 3:1 au moins sur chaque fond, thème %s', (theme) => {
    const accent = couleur(`--${theme}-accent`)
    for (const fond of FONDS) {
      const ratio = contraste(accent, couleur(`--${theme}-${fond}`))
      expect(ratio, `${theme} : --accent sur --${fond}`).toBeGreaterThanOrEqual(3)
    }
  })
})
