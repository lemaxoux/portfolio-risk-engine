/**
 * Section 5 — « Ce qui se passe en crise ». DESIGN.md §8.2, §11.2, §11.6.
 *
 * ═══ TROIS CHIFFRES, PAS UN, À LA MÊME TAILLE (§11.2) ═══
 *
 * Un scénario rend ce que vaudrait le portefeuille à la SORTIE de l'épisode,
 * le pire moment TRAVERSÉ en chemin — souvent plus profond —, et la PORTÉE du
 * chiffre : la part de la valeur que le rejeu couvre. Les trois partagent la
 * MÊME classe, donc la même taille : la perte n'a jamais le droit d'être plus
 * grosse que sa couverture. Un scénario réduit à un seul chiffre laisserait
 * croire que le creux s'est arrêté là où l'épisode s'est terminé.
 *
 * La couverture porte le point `--caveat` DÈS qu'elle est incomplète, et pas
 * seulement sous le seuil de 80 % : le seuil déclenche l'observation du moteur
 * de règles (section 6), l'affichage signale le fait.
 *
 * ═══ RÉGIMES : APPARIÉS, JAMAIS MOYENNÉS (§11.6) ═══
 *
 * Beta et R² de régime calme et de crise côte à côte, dans le bloc du
 * scénario. Un beta de 0,57 en calme et de 1,07 en crise n'a pas de moyenne
 * qui veuille dire quelque chose ; aucune n'est écrite.
 */
import type { ReactNode } from 'react'

import type { Regime, Scenario } from '../api/types'
import { DataTable, type Colonne } from '../components/DataTable'
import { Provenance } from '../components/Provenance'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import {
  TIRET_INDEFINI,
  dateISO,
  decimal,
  lignes,
  pointsSignes,
  pourcentage,
  pourcentageSigne,
  seances,
} from '../lib/format'
import { phraseCouverturePartielle, phraseEchantillonMince } from '../lib/phrases'
import styles from './SectionCrise.module.css'

/**
 * Un des trois chiffres d'un scénario. La classe `chiffre` est la même pour
 * les trois : c'est elle qui garantit la même taille, et le test le vérifie.
 */
function Chiffre({
  libelle,
  valeur,
  children,
}: {
  libelle: string
  valeur: string
  children?: ReactNode
}) {
  return (
    <div className={styles.cellule}>
      <dt className={styles.libelle}>{libelle}</dt>
      <dd className={styles.chiffre}>{valeur}</dd>
      {children}
    </div>
  )
}

interface LigneRegime {
  readonly mesure: string
  readonly calme: string
  readonly crise: string
}

const COLONNES_REGIME: Colonne<LigneRegime>[] = [
  { cle: 'mesure', titre: 'Mesure', nature: 'texte', cellule: (l) => l.mesure },
  { cle: 'calme', titre: 'Régime calme', nature: 'nombre', cellule: (l) => l.calme },
  { cle: 'crise', titre: 'Crise', nature: 'nombre', cellule: (l) => l.crise },
]

function avecErreur(valeur: number, erreur: number | null): string {
  return erreur === null ? decimal(valeur, 2) : `${decimal(valeur, 2)} ± ${decimal(erreur, 2)}`
}

function BlocRegime({ regime }: { regime: Regime }) {
  const { calm_beta: calme, crisis_beta: crise } = regime
  if (regime.unavailable_reason !== null || calme === null || crise === null) {
    return (
      <p className={styles.reserve}>
        <span className={styles.point} aria-hidden="true" />
        {regime.unavailable_reason ?? 'Comparaison de régimes indisponible, sans raison publiée.'}
      </p>
    )
  }

  const lignesRegime: LigneRegime[] = [
    {
      mesure: 'Beta',
      calme: avecErreur(calme.beta, calme.standard_error),
      crise: avecErreur(crise.beta, crise.standard_error),
    },
    { mesure: 'R²', calme: decimal(calme.r_squared, 2), crise: decimal(crise.r_squared, 2) },
    { mesure: 'Séances', calme: seances(calme.observations), crise: seances(crise.observations) },
    {
      mesure: 'Période',
      calme: `${dateISO(calme.start)} → ${dateISO(calme.end)}`,
      crise: `${dateISO(crise.start)} → ${dateISO(crise.end)}`,
    },
  ]

  return (
    <div className={styles.regime}>
      <DataTable
        legende={`Sensibilité à ${regime.benchmark}, en régime calme et en crise — jamais moyennées`}
        colonnes={COLONNES_REGIME}
        lignes={lignesRegime}
        cleDeLigne={(l) => l.mesure}
      />
      {crise.sample_too_thin && (
        <p className={styles.reserve}>
          <span className={styles.point} aria-hidden="true" />
          {phraseEchantillonMince(crise.observations, crise.min_observations)}
        </p>
      )}
      {regime.predicted_return !== null &&
        regime.portfolio_return !== null &&
        regime.benchmark_return !== null &&
        regime.prediction_gap !== null && (
          <p className={styles.prediction}>
            Face au mouvement de {regime.benchmark} ({pourcentageSigne(regime.benchmark_return, 1)}),
            le beta de régime calme annonçait {pourcentageSigne(regime.predicted_return, 1)} ; le
            portefeuille a fait {pourcentageSigne(regime.portfolio_return, 1)}, soit un écart de{' '}
            {pointsSignes(regime.prediction_gap, 1)}.
          </p>
        )}
    </div>
  )
}

export function BlocScenario({
  scenario,
  regime,
  asOf,
}: {
  scenario: Scenario
  regime: Regime | undefined
  asOf: string
}) {
  const definition = scenario.scenario
  const couverture = scenario.coverage
  const partielle = !couverture.is_complete

  return (
    <article className={styles.bloc} aria-labelledby={`scenario-${definition.key}`}>
      <h3 id={`scenario-${definition.key}`} className={styles.titre}>
        {definition.name}
        <span className={styles.periode}>
          {dateISO(definition.start)} → {dateISO(definition.end)}
        </span>
      </h3>
      <p className={styles.description}>{definition.description}</p>

      <dl className={styles.triade}>
        <Chiffre
          libelle="À la sortie"
          valeur={
            scenario.end_to_end_return === null
              ? TIRET_INDEFINI
              : pourcentageSigne(scenario.end_to_end_return, 1)
          }
        />
        <Chiffre
          libelle="Pire moment traversé"
          valeur={
            scenario.max_drawdown === null
              ? TIRET_INDEFINI
              : pourcentageSigne(scenario.max_drawdown.value, 1)
          }
        />
        <Chiffre libelle="Couverture" valeur={pourcentage(couverture.value_share, 0)}>
          <dd className={styles.sousChiffre}>
            {partielle && <span className={styles.point} aria-hidden="true" />}
            {lignes(couverture.covered_count)} sur {couverture.total_count}
          </dd>
        </Chiffre>
      </dl>

      {scenario.unavailable_reason !== null && (
        <p className={styles.reserve}>
          <span className={styles.point} aria-hidden="true" />
          {scenario.unavailable_reason}
        </p>
      )}

      {partielle && (
        <div className={styles.reserve}>
          <span className={styles.point} aria-hidden="true" />
          <div>
            <p>
              {phraseCouverturePartielle(
                couverture.excluded.length,
                couverture.covered_count,
                couverture.total_count,
              )}
            </p>
            <ul className={styles.exclues}>
              {couverture.excluded.map((ligne) => (
                <li key={ligne.ticker}>
                  <span className={styles.ticker}>{ligne.ticker}</span>{' '}
                  {pourcentage(ligne.weight, 1)} de la valeur&nbsp;: {ligne.reason}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <Provenance
        disposition="ligne"
        lignes={[
          // La période est dans le titre du bloc, à côté du nom de la crise.
          { libelle: 'Séances', valeur: seances(scenario.observations) },
          { libelle: 'Poids', valeur: `ceux du ${dateISO(asOf)}, quantités figées ensuite` },
          { libelle: 'Référence', valeur: definition.benchmark },
        ]}
      />

      {regime !== undefined && <BlocRegime regime={regime} />}
    </article>
  )
}

interface Props {
  readonly scenarios: readonly Scenario[]
  readonly regimes: readonly Regime[]
  readonly asOf: string
}

export function SectionCrise({ scenarios, regimes, asOf }: Props) {
  return (
    <Section ancre="en-crise" numero={5} titre="Ce qui se passe en crise">
      <p className={commun.chapeau}>
        Chaque crise est rejouée sur le portefeuille d'aujourd'hui&nbsp;: ses poids au
        départ, ses quantités figées ensuite. Trois chiffres par crise, à la
        même taille — la sortie, le pire moment traversé, et la part du
        portefeuille que le rejeu couvre réellement.
      </p>
      <div className={styles.liste}>
        {scenarios.map((scenario) => (
          <BlocScenario
            key={scenario.scenario.key}
            scenario={scenario}
            regime={regimes.find((r) => r.scenario.key === scenario.scenario.key)}
            asOf={asOf}
          />
        ))}
      </div>
    </Section>
  )
}
