/**
 * `<Observation>` — les trois cas de §9.2, rendus côté serveur.
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { Observation as ObservationApi, Threshold } from '../api/types'
import { Observation, sujetDejaDit } from './Observation'
import styles from './Observation.module.css'

function seuil(
  kind: Threshold['kind'],
  rendered: string,
  role: Threshold['role'] = kind === 'chosen' ? 'threshold' : 'reference',
): Threshold {
  return {
    name: `seuil ${kind}`,
    kind,
    role,
    value: 0.7,
    rationale: 'une raison',
    percent: false,
    chosen: kind === 'chosen',
    rendered,
  }
}

function observation(thresholds: Threshold[]): ObservationApi {
  return {
    rule: 'apparent_diversification',
    rule_label: 'Lignes qui bougent ensemble',
    subject: 'portefeuille',
    statement: "Ces deux dernières années, aucune corrélation n'atteint 0,70.",
    facts: {},
    provenance: "fenêtre d'estimation : 504 séances, 2024-09-05 → 2026-09-09",
    thresholds,
    uses_chosen_threshold: thresholds.some((s) => s.chosen),
    rendered: '',
  }
}

function rendu(o: ObservationApi): string {
  return renderToStaticMarkup(createElement(Observation, { observation: o })).replaceAll(
    '&#x27;',
    "'",
  )
}

describe('le sujet, à côté du libellé', () => {
  const avec = (rule_label: string, subject: string): ObservationApi => ({
    ...observation([]),
    rule_label,
    subject,
  })
  const sujetAffiche = (o: ObservationApi) => rendu(o).includes(`<span class="${styles.sujet}">`)

  it('est masqué quand le libellé le dit déjà', () => {
    const html = rendu(avec('Le portefeuille en crise', 'portefeuille'))
    expect(sujetAffiche(avec('Le portefeuille en crise', 'portefeuille'))).toBe(false)
    // Le mot n'apparaît qu'une fois dans l'en-tête : celle du libellé.
    expect(html.split('portefeuille').length - 1).toBe(1)
  })

  it('reste affiché quand le libellé ne le dit pas', () => {
    expect(sujetAffiche(avec('Combien de lignes, en réalité', 'portefeuille'))).toBe(true)
    expect(sujetAffiche(avec('Poids dans les variations', 'JPM'))).toBe(true)
    expect(sujetAffiche(avec('Crise rejouée en partie', 'Crise financière 2008'))).toBe(true)
  })

  it('cherche un mot entier, casse comprise : un ticker n’est pas un mot du libellé', () => {
    expect(sujetDejaDit('Le portefeuille en crise', 'portefeuille')).toBe(true)
    expect(sujetDejaDit('Le portefeuille en crise', 'EN')).toBe(false)
    expect(sujetDejaDit('Le portefeuille en crise', 'porte')).toBe(false)
    expect(sujetDejaDit('Poids dans les variations', 'A')).toBe(false)
  })
})

describe('les trois cas de §9.2', () => {
  it('aucun seuil : AUCUNE ligne de seuil, pas même « n/a »', () => {
    const html = rendu(observation([]))
    expect(html).not.toContain('Seuil')
    expect(html).not.toContain('data-seuil')
    expect(html).not.toContain('n/a')
  })

  it('seuil dérivé : la ligne, sans point de réserve', () => {
    const html = rendu(observation([seuil('derived', 'part de JPM = 25,6 % (référence calculée)')]))
    expect(html).toContain('data-seuil="derived"')
    expect(html).not.toContain(styles.point)
    expect(html).not.toContain(styles.choisi)
  })

  it('seuil relatif au portefeuille : la ligne, sans point non plus', () => {
    const html = rendu(observation([seuil('portfolio_relative', 'corrélation JPM–KO = 0,53')]))
    expect(html).not.toContain(styles.point)
  })

  it('seuil CHOISI : le point --caveat, et lui seul', () => {
    const html = rendu(
      observation([
        seuil('chosen', 'corrélation forte = 0,7 (seuil CHOISI à la main)'),
        seuil('portfolio_relative', 'corrélation JPM–KO = 0,53'),
      ]),
    )
    expect(html.match(new RegExp(styles.point ?? 'absent', 'g'))).toHaveLength(1)
    expect(html).toContain(styles.choisi)
  })

  it('le point dépend du champ machine `kind`, pas du mot « CHOISI »', () => {
    // Un texte qui contiendrait le mot sans que le seuil soit choisi ne doit
    // pas allumer le point ; l'inverse non plus.
    expect(rendu(observation([seuil('derived', 'CHOISI dans le texte')]))).not.toContain(styles.point)
    expect(rendu(observation([seuil('chosen', 'sans le mot')]))).toContain(styles.point)
  })
})

describe('le texte est celui du backend', () => {
  it('rend statement, rendered et provenance mot pour mot', () => {
    const o = observation([seuil('chosen', 'corrélation forte = 0,7 (seuil CHOISI à la main)')])
    const html = rendu(o)
    expect(html).toContain(o.statement)
    expect(html).toContain('corrélation forte = 0,7 (seuil CHOISI à la main)')
    expect(html).toContain(o.provenance)
  })
})

describe('« Seuil » pour une frontière, « Référence » pour une valeur du portefeuille', () => {
  // DESIGN.md §9.2. Dans « Lignes qui bougent ensemble », la corrélation de la
  // paire la plus corrélée était titrée « Seuil : » comme le vrai seuil choisi
  // affiché juste au-dessus d'elle.
  const choisi = seuil('chosen', 'corrélation forte = 0,70 (seuil CHOISI à la main)')
  const paire = seuil('portfolio_relative', 'corrélation JNJ–KO = 0,42 (relatif au portefeuille)')

  it('la paire la plus corrélée est une référence, le seuil choisi reste un seuil', () => {
    const html = rendu(observation([choisi, paire]))
    expect(html).toMatch(/Seuil\u00a0: <\/span>corrélation forte = 0,70/)
    expect(html).toMatch(/Référence\u00a0: <\/span>corrélation JNJ–KO = 0,42/)
    expect(html).not.toMatch(/Seuil\u00a0: <\/span>corrélation JNJ–KO/)
  })

  it("la part de capital d'une ligne, dérivée du portefeuille, est une référence", () => {
    const html = rendu(
      observation([seuil('derived', 'part de JPM dans la valeur = 25,6 %', 'reference')]),
    )
    expect(html).toContain('Référence\u00a0: ')
    expect(html).not.toContain('Seuil\u00a0: ')
  })

  it("un seuil dérivé qui se démontre reste un seuil : l'étiquette suit role, pas kind", () => {
    const html = rendu(
      observation([seuil('derived', 'nombre minimal de séances estimables = 3', 'threshold')]),
    )
    expect(html).toContain('Seuil\u00a0: ')
    expect(html).not.toContain('Référence')
  })
})
