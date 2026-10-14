/**
 * Le build de démonstration : ce que son greffon ajoute, et ce qu'il refuse.
 *
 * Trois gardes, chacune vue échouer : l'export relu contre son manifeste, la
 * garde du bundle (ni API ni écriture), et la configuration de Vite, où le
 * greffon et le dossier `dist-demo` n'existent que dans le mode `demo`.
 */
import { createHash } from 'node:crypto'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'

import type { Plugin, UserConfig } from 'vite'
import { afterEach, describe, expect, it } from 'vitest'

import configuration from '../../vite.config'
import { DATE_DE_LA_DEMO, PORTEFEUILLES_DE_LA_DEMO } from '../contenu/demo'
import { LANGUES } from '../lib/langue'
import {
  BALISE_ROBOTS,
  COMMANDE_D_EXPORT,
  CONSTANTE_DU_SERVEUR,
  demonstration,
  EN_TETES,
  fautesDuBuild,
  fautesDuBundle,
  fichiersAttendus,
  LANGUES_DE_L_EXPORT,
  lireExport,
  lireLeServeur,
  MANIFESTE,
  ORIGINES_ADMISES,
  VARIABLE_DU_SERVEUR,
} from './demoAuBuild'

// ═════════════════════════════════════════════════ La garde du bundle ══

describe('la garde du bundle', () => {
  it('voit la chaîne de l’API, quelle que soit sa citation', () => {
    expect(fautesDuBundle('const ve=`/api`;fetch(ve)')).toEqual(['la chaîne /api'])
    expect(fautesDuBundle('fetch("/api/portfolios?lang=fr")')).not.toEqual([])
    expect(fautesDuBundle("proxy: { '/api': {} }")).not.toEqual([])
  })

  it('voit chaque méthode d’écriture de l’application, et un second POST', () => {
    // Un POST seul est l'envoi au serveur public : le compte se tient sur le
    // build entier (`fautesDuBuild`, contrôle c).
    expect(fautesDuBundle('fetch(u,{method:`POST`,body:b})')).toEqual([])
    expect(fautesDuBundle('a(`POST`);b("POST")')).toEqual(['la méthode d\'écriture POST, citée 2 fois'])
    expect(fautesDuBundle('fetch(u,{method:"PUT"})')).not.toEqual([])
    expect(fautesDuBundle("fetch(u,{method:'DELETE'})")).not.toEqual([])
    expect(fautesDuBundle('x={methode:`PATCH`}')).not.toEqual([])
    expect(fautesDuBundle('a(`POST`);b(`POST`);c(`PUT`)')).toHaveLength(2)
  })

  it('laisse passer un fichier qui ne fait que lire ses données', () => {
    expect(fautesDuBundle('fetch(`/donnees/fr/portfolios.json`,{headers:{Accept:`application/json`}})')).toEqual([])
    // Un mot en capitales dans une phrase n'est pas une méthode citée.
    expect(fautesDuBundle('`Rien à POSTER ici` ; "DELETED" ; `PUTATIF`')).toEqual([])
    expect(fautesDuBundle('`python -m backend.api` ; rapide ; `/portefeuilles/1`')).toEqual([])
    expect(fautesDuBundle('')).toEqual([])
  })
})

// ════════════════════════════════════════════════════════════ L'export ══

const dossiers: string[] = []

afterEach(() => {
  for (const dossier of dossiers.splice(0)) rmSync(dossier, { recursive: true, force: true })
})

interface Options {
  readonly date?: string
  readonly portefeuilles?: number
  /** Les chemins listés par le manifeste ; par défaut, ceux que lit la démonstration. */
  readonly chemins?: readonly string[]
}

/** Un export de fantaisie, cohérent avec son manifeste. */
function ecrireExport(options: Options = {}): string {
  const dossier = mkdtempSync(join(tmpdir(), 'export-demo-'))
  dossiers.push(dossier)
  const portefeuilles = options.portefeuilles ?? PORTEFEUILLES_DE_LA_DEMO
  const chemins = options.chemins ?? fichiersAttendus(portefeuilles)
  const fichiers = chemins.map((chemin) => {
    const contenu = Buffer.from(JSON.stringify({ fichier: chemin }), 'utf-8')
    mkdirSync(dirname(join(dossier, chemin)), { recursive: true })
    writeFileSync(join(dossier, chemin), contenu)
    return { chemin, octets: contenu.length, sha256: createHash('sha256').update(contenu).digest('hex') }
  })
  const manifeste = {
    date_gel: options.date ?? DATE_DE_LA_DEMO,
    portefeuilles: Array.from({ length: portefeuilles }, (_, rang) => ({ id: rang + 1 })),
    fichiers,
  }
  writeFileSync(join(dossier, MANIFESTE), JSON.stringify(manifeste), 'utf-8')
  return dossier
}

describe('les fichiers que lit la démonstration', () => {
  it('sont dans les langues du site', () => {
    expect([...LANGUES_DE_L_EXPORT]).toEqual([...LANGUES])
  })

  it('sont ceux de `client.ts`, dans les deux langues, pour chaque portefeuille', () => {
    expect(fichiersAttendus(2)).toEqual([
      'en/csv-format.json',
      'en/disclaimer.json',
      'en/portfolios.json',
      'en/portfolios/1/analysis.json',
      'en/portfolios/2/analysis.json',
      'en/securities.json',
      'fr/csv-format.json',
      'fr/disclaimer.json',
      'fr/portfolios.json',
      'fr/portfolios/1/analysis.json',
      'fr/portfolios/2/analysis.json',
      'fr/securities.json',
    ])
    expect(fichiersAttendus(PORTEFEUILLES_DE_LA_DEMO)).toHaveLength(2 * (4 + PORTEFEUILLES_DE_LA_DEMO))
  })
})

describe('l’export relu au build', () => {
  it('rend les fichiers du manifeste, tels quels, et pas le manifeste', () => {
    const dossier = ecrireExport()
    const fichiers = lireExport(dossier)
    expect([...fichiers.keys()].sort()).toEqual(fichiersAttendus(PORTEFEUILLES_DE_LA_DEMO))
    expect(fichiers.get('fr/portfolios.json')?.toString('utf-8')).toBe('{"fichier":"fr/portfolios.json"}')
    expect(fichiers.has(MANIFESTE)).toBe(false)
  })

  it('sans export, dit la commande qui l’écrit', () => {
    const vide = mkdtempSync(join(tmpdir(), 'export-demo-'))
    dossiers.push(vide)
    expect(() => lireExport(vide)).toThrow(/absent/)
    expect(() => lireExport(vide)).toThrow(COMMANDE_D_EXPORT)
  })

  it('refuse un fichier retouché après l’export', () => {
    const dossier = ecrireExport()
    writeFileSync(join(dossier, 'fr/portfolios/1/analysis.json'), '{"fichier":"autre chose"}')
    expect(() => lireExport(dossier)).toThrow(/fr\/portfolios\/1\/analysis\.json.*manifeste/)
  })

  it('refuse un fichier de même taille mais d’un autre contenu', () => {
    const dossier = ecrireExport()
    // « en/disclaimer.json » et « fr/disclaimer.json » ont la même longueur.
    writeFileSync(join(dossier, 'en/disclaimer.json'), '{"fichier":"fr/disclaimer.json"}')
    expect(() => lireExport(dossier)).toThrow(/en\/disclaimer\.json/)
  })

  it('refuse un fichier listé mais absent', () => {
    const dossier = ecrireExport()
    rmSync(join(dossier, 'en/portfolios.json'))
    expect(() => lireExport(dossier)).toThrow(/en\/portfolios\.json.*manque/)
  })

  it('refuse un manifeste qui ne liste pas exactement ce que lit la démonstration', () => {
    const attendus = fichiersAttendus(PORTEFEUILLES_DE_LA_DEMO)
    // Un fichier de moins : une analyse que le client demanderait en vain.
    expect(() => lireExport(ecrireExport({ chemins: attendus.slice(0, -1) }))).toThrow(/exactement/)
    // Un fichier de plus : ce que la démonstration ne lit pas ne sort pas.
    expect(() => lireExport(ecrireExport({ chemins: [...attendus, 'fr/meta.json'] }))).toThrow(
      /exactement/,
    )
  })

  it('refuse un export dont la date n’est pas celle de la mention', () => {
    expect(() => lireExport(ecrireExport({ date: '2026-09-10' }))).toThrow(/2026-09-10.*contenu\/demo\.ts/)
  })

  it('refuse un export dont le nombre de portefeuilles n’est pas celui de la mention', () => {
    const quatre = ecrireExport({ portefeuilles: PORTEFEUILLES_DE_LA_DEMO + 1 })
    expect(() => lireExport(quatre)).toThrow(/portefeuilles.*contenu\/demo\.ts/)
    // Le même export se lit quand la mention dit ce nombre.
    expect(
      lireExport(quatre, { date: DATE_DE_LA_DEMO, portefeuilles: PORTEFEUILLES_DE_LA_DEMO + 1 }).size,
    ).toBe(2 * (4 + PORTEFEUILLES_DE_LA_DEMO + 1))
  })

  it('refuse un manifeste illisible', () => {
    const dossier = ecrireExport()
    writeFileSync(join(dossier, MANIFESTE), '{"date_gel": ')
    expect(() => lireExport(dossier)).toThrow(/ne se lit pas/)
    writeFileSync(join(dossier, MANIFESTE), '{"date_gel": "2026-09-09"}')
    expect(() => lireExport(dossier)).toThrow(/forme attendue/)
  })
})

// ══════════════════════════════════════════════════════════ Le greffon ══

describe('le greffon', () => {
  it('ne sert qu’au build', () => {
    expect(demonstration('nulle-part').apply).toBe('build')
  })

  it('interdit l’indexation : la balise, et l’en-tête sur toute adresse', () => {
    expect(BALISE_ROBOTS).toEqual({ name: 'robots', content: 'noindex' })
    expect(EN_TETES).toBe('/*\n  X-Robots-Tag: noindex\n')
    const greffon = demonstration('nulle-part')
    const transformer = greffon.transformIndexHtml as () => unknown[]
    expect(transformer()[0]).toEqual({
      tag: 'meta',
      attrs: { name: 'robots', content: 'noindex' },
      injectTo: 'head',
    })
  })
})

// ═══════════════════════════════════════════════ La configuration de Vite ══

const NOM_DU_GREFFON = 'mx-risk-demonstration'

function configurationDe(mode: string): UserConfig {
  const lue = configuration as unknown as (env: { mode: string; command: 'build' }) => UserConfig
  return lue({ mode, command: 'build' })
}

function greffons(config: UserConfig): string[] {
  return (config.plugins ?? [])
    .flat(4)
    .filter((greffon): greffon is Plugin => typeof greffon === 'object' && greffon !== null && 'name' in greffon)
    .map((greffon) => greffon.name)
}

describe('les deux builds', () => {
  it('le build ordinaire écrit `dist`, sans rien de la démonstration', () => {
    for (const mode of ['production', 'development']) {
      const config = configurationDe(mode)
      expect(config.build?.outDir).toBe('dist')
      expect(greffons(config)).not.toContain(NOM_DU_GREFFON)
    }
  })

  it('le build de démonstration écrit `dist-demo`, avec son greffon', () => {
    const config = configurationDe('demo')
    expect(config.build?.outDir).toBe('dist-demo')
    expect(greffons(config)).toContain(NOM_DU_GREFFON)
  })

  it('les deux gardent les coupures de la méthodologie', () => {
    for (const mode of ['production', 'demo']) {
      expect(greffons(configurationDe(mode))).toContain('mx-risk-coupures-de-la-methodologie')
    }
  })
})

// ═══════════════════════════════════ La garde du build entier (chantier 9.6) ══

describe('la garde du build entier', () => {
  const SERVEUR = 'https://serveur.exemple'
  const ENTREE = {
    nom: 'index.js',
    code: `const s="${SERVEUR}";fetch(s+"/health");fetch(s+"/analysis",{method:\`POST\`});a="http://www.w3.org/2000/svg"`,
  }
  const ANALYSE = { nom: 'Analyse.js', code: 'b="http://www.w3.org/1999/xlink";c="https://react.dev/errors/"' }

  it('laisse passer un build qui n’a qu’un POST, dans le fichier du serveur, et les origines admises', () => {
    expect(fautesDuBuild([ENTREE, ANALYSE], SERVEUR)).toEqual([])
    expect(Object.keys(ORIGINES_ADMISES).sort()).toEqual([
      'http://www.w3.org',
      'https://github.com',
      'https://react.dev',
      'https://www.linkedin.com',
    ])
  })

  it('a et b : /api ou une écriture de l’application, dans n’importe quel fichier', () => {
    const fautes = fautesDuBuild([ENTREE, { nom: 'Analyse.js', code: 'fetch("/api/portfolios",{method:"PUT"})' }], SERVEUR)
    expect(fautes.join(' ')).toContain('Analyse.js')
    expect(fautes.join(' ')).toContain('/api')
    expect(fautes.join(' ')).toContain('"PUT"')
  })

  it('c : un second POST, dans le même fichier ou dans un autre', () => {
    expect(fautesDuBuild([{ ...ENTREE, code: `${ENTREE.code};x(\`POST\`)` }, ANALYSE], SERVEUR)).not.toEqual([])
    const ailleurs = fautesDuBuild([ENTREE, { nom: 'Analyse.js', code: 'fetch(u,{method:"POST"})' }], SERVEUR)
    expect(ailleurs.join(' ')).toContain('2 fichiers')
  })

  it('c : un POST dans un fichier qui ne porte pas l’adresse du serveur', () => {
    const fautes = fautesDuBuild(
      [{ nom: 'index.js', code: `const s="${SERVEUR}"` }, { nom: 'Analyse.js', code: 'fetch(u,{method:`POST`})' }],
      SERVEUR,
    )
    expect(fautes.join(' ')).toContain('Analyse.js')
    expect(fautes.join(' ')).toContain("ne porte pas l'adresse du serveur public")
  })

  it('d : une seconde adresse de serveur, ou une adresse écrite en dur', () => {
    const fautes = fautesDuBuild([ENTREE, { nom: 'Analyse.js', code: 'fetch("https://autre.exemple/analysis")' }], SERVEUR)
    expect(fautes.join(' ')).toContain('https://autre.exemple')
    expect(fautesDuBuild([ENTREE, { nom: 'x.js', code: 'u="http://127.0.0.1:8000/api"' }], SERVEUR).join(' ')).toContain(
      'http://127.0.0.1:8000',
    )
  })

  it('d : l’adresse du serveur public doit y être', () => {
    const fautes = fautesDuBuild([{ nom: 'index.js', code: 'fetch("/donnees/fr/portfolios.json")' }], SERVEUR)
    expect(fautes.join(' ')).toContain(`(${SERVEUR}) n'est dans aucun fichier`)
  })
})

// ═════════════════════════════════════════ L'adresse du serveur public (9.6) ══

describe('l’adresse du serveur public', () => {
  it('se lit dans MX_RISK_SERVEUR_PUBLIC, et elle est obligatoire', () => {
    expect(VARIABLE_DU_SERVEUR).toBe('MX_RISK_SERVEUR_PUBLIC')
    expect(() => lireLeServeur(undefined)).toThrow(/obligatoire/)
    expect(() => lireLeServeur('')).toThrow(/obligatoire/)
  })

  it('une origine `https://hôte` est rendue telle quelle', () => {
    expect(lireLeServeur('https://portfolio-risk-engine-lemaxoux.onrender.com')).toBe(
      'https://portfolio-risk-engine-lemaxoux.onrender.com',
    )
  })

  it('pour un essai sur le poste, `http://127.0.0.1:<port>` et `http://localhost:<port>`', () => {
    expect(lireLeServeur('http://127.0.0.1:8002')).toBe('http://127.0.0.1:8002')
    expect(lireLeServeur('http://localhost:8003')).toBe('http://localhost:8003')
  })

  it('refuse tout le reste : un chemin, une barre finale, un autre hôte en clair, sans port', () => {
    for (const valeur of [
      'https://serveur.exemple/',
      'https://serveur.exemple/api',
      'http://serveur.exemple',
      'http://exemple.test:8002',
      'http://127.0.0.1',
      'http://127.0.0.1:8002/',
      'serveur.exemple',
      'ftp://serveur.exemple',
    ]) {
      expect(() => lireLeServeur(valeur), valeur).toThrow(VARIABLE_DU_SERVEUR)
    }
  })

  it('le greffon la pose dans le code au build, et seulement là', () => {
    // Construire le greffon ne lit pas la variable : la configuration se lit
    // sans elle (les tests de la configuration de Vite).
    const sans = demonstration('nulle-part')
    expect(sans.name).toBe('mx-risk-demonstration')
    const config = sans.config as () => unknown
    expect(() => config()).toThrow(/obligatoire/)

    const avec = demonstration('nulle-part', undefined, 'https://serveur.exemple').config as () => {
      define: Record<string, string>
    }
    expect(avec().define).toEqual({
      [CONSTANTE_DU_SERVEUR]: JSON.stringify('https://serveur.exemple'),
    })
    expect(CONSTANTE_DU_SERVEUR).toBe('import.meta.env.MX_RISK_SERVEUR_PUBLIC')
  })
})
