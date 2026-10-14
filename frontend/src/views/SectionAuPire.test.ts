/**
 * Section 3 sans série : la phrase à la place du sous-titre et de la courbe
 * (chantier 9.6). Rendue côté serveur ; l'espacement, lu dans la feuille de
 * style, commentaires blanchis.
 *
 * Constaté par Cowork le 2026-10-14, à 718 px : la phrase collait au bas du
 * bloc de la perte maximale. Elle prend l'espacement du sous-titre qu'elle
 * remplace. Mesuré dans Chrome à 390, 718 et 1 350 px.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Drawdown } from '../api/types'
import commun from '../components/Section.module.css'
import { LIBELLES } from '../contenu/libelles'
import { ContexteDeLangue, langueDuSite, type Langue } from '../lib/langue'
import { SectionAuPire } from './SectionAuPire'

const CREUX: Drawdown = {
  value: -0.1,
  peak_date: '2026-01-02',
  trough_date: '2026-01-06',
  window: { requested: 504, observations: 504, start: '2024-09-10', end: '2026-09-09', complete: true },
  amount: -8400,
  recovery_date: '2026-01-08',
  recovery_sessions: 2,
  period_label: 'ces deux dernières années',
}

function sansSerie(langue: Langue): string {
  return renderToStaticMarkup(
    createElement(
      ContexteDeLangue.Provider,
      { value: langueDuSite(langue, () => undefined) },
      createElement(SectionAuPire, { serie: null, creux: CREUX, asOf: '2026-09-09', devise: 'USD' }),
    ),
  )
}

/** Un texte tel que React l'écrit dans le HTML, apostrophes comprises. */
function commeEcrit(texte: string): string {
  return renderToStaticMarkup(createElement('i', null, texte)).slice('<i>'.length, -'</i>'.length)
}

const FEUILLE = readFileSync(
  fileURLToPath(new URL('../components/Section.module.css', import.meta.url)),
  'utf-8',
).replace(/\/\*[\s\S]*?\*\//g, '')

/** La valeur de `propriete` dans la première règle hors requête dont le sélecteur est `selecteur`. */
function declaration(selecteur: string, propriete: string): string | undefined {
  for (const [, tete, corps] of FEUILLE.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (tete?.trim() !== selecteur) continue
    for (const ligne of (corps ?? '').split(';')) {
      const [nom, ...valeur] = ligne.split(':')
      if (nom?.trim() === propriete) return valeur.join(':').trim()
    }
  }
  return undefined
}

describe('section 3 sans série', () => {
  it('la phrase prend la place du sous-titre, avec son espacement', () => {
    for (const langue of ['fr', 'en'] as const) {
      const l = LIBELLES[langue].auPire
      const html = sansSerie(langue)
      const phrase = `<p class="${commun.introduction} ${commun.aLaPlaceDuSousTitre}">${commeEcrit(l.sansCourbe)}</p>`
      expect(html, langue).toContain(phrase)
      // Ni sous-titre, ni courbe : la seule figure est le bloc mesure.
      expect(html, langue).not.toContain('<h3')
      expect(html.match(/<figure/g), langue).toHaveLength(1)
      expect(html, langue).not.toContain(commeEcrit(l.ou))
      // Après le bloc de la perte maximale.
      expect(html.indexOf(commeEcrit(l.perteMaximale)), langue).toBeGreaterThan(-1)
      expect(html.indexOf(phrase), langue).toBeGreaterThan(html.indexOf(commeEcrit(l.perteMaximale)))
    }
  })

  it('au-dessus de la phrase, l’espacement du sous-titre qu’elle remplace', () => {
    const sousTitre = declaration('.sousTitre', 'margin-block')?.split(/\s+/)[0]
    expect(sousTitre).toBe('var(--space-6)')
    expect(declaration('.aLaPlaceDuSousTitre', 'margin-block-start')).toBe(sousTitre)
    // L'introduction, que la phrase garde pour sa typographie, n'en fixe aucun.
    expect(declaration('.introduction', 'margin-block-start')).toBeUndefined()
    expect(declaration('.introduction', 'margin-block')).toBeUndefined()
  })
})
