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
 * ═══ LES QUATRE ÉTATS (§13) ═══
 *
 * Vide : aucune position, reconnu à la liste — invitation, lien vers la
 * saisie, format CSV. En cours : la forme de la page, sans animation.
 * Insuffisant : le moteur a les positions mais n'en tire pas d'analyse (409,
 * moins de trois séances communes, indice absent) — son message, et la
 * section 1 depuis la valorisation de la liste ; une fenêtre seulement
 * COURTE, elle, donne une analyse, où chaque mesure indisponible dit
 * pourquoi. Erreur : le message et l'action suivante.
 */
import { useEffect, useState } from 'react'

import { ApiErreur, getAnalysis, versApiErreur } from '../api/client'
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
import { cite } from '../lib/phrases'
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
  | { phase: 'chargement' }
  | { phase: 'erreur'; erreur: ApiErreur }
  | { phase: 'insuffisant'; raison: ApiErreur }
  | { phase: 'analyse'; analyse: Analysis }

interface Props {
  readonly portefeuille: PortfolioDetail
  readonly annonce: string | null
}

export function VueAnalyse({ portefeuille, annonce }: Props) {
  const { langue } = useLangue()
  const vide = portefeuille.positions.length === 0
  const positionsStockees = JSON.stringify(portefeuille.positions)
  const [etat, setEtat] = useState<Etat>({ phase: 'chargement' })
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    memoriserPortefeuille(portefeuille.id)
  }, [portefeuille.id])

  useEffect(() => {
    if (vide) return
    let vivant = true
    setEtat({ phase: 'chargement' })
    getAnalysis(portefeuille.id, langue).then(
      (analyse) => {
        if (vivant) setEtat({ phase: 'analyse', analyse })
      },
      (cause: unknown) => {
        if (!vivant) return
        const refus = versApiErreur(cause)
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
  const pages = pagesApplication('analyse', portefeuille.id)
  const titre = `Analyse de ${cite(nom)}`
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
            {cite(nom)} n'a encore aucune position
          </h1>
          <p className={styles.texte}>
            L'analyse décrit des positions&nbsp;: ce portefeuille n'en a aucune.
          </p>
          <Lien vers={cheminDe({ vue: 'positions', id: portefeuille.id })}>
            Saisir ou importer les positions
          </Lien>
          <FormatCsv niveau={2} />
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
            {cite(nom)} ne s'analyse pas en l'état
          </h1>
          <p className={styles.texte}>
            Ses positions sont en base, mais le moteur n'en tire pas d'analyse. Il dit
            pourquoi, et ce qu'il faut faire&nbsp;:
          </p>
          <MessageErreur erreur={etat.raison} alerte={false} />
          <p className={`${styles.texte} ${styles.suite}`}>
            <Lien vers={cheminDe({ vue: 'positions', id: portefeuille.id })}>
              Revoir les positions
            </Lien>
          </p>
        </div>
        {portefeuille.valuation !== null && (
          <SectionPortefeuille valorisation={portefeuille.valuation} />
        )}
      </Cadre>
    )
  }

  if (etat.phase !== 'analyse') {
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
        {etat.phase === 'chargement' ? (
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
                Recharger l'analyse
              </button>
            }
          />
        )}
      </Cadre>
    )
  }

  const analyse = etat.analyse
  return (
    <Cadre
      titre={titre}
      page={page}
      annonce={annonce}
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
