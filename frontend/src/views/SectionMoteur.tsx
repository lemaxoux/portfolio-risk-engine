/**
 * Section 6 — « Ce que le moteur en dit ». DESIGN.md §8.2, §9.2, §15.
 *
 * La liste des observations du moteur de règles, dans l'ordre où il les
 * publie. Aucun score, aucune synthèse, aucun tri par « gravité » : le moteur
 * décrit, il ne classe pas (§11.1).
 *
 * En pied de section, le rappel court et permanent de l'acceptation (§15) :
 * en texte courant, sans case ni bouton. Ce sont les titres des sections du
 * bandeau, tels que le backend les publie — l'interface n'en écrit pas une
 * version abrégée à elle.
 */
import type { Disclaimer, Observation as ObservationApi } from '../api/types'
import { Observation } from '../components/Observation'
import { Provenance } from '../components/Provenance'
import { Section } from '../components/Section'
import commun from '../components/Section.module.css'
import { dateISO } from '../lib/format'
import styles from './SectionMoteur.module.css'

interface Props {
  readonly observations: readonly ObservationApi[]
  readonly bandeau: Disclaimer
  readonly asOf: string
}

export function SectionMoteur({ observations, bandeau, asOf }: Props) {
  return (
    <Section ancre="moteur" numero={6} titre="Ce que le moteur en dit">
      <p className={commun.chapeau}>
        Des propriétés chiffrées du portefeuille, écrites par le moteur de
        règles. Elles décrivent, elles ne prescrivent pas. Quand une phrase
        repose sur un seuil, il est donné avec sa provenance ; un seuil choisi
        à la main le dit.
      </p>
      <div className={commun.conditions}>
        <Provenance disposition="ligne" lignes={[{ libelle: 'Valorisé au', valeur: dateISO(asOf) }]} />
      </div>

      <div className={styles.liste}>
        {observations.map((observation) => (
          <Observation
            key={`${observation.rule}-${observation.subject}`}
            observation={observation}
          />
        ))}
      </div>

      <footer className={styles.rappel}>
        <p className={styles.rappelTitre}>{bandeau.title}</p>
        <ul className={styles.rappelListe}>
          {bandeau.sections.map((section) => (
            <li key={section.title}>{section.title}</li>
          ))}
        </ul>
      </footer>
    </Section>
  )
}
