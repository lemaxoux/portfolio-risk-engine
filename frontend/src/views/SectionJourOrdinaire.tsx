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
 * ═══ CE QUE CE COMPOSANT NE FAIT PAS ═══
 *
 * Aucun calcul. Aucun écart n'est soustrait entre normale et Student : les
 * deux chiffres sont posés côte à côte et l'œil fait le reste. Si l'écart doit
 * être publié, il s'ajoutera au moteur avec son test.
 */
import type { Risk, TailRiskLevel } from '../api/types'
import { Measure } from '../components/Measure'
import { pourcentage } from '../lib/format'
import { lectureDeCVaR, lectureDeVar } from '../lib/phrases'
import {
  provenanceDeCVaR,
  provenanceDeVar,
  provenanceDeVolatilite,
} from '../lib/provenance'
import styles from './SectionJourOrdinaire.module.css'

function niveauLu(confiance: number): string {
  return pourcentage(confiance, 0)
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
}: {
  niveau: TailRiskLevel
  raisonStudent: string | null
}) {
  const confiance = niveauLu(niveau.confidence)
  const student = niveau.student_parametric_var

  return (
    <div className={styles.couple}>
      <Measure
        niveau="secondaire"
        libelle={`VaR ${confiance} paramétrique, loi normale`}
        valeur={pourcentage(niveau.parametric_var.value, 2)}
        lecture={lectureDeVar(niveau.parametric_var.value, niveau.confidence, 2)}
        provenance={provenanceDeVar(
          niveau.parametric_var,
          niveau.monte_carlo_var,
        )}
      />

      {student !== null ? (
        <Measure
          niveau="secondaire"
          libelle={`VaR ${confiance} paramétrique, loi de Student`}
          valeur={pourcentage(student.value, 2)}
          lecture={lectureDeVar(student.value, niveau.confidence, 2)}
          provenance={provenanceDeVar(student, niveau.student_monte_carlo_var)}
        />
      ) : (
        <p className={styles.absenceStudent}>
          <span className={styles.point} aria-hidden="true" />
          {raisonStudent ??
            "Le volet Student n'a pas pu être ajusté, sans raison publiée."}
        </p>
      )}
    </div>
  )
}

export function SectionJourOrdinaire({ risque }: { risque: Risk }) {
  const niveaux = risque.tail_risk.levels
  const raisonStudent = risque.tail_risk.student_unavailable_reason

  return (
    <section className={styles.section} id="jour-ordinaire">
      <h2 className={styles.titre}>
        <span className={styles.numero}>2.</span> Ce qu'il perd un jour
        ordinaire
      </h2>

      <h3 className={styles.sousTitre}>Sans hypothèse de loi</h3>
      <p className={styles.chapeau}>
        Le quantile des rendements réellement observés sur la fenêtre. Aucune
        loi n'est supposée : ce sont les séances qui ont eu lieu.
      </p>
      <div className={styles.rangee}>
        {niveaux.map((niveau) => (
          <Measure
            key={niveau.confidence}
            libelle={`VaR ${niveauLu(niveau.confidence)} historique, horizon 1 séance`}
            valeur={pourcentage(niveau.historical_var.value, 2)}
            lecture={lectureDeVar(
              niveau.historical_var.value,
              niveau.confidence,
              2,
            )}
            provenance={provenanceDeVar(niveau.historical_var)}
          />
        ))}
      </div>

      <h3 className={styles.sousTitre}>Ce que coûte l'hypothèse de normalité</h3>
      <p className={styles.chapeau}>
        Les deux mêmes niveaux, sous deux lois. L'écart entre la normale et la
        loi de Student est l'information : il mesure ce que la normalité fait
        perdre de vue dans la queue.
      </p>
      {niveaux.map((niveau) => (
        <CoupleParametrique
          key={niveau.confidence}
          niveau={niveau}
          raisonStudent={raisonStudent}
        />
      ))}

      <h3 className={styles.sousTitre}>Amplitude ordinaire</h3>
      <div className={styles.rangee}>
        <Measure
          libelle="Volatilité annualisée"
          valeur={pourcentage(risque.volatility.annualised, 1)}
          lecture="écart-type des rendements quotidiens, ramené à l'année"
          provenance={provenanceDeVolatilite(risque.volatility)}
        />
      </div>

      <h3 className={styles.sousTitre}>Au-delà du quantile</h3>
      <p className={styles.chapeau}>
        La VaR dit à partir de quel niveau la perte est rare. La CVaR dit
        combien on perd, en moyenne, les jours où ce niveau est dépassé.
      </p>
      <div className={styles.rangee}>
        {niveaux.map((niveau) => (
          <Measure
            key={niveau.confidence}
            libelle={`CVaR ${niveauLu(niveau.confidence)}, horizon 1 séance`}
            valeur={pourcentage(niveau.expected_shortfall.value, 2)}
            lecture={lectureDeCVaR(niveau.confidence)}
            provenance={provenanceDeCVaR(niveau.expected_shortfall)}
            caveat={niveau.expected_shortfall.caveat}
          />
        ))}
      </div>
    </section>
  )
}
