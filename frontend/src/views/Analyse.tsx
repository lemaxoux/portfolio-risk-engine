/**
 * La page d'analyse d'un portefeuille — DESIGN.md §8.2, §13.
 *
 * Le portefeuille arrive de la LISTE, déjà chargée par l'application : son
 * nom, et ses positions telles que stockées. Un portefeuille sans position
 * se reconnaît donc à sa structure, sans appel d'analyse et sans lire le
 * texte d'un 409.
 *
 * L'analyse est redemandée quand les positions changent (`updated_at`) : une
 * page qui montrerait l'analyse d'avant un enregistrement décrirait un
 * portefeuille qui n'existe plus.
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
  | { phase: 'analyse'; analyse: Analysis }

interface Props {
  readonly portefeuille: PortfolioDetail
  readonly annonce: string | null
}

export function VueAnalyse({ portefeuille, annonce }: Props) {
  const vide = portefeuille.positions.length === 0
  const [etat, setEtat] = useState<Etat>({ phase: 'chargement' })
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    memoriserPortefeuille(portefeuille.id)
  }, [portefeuille.id])

  useEffect(() => {
    if (vide) return
    let vivant = true
    setEtat({ phase: 'chargement' })
    getAnalysis(portefeuille.id).then(
      (analyse) => {
        if (vivant) setEtat({ phase: 'analyse', analyse })
      },
      (cause: unknown) => {
        if (vivant) setEtat({ phase: 'erreur', erreur: versApiErreur(cause) })
      },
    )
    return () => {
      vivant = false
    }
  }, [portefeuille.id, portefeuille.updated_at, vide, essai])

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
            L'analyse décrit des positions : ce portefeuille n'en a aucune.
          </p>
          <Lien vers={cheminDe({ vue: 'positions', id: portefeuille.id })}>
            Saisir ou importer les positions
          </Lien>
          <FormatCsv niveau={2} />
        </div>
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
      />
      <SectionAuPire serie={analyse.series} creux={analyse.risk.drawdown} asOf={analyse.as_of} />
      <SectionRisque
        variance={analyse.risk.variance_contributions}
        concentration={analyse.risk.concentration}
        matrices={analyse.risk.matrices}
        scenarios={analyse.scenarios}
        asOf={analyse.as_of}
      />
      <SectionCrise scenarios={analyse.scenarios} regimes={analyse.regimes} asOf={analyse.as_of} />
      <SectionMoteur
        observations={analyse.observations}
        bandeau={analyse.disclaimer}
        asOf={analyse.as_of}
      />
    </Cadre>
  )
}
