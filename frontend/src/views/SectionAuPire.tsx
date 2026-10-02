/**
 * Section 3 — « Ce qu'il a perdu au pire ». DESIGN.md §8.2, §9.4.
 *
 * Le chiffre d'abord, dans un bloc mesure avec sa provenance ; la courbe
 * ensuite, qui montre OÙ ce chiffre s'est produit. Le pic et le creux sont
 * annotés sur la courbe elle-même.
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
import { Measure } from '../components/Measure'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { dateISO, decimal, pourcentage } from '../lib/format'
import { lectureDeCreux } from '../lib/phrases'
import { lignesDeFenetre } from '../lib/provenance'

/** Ce que lit un lecteur d'écran à la place de la courbe (§13). */
export function descriptionRichesse(serie: PortfolioSeries, creux: Drawdown): string {
  const depart = serie.wealth[0]
  const arrivee = serie.wealth[serie.wealth.length - 1]
  if (depart === undefined || arrivee === undefined) return 'Courbe de richesse vide.'
  return (
    `Une unité investie le ${dateISO(depart.date)} vaut ${decimal(arrivee.value, 2)} ` +
    `le ${dateISO(arrivee.date)}\u00a0; perte maximale de ${pourcentage(creux.value, 1)} ` +
    `entre le pic du ${dateISO(creux.peak_date)} et le creux du ${dateISO(creux.trough_date)}.`
  )
}

interface Props {
  readonly serie: PortfolioSeries
  readonly creux: Drawdown
  readonly asOf: string
}

export function SectionAuPire({ serie, creux, asOf }: Props) {
  const options = useCallback(
    (contexte: ContexteGraphique) =>
      optionsRichesse({ richesse: serie.wealth, creux }, contexte),
    [serie, creux],
  )
  const depart = serie.wealth[0]

  return (
    <Section ancre="au-pire" numero={3} titre="Ce qu'il a perdu au pire">
      <p className={commun.chapeau}>
        La plus forte baisse depuis un sommet, sur la fenêtre d'estimation&nbsp;: ce
        qu'aurait perdu quelqu'un entré au plus haut et sorti au plus bas, avec
        les positions d'aujourd'hui.
      </p>
      <div className={commun.rangee}>
        <Measure
          libelle="Perte maximale pic-creux"
          valeur={pourcentage(creux.value, 1)}
          lecture={lectureDeCreux(creux.peak_date, creux.trough_date)}
          provenance={[
            { libelle: 'Pic', valeur: dateISO(creux.peak_date) },
            { libelle: 'Creux', valeur: dateISO(creux.trough_date) },
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
        titre="Valeur d'une unité investie"
        unite={`base 1${depart === undefined ? '' : ` le ${dateISO(depart.date)}`}, poids actuels`}
        fenetre={serie.window}
        asOf={asOf}
        description={descriptionRichesse(serie, creux)}
        options={options}
      />
    </Section>
  )
}
