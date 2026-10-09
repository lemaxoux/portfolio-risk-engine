/**
 * Les coupures conditionnelles de la méthodologie, posées au build (DESIGN.md
 * §6.3, décision du 2026-10-08).
 *
 * Ce qui est vérifié : le texte livré, coupures retirées, est la source, dans
 * les deux langues, et c'est bien lui que le greffon livre au build, et au
 * build seulement ; les coupures ne tombent que dans les paragraphes, hors
 * formules, liens et entités, jamais dans un mot qui porte une capitale ou un
 * chiffre, et toujours avec deux lettres avant et trois après ; chaque
 * exception de la liste est appliquée et nécessaire ; aucun module du client
 * n'importe les motifs ; sous 900 px, les coupures ne coupent rien.
 *
 * Ce qui se voit dans le navigateur, l'espace des lignes justifiées, est
 * mesuré dans Chrome (`docs/outils/justification-methodo.mjs`, hors dépôt).
 */
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import creerCoupeur from 'hyphen'
import motifsEn from 'hyphen/patterns/en-us'
import motifsFr from 'hyphen/patterns/fr'
import { describe, expect, it } from 'vitest'

import { lireContenu, texteDe, type EnLigne } from '../lib/contenu'
import {
  APRES,
  AVANT,
  COUPURE,
  EXCEPTIONS,
  borner,
  poserCoupures,
  secable,
  type LangueDesCoupures,
} from './coupures'
import { chargerMethodologie, coupeur, coupuresDeLaMethodologie, texteLivre } from './coupuresAuBuild'

const LANGUES = ['fr', 'en'] as const

const fichier = (langue: LangueDesCoupures) =>
  fileURLToPath(new URL(`./methodologie.${langue}.md`, import.meta.url))

const SOURCES: Record<LangueDesCoupures, string> = {
  fr: readFileSync(fichier('fr'), 'utf-8'),
  en: readFileSync(fichier('en'), 'utf-8'),
}

const sans = (texte: string) => texte.split(COUPURE).join('')

/** Un paragraphe d'essai, dans un contenu qui commence par son titre. */
const paragraphe = (texte: string) => `# Titre\n\n${texte}\n`

describe('le texte livré, coupures retirées, est la source', () => {
  it.each(LANGUES)('%s', (langue) => {
    const livre = texteLivre(SOURCES[langue], langue)
    expect(livre).not.toBe(SOURCES[langue])
    expect(sans(livre)).toBe(SOURCES[langue])
  })

  it('la source ne porte aucune coupure : elles ne vivent que dans le texte livré', () => {
    for (const langue of LANGUES) expect(SOURCES[langue]).not.toContain(COUPURE)
  })

  it.each(LANGUES)('%s : le greffon livre ce texte-là, pour l’import brut du fichier', (langue) => {
    const module = chargerMethodologie(`${fichier(langue)}?raw`)
    expect(module).not.toBeNull()
    const livre: unknown = JSON.parse((module ?? '').slice('export default '.length))
    expect(livre).toBe(texteLivre(SOURCES[langue], langue))
  })

  it('au build seulement, avant Vite, et pour ces deux fichiers seulement', () => {
    const greffon = coupuresDeLaMethodologie()
    expect(greffon.apply).toBe('build')
    expect(greffon.enforce).toBe('pre')
    expect(greffon.load).toBe(chargerMethodologie)
    // Le fichier sans `?raw`, un autre contenu, un autre module : Vite les charge.
    expect(chargerMethodologie(fichier('fr'))).toBeNull()
    expect(chargerMethodologie(fichier('fr').replace('methodologie.fr', 'autre.fr') + '?raw')).toBeNull()
    expect(chargerMethodologie(fileURLToPath(new URL('./methodes.ts', import.meta.url)))).toBeNull()
  })
})

/** Le texte d'un élément en ligne qui n'est ni du texte courant, ni une étiquette. */
function horsProse(contenu: readonly EnLigne[]): string[] {
  return contenu.flatMap((element) => (element.type === 'texte' ? [] : [texteDe([element])]))
}

describe('où tombent les coupures', () => {
  it.each(LANGUES)('%s : dans les paragraphes seulement, hors formules, liens et entités', (langue) => {
    const livre = texteLivre(SOURCES[langue], langue)
    let dansLaProse = 0
    for (const bloc of lireContenu(livre).blocs) {
      if (bloc.type !== 'paragraphe') {
        expect(JSON.stringify(bloc), `bloc ${bloc.type}, ligne ${bloc.ligne}`).not.toContain(COUPURE)
        continue
      }
      for (const texte of horsProse(bloc.contenu)) expect(texte, `ligne ${bloc.ligne}`).not.toContain(COUPURE)
      dansLaProse += [...JSON.stringify(bloc)].filter((c) => c === COUPURE).length
    }
    expect(dansLaProse).toBe([...livre].filter((c) => c === COUPURE).length)
    // Une entité reste entière : aucune coupure entre « & » et « ; ».
    expect(livre).not.toMatch(new RegExp(`&[#a-zA-Z0-9${COUPURE}]*${COUPURE}[#a-zA-Z0-9${COUPURE}]*;`))
  })

  it.each(LANGUES)(
    '%s : jamais dans un mot qui porte une capitale ou un chiffre ; deux lettres avant, trois après',
    (langue) => {
      const livre = texteLivre(SOURCES[langue], langue)
      const mots = livre.match(new RegExp(`[\\p{L}\\p{N}${COUPURE}]+`, 'gu')) ?? []
      const coupes = mots.filter((mot) => mot.includes(COUPURE))
      expect(coupes.length).toBeGreaterThan(100)
      for (const mot of coupes) {
        expect(secable(sans(mot)), mot).toBe(true)
        const morceaux = mot.split(COUPURE)
        const total = [...sans(mot)].length
        let avant = 0
        for (const morceau of morceaux.slice(0, -1)) {
          avant += [...morceau].length
          expect(avant, mot).toBeGreaterThanOrEqual(AVANT)
          expect(total - avant, mot).toBeGreaterThanOrEqual(APRES)
        }
      }
    },
  )
})

describe('les règles', () => {
  it('les mots que nomme la décision ne se coupent pas', () => {
    const fr = coupeur('fr')
    const en = coupeur('en')
    for (const texte of ['VaR', 'CVaR', 'Student', 'Monte Carlo', 'S&P 500', 'Méthodologie', '1er']) {
      expect(poserCoupures(paragraphe(`${texte} historiquement.`), fr), texte).toContain(`${texte} `)
      expect(poserCoupures(paragraphe(`${texte} historically.`), en), texte).toContain(`${texte} `)
    }
    expect(secable('historique')).toBe(true)
    expect(secable('VaR')).toBe(false)
    expect(secable('q1')).toBe(false)
  })

  it('titres, listes, formules, liens et entités restent tels quels', () => {
    const fr = coupeur('fr')
    const source = [
      '# Méthodologie',
      '',
      '## Les conventions {#conventions}',
      '',
      '- les rendements quotidiennement composés',
      '',
      '$$rendement_{quotidien}$$',
      '',
      'La volatilité $volatilite$ et [la volatilité historique](#volatilite)&nbsp;: quotidiennement.',
      '',
    ].join('\n')
    const livre = poserCoupures(source, fr)
    const lignes = livre.split('\n')
    expect(lignes.slice(0, 8)).toEqual(source.split('\n').slice(0, 8))
    expect(lignes[8]).toContain('$volatilite$ et [la volatilité historique](#volatilite)&nbsp;:')
    expect(lignes[8]).toContain(COUPURE)
    expect(sans(livre)).toBe(source)
  })

  it('l’étiquette en tête d’un paragraphe est de la prose', () => {
    const livre = poserCoupures(paragraphe('**La composition quotidienne.** Le texte.'), coupeur('fr'))
    expect(livre.slice(0, livre.indexOf('.**'))).toContain(COUPURE)
  })

  it('borner : deux lettres au moins avant une coupure, trois au moins après', () => {
    const c = COUPURE
    expect(borner(`a${c}bcdef`)).toBe('abcdef')
    expect(borner(`ab${c}cdef`)).toBe(`ab${c}cdef`)
    expect(borner(`abc${c}def`)).toBe(`abc${c}def`)
    expect(borner(`abcd${c}ef`)).toBe('abcdef')
    expect(borner(`é${c}tu${c}diant`)).toBe(`étu${c}diant`)
    expect(borner('mot')).toBe('mot')
  })

  it('les exceptions : chacune appliquée, présente dans son texte, et nécessaire', () => {
    const sansExceptions = {
      fr: creerCoupeur(motifsFr, { hyphenChar: COUPURE, html: false }),
      en: creerCoupeur(motifsEn, { hyphenChar: COUPURE, html: false }),
    }
    for (const langue of LANGUES) {
      for (const exception of EXCEPTIONS[langue]) {
        const mot = exception.split('-').join('')
        const attendu = exception.split('-').join(COUPURE)
        expect(coupeur(langue)(mot), exception).toBe(attendu)
        expect(SOURCES[langue], exception).toContain(mot)
        expect(texteLivre(SOURCES[langue], langue), exception).toContain(attendu)
        expect(borner(sansExceptions[langue](mot)), exception).not.toBe(attendu)
      }
    }
  })
})

describe('les motifs ne servent qu’au build', () => {
  const SRC = fileURLToPath(new URL('..', import.meta.url))
  const PERMIS = new Set(['contenu/coupuresAuBuild.ts', 'contenu/coupures.test.ts', 'contenu/hyphen.d.ts'])

  it('aucun module du client n’importe `hyphen` ni le greffon', () => {
    const fautifs = readdirSync(SRC, { recursive: true })
      .map((chemin) => String(chemin).split(path.sep).join('/'))
      .filter((chemin) => /\.(ts|tsx)$/.test(chemin) && !PERMIS.has(chemin))
      .filter((chemin) => {
        const code = readFileSync(path.join(SRC, chemin), 'utf-8')
        return /from ['"]hyphen/.test(code) || /from ['"][^'"]*coupuresAuBuild['"]/.test(code)
      })
    expect(fautifs).toEqual([])
  })

  it('aucun fichier du client n’écrit U+00AD : la coupure ne vient que du build', () => {
    const fautifs = readdirSync(SRC, { recursive: true })
      .map((chemin) => String(chemin).split(path.sep).join('/'))
      .filter((chemin) => /\.(ts|tsx|css|md|json)$/.test(chemin))
      .filter((chemin) => readFileSync(path.join(SRC, chemin), 'utf-8').includes(COUPURE))
    expect(fautifs).toEqual([])
  })
})

describe('sous 900 px, les coupures ne coupent rien', () => {
  it('`hyphens: none` sur la prose de la méthodologie, hors de la requête des 900 px', () => {
    const css = readFileSync(fileURLToPath(new URL('../views/Methodologie.module.css', import.meta.url)), 'utf-8')
    const sansCommentaires = css.replace(/\/\*[\s\S]*?\*\//g, '')
    const horsMedia = sansCommentaires.slice(0, sansCommentaires.indexOf('@media'))
    expect(horsMedia).toMatch(/\.texte \{\s*hyphens: none;\s*\}/)
  })
})
