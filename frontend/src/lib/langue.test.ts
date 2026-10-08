/**
 * Le choix de la langue (chantier 7D), et le script de `index.html` qui le
 * fait avant le premier rendu.
 *
 * Le script est en JavaScript nu, dans la page : il ne peut pas importer
 * `choisirLangue`. Il est donc EXÉCUTÉ ici, sur les mêmes cas, avec une
 * adresse, un stockage et un navigateur simulés : les deux écritures du même
 * choix ne peuvent pas diverger sans qu'un test échoue.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  appliquerLangue,
  ATTRIBUT_LANG,
  autreLangue,
  choisirLangue,
  CLE_LANGUE,
  langueDeLAdresse,
  langueDeLaPage,
  langueDuNavigateur,
  langueMemorisee,
  type Langue,
} from './langue'

describe('le choix', () => {
  it('lit `lang` dans l’adresse, et rien d’autre', () => {
    expect(langueDeLAdresse('?lang=en')).toBe('en')
    expect(langueDeLAdresse('?x=1&lang=fr')).toBe('fr')
    expect(langueDeLAdresse('?lang=de')).toBeNull()
    expect(langueDeLAdresse('?lang=EN')).toBeNull()
    expect(langueDeLAdresse('')).toBeNull()
  })

  it('prend la première langue du navigateur qui est du français ou de l’anglais', () => {
    expect(langueDuNavigateur(['fr-CA', 'en-US'])).toBe('fr')
    expect(langueDuNavigateur(['de-DE', 'en-GB', 'fr'])).toBe('en')
    expect(langueDuNavigateur(['EN-us'])).toBe('en')
    expect(langueDuNavigateur(['de', 'it'])).toBeNull()
    expect(langueDuNavigateur([])).toBeNull()
  })

  it('l’adresse, puis la mémoire, puis le navigateur, puis le français', () => {
    expect(choisirLangue({ adresse: 'en', memorisee: 'fr', navigateur: 'fr' })).toBe('en')
    expect(choisirLangue({ adresse: null, memorisee: 'en', navigateur: 'fr' })).toBe('en')
    expect(choisirLangue({ adresse: null, memorisee: null, navigateur: 'en' })).toBe('en')
    expect(choisirLangue({ adresse: null, memorisee: null, navigateur: null })).toBe('fr')
  })

  it('l’autre langue, et l’attribut de la page', () => {
    expect(autreLangue('fr')).toBe('en')
    expect(autreLangue('en')).toBe('fr')
    expect(ATTRIBUT_LANG).toEqual({ fr: 'fr', en: 'en-US' })
  })
})

// ═══════════════════════════════════════════ Le navigateur, simulé ══

interface Simulation {
  readonly stockage: Map<string, string>
  readonly racine: { lang: string; setAttribute: (nom: string, valeur: string) => void }
  readonly adresses: string[]
  readonly globaux: {
    location: { search: string; pathname: string; hash: string }
    localStorage: Storage
    navigator: { languages: readonly string[]; language: string }
    history: { state: unknown; replaceState: (etat: unknown, titre: string, url: string) => void }
    document: { documentElement: Simulation['racine'] }
  }
}

function simuler(options: {
  readonly recherche?: string
  readonly chemin?: string
  readonly fragment?: string
  readonly memorisee?: string | null
  readonly bloque?: boolean
  readonly langues?: readonly string[]
  readonly langue?: string
}): Simulation {
  const stockage = new Map<string, string>()
  if (options.memorisee) stockage.set(CLE_LANGUE, options.memorisee)
  const refus = () => {
    throw new DOMException('refusé')
  }
  const localStorage = {
    getItem: options.bloque ? refus : (cle: string) => stockage.get(cle) ?? null,
    setItem: options.bloque ? refus : (cle: string, valeur: string) => void stockage.set(cle, valeur),
    removeItem: (cle: string) => void stockage.delete(cle),
  } as unknown as Storage
  const racine = {
    lang: 'fr',
    setAttribute(nom: string, valeur: string) {
      if (nom === 'lang') racine.lang = valeur
    },
  }
  const adresses: string[] = []
  return {
    stockage,
    racine,
    adresses,
    globaux: {
      location: {
        search: options.recherche ?? '',
        pathname: options.chemin ?? '/portefeuilles/1',
        hash: options.fragment ?? '',
      },
      localStorage,
      navigator: { languages: options.langues ?? [], language: options.langue ?? '' },
      history: { state: null, replaceState: (_etat, _titre, url) => void adresses.push(url) },
      document: { documentElement: racine },
    },
  }
}

const SCRIPT = (() => {
  const page = readFileSync(join(import.meta.dirname, '..', '..', 'index.html'), 'utf-8')
  const trouve = /<script id="choix-de-la-langue">([\s\S]*?)<\/script>/.exec(page)
  if (trouve === null || trouve[1] === undefined) throw new Error('Script de langue introuvable dans index.html.')
  return trouve[1]
})()

/** Fait tourner le script de `index.html` dans la simulation. */
function executer(simulation: Simulation): void {
  const g = simulation.globaux
  new Function('location', 'localStorage', 'navigator', 'history', 'document', 'URLSearchParams', SCRIPT)(
    g.location,
    g.localStorage,
    g.navigator,
    g.history,
    g.document,
    URLSearchParams,
  )
}

/** Ce que `choisirLangue` décide pour la même simulation. */
function attendu(simulation: Simulation, options: Parameters<typeof simuler>[0]): Langue {
  const memorisee = options.bloque ? null : (simulation.stockage.get(CLE_LANGUE) ?? null)
  const langues = (options.langues ?? []).length > 0 ? (options.langues ?? []) : [options.langue ?? '']
  return choisirLangue({
    adresse: langueDeLAdresse(options.recherche ?? ''),
    memorisee: memorisee === 'fr' || memorisee === 'en' ? memorisee : null,
    navigateur: langueDuNavigateur(langues),
  })
}

const CAS: readonly { nom: string; options: Parameters<typeof simuler>[0]; langue: Langue }[] = [
  { nom: 'l’adresse l’emporte', options: { recherche: '?lang=en', memorisee: 'fr', langues: ['fr-FR'] }, langue: 'en' },
  { nom: 'l’adresse en français', options: { recherche: '?lang=fr', memorisee: 'en', langues: ['en-US'] }, langue: 'fr' },
  { nom: 'une valeur inconnue est ignorée', options: { recherche: '?lang=de', memorisee: 'en', langues: ['fr'] }, langue: 'en' },
  { nom: 'la mémoire avant le navigateur', options: { memorisee: 'en', langues: ['fr-CA'] }, langue: 'en' },
  { nom: 'une mémoire illisible est ignorée', options: { memorisee: 'de', langues: ['en-GB'] }, langue: 'en' },
  { nom: 'le navigateur, première langue connue', options: { langues: ['de-DE', 'en-GB', 'fr'] }, langue: 'en' },
  { nom: 'le navigateur, français canadien', options: { langues: ['fr-CA', 'en-US'] }, langue: 'fr' },
  { nom: 'aucune langue connue : le français', options: { langues: ['de', 'it'] }, langue: 'fr' },
  { nom: 'sans `languages`, `language`', options: { langues: [], langue: 'en-US' }, langue: 'en' },
  { nom: 'stockage bloqué : le navigateur', options: { bloque: true, langues: ['en-US'] }, langue: 'en' },
  { nom: 'stockage bloqué, adresse', options: { bloque: true, recherche: '?lang=en', langues: ['fr'] }, langue: 'en' },
]

describe('le script de index.html', () => {
  for (const cas of CAS) {
    it(`fait le même choix que choisirLangue : ${cas.nom}`, () => {
      const simulation = simuler(cas.options)
      const decision = attendu(simulation, cas.options)
      executer(simulation)
      expect(decision).toBe(cas.langue)
      expect(simulation.racine.lang).toBe(ATTRIBUT_LANG[cas.langue])
    })
  }

  it('mémorise la langue de l’adresse comme un choix', () => {
    const simulation = simuler({ recherche: '?lang=en', langues: ['fr-FR'] })
    executer(simulation)
    expect(simulation.stockage.get(CLE_LANGUE)).toBe('en')
  })

  it('ne mémorise rien tant que l’utilisateur n’a pas choisi', () => {
    const simulation = simuler({ langues: ['en-US'] })
    executer(simulation)
    expect(simulation.stockage.has(CLE_LANGUE)).toBe(false)
  })

  it('retire `lang` de l’adresse, et garde le reste', () => {
    const simulation = simuler({
      recherche: '?x=1&lang=en',
      chemin: '/methodologie',
      fragment: '#cvar',
    })
    executer(simulation)
    expect(simulation.adresses).toEqual(['/methodologie?x=1#cvar'])

    const seule = simuler({ recherche: '?lang=fr', chemin: '/portefeuilles' })
    executer(seule)
    expect(seule.adresses).toEqual(['/portefeuilles'])
  })

  it('ne touche pas à une adresse sans `lang`', () => {
    const simulation = simuler({ recherche: '?x=1', langues: ['fr'] })
    executer(simulation)
    expect(simulation.adresses).toEqual([])
  })
})

describe('la page', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('React lit la langue que le script a posée', () => {
    const simulation = simuler({})
    vi.stubGlobal('document', simulation.globaux.document)
    simulation.racine.lang = 'en-US'
    expect(langueDeLaPage()).toBe('en')
    simulation.racine.lang = 'fr'
    expect(langueDeLaPage()).toBe('fr')
  })

  it('un choix pose l’attribut et se mémorise', () => {
    const simulation = simuler({})
    vi.stubGlobal('document', simulation.globaux.document)
    vi.stubGlobal('localStorage', simulation.globaux.localStorage)
    appliquerLangue('en')
    expect(simulation.racine.lang).toBe('en-US')
    expect(simulation.stockage.get(CLE_LANGUE)).toBe('en')
    expect(langueMemorisee()).toBe('en')
  })

  it('stockage bloqué : la langue s’applique quand même, sans lever', () => {
    const simulation = simuler({ bloque: true })
    vi.stubGlobal('document', simulation.globaux.document)
    vi.stubGlobal('localStorage', simulation.globaux.localStorage)
    expect(() => appliquerLangue('en')).not.toThrow()
    expect(simulation.racine.lang).toBe('en-US')
    expect(langueMemorisee()).toBeNull()
  })
})
