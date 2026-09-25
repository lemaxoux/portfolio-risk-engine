/**
 * Coquille de l'application et enchaînement des états — DESIGN.md §13.
 *
 * Les quatre états sont dessinés, pas seulement l'état nominal : EN COURS
 * (squelettes de la forme finale, jamais un rond qui tourne), VIDE (aucun
 * portefeuille, et ce qu'on peut faire), ERREUR (ce qui a échoué et l'action
 * suivante, dans la voix du moteur) et NOMINAL.
 *
 * ═══ L'ACCEPTATION PRÉCÈDE TOUT ═══
 *
 * Le bandeau d'acceptation est demandé AVANT la liste des portefeuilles et
 * avant l'analyse. Ce n'est pas un détail d'ordonnancement : une page qui
 * afficherait des chiffres puis demanderait l'acceptation par-dessus aurait
 * déjà montré ce que l'acceptation encadre.
 *
 * ═══ N'AFFICHER QUE CE QUI EST CONSTRUIT ═══
 *
 * Le rail de navigation ne liste que les sections qui existent. Pas de section
 * vide, pas de « bientôt », pas de texte provisoire : une entrée grisée
 * promettrait un contenu, et une page de démonstration qui promet vaut moins
 * qu'une page courte qui tient.
 */
import { useCallback, useEffect, useState } from 'react'

import { ApiErreur, getAnalysis, getDisclaimer, getPortfolios } from './api/client'
import type { Analysis, Disclaimer } from './api/types'
import { Bandeau } from './components/Bandeau'
import { MessageErreur } from './components/MessageErreur'
import { AncresSections, RailSections } from './components/Navigation'
import { aAccepte } from './lib/acceptation'
import { Acceptation } from './views/Acceptation'
import { SectionAuPire } from './views/SectionAuPire'
import { SectionCrise } from './views/SectionCrise'
import { SectionJourOrdinaire } from './views/SectionJourOrdinaire'
import { SectionMoteur } from './views/SectionMoteur'
import { SectionPortefeuille } from './views/SectionPortefeuille'
import { SectionRisque } from './views/SectionRisque'
import styles from './App.module.css'

type Etat =
  | { phase: 'chargement' }
  | { phase: 'erreur'; erreur: ApiErreur }
  | { phase: 'acceptation'; bandeau: Disclaimer }
  | { phase: 'vide' }
  | { phase: 'analyse'; analyse: Analysis }


function enErreur(cause: unknown): Etat {
  return {
    phase: 'erreur',
    erreur:
      cause instanceof ApiErreur
        ? cause
        : new ApiErreur(0, `Erreur inattendue du client : ${String(cause)}`),
  }
}

export function App() {
  const [etat, setEtat] = useState<Etat>({ phase: 'chargement' })

  const chargerAnalyse = useCallback(async () => {
    setEtat({ phase: 'chargement' })
    try {
      const portefeuilles = await getPortfolios()
      const premier = portefeuilles[0]
      if (premier === undefined) {
        setEtat({ phase: 'vide' })
        return
      }
      setEtat({ phase: 'analyse', analyse: await getAnalysis(premier.id) })
    } catch (cause) {
      setEtat(enErreur(cause))
    }
  }, [])

  useEffect(() => {
    let vivant = true
    void (async () => {
      try {
        const bandeau = await getDisclaimer()
        if (!vivant) return
        if (aAccepte(bandeau.text)) await chargerAnalyse()
        else setEtat({ phase: 'acceptation', bandeau })
      } catch (cause) {
        if (vivant) setEtat(enErreur(cause))
      }
    })()
    return () => {
      vivant = false
    }
  }, [chargerAnalyse])

  if (etat.phase === 'acceptation') {
    return (
      <Acceptation bandeau={etat.bandeau} onAccepte={() => void chargerAnalyse()} />
    )
  }

  return (
    <>
      <a className={styles.evitement} href="#contenu">
        Aller au contenu
      </a>

      {etat.phase === 'analyse' && <Bandeau analyse={etat.analyse} />}

      <div className={styles.page}>
        {etat.phase === 'analyse' && <RailSections />}

        <main id="contenu" className={styles.contenu}>
          {etat.phase === 'chargement' && <Squelette />}
          {etat.phase === 'erreur' && <MessageErreur erreur={etat.erreur} />}
          {etat.phase === 'vide' && <AucunPortefeuille />}
          {etat.phase === 'analyse' && (
            <>
              <AncresSections />
              <SectionPortefeuille valorisation={etat.analyse.valuation} />
              <SectionJourOrdinaire
                risque={etat.analyse.risk}
                histogramme={etat.analyse.histogram}
                asOf={etat.analyse.as_of}
              />
              <SectionAuPire
                serie={etat.analyse.series}
                creux={etat.analyse.risk.drawdown}
                asOf={etat.analyse.as_of}
              />
              <SectionRisque
                variance={etat.analyse.risk.variance_contributions}
                concentration={etat.analyse.risk.concentration}
                matrices={etat.analyse.risk.matrices}
                scenarios={etat.analyse.scenarios}
                asOf={etat.analyse.as_of}
              />
              <SectionCrise
                scenarios={etat.analyse.scenarios}
                regimes={etat.analyse.regimes}
                asOf={etat.analyse.as_of}
              />
              <SectionMoteur
                observations={etat.analyse.observations}
                bandeau={etat.analyse.disclaimer}
                asOf={etat.analyse.as_of}
              />
            </>
          )}
        </main>
      </div>
    </>
  )
}

/**
 * État EN COURS — la forme de ce qui arrive, pas un rond qui tourne (§13).
 *
 * Sans animation : §10 interdit tout mouvement au chargement, et une pulsation
 * sur des blocs vides est le marqueur d'interface générée le plus reconnaissable.
 */
function Squelette() {
  return (
    <div className={styles.squelette} aria-hidden="true">
      <span className={styles.squeletteTitre} />
      <div className={styles.squeletteRangee}>
        <span className={styles.squeletteBloc} />
        <span className={styles.squeletteBloc} />
      </div>
    </div>
  )
}

/**
 * État VIDE — aucun portefeuille en base.
 *
 * La saisie et l'import arrivent plus tard ; en attendant, cet écran dit ce
 * qui est possible AUJOURD'HUI plutôt que d'annoncer un écran qui n'existe
 * pas. Le format CSV n'est pas décrit ici : il le sera par l'écran qui le lit,
 * et le recopier créerait une deuxième description à tenir à jour.
 */
function AucunPortefeuille() {
  return (
    <div className={styles.vide}>
      <h1 className={styles.videTitre}>Aucun portefeuille en base</h1>
      <p className={styles.videTexte}>
        L'analyse décrit un portefeuille : il en faut un. Les positions
        s'écrivent par l'API, qui vérifie chaque ticker contre l'univers chargé
        et refuse ligne à ligne ce qu'elle ne reconnaît pas.
      </p>
      <code className={styles.videCommande}>POST /api/portfolios</code>
      <code className={styles.videCommande}>
        PUT /api/portfolios/&lt;id&gt;/positions
      </code>
    </div>
  )
}
