/**
 * Le client d'API, et surtout ce qu'il fait des refus.
 *
 * Les messages exercés ici sont RECOPIÉS du backend, pas inventés : ils
 * viennent de `backend/risk_engine/engine.py` et
 * `backend/risk_engine/portfolio.py`. Un test écrit contre un message
 * plausible vérifierait que l'analyseur marche sur ce qu'on a imaginé.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ApiErreur,
  deletePortfolio,
  getDisclaimer,
  getMeta,
  importCsv,
  putPositions,
  segmenter,
} from './client'

// Recopiés mot pour mot du moteur.
const BENCHMARK_ABSENT =
  "Aucun prix en base pour ['SPY']. Le charger avec " +
  '`python -m backend.ingestion add SPY`, ' +
  "ou demander l'analyse sans benchmark (benchmark=None)."

const LIGNE_SANS_PRIX =
  "Aucun prix en base pour ['NEWCO']. " +
  'Lancer : python -m backend.ingestion add <TICKER>'

describe('segmenter — la commande sort du texte courant', () => {
  it('reconnaît une commande entre accents graves', () => {
    const segments = segmenter(BENCHMARK_ABSENT)
    const commandes = segments.filter((s) => s.genre === 'commande')

    expect(commandes).toHaveLength(1)
    expect(commandes[0]?.contenu).toBe('python -m backend.ingestion add SPY')
    // Les accents graves eux-mêmes ne doivent pas rester dans le texte affiché.
    expect(segments.map((s) => s.contenu).join('')).not.toContain('`')
  })

  it('reconnaît aussi une commande écrite sans accents graves', () => {
    const commandes = segmenter(LIGNE_SANS_PRIX).filter(
      (s) => s.genre === 'commande',
    )
    expect(commandes).toHaveLength(1)
    expect(commandes[0]?.contenu).toBe(
      'python -m backend.ingestion add <TICKER>',
    )
  })

  it('conserve la phrase entière, dans l’ordre', () => {
    // La segmentation ne doit RIEN perdre : le message du moteur est ce que
    // l'utilisateur doit lire, et un morceau avalé serait invisible.
    const recompose = segmenter(LIGNE_SANS_PRIX)
      .map((s) => s.contenu)
      .join('')
    expect(recompose).toBe(LIGNE_SANS_PRIX)
  })

  it('laisse la ponctuation de la phrase hors de la commande', () => {
    // « …add SPY, ou demander » : la virgule appartient à la phrase, pas à la
    // commande, et recopiée dans un terminal elle la ferait échouer.
    const segments = segmenter(
      'Le charger avec python -m backend.ingestion add SPY, ou sans benchmark.',
    )
    const commande = segments.find((s) => s.genre === 'commande')
    expect(commande?.contenu).toBe('python -m backend.ingestion add SPY')
    expect(segments.some((s) => s.contenu.startsWith(', ou sans'))).toBe(true)
  })

  it('rend un message sans commande en un seul morceau de texte', () => {
    const message = 'Portefeuille 7 introuvable.'
    expect(segmenter(message)).toEqual([{ genre: 'texte', contenu: message }])
  })

  it('n’invente pas de commande dans une phrase qui parle de Python', () => {
    const message = 'Le moteur est écrit en python et ne calcule rien ici.'
    expect(segmenter(message).every((s) => s.genre === 'texte')).toBe(true)
  })
})

describe('ApiErreur', () => {
  it('porte le détail du backend mot pour mot', () => {
    const erreur = new ApiErreur(409, BENCHMARK_ABSENT)
    expect(erreur.detail).toBe(BENCHMARK_ABSENT)
    expect(erreur.message).toBe(BENCHMARK_ABSENT)
  })

  it('expose la commande séparément, prête pour un bloc de code', () => {
    const erreur = new ApiErreur(409, BENCHMARK_ABSENT)
    const commandes = erreur.segments.filter((s) => s.genre === 'commande')
    expect(commandes[0]?.contenu).toBe('python -m backend.ingestion add SPY')
  })
})

describe('lecture', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function repondre(statut: number, corps: unknown, ok = statut < 400) {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok,
        status: statut,
        text: async () => JSON.stringify(corps),
      })),
    )
  }

  it('rend le corps décodé sur un 200', async () => {
    repondre(200, { as_of: '2026-09-09', securities_count: 7 })
    await expect(getMeta()).resolves.toEqual({
      as_of: '2026-09-09',
      securities_count: 7,
    })
  })

  it('lève une ApiErreur portant le detail et le statut sur un 4xx', async () => {
    repondre(409, { detail: BENCHMARK_ABSENT, problems: [] })
    await expect(getDisclaimer()).rejects.toMatchObject({
      statut: 409,
      detail: BENCHMARK_ABSENT,
    })
  })

  it('conserve les problèmes ligne à ligne d’un 422', async () => {
    const problems = [
      { line: 4, field: 'ticker', value: 'XYZ', problem: 'Ticker inconnu' },
    ]
    repondre(422, { detail: 'Requête refusée.', problems })
    await expect(getMeta()).rejects.toMatchObject({ statut: 422, problems })
  })

  it('dit quoi faire quand l’API ne répond pas du tout', async () => {
    // Serveur éteint : il n'y a rien à corriger dans la demande, il y a un
    // serveur à démarrer. Le message le dit, et le statut 0 le distingue.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    const erreur = await getMeta().catch((e: unknown) => e)
    expect(erreur).toBeInstanceOf(ApiErreur)
    expect((erreur as ApiErreur).statut).toBe(0)
    expect((erreur as ApiErreur).segments.some((s) => s.genre === 'commande')).toBe(
      true,
    )
  })

  it('ne présente pas du HTML comme une réponse d’API', async () => {
    // Le repli du frontend ne masque jamais /api (backend/api/static.py). Si la
    // garantie tombait, le client doit le dire plutôt que d'échouer sur
    // « <!doctype » avec un message qui ne parle plus de la requête.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 404,
        text: async () => '<!doctype html><html lang="fr"></html>',
      })),
    )
    const erreur = await getMeta().catch((e: unknown) => e)
    expect(erreur).toBeInstanceOf(ApiErreur)
    expect((erreur as ApiErreur).detail).toContain('404')
    expect((erreur as ApiErreur).detail).not.toContain('doctype')
  })
})

describe('écritures', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function espionner(statut: number, corps: string) {
    const espion = vi.fn(async (_url: string, _init?: RequestInit) => ({
      ok: statut < 400,
      status: statut,
      text: async () => corps,
    }))
    vi.stubGlobal('fetch', espion)
    return espion
  }

  it('remplace les positions par un PUT en JSON, numéros de ligne compris', async () => {
    const espion = espionner(
      200,
      JSON.stringify({ portfolio_id: 3, positions_count: 1, updated_at: '2026-09-30', replaced: true }),
    )
    await putPositions(3, [{ ticker: 'AAPL', quantity: 40, cost_basis: 185.2, line: 1 }])
    const [url, init] = espion.mock.calls[0] ?? []
    expect(url).toBe('/api/portfolios/3/positions')
    expect(init?.method).toBe('PUT')
    expect(JSON.parse(String(init?.body))).toEqual({
      positions: [{ ticker: 'AAPL', quantity: 40, cost_basis: 185.2, line: 1 }],
    })
  })

  it('une suppression réussie n’a pas de corps, et ce n’est pas une erreur', async () => {
    espionner(204, '')
    await expect(deletePortfolio(3)).resolves.toBeUndefined()
  })

  it('une suppression refusée porte le détail du backend', async () => {
    espionner(404, JSON.stringify({ detail: 'Portefeuille 3 introuvable.', problems: [] }))
    await expect(deletePortfolio(3)).rejects.toMatchObject({
      statut: 404,
      detail: 'Portefeuille 3 introuvable.',
    })
  })

  it('envoie le fichier en multipart, sous le champ que la route attend', async () => {
    const espion = espionner(
      200,
      JSON.stringify({ portfolio_id: 3, positions_count: 2, updated_at: '2026-09-30', replaced: true }),
    )
    const fichier = new File(['ticker;quantity\nAAPL;40\n'], 'positions.csv', { type: 'text/csv' })
    await importCsv(3, fichier)
    const [url, init] = espion.mock.calls[0] ?? []
    expect(url).toBe('/api/portfolios/3/positions/csv')
    expect(init?.method).toBe('POST')
    const corps = init?.body as FormData
    expect((corps.get('file') as File).name).toBe('positions.csv')
    // Pas d'en-tête Content-Type écrit à la main : le navigateur pose la frontière.
    expect(new Headers(init?.headers).has('Content-Type')).toBe(false)
  })
})
