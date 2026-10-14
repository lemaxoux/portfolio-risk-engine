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
 * ═══ LES PORTEFEUILLES DE LA DÉMONSTRATION N'ONT PAS DE SAISIE (9.2) ═══
 *
 * Dans le build de démonstration, `/portefeuilles/<id>/positions` n'est
 * l'adresse d'aucune page : elle rend « Page introuvable », comme toute
 * adresse inconnue, et l'enregistrement en base sort du build avec ses
 * écritures.
 *
 * ═══ L'ÉCRAN D'ACCEPTATION, DEVANT LE PORTEFEUILLE SAISI (9.4, 9.6) ═══
 *
 * Cet écran a été décidé pour quelqu'un qui analyse son propre portefeuille
 * (DESIGN.md §15). Les portefeuilles d'exemple de la démonstration ne le sont
 * pas : rien n'attend le texte au démarrage, et le texte se lit à l'adresse
 * `/avertissement`, qui n'est une page que là (§19.6). Dans l'application,
 * elle rend « Page introuvable ».
 *
 * Le visiteur peut aussi saisir son propre portefeuille, que le serveur
 * public analyse (chantier 9.6). Ses deux pages, `/portefeuilles/saisi` et
 * `/portefeuilles/saisi/positions`, sont gardées par l'écran d'acceptation de
 * la langue de la page, celui de l'application, avec le texte du site : tant
 * qu'il n'est pas accepté, il remplace la page, et rien n'est envoyé. Il se
 * traverse une fois par langue ; changer de langue sur l'une de ces deux
 * pages, vers une langue dont le texte n'a pas été accepté, remplace la page
 * par l'écran de cette langue, la garde des modifications consultée d'abord,
 * comme dans l'application. Ailleurs, le changement de langue reste en place.
 * L'acceptation délivre la preuve sans laquelle `client.ts` n'envoie rien.
 * Dans l'application, ces deux adresses rendent « Page introuvable ».
 *
 * ═══ DANS LA DÉMONSTRATION, `/` EST UNE PAGE (chantier 9.4) ═══
 *
 * L'adresse `/` y rend la présentation du projet (`views/Presentation`,
 * DESIGN.md §19) au lieu de rediriger. Elle n'ouvre plus le dernier
 * portefeuille consulté, qui reste mémorisé pour le bandeau et pour
 * « Analyse ». Dans l'application, `/` reste la redirection décrite plus
 * bas, et la présentation sort de son build.
 *
 * ═══ L'ANALYSE SE CHARGE À LA DEMANDE (chantier 9.4) ═══
 *
 * Son fichier, avec la bibliothèque de graphiques, n'est plus dans le fichier
 * d'entrée (`views/AnalyseALaDemande`, DESIGN.md §19.9). Il est demandé en
 * tâche de fond une fois l'application affichée : la page d'attente ne se
 * voit que si l'on va à une analyse avant qu'il soit arrivé. Un échec de
 * cette avance est muet ; c'est la navigation qui le dira.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react'

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
import { aAccepte, preuveDAcceptation, type PreuveDAcceptation } from './lib/acceptation'
import { apresLAffichage } from './lib/affichage'
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
  lireRoute,
  marquerGesteDecide,
  naviguer,
  portefeuilleDAccueil,
  remplacerLaPage,
  SAISI,
  saisiEnVue,
  useRoute,
  type PortefeuilleEnVue,
} from './lib/route'
import { lireLeSaisi } from './lib/saisi'
import controles from './styles/controles.module.css'
import { Acceptation } from './views/Acceptation'
import {
  AnalyseALaDemande,
  AnalyseDuSaisiALaDemande,
  chargerLAnalyse,
} from './views/AnalyseALaDemande'
import { VueAvertissement } from './views/Avertissement'
import { PageInconnue, PortefeuilleIntrouvable } from './views/Introuvable'
import { VueMethodologie } from './views/Methodologie'
import { VuePortefeuilles } from './views/Portefeuilles'
import { VuePositions, VuePositionsDuSaisi } from './views/Positions'
import { VuePresentation } from './views/Presentation'

type EtatAcceptation =
  | { phase: 'verification' }
  | { phase: 'erreur'; erreur: ApiErreur }
  /** `decidee` : l'écran remplace une page après un geste, et son titre prend le focus. */
  | { phase: 'acceptation'; bandeau: Disclaimer; decidee?: boolean }
  | { phase: 'acceptee' }

/**
 * La garde des deux pages du portefeuille saisi, sur le site (chantier 9.6),
 * pour la langue affichée. `inconnue` : pas encore vérifiée dans cette langue.
 * `acceptee` porte la preuve que `client.ts` demande avant tout envoi.
 */
type GardeDuSaisi =
  | { phase: 'inconnue' }
  | { phase: 'erreur'; erreur: ApiErreur }
  /** `decidee` : l'écran remplace une page après un geste, et son titre prend le focus. */
  | { phase: 'acceptation'; bandeau: Disclaimer; decidee?: boolean }
  | { phase: 'acceptee'; preuve: PreuveDAcceptation }

/** L'adresse est-elle celle d'une des deux pages du portefeuille saisi ? */
function estUnePageDuSaisi(chemin: string): boolean {
  const vue = lireRoute(chemin).vue
  return vue === 'saisi' || vue === 'saisi-positions'
}

export function App() {
  const [langue, setLangue] = useState<Langue>(langueDeLaPage)
  const [etat, setEtat] = useState<EtatAcceptation>(
    DEMO ? { phase: 'acceptee' } : { phase: 'verification' },
  )
  const [garde, setGarde] = useState<GardeDuSaisi>({ phase: 'inconnue' })
  const langueDuDemarrage = useRef(langue)

  useEffect(() => {
    if (DEMO) return
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
      if (DEMO) {
        // Hors des pages du portefeuille saisi, la page reste en place ; la
        // garde se vérifiera dans la nouvelle langue en y arrivant.
        if (!estUnePageDuSaisi(window.location.pathname)) {
          setGarde({ phase: 'inconnue' })
          passer({ phase: 'acceptee' })
          return
        }
        getDisclaimer(nouvelle).then(
          (bandeau) => {
            const preuve = preuveDAcceptation(bandeau.text, nouvelle)
            if (preuve !== null) {
              setGarde({ phase: 'acceptee', preuve })
              passer({ phase: 'acceptee' })
              return
            }
            remplacerLaPage(() => {
              setGarde({ phase: 'acceptation', bandeau, decidee: true })
              passer({ phase: 'acceptee' })
            })
          },
          (cause: unknown) => {
            remplacerLaPage(() => {
              setGarde({ phase: 'erreur', erreur: versApiErreur(cause, nouvelle) })
              passer({ phase: 'acceptee' })
            })
          },
        )
        return
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
      <Ecran
        etat={etat}
        accepter={() => setEtat({ phase: 'acceptee' })}
        garde={garde}
        setGarde={setGarde}
      />
    </ContexteDeLangue.Provider>
  )
}

interface PropsDeLaGarde {
  readonly garde: GardeDuSaisi
  readonly setGarde: Dispatch<SetStateAction<GardeDuSaisi>>
}

/** L'écran que demande l'état de l'acceptation, dans la langue affichée. */
function Ecran({
  etat,
  accepter,
  garde,
  setGarde,
}: { etat: EtatAcceptation; accepter: () => void } & PropsDeLaGarde) {
  const { langue, libelles } = useLangue()

  if (DEMO) return <Application garde={garde} setGarde={setGarde} />
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
  if (etat.phase === 'acceptee') return <Application garde={garde} setGarde={setGarde} />

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

function Application({ garde, setGarde }: PropsDeLaGarde) {
  const route = useRoute()
  const { langue, libelles } = useLangue()
  // Sur la présentation de la démonstration, la liste part après le premier
  // affichage : son premier écran n'attend aucune requête (DESIGN.md §19.9).
  const { etat: liste, recharger } = useListe(langue, DEMO && route.vue === 'accueil')
  const [annonce, setAnnonce] = useState<Annonce | null>(null)

  const annoncer = useCallback((texte: string, page: string) => {
    setAnnonce({ texte, page })
  }, [])

  // Le fichier de l'analyse, en tâche de fond, une fois la page affichée.
  useEffect(() => apresLAffichage(() => void chargerLAnalyse().catch(() => undefined)), [])

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

  /**
   * Le portefeuille que nomme le bandeau d'une page qui n'en dépend pas : le
   * dernier consulté s'il existe encore ; sinon aucun, et pas le premier de
   * la liste, que personne n'a ouvert. Sur le site, ce peut être le
   * portefeuille saisi (chantier 9.6).
   */
  const portefeuilleEnVue = (): PortefeuilleEnVue | null => {
    if (DEMO && saisiEnVue()) return { id: SAISI, name: libelles.saisi.nom }
    if (liste.phase !== 'prete') return null
    const memorise = dernierPortefeuille()
    return liste.portefeuilles.find((p) => p.id === memorise) ?? null
  }

  switch (route.vue) {
    case 'accueil':
      if (DEMO) {
        return (
          <VuePresentation
            liste={liste}
            recharger={recharger}
            portefeuille={portefeuilleEnVue()}
          />
        )
      }
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
        <AnalyseALaDemande portefeuille={portefeuille} annonce={annonceIci} />
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
    case 'saisi':
      // Les deux pages du portefeuille saisi n'existent que sur le site, où
      // l'écran d'acceptation les garde.
      if (!DEMO) return <PageInconnue chemin={chemin} />
      return (
        <GardeDuPortefeuilleSaisi garde={garde} setGarde={setGarde} forme="analyse">
          {(preuve) => (
            <AnalyseDuSaisiALaDemande saisi={lireLeSaisi()} preuve={preuve} annonce={annonceIci} />
          )}
        </GardeDuPortefeuilleSaisi>
      )
    case 'saisi-positions':
      if (!DEMO) return <PageInconnue chemin={chemin} />
      return (
        <GardeDuPortefeuilleSaisi garde={garde} setGarde={setGarde} forme="tableau">
          {(preuve) => (
            <VuePositionsDuSaisi preuve={preuve} annonce={annonceIci} annoncer={annoncer} />
          )}
        </GardeDuPortefeuilleSaisi>
      )
    case 'methodologie':
      // Elle ne dépend d'aucun portefeuille, et n'attend pas la liste.
      return <VueMethodologie portefeuille={portefeuilleEnVue()} />
    case 'avertissement':
      // Une page de la démonstration seulement (DESIGN.md §19.6). Ailleurs,
      // l'adresse reste celle d'aucune page, citée telle qu'elle a été écrite.
      if (!DEMO) return <PageInconnue chemin={window.location.pathname} />
      return <VueAvertissement portefeuille={portefeuilleEnVue()} />
    case 'inconnue':
      return <PageInconnue chemin={chemin} />
  }
}

/**
 * La garde des deux pages du portefeuille saisi (chantier 9.6) : le texte du
 * site, lu dans la langue de la page ; l'écran d'acceptation tant qu'il n'est
 * pas accepté ; la page, avec la preuve, une fois qu'il l'est. Rien n'est
 * envoyé avant : la page n'est pas montée.
 */
function GardeDuPortefeuilleSaisi({
  garde,
  setGarde,
  forme,
  children,
}: PropsDeLaGarde & {
  forme: 'analyse' | 'tableau'
  children: (preuve: PreuveDAcceptation) => ReactNode
}) {
  const { langue, libelles } = useLangue()
  // Une preuve d'une autre langue ne vaut pas pour celle-ci : la garde se
  // vérifie de nouveau.
  const aVerifier =
    garde.phase === 'inconnue' || (garde.phase === 'acceptee' && garde.preuve.langue !== langue)

  useEffect(() => {
    if (!aVerifier) return
    let vivant = true
    getDisclaimer(langue).then(
      (bandeau) => {
        if (!vivant) return
        const preuve = preuveDAcceptation(bandeau.text, langue)
        setGarde(preuve !== null ? { phase: 'acceptee', preuve } : { phase: 'acceptation', bandeau })
      },
      (cause: unknown) => {
        if (vivant) setGarde({ phase: 'erreur', erreur: versApiErreur(cause, langue) })
      },
    )
    return () => {
      vivant = false
    }
  }, [aVerifier, langue, setGarde])

  if (garde.phase === 'acceptee' && !aVerifier) return children(garde.preuve)
  if (garde.phase === 'acceptation') {
    const bandeau = garde.bandeau
    // Une clé par langue : la case cochée sous un texte ne l'est pas sous
    // l'autre.
    return (
      <Acceptation
        key={langue}
        bandeau={bandeau}
        focaliser={garde.decidee === true}
        onAccepte={() => {
          const preuve = preuveDAcceptation(bandeau.text, langue)
          if (preuve !== null) setGarde({ phase: 'acceptee', preuve })
        }}
      />
    )
  }
  return (
    <Cadre
      titre={garde.phase === 'erreur' ? titreSourceInjoignable(langue) : libelles.application.chargement}
      page={window.location.pathname}
      occupe={garde.phase !== 'erreur'}
      entete={<BandeauSimple portefeuille={libelles.saisi.nom} />}
    >
      {garde.phase === 'erreur' ? (
        <MessageErreur
          erreur={garde.erreur}
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
      ) : forme === 'tableau' ? (
        <SqueletteTableau rangees={6} />
      ) : (
        <SqueletteAnalyse />
      )}
    </Cadre>
  )
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
