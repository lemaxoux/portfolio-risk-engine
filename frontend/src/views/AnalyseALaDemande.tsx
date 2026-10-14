/**
 * L'analyse, chargée à la demande — DESIGN.md §19.9 (chantier 9.4).
 *
 * ═══ CE QUI SORT DU FICHIER D'ENTRÉE ═══
 *
 * `views/Analyse`, ses six sections et la bibliothèque de graphiques. Le
 * fichier d'entrée porte ce que toute page affiche, et rien de ce qui dessine
 * un graphique. L'`import()` ci-dessous est le SEUL du client : rien ne se
 * découpe par langue, puisqu'un changement de langue laisse la page en place
 * (§13), et la méthodologie reste dans le fichier d'entrée, où l'analyse lit
 * les titres de ses liens. `src/decoupage.test.ts` tient les deux. Le même
 * code vaut pour les deux builds.
 *
 * Le même fichier porte l'analyse du portefeuille saisi sur le site
 * (chantier 9.6) : ses six sections sont celles de l'analyse. Hors du build
 * de démonstration, elle n'est pas demandée au module.
 *
 * ═══ LA PAGE D'ATTENTE, ET CE QUI LA REND RARE ═══
 *
 * Tant que le fichier manque, une page d'attente tient la place de
 * l'analyse : son titre, son cadre, son squelette (`aria-busy`). Elle ne
 * prend ni le focus ni le défilement (`attente`, `components/Cadre`) :
 * l'analyse fait l'unique déplacement de la navigation en s'installant,
 * retour depuis la méthode compris.
 *
 * Le fichier est aussi demandé en tâche de fond, une fois l'application
 * affichée (`App.tsx`). Quand il est déjà là, la vue est rendue directement
 * et la page d'attente n'existe pas. Ce choix se fait AU MONTAGE, une fois :
 * la vue ne change pas de place dans l'arbre pendant qu'elle est affichée,
 * et garde son état.
 *
 * ═══ LE FICHIER N'ARRIVE PAS ═══
 *
 * Le réseau est coupé, ou l'onglet est resté ouvert pendant une
 * reconstruction. La page le dit à la place de l'analyse, avec l'action
 * suivante (§13), au lieu de laisser un écran blanc. Cette action est de
 * recharger la page, et pas de réessayer sur place : Chrome ne redemande pas,
 * dans le même document, un module qui n'est pas arrivé (constaté le
 * 2026-10-11, les deux pannes rejouées par le protocole DevTools).
 */
import {
  lazy,
  Suspense,
  useEffect,
  useState,
  type ComponentProps,
  type ComponentType,
  type LazyExoticComponent,
  type ReactNode,
} from 'react'

import { ApiErreur } from '../api/client'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { EtatDuServeur } from '../components/EtatDuServeur'
import { MessageErreur } from '../components/MessageErreur'
import {
  AncresSections,
  pagesApplication,
  RailPages,
  type PageApplication,
} from '../components/Navigation'
import { SqueletteAnalyse } from '../components/Squelette'
import { useLangue } from '../lib/langue'
import { cheminDe, memoriserLeSaisi, memoriserPortefeuille, SAISI } from '../lib/route'
import controles from '../styles/controles.module.css'
import type { VueAnalyse, VueAnalyseDuSaisi } from './Analyse'

type Props = ComponentProps<typeof VueAnalyse>
type PropsDuSaisi = ComponentProps<NonNullable<typeof VueAnalyseDuSaisi>>

/** Les deux vues du fichier de l'analyse ; celle du portefeuille saisi, sur le site seulement. */
interface Vues {
  readonly base: ComponentType<Props>
  readonly saisi: ComponentType<PropsDuSaisi> | null
}

/** Les vues, une fois leur fichier arrivé. */
let chargees: Vues | null = null
let demande: Promise<Vues> | null = null

/**
 * Demande le fichier de l'analyse, une seule fois tant que la demande tient.
 * Un échec n'est pas gardé ici : la demande suivante repart, pour un
 * navigateur qui accepte de la refaire.
 */
export function chargerLAnalyse(): Promise<Vues> {
  demande ??= import('./Analyse').then(
    (module) => {
      chargees = { base: module.VueAnalyse, saisi: module.VueAnalyseDuSaisi }
      return chargees
    },
    (cause: unknown) => {
      demande = null
      throw cause
    },
  )
  return demande
}

/**
 * Le cadre de l'analyse sans l'analyse : celui qu'elle a elle-même pendant
 * qu'elle charge ses données, pour que rien ne bouge quand elle arrive.
 */
function CadreDeLAnalyse({
  nom,
  page,
  pages,
  attente,
  children,
}: {
  nom: string
  page: string
  pages: readonly PageApplication[]
  attente: boolean
  children: ReactNode
}) {
  const { libelles } = useLangue()
  const titre = libelles.analyse.titre(nom)
  return (
    <Cadre
      titre={titre}
      page={page}
      occupe={attente}
      attente={attente}
      entete={<BandeauSimple portefeuille={nom} />}
      rail={<RailPages pages={pages} />}
    >
      <h1 tabIndex={-1} className="visuellement-cache">
        {titre}
      </h1>
      <AncresSections pages={pages} sections={false} />
      {children}
    </Cadre>
  )
}

/** Ce qui tient la place de l'analyse quand son fichier n'est pas arrivé. */
function FichierNonCharge() {
  const { libelles } = useLangue()
  return (
    <MessageErreur
      erreur={new ApiErreur(0, libelles.application.pageNonChargee)}
      action={
        <button type="button" className={controles.bouton} onClick={() => window.location.reload()}>
          {libelles.application.rechargerLaPage}
        </button>
      }
    />
  )
}

/** Le cadre d'un portefeuille de la liste : son nom, son adresse, ses pages. */
function CadreDuPortefeuille({
  portefeuille,
  attente,
  children,
}: {
  portefeuille: Props['portefeuille']
  attente: boolean
  children: ReactNode
}) {
  const { langue } = useLangue()
  return (
    <CadreDeLAnalyse
      nom={portefeuille.name}
      page={cheminDe({ vue: 'analyse', id: portefeuille.id })}
      pages={pagesApplication('analyse', portefeuille.id, langue)}
      attente={attente}
    >
      {children}
    </CadreDeLAnalyse>
  )
}

/** Le cadre du portefeuille saisi, sur le site. */
function CadreDuSaisi({ attente, children }: { attente: boolean; children: ReactNode }) {
  const { langue, libelles } = useLangue()
  return (
    <CadreDeLAnalyse
      nom={libelles.saisi.nom}
      page={cheminDe({ vue: 'saisi' })}
      pages={pagesApplication('analyse', SAISI, langue)}
      attente={attente}
    >
      {children}
    </CadreDeLAnalyse>
  )
}

/** À la place de l'analyse, quand son fichier n'est pas arrivé. */
function AnalyseNonChargee({ portefeuille }: Props) {
  return (
    <CadreDuPortefeuille portefeuille={portefeuille} attente={false}>
      <FichierNonCharge />
    </CadreDuPortefeuille>
  )
}

function AnalyseDuSaisiNonChargee() {
  return (
    <CadreDuSaisi attente={false}>
      <FichierNonCharge />
    </CadreDuSaisi>
  )
}

/** La vue d'un portefeuille de la liste, déjà chargée, ou celle qui attend son fichier. */
function vueAuMontage(): ComponentType<Props> | LazyExoticComponent<ComponentType<Props>> {
  return (
    chargees?.base ??
    lazy<ComponentType<Props>>(() =>
      chargerLAnalyse().then(
        (vues) => ({ default: vues.base }),
        () => ({ default: AnalyseNonChargee }),
      ),
    )
  )
}

/** La vue du portefeuille saisi, déjà chargée, ou celle qui attend son fichier. */
function vueDuSaisiAuMontage():
  | ComponentType<PropsDuSaisi>
  | LazyExoticComponent<ComponentType<PropsDuSaisi>> {
  return (
    chargees?.saisi ??
    lazy<ComponentType<PropsDuSaisi>>(() =>
      chargerLAnalyse().then(
        (vues) => ({ default: vues.saisi ?? AnalyseDuSaisiNonChargee }),
        () => ({ default: AnalyseDuSaisiNonChargee }),
      ),
    )
  )
}

export function AnalyseALaDemande(props: Props) {
  const [Vue] = useState(vueAuMontage)
  const id = props.portefeuille.id

  // Le portefeuille est consulté dès que sa page s'ouvre, pas quand le
  // fichier de l'analyse arrive : quitter la page d'attente pour la
  // méthodologie laisse quand même son nom dans le bandeau.
  useEffect(() => {
    memoriserPortefeuille(id)
  }, [id])

  return (
    <Suspense
      fallback={
        <CadreDuPortefeuille portefeuille={props.portefeuille} attente>
          <SqueletteAnalyse />
        </CadreDuPortefeuille>
      }
    >
      <Vue {...props} />
    </Suspense>
  )
}

/** L'analyse du portefeuille saisi, sur le site (chantier 9.6). */
export function AnalyseDuSaisiALaDemande(props: PropsDuSaisi) {
  const [Vue] = useState(vueDuSaisiAuMontage)

  useEffect(() => {
    memoriserLeSaisi()
  }, [])

  return (
    <Suspense
      fallback={
        // La place de l'état du serveur est prise dès l'attente : la vue qui
        // arrive l'occupe sans rien déplacer.
        <CadreDuSaisi attente>
          <EtatDuServeur etape={null} />
          <SqueletteAnalyse />
        </CadreDuSaisi>
      }
    >
      <Vue {...props} />
    </Suspense>
  )
}
