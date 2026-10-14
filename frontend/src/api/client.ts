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
 *
 * ═══ DEUX SOURCES, CHOISIES AU BUILD, ICI SEULEMENT ═══
 *
 * Le build de démonstration (`npm run build:demo`, mode Vite `demo`) est un
 * site statique. Les LECTURES y demandent des réponses de l'API enregistrées
 * en fichiers par `python -m tools.export_demo`, une par langue :
 * `/donnees/fr/portfolios.json` à la place de `/api/portfolios?lang=fr`. Ce
 * module est le seul à savoir d'où viennent les données, et où part une
 * saisie ; le reste du client ne lit `DEMO` que pour masquer ce qui écrit en
 * base, afficher la mention, rendre la page de présentation à l'adresse `/`,
 * et ne poser l'écran d'acceptation que devant les pages du portefeuille
 * saisi (DESIGN.md §18.1, §19).
 *
 * Les ÉCRITURES de l'application n'ont pas d'autre source que l'API. En
 * démonstration, plus rien ne les appelle : elles sortent du bundle avec les
 * écrans qui les portaient, et le build de démonstration échoue si l'une
 * d'elles y revient.
 *
 * La démonstration a ses propres échecs. Un fichier absent ne se voit pas au
 * statut : un hébergeur statique rend sa page d'accueil, avec un 200, pour une
 * adresse qu'il ne connaît pas.
 *
 * ═══ LE SERVEUR PUBLIC (chantier 9.6) ═══
 *
 * Le site analyse aussi le portefeuille qu'un visiteur saisit, par un serveur
 * public sans état (`backend/public_api/`). Son adresse arrive au build
 * (`MX_RISK_SERVEUR_PUBLIC`, lue par `vite.config.ts`), et ce module est le
 * seul qui la lit. Trois appels, et eux seuls : le réveil (`GET /health`),
 * l'analyse d'une composition (`POST /analysis`) et la lecture d'un fichier
 * (`POST /csv`). Les deux envois passent par une seule fonction, où la
 * méthode est écrite une fois : la garde du build en tient le compte.
 *
 * Le serveur s'arrête quand personne ne s'en sert, et redémarre à la première
 * demande. Une réponse qui n'est pas son JSON (la page d'attente de
 * l'hébergeur, un 503, une réponse sans en-tête CORS) compte comme « pas
 * encore réveillé » : son contenu n'est jamais lu au-delà de ce constat, ni
 * affiché. Aucun envoi ne part avant un `/health` réussi, ni sans la preuve
 * que le texte d'acceptation de sa langue a été accepté (`lib/acceptation`).
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
  PublicAnalysis,
  PublicCsv,
  Security,
} from './types'
import { LIBELLES } from '../contenu/libelles'
import { estUnePreuve, type PreuveDAcceptation } from '../lib/acceptation'
import type { Langue } from '../lib/langue'

const BASE = '/api'

/**
 * Le build de démonstration. Une constante connue au build : Vite remplace
 * `import.meta.env.MODE`, et tout ce qui ne sert qu'à l'autre source sort du
 * bundle. Fausse dans le build ordinaire, en développement et sous Vitest.
 */
export const DEMO = import.meta.env.MODE === 'demo'

/** Où le site de démonstration sert les réponses enregistrées. */
const DONNEES = '/donnees'

/** Le fichier d'une lecture, tel que l'export le nomme : `fr/portfolios.json`. */
function fichierDeDemo(chemin: string, langue: Langue): string {
  return `${langue}${chemin}.json`
}

/**
 * L'adresse d'une lecture en démonstration. La langue est dans le chemin : un
 * fichier statique ne lit pas `?lang`.
 */
export function adresseDeDemo(chemin: string, langue: Langue): string {
  return `${DONNEES}/${fichierDeDemo(chemin, langue)}`
}

/**
 * La langue des textes rédigés de la réponse (chantier 7D) : `?lang=fr` ou
 * `?lang=en`, sur CHAQUE appel. Le serveur rend la même réponse française avec
 * ou sans `lang=fr`, octet pour octet ; l'écrire quand même fait voir la
 * langue demandée dans l'adresse, les journaux et les tests. Les routes qui
 * ne rédigent rien (`/meta`, `/securities`) l'ignorent.
 */
function avecLangue(chemin: string, langue: Langue): string {
  return `${chemin}${chemin.includes('?') ? '&' : '?'}lang=${langue}`
}

export interface Probleme {
  line: number | null
  field: string | null
  value: string | null
  problem: string
}

/**
 * Un morceau de message : du texte courant, une commande à recopier, ou un
 * littéral cité — un séparateur, une décimale — qui se lit dans la phrase.
 */
export type Segment =
  | { readonly genre: 'texte'; readonly contenu: string }
  | { readonly genre: 'commande'; readonly contenu: string }
  | { readonly genre: 'litteral'; readonly contenu: string }

/** Ce qui fait d'un passage entre accents graves une commande. */
const COMMANDE = /^python -m /

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
 *
 * TOUT CE QUI EST ENTRE ACCENTS GRAVES N'EST PAS UNE COMMANDE. L'import CSV
 * cite ainsi ses séparateurs : « avec le séparateur `,`, une virgule
 * décimale… ». Pris pour une commande, `,` perdait sa ponctuation finale —
 * c'est-à-dire lui-même — et disparaissait de la phrase. Un passage qui ne
 * commence pas par `python -m` est un LITTÉRAL, rendu en code dans la ligne,
 * tel quel.
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
      if (COMMANDE.test(morceau)) pousserCommande(morceau)
      else if (morceau.length > 0) segments.push({ genre: 'litteral', contenu: morceau })
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
 * à corriger dans la demande, il y a un serveur à démarrer. Il vaut 0 aussi
 * pour tout échec de la démonstration : un fichier absent n'est pas le refus
 * d'une API, et son statut ne doit pas se lire comme tel.
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
 * erreur du client est nommée comme telle plutôt que tue, dans la langue de
 * la page.
 */
export function versApiErreur(cause: unknown, langue: Langue = 'fr'): ApiErreur {
  return cause instanceof ApiErreur
    ? cause
    : new ApiErreur(0, LIBELLES[langue].api.erreurDuClient(String(cause)))
}

/**
 * Un refus de ce qui a été envoyé (chantier 9.6) : le serveur public a lu la
 * demande et la refuse, lignes, fichier ou composition. Le renvoyer telle
 * quelle ne servirait à rien : c'est elle qui se corrige. Les autres échecs,
 * une limite atteinte (429), un serveur occupé, une panne, aucune réponse,
 * se réessaient.
 */
export function estUnRefus(erreur: ApiErreur): boolean {
  return erreur.statut >= 400 && erreur.statut < 500 && erreur.statut !== 429
}

/**
 * Le titre de la page quand la source des données ne répond pas au démarrage.
 * Il dépend de la source, donc il se demande ici.
 */
export function titreSourceInjoignable(langue: Langue = 'fr'): string {
  return DEMO ? LIBELLES[langue].demo.indisponible : LIBELLES[langue].application.apiInjoignable
}

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

/**
 * La démonstration n'a pas d'API : ni lecture, ni écriture n'y part vers
 * elle. Aucun de ses écrans ne l'appelle, et la garde du build le tient sur
 * le bundle ; à l'exécution, l'appel lève avant toute requête. L'adresse est
 * écrite avant : un écran qui appellerait l'API laisserait `/api` dans le
 * bundle, et la garde le verrait.
 */
const SANS_API = "Le build de démonstration n'a pas d'API à appeler."

/** Un appel à l'API : toute écriture, et les lectures hors démonstration. */
async function appeler<T>(chemin: string, langue: Langue, envoi?: Envoi): Promise<T> {
  const adresse = `${BASE}${avecLangue(chemin, langue)}`
  if (DEMO) throw new Error(`${SANS_API} (${adresse})`)
  let reponse: Response
  try {
    reponse = await fetch(adresse, requete(envoi))
  } catch {
    throw new ApiErreur(0, LIBELLES[langue].api.serveurInjoignable)
  }
  return decoder<T>(reponse, langue)
}

/**
 * Une lecture en démonstration : le fichier de la réponse enregistrée.
 *
 * Seul un corps qui se lit comme un document JSON non vide est une réponse.
 * Le statut ne suffit pas : pour un fichier absent, un hébergeur statique
 * rend sa page d'accueil avec un 200. Une liste vide est un export cassé, pas
 * un état de la démonstration, qui n'a rien pour créer un portefeuille.
 */
async function lireFichier<T>(chemin: string, langue: Langue): Promise<T> {
  const textes = LIBELLES[langue].demo
  let reponse: Response
  try {
    reponse = await fetch(adresseDeDemo(chemin, langue), { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiErreur(0, textes.injoignable)
  }
  const illisible = new ApiErreur(0, textes.fichierIllisible(fichierDeDemo(chemin, langue)))
  if (!reponse.ok) throw illisible
  let corps: unknown
  try {
    corps = JSON.parse(await reponse.text())
  } catch {
    throw illisible
  }
  if (typeof corps !== 'object' || corps === null) throw illisible
  if (Array.isArray(corps) && corps.length === 0) throw illisible
  return corps as T
}

/** Les lectures : l'API, ou les fichiers de la démonstration. */
const lire: <T>(chemin: string, langue: Langue) => Promise<T> = DEMO ? lireFichier : appeler

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
async function ecrireSansCorps(chemin: string, langue: Langue, envoi: Envoi): Promise<void> {
  const adresse = `${BASE}${avecLangue(chemin, langue)}`
  if (DEMO) throw new Error(`${SANS_API} (${adresse})`)
  let reponse: Response
  try {
    reponse = await fetch(adresse, requete(envoi))
  } catch {
    throw new ApiErreur(0, LIBELLES[langue].api.serveurInjoignable)
  }
  if (reponse.ok) return
  await decoder<never>(reponse, langue)
}

async function decoder<T>(reponse: Response, langue: Langue): Promise<T> {
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
      detailDe(corps) ?? LIBELLES[langue].api.reponseInattendue(reponse.status),
      problemesDe(corps),
    )
  }
  if (corps === null) {
    throw new ApiErreur(reponse.status, LIBELLES[langue].api.corpsVide)
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

export function getMeta(langue: Langue = 'fr'): Promise<Meta> {
  return lire<Meta>('/meta', langue)
}

export function getDisclaimer(langue: Langue = 'fr'): Promise<Disclaimer> {
  return lire<Disclaimer>('/disclaimer', langue)
}

export function getAnalysis(portfolioId: number, langue: Langue = 'fr'): Promise<Analysis> {
  return lire<Analysis>(`/portfolios/${portfolioId}/analysis`, langue)
}

/**
 * La liste des portefeuilles : nom, positions telles que stockées, et
 * valorisation quand elle est possible. C'est elle qui dit qu'un portefeuille
 * est vide — par ses positions, jamais par le texte d'une erreur.
 */
export function getPortfolios(langue: Langue = 'fr'): Promise<PortfolioDetail[]> {
  return lire<PortfolioDetail[]>('/portfolios', langue)
}

/** L'univers : tickers, noms, et première séance de prix de chacun. */
export function getSecurities(langue: Langue = 'fr'): Promise<Security[]> {
  return lire<Security[]>('/securities', langue)
}

/** Le format que lit l'import CSV, publié par le lecteur lui-même. */
export function getCsvFormat(langue: Langue = 'fr'): Promise<CsvFormat> {
  return lire<CsvFormat>('/csv-format', langue)
}

export function createPortfolio(nom: string, langue: Langue = 'fr'): Promise<Portfolio> {
  return appeler<Portfolio>('/portfolios', langue, {
    methode: 'POST',
    json: { name: nom },
  })
}

export function deletePortfolio(portfolioId: number, langue: Langue = 'fr'): Promise<void> {
  return ecrireSansCorps(`/portfolios/${portfolioId}`, langue, { methode: 'DELETE' })
}

/** Remplace TOUTES les positions : le tableau envoyé EST le portefeuille. */
export function putPositions(
  portfolioId: number,
  positions: readonly PositionIn[],
  langue: Langue = 'fr',
): Promise<PositionsWritten> {
  return appeler<PositionsWritten>(`/portfolios/${portfolioId}/positions`, langue, {
    methode: 'PUT',
    json: { positions },
  })
}

/** Importe un fichier CSV, qui remplace lui aussi toutes les positions. */
export function importCsv(
  portfolioId: number,
  fichier: File,
  langue: Langue = 'fr',
): Promise<CsvImport> {
  return appeler<CsvImport>(`/portfolios/${portfolioId}/positions/csv`, langue, {
    methode: 'POST',
    fichier,
  })
}

// ═══════════════════════════════════════════════ Le serveur public (9.6) ══

/**
 * L'origine du serveur public, que le build de démonstration reçoit de
 * `MX_RISK_SERVEUR_PUBLIC` (`vite.config.ts`, `lireLeServeur`). Vide hors de
 * ce build : rien n'y appelle le serveur public, et ce qui suit n'y reste pas.
 */
const SERVEUR: string = DEMO ? (import.meta.env.MX_RISK_SERVEUR_PUBLIC ?? '') : ''

/**
 * Hors du build de démonstration, l'attente et l'envoi lèvent d'entrée : la
 * constante y vaut faux, et le bundler retire ce qui suit, requêtes comprises.
 * Aucune page de l'application ne les appelle.
 */
const HORS_DU_SITE = "Le serveur public n'existe que dans le build de démonstration."

/**
 * Seuil CHOISI. Le délai d'un essai de réveil, en millisecondes : au-delà,
 * l'essai est abandonné et repris, le démarrage continue.
 */
const DELAI_D_UN_ESSAI = 15_000

/** Seuil CHOISI. L'attente entre deux essais de réveil. */
const ENTRE_DEUX_ESSAIS = 3_000

/**
 * Seuil CHOISI. La durée totale du réveil, du premier essai au dernier.
 * Observé sur le serveur endormi : 52 s par `curl` le 2026-10-13, jusqu'au
 * premier `/health` en 200 ; 71,6 s depuis un navigateur le 2026-10-14, sur
 * le site en ligne. Pendant le réveil, l'hébergeur retient les requêtes au
 * lieu de les refuser : les premiers essais restent sans réponse, et sont
 * abandonnés à leur délai.
 */
const DUREE_DU_REVEIL = 150_000

/**
 * Seuil CHOISI. Le délai d'un envoi, analyse ou fichier : quatre analyses à
 * la file en font vingt-cinq à trente secondes. Relevé le 2026-10-13 : une
 * analyse de la démonstration prend 7 s, une de tous les titres 13 s.
 */
const DELAI_D_UN_ENVOI = 60_000

/**
 * Seuil CHOISI. Le silence avant de dire le réveil : un serveur éveillé
 * répond à `/health` bien avant. La phrase du réveil ne s'affiche donc que
 * quand l'attente se voit, et pas le temps d'un aller-retour.
 */
const SILENCE_AVANT_LE_REVEIL = 1_000

/** `GET /health` a-t-il rendu le JSON du serveur, et non une page de l'hébergeur ? */
function estLaReponseDuServeur(corps: unknown): boolean {
  return (
    typeof corps === 'object' &&
    corps !== null &&
    (corps as Record<string, unknown>)['status'] === 'ready'
  )
}

/** Un signal qui s'arrête au premier des deux : le délai, ou l'abandon de la page. */
function signalBorne(
  delai: number,
  abandon?: AbortSignal,
): { readonly signal: AbortSignal; readonly liberer: () => void } {
  const arret = new AbortController()
  const minuterie = setTimeout(() => arret.abort(), Math.max(0, delai))
  const suivre = () => arret.abort()
  if (abandon?.aborted === true) arret.abort()
  abandon?.addEventListener('abort', suivre, { once: true })
  return {
    signal: arret.signal,
    liberer: () => {
      clearTimeout(minuterie)
      abandon?.removeEventListener('abort', suivre)
    },
  }
}

/**
 * Un essai de réveil : `GET /health`, nu. Ni corps, ni paramètre, ni en-tête
 * ajouté, ni cookie, ni référent : une requête « simple », sans pré-requête,
 * qui ne porte rien d'autre que ce que le navigateur envoie de lui-même. Vrai
 * si la réponse est le JSON du serveur ; faux pour toute autre réponse, dont
 * le contenu n'est pas lu plus loin.
 */
async function sonder(delai: number, abandon?: AbortSignal): Promise<boolean> {
  const { signal, liberer } = signalBorne(delai, abandon)
  try {
    const reponse = await fetch(`${SERVEUR}/health`, {
      credentials: 'omit',
      referrerPolicy: 'no-referrer',
      cache: 'no-store',
      signal,
    })
    if (!reponse.ok) return false
    return estLaReponseDuServeur(JSON.parse(await reponse.text()))
  } catch {
    return false
  } finally {
    liberer()
  }
}

/**
 * La page d'accueil réveille le serveur, une fois l'affichage fait : un seul
 * essai, muet. Ni attente, ni message, ni nouvel essai.
 */
export function reveillerLeServeur(): void {
  if (SERVEUR !== '') void sonder(DELAI_D_UN_ESSAI)
}

function patienter(duree: number, abandon?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const minuterie = setTimeout(resolve, duree)
    abandon?.addEventListener(
      'abort',
      () => {
        clearTimeout(minuterie)
        resolve()
      },
      { once: true },
    )
  })
}

/**
 * Attend que le serveur réponde, avant tout envoi : un essai, puis un toutes
 * les trois secondes après un échec, chacun borné, pendant la durée du réveil
 * au plus. Passé elle, lève « sans réponse », sans chercher pourquoi.
 *
 * `surAttente` est appelé une fois, quand l'attente se voit : le premier essai
 * a échoué, ou n'a rien rendu au bout du silence. Un serveur éveillé répond
 * avant, et rien n'est dit.
 */
export async function attendreLeServeur(
  langue: Langue,
  surAttente: () => void,
  abandon?: AbortSignal,
): Promise<void> {
  if (!DEMO) throw new Error(HORS_DU_SITE)
  const sansReponse = new ApiErreur(0, LIBELLES[langue].serveur.sansReponse)
  const debut = Date.now()
  let dite = false
  const dire = () => {
    if (dite || abandon?.aborted === true) return
    dite = true
    surAttente()
  }
  const silence = setTimeout(dire, SILENCE_AVANT_LE_REVEIL)
  try {
    for (;;) {
      const reste = DUREE_DU_REVEIL - (Date.now() - debut)
      if (reste <= 0 || abandon?.aborted === true) throw sansReponse
      if (await sonder(Math.min(DELAI_D_UN_ESSAI, reste), abandon)) return
      dire()
      if (Date.now() - debut + ENTRE_DEUX_ESSAIS >= DUREE_DU_REVEIL) throw sansReponse
      await patienter(ENTRE_DEUX_ESSAIS, abandon)
    }
  } finally {
    clearTimeout(silence)
  }
}

/**
 * Ce que rend le serveur public : son document, ou son refus, dont le
 * `detail` et les `problems` sont ses propres phrases, relayées telles
 * quelles, comme celles de l'application.
 */
async function lireLaReponse<T>(reponse: Response, langue: Langue): Promise<T> {
  const illisible = LIBELLES[langue].serveur.reponseIllisible
  let corps: unknown = null
  try {
    const brut = await reponse.text()
    corps = brut.length > 0 ? JSON.parse(brut) : null
  } catch {
    corps = null
  }
  if (!reponse.ok) {
    throw new ApiErreur(reponse.status, detailDe(corps) ?? illisible, problemesDe(corps))
  }
  if (typeof corps !== 'object' || corps === null || Array.isArray(corps)) {
    throw new ApiErreur(0, illisible)
  }
  return corps as T
}

/**
 * L'envoi au serveur public : la seule écriture du site, et le seul endroit
 * du client où sa méthode est écrite (la garde du build la compte). Rien ne
 * part sans la preuve que le texte d'acceptation de la langue de la requête a
 * été accepté : sans elle, l'envoi lève avant tout appel réseau. La
 * composition voyage dans le corps, jamais dans l'adresse.
 */
async function envoyer<T>(
  chemin: '/analysis' | '/csv',
  corps: string | FormData,
  langue: Langue,
  preuve: PreuveDAcceptation | null,
): Promise<T> {
  if (!DEMO) throw new Error(HORS_DU_SITE)
  if (!estUnePreuve(preuve, langue)) {
    throw new Error(`Envoi refusé, faute de preuve d'acceptation dans la langue ${langue}.`)
  }
  const { signal, liberer } = signalBorne(DELAI_D_UN_ENVOI)
  try {
    let reponse: Response
    try {
      reponse = await fetch(`${SERVEUR}${chemin}?lang=${langue}`, {
        method: 'POST',
        body: corps,
        headers: typeof corps === 'string' ? { 'Content-Type': 'application/json' } : {},
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
        cache: 'no-store',
        signal,
      })
    } catch {
      throw new ApiErreur(0, LIBELLES[langue].serveur.sansReponse)
    }
    return await lireLaReponse<T>(reponse, langue)
  } finally {
    liberer()
  }
}

/**
 * L'analyse d'une composition par le serveur public : celle de l'application,
 * sans identifiant, sans nom et sans série. Le nom du portefeuille n'est
 * jamais envoyé.
 */
export function analyserLeSaisi(
  positions: readonly PositionIn[],
  langue: Langue,
  preuve: PreuveDAcceptation | null,
): Promise<PublicAnalysis> {
  return envoyer<PublicAnalysis>('/analysis', JSON.stringify({ positions }), langue, preuve)
}

/** La lecture d'un fichier CSV par le serveur public : ses lignes, validées, sans analyse. */
export function lireUnFichier(
  fichier: File,
  langue: Langue,
  preuve: PreuveDAcceptation | null,
): Promise<PublicCsv> {
  const corps = new FormData()
  corps.append('file', fichier, fichier.name)
  return envoyer<PublicCsv>('/csv', corps, langue, preuve)
}
