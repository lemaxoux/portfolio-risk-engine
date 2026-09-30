/**
 * Le SEUL module qui parle à l'API — DESIGN.md §13 (état d'erreur).
 *
 * ═══ CE QU'IL FAIT DU CORPS D'ERREUR ═══
 *
 * Le backend porte déjà des messages actionnables : `PortfolioError` dit
 * « Aucun prix en base pour ['SPY']. Le charger avec `python -m
 * backend.ingestion add SPY` » — c'est exactement ce que l'utilisateur a besoin
 * de lire. Les remplacer par « Une erreur est survenue » échangerait une
 * instruction contre un aveu d'impuissance.
 *
 * Le client relaie donc `detail` MOT POUR MOT. Il ne reformule pas, ne traduit
 * pas, n'abrège pas. La seule chose qu'il fait est typographique : reconnaître
 * la COMMANDE dans la phrase et la sortir du texte courant, pour qu'elle soit
 * rendue en bloc de code — sélectionnable, copiable, sans césure. Une commande
 * shell noyée dans une phrase justifiée se recopie de travers.
 *
 * ═══ UNE SEULE ORIGINE ═══
 *
 * `/api` est un chemin RELATIF. En développement, Vite le relaie vers
 * 127.0.0.1:8000 ; en production, FastAPI sert la page et l'API. Dans les deux
 * cas le navigateur ne voit qu'une origine, et il n'y a pas d'adresse d'API à
 * configurer quelque part — donc pas d'adresse à se tromper.
 */
import type {
  Analysis,
  CsvFormat,
  CsvImport,
  Disclaimer,
  Meta,
  Portfolio,
  PortfolioDetail,
  PositionIn,
  PositionsWritten,
  Security,
} from './types'

const BASE = '/api'

export interface Probleme {
  line: number | null
  field: string | null
  value: string | null
  problem: string
}

/** Un morceau de message : du texte courant, ou une commande à recopier. */
export type Segment =
  | { readonly genre: 'texte'; readonly contenu: string }
  | { readonly genre: 'commande'; readonly contenu: string }

/**
 * Sépare les commandes du texte courant dans un message du backend.
 *
 * Deux écritures coexistent dans le moteur, et les deux sont reconnues :
 *
 *   « …Le charger avec `python -m backend.ingestion add SPY`, ou… »
 *   « …Lancer : python -m backend.ingestion add <TICKER> »
 *
 * Les reconnaître ici plutôt que d'uniformiser le backend est un choix : ces
 * messages sont aussi lus dans un terminal, où les accents graves seraient du
 * bruit. C'est l'affichage qui s'adapte au texte, pas le texte à l'affichage.
 */
export function segmenter(message: string): Segment[] {
  const segments: Segment[] = []

  const pousserTexte = (texte: string) => {
    if (texte.length > 0) segments.push({ genre: 'texte', contenu: texte })
  }

  const pousserCommande = (commande: string) => {
    // Une phrase qui se termine après la commande lui colle sa ponctuation.
    const nettoyee = commande.replace(/[.,;:]+$/, '')
    if (nettoyee.length > 0) segments.push({ genre: 'commande', contenu: nettoyee })
  }

  // 1. Les accents graves délimitent explicitement. Les indices impairs du
  //    découpage sont, par construction, ce qu'ils encadraient.
  message.split('`').forEach((morceau, index) => {
    if (index % 2 === 1) {
      pousserCommande(morceau)
      return
    }
    // 2. Hors accents graves, une commande commence par « python -m » et court
    //    jusqu'à une virgule, un point-virgule ou la fin de la phrase.
    const NUE = /python -m \S+(?:[ \t]+[^\s,;]+)*/g
    let curseur = 0
    for (const trouve of morceau.matchAll(NUE)) {
      pousserTexte(morceau.slice(curseur, trouve.index))
      pousserCommande(trouve[0])
      curseur = trouve.index + trouve[0].length
    }
    pousserTexte(morceau.slice(curseur))
  })

  return segments
}

/**
 * Un refus de l'API, avec de quoi l'afficher tel qu'il a été écrit.
 *
 * `statut` vaut 0 quand la requête n'est jamais partie — serveur éteint, réseau
 * coupé. C'est un cas distinct d'un 4xx, et il se dit autrement : il n'y a rien
 * à corriger dans la demande, il y a un serveur à démarrer.
 */
export class ApiErreur extends Error {
  readonly statut: number
  readonly detail: string
  readonly problems: Probleme[]

  constructor(statut: number, detail: string, problems: Probleme[] = []) {
    super(detail)
    this.name = 'ApiErreur'
    this.statut = statut
    this.detail = detail
    this.problems = problems
  }

  /** Le détail, prêt à rendre : texte courant et commandes séparés. */
  get segments(): Segment[] {
    return segmenter(this.detail)
  }
}

/**
 * Toute erreur en `ApiErreur` : celles de l'API passent telles quelles, une
 * erreur du client est nommée comme telle plutôt que tue.
 */
export function versApiErreur(cause: unknown): ApiErreur {
  return cause instanceof ApiErreur
    ? cause
    : new ApiErreur(0, `Erreur inattendue du client : ${String(cause)}`)
}

const SERVEUR_INJOIGNABLE =
  "L'API ne répond pas. La démarrer : python -m backend.api"

/**
 * Ce qu'une requête envoie. `json` est sérialisé ; `fichier` part en
 * multipart, sous le nom de champ que la route attend (`file`), et c'est le
 * navigateur qui pose l'en-tête `Content-Type` avec sa frontière — l'écrire à
 * la main la perdrait.
 */
interface Envoi {
  readonly methode: 'POST' | 'PUT' | 'DELETE'
  readonly json?: unknown
  readonly fichier?: File
}

async function lire<T>(chemin: string, envoi?: Envoi): Promise<T> {
  let reponse: Response
  try {
    reponse = await fetch(`${BASE}${chemin}`, requete(envoi))
  } catch {
    throw new ApiErreur(0, SERVEUR_INJOIGNABLE)
  }
  return decoder<T>(reponse)
}

function requete(envoi: Envoi | undefined): RequestInit {
  const entetes: Record<string, string> = { Accept: 'application/json' }
  if (envoi === undefined) return { headers: entetes }
  if (envoi.fichier !== undefined) {
    const corps = new FormData()
    corps.append('file', envoi.fichier, envoi.fichier.name)
    return { method: envoi.methode, headers: entetes, body: corps }
  }
  if (envoi.json !== undefined) {
    return {
      method: envoi.methode,
      headers: { ...entetes, 'Content-Type': 'application/json' },
      body: JSON.stringify(envoi.json),
    }
  }
  return { method: envoi.methode, headers: entetes }
}

/** Une écriture qui ne rend rien (204) : le succès EST la réponse. */
async function ecrireSansCorps(chemin: string, envoi: Envoi): Promise<void> {
  let reponse: Response
  try {
    reponse = await fetch(`${BASE}${chemin}`, requete(envoi))
  } catch {
    throw new ApiErreur(0, SERVEUR_INJOIGNABLE)
  }
  if (reponse.ok) return
  await decoder<never>(reponse)
}

async function decoder<T>(reponse: Response): Promise<T> {
  // Le corps est lu comme du TEXTE avant d'être décodé : si l'API rendait autre
  // chose que du JSON, `response.json()` lèverait une erreur de syntaxe qui ne
  // dirait pas ce qui est arrivé. Ici on peut montrer ce qu'on a reçu.
  const brut = await reponse.text()
  let corps: unknown = null
  try {
    corps = brut.length > 0 ? JSON.parse(brut) : null
  } catch {
    corps = null
  }

  if (!reponse.ok) {
    throw new ApiErreur(
      reponse.status,
      detailDe(corps) ?? `Réponse ${reponse.status} inattendue de l'API.`,
      problemesDe(corps),
    )
  }
  if (corps === null) {
    throw new ApiErreur(reponse.status, "L'API a répondu un corps vide.")
  }
  return corps as T
}

function detailDe(corps: unknown): string | null {
  if (typeof corps !== 'object' || corps === null) return null
  const detail = (corps as Record<string, unknown>)['detail']
  return typeof detail === 'string' ? detail : null
}

function problemesDe(corps: unknown): Probleme[] {
  if (typeof corps !== 'object' || corps === null) return []
  const problems = (corps as Record<string, unknown>)['problems']
  return Array.isArray(problems) ? (problems as Probleme[]) : []
}

export function getMeta(): Promise<Meta> {
  return lire<Meta>('/meta')
}

export function getDisclaimer(): Promise<Disclaimer> {
  return lire<Disclaimer>('/disclaimer')
}

export function getAnalysis(portfolioId: number): Promise<Analysis> {
  return lire<Analysis>(`/portfolios/${portfolioId}/analysis`)
}

/**
 * La liste des portefeuilles : nom, positions telles que stockées, et
 * valorisation quand elle est possible. C'est elle qui dit qu'un portefeuille
 * est vide — par ses positions, jamais par le texte d'une erreur.
 */
export function getPortfolios(): Promise<PortfolioDetail[]> {
  return lire<PortfolioDetail[]>('/portfolios')
}

/** L'univers : tickers, noms, et première séance de prix de chacun. */
export function getSecurities(): Promise<Security[]> {
  return lire<Security[]>('/securities')
}

/** Le format que lit l'import CSV, publié par le lecteur lui-même. */
export function getCsvFormat(): Promise<CsvFormat> {
  return lire<CsvFormat>('/csv-format')
}

export function createPortfolio(nom: string): Promise<Portfolio> {
  return lire<Portfolio>('/portfolios', { methode: 'POST', json: { name: nom } })
}

export function deletePortfolio(portfolioId: number): Promise<void> {
  return ecrireSansCorps(`/portfolios/${portfolioId}`, { methode: 'DELETE' })
}

/** Remplace TOUTES les positions : le tableau envoyé EST le portefeuille. */
export function putPositions(
  portfolioId: number,
  positions: readonly PositionIn[],
): Promise<PositionsWritten> {
  return lire<PositionsWritten>(`/portfolios/${portfolioId}/positions`, {
    methode: 'PUT',
    json: { positions },
  })
}

/** Importe un fichier CSV, qui remplace lui aussi toutes les positions. */
export function importCsv(portfolioId: number, fichier: File): Promise<CsvImport> {
  return lire<CsvImport>(`/portfolios/${portfolioId}/positions/csv`, {
    methode: 'POST',
    fichier,
  })
}
