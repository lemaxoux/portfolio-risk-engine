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
import { useCallback, useId, type CSSProperties } from 'react'

import type {
  Concentration,
  Contribution,
  Matrices,
  Scenario,
  VarianceContributions,
} from '../api/types'
import { LIBELLES } from '../contenu/libelles'
import { Absent } from '../components/Absent'
import { DataTable, type Colonne } from '../components/DataTable'
import { Graphique, type ContexteGraphique, type Trace } from '../components/charts/Graphique'
import {
  lignesParContribution,
  optionsContributions,
} from '../components/charts/contributions'
import {
  DOMAINE_CORRELATION,
  MARGE_HAUTE_CARTE,
  colonnesCorrelation,
  hautDeGrille,
  largeurMaxCarte,
  optionsCarteCorrelation,
  rangeesCorrelation,
} from '../components/charts/correlation'
import { Measure } from '../components/Measure'
import { Provenance } from '../components/Provenance'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { METHODES, avecRefus, type Methode } from '../contenu/methodes'
import {
  dateISO,
  decimal,
  decimalOuTiret,
  lignes as compteLignes,
  pointsSignes,
  pointsSignesEnToutesLettres,
  pourcentage,
} from '../lib/format'
import { useLangue, type Langue } from '../lib/langue'
import { lignesDeFenetre } from '../lib/provenance'
import styles from './SectionRisque.module.css'

/** La légende exacte de §5.4, dans une langue. */
export function legendeContributions(langue: Langue = 'fr'): string {
  const l = LIBELLES[langue].risque
  return `${l.cleBarre}, ${l.cleTrait}`
}
export const LEGENDE_CONTRIBUTIONS = legendeContributions('fr')

/** Une contribution de scénario : le chiffre signé, et sa marque de signe. */
function ApportEnCrise({ scenario, ticker }: { scenario: Scenario; ticker: string }) {
  const { langue, libelles } = useLangue()
  if (scenario.end_to_end_return === null) {
    return (
      <span className={styles.absent}>
        <Absent />
      </span>
    )
  }
  const apport = scenario.contributions.find((ligne) => ligne.ticker === ticker)
  if (apport === undefined) {
    return (
      <span className={styles.absent}>
        <Absent />
        {libelles.risque.nonCouverte}
      </span>
    )
  }
  const sens = apport.contribution < 0 ? styles.perte : apport.contribution > 0 ? styles.gain : ''
  return (
    <span className={styles.apport}>
      {pointsSignes(apport.contribution, 1, langue)}
      <span className={`${styles.marque} ${sens}`} aria-hidden="true" />
    </span>
  )
}

export function colonnesDuRisque(
  scenarios: readonly Scenario[],
  langue: Langue = 'fr',
): Colonne<Contribution>[] {
  const titres = LIBELLES[langue].risque.colonnes
  return [
    { cle: 'ticker', titre: titres.ticker, nature: 'texte', cellule: (l) => l.ticker },
    {
      cle: 'variance',
      titre: titres.variance,
      nature: 'nombre',
      cellule: (l) => pourcentage(l.contribution, 1, langue),
    },
    {
      cle: 'capital',
      titre: titres.capital,
      nature: 'nombre',
      cellule: (l) => pourcentage(l.weight, 1, langue),
    },
    {
      cle: 'ecart',
      titre: titres.ecart,
      nature: 'nombre',
      cellule: (l) => pointsSignes(l.excess_over_weight, 1, langue),
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

/**
 * La légende de la carte, en trois paragraphes : l'échelle de couleurs, sa
 * lecture, la clé de la diagonale. Sous 900 px, ils se suivent sous la grille,
 * dans cet ordre. À partir de 900 px, la lecture passe à droite de la carte,
 * alignée sur le haut de sa grille, dans la place que les cellules laissent
 * vide ; l'échelle et la diagonale restent dessous (`.carte`, §5.4).
 *
 * Les cinq points de l'échelle sont des pastilles, pas un dégradé (§12).
 */
function LegendeCorrelation() {
  const { langue, libelles } = useLangue()
  const classes = [
    styles.divNegFort,
    styles.divNegMoyen,
    styles.divZero,
    styles.divPosMoyen,
    styles.divPosFort,
  ]
  return (
    <div className={styles.legendeCorrelation}>
      <p className={styles.echelle}>
        {DOMAINE_CORRELATION.map((valeur, rang) => (
          <span key={valeur} className={styles.pas}>
            <span className={`${styles.pastille} ${classes[rang] ?? ''}`} aria-hidden="true" />
            {decimal(valeur, 1, langue)}
          </span>
        ))}
      </p>
      <p className={styles.lectureEchelle}>{libelles.risque.lectureEchelle}</p>
      <p className={`${styles.pas} ${styles.cleDiagonale}`}>
        <span className={`${styles.pastille} ${styles.diagonale}`} aria-hidden="true" />
        {libelles.risque.diagonale}
      </p>
    </div>
  )
}

/**
 * Un graphique que le moteur refuse : sa raison, à la place du dessin, et le
 * lien vers la méthode de la mesure et vers celle des refus (chantier 7E).
 */
function Refus({ raison, methode }: { raison: string; methode: Methode }) {
  return (
    <div className={styles.refus}>
      <span className={styles.point} aria-hidden="true" />
      <div>
        <p>{raison}</p>
        <div className={styles.methode}>
          <Provenance lignes={[]} disposition="ligne" methode={methode} />
        </div>
      </div>
    </div>
  )
}

/**
 * Les deux mesures de la carte dont sa mise en page a besoin, posées en
 * propriétés CSS sur son conteneur : sa largeur quand la place ne manque pas,
 * et la hauteur des tickers au-dessus de sa grille. À partir de 900 px, la
 * lecture de l'échelle se place juste à droite de la première, à la hauteur
 * de la seconde. Elles viennent du module qui dessine la carte : rien n'est
 * recopié ici.
 */
function dispositionDeCarte(nombreDeLignes: number): CSSProperties {
  return {
    '--largeur-carte': `${largeurMaxCarte(nombreDeLignes)}px`,
    '--haut-de-grille': `${MARGE_HAUTE_CARTE}px`,
  } as CSSProperties
}

interface Props {
  readonly variance: VarianceContributions
  readonly concentration: Concentration
  readonly matrices: Matrices
  readonly scenarios: readonly Scenario[]
  readonly asOf: string
}

export function SectionRisque({ variance, concentration, matrices, scenarios, asOf }: Props) {
  const { langue, libelles, phrases } = useLangue()
  const l = libelles.risque
  const contributions = variance.contributions
  const correlation = matrices.correlation
  // La ligne qui fait le plus bouger le portefeuille : la première du tri par
  // part de variance, celui du graphique. Un tri, pas un calcul.
  const premiere = contributions === null ? undefined : lignesParContribution(contributions)[0]
  const introduction = l.introduction
  // La légende du tableau qui suit les barres : il en porte toutes les
  // valeurs, et le tracé le désigne plutôt que d'en recevoir un second.
  const idTableau = useId()

  const optionsBarres = useCallback(
    (contexte: ContexteGraphique) => optionsContributions(contributions ?? [], contexte),
    [contributions],
  )
  const optionsCarte = useCallback(
    (contexte: ContexteGraphique) =>
      optionsCarteCorrelation(correlation ?? { tickers: [], values: [] }, contexte),
    [correlation],
  )
  // Le haut de la grille, lu sur la carte dessinée : la lecture de l'échelle
  // s'y aligne à partir de 900 px. Avant le premier dessin, `.carte` donne la
  // hauteur des tickers.
  const proprietesCarte = useCallback(
    (trace: Trace) => ({
      '--haut-de-grille': `${hautDeGrille(trace, correlation ?? { tickers: [], values: [] })}px`,
    }),
    [correlation],
  )

  return (
    <Section ancre="qui-porte" numero={4} titre={libelles.sections[3]} introduction={introduction}>
      <h3 className={commun.sousTitre}>{l.combien}</h3>
      <p className={commun.chapeau}>{phrases.chapeauLignesEffectives(concentration.n_positions)}</p>
      <div className={commun.rangee}>
        <Measure
          libelle={l.enCapital}
          valeur={decimal(concentration.effective_positions, 1, langue)}
          lecture={phrases.lectureLignesEnCapital(
            concentration.n_positions,
            concentration.effective_positions,
          )}
          neDitPas={phrases.NE_DIT_PAS_CAPITAL}
          provenance={[
            { libelle: l.lignes, valeur: compteLignes(concentration.n_positions, langue) },
            { libelle: libelles.provenance.valoriseAu, valeur: dateISO(concentration.as_of) },
          ]}
          methode={{ bloc: 'lignes-capital', ancres: METHODES.lignesEffectives }}
        />
        <Measure
          libelle={l.enRisque}
          valeur={decimalOuTiret(variance.effective_positions, 1, langue)}
          lecture={
            variance.effective_positions === null
              ? (variance.undefined_reason ?? l.nonEstimable)
              : phrases.lectureLignesEnRisque(concentration.n_positions, variance.effective_positions)
          }
          neDitPas={
            variance.effective_positions === null ? phrases.NE_DIT_PAS_REFUS : phrases.NE_DIT_PAS_RISQUE
          }
          provenance={lignesDeFenetre(variance.window, langue)}
          methode={{
            bloc: 'lignes-risque',
            ancres: avecRefus(METHODES.lignesEffectives, variance.effective_positions === null),
          }}
        />
      </div>

      <h3 className={commun.sousTitre}>{l.poids}</h3>
      {contributions === null ? (
        <Refus
          raison={variance.undefined_reason ?? l.contributionsNonEstimables}
          methode={{
            bloc: 'parts-des-variations',
            ancres: avecRefus(METHODES.partsDesVariations, true),
          }}
        />
      ) : (
        <>
          <p className={commun.chapeau}>{l.chapeauPoids}</p>
          {premiere !== undefined && (
            <p className={commun.lecture}>{phrases.lectureContribution(premiere)}</p>
          )}
          <p className={commun.neDitPas}>{phrases.NE_DIT_PAS_CONTRIBUTIONS}</p>
          <Graphique
            titre={l.titreBarres}
            unite={l.uniteBarres}
            fenetre={variance.window}
            asOf={asOf}
            methode={{ bloc: 'parts-des-variations', ancres: METHODES.partsDesVariations }}
            description={l.descriptionBarres(
              contributions.length,
              lignesParContribution(contributions)
                .map(
                  (ligne) =>
                    `${ligne.ticker} ${pointsSignesEnToutesLettres(ligne.excess_over_weight, 1, langue)}`,
                )
                .join(', '),
            )}
            options={optionsBarres}
            decritPar={idTableau}
          >
            <p className={styles.legende}>
              <span className={styles.cleBarre} aria-hidden="true" />
              {l.cleBarre}
              {', '}
              <span className={styles.cleTrait} aria-hidden="true" />
              {l.cleTrait}
            </p>
          </Graphique>
          {variance.has_negative_contribution === true && (
            <p className={styles.negative}>{phrases.PHRASE_CONTRIBUTION_NEGATIVE}</p>
          )}
          <div className={styles.tableau}>
            <DataTable
              legende={l.legendeTableau}
              idLegende={idTableau}
              colonnes={colonnesDuRisque(scenarios, langue)}
              lignes={lignesParContribution(contributions)}
              cleDeLigne={(l) => l.ticker}
            />
            <div className={styles.methode}>
              <Provenance
                lignes={[]}
                disposition="ligne"
                methode={{ bloc: 'apports-en-crise', ancres: METHODES.apportsEnCrise }}
              />
            </div>
          </div>
        </>
      )}

      <h3 className={commun.sousTitre}>{l.ensemble}</h3>
      <p className={commun.chapeau}>{l.chapeauEnsemble}</p>
      {correlation === null ? (
        <Refus
          raison={matrices.correlation_undefined_reason ?? l.correlationNonEstimable}
          methode={{ bloc: 'correlation', ancres: avecRefus(METHODES.correlation, true) }}
        />
      ) : (
        <div className={styles.carte} style={dispositionDeCarte(correlation.tickers.length)}>
          <Graphique
            titre={l.titreCarte}
            unite={l.uniteCarte}
            fenetre={matrices.window}
            asOf={asOf}
            methode={{ bloc: 'correlation', ancres: METHODES.correlation }}
            description={l.descriptionCarte(correlation.tickers.length)}
            options={optionsCarte}
            proprietesDuTrace={proprietesCarte}
            valeurs={{
              legende: libelles.graphiques.tableauCorrelation,
              colonnes: colonnesCorrelation(correlation, langue),
              lignes: rangeesCorrelation(correlation),
              cleDeLigne: (rangee) => rangee.ticker,
            }}
          >
            <LegendeCorrelation />
          </Graphique>
        </div>
      )}
      {correlation !== null && <p className={commun.neDitPas}>{phrases.NE_DIT_PAS_CORRELATION}</p>}
    </Section>
  )
}
