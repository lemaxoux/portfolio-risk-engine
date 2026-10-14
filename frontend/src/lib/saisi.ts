/**
 * Le portefeuille saisi sur le site (chantier 9.6).
 *
 * ═══ UN SEUL, DANS CE NAVIGATEUR ═══
 *
 * Le visiteur compose un portefeuille parmi les titres de la base de la
 * démonstration. Il n'a pas de nom à saisir (« Votre portefeuille »), et il
 * n'est gardé nulle part ailleurs que dans ce navigateur : le serveur public
 * ne garde rien. Gardés ici : ses lignes telles qu'envoyées et acceptées
 * (ticker, quantité, prix de revient), et la date de leur dernier envoi
 * accepté, lue à l'horloge du navigateur. Cette date date un geste du
 * visiteur, comme `updated_at` dans l'application ; aucune date de cours n'en
 * vient.
 *
 * Lectures et écritures dans un `try`/`catch`, comme le thème et la langue.
 * Un contenu qui ne se lit pas comme attendu est traité comme absent. Sans
 * stockage, le portefeuille vit dans la mémoire de la page : la saisie et
 * l'analyse marchent jusqu'à sa fermeture, et la page des positions le dit.
 *
 * ═══ UNE ANALYSE PAR COMPOSITION ET PAR LANGUE, LE TEMPS DE LA PAGE ═══
 *
 * L'analyse que rend l'envoi d'une saisie est celle qu'affiche la page
 * suivante, sans second appel. Elle reste en mémoire tant que la page est
 * ouverte : une analyse se redemande au serveur quand la composition ou la
 * langue change, et à la visite suivante. Chaque demande coûte au serveur
 * quelques secondes d'un processeur que tous partagent, et compte dans la
 * limite de son adresse.
 */
import type { Position, PositionIn, PublicAnalysis } from '../api/types'
import type { Langue } from './langue'

/** La clé du stockage, à côté de celles du thème, de la langue et de l'acceptation. */
export const CLE_DU_SAISI = 'mx-risk-portefeuille-saisi'

/** Le portefeuille saisi : ses lignes, et la date ISO de leur dernier envoi accepté. */
export interface PortefeuilleSaisi {
  readonly positions: readonly Position[]
  readonly modifie: string
}

/** Sans stockage : le portefeuille de la page, perdu à sa fermeture. */
let dansLaPage: PortefeuilleSaisi | null = null

const DATE = /^\d{4}-\d{2}-\d{2}$/

function estUnePosition(valeur: unknown): valeur is Position {
  if (typeof valeur !== 'object' || valeur === null) return false
  const { ticker, quantity, cost_basis } = valeur as Record<string, unknown>
  return (
    typeof ticker === 'string' &&
    ticker.trim() !== '' &&
    typeof quantity === 'number' &&
    Number.isFinite(quantity) &&
    (cost_basis === null || (typeof cost_basis === 'number' && Number.isFinite(cost_basis)))
  )
}

/** Le contenu du stockage, s'il se lit comme un portefeuille saisi ; sinon `null`. */
export function lireUnSaisi(brut: string | null): PortefeuilleSaisi | null {
  if (brut === null) return null
  let lu: unknown
  try {
    lu = JSON.parse(brut)
  } catch {
    return null
  }
  if (typeof lu !== 'object' || lu === null) return null
  const { positions, modifie } = lu as Record<string, unknown>
  if (!Array.isArray(positions) || !positions.every(estUnePosition)) return null
  if (typeof modifie !== 'string' || !DATE.test(modifie)) return null
  return {
    positions: positions.map(({ ticker, quantity, cost_basis }) => ({ ticker, quantity, cost_basis })),
    modifie,
  }
}

/** Le portefeuille saisi : celui du stockage, ou à défaut celui de la page. */
export function lireLeSaisi(): PortefeuilleSaisi | null {
  try {
    const garde = lireUnSaisi(localStorage.getItem(CLE_DU_SAISI))
    if (garde !== null) return garde
  } catch {
    /* Stockage bloqué : la mémoire de la page. */
  }
  return dansLaPage
}

/**
 * La date du jour, dans le fuseau du navigateur, en ISO. Découpée sur les
 * champs locaux : `toISOString` donnerait celle de Greenwich, la veille ou le
 * lendemain selon l'heure.
 */
export function aujourdHui(maintenant: Date = new Date()): string {
  const mois = String(maintenant.getMonth() + 1).padStart(2, '0')
  const jour = String(maintenant.getDate()).padStart(2, '0')
  return `${maintenant.getFullYear()}-${mois}-${jour}`
}

/**
 * Garde des lignes acceptées par le serveur, datées du jour, et rend le
 * portefeuille gardé. Le numéro de ligne d'un envoi ne se garde pas : il est
 * celui du tableau au moment de l'envoi.
 */
export function garderLeSaisi(
  positions: readonly (Position | PositionIn)[],
  modifie: string = aujourdHui(),
): PortefeuilleSaisi {
  const saisi: PortefeuilleSaisi = {
    positions: positions.map((p) => ({
      ticker: p.ticker,
      quantity: p.quantity,
      cost_basis: p.cost_basis ?? null,
    })),
    modifie,
  }
  dansLaPage = saisi
  try {
    localStorage.setItem(CLE_DU_SAISI, JSON.stringify(saisi))
  } catch {
    /* Stockage bloqué : la mémoire de la page seulement. */
  }
  return saisi
}

/** Efface le portefeuille saisi, du stockage et de la page. */
export function effacerLeSaisi(): void {
  dansLaPage = null
  analyses.clear()
  try {
    localStorage.removeItem(CLE_DU_SAISI)
  } catch {
    /* Rien à faire. */
  }
}

/**
 * Ce navigateur garde-t-il quelque chose pour ce site ? Un essai d'écriture,
 * aussitôt retiré : un stockage bloqué lève, un stockage plein aussi.
 */
export function stockageDisponible(): boolean {
  const essai = `${CLE_DU_SAISI}-essai`
  try {
    localStorage.setItem(essai, '1')
    localStorage.removeItem(essai)
    return true
  } catch {
    return false
  }
}

// ═════════════════════════════════════════ L'analyse, le temps de la page ══

const analyses = new Map<string, PublicAnalysis>()

/** La composition et la langue d'une analyse : sa clé, sans le numéro des lignes. */
function cleDAnalyse(positions: readonly (Position | PositionIn)[], langue: Langue): string {
  return JSON.stringify([
    langue,
    positions.map((p) => [p.ticker, p.quantity, p.cost_basis ?? null]),
  ])
}

/** Garde l'analyse d'une composition, dans une langue, pour le temps de la page. */
export function deposerLAnalyse(
  positions: readonly (Position | PositionIn)[],
  langue: Langue,
  analyse: PublicAnalysis,
): void {
  analyses.set(cleDAnalyse(positions, langue), analyse)
}

/** L'analyse déjà reçue pour cette composition, dans cette langue, ou `null`. */
export function analyseDeposee(
  positions: readonly (Position | PositionIn)[],
  langue: Langue,
): PublicAnalysis | null {
  return analyses.get(cleDAnalyse(positions, langue)) ?? null
}
