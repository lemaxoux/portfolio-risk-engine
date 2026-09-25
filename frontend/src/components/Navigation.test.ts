/**
 * La navigation ne promet que des sections qui existent.
 *
 * Chaque ancre du rail et de la liste d'ancres doit correspondre à une
 * `<Section ancre=…>` réellement rendue par une vue : un lien qui ne mène
 * nulle part serait une promesse, et §8.2 veut une page courte qui tient
 * plutôt qu'une page qui promet.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { SECTIONS } from './Navigation'

const VUES = fileURLToPath(new URL('../views', import.meta.url))

function ancresDesVues(): Map<string, number> {
  const trouvees = new Map<string, number>()
  for (const nom of readdirSync(VUES).filter((n) => n.endsWith('.tsx'))) {
    const source = readFileSync(join(VUES, nom), 'utf-8')
    for (const m of source.matchAll(/<Section ancre="([^"]+)" numero=\{(\d+)\}/g)) {
      trouvees.set(m[1] ?? '', Number(m[2]))
    }
  }
  return trouvees
}

describe('navigation entre les sections', () => {
  it('chaque ancre mène à une section rendue, sous le même numéro', () => {
    const vues = ancresDesVues()
    for (const section of SECTIONS) {
      expect(vues.get(section.ancre), section.ancre).toBe(section.numero)
    }
  })

  it('les six sections de §8.2, dans l’ordre, et aucune autre', () => {
    expect(SECTIONS.map((s) => s.numero)).toEqual([1, 2, 3, 4, 5, 6])
    expect(ancresDesVues().size).toBe(SECTIONS.length)
  })
})
