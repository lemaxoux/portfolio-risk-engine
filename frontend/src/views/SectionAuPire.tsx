/**
 * Section 3 — « Ce qu'il a perdu au pire ». DESIGN.md §8.2, §9.4.
 *
 * Le chiffre d'abord, dans un bloc mesure avec sa phrase de lecture — la
 * chute, ses dates, le retour au pic, ce qu'elle représente sur la valeur
 * d'aujourd'hui — et sa provenance ; la courbe ensuite, qui montre OÙ ce
 * chiffre s'est produit. Le pic et le creux sont annotés sur la courbe
 * elle-même.
 *
 * Le creux affiché est celui du RÉGIME COURANT — la fenêtre d'estimation, pas
 * l'historique complet depuis 2005. Les crises rejouées, avec leur propre
 * « pire moment traversé », sont en section 5 : la provenance le dit par la
 * fenêtre et la période, écrites sous le chiffre comme sous la courbe.
 */
import { useCallback } from 'react'

import type { Drawdown, PortfolioSeries } from '../api/types'
import { Graphique, type ContexteGraphique } from '../components/charts/Graphique'
import { optionsRichesse, pointA } from '../components/charts/richesse'
import type { LigneProvenance } from '../components/Provenance'
import { Measure } from '../components/Measure'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import {
  ESPACE_INSECABLE,
  dateEnToutesLettres,
  dateISO,
  decimal,
  pourcentage,
} from '../lib/format'
import { introAuPire, lectureCreux, neDitPasCreux } from '../lib/phrases'
import { lignesDeFenetre } from '../lib/provenance'

/** Ce que lit un lecteur d'écran à la place de la courbe (§13). */
export function descriptionRichesse(serie: PortfolioSeries, creux: Drawdown): string {
  const depart = serie.wealth[0]
  const arrivee = serie.wealth[serie.wealth.length - 1]
  if (depart === undefined || arrivee === undefined) return 'Courbe de richesse vide.'
  return (
    `Une unité investie le ${dateISO(depart.date)} vaut ${decimal(arrivee.value, 2)} ` +
    `le ${dateISO(arrivee.date)}${ESPACE_INSECABLE}; perte maximale de ${pourcentage(creux.value, 1)} ` +
    `entre le pic du ${dateISO(creux.peak_date)} et le creux du ${dateISO(creux.trough_date)}.`
  )
}

interface Props {
  readonly serie: PortfolioSeries
  readonly creux: Drawdown
  readonly asOf: string
  /** Le code ISO de la devise publiée (`valuation.currency`). */
  readonly devise: string
}

export function SectionAuPire({ serie, creux, asOf, devise }: Props) {
  const options = useCallback(
    (contexte: ContexteGraphique) =>
      optionsRichesse({ richesse: serie.wealth, creux }, contexte),
    [serie, creux],
  )
  const depart = serie.wealth[0]
  const introduction = introAuPire(creux.period_label)
  // Le retour au pic n'a de ligne que s'il a eu lieu : `null` se dit dans la
  // phrase de lecture (« il n'avait pas encore retrouvé ce plus haut »).
  const retour: LigneProvenance[] =
    creux.recovery_date === null
      ? []
      : [{ libelle: 'Retour au pic', valeur: dateISO(creux.recovery_date) }]

  return (
    <Section ancre="au-pire" numero={3} titre="Ce qu'il a perdu au pire" introduction={introduction}>
      <div className={commun.rangee}>
        <Measure
          libelle="Perte maximale pic-creux"
          valeur={pourcentage(creux.value, 1)}
          lecture={lectureCreux(creux, devise)}
          neDitPas={neDitPasCreux(creux)}
          provenance={[
            { libelle: 'Pic', valeur: dateISO(creux.peak_date) },
            { libelle: 'Creux', valeur: dateISO(creux.trough_date) },
            ...retour,
            {
              libelle: 'Niveaux',
              valeur: `${decimal(pointA(serie.wealth, creux.peak_date).value, 3)} → ${decimal(pointA(serie.wealth, creux.trough_date).value, 3)}`,
            },
            ...lignesDeFenetre(creux.window),
          ]}
        />
      </div>

      <h3 className={commun.sousTitre}>Où ce creux s'est produit</h3>
      <Graphique
        titre={
          depart === undefined
            ? "Valeur d'une unité investie"
            : `Valeur de 1${ESPACE_INSECABLE}${devise} placé le ${dateEnToutesLettres(depart.date)}`
        }
        unite={`base 1${depart === undefined ? '' : ` le ${dateISO(depart.date)}`}, poids actuels`}
        fenetre={serie.window}
        asOf={asOf}
        description={descriptionRichesse(serie, creux)}
        options={options}
      />
    </Section>
  )
}
