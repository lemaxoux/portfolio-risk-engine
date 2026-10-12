/**
 * Les métadonnées de partage de la démonstration (DESIGN.md §19.7,
 * `demoAuBuild.ts`).
 *
 * `index.html` n'a qu'une langue, l'anglais, et ses balises sont lues sans
 * JavaScript par les robots de prévisualisation. AUCUNE ADRESSE N'EST ÉCRITE
 * EN DUR : sans l'origine du site, donnée par une variable d'environnement,
 * ni `og:url` ni `og:image`. Ce que les outils de partage en font se vérifie
 * chez l'hébergeur (9.5).
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { Plugin, UserConfig } from 'vite'
import { afterEach, describe, expect, it, vi } from 'vitest'

import configuration from '../../vite.config'
import { LIBELLES } from '../contenu/libelles'
import {
  ALTERNATIVE_DE_L_APERCU,
  balisesDePartage,
  demonstration,
  DESCRIPTION_DU_PARTAGE,
  DIMENSIONS_DE_L_APERCU,
  lireLApercu,
  lireLOrigine,
  sansLaDemonstration,
  TITRE_DU_PARTAGE,
  VARIABLE_DE_L_ORIGINE,
  type BaliseMeta,
} from './demoAuBuild'

const CLIENT = join(import.meta.dirname, '..', '..')
const README = readFileSync(join(CLIENT, '..', 'README.md'), 'utf-8')
const INDEX = readFileSync(join(CLIENT, 'index.html'), 'utf-8')
const APERCU = join(CLIENT, 'src', 'images', 'presentation', 'apercu.png')

const ORIGINE = 'https://exemple.test'

/** Le contenu d'une balise, par son nom (`name`) ou sa propriété (`property`). */
function contenu(balises: readonly BaliseMeta[], cle: string): string | undefined {
  return balises.find((balise) => balise.attrs.name === cle || balise.attrs.property === cle)?.attrs
    .content
}

const cles = (balises: readonly BaliseMeta[]) =>
  balises.map((balise) => balise.attrs.name ?? balise.attrs.property)

// ══════════════════════════════════════════════════════ L'origine du site ══

describe('l’origine du site', () => {
  it('se lit dans MX_RISK_ORIGINE_DU_SITE', () => {
    expect(VARIABLE_DE_L_ORIGINE).toBe('MX_RISK_ORIGINE_DU_SITE')
  })

  it('absente ou vide : pas d’origine', () => {
    expect(lireLOrigine(undefined)).toBeNull()
    expect(lireLOrigine('')).toBeNull()
  })

  it('une origine est rendue telle quelle', () => {
    expect(lireLOrigine(ORIGINE)).toBe(ORIGINE)
    expect(lireLOrigine('https://demo.exemple.test:8443')).toBe('https://demo.exemple.test:8443')
  })

  it('refuse ce qui n’est pas `https://hôte`, sans chemin ni barre finale', () => {
    for (const fautive of [
      'http://exemple.test',
      'https://exemple.test/',
      'https://exemple.test/demo',
      'https://exemple.test?x=1',
      'https://exemple.test#haut',
      'exemple.test',
      '//exemple.test',
      ' https://exemple.test',
      'https://Exemple.test',
    ]) {
      expect(() => lireLOrigine(fautive), fautive).toThrow(VARIABLE_DE_L_ORIGINE)
    }
  })
})

// ════════════════════════════════════════════════════════════ Les balises ══

describe('les balises de partage', () => {
  it('le titre est celui de `index.html`', () => {
    expect(INDEX).toContain(`<title>${TITRE_DU_PARTAGE}</title>`)
  })

  it('la description est la première phrase du README', () => {
    const [premierParagraphe = ''] = README.split('\n\n').slice(1)
    const premierePhrase = `${premierParagraphe.split('\n').join(' ').split('. ')[0]}.`
    expect(DESCRIPTION_DU_PARTAGE).toBe(premierePhrase)
  })

  it('le texte alternatif de l’image est celui de la figure, en anglais', () => {
    expect(ALTERNATIVE_DE_L_APERCU).toBe(LIBELLES.en.presentation.distingue.figure.alternative)
  })

  it('sans origine : aucune adresse absolue, et la petite carte', () => {
    const balises = balisesDePartage(null, null)
    expect(cles(balises)).toEqual([
      'description',
      'og:type',
      'og:title',
      'og:description',
      'twitter:card',
    ])
    expect(contenu(balises, 'description')).toBe(DESCRIPTION_DU_PARTAGE)
    expect(contenu(balises, 'og:description')).toBe(DESCRIPTION_DU_PARTAGE)
    expect(contenu(balises, 'og:title')).toBe(TITRE_DU_PARTAGE)
    expect(contenu(balises, 'og:type')).toBe('website')
    expect(contenu(balises, 'twitter:card')).toBe('summary')
    for (const balise of balises) expect(balise.attrs.content).not.toMatch(/https?:|\/\//)
  })

  it('une image sans origine ne suffit pas : toujours aucune adresse', () => {
    expect(cles(balisesDePartage(null, 'assets/apercu-00000000.png'))).not.toContain('og:image')
  })

  it('avec l’origine : l’adresse du site, l’image et ses dimensions, la grande carte', () => {
    const balises = balisesDePartage(ORIGINE, 'assets/apercu-00000000.png')
    expect(contenu(balises, 'og:url')).toBe(`${ORIGINE}/`)
    expect(contenu(balises, 'og:image')).toBe(`${ORIGINE}/assets/apercu-00000000.png`)
    expect(contenu(balises, 'og:image:type')).toBe('image/png')
    expect(contenu(balises, 'og:image:width')).toBe('1200')
    expect(contenu(balises, 'og:image:height')).toBe('630')
    expect(contenu(balises, 'og:image:alt')).toBe(ALTERNATIVE_DE_L_APERCU)
    expect(contenu(balises, 'twitter:card')).toBe('summary_large_image')
    expect(contenu(balises, 'description')).toBe(DESCRIPTION_DU_PARTAGE)
  })

  it('les balises Open Graph ont une propriété, les autres un nom', () => {
    for (const balise of balisesDePartage(ORIGINE, 'assets/apercu-00000000.png')) {
      const cle = balise.attrs.name ?? balise.attrs.property ?? ''
      expect(cle.startsWith('og:')).toBe(balise.attrs.property !== undefined)
      expect(balise).toMatchObject({ tag: 'meta', injectTo: 'head' })
    }
  })
})

// ══════════════════════════════════════════ L'image de prévisualisation ══

describe('l’image de prévisualisation', () => {
  it('est un PNG aux dimensions que les balises déclarent', () => {
    expect(DIMENSIONS_DE_L_APERCU).toEqual({ largeur: 1200, hauteur: 630 })
    const apercu = lireLApercu(APERCU)
    expect(apercu.contenu.readUInt32BE(16)).toBe(1200)
    expect(apercu.contenu.readUInt32BE(20)).toBe(630)
  })

  it('son nom dans le site porte l’empreinte de son contenu', () => {
    expect(lireLApercu(APERCU).fichier).toMatch(/^assets\/apercu-[0-9a-f]{8}\.png$/)
  })

  it('refuse un fichier absent, et une image d’une autre taille', () => {
    expect(() => lireLApercu(join(CLIENT, 'nulle-part.png'))).toThrow('absente')
    const capture = join(CLIENT, 'src', 'images', 'presentation', 'mesure-en-clair.png')
    expect(() => lireLApercu(capture)).toThrow('1200')
  })
})

// ══════════════════════════════════════════════════════════ Le greffon ══

const balisesDe = (greffon: Plugin) => (greffon.transformIndexHtml as () => BaliseMeta[])()

describe('le greffon de la démonstration', () => {
  it('sans origine : `noindex`, puis les balises sans adresse', () => {
    const balises = balisesDe(demonstration('nulle-part', { origine: null, apercu: APERCU }))
    expect(cles(balises)).toEqual(['robots', 'description', 'og:type', 'og:title', 'og:description', 'twitter:card'])
  })

  it('avec l’origine : les adresses absolues, et l’image que le site porte', () => {
    const balises = balisesDe(demonstration('nulle-part', { origine: ORIGINE, apercu: APERCU }))
    expect(cles(balises)[0]).toBe('robots')
    expect(contenu(balises, 'og:url')).toBe(`${ORIGINE}/`)
    expect(contenu(balises, 'og:image')).toBe(`${ORIGINE}/${lireLApercu(APERCU).fichier}`)
    expect(contenu(balises, 'twitter:card')).toBe('summary_large_image')
  })

  it('le build ordinaire n’écrit rien dans `index.html`', () => {
    expect(sansLaDemonstration().transformIndexHtml).toBeUndefined()
  })
})

// ═══════════════════════════════════════════════ La configuration de Vite ══

function configurer(mode: string): UserConfig {
  const lue = configuration as unknown as (env: { mode: string; command: 'build' }) => UserConfig
  return lue({ mode, command: 'build' })
}

function greffons(config: UserConfig): Plugin[] {
  return (config.plugins ?? [])
    .flat(4)
    .filter((g): g is Plugin => typeof g === 'object' && g !== null && 'name' in g)
}

describe('l’origine dans la configuration', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('sans la variable, aucune adresse absolue', () => {
    vi.stubEnv(VARIABLE_DE_L_ORIGINE, '')
    const tous = greffons(configurer('demo'))
      .filter((g) => g.name.startsWith('mx-risk-') && typeof g.transformIndexHtml === 'function')
      .flatMap(balisesDe)
    expect(cles(tous)).toContain('og:title')
    expect(cles(tous)).not.toContain('og:url')
    expect(cles(tous)).not.toContain('og:image')
  })

  it('une origine fautive arrête le build de démonstration, pas le build ordinaire', () => {
    vi.stubEnv(VARIABLE_DE_L_ORIGINE, `${ORIGINE}/demo`)
    expect(() => configurer('demo')).toThrow(VARIABLE_DE_L_ORIGINE)
    expect(() => configurer('production')).not.toThrow()
  })

  it('avec l’origine, le greffon de la démonstration écrit les adresses', () => {
    vi.stubEnv(VARIABLE_DE_L_ORIGINE, ORIGINE)
    const greffon = greffons(configurer('demo')).find((g) => g.name === 'mx-risk-demonstration')
    expect(greffon).toBeDefined()
    expect(contenu(balisesDe(greffon as Plugin), 'og:url')).toBe(`${ORIGINE}/`)
  })
})
