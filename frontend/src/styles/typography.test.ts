/**
 * L'espace fine avant « % » en Spectral — la face qui complète @fontsource.
 *
 * Le défaut, mesuré dans le navigateur : Spectral revendique U+202F dans sa
 * `unicode-range` sans le contenir, Chrome synthétise alors une demi-espace de
 * 0,125 em, et « 50 % » se lit « 50% ». La face `espace-fine.ttf` le dessine à
 * 0,200 em (voir `tools/espace_fine.py` et `typography.css`).
 *
 * Ce qui se vérifie ici sans navigateur : que la police contient bien ce
 * qu'on croit, et qu'elle est déclarée là où elle peut servir. Le rendu, lui,
 * a été mesuré dans Chrome (README, §10).
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const POLICE = readFileSync(fileURLToPath(new URL('./fonts/espace-fine.ttf', import.meta.url)))
const TYPOGRAPHIE = readFileSync(fileURLToPath(new URL('./typography.css', import.meta.url)), 'utf-8')

/** Décalage de chaque table, lu dans le répertoire du fichier TrueType. */
function tables(octets: Buffer): Map<string, number> {
  const nombre = octets.readUInt16BE(4)
  const resultat = new Map<string, number>()
  for (let i = 0; i < nombre; i++) {
    const entree = 12 + 16 * i
    resultat.set(octets.toString('latin1', entree, entree + 4), octets.readUInt32BE(entree + 8))
  }
  return resultat
}

/** Tous les points de code du cmap (sous-tables de format 4), avec leur glyphe. */
function pointsDeCode(octets: Buffer, cmap: number): Map<number, number> {
  const resultat = new Map<number, number>()
  const sousTables = octets.readUInt16BE(cmap + 2)
  for (let i = 0; i < sousTables; i++) {
    const sousTable = cmap + octets.readUInt32BE(cmap + 4 + 8 * i + 4)
    if (octets.readUInt16BE(sousTable) !== 4) continue
    const segments = octets.readUInt16BE(sousTable + 6) / 2
    const fins = sousTable + 14
    const debuts = fins + 2 * segments + 2
    const deltas = debuts + 2 * segments
    const decalages = deltas + 2 * segments
    for (let s = 0; s < segments; s++) {
      const fin = octets.readUInt16BE(fins + 2 * s)
      const debut = octets.readUInt16BE(debuts + 2 * s)
      const delta = octets.readInt16BE(deltas + 2 * s)
      const decalage = octets.readUInt16BE(decalages + 2 * s)
      for (let c = debut; c <= fin && c !== 0xffff; c++) {
        const glyphe =
          decalage === 0
            ? (c + delta) & 0xffff
            : octets.readUInt16BE(decalages + 2 * s + decalage + 2 * (c - debut))
        resultat.set(c, glyphe)
      }
    }
  }
  return resultat
}

describe('la police espace-fine.ttf', () => {
  const t = tables(POLICE)

  it("ne dessine qu'un caractère : U+202F", () => {
    const cmap = pointsDeCode(POLICE, t.get('cmap')!)
    expect([...cmap.keys()]).toEqual([0x202f])
  })

  it("lui donne 0,200 em, la largeur de Times New Roman, d'Arial et de Cambria", () => {
    const glyphe = pointsDeCode(POLICE, t.get('cmap')!).get(0x202f)!
    const unitesParEm = POLICE.readUInt16BE(t.get('head')! + 18)
    // Les glyphes au-delà de `numberOfHMetrics` reprennent la dernière avance
    // stockée : l'optimiseur ne garde qu'une métrique quand toutes sont égales.
    const metriques = POLICE.readUInt16BE(t.get('hhea')! + 34)
    const avance = POLICE.readUInt16BE(t.get('hmtx')! + 4 * Math.min(glyphe, metriques - 1))
    expect(avance / unitesParEm).toBe(0.2)
  })

  it('reprend les métriques verticales de Spectral, pour ne pas agrandir la ligne', () => {
    const hhea = t.get('hhea')!
    expect(POLICE.readInt16BE(hhea + 4)).toBe(1059)
    expect(POLICE.readInt16BE(hhea + 6)).toBe(-463)
    expect(POLICE.readInt16BE(hhea + 8)).toBe(0)
  })
})

describe('la face est déclarée pour chaque graisse de Spectral importée', () => {
  const graisses = [...TYPOGRAPHIE.matchAll(/@import '@fontsource\/spectral\/(\d+)\.css'/g)].map(
    (m) => m[1],
  )
  const faces = [...TYPOGRAPHIE.matchAll(/@font-face\s*\{([^}]*)\}/g)].map((m) => ({
    corps: m[1] ?? '',
    position: m.index ?? 0,
  }))
  const derniereImportation = TYPOGRAPHIE.lastIndexOf('@import')

  it('trouve bien les graisses importées', () => {
    expect(graisses).toEqual(['400', '500'])
  })

  it.each(['400', '500'])('graisse %s : famille Spectral, U+202F seulement, après @fontsource', (graisse) => {
    const face = faces.find((f) => f.corps.includes(`font-weight: ${graisse};`))
    expect(face, `aucune face U+202F en ${graisse}`).toBeDefined()
    expect(face!.corps).toContain("font-family: 'Spectral';")
    expect(face!.corps).toContain('unicode-range: U+202F;')
    expect(face!.corps).toContain("url('./fonts/espace-fine.ttf')")
    // Entre deux faces qui couvrent le même caractère, la dernière déclarée
    // est essayée d'abord : avant @fontsource, celle-ci ne servirait jamais.
    expect(face!.position).toBeGreaterThan(derniereImportation)
  })
})
