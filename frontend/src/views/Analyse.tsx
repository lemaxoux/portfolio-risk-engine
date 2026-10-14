/**
 * La page d'analyse d'un portefeuille — DESIGN.md §8.2, §13.
 *
 * Le portefeuille arrive de la LISTE, déjà chargée par l'application : son
 * nom, et ses positions telles que stockées. Un portefeuille sans position
 * se reconnaît donc à sa structure, sans appel d'analyse et sans lire le
 * texte d'un 409.
 *
 * L'analyse est redemandée quand les positions changent — leur CONTENU, et non
 * `updated_at`, daté au jour près : deux enregistrements le même jour
 * laisseraient sinon l'analyse du premier. Une page qui montrerait l'analyse
 * d'avant un enregistrement décrirait un portefeuille qui n'existe plus. Elle
 * l'est aussi quand la langue change : le serveur rédige ses phrases dans
 * celle de la page (chantier 7D).
 *
 * Pendant cette relecture, l'analyse affichée du MÊME portefeuille reste en
 * place, occupée (`aria-busy`), jusqu'à la nouvelle (chantier 7E). Le
 * squelette, lui, se dessinait avec le bandeau simple : le bandeau changeait
 * deux fois de composant, le bouton de langue avec lui, et le focus tombait
 * sur le corps de la page, ramenée en haut. Un autre portefeuille, ou une
 * erreur, repart du squelette.
 *
 * ═══ LES QUATRE ÉTATS (§13) ═══
 *
 * Vide : aucune position, reconnu à la liste — invitation, lien vers la
 * saisie, format CSV. En cours : la forme de la page, sans animation.
 * Insuffisant : le moteur a les positions mais n'en tire pas d'analyse (409,
 * moins de trois séances communes, indice absent) — son message, et la
 * section 1 depuis la valorisation de la liste ; une fenêtre seulement
 * COURTE, elle, donne une analyse, où chaque mesure indisponible dit
 * pourquoi. Erreur : le message et l'action suivante.
 *
 * En démonstration (chantier 9.2), rien ne mène à la saisie : les états vide
 * et insuffisant, que ses portefeuilles n'atteignent pas, n'y proposent ni le
 * lien vers les positions ni le format du fichier.
 *
 * Cette vue se charge à la demande (chantier 9.4). Ce qui tient à l'ouverture
 * de la page, et non à l'arrivée de son fichier, se fait avant elle : c'est
 * `views/AnalyseALaDemande` qui mémorise le portefeuille consulté.
 *
 * ═══ LE PORTEFEUILLE SAISI SUR LE SITE (chantier 9.6) ═══
 *
 * `VueAnalyseDuSaisi` montre l'analyse du portefeuille que le visiteur a
 * saisi, demandée au serveur public : les six sections, par les mêmes
 * composants (`pageDeLAnalyse`). Deux différences, en section 3 : la ligne
 * « Niveaux » et la courbe, qui lisent une série que la réponse publique n'a
 * pas, laissent place à une phrase. Le bandeau reçoit le nom et la date des
 * positions à part de l'analyse.
 *
 * Ses états : vide (rien de gardé dans ce navigateur) ; en cours, la forme de
 * la page et ce qu'observe le client, le serveur qui ne répond pas encore puis
 * le calcul (`EtatDuServeur`) ; refus du serveur, ses phrases et « Revoir les
 * positions » ; échec (limite atteinte, serveur occupé, aucune réponse), le
 * message et « Réessayer ». Une analyse déjà reçue pour la même composition,
 * dans la même langue, s'affiche sans nouvel appel (`lib/saisi`).
 */
import { useEffect, useState, type ReactNode } from 'react'

import {
  analyserLeSaisi,
  ApiErreur,
  attendreLeServeur,
  DEMO,
  estUnRefus,
  getAnalysis,
  versApiErreur,
} from '../api/client'
import type { Analysis, PortfolioDetail, PortfolioSeries, PublicAnalysis } from '../api/types'
import { Bandeau, BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { EtatDuServeur, type EtapeDuServeur } from '../components/EtatDuServeur'
import { FormatCsv } from '../components/FormatCsv'
import { Lien } from '../components/Lien'
import { MessageErreur } from '../components/MessageErreur'
import {
  AncresSections,
  pagesApplication,
  RailPages,
  RailSections,
  type PageApplication,
} from '../components/Navigation'
import { SqueletteAnalyse } from '../components/Squelette'
import type { PreuveDAcceptation } from '../lib/acceptation'
import { useLangue, type Langue } from '../lib/langue'
import { cheminDe, SAISI } from '../lib/route'
import { analyseDeposee, deposerLAnalyse, type PortefeuilleSaisi } from '../lib/saisi'
import controles from '../styles/controles.module.css'
import { SectionAuPire } from './SectionAuPire'
import { SectionCrise } from './SectionCrise'
import { SectionJourOrdinaire } from './SectionJourOrdinaire'
import { SectionMoteur } from './SectionMoteur'
import { SectionPortefeuille } from './SectionPortefeuille'
import { SectionRisque } from './SectionRisque'
import styles from './Pages.module.css'

type Etat =
  | { phase: 'chargement'; precedente: Analysis | null }
  | { phase: 'erreur'; erreur: ApiErreur }
  | { phase: 'insuffisant'; raison: ApiErreur }
  | { phase: 'analyse'; analyse: Analysis }

/**
 * L'analyse que la page garde affichée pendant qu'elle se relit : celle du
 * même portefeuille, déjà affichée ou déjà gardée. Aucune autre.
 */
function analyseAGarder(avant: Etat, id: number): Analysis | null {
  const affichee =
    avant.phase === 'analyse' ? avant.analyse : avant.phase === 'chargement' ? avant.precedente : null
  return affichee !== null && affichee.portfolio_id === id ? affichee : null
}

interface Props {
  readonly portefeuille: PortfolioDetail
  readonly annonce: string | null
}

export function VueAnalyse({ portefeuille, annonce }: Props) {
  const { langue, libelles } = useLangue()
  const l = libelles.analyse
  const vide = portefeuille.positions.length === 0
  const positionsStockees = JSON.stringify(portefeuille.positions)
  const [etat, setEtat] = useState<Etat>({ phase: 'chargement', precedente: null })
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    if (vide) return
    let vivant = true
    setEtat((avant) => ({ phase: 'chargement', precedente: analyseAGarder(avant, portefeuille.id) }))
    getAnalysis(portefeuille.id, langue).then(
      (analyse) => {
        if (vivant) setEtat({ phase: 'analyse', analyse })
      },
      (cause: unknown) => {
        if (!vivant) return
        const refus = versApiErreur(cause, langue)
        // 409 : le portefeuille existe, il a des positions, mais il n'est pas
        // analysable en l'état. C'est un ÉTAT de la base, pas une panne.
        setEtat(
          refus.statut === 409
            ? { phase: 'insuffisant', raison: refus }
            : { phase: 'erreur', erreur: refus },
        )
      },
    )
    return () => {
      vivant = false
    }
  }, [portefeuille.id, positionsStockees, vide, essai, langue])

  const nom = portefeuille.name
  const pages = pagesApplication('analyse', portefeuille.id, langue)
  const titre = l.titre(nom)
  const page = cheminDe({ vue: 'analyse', id: portefeuille.id })

  if (vide) {
    return (
      <Cadre
        titre={titre}
        page={page}
        annonce={annonce}
        entete={<BandeauSimple portefeuille={nom} />}
        rail={<RailPages pages={pages} />}
      >
        <AncresSections pages={pages} sections={false} />
        <div className={styles.vide}>
          <h1 tabIndex={-1} className={styles.titre}>
            {l.vide(nom)}
          </h1>
          <p className={styles.texte}>{l.decritDesPositions}</p>
          {!DEMO && (
            <>
              <Lien vers={cheminDe({ vue: 'positions', id: portefeuille.id })}>
                {l.saisirOuImporter}
              </Lien>
              <FormatCsv niveau={2} />
            </>
          )}
        </div>
      </Cadre>
    )
  }

  if (etat.phase === 'insuffisant') {
    return (
      <Cadre
        titre={titre}
        page={page}
        annonce={annonce}
        entete={<BandeauSimple portefeuille={nom} />}
        rail={<RailPages pages={pages} />}
      >
        <AncresSections pages={pages} sections={false} />
        <div className={styles.vide}>
          <h1 tabIndex={-1} className={styles.titre}>
            {l.insuffisant(nom)}
          </h1>
          <p className={styles.texte}>{l.ditPourquoi}</p>
          <MessageErreur erreur={etat.raison} alerte={false} />
          {!DEMO && (
            <p className={`${styles.texte} ${styles.suite}`}>
              <Lien vers={cheminDe({ vue: 'positions', id: portefeuille.id })}>
                {l.revoirLesPositions}
              </Lien>
            </p>
          )}
        </div>
        {portefeuille.valuation !== null && (
          <SectionPortefeuille valorisation={portefeuille.valuation} />
        )}
      </Cadre>
    )
  }

  // L'analyse à montrer : la nouvelle, ou, pendant qu'elle se relit, la
  // précédente du même portefeuille (`analyseAGarder`).
  const affichee =
    etat.phase === 'analyse' ? etat.analyse : etat.phase === 'chargement' ? etat.precedente : null

  if (affichee === null) {
    return (
      <Cadre
        titre={titre}
        page={page}
        annonce={annonce}
        occupe={etat.phase === 'chargement'}
        entete={<BandeauSimple portefeuille={nom} />}
        rail={<RailPages pages={pages} />}
      >
        <h1 tabIndex={-1} className="visuellement-cache">
          {titre}
        </h1>
        <AncresSections pages={pages} sections={false} />
        {etat.phase !== 'erreur' ? (
          <SqueletteAnalyse />
        ) : (
          <MessageErreur
            erreur={etat.erreur}
            action={
              <button
                type="button"
                className={controles.bouton}
                onClick={() => setEssai((n) => n + 1)}
              >
                {l.rechargerLAnalyse}
              </button>
            }
          />
        )}
      </Cadre>
    )
  }

  return pageDeLAnalyse({
    analyse: affichee,
    serie: affichee.series,
    portefeuille: affichee.portfolio,
    titre,
    page,
    pages,
    annonce,
    occupe: etat.phase === 'chargement',
  })
}

/**
 * La page d'une analyse lue, pour les deux vues. Une fonction qui rend la
 * page, et non un composant : la racine reste le même `Cadre` que celle des
 * autres états, et son titre le même nœud, qui garde le focus quand
 * l'analyse arrive (chantier 7E).
 */
function pageDeLAnalyse({
  analyse,
  serie,
  portefeuille,
  titre,
  page,
  pages,
  annonce,
  occupe,
}: {
  analyse: PublicAnalysis
  /** La série de la courbe ; `null` pour la réponse du serveur public, qui n'en a pas. */
  serie: PortfolioSeries | null
  portefeuille: { readonly name: string; readonly updated_at: string | null }
  titre: string
  page: string
  pages: readonly PageApplication[]
  annonce: string | null
  occupe: boolean
}): ReactNode {
  return (
    <Cadre
      titre={titre}
      page={page}
      annonce={annonce}
      occupe={occupe}
      entete={<Bandeau analyse={analyse} portefeuille={portefeuille} />}
      rail={<RailSections pages={pages} />}
    >
      <h1 tabIndex={-1} className="visuellement-cache">
        {titre}
      </h1>
      <AncresSections pages={pages} />
      <SectionPortefeuille valorisation={analyse.valuation} />
      <SectionJourOrdinaire
        risque={analyse.risk}
        histogramme={analyse.histogram}
        asOf={analyse.as_of}
        parametres={analyse.parameters}
        devise={analyse.valuation.currency}
        periode={analyse.estimation_period_label}
      />
      <SectionAuPire
        serie={serie}
        creux={analyse.risk.drawdown}
        asOf={analyse.as_of}
        devise={analyse.valuation.currency}
      />
      <SectionRisque
        variance={analyse.risk.variance_contributions}
        concentration={analyse.risk.concentration}
        matrices={analyse.risk.matrices}
        scenarios={analyse.scenarios}
        asOf={analyse.as_of}
      />
      <SectionCrise
        scenarios={analyse.scenarios}
        regimes={analyse.regimes}
        asOf={analyse.as_of}
        devise={analyse.valuation.currency}
      />
      <SectionMoteur
        observations={analyse.observations}
        bandeau={analyse.disclaimer}
        asOf={analyse.as_of}
      />
    </Cadre>
  )
}

// ═══════════════════════════════════════════ Le portefeuille saisi (9.6) ══

type EtatDuSaisi =
  /** La demande est en cours : rien d'observé encore, le réveil, ou le calcul. */
  | { phase: 'envoi'; etape: EtapeDuServeur | null }
  /** Le serveur refuse la composition gardée : ses phrases. */
  | { phase: 'refus'; erreur: ApiErreur }
  /** Une limite, un serveur occupé, aucune réponse : cela se réessaie. */
  | { phase: 'echec'; erreur: ApiErreur }
  | { phase: 'analyse'; analyse: PublicAnalysis }

interface PropsDuSaisi {
  /** Le portefeuille gardé dans ce navigateur, ou `null` s'il n'y en a pas. */
  readonly saisi: PortefeuilleSaisi | null
  /** La preuve que le texte d'acceptation de la langue a été accepté. */
  readonly preuve: PreuveDAcceptation
  readonly annonce: string | null
}

/** L'état d'arrivée : l'analyse déjà reçue pour cette composition et cette langue, sinon la demande. */
function etatDArrivee(saisi: PortefeuilleSaisi | null, langue: Langue): EtatDuSaisi {
  const deposee = saisi === null ? null : analyseDeposee(saisi.positions, langue)
  return deposee === null ? { phase: 'envoi', etape: null } : { phase: 'analyse', analyse: deposee }
}

/**
 * L'analyse du portefeuille saisi, dans le build de démonstration seulement :
 * ailleurs, la constante vaut `null`, et la vue sort du bundle avec ce
 * qu'elle envoie au serveur public.
 */
export const VueAnalyseDuSaisi = DEMO ? AnalyseDuSaisi : null

function AnalyseDuSaisi({ saisi, preuve, annonce }: PropsDuSaisi) {
  const { langue, libelles } = useLangue()
  const l = libelles.analyse
  const nom = libelles.saisi.nom
  const vide = saisi === null || saisi.positions.length === 0
  const composition = JSON.stringify(saisi?.positions ?? [])
  const [etat, setEtat] = useState<EtatDuSaisi>(() => etatDArrivee(saisi, langue))
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    if (saisi === null || saisi.positions.length === 0) return
    const deja = analyseDeposee(saisi.positions, langue)
    if (deja !== null) {
      setEtat({ phase: 'analyse', analyse: deja })
      return
    }
    const abandon = new AbortController()
    const vivant = () => !abandon.signal.aborted
    setEtat({ phase: 'envoi', etape: null })
    // Le numéro de ligne d'un envoi est le rang dans le portefeuille gardé :
    // un refus nommera la ligne que la page des positions montre.
    const positions = saisi.positions.map((position, rang) => ({ ...position, line: rang + 1 }))
    attendreLeServeur(
      langue,
      () => {
        if (vivant()) setEtat({ phase: 'envoi', etape: 'reveil' })
      },
      abandon.signal,
    )
      .then(() => {
        if (!vivant()) return null
        setEtat({ phase: 'envoi', etape: 'calcul' })
        return analyserLeSaisi(positions, langue, preuve)
      })
      .then(
        (analyse) => {
          if (analyse === null || !vivant()) return
          deposerLAnalyse(saisi.positions, langue, analyse)
          setEtat({ phase: 'analyse', analyse })
        },
        (cause: unknown) => {
          if (!vivant()) return
          const erreur = versApiErreur(cause, langue)
          setEtat(estUnRefus(erreur) ? { phase: 'refus', erreur } : { phase: 'echec', erreur })
        },
      )
    return () => abandon.abort()
    // `composition` porte le contenu de `saisi`, dont l'objet change à chaque lecture.
  }, [composition, langue, essai, preuve])

  const pages = pagesApplication('analyse', SAISI, langue)
  const titre = l.titre(nom)
  const page = cheminDe({ vue: 'saisi' })
  const positions = cheminDe({ vue: 'saisi-positions' })

  if (vide) {
    return (
      <Cadre
        titre={titre}
        page={page}
        annonce={annonce}
        entete={<BandeauSimple portefeuille={nom} />}
        rail={<RailPages pages={pages} />}
      >
        <AncresSections pages={pages} sections={false} />
        <div className={styles.vide}>
          <h1 tabIndex={-1} className={styles.titre}>
            {l.vide(nom)}
          </h1>
          <p className={styles.texte}>{l.decritDesPositions}</p>
          <Lien vers={positions}>{l.saisirOuImporter}</Lien>
          <FormatCsv niveau={2} />
        </div>
      </Cadre>
    )
  }

  if (etat.phase === 'analyse') {
    return pageDeLAnalyse({
      analyse: etat.analyse,
      serie: null,
      portefeuille: { name: nom, updated_at: saisi.modifie },
      titre,
      page,
      pages,
      annonce,
      occupe: false,
    })
  }

  const indisponible = etat.phase !== 'envoi'
  return (
    <Cadre
      titre={indisponible ? libelles.serveur.indisponible : titre}
      page={page}
      annonce={annonce}
      occupe={!indisponible}
      entete={<BandeauSimple portefeuille={nom} />}
      rail={<RailPages pages={pages} />}
    >
      <h1 tabIndex={-1} className={indisponible ? styles.titre : 'visuellement-cache'}>
        {indisponible ? libelles.serveur.indisponible : titre}
      </h1>
      <AncresSections pages={pages} sections={false} />
      {etat.phase === 'envoi' && (
        <>
          <EtatDuServeur etape={etat.etape} />
          <SqueletteAnalyse />
        </>
      )}
      {etat.phase === 'refus' && (
        <div className={styles.vide}>
          <MessageErreur erreur={etat.erreur} />
          <p className={`${styles.texte} ${styles.suite}`}>
            <Lien vers={positions}>{l.revoirLesPositions}</Lien>
          </p>
        </div>
      )}
      {etat.phase === 'echec' && (
        <MessageErreur
          erreur={etat.erreur}
          action={
            <button type="button" className={controles.bouton} onClick={() => setEssai((n) => n + 1)}>
              {libelles.serveur.reessayer}
            </button>
          }
        />
      )}
    </Cadre>
  )
}
