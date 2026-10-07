/**
 * La page méthodologie — DESIGN.md §8.2, §6.3.
 *
 * Comment chaque chiffre de l'analyse est obtenu, pour un lecteur qui part de
 * zéro. Le texte n'est pas dans cette vue : il est dans un fichier de contenu
 * par langue (`src/contenu/`), que `lib/contenu.ts` lit en blocs typés. La
 * vue les compose, sans ajouter un mot, sinon le nom de la navigation.
 *
 * ═══ AUCUN PORTEFEUILLE, AUCUN APPEL ═══
 *
 * Le texte ne cite aucun chiffre d'un portefeuille, et la page n'appelle pas
 * l'API : elle s'affiche sans attendre la liste des portefeuilles. Le bandeau
 * nomme le dernier portefeuille consulté, s'il existe encore, pour que
 * « Analyse » et « Positions et import » y ramènent.
 *
 * ═══ LES PARTIES ET LEURS ANCRES ═══
 *
 * Chaque partie (`##`) est une `<section>` que son titre nomme, et que le
 * rail liste sans numéro. Chaque titre, de partie ou d'entrée, porte son
 * ancre fixe et `tabIndex={-1}` : `/methodologie#cvar` fait défiler la page
 * jusqu'à lui et lui donne le focus (`components/Cadre`).
 *
 * ═══ LES FORMULES ═══
 *
 * En IBM Plex Sans, dans la phrase ou sur leur propre ligne (§6.3) :
 * Spectral n'a pas de lettre grecque. Indices et exposants en `<sub>` et
 * `<sup>`. Une formule en bloc qui dépasserait la colonne défilerait dans son
 * cadre, jamais la page.
 */
import { Fragment, useMemo } from 'react'

import type { PortfolioDetail } from '../api/types'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import {
  AncresSections,
  pagesApplication,
  RailSections,
  type SectionDeNavigation,
} from '../components/Navigation'
import { LANGUE, METHODOLOGIE } from '../contenu/langue'
import { lireContenu, type Bloc, type Corps, type EnLigne, type Morceau } from '../lib/contenu'
import { cheminDe } from '../lib/route'
import communs from './Pages.module.css'
import styles from './Methodologie.module.css'

const PAGE = cheminDe({ vue: 'methodologie' })

/** Le nom du rail et de la liste d'ancres, pour un lecteur d'écran. */
const PARTIES = 'Parties de la méthodologie'

type Titre = Extract<Bloc, { type: 'titre' }>

interface Partie {
  readonly titre: Titre
  readonly blocs: readonly Bloc[]
}

/**
 * Les blocs qui suivent le titre de la page, avant la première partie, puis
 * chaque partie avec les siens.
 */
function enParties(blocs: readonly Bloc[]): { tete: Bloc[]; parties: Partie[] } {
  const tete: Bloc[] = []
  const parties: { titre: Titre; blocs: Bloc[] }[] = []
  for (const bloc of blocs) {
    if (bloc.type === 'titre' && bloc.niveau === 2) parties.push({ titre: bloc, blocs: [] })
    else (parties[parties.length - 1]?.blocs ?? tete).push(bloc)
  }
  return { tete, parties }
}

function Formule({ morceaux }: { morceaux: readonly Morceau[] }) {
  return (
    <>
      {morceaux.map((morceau, rang) =>
        morceau.position === 'indice' ? (
          <sub key={rang}>{morceau.texte}</sub>
        ) : morceau.position === 'exposant' ? (
          <sup key={rang}>{morceau.texte}</sup>
        ) : (
          <Fragment key={rang}>{morceau.texte}</Fragment>
        ),
      )}
    </>
  )
}

function EnLignes({ contenu }: { contenu: readonly EnLigne[] }) {
  return (
    <>
      {contenu.map((element, rang) => {
        switch (element.type) {
          case 'texte':
            return <Fragment key={rang}>{element.texte}</Fragment>
          case 'formule':
            return (
              <span key={rang} className={styles.formule}>
                <Formule morceaux={element.morceaux} />
              </span>
            )
          case 'lien':
            return (
              <a key={rang} href={`#${element.cible}`}>
                <EnLignes contenu={element.contenu} />
              </a>
            )
        }
      })}
    </>
  )
}

/** Un paragraphe ou un élément de liste : l'étiquette en tête, puis le texte. */
function Texte({ corps }: { corps: Corps }) {
  return (
    <>
      {corps.etiquette !== null && <strong className={styles.etiquette}>{corps.etiquette}</strong>}
      <EnLignes contenu={corps.contenu} />
    </>
  )
}

/** Un bloc dans une partie. Les titres de la page et des parties sont rendus plus haut. */
function BlocDe({ bloc }: { bloc: Bloc }) {
  switch (bloc.type) {
    case 'titre':
      return bloc.niveau === 3 ? (
        <h3 id={bloc.ancre ?? undefined} tabIndex={-1} className={styles.entree}>
          <EnLignes contenu={bloc.contenu} />
        </h3>
      ) : null
    case 'paragraphe':
      return (
        <p className={styles.texte}>
          <Texte corps={bloc} />
        </p>
      )
    case 'liste':
      return (
        <ul className={styles.liste}>
          {bloc.elements.map((element, rang) => (
            <li key={rang}>
              <Texte corps={element} />
            </li>
          ))}
        </ul>
      )
    case 'formule':
      return (
        <p className={styles.formuleBloc}>
          <Formule morceaux={bloc.morceaux} />
        </p>
      )
  }
}

function PartieDe({ partie }: { partie: Partie }) {
  const ancre = partie.titre.ancre ?? undefined
  return (
    <section className={styles.partie} aria-labelledby={ancre}>
      <h2 id={ancre} tabIndex={-1} className={styles.titrePartie}>
        <EnLignes contenu={partie.titre.contenu} />
      </h2>
      {partie.blocs.map((bloc) => (
        <BlocDe key={bloc.ligne} bloc={bloc} />
      ))}
    </section>
  )
}

interface Props {
  /** Le dernier portefeuille consulté, s'il existe encore ; sinon aucun. */
  readonly portefeuille: PortfolioDetail | null
}

export function VueMethodologie({ portefeuille }: Props) {
  const { contenu, tete, parties, sections } = useMemo(() => {
    const lu = lireContenu(METHODOLOGIE[LANGUE])
    const sections: SectionDeNavigation[] = lu.parties.map((partie) => ({
      ancre: partie.ancre,
      libelle: partie.titre,
    }))
    // Le premier bloc est le titre de la page, rendu à part.
    return { contenu: lu, sections, ...enParties(lu.blocs.slice(1)) }
  }, [])
  const pages = pagesApplication('methodologie', portefeuille?.id ?? null)

  return (
    <Cadre
      titre={contenu.titre}
      page={PAGE}
      entete={<BandeauSimple portefeuille={portefeuille?.name ?? null} />}
      rail={<RailSections pages={pages} sections={sections} etiquette={PARTIES} />}
    >
      <AncresSections pages={pages} liste={sections} etiquette={PARTIES} />
      <h1 tabIndex={-1} className={communs.titre}>
        {contenu.titre}
      </h1>
      {tete.map((bloc) => (
        <BlocDe key={bloc.ligne} bloc={bloc} />
      ))}
      {parties.map((partie) => (
        <PartieDe key={partie.titre.ligne} partie={partie} />
      ))}
    </Cadre>
  )
}
