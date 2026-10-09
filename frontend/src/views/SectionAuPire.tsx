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
import {
  colonnesCourbe,
  optionsRichesse,
  pointA,
  rangeesCourbe,
} from '../components/charts/richesse'
import type { LigneProvenance } from '../components/Provenance'
import { Measure } from '../components/Measure'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { LIBELLES } from '../contenu/libelles'
import { METHODES } from '../contenu/methodes'
import { dateISO, decimal, pourcentage } from '../lib/format'
import { useLangue, type Langue } from '../lib/langue'
import { lignesDeFenetre } from '../lib/provenance'

/** Ce que lit un lecteur d'écran à la place de la courbe (§13). */
export function descriptionRichesse(
  serie: PortfolioSeries,
  creux: Drawdown,
  langue: Langue = 'fr',
): string {
  const l = LIBELLES[langue].auPire
  const depart = serie.wealth[0]
  const arrivee = serie.wealth[serie.wealth.length - 1]
  if (depart === undefined || arrivee === undefined) return l.descriptionVide
  return l.description(
    depart.date,
    arrivee.value,
    arrivee.date,
    creux.value,
    creux.peak_date,
    creux.trough_date,
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
  const { langue, libelles, phrases } = useLangue()
  const l = libelles.auPire
  const options = useCallback(
    (contexte: ContexteGraphique) =>
      optionsRichesse({ richesse: serie.wealth, creux }, contexte),
    [serie, creux],
  )
  const depart = serie.wealth[0]
  const titre = depart === undefined ? l.titreSansDepart : l.titre(devise, depart.date)
  const introduction = phrases.introAuPire(creux.period_label)
  // Le retour au pic n'a de ligne que s'il a eu lieu : `null` se dit dans la
  // phrase de lecture (« il n'avait pas encore retrouvé ce plus haut »).
  const retour: LigneProvenance[] =
    creux.recovery_date === null
      ? []
      : [{ libelle: l.retourAuPic, valeur: dateISO(creux.recovery_date) }]

  return (
    <Section ancre="au-pire" numero={3} titre={libelles.sections[2]} introduction={introduction}>
      <div className={commun.rangee}>
        <Measure
          libelle={l.perteMaximale}
          valeur={pourcentage(creux.value, 1, langue)}
          lecture={phrases.lectureCreux(creux, devise)}
          neDitPas={phrases.neDitPasCreux(creux)}
          provenance={[
            { libelle: l.pic, valeur: dateISO(creux.peak_date) },
            { libelle: l.creux, valeur: dateISO(creux.trough_date) },
            ...retour,
            {
              libelle: l.niveaux,
              valeur: `${decimal(pointA(serie.wealth, creux.peak_date).value, 3, langue)} → ${decimal(pointA(serie.wealth, creux.trough_date).value, 3, langue)}`,
            },
            ...lignesDeFenetre(creux.window, langue),
          ]}
          methode={{ bloc: 'perte-maximale', ancres: METHODES.perteMaximale }}
        />
      </div>

      <h3 className={commun.sousTitre}>{l.ou}</h3>
      <Graphique
        titre={titre}
        unite={l.unite(depart === undefined ? null : depart.date)}
        fenetre={serie.window}
        asOf={asOf}
        methode={{ bloc: 'courbe', ancres: METHODES.courbe }}
        description={descriptionRichesse(serie, creux, langue)}
        options={options}
        valeurs={{
          legende: libelles.graphiques.tableauCourbe(titre),
          colonnes: colonnesCourbe(creux, langue),
          lignes: rangeesCourbe(serie.wealth, creux),
          cleDeLigne: (rangee) => rangee.date,
        }}
      />
    </Section>
  )
}
