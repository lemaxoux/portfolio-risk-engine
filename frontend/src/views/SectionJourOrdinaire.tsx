/**
 * Section 2 — « Ce qu'il perd un jour ordinaire ». DESIGN.md §8.2, §9.1, §11.5.
 *
 * ═══ L'ORDRE EST L'ARGUMENT ═══
 *
 * 1. LA VaR HISTORIQUE d'abord, en chiffre principal. Elle ne suppose AUCUNE
 *    loi : c'est le quantile des rendements réellement observés sur la
 *    fenêtre. Mettre la paramétrique en tête ferait passer une hypothèse pour
 *    une mesure.
 *
 * 2. SOUS ELLE, LE COUPLE normale / Student (§11.5). Jamais l'une sans
 *    l'autre : l'écart entre les deux EST l'information, il chiffre le coût de
 *    l'hypothèse de normalité. Sur ce portefeuille, la normale est au-dessus
 *    de la Student à 95 % et en dessous à 99 % — la queue est plus épaisse que
 *    la loi normale ne l'admet, et cela ne se voit qu'au niveau extrême.
 *
 * 3. LE MONTE CARLO N'EST PAS UNE TROISIÈME OPINION. Le Monte Carlo normal
 *    tire dans la loi que la paramétrique intègre : il la reproduit par
 *    construction. En faire un bloc mesure afficherait deux chiffres presque
 *    égaux côte à côte, qui se liraient comme deux méthodes indépendantes qui
 *    concordent — une confirmation illusoire. Il vit donc dans la provenance,
 *    en tant que contrôle de calcul.
 *
 * 4. LA VOLATILITÉ ANNUALISÉE, puis les CVaR, qui disent ce qui se passe
 *    au-delà du quantile et combien de séances elles moyennent.
 *
 * ═══ LES TEXTES DE LECTURE ═══
 *
 * Chaque bloc dit sa mesure en calendrier, en dollars et en période, puis ce
 * qu'elle ne dit pas (`lib/phrases`). Les sous-titres posent la question en
 * mots simples ; le terme technique reste dans le libellé du bloc (§15). Un
 * texte du moteur — raison de refus, réserve — s'affiche tel quel.
 *
 * Sous 30 séances, la VaR normale et la volatilité portent la réserve du
 * moteur (`caveat`) : point `--caveat` et phrase sous la provenance, comme la
 * CVaR à 99 %. Le chiffre reste affiché — marqué, pas refusé.
 *
 * Sous 1/(1 − α) séances, la VaR historique et la CVaR du niveau sont, elles,
 * REFUSÉES par le moteur : le tiret d'absence à la place du chiffre, la raison
 * du moteur à la place de la phrase de lecture (§9.1, règle 3). Jamais le
 * minimum de la fenêtre présenté comme un quantile.
 *
 * ═══ CE QUE CE COMPOSANT NE FAIT PAS ═══
 *
 * Aucun calcul. Aucun écart n'est soustrait entre normale et Student : les
 * deux chiffres sont posés côte à côte et l'œil fait le reste. Si l'écart doit
 * être publié, il s'ajoutera au moteur avec son test.
 */
import { useCallback } from 'react'

import type { Parameters, ReturnHistogram, Risk, TailRiskLevel } from '../api/types'
import { Graphique, type ContexteGraphique } from '../components/charts/Graphique'
import { optionsHistogramme } from '../components/charts/histogramme'
import { Measure } from '../components/Measure'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { pourcentage, TIRET_INDEFINI } from '../lib/format'
import { PHRASES, useLangue, type Langue } from '../lib/langue'
import {
  provenanceDeCVaR,
  provenanceDeVar,
  provenanceDeVolatilite,
} from '../lib/provenance'
import styles from './SectionJourOrdinaire.module.css'

function niveauLu(confiance: number, langue: Langue): string {
  return pourcentage(confiance, 0, langue)
}

/**
 * Le couple normale / Student d'un niveau de confiance (§11.5).
 *
 * Quand le volet Student est indisponible, sa PHRASE prend la place du bloc :
 * la normale ne s'affiche jamais seule sans dire pourquoi elle l'est. Sans
 * cela, l'absence de contrepartie se lirait comme une absence de doute.
 */
function CoupleParametrique({
  niveau,
  raisonStudent,
  raisonMonteCarlo,
  devise,
}: {
  niveau: TailRiskLevel
  raisonStudent: string | null
  raisonMonteCarlo: string | null
  devise: string
}) {
  const { langue, libelles, phrases } = useLangue()
  const l = libelles.jourOrdinaire
  const confiance = niveauLu(niveau.confidence, langue)
  const student = niveau.student_parametric_var

  return (
    <div className={styles.couple}>
      <Measure
        niveau="secondaire"
        libelle={l.varNormale(confiance)}
        valeur={pourcentage(niveau.parametric_var.value, 2, langue)}
        lecture={phrases.lectureVarParametrique(niveau.parametric_var, 'normale', devise)}
        provenance={provenanceDeVar(
          niveau.parametric_var,
          niveau.monte_carlo_var,
          raisonMonteCarlo,
          langue,
        )}
        caveat={niveau.parametric_var.caveat}
      />

      {student !== null ? (
        <Measure
          niveau="secondaire"
          libelle={l.varStudent(confiance)}
          valeur={pourcentage(student.value, 2, langue)}
          lecture={phrases.lectureVarParametrique(student, 'de Student', devise)}
          provenance={provenanceDeVar(student, niveau.student_monte_carlo_var, null, langue)}
        />
      ) : (
        <p className={styles.absenceStudent}>
          <span className={styles.point} aria-hidden="true" />
          {raisonStudent ?? l.studentSansRaison}
        </p>
      )}
    </div>
  )
}

/**
 * La phrase que lit un lecteur d'écran à la place de l'histogramme (§13) : la
 * conclusion, pas la forme. Elle est rédigée dans `lib/phrases.*`.
 */
export function descriptionHistogramme(
  histogramme: ReturnHistogram,
  niveaux: readonly TailRiskLevel[],
  langue: Langue = 'fr',
): string {
  return PHRASES[langue].descriptionHistogramme(histogramme, niveaux)
}

interface Props {
  readonly risque: Risk
  readonly histogramme: ReturnHistogram
  readonly asOf: string
  /** L'indice de référence demandé, et son nom lisible publié par le moteur. */
  readonly parametres: Parameters
  /** Le code ISO de la devise publiée (`valuation.currency`). */
  readonly devise: string
  /** La période de la fenêtre d'estimation, dite pour un lecteur. */
  readonly periode: string
}

export function SectionJourOrdinaire({
  risque,
  histogramme,
  asOf,
  parametres,
  devise,
  periode,
}: Props) {
  const { langue, libelles, phrases } = useLangue()
  const l = libelles.jourOrdinaire
  const niveaux = risque.tail_risk.levels
  const raisonStudent = risque.tail_risk.student_unavailable_reason
  const raisonMonteCarlo = risque.tail_risk.monte_carlo_unavailable_reason
  const options = useCallback(
    (contexte: ContexteGraphique) => optionsHistogramme({ histogramme, niveaux }, contexte),
    [histogramme, niveaux],
  )
  const introduction = phrases.introJourOrdinaire(periode)

  return (
    <Section ancre="jour-ordinaire" numero={2} titre={libelles.sections[1]} introduction={introduction}>
      <h3 className={commun.sousTitre}>{l.observes}</h3>
      <p className={commun.chapeau}>{l.chapeauObserves}</p>
      <div className={commun.rangee}>
        {niveaux.map((niveau) => {
          const valeur = niveau.historical_var.value
          return (
            <Measure
              key={niveau.confidence}
              libelle={l.varHistorique(niveauLu(niveau.confidence, langue))}
              valeur={valeur === null ? TIRET_INDEFINI : pourcentage(valeur, 2, langue)}
              lecture={phrases.lectureVarHistorique(niveau.historical_var, 2, devise)}
              neDitPas={phrases.neDitPasVarHistorique(
                niveau.historical_var,
                risque.worst_day,
                niveau.expected_shortfall.tail_observations,
              )}
              provenance={provenanceDeVar(niveau.historical_var, null, null, langue)}
            />
          )
        })}
      </div>

      <div className={styles.histogramme}>
        <Graphique
          titre={l.titreHistogramme}
          unite={l.uniteHistogramme(histogramme.bin_width)}
          fenetre={histogramme.window}
          asOf={asOf}
          description={descriptionHistogramme(histogramme, niveaux, langue)}
          options={options}
        >
          <p className={styles.legende}>
            {phrases.legendeHistogramme(
              niveaux
                .filter((niveau) => niveau.expected_shortfall.threshold !== null)
                .map((niveau) => niveau.confidence),
              niveaux
                .filter((niveau) => niveau.expected_shortfall.threshold === null)
                .map((niveau) => niveau.confidence),
              histogramme.bin_width,
            )}
          </p>
        </Graphique>
      </div>

      <h3 className={commun.sousTitre}>{l.courbe}</h3>
      <p className={commun.chapeau}>{l.chapeauCourbe}</p>
      {niveaux.map((niveau) => (
        <CoupleParametrique
          key={niveau.confidence}
          niveau={niveau}
          raisonStudent={raisonStudent}
          raisonMonteCarlo={raisonMonteCarlo}
          devise={devise}
        />
      ))}
      <p className={commun.neDitPas}>{phrases.NE_DIT_PAS_COURBES}</p>

      <h3 className={commun.sousTitre}>{l.ampleur}</h3>
      <div className={commun.rangee}>
        <Measure
          libelle={l.volatilite}
          valeur={pourcentage(risque.volatility.annualised, 1, langue)}
          lecture={phrases.lectureVolatilite(risque.benchmark_volatility, parametres)}
          neDitPas={phrases.NE_DIT_PAS_VOLATILITE}
          provenance={provenanceDeVolatilite(risque.volatility, langue)}
          caveat={risque.volatility.caveat}
        />
      </div>

      <h3 className={commun.sousTitre}>{l.piresJours}</h3>
      <p className={commun.chapeau}>{l.chapeauPiresJours}</p>
      <div className={commun.rangee}>
        {niveaux.map((niveau) => {
          const cvar = niveau.expected_shortfall
          return (
            <Measure
              key={niveau.confidence}
              libelle={l.cvar(niveauLu(niveau.confidence, langue))}
              valeur={cvar.value === null ? TIRET_INDEFINI : pourcentage(cvar.value, 2, langue)}
              lecture={phrases.lectureCVaR(cvar, devise)}
              neDitPas={phrases.neDitPasCVaR(cvar)}
              provenance={provenanceDeCVaR(cvar, langue)}
              caveat={cvar.caveat}
            />
          )
        })}
      </div>
    </Section>
  )
}
