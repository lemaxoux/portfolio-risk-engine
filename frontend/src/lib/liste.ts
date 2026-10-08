/**
 * La liste des portefeuilles, chargée une fois par l'application.
 *
 * Elle porte ce que chaque page demande à un portefeuille avant tout autre
 * appel : son nom, ses positions telles que stockées (vide ou non), sa
 * valorisation quand elle existe. Elle est RELUE après chaque écriture —
 * création, suppression, enregistrement, import — pour que toutes les pages
 * décrivent le même état de la base.
 *
 * Un rechargement garde la liste affichée pendant qu'il se fait : seul le
 * premier chargement montre un squelette. Sans cela, chaque action ferait
 * clignoter la page entière.
 */
import { useCallback, useEffect, useState } from 'react'

import { ApiErreur, getPortfolios, versApiErreur } from '../api/client'
import type { PortfolioDetail } from '../api/types'
import type { Langue } from './langue'

export type EtatListe =
  | { readonly phase: 'chargement' }
  | { readonly phase: 'erreur'; readonly erreur: ApiErreur }
  | { readonly phase: 'prete'; readonly portefeuilles: readonly PortfolioDetail[] }

/**
 * La liste, dans la langue de la page : la raison d'une valorisation
 * impossible est rédigée par le serveur. Un changement de langue la relit,
 * en gardant l'ancienne affichée pendant ce temps.
 */
export function useListe(langue: Langue = 'fr'): { etat: EtatListe; recharger: () => Promise<void> } {
  const [etat, setEtat] = useState<EtatListe>({ phase: 'chargement' })

  const recharger = useCallback(async () => {
    try {
      const portefeuilles = await getPortfolios(langue)
      setEtat({ phase: 'prete', portefeuilles })
    } catch (cause) {
      setEtat({ phase: 'erreur', erreur: versApiErreur(cause) })
    }
  }, [langue])

  useEffect(() => {
    void recharger()
  }, [recharger])

  return { etat, recharger }
}
