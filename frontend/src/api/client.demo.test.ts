/**
 * Le client dans le build de démonstration (mode Vite `demo`).
 *
 * `DEMO` est une constante lue au chargement du module : chaque test relit
 * donc `client.ts` dans le mode voulu. Ce qui est tenu ici :
 *
 * - une lecture demande le fichier de la réponse enregistrée, dans le dossier
 *   de sa langue, et jamais l'API ;
 * - un échec se dit avec les mots de la démonstration. « L'API ne répond
 *   pas. La démarrer : python -m backend.api » n'a aucun sens pour un
 *   visiteur, et un hébergeur statique rend sa page d'accueil avec un 200
 *   pour un fichier absent : ni le statut ni « corps vide » ne le diraient.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LIBELLES } from '../contenu/libelles'
import { DEMO, titreSourceInjoignable } from './client'

type Client = typeof import('./client')

async function clientEnMode(mode: string): Promise<Client> {
  vi.stubEnv('MODE', mode)
  vi.resetModules()
  return import('./client')
}

const clientDeDemo = () => clientEnMode('demo')

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.resetModules()
})

/** Une réponse telle que `fetch` la rend : un statut, et un corps en texte. */
function repondre(statut: number, corps: string) {
  const espion = vi.fn(async (_adresse: string, _init?: RequestInit) => ({
    ok: statut >= 200 && statut < 300,
    status: statut,
    text: async () => corps,
  }))
  vi.stubGlobal('fetch', espion)
  return espion
}

const PAGE_D_ACCUEIL = '<!doctype html><html lang="fr"><head><title>Portfolio Risk Engine</title></head></html>'

/** Ce qu'un visiteur de la démonstration ne doit jamais lire. */
function textesDeLApi(langue: 'fr' | 'en'): string[] {
  const api = LIBELLES[langue].api
  return [api.serveurInjoignable, api.corpsVide, api.reponseInattendue(404), api.reponseInattendue(200)]
}

describe('le mode', () => {
  it('est faux hors du build de démonstration, tests compris', async () => {
    expect(DEMO).toBe(false)
    expect((await clientEnMode('production')).DEMO).toBe(false)
    expect((await clientEnMode('development')).DEMO).toBe(false)
  })

  it('est vrai dans le mode « demo »', async () => {
    expect((await clientDeDemo()).DEMO).toBe(true)
  })
})

describe('les lectures de la démonstration', () => {
  it('demandent le fichier de la réponse, dans le dossier de la langue', async () => {
    const client = await clientDeDemo()
    const espion = repondre(200, '{"x": 1}')
    await client.getDisclaimer('fr')
    await client.getDisclaimer('en')
    await client.getPortfolios('fr')
    await client.getPortfolios('en')
    await client.getAnalysis(2, 'fr')
    await client.getAnalysis(3, 'en')
    expect(espion.mock.calls.map(([adresse]) => adresse)).toEqual([
      '/donnees/fr/disclaimer.json',
      '/donnees/en/disclaimer.json',
      '/donnees/fr/portfolios.json',
      '/donnees/en/portfolios.json',
      '/donnees/fr/portfolios/2/analysis.json',
      '/donnees/en/portfolios/3/analysis.json',
    ])
  })

  it('ne nomment jamais l’API, n’écrivent rien et ne portent pas « ?lang »', async () => {
    const client = await clientDeDemo()
    const espion = repondre(200, '{"x": 1}')
    await client.getPortfolios('fr')
    await client.getAnalysis(1, 'en')
    for (const [adresse, init] of espion.mock.calls) {
      expect(adresse).not.toContain('/api')
      expect(adresse).not.toContain('lang=')
      expect(init?.method).toBeUndefined()
      expect(init?.body).toBeUndefined()
    }
  })

  it('rendent le document enregistré', async () => {
    const client = await clientDeDemo()
    repondre(200, '[{"id": 1, "name": "Démo"}]')
    await expect(client.getPortfolios('fr')).resolves.toEqual([{ id: 1, name: 'Démo' }])
    repondre(200, '{"title": "Avant d\'utiliser", "sections": []}')
    await expect(client.getDisclaimer('fr')).resolves.toEqual({ title: "Avant d'utiliser", sections: [] })
  })

  it('hors démonstration, la même lecture appelle l’API', async () => {
    const client = await clientEnMode('production')
    const espion = repondre(200, '[{"id": 1}]')
    await client.getPortfolios('en')
    expect(espion.mock.calls[0]?.[0]).toBe('/api/portfolios?lang=en')
  })
})

describe('les échecs de la démonstration', () => {
  it.each(['fr', 'en'] as const)('une requête qui n’aboutit pas (%s)', async (langue) => {
    const client = await clientDeDemo()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const erreur = await client.getDisclaimer(langue).catch((e: unknown) => e)
    expect(erreur).toBeInstanceOf(client.ApiErreur)
    expect(erreur).toMatchObject({ statut: 0, detail: LIBELLES[langue].demo.injoignable })
    // Aucune commande à recopier : il n'y a pas de serveur à démarrer.
    expect((erreur as InstanceType<Client['ApiErreur']>).segments.every((s) => s.genre === 'texte')).toBe(true)
  })

  const ILLISIBLES: ReadonlyArray<readonly [string, number, string]> = [
    ['un 404', 404, 'Not Found'],
    // Un refus qui se lit comme du JSON n'est pas la réponse enregistrée.
    ['un 404 dont le corps est du JSON', 404, '{"detail": "Not Found"}'],
    ['un 500', 500, ''],
    ['la page d’accueil rendue avec un 200 à la place du fichier', 200, PAGE_D_ACCUEIL],
    ['un corps vide', 200, ''],
    ['un document tronqué', 200, '[{"id": 1, "name": "Dé'],
    ['une liste vide', 200, '[]'],
    ['un nul', 200, 'null'],
    ['un nombre', 200, '42'],
  ]

  it.each(ILLISIBLES)('%s se dit « fichier illisible », dans les deux langues', async (_cas, statut, corps) => {
    const client = await clientDeDemo()
    for (const langue of ['fr', 'en'] as const) {
      repondre(statut, corps)
      const erreur = await client.getPortfolios(langue).catch((e: unknown) => e)
      expect(erreur).toBeInstanceOf(client.ApiErreur)
      const refus = erreur as InstanceType<Client['ApiErreur']>
      expect(refus.detail).toBe(LIBELLES[langue].demo.fichierIllisible(`${langue}/portfolios.json`))
      // Jamais le statut d'un refus d'API : un 409 se lirait « insuffisant ».
      expect(refus.statut).toBe(0)
      expect(refus.problems).toEqual([])
      // Le nom du fichier sort de la phrase, en code.
      expect(refus.segments).toContainEqual({ genre: 'litteral', contenu: `${langue}/portfolios.json` })
    }
  })

  it('aucun échec ne parle de l’API, ni d’une commande, ni de « doctype »', async () => {
    const client = await clientDeDemo()
    const details: string[] = []
    for (const langue of ['fr', 'en'] as const) {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => {
          throw new TypeError('Failed to fetch')
        }),
      )
      details.push(await client.getAnalysis(1, langue).then(String, (e: Error) => e.message))
      for (const [, statut, corps] of ILLISIBLES) {
        repondre(statut, corps)
        details.push(await client.getAnalysis(1, langue).then(String, (e: Error) => e.message))
      }
      for (const detail of details) expect(textesDeLApi(langue)).not.toContain(detail)
    }
    expect(details).toHaveLength(2 * (1 + ILLISIBLES.length))
    for (const detail of details) {
      expect(detail).not.toMatch(/\bAPI\b/)
      expect(detail).not.toContain('python')
      expect(detail).not.toContain('doctype')
    }
  })

  it('le fichier d’une analyse est nommé avec son numéro', async () => {
    const client = await clientDeDemo()
    repondre(200, PAGE_D_ACCUEIL)
    await expect(client.getAnalysis(3, 'en')).rejects.toMatchObject({
      detail: LIBELLES.en.demo.fichierIllisible('en/portfolios/3/analysis.json'),
    })
  })
})

describe('le titre de la page quand le démarrage échoue', () => {
  it('nomme l’API hors démonstration, comme avant', () => {
    expect(titreSourceInjoignable('fr')).toBe('API injoignable')
    expect(titreSourceInjoignable('en')).toBe('API unreachable')
  })

  it('nomme la démonstration dans son build', async () => {
    const client = await clientDeDemo()
    expect(client.titreSourceInjoignable('fr')).toBe('Démonstration indisponible')
    expect(client.titreSourceInjoignable('en')).toBe('Demonstration unavailable')
  })
})

describe('les textes d’échec, tels qu’ils sont validés', () => {
  it('en français', () => {
    expect(LIBELLES.fr.demo.injoignable).toBe(
      "Les données de la démonstration n'ont pas pu être chargées. Vérifier la connexion, puis recharger la page.",
    )
    expect(LIBELLES.fr.demo.fichierIllisible('fr/portfolios.json')).toBe(
      "Le fichier `fr/portfolios.json` de la démonstration manque ou n'est pas lisible. Recharger la page.",
    )
  })

  it('en anglais', () => {
    expect(LIBELLES.en.demo.injoignable).toBe(
      'The demonstration data could not be loaded. Check the connection, then reload the page.',
    )
    expect(LIBELLES.en.demo.fichierIllisible('en/portfolios.json')).toBe(
      'The demonstration file `en/portfolios.json` is missing or cannot be read. Reload the page.',
    )
  })
})
