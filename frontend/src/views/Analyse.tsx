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
 */
import { useEffect, useState } from 'react'

import { ApiErreur, DEMO, getAnalysis, versApiErreur } from '../api/client'
import type { Analysis, PortfolioDetail } from '../api/types'
import { Bandeau, BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { FormatCsv } from '../components/FormatCsv'
import { Lien } from '../components/Lien'
import { MessageErreur } from '../components/MessageErreur'
import {
  AncresSections,
  pagesApplication,
  RailPages,
  RailSections,
} from '../components/Navigation'
import { SqueletteAnalyse } from '../components/Squelette'
import { useLangue } from '../lib/langue'
import { cheminDe, memoriserPortefeuille } from '../lib/route'
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
    memoriserPortefeuille(portefeuille.id)
  }, [portefeuille.id])

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

  const analyse = affichee
  return (
    <Cadre
      titre={titre}
      page={page}
      annonce={annonce}
      occupe={etat.phase === 'chargement'}
      entete={<Bandeau analyse={analyse} />}
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
        serie={analyse.series}
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
