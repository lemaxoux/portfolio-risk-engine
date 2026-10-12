/**
 * La page de présentation — DESIGN.md §19 (chantier 9.4).
 *
 * Dans la démonstration, l'adresse `/` présente le projet à quelqu'un qui ne
 * le connaît pas : un recruteur, qui lira deux minutes. Une page de l'outil,
 * pas une page de site marketing (§19.2) : une colonne de lecture, sans
 * grand chiffre ni bouton d'appel. Les entrées sont les liens du tableau.
 *
 * ═══ LE TEXTE EST DANS LE BUNDLE, IL S'AFFICHE TOUJOURS ═══
 *
 * Le premier écran n'attend aucune requête (§19.9) : la liste et l'analyse
 * du premier portefeuille sont demandées une fois ce premier écran peint.
 * Seuls deux blocs lisent un fichier : le tableau des portefeuilles et le
 * bloc du résultat. Chacun a le squelette de sa forme, et son message quand
 * son fichier manque ; le reste de la page se lit sans eux (§19.8). La page
 * n'est pas « occupée » en entier.
 *
 * ═══ AUCUN NOMBRE N'EST ÉCRIT ICI ═══
 *
 * La prose ne contient aucun nombre, ni en chiffres ni en lettres
 * (`contenu/presentation.test.ts`). Ceux qui s'affichent sont lus dans un
 * fichier exporté ou dans `contenu/demo.ts`, et écrits par `format.ts`.
 *
 * LE RÉSULTAT EST UNE PHRASE DE L'ANALYSE, pas un texte de la page : celle
 * de la section 5 qui compare, pour la première crise rejouée, ce que le
 * comportement de temps ordinaire laissait attendre et ce que le rejeu
 * donne. La même fonction (`phrases.lecturePrediction`) la compose, depuis
 * les mêmes champs publiés, lus dans l'analyse exportée du premier
 * portefeuille. Sa couverture la suit, à sa taille, écrite par le code de
 * la section 5 (`lib/couverture`, §11.2) ; puis ses conditions, dans une
 * grille libellé et valeur, comme sous une mesure (§9.1). C'est le produit
 * qui parle : la page montre un chiffre et ses conditions comme un seul
 * objet, au lieu de le dire.
 *
 * Cette page n'existe que dans la démonstration. Dans l'application, `/`
 * reste une redirection (`App.tsx`).
 */
import { useEffect, useState } from 'react'

import { ApiErreur, getAnalysis, versApiErreur } from '../api/client'
import type { Analysis, PortfolioDetail } from '../api/types'
import { Absent } from '../components/Absent'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { DataTable, type Colonne } from '../components/DataTable'
import { Lien } from '../components/Lien'
import { MessageErreur } from '../components/MessageErreur'
import { AncresSections, pagesApplication, RailPages, SECTIONS } from '../components/Navigation'
import { Provenance, type LigneProvenance } from '../components/Provenance'
import { DATE_DE_LA_DEMO, PORTEFEUILLES_DE_LA_DEMO } from '../contenu/demo'
import { ADRESSES, NOMS } from '../contenu/liens'
import { apresLAffichage } from '../lib/affichage'
import { ecrireLaCouverture } from '../lib/couverture'
import { dateISO, montant, seances } from '../lib/format'
import { useLangue } from '../lib/langue'
import type { EtatListe } from '../lib/liste'
import { cheminDe } from '../lib/route'
import controles from '../styles/controles.module.css'
import communs from './Pages.module.css'
import styles from './Presentation.module.css'

const PAGE = cheminDe({ vue: 'accueil' })

/** Le premier portefeuille : celui dont l'analyse donne le résultat. */
const PREMIER = 1

/** La section de l'analyse où se lit la crise, avec sa provenance complète. */
const SECTION_DES_CRISES = `${cheminDe({ vue: 'analyse', id: PREMIER })}#${SECTIONS[4].ancre}`

const TITRE_DU_BLOC = 'resultat-titre'

// ═══════════════════════════════════════════ Le tableau des portefeuilles ══

/**
 * Une cellule du squelette : la place d'un texte, sans texte, à peu près à
 * sa largeur. Les colonnes prennent ainsi leur place avant leurs données, et
 * les en-têtes ne se replacent presque pas quand elles arrivent.
 */
function barre(largeur: string | undefined) {
  return () => <span className={`${styles.barre} ${largeur}`} />
}

/**
 * Les portefeuilles de la démonstration : le nom, qui est le lien vers
 * l'analyse, les titres et la valeur, lus dans la liste. La date de la
 * légende est celle de la mention (`contenu/demo.ts`).
 *
 * Le squelette est le même tableau, sans ses données : la légende, les
 * en-têtes, une rangée par portefeuille. Il a la même largeur, donc la même
 * légende, sur autant de lignes. À partir de 900 px, où le tableau est dans
 * le premier écran, les titres ne se coupent pas et les rangées font 36 px
 * dans les deux cas : rien ne bouge à l'arrivée. En dessous, les titres
 * passent à la ligne après leurs virgules, et le tableau, alors hors du
 * premier écran, peut grandir en arrivant.
 */
function TableauDesPortefeuilles({
  liste,
  recharger,
}: {
  liste: EtatListe
  recharger: () => Promise<void>
}) {
  const { langue, libelles } = useLangue()
  const l = libelles.presentation.tableau
  const legende = l.legende(DATE_DE_LA_DEMO)

  if (liste.phase === 'erreur') {
    return (
      <MessageErreur
        erreur={liste.erreur}
        action={
          <button type="button" className={controles.bouton} onClick={() => void recharger()}>
            {libelles.application.rechargerLaListe}
          </button>
        }
      />
    )
  }

  if (liste.phase === 'chargement') {
    const vides: Colonne<number>[] = [
      {
        cle: 'portefeuille',
        titre: l.colonnes.portefeuille,
        nature: 'texte',
        cellule: barre(styles.barreDeNom),
      },
      {
        cle: 'titres',
        titre: l.colonnes.titres,
        nature: 'texte',
        cellule: barre(styles.barreDeTitres),
      },
      {
        cle: 'valeur',
        titre: l.colonnes.valeur,
        nature: 'nombre',
        cellule: barre(styles.barreDeValeur),
      },
    ]
    return (
      <div className={styles.tableau} aria-hidden="true">
        <DataTable
          legende={legende}
          colonnes={vides}
          lignes={Array.from({ length: PORTEFEUILLES_DE_LA_DEMO }, (_, rang) => rang)}
          cleDeLigne={(rang) => String(rang)}
        />
      </div>
    )
  }

  const colonnes: Colonne<PortfolioDetail>[] = [
    {
      cle: 'portefeuille',
      titre: l.colonnes.portefeuille,
      nature: 'texte',
      cellule: (p) => <Lien vers={cheminDe({ vue: 'analyse', id: p.id })}>{p.name}</Lien>,
    },
    {
      cle: 'titres',
      titre: l.colonnes.titres,
      nature: 'texte',
      cellule: (p) => (
        <span className={styles.titres}>
          {p.positions.map((position) => position.ticker).join(', ')}
        </span>
      ),
    },
    {
      cle: 'valeur',
      titre: l.colonnes.valeur,
      nature: 'nombre',
      cellule: (p) =>
        p.valuation === null ? (
          <Absent />
        ) : (
          montant(p.valuation.total_value, p.valuation.currency, langue)
        ),
    },
  ]
  return (
    <div className={styles.tableau}>
      <DataTable
        legende={legende}
        colonnes={colonnes}
        lignes={liste.portefeuilles}
        cleDeLigne={(p) => String(p.id)}
      />
    </div>
  )
}

// ═════════════════════════════════════════════════ Le bloc du résultat ══

type EtatDuResultat =
  | { phase: 'chargement'; precedente: Analysis | null }
  | { phase: 'erreur'; erreur: ApiErreur }
  | { phase: 'lue'; analyse: Analysis }

/** L'analyse à montrer : la nouvelle, ou, pendant qu'elle se relit, la précédente. */
function analyseDe(etat: EtatDuResultat): Analysis | null {
  return etat.phase === 'lue' ? etat.analyse : etat.phase === 'chargement' ? etat.precedente : null
}

/**
 * La phrase, sa couverture, ses conditions, puis le lien vers la section 5.
 *
 * L'analyse du premier portefeuille est demandée APRÈS le premier affichage
 * (`lib/affichage`, §19.9) : c'est une requête de plus, et le premier écran
 * n'en attend aucune. Un changement de langue la relit, la précédente
 * restant en place.
 */
function BlocDuResultat() {
  const { langue, libelles, phrases } = useLangue()
  const l = libelles.presentation.resultat
  const [etat, setEtat] = useState<EtatDuResultat>({ phase: 'chargement', precedente: null })
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    let vivant = true
    setEtat((avant) => ({ phase: 'chargement', precedente: analyseDe(avant) }))
    const renoncer = apresLAffichage(() => {
      getAnalysis(PREMIER, langue).then(
        (analyse) => {
          if (vivant) setEtat({ phase: 'lue', analyse })
        },
        (cause: unknown) => {
          if (vivant) setEtat({ phase: 'erreur', erreur: versApiErreur(cause, langue) })
        },
      )
    })
    return () => {
      vivant = false
      renoncer()
    }
  }, [langue, essai])

  if (etat.phase === 'erreur') {
    return (
      <MessageErreur
        erreur={etat.erreur}
        action={
          <button
            type="button"
            className={controles.bouton}
            onClick={() => setEssai((n) => n + 1)}
          >
            {libelles.analyse.rechargerLAnalyse}
          </button>
        }
      />
    )
  }

  const analyse = analyseDe(etat)
  if (analyse === null) {
    return (
      <div className={styles.bloc} aria-hidden="true">
        <span className={`${styles.barre} ${styles.barreDeTitre}`} />
        <span className={`${styles.barre} ${styles.ligne}`} />
        <span className={`${styles.barre} ${styles.ligne}`} />
        <span className={`${styles.barre} ${styles.ligne} ${styles.courte}`} />
      </div>
    )
  }

  // La première crise que l'analyse rejoue, telle que le moteur la publie.
  const [regime] = analyse.regimes
  if (regime === undefined) {
    return (
      <div className={styles.bloc}>
        <p className={styles.reserve}>
          <span className={styles.point} aria-hidden="true" />
          {libelles.crise.regimeIndisponible}
        </p>
      </div>
    )
  }

  const prediction = phrases.lecturePrediction(regime)
  const couverture = ecrireLaCouverture(regime.coverage, langue)
  const calme = regime.calm_beta
  const conditions: LigneProvenance[] = [
    { libelle: l.conditions.portefeuille, valeur: analyse.portfolio.name },
    { libelle: libelles.provenance.valoriseAu, valeur: dateISO(analyse.as_of) },
    // La fenêtre et la période sont celles de la mesure citée, le
    // comportement de temps ordinaire, pas celles du bandeau de l'analyse.
    ...(calme === null
      ? []
      : [
          { libelle: libelles.provenance.fenetre, valeur: seances(calme.observations, langue) },
          {
            libelle: libelles.provenance.periode,
            valeur: `${dateISO(calme.start)} → ${dateISO(calme.end)}`,
          },
        ]),
    {
      libelle: l.conditions.crise,
      valeur: `${dateISO(regime.scenario.start)} → ${dateISO(regime.scenario.end)}`,
    },
  ]

  return (
    <article className={styles.bloc} aria-labelledby={TITRE_DU_BLOC}>
      <h3 id={TITRE_DU_BLOC} className={styles.titreDuBloc}>
        {l.titreDuBloc(regime.scenario.name, analyse.portfolio.name)}
      </h3>

      {prediction !== null ? (
        <p className={styles.phrase}>{prediction}</p>
      ) : (
        // Le moteur ne publie pas la comparaison : sa raison, comme en section 5.
        <p className={styles.reserve}>
          <span className={styles.point} aria-hidden="true" />
          {regime.unavailable_reason ?? libelles.crise.regimeIndisponible}
        </p>
      )}

      {/* La couverture suit la phrase, à sa taille (§11.2, §19.3) : pas dans
          la grille des conditions, qui est plus petite. */}
      <p className={styles.couverture}>
        <span className={styles.libelle}>{libelles.crise.couverture}</span>
        <span>{couverture.part}</span>
        <span className={styles.lignes}>
          {couverture.partielle && <span className={styles.point} aria-hidden="true" />}
          {couverture.lignes}
        </span>
      </p>

      <p className={styles.detailsTitre}>{libelles.mesure.detailsDuCalcul}</p>
      <Provenance lignes={conditions} />

      <p className={styles.suite}>
        <Lien vers={SECTION_DES_CRISES}>{l.lien}</Lien>
      </p>
    </article>
  )
}

// ══════════════════════════════════════════════════════════════ La page ══

interface Props {
  readonly liste: EtatListe
  readonly recharger: () => Promise<void>
  /** Le dernier portefeuille consulté, s'il existe encore : le bandeau le nomme. */
  readonly portefeuille: PortfolioDetail | null
}

const POINTS = ['conditions', 'note', 'refus'] as const

export function VuePresentation({ liste, recharger, portefeuille }: Props) {
  const { langue, libelles } = useLangue()
  const l = libelles.presentation
  const pages = pagesApplication('presentation', portefeuille?.id ?? null, langue)

  return (
    <Cadre
      titre={libelles.navigation.pages.presentation}
      page={PAGE}
      entete={<BandeauSimple portefeuille={portefeuille?.name ?? null} />}
      rail={<RailPages pages={pages} />}
    >
      <AncresSections pages={pages} sections={false} />
      <h1 tabIndex={-1} className={communs.titre}>
        {l.titre}
      </h1>
      <p className={communs.texte}>{l.chapeau}</p>

      <section className={styles.partie}>
        <h2 className={styles.intertitre}>{l.demonstration.titre}</h2>
        <p className={communs.texte}>{l.demonstration.texte}</p>
        <TableauDesPortefeuilles liste={liste} recharger={recharger} />
      </section>

      <section className={styles.partie}>
        <h2 className={styles.intertitre}>{l.distingue.titre}</h2>
        {POINTS.map((point) => (
          <div key={point}>
            <h3 className={styles.attaque}>{l.distingue[point].attaque}</h3>
            <p className={communs.texte}>{l.distingue[point].texte}</p>
          </div>
        ))}
      </section>

      <section className={styles.partie}>
        <h2 className={styles.intertitre}>{l.resultat.titre}</h2>
        <p className={communs.texte}>{l.resultat.texte}</p>
        <div className={styles.resultat}>
          <BlocDuResultat />
        </div>
      </section>

      <section className={styles.partie}>
        <h2 className={styles.intertitre}>{l.construit.titre}</h2>
        <p className={communs.texte}>{l.construit.texte}</p>
      </section>

      <section className={styles.partie}>
        <h2 className={styles.intertitre}>{l.neMontrePas.titre}</h2>
        <p className={communs.texte}>{l.neMontrePas.texte}</p>
        <p className={communs.texte}>
          <a href={ADRESSES.installation}>{l.neMontrePas.installer}</a>
        </p>
      </section>

      <section className={styles.partie}>
        <h2 className={styles.intertitre}>{l.liens.titre}</h2>
        <ul className={styles.liens}>
          <li>
            <a href={ADRESSES.depot}>{l.liens.code}</a>
          </li>
          <li>
            <Lien vers={cheminDe({ vue: 'methodologie' })}>{l.liens.methodologie}</Lien>
          </li>
          <li>
            <a href={ADRESSES.methodologieTechnique}>{l.liens.methodologieTechnique}</a>
          </li>
          <li>
            <a href={ADRESSES.architecture}>{l.liens.architecture}</a>
          </li>
          <li>
            <Lien vers={cheminDe({ vue: 'avertissement' })}>{l.liens.avertissement}</Lien>
          </li>
        </ul>
        <p className={styles.auteur}>
          <span>{l.auteur}</span>
          <span className={styles.liensDeLAuteur}>
            <a href={ADRESSES.auteurSurGitHub}>{NOMS.gitHub}</a>
            <a href={ADRESSES.auteurSurLinkedIn}>{NOMS.linkedIn}</a>
          </span>
        </p>
      </section>
    </Cadre>
  )
}
