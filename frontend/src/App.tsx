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
 *
 * ═══ LA LANGUE (chantier 7D) ═══
 *
 * L'application tient la langue affichée et la fournit à toutes les pages
 * (`lib/langue.ts`). Changer de langue demande d'abord l'écran d'acceptation
 * de l'autre langue : s'il a déjà été accepté, les pages restent en place et
 * se relisent dans la nouvelle langue ; sinon, il remplace la page, comme à
 * l'arrivée, et la garde des modifications non enregistrées est consultée
 * avant (`remplacerLaPage`). La langue ne change qu'une fois cette réponse
 * connue : aucune page ne s'affiche dans une langue dont le texte n'a pas
 * été accepté.
 *
 * ═══ LA DÉMONSTRATION N'A PAS DE PAGE DE SAISIE (chantier 9.2) ═══
 *
 * Dans le build de démonstration, `/portefeuilles/<id>/positions` n'est
 * l'adresse d'aucune page : elle rend « Page introuvable », comme toute
 * adresse inconnue, et la page des positions sort du build avec ses
 * écritures.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import {
  ApiErreur,
  DEMO,
  getDisclaimer,
  titreSourceInjoignable,
  versApiErreur,
} from './api/client'
import type { Disclaimer, PortfolioDetail } from './api/types'
import { BandeauSimple } from './components/Bandeau'
import { Cadre } from './components/Cadre'
import { MessageErreur } from './components/MessageErreur'
import { SqueletteAnalyse, SqueletteTableau } from './components/Squelette'
import { aAccepte } from './lib/acceptation'
import {
  appliquerLangue,
  ContexteDeLangue,
  langueDeLaPage,
  langueDuSite,
  useLangue,
  type Langue,
} from './lib/langue'
import { useListe, type EtatListe } from './lib/liste'
import {
  cheminDe,
  dernierPortefeuille,
  marquerGesteDecide,
  naviguer,
  portefeuilleDAccueil,
  remplacerLaPage,
  useRoute,
} from './lib/route'
import controles from './styles/controles.module.css'
import { Acceptation } from './views/Acceptation'
import { VueAnalyse } from './views/Analyse'
import { PageInconnue, PortefeuilleIntrouvable } from './views/Introuvable'
import { VueMethodologie } from './views/Methodologie'
import { VuePortefeuilles } from './views/Portefeuilles'
import { VuePositions } from './views/Positions'

type EtatAcceptation =
  | { phase: 'verification' }
  | { phase: 'erreur'; erreur: ApiErreur }
  /** `decidee` : l'écran remplace une page après un geste, et son titre prend le focus. */
  | { phase: 'acceptation'; bandeau: Disclaimer; decidee?: boolean }
  | { phase: 'acceptee' }

export function App() {
  const [langue, setLangue] = useState<Langue>(langueDeLaPage)
  const [etat, setEtat] = useState<EtatAcceptation>({ phase: 'verification' })
  const langueDuDemarrage = useRef(langue)

  useEffect(() => {
    let vivant = true
    const premiere = langueDuDemarrage.current
    getDisclaimer(premiere).then(
      (bandeau) => {
        if (!vivant) return
        setEtat(
          aAccepte(bandeau.text, premiere)
            ? { phase: 'acceptee' }
            : { phase: 'acceptation', bandeau },
        )
      },
      (cause: unknown) => {
        if (vivant) setEtat({ phase: 'erreur', erreur: versApiErreur(cause, premiere) })
      },
    )
    return () => {
      vivant = false
    }
  }, [])

  const changerLangue = useCallback(
    (nouvelle: Langue) => {
      if (nouvelle === langue) return
      const passer = (suivant: EtatAcceptation) => {
        // Un geste de l'utilisateur : la page qui s'affiche, si elle change,
        // s'ouvre en haut, son titre focalisé (chantier 7E).
        marquerGesteDecide()
        appliquerLangue(nouvelle)
        setLangue(nouvelle)
        setEtat(suivant)
      }
      getDisclaimer(nouvelle).then(
        (bandeau) => {
          if (aAccepte(bandeau.text, nouvelle)) passer({ phase: 'acceptee' })
          else remplacerLaPage(() => passer({ phase: 'acceptation', bandeau, decidee: true }))
        },
        (cause: unknown) => {
          remplacerLaPage(() => passer({ phase: 'erreur', erreur: versApiErreur(cause, nouvelle) }))
        },
      )
    },
    [langue],
  )

  const contexte = useMemo(() => langueDuSite(langue, changerLangue), [langue, changerLangue])

  return (
    <ContexteDeLangue.Provider value={contexte}>
      <Ecran etat={etat} accepter={() => setEtat({ phase: 'acceptee' })} />
    </ContexteDeLangue.Provider>
  )
}

/** L'écran que demande l'état de l'acceptation, dans la langue affichée. */
function Ecran({ etat, accepter }: { etat: EtatAcceptation; accepter: () => void }) {
  const { langue, libelles } = useLangue()

  if (etat.phase === 'acceptation') {
    // Une clé par langue : la case cochée sous un texte ne l'est pas sous
    // l'autre.
    return (
      <Acceptation
        key={langue}
        bandeau={etat.bandeau}
        onAccepte={accepter}
        focaliser={etat.decidee === true}
      />
    )
  }
  if (etat.phase === 'acceptee') return <Application />

  return (
    <Cadre
      titre={
        etat.phase === 'erreur' ? titreSourceInjoignable(langue) : libelles.application.chargement
      }
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
              {libelles.application.rechargerLaPage}
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
  const { langue } = useLangue()
  const { etat: liste, recharger } = useListe(langue)
  const [annonce, setAnnonce] = useState<Annonce | null>(null)

  const annoncer = useCallback((texte: string, page: string) => {
    setAnnonce({ texte, page })
  }, [])

  const chemin = route.vue === 'inconnue' ? route.chemin : cheminDe(route)
  const annonceIci = annonce !== null && annonce.page === chemin ? annonce.texte : null

  /**
   * La page d'un portefeuille : il est lu dans la liste, qui dit s'il existe
   * avant tout autre appel. `forme` est celle du squelette en attendant.
   */
  const avecPortefeuille = (
    id: number,
    forme: 'analyse' | 'tableau',
    rendre: (portefeuille: PortfolioDetail) => ReactNode,
  ): ReactNode => {
    if (liste.phase !== 'prete') {
      return <ListeEnAttente liste={liste} recharger={recharger} page={chemin} forme={forme} />
    }
    const portefeuille = liste.portefeuilles.find((p) => p.id === id)
    if (portefeuille === undefined) return <PortefeuilleIntrouvable id={id} page={chemin} />
    return rendre(portefeuille)
  }

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
      return avecPortefeuille(route.id, 'analyse', (portefeuille) => (
        <VueAnalyse portefeuille={portefeuille} annonce={annonceIci} />
      ))
    case 'positions':
      if (DEMO) return <PageInconnue chemin={chemin} />
      return avecPortefeuille(route.id, 'tableau', (portefeuille) => (
        // Une clé par portefeuille : passer de l'un à l'autre repart d'un
        // tableau neuf, jamais des lignes du précédent.
        <VuePositions
          key={portefeuille.id}
          portefeuille={portefeuille}
          recharger={recharger}
          annonce={annonceIci}
          annoncer={annoncer}
        />
      ))
    case 'methodologie': {
      // Elle ne dépend d'aucun portefeuille, et n'attend pas la liste. Le
      // bandeau nomme le dernier consulté s'il existe encore ; sinon aucun,
      // et pas le premier de la liste, que personne n'a ouvert.
      const memorise = dernierPortefeuille()
      const portefeuille =
        liste.phase === 'prete'
          ? (liste.portefeuilles.find((p) => p.id === memorise) ?? null)
          : null
      return <VueMethodologie portefeuille={portefeuille} />
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

  return <ListeEnAttente liste={liste} recharger={recharger} page="/" forme="analyse" />
}

/**
 * La liste n'est pas encore là, ou n'a pas pu être lue. Le squelette a la
 * forme de la page attendue (§13) : l'analyse, ou le tableau de saisie.
 */
function ListeEnAttente({
  liste,
  recharger,
  page,
  forme,
}: {
  liste: EtatListe
  recharger: () => Promise<void>
  page: string
  forme: 'analyse' | 'tableau'
}) {
  const { libelles } = useLangue()
  return (
    <Cadre
      titre={
        liste.phase === 'erreur'
          ? libelles.application.portefeuillesIllisibles
          : libelles.application.chargement
      }
      page={page}
      occupe={liste.phase !== 'erreur'}
      entete={<BandeauSimple portefeuille={null} />}
    >
      {liste.phase === 'erreur' ? (
        <MessageErreur
          erreur={liste.erreur}
          action={
            <button type="button" className={controles.bouton} onClick={() => void recharger()}>
              {libelles.application.rechargerLaListe}
            </button>
          }
        />
      ) : forme === 'tableau' ? (
        <SqueletteTableau rangees={6} />
      ) : (
        <SqueletteAnalyse />
      )}
    </Cadre>
  )
}
