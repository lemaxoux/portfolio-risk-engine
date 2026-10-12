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
 *
 * ═══ APRÈS L'AFFICHAGE, SUR LA PAGE DE PRÉSENTATION (chantier 9.4) ═══
 *
 * Toute page attend la liste, sauf une : la présentation de la démonstration,
 * dont le premier écran est du texte du bundle (DESIGN.md §19.9). Quand elle
 * est la première page affichée, la liste n'est demandée qu'une fois cet
 * écran peint (`lib/affichage`). Demandée au montage, elle partait avant la
 * première peinture : la page ne l'attendait pas, mais la mesure du LCP la
 * comptait. Seul le premier chargement est repoussé ; les relectures
 * (langue, écriture) partent aussitôt.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiErreur, getPortfolios, versApiErreur } from '../api/client'
import type { PortfolioDetail } from '../api/types'
import { apresLAffichage } from './affichage'
import type { Langue } from './langue'

export type EtatListe =
  | { readonly phase: 'chargement' }
  | { readonly phase: 'erreur'; readonly erreur: ApiErreur }
  | { readonly phase: 'prete'; readonly portefeuilles: readonly PortfolioDetail[] }

/**
 * La liste, dans la langue de la page : la raison d'une valorisation
 * impossible est rédigée par le serveur. Un changement de langue la relit,
 * en gardant l'ancienne affichée pendant ce temps.
 *
 * `apresAffichage` : le premier chargement attend que la page soit peinte.
 * Il est lu au montage, une fois.
 */
export function useListe(
  langue: Langue = 'fr',
  apresAffichage = false,
): { etat: EtatListe; recharger: () => Promise<void> } {
  const [etat, setEtat] = useState<EtatListe>({ phase: 'chargement' })
  const premierChargement = useRef(true)

  const recharger = useCallback(async () => {
    try {
      const portefeuilles = await getPortfolios(langue)
      setEtat({ phase: 'prete', portefeuilles })
    } catch (cause) {
      setEtat({ phase: 'erreur', erreur: versApiErreur(cause, langue) })
    }
  }, [langue])

  useEffect(() => {
    const premier = premierChargement.current
    premierChargement.current = false
    if (premier && apresAffichage) return apresLAffichage(() => void recharger())
    void recharger()
  }, [recharger])

  return { etat, recharger }
}
