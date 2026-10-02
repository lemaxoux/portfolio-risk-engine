/**
 * Le tableau de saisie des positions : ce qu'il lit, ce qu'il envoie, et où il
 * range les refus. DESIGN.md §8.2, §13.
 *
 * ═══ LE SEUL CONTRÔLE LOCAL : UN NOMBRE SE LIT-IL ? ═══
 *
 * L'API reçoit des nombres en JSON : « 12,5 » tapé dans une cellule doit donc
 * être lu ICI. C'est le seul contrôle fait avant l'envoi, et il est purement
 * syntaxique. Tout le reste — ticker inconnu, doublon, quantité nulle ou
 * négative, ligne sans ticker — est refusé par le serveur, qui rend ses
 * refus ligne à ligne : deux validations parallèles finiraient par diverger,
 * et la plus laxiste deviendrait la porte d'entrée.
 *
 * Ce lecteur accepte et refuse EXACTEMENT ce que lit l'import CSV avec le
 * séparateur « ; » (`backend/api/csv_import.NOMBRE`) : la même grammaire, et
 * une liste de cas partagée, `nombres-saisis.json`, que les deux suites de
 * tests font lire à leur lecteur.
 *
 * ═══ UNE LIGNE A UN NUMÉRO ═══
 *
 * Le numéro affiché devant chaque ligne part avec elle (`line`), et l'API le
 * renvoie dans ses refus : chaque refus se rattache à sa ligne et à son champ
 * sans que le client lise la phrase. Une ligne vide n'est pas envoyée, mais
 * les suivantes gardent leur numéro — celui que l'utilisateur voit.
 */
import type { Position, PositionIn } from '../api/types'
import type { Probleme } from '../api/client'
import { decimal, decimalesDeColonne } from './format'
import { cite } from './phrases'

// ═══════════════════════════════════════════════════════════ Les nombres ══

/** Espaces qu'un tableur glisse entre les milliers : ordinaire, insécable, fine. */
const ESPACES = /[ \u00A0\u202F]/g

/** Un signe facultatif, des chiffres latins, au plus une décimale suivie de chiffres. */
const NOMBRE = /^[+-]?[0-9]+(?:[.,][0-9]+)?$/

/** Le nombre tapé, ou `null` s'il ne se lit pas. */
export function lireNombreSaisi(texte: string): number | null {
  const compact = texte.trim().replace(ESPACES, '')
  if (!NOMBRE.test(compact)) return null
  return Number(compact.replace(',', '.'))
}

/**
 * Assez pour relire tout flottant utile ici : `decimalesDeColonne` prend le
 * PLUS PETIT nombre de décimales qui rend la valeur exacte, jamais celui-ci
 * quand moins suffit.
 */
const DECIMALES_MAX = 20

/**
 * Un nombre stocké, écrit pour être modifié : en français, avec juste assez de
 * décimales pour qu'il se relise À L'IDENTIQUE. Un prix de revient importé à
 * 185,20 doit repartir à 185,2, et non à 185 : sinon enregistrer le tableau
 * sans y toucher changerait le portefeuille.
 */
export function ecrireNombreSaisi(valeur: number): string {
  return decimal(valeur, decimalesDeColonne([valeur], DECIMALES_MAX))
}

// ═══════════════════════════════════════════════════════════ Les lignes ══

export interface LigneSaisie {
  /** Identité stable de la ligne, pour React : jamais montrée. */
  readonly cle: string
  readonly ticker: string
  readonly quantite: string
  readonly prixRevient: string
}

export type Champ = 'ticker' | 'quantity' | 'cost_basis'

let compteur = 0

export function ligneVide(): LigneSaisie {
  compteur += 1
  return { cle: `ligne-${compteur}`, ticker: '', quantite: '', prixRevient: '' }
}

/** Les lignes du tableau, depuis les positions TELLES QUE STOCKÉES. */
export function lignesDepuisPositions(positions: readonly Position[]): LigneSaisie[] {
  if (positions.length === 0) return [ligneVide()]
  return positions.map((position) => ({
    ...ligneVide(),
    ticker: position.ticker,
    quantite: ecrireNombreSaisi(position.quantity),
    prixRevient: position.cost_basis === null ? '' : ecrireNombreSaisi(position.cost_basis),
  }))
}

export function estVide(ligne: LigneSaisie): boolean {
  return (
    ligne.ticker.trim() === '' && ligne.quantite.trim() === '' && ligne.prixRevient.trim() === ''
  )
}

/**
 * L'empreinte de ce que le tableau décrit, pour savoir s'il a changé. Les
 * lignes vides n'en font pas partie : en ajouter une n'est pas une
 * modification du portefeuille.
 */
export function empreinteDesLignes(lignes: readonly LigneSaisie[]): string {
  return JSON.stringify(
    lignes
      .filter((ligne) => !estVide(ligne))
      .map((ligne) => [ligne.ticker.trim(), ligne.quantite.trim(), ligne.prixRevient.trim()]),
  )
}

// ═══════════════════════════════════════════════════════════ L'envoi ══

/** Un refus rattaché à une cellule : numéro de ligne affiché, et champ. */
export interface RefusDeCellule {
  readonly ligne: number
  readonly champ: Champ
  readonly message: string
}

/**
 * Ce qui part vers l'API, ou les nombres qui ne se lisent pas. Quand `refus`
 * n'est pas vide, rien n'est envoyé : un nombre illisible ne peut pas être
 * transmis, et le serveur ne verrait qu'un champ manquant.
 */
export function preparerEnvoi(lignes: readonly LigneSaisie[]): {
  positions: PositionIn[]
  refus: RefusDeCellule[]
} {
  const positions: PositionIn[] = []
  const refus: RefusDeCellule[] = []

  lignes.forEach((ligne, rang) => {
    const numero = rang + 1
    if (estVide(ligne)) return

    const quantite = lireNombreSaisi(ligne.quantite)
    if (ligne.quantite.trim() === '') {
      refus.push({ ligne: numero, champ: 'quantity', message: 'Quantité manquante.' })
    } else if (quantite === null) {
      refus.push({
        ligne: numero,
        champ: 'quantity',
        message: `Quantité illisible\u00a0: ${cite(ligne.quantite.trim())}. Écrire par exemple 40 ou 12,5.`,
      })
    }

    let prixRevient: number | null = null
    if (ligne.prixRevient.trim() !== '') {
      prixRevient = lireNombreSaisi(ligne.prixRevient)
      if (prixRevient === null) {
        refus.push({
          ligne: numero,
          champ: 'cost_basis',
          message: `Prix de revient illisible\u00a0: ${cite(ligne.prixRevient.trim())}. Écrire par exemple 185,20, ou laisser vide.`,
        })
      }
    }

    if (quantite !== null) {
      positions.push({
        ticker: ligne.ticker,
        quantity: quantite,
        cost_basis: prixRevient,
        line: numero,
      })
    }
  })

  return { positions, refus }
}

/**
 * Les refus du serveur, rangés : ceux qui portent une ligne vont à leur
 * cellule — le champ nommé, ou le ticker quand le refus vise la ligne
 * entière ; les autres (« Aucune position soumise… ») restent généraux.
 */
export function rangerRefus(problemes: readonly Probleme[]): {
  parCellule: RefusDeCellule[]
  generaux: string[]
} {
  const parCellule: RefusDeCellule[] = []
  const generaux: string[] = []
  for (const probleme of problemes) {
    if (probleme.line === null) {
      generaux.push(probleme.problem)
      continue
    }
    const champ: Champ =
      probleme.field === 'quantity' || probleme.field === 'cost_basis' ? probleme.field : 'ticker'
    parCellule.push({ ligne: probleme.line, champ, message: probleme.problem })
  }
  return { parCellule, generaux }
}
