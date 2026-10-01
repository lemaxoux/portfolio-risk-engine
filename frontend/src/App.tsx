/**
 * Coquille de l'application : l'acceptation, puis les routes — DESIGN.md §13,
 * §15.
 *
 * ═══ L'ACCEPTATION PRÉCÈDE TOUT ═══
 *
 * Le bandeau d'acceptation est demandé AVANT la liste des portefeuilles et
 * avant l'analyse, quelle que soit l'adresse d'arrivée. Ce n'est pas un détail
 * d'ordonnancement : une page qui afficherait des chiffres puis demanderait
 * l'acceptation par-dessus aurait déjà montré ce que l'acceptation encadre.
 *
 * ═══ LA LISTE AVANT LES PAGES ═══
 *
 * La liste des portefeuilles est chargée une fois, puis relue après chaque
 * écriture. Toutes les pages y lisent ce qu'elles doivent savoir d'un
 * portefeuille avant tout autre appel — qu'il existe, son nom, qu'il est vide.
 *
 * ═══ UNE ANNONCE PAR PAGE ═══
 *
 * « Portefeuille « Démo » créé. » est adressé à la page où l'on arrive, et ne
 * s'affiche que là : l'annonce d'une action ne suit pas l'utilisateur de page
 * en page.
 */
import { useCallback, useEffect, useState } from 'react'

import { ApiErreur, getDisclaimer, versApiErreur } from './api/client'
import type { Disclaimer } from './api/types'
import { BandeauSimple } from './components/Bandeau'
import { Cadre } from './components/Cadre'
import { MessageErreur } from './components/MessageErreur'
import { SqueletteAnalyse } from './components/Squelette'
import { aAccepte } from './lib/acceptation'
import { useListe, type EtatListe } from './lib/liste'
import {
  cheminDe,
  dernierPortefeuille,
  naviguer,
  portefeuilleDAccueil,
  useRoute,
} from './lib/route'
import controles from './styles/controles.module.css'
import { Acceptation } from './views/Acceptation'
import { VueAnalyse } from './views/Analyse'
import { PageInconnue, PortefeuilleIntrouvable } from './views/Introuvable'
import { VuePortefeuilles } from './views/Portefeuilles'
import { VuePositions } from './views/Positions'

type EtatAcceptation =
  | { phase: 'verification' }
  | { phase: 'erreur'; erreur: ApiErreur }
  | { phase: 'acceptation'; bandeau: Disclaimer }
  | { phase: 'acceptee' }

export function App() {
  const [etat, setEtat] = useState<EtatAcceptation>({ phase: 'verification' })

  useEffect(() => {
    let vivant = true
    getDisclaimer().then(
      (bandeau) => {
        if (!vivant) return
        setEtat(aAccepte(bandeau.text) ? { phase: 'acceptee' } : { phase: 'acceptation', bandeau })
      },
      (cause: unknown) => {
        if (vivant) setEtat({ phase: 'erreur', erreur: versApiErreur(cause) })
      },
    )
    return () => {
      vivant = false
    }
  }, [])

  if (etat.phase === 'acceptation') {
    return <Acceptation bandeau={etat.bandeau} onAccepte={() => setEtat({ phase: 'acceptee' })} />
  }
  if (etat.phase === 'acceptee') return <Application />

  return (
    <Cadre
      titre={etat.phase === 'erreur' ? 'API injoignable' : 'Chargement'}
      page="demarrage"
      occupe={etat.phase === 'verification'}
      entete={<BandeauSimple portefeuille={null} navigation={false} />}
    >
      {etat.phase === 'verification' ? (
        <SqueletteAnalyse />
      ) : (
        <MessageErreur
          erreur={etat.erreur}
          action={
            <button
              type="button"
              className={controles.bouton}
              onClick={() => window.location.reload()}
            >
              Recharger la page
            </button>
          }
        />
      )}
    </Cadre>
  )
}

interface Annonce {
  readonly texte: string
  readonly page: string
}

function Application() {
  const route = useRoute()
  const { etat: liste, recharger } = useListe()
  const [annonce, setAnnonce] = useState<Annonce | null>(null)

  const annoncer = useCallback((texte: string, page: string) => {
    setAnnonce({ texte, page })
  }, [])

  const chemin = route.vue === 'inconnue' ? route.chemin : cheminDe(route)
  const annonceIci = annonce !== null && annonce.page === chemin ? annonce.texte : null

  switch (route.vue) {
    case 'accueil':
      return <Accueil liste={liste} recharger={recharger} />
    case 'portefeuilles':
      return (
        <VuePortefeuilles
          liste={liste}
          recharger={recharger}
          annonce={annonceIci}
          annoncer={annoncer}
        />
      )
    case 'analyse':
    case 'positions': {
      if (liste.phase !== 'prete') {
        return <ListeEnAttente liste={liste} recharger={recharger} page={chemin} />
      }
      const portefeuille = liste.portefeuilles.find((p) => p.id === route.id)
      if (portefeuille === undefined) {
        return <PortefeuilleIntrouvable id={route.id} page={chemin} />
      }
      return route.vue === 'analyse' ? (
        <VueAnalyse portefeuille={portefeuille} annonce={annonceIci} />
      ) : (
        // Une clé par portefeuille : passer de l'un à l'autre repart d'un
        // tableau neuf, jamais des lignes du précédent.
        <VuePositions
          key={portefeuille.id}
          portefeuille={portefeuille}
          recharger={recharger}
          annonce={annonceIci}
          annoncer={annoncer}
        />
      )
    }
    case 'inconnue':
      return <PageInconnue chemin={chemin} />
  }
}

/**
 * `/` : le dernier portefeuille ouvert s'il existe encore, sinon le premier,
 * sinon la liste — vide, avec sa proposition de créer. Une REDIRECTION, qui
 * remplace l'entrée d'historique : le retour arrière ne ramène pas ici.
 */
function Accueil({ liste, recharger }: { liste: EtatListe; recharger: () => Promise<void> }) {
  useEffect(() => {
    if (liste.phase !== 'prete') return
    const id = portefeuilleDAccueil(
      liste.portefeuilles.map((p) => p.id),
      dernierPortefeuille(),
    )
    naviguer(id === null ? cheminDe({ vue: 'portefeuilles' }) : cheminDe({ vue: 'analyse', id }), {
      remplacer: true,
    })
  }, [liste])

  return <ListeEnAttente liste={liste} recharger={recharger} page="/" />
}

/** La liste n'est pas encore là, ou n'a pas pu être lue. */
function ListeEnAttente({
  liste,
  recharger,
  page,
}: {
  liste: EtatListe
  recharger: () => Promise<void>
  page: string
}) {
  return (
    <Cadre
      titre={liste.phase === 'erreur' ? 'Portefeuilles illisibles' : 'Chargement'}
      page={page}
      occupe={liste.phase !== 'erreur'}
      entete={<BandeauSimple portefeuille={null} />}
    >
      {liste.phase === 'erreur' ? (
        <MessageErreur
          erreur={liste.erreur}
          action={
            <button type="button" className={controles.bouton} onClick={() => void recharger()}>
              Recharger la liste
            </button>
          }
        />
      ) : (
        <SqueletteAnalyse />
      )}
    </Cadre>
  )
}
