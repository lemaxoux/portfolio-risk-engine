/**
 * Section 4 — « Qui porte le risque ». DESIGN.md §5.4, §8.2, §11.4.
 *
 * ═══ UNE CONTRIBUTION À LA VARIANCE EST UNE AMPLITUDE, PAS UN VERDICT ═══
 *
 * Elle dit de combien une ligne fait bouger le portefeuille, JAMAIS dans quel
 * sens (§11.4). La même variance qui fait peser XOM dans le risque a produit
 * un gain pendant le resserrement de 2022, pendant que le portefeuille
 * perdait. La montrer seule, comme un danger, est une erreur de lecture que
 * l'interface doit empêcher : le tableau qui accompagne le graphique pose, dans
 * le MÊME bloc, ce que chaque ligne a réellement apporté dans chaque crise
 * rejouée — le seul endroit hors de la section 5 où le signe varie d'une ligne
 * à l'autre, donc le seul où `--loss` et `--gain` marquent un chiffre (§5.3).
 *
 * ═══ CE QUE CETTE SECTION NE CALCULE PAS ═══
 *
 * L'écart en points est `excess_over_weight`, publié. Les lignes effectives
 * sont publiées, en capital comme en risque. La contribution d'une ligne à un
 * scénario est `scenarios[].contributions[].contribution`. Rien n'est soustrait
 * ni moyenné ici.
 */
import { useCallback } from 'react'

import type {
  Concentration,
  Contribution,
  Matrices,
  Scenario,
  VarianceContributions,
} from '../api/types'
import { DataTable, type Colonne } from '../components/DataTable'
import { Graphique, type ContexteGraphique } from '../components/charts/Graphique'
import {
  lignesParContribution,
  optionsContributions,
} from '../components/charts/contributions'
import { DOMAINE_CORRELATION, optionsCarteCorrelation } from '../components/charts/correlation'
import { Measure } from '../components/Measure'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import {
  TIRET_INDEFINI,
  dateISO,
  decimal,
  decimalOuTiret,
  lignes as compteLignes,
  pointsSignes,
  pourcentage,
} from '../lib/format'
import { PHRASE_CONTRIBUTION_NEGATIVE } from '../lib/phrases'
import { lignesDeFenetre } from '../lib/provenance'
import styles from './SectionRisque.module.css'

/** La légende exacte de §5.4. */
export const LEGENDE_CONTRIBUTIONS = 'barre : part de la variance — trait : part du capital'

/** Une contribution de scénario : le chiffre signé, et sa marque de signe. */
function ApportEnCrise({ scenario, ticker }: { scenario: Scenario; ticker: string }) {
  if (scenario.end_to_end_return === null) {
    return <span className={styles.absent}>{TIRET_INDEFINI}</span>
  }
  const apport = scenario.contributions.find((ligne) => ligne.ticker === ticker)
  if (apport === undefined) {
    return <span className={styles.absent}>{TIRET_INDEFINI} non couverte</span>
  }
  const sens = apport.contribution < 0 ? styles.perte : apport.contribution > 0 ? styles.gain : ''
  return (
    <span className={styles.apport}>
      {pointsSignes(apport.contribution, 1)}
      <span className={`${styles.marque} ${sens}`} aria-hidden="true" />
    </span>
  )
}

export function colonnesDuRisque(scenarios: readonly Scenario[]): Colonne<Contribution>[] {
  return [
    { cle: 'ticker', titre: 'Ticker', nature: 'texte', cellule: (l) => l.ticker },
    {
      cle: 'variance',
      titre: 'Part de la variance',
      nature: 'nombre',
      cellule: (l) => pourcentage(l.contribution, 1),
    },
    {
      cle: 'capital',
      titre: 'Part du capital',
      nature: 'nombre',
      cellule: (l) => pourcentage(l.weight, 1),
    },
    {
      cle: 'ecart',
      titre: 'Écart',
      nature: 'nombre',
      cellule: (l) => pointsSignes(l.excess_over_weight, 1),
    },
    ...scenarios.map(
      (scenario): Colonne<Contribution> => ({
        cle: scenario.scenario.key,
        titre: scenario.scenario.name,
        nature: 'nombre',
        cellule: (l) => <ApportEnCrise scenario={scenario} ticker={l.ticker} />,
      }),
    ),
  ]
}

/** Les cinq points de l'échelle, en légende : des pastilles, pas un dégradé (§12). */
function LegendeCorrelation() {
  const classes = [
    styles.divNegFort,
    styles.divNegMoyen,
    styles.divZero,
    styles.divPosMoyen,
    styles.divPosFort,
  ]
  return (
    <p className={styles.legendeCorrelation}>
      {DOMAINE_CORRELATION.map((valeur, rang) => (
        <span key={valeur} className={styles.pas}>
          <span className={`${styles.pastille} ${classes[rang] ?? ''}`} aria-hidden="true" />
          {decimal(valeur, 1)}
        </span>
      ))}
      <span className={styles.lectureEchelle}>
        échelle fixe : de −1, lignes qui bougent en sens inverse, à +1, lignes
        qui bougent ensemble
      </span>
    </p>
  )
}

interface Props {
  readonly variance: VarianceContributions
  readonly concentration: Concentration
  readonly matrices: Matrices
  readonly scenarios: readonly Scenario[]
  readonly asOf: string
}

export function SectionRisque({ variance, concentration, matrices, scenarios, asOf }: Props) {
  const contributions = variance.contributions
  const correlation = matrices.correlation

  const optionsBarres = useCallback(
    (contexte: ContexteGraphique) => optionsContributions(contributions ?? [], contexte),
    [contributions],
  )
  const optionsCarte = useCallback(
    (contexte: ContexteGraphique) =>
      optionsCarteCorrelation(correlation ?? { tickers: [], values: [] }, contexte),
    [correlation],
  )

  return (
    <Section ancre="qui-porte" numero={4} titre="Qui porte le risque">
      <h3 className={commun.sousTitre}>Combien de lignes, en réalité</h3>
      <p className={commun.chapeau}>
        Des poids inégaux font compter un portefeuille pour moins de lignes
        qu'il n'en détient. La lecture en risque pondère chaque ligne par ce
        qu'elle fait bouger, pas par ce qu'elle vaut.
      </p>
      <div className={commun.rangee}>
        <Measure
          libelle="Lignes effectives en capital"
          valeur={decimal(concentration.effective_positions, 1)}
          lecture={`sur ${compteLignes(concentration.n_positions)} détenues : inverse de la somme des carrés des poids`}
          provenance={[
            { libelle: 'Lignes', valeur: compteLignes(concentration.n_positions) },
            { libelle: 'Valorisé au', valeur: dateISO(concentration.as_of) },
          ]}
        />
        <Measure
          libelle="Lignes effectives en risque"
          valeur={decimalOuTiret(variance.effective_positions, 1)}
          lecture={
            variance.effective_positions === null
              ? (variance.undefined_reason ?? 'non estimable, sans raison publiée')
              : 'inverse de la somme des carrés des parts de variance'
          }
          provenance={lignesDeFenetre(variance.window)}
        />
      </div>

      <h3 className={commun.sousTitre}>Part de la variance, part du capital</h3>
      {contributions === null ? (
        <p className={styles.refus}>
          <span className={styles.point} aria-hidden="true" />
          {variance.undefined_reason ?? 'Contributions non estimables, sans raison publiée.'}
        </p>
      ) : (
        <>
          <p className={commun.chapeau}>
            Une ligne qui pèse plus dans le risque que dans le capital fait
            bouger le portefeuille plus que son poids ne le laisse croire. Ce
            n'est pas un sens : le tableau dit ce que chacune a apporté,
            réellement, dans les crises rejouées.
          </p>
          <Graphique
            titre="Part de chaque ligne dans la variance et dans le capital"
            unite="% de la variance du portefeuille, % de sa valeur ; écart en points"
            fenetre={variance.window}
            asOf={asOf}
            description={
              `Parts de variance comparées aux parts de capital, ${compteLignes(contributions.length)} : ` +
              lignesParContribution(contributions)
                .map((l) => `${l.ticker} ${pointsSignes(l.excess_over_weight, 1)}`)
                .join(', ')
            }
            options={optionsBarres}
          >
            <p className={styles.legende}>
              <span className={styles.cleBarre} aria-hidden="true" />
              {LEGENDE_CONTRIBUTIONS.split(' — ')[0]}
              {' — '}
              <span className={styles.cleTrait} aria-hidden="true" />
              {LEGENDE_CONTRIBUTIONS.split(' — ')[1]}
            </p>
          </Graphique>
          {variance.has_negative_contribution === true && (
            <p className={styles.negative}>{PHRASE_CONTRIBUTION_NEGATIVE}</p>
          )}
          <div className={styles.tableau}>
            <DataTable
              legende="Part du risque, et ce que chaque ligne a apporté au résultat du portefeuille dans chaque crise rejouée (en points)"
              colonnes={colonnesDuRisque(scenarios)}
              lignes={lignesParContribution(contributions)}
              cleDeLigne={(l) => l.ticker}
            />
          </div>
        </>
      )}

      <h3 className={commun.sousTitre}>Ce qui bouge ensemble</h3>
      {correlation === null ? (
        <p className={styles.refus}>
          <span className={styles.point} aria-hidden="true" />
          {matrices.correlation_undefined_reason ??
            'Corrélation non estimable, sans raison publiée.'}
        </p>
      ) : (
        <Graphique
          titre="Corrélation des rendements quotidiens"
          unite="coefficient de corrélation, sans unité"
          fenetre={matrices.window}
          asOf={asOf}
          description={`Corrélations deux à deux de ${compteLignes(correlation.tickers.length)}, valeur écrite dans chaque cellule.`}
          options={optionsCarte}
        >
          <LegendeCorrelation />
        </Graphique>
      )}
    </Section>
  )
}
