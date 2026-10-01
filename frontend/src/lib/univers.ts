/**
 * L'univers des titres — tickers, noms, première séance de prix —, lu une
 * fois par session.
 *
 * Il sert à la saisie, et à rien d'autre : proposer les tickers à la frappe,
 * écrire le nom d'une ligne, et montrer DEPUIS QUAND elle a un historique. Un
 * titre coté depuis peu raccourcira la fenêtre de toute l'analyse : le voir
 * avant d'enregistrer évite de le découvrir dans le bandeau.
 *
 * Son échec n'empêche pas de saisir : le serveur vérifie chaque ticker à
 * l'enregistrement. La page le dit, et continue.
 */
import { useEffect, useState } from 'react'

import { ApiErreur, getSecurities, versApiErreur } from '../api/client'
import type { Security } from '../api/types'

let enCours: Promise<Security[]> | null = null

function charger(): Promise<Security[]> {
  if (enCours === null) {
    enCours = getSecurities().catch((cause: unknown) => {
      enCours = null // un prochain affichage réessaiera
      throw cause
    })
  }
  return enCours
}

export function useUnivers(): {
  univers: ReadonlyMap<string, Security> | null
  erreur: ApiErreur | null
} {
  const [univers, setUnivers] = useState<ReadonlyMap<string, Security> | null>(null)
  const [erreur, setErreur] = useState<ApiErreur | null>(null)

  useEffect(() => {
    let vivant = true
    charger().then(
      (titres) => {
        if (vivant) setUnivers(new Map(titres.map((titre) => [titre.ticker, titre])))
      },
      (cause: unknown) => {
        if (vivant) setErreur(versApiErreur(cause))
      },
    )
    return () => {
      vivant = false
    }
  }, [])

  return { univers, erreur }
}

/**
 * Le titre d'une ligne, par son ticker tel qu'il est tapé. La casse et les
 * espaces sont ignorés ici comme le serveur les ignore (`normalise_ticker`) :
 * c'est une recherche pour AFFICHER un nom, pas une validation.
 */
export function titreDe(
  univers: ReadonlyMap<string, Security> | null,
  ticker: string,
): Security | undefined {
  return univers?.get(ticker.trim().toUpperCase())
}
