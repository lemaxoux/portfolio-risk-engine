/**
 * La page « Portefeuilles » — choisir, créer, supprimer. DESIGN.md §8.2, §13.
 *
 * ═══ POURQUOI UNE PAGE, ET PAS UN MENU DANS LE BANDEAU ═══
 *
 * Un menu déroulant qui change de page à la sélection déplace l'utilisateur
 * au moindre coup de flèche (WCAG 3.2.2). Une page de liens, elle, ne bouge
 * que sur un clic délibéré, et elle a la place de dire ce que le menu tairait :
 * la valeur de chaque portefeuille, sa date, et pourquoi un portefeuille ne se
 * valorise pas.
 *
 * ═══ LA SUPPRESSION SE CONFIRME SUR PLACE ═══
 *
 * Pas de modale : §15 préfère ce qu'on traverse délibérément à ce qu'on
 * clique sans lire. La question apparaît sous le tableau, reçoit le focus, et
 * dit ce qui disparaît avec le portefeuille : ses positions. « Annuler » rend
 * le focus au bouton d'où l'on venait.
 *
 * ═══ AUCUN CALCUL ═══
 *
 * La colonne « Lignes » compte les positions PUBLIÉES par l'API ; la valeur,
 * la date et la raison d'une valorisation impossible sont des champs publiés.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react'

import {
  ApiErreur,
  createPortfolio,
  deletePortfolio,
  versApiErreur,
} from '../api/client'
import type { PortfolioDetail } from '../api/types'
import { Absent } from '../components/Absent'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { DataTable, type Colonne } from '../components/DataTable'
import { FormatCsv } from '../components/FormatCsv'
import { Lien } from '../components/Lien'
import { MessageErreur } from '../components/MessageErreur'
import { AncresSections, pagesApplication, RailPages } from '../components/Navigation'
import { SqueletteTableau } from '../components/Squelette'
import { dateISO, decimal, montant, TIRET_INDEFINI } from '../lib/format'
import { useLangue } from '../lib/langue'
import type { EtatListe } from '../lib/liste'
import { cheminDe, naviguer, oublierPortefeuille } from '../lib/route'
import controles from '../styles/controles.module.css'
import styles from './Pages.module.css'

interface Props {
  readonly liste: EtatListe
  readonly recharger: () => Promise<void>
  readonly annonce: string | null
  readonly annoncer: (texte: string, page: string) => void
}

const PAGE = cheminDe({ vue: 'portefeuilles' })

export function VuePortefeuilles({ liste, recharger, annonce, annoncer }: Props) {
  const { langue, libelles } = useLangue()
  // Aucun portefeuille n'est en vue ici : ni analyse, ni saisie.
  const PAGES = pagesApplication('portefeuilles', null, langue)
  return (
    <Cadre
      titre={libelles.portefeuilles.titre}
      page={PAGE}
      annonce={annonce}
      occupe={liste.phase === 'chargement'}
      entete={<BandeauSimple portefeuille={null} navigation={false} />}
      rail={<RailPages pages={PAGES} />}
    >
      <AncresSections pages={PAGES} sections={false} />
      <h1 tabIndex={-1} className={styles.titre}>
        {libelles.portefeuilles.titre}
      </h1>
      {liste.phase === 'chargement' && <SqueletteTableau />}
      {liste.phase === 'erreur' && (
        <MessageErreur
          erreur={liste.erreur}
          action={
            <button type="button" className={controles.bouton} onClick={() => void recharger()}>
              {libelles.application.rechargerLaListe}
            </button>
          }
        />
      )}
      {liste.phase === 'prete' &&
        (liste.portefeuilles.length === 0 ? (
          <AucunPortefeuille recharger={recharger} annoncer={annoncer} />
        ) : (
          <Liste
            portefeuilles={liste.portefeuilles}
            recharger={recharger}
            annoncer={annoncer}
          />
        ))}
    </Cadre>
  )
}

/**
 * État VIDE — aucun portefeuille en base : une invitation à agir (§13). La
 * création vient d'abord ; les positions se saisissent ensuite, sur la page
 * du portefeuille créé.
 */
function AucunPortefeuille({
  recharger,
  annoncer,
}: Pick<Props, 'recharger' | 'annoncer'>) {
  const { libelles } = useLangue()
  const l = libelles.portefeuilles
  return (
    <div className={styles.vide}>
      <p className={styles.texte}>{l.aucun}</p>
      <Creation recharger={recharger} annoncer={annoncer} titre={l.creerUn} />
      <p className={`${styles.texte} ${styles.suite}`}>{l.suiteDeLaCreation}</p>
      <FormatCsv niveau={2} />
    </div>
  )
}

function Liste({
  portefeuilles,
  recharger,
  annoncer,
}: {
  portefeuilles: readonly PortfolioDetail[]
} & Pick<Props, 'recharger' | 'annoncer'>) {
  const { langue, libelles } = useLangue()
  const l = libelles.portefeuilles
  const [aSupprimer, setASupprimer] = useState<PortfolioDetail | null>(null)
  const origine = useRef<HTMLElement | null>(null)

  const demander = (portefeuille: PortfolioDetail) => {
    origine.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setASupprimer(portefeuille)
  }

  const annuler = () => {
    setASupprimer(null)
    origine.current?.focus()
  }

  const colonnes: Colonne<PortfolioDetail>[] = [
    {
      cle: 'nom',
      titre: l.colonnes.nom,
      nature: 'texte',
      cellule: (p) => (
        <>
          <Lien vers={cheminDe({ vue: 'analyse', id: p.id })}>{p.name}</Lien>
          <EtatDuPortefeuille portefeuille={p} />
        </>
      ),
    },
    {
      cle: 'lignes',
      titre: l.colonnes.lignes,
      nature: 'nombre',
      cellule: (p) => decimal(p.positions.length, 0, langue),
    },
    {
      cle: 'valeur',
      titre: l.colonnes.valeur,
      nature: 'nombre',
      cellule: (p) =>
        p.valuation === null
          ? TIRET_INDEFINI
          : montant(p.valuation.total_value, p.valuation.currency, langue),
    },
    {
      cle: 'valorise',
      titre: l.colonnes.valorise,
      nature: 'texte',
      cellule: (p) => (
        <span className={styles.date}>
          {p.valuation === null ? <Absent /> : dateISO(p.valuation.as_of)}
        </span>
      ),
    },
    {
      cle: 'modifie',
      titre: l.colonnes.modifie,
      nature: 'texte',
      cellule: (p) => (
        <span className={styles.date}>
          {p.updated_at === null ? l.jamais : dateISO(p.updated_at)}
        </span>
      ),
    },
    {
      cle: 'actions',
      titre: l.colonnes.actions,
      nature: 'texte',
      cellule: (p) => (
        <span className={styles.actions}>
          <Lien vers={cheminDe({ vue: 'positions', id: p.id })}>
            {l.positionsDe}
            <span className="visuellement-cache">{l.deNom(p.name)}</span>
          </Lien>
          {/* Jamais désactivé pendant une confirmation : « Annuler » doit
              pouvoir lui rendre le focus, et en choisir un autre change
              simplement la question. */}
          <button type="button" className={controles.discret} onClick={() => demander(p)}>
            {l.supprimer}
            <span className="visuellement-cache">{l.nomCite(p.name)}</span>
          </button>
        </span>
      ),
    },
  ]

  return (
    <>
      <p className={styles.texte}>{l.chacun}</p>
      <DataTable
        legende={l.legende}
        colonnes={colonnes}
        lignes={portefeuilles}
        cleDeLigne={(p) => String(p.id)}
      />
      {aSupprimer !== null && (
        <ConfirmationSuppression
          portefeuille={aSupprimer}
          annuler={annuler}
          supprime={async () => {
            oublierPortefeuille(aSupprimer.id)
            annoncer(l.supprime(aSupprimer.name), PAGE)
            setASupprimer(null)
            await recharger()
            // La question a disparu avec la ligne : le focus revient au
            // titre de la page plutôt que de tomber au début du document.
            document.querySelector<HTMLElement>('main h1[tabindex="-1"]')?.focus()
          }}
        />
      )}
      <Creation recharger={recharger} annoncer={annoncer} titre={l.nouveau} />
    </>
  )
}

/**
 * Ce que la liste sait d'un portefeuille qui ne s'analyse pas : vide, ou non
 * valorisable — et alors la raison du moteur, telle quelle.
 */
function EtatDuPortefeuille({ portefeuille }: { portefeuille: PortfolioDetail }) {
  const { libelles } = useLangue()
  if (portefeuille.positions.length === 0) {
    return <span className={styles.etat}>{libelles.portefeuilles.aucunePosition}</span>
  }
  if (portefeuille.valuation === null) {
    return (
      <span className={styles.etat}>
        {libelles.portefeuilles.nonValorise(portefeuille.valuation_error)}
      </span>
    )
  }
  return null
}

function ConfirmationSuppression({
  portefeuille,
  annuler,
  supprime,
}: {
  portefeuille: PortfolioDetail
  annuler: () => void
  supprime: () => Promise<void>
}) {
  const { langue, libelles } = useLangue()
  const l = libelles.portefeuilles
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState<ApiErreur | null>(null)
  const question = useRef<HTMLParagraphElement>(null)
  const nombre = portefeuille.positions.length

  // Au premier affichage seulement : la question reçoit le focus, pour être
  // lue, puis la tabulation mène aux deux boutons.
  useEffect(() => {
    question.current?.focus()
  }, [])

  const confirmer = async () => {
    setEnCours(true)
    setErreur(null)
    try {
      await deletePortfolio(portefeuille.id, langue)
      await supprime()
    } catch (cause) {
      setErreur(versApiErreur(cause, langue))
      setEnCours(false)
    }
  }

  return (
    <div className={styles.confirmation}>
      <p className={styles.question} tabIndex={-1} ref={question}>
        {l.question(portefeuille.name, nombre)}
      </p>
      {erreur !== null && <MessageErreur erreur={erreur} />}
      <div className={controles.groupe}>
        <button
          type="button"
          className={`${controles.bouton} ${controles.principal}`}
          onClick={() => void confirmer()}
          disabled={enCours}
        >
          {enCours ? l.suppressionEnCours : l.supprimerDefinitivement}
        </button>
        <button type="button" className={controles.bouton} onClick={annuler} disabled={enCours}>
          {l.annuler}
        </button>
      </div>
    </div>
  )
}

/**
 * La création est EXPLICITE : un nom, puis le portefeuille existe, vide. Le
 * geste garde son nom du bouton au message : « Créer le portefeuille »,
 * « Portefeuille « … » créé. » (§15).
 */
function Creation({
  recharger,
  annoncer,
  titre,
}: Pick<Props, 'recharger' | 'annoncer'> & { titre: string }) {
  const { langue, libelles } = useLangue()
  const l = libelles.portefeuilles
  const [nom, setNom] = useState('')
  const [refus, setRefus] = useState<string | null>(null)
  const [erreur, setErreur] = useState<ApiErreur | null>(null)
  const [enCours, setEnCours] = useState(false)
  const champ = useRef<HTMLInputElement>(null)
  // Un refus porte le focus au champ, après le rendu qui le relie au champ
  // (`aria-describedby`) : un lecteur d'écran lit alors le champ ET son refus.
  // Le focus restait sur le bouton, et le refus n'était annoncé nulle part
  // (chantier 7E).
  const [refusAFocaliser, setRefusAFocaliser] = useState(0)
  useEffect(() => {
    if (refusAFocaliser > 0) champ.current?.focus()
  }, [refusAFocaliser])

  const creer = async (evenement: FormEvent<HTMLFormElement>) => {
    evenement.preventDefault()
    const propre = nom.trim()
    if (propre.length === 0) {
      setRefus(l.nomVide)
      setRefusAFocaliser((n) => n + 1)
      return
    }
    setEnCours(true)
    setErreur(null)
    try {
      const cree = await createPortfolio(propre, langue)
      // Un portefeuille créé est vide : on arrive là où il se remplit.
      const destination = cheminDe({ vue: 'positions', id: cree.id })
      annoncer(l.cree(cree.name), destination)
      await recharger()
      naviguer(destination)
    } catch (cause) {
      setErreur(versApiErreur(cause, langue))
      setEnCours(false)
    }
  }

  return (
    <form className={styles.formulaire} onSubmit={(e) => void creer(e)} noValidate>
      <h2 className={styles.sousTitre}>{titre}</h2>
      <div className={controles.champ}>
        <label htmlFor="nom-portefeuille" className={controles.libelle}>
          {l.nom}
        </label>
        <p id="nom-portefeuille-aide" className={controles.aide}>
          {l.aideNom}
        </p>
        <input
          ref={champ}
          id="nom-portefeuille"
          name="nom"
          className={controles.saisie}
          value={nom}
          maxLength={120}
          autoComplete="off"
          aria-invalid={refus !== null ? true : undefined}
          aria-describedby={
            refus !== null ? 'nom-portefeuille-aide nom-portefeuille-refus' : 'nom-portefeuille-aide'
          }
          onChange={(e) => {
            setNom(e.target.value)
            setRefus(null)
          }}
        />
        {refus !== null && (
          <p id="nom-portefeuille-refus" className={controles.refus}>
            {refus}
          </p>
        )}
      </div>
      <button
        type="submit"
        className={`${controles.bouton} ${controles.principal}`}
        disabled={enCours}
      >
        {enCours ? l.creationEnCours : l.creer}
      </button>
      {erreur !== null && <MessageErreur erreur={erreur} />}
    </form>
  )
}
