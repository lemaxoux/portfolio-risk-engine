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

// ═══════════════════════════════════════════════ Le serveur public (9.6) ══

describe('le serveur public du site (chantier 9.6)', () => {
  const SERVEUR = 'https://serveur.exemple'
  const SANTE = '{"status":"ready","freeze_date":"2026-09-09","database_sha256":"a","code_sha256":"b"}'
  const PAGE_D_ATTENTE = '<!doctype html><title>Render - Application loading</title>'
  const POSITIONS = [{ ticker: 'KO', quantity: 120, cost_basis: null, line: 1 }]

  /** Le client du site, et le module d'acceptation qu'il lit : les mêmes instances. */
  async function site() {
    vi.stubEnv('MODE', 'demo')
    vi.stubEnv('MX_RISK_SERVEUR_PUBLIC', SERVEUR)
    vi.resetModules()
    const client = await import('./client')
    const acceptation = await import('../lib/acceptation')
    return { client, acceptation }
  }

  /** La preuve d'un texte accepté dans cette page. */
  function preuve(acceptation: typeof import('../lib/acceptation'), langue: 'fr' | 'en') {
    acceptation.memoriserAcceptation(`Texte accepté (${langue})`, langue)
    return acceptation.preuveDAcceptation(`Texte accepté (${langue})`, langue)
  }

  afterEach(() => {
    vi.useRealTimers()
  })

  it('le réveil est un GET /health nu : ni corps, ni paramètre, ni en-tête, ni cookie, ni référent', async () => {
    const { client } = await site()
    const espion = repondre(200, SANTE)
    client.reveillerLeServeur()
    await vi.waitFor(() => expect(espion).toHaveBeenCalledOnce())
    const [adresse, init] = espion.mock.calls[0] ?? []
    expect(adresse).toBe(`${SERVEUR}/health`)
    expect(init?.method).toBeUndefined()
    expect(init?.body).toBeUndefined()
    expect(init?.headers).toBeUndefined()
    expect(init).toMatchObject({ credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store' })
  })

  it('un serveur éveillé : l’attente finit au premier essai, et rien n’est dit', async () => {
    vi.useFakeTimers()
    const { client } = await site()
    const espion = repondre(200, SANTE)
    const dit = vi.fn()
    await client.attendreLeServeur('fr', dit)
    await vi.advanceTimersByTimeAsync(5_000)
    expect(espion).toHaveBeenCalledOnce()
    expect(dit).not.toHaveBeenCalled()
  })

  it('une réponse qui n’est pas le JSON du serveur compte comme « pas encore réveillé »', async () => {
    vi.useFakeTimers()
    const { client } = await site()
    const reponses = [
      { ok: false, status: 503, text: async () => PAGE_D_ATTENTE },
      { ok: true, status: 200, text: async () => PAGE_D_ATTENTE },
      { ok: true, status: 200, text: async () => SANTE },
    ]
    const espion = vi.fn(async (_adresse: string, _init?: RequestInit) => reponses.shift())
    vi.stubGlobal('fetch', espion)
    const dit = vi.fn()
    const attente = client.attendreLeServeur('en', dit)
    await vi.advanceTimersByTimeAsync(10_000)
    await expect(attente).resolves.toBeUndefined()
    expect(espion).toHaveBeenCalledTimes(3)
    // Dit une fois, dès le premier échec.
    expect(dit).toHaveBeenCalledOnce()
  })

  it('un essai qui ne rend rien se dit au bout du silence', async () => {
    vi.useFakeTimers()
    const { client } = await site()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_adresse: string, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => reject(new DOMException('Abandon', 'AbortError')))
          }),
      ),
    )
    const dit = vi.fn()
    const attente = client.attendreLeServeur('fr', dit).catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(999)
    expect(dit).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(2)
    expect(dit).toHaveBeenCalledOnce()
    await vi.advanceTimersByTimeAsync(160_000)
    expect(await attente).toMatchObject({ statut: 0, detail: LIBELLES.fr.serveur.sansReponse })
  })

  it('passé la durée du réveil : « sans réponse », sans cause', async () => {
    vi.useFakeTimers()
    const { client } = await site()
    const espion = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', espion)
    const attente = client.attendreLeServeur('en', () => undefined).catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(160_000)
    const erreur = await attente
    expect(erreur).toBeInstanceOf(client.ApiErreur)
    expect(erreur).toMatchObject({ statut: 0, detail: LIBELLES.en.serveur.sansReponse })
    // Un essai toutes les trois secondes, pendant cent cinquante secondes au plus.
    expect(espion.mock.calls.length).toBeGreaterThan(20)
    expect(espion.mock.calls.length).toBeLessThanOrEqual(51)
  })

  it('un serveur qui retient les essais : cent cinquante secondes d’attente, puis « sans réponse »', async () => {
    // Ce que fait l'hébergeur pendant le réveil : la requête reste sans
    // réponse, jusqu'à ce que l'essai l'abandonne.
    vi.useFakeTimers()
    const { client } = await site()
    const espion = vi.fn(
      (_adresse: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Abandon', 'AbortError')))
        }),
    )
    vi.stubGlobal('fetch', espion)
    let fin: unknown = 'en attente'
    const attente = client.attendreLeServeur('fr', () => undefined).then(
      () => (fin = 'réveillé'),
      (e: unknown) => (fin = e),
    )
    await vi.advanceTimersByTimeAsync(149_999)
    expect(fin).toBe('en attente')
    // Un essai de quinze secondes, puis trois secondes de pause : neuf essais
    // partis, le dernier à 144 s, borné à ce qui restait.
    expect(espion).toHaveBeenCalledTimes(9)
    await vi.advanceTimersByTimeAsync(1)
    await attente
    expect(fin).toBeInstanceOf(client.ApiErreur)
    expect(fin).toMatchObject({ statut: 0, detail: LIBELLES.fr.serveur.sansReponse })
  })

  it('trois essais retenus puis abandonnés, le quatrième en 200 : l’attente finit là', async () => {
    // La suite vue par Cowork dans Chrome le 2026-10-14, serveur endormi.
    vi.useFakeTimers()
    const { client } = await site()
    let essais = 0
    const espion = vi.fn((_adresse: string, init?: RequestInit) => {
      essais += 1
      if (essais === 4) return Promise.resolve({ ok: true, status: 200, text: async () => SANTE })
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Abandon', 'AbortError')))
      })
    })
    vi.stubGlobal('fetch', espion)
    const dit = vi.fn()
    const attente = client.attendreLeServeur('en', dit)
    await vi.advanceTimersByTimeAsync(60_000)
    await expect(attente).resolves.toBeUndefined()
    expect(espion).toHaveBeenCalledTimes(4)
    expect(dit).toHaveBeenCalledOnce()
  })

  it('sans preuve d’acceptation de sa langue, rien ne part', async () => {
    const { client, acceptation } = await site()
    const espion = repondre(200, '{}')
    const fichier = new File(['ticker;quantity\nKO;1\n'], 'p.csv', { type: 'text/csv' })
    await expect(client.analyserLeSaisi(POSITIONS, 'fr', null)).rejects.toThrow()
    await expect(client.lireUnFichier(fichier, 'fr', null)).rejects.toThrow()
    // Une preuve de l'autre langue, ou un objet de même forme, n'en sont pas.
    await expect(client.analyserLeSaisi(POSITIONS, 'fr', preuve(acceptation, 'en'))).rejects.toThrow()
    await expect(
      client.analyserLeSaisi(POSITIONS, 'fr', { langue: 'fr', empreinte: acceptation.empreinte('x') }),
    ).rejects.toThrow()
    expect(espion).not.toHaveBeenCalled()
  })

  it('l’analyse part en POST, la composition dans le corps, la langue dans l’adresse', async () => {
    const { client, acceptation } = await site()
    const espion = repondre(200, '{"as_of": "2026-09-09"}')
    await expect(client.analyserLeSaisi(POSITIONS, 'en', preuve(acceptation, 'en'))).resolves.toEqual({
      as_of: '2026-09-09',
    })
    const [adresse, init] = espion.mock.calls[0] ?? []
    expect(adresse).toBe(`${SERVEUR}/analysis?lang=en`)
    expect(init?.method).toBe('POST')
    // Aucun nom de portefeuille : les lignes, et rien d'autre.
    expect(JSON.parse(String(init?.body))).toEqual({ positions: POSITIONS })
    expect(init?.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(init).toMatchObject({ credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store' })
  })

  it('le fichier part en multipart vers /csv, sous le champ « file »', async () => {
    const { client, acceptation } = await site()
    const espion = repondre(200, '{"positions": [], "source": {}}')
    const fichier = new File(['ticker;quantity\nKO;1\n'], 'p.csv', { type: 'text/csv' })
    await client.lireUnFichier(fichier, 'fr', preuve(acceptation, 'fr'))
    const [adresse, init] = espion.mock.calls[0] ?? []
    expect(adresse).toBe(`${SERVEUR}/csv?lang=fr`)
    expect(init?.method).toBe('POST')
    expect(init?.body).toBeInstanceOf(FormData)
    expect((init?.body as FormData).get('file')).toBeInstanceOf(File)
    // Le navigateur pose lui-même l'en-tête du multipart, avec sa frontière.
    expect(init?.headers).toEqual({})
  })

  it('un refus garde les phrases du serveur, telles quelles', async () => {
    const { client, acceptation } = await site()
    const corps = {
      detail: '2 lignes refusées, le portefeuille n’a pas été analysé.',
      problems: [{ line: 2, field: 'ticker', value: 'XYZ', problem: 'XYZ n’est pas un titre de la base.' }],
    }
    repondre(422, JSON.stringify(corps))
    const erreur = await client.analyserLeSaisi(POSITIONS, 'fr', preuve(acceptation, 'fr')).catch((e: unknown) => e)
    expect(erreur).toMatchObject({ statut: 422, detail: corps.detail, problems: corps.problems })
    expect(client.estUnRefus(erreur as InstanceType<Client['ApiErreur']>)).toBe(true)
  })

  it('une limite atteinte se réessaie : ce n’est pas un refus de la composition', async () => {
    const { client, acceptation } = await site()
    repondre(429, '{"detail": "Trop de demandes depuis cette adresse.", "problems": []}')
    const erreur = await client.analyserLeSaisi(POSITIONS, 'fr', preuve(acceptation, 'fr')).catch((e: unknown) => e)
    expect(erreur).toMatchObject({ statut: 429, detail: 'Trop de demandes depuis cette adresse.' })
    expect(client.estUnRefus(erreur as InstanceType<Client['ApiErreur']>)).toBe(false)
  })

  it('une réponse sans en-tête CORS, ou une coupure : « sans réponse »', async () => {
    const { client, acceptation } = await site()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const erreur = await client.analyserLeSaisi(POSITIONS, 'en', preuve(acceptation, 'en')).catch((e: unknown) => e)
    expect(erreur).toMatchObject({ statut: 0, detail: LIBELLES.en.serveur.sansReponse })
  })

  it('une réponse qui n’est pas un document : « illisible », jamais son contenu', async () => {
    const { client, acceptation } = await site()
    for (const [statut, corps] of [
      [200, PAGE_D_ATTENTE],
      [200, '[]'],
      [502, PAGE_D_ATTENTE],
    ] as const) {
      repondre(statut, corps)
      const erreur = await client.analyserLeSaisi(POSITIONS, 'fr', preuve(acceptation, 'fr')).catch((e: unknown) => e)
      expect((erreur as Error).message).toBe(LIBELLES.fr.serveur.reponseIllisible)
      expect((erreur as Error).message).not.toContain('doctype')
    }
  })

  it('toute adresse demandée est un fichier de /donnees/, ou l’une des trois routes du serveur', async () => {
    const { client, acceptation } = await site()
    const adresses: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (adresse: string) => {
        adresses.push(adresse)
        return { ok: true, status: 200, text: async () => (adresse.endsWith('/health') ? SANTE : '{"x": 1}') }
      }),
    )
    const fichier = new File(['ticker;quantity\nKO;1\n'], 'p.csv', { type: 'text/csv' })
    const appels: Record<string, () => unknown> = {
      getMeta: () => client.getMeta('fr'),
      getDisclaimer: () => client.getDisclaimer('en'),
      getAnalysis: () => client.getAnalysis(1, 'fr'),
      getPortfolios: () => client.getPortfolios('en'),
      getSecurities: () => client.getSecurities('fr'),
      getCsvFormat: () => client.getCsvFormat('en'),
      createPortfolio: () => client.createPortfolio('Nouveau', 'fr'),
      deletePortfolio: () => client.deletePortfolio(1, 'fr'),
      putPositions: () => client.putPositions(1, POSITIONS, 'fr'),
      importCsv: () => client.importCsv(1, fichier, 'fr'),
      reveillerLeServeur: () => client.reveillerLeServeur(),
      attendreLeServeur: () => client.attendreLeServeur('fr', () => undefined),
      analyserLeSaisi: () => client.analyserLeSaisi(POSITIONS, 'fr', preuve(acceptation, 'fr')),
      lireUnFichier: () => client.lireUnFichier(fichier, 'en', preuve(acceptation, 'en')),
    }
    // Les fonctions pures, qui ne demandent rien au réseau.
    const PURES = ['adresseDeDemo', 'segmenter', 'versApiErreur', 'estUnRefus', 'titreSourceInjoignable', 'ApiErreur']
    const exportees = Object.entries(client)
      .filter(([, valeur]) => typeof valeur === 'function')
      .map(([nom]) => nom)
      .sort()
    expect(exportees).toEqual([...Object.keys(appels), ...PURES].sort())

    for (const appel of Object.values(appels)) {
      await Promise.resolve(appel()).catch(() => undefined)
    }
    await vi.waitFor(() => expect(adresses.filter((a) => a.endsWith('/health')).length).toBeGreaterThanOrEqual(2))
    const routes = [`${SERVEUR}/health`, ...['fr', 'en'].flatMap((l) => [`${SERVEUR}/analysis?lang=${l}`, `${SERVEUR}/csv?lang=${l}`])]
    const permise = (adresse: string) => /^\/donnees\/(fr|en)\/[a-z0-9/-]+\.json$/.test(adresse) || routes.includes(adresse)
    expect(adresses.filter((adresse) => !permise(adresse))).toEqual([])
    expect(adresses.some((adresse) => adresse.includes('/api'))).toBe(false)
    expect(adresses).toContain(`${SERVEUR}/analysis?lang=fr`)
    expect(adresses).toContain(`${SERVEUR}/csv?lang=en`)
  })

  it('hors du site, rien n’attend ni n’envoie au serveur public', async () => {
    vi.stubEnv('MX_RISK_SERVEUR_PUBLIC', SERVEUR)
    const client = await clientEnMode('production')
    const espion = repondre(200, SANTE)
    client.reveillerLeServeur()
    await expect(client.attendreLeServeur('fr', () => undefined)).rejects.toThrow()
    await expect(client.analyserLeSaisi(POSITIONS, 'fr', null)).rejects.toThrow()
    expect(espion).not.toHaveBeenCalled()
  })
})
