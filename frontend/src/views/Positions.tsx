/**
 * La page « Positions » — saisir et importer. DESIGN.md §8.2, §13, §15.
 *
 * ═══ LE TABLEAU EST LE PORTEFEUILLE ═══
 *
 * L'enregistrer remplace TOUTES les positions, comme le `PUT` qu'il envoie :
 * ce qui est à l'écran est ce qui sera en base. Il s'ouvre sur les positions
 * TELLES QUE STOCKÉES — prix de revient compris —, et se recharge sur elles
 * après chaque écriture.
 *
 * ═══ DES MODIFICATIONS NON ENREGISTRÉES NE SE PERDENT PAS SANS LE DIRE ═══
 *
 * Tant que le tableau diffère de ce qui est en base : l'avertissement natif du
 * navigateur à la fermeture ou au rechargement (`beforeunload`), et une garde
 * sur la navigation interne. La garde retient le lien et affiche sa question
 * SUR PLACE, en tête de page, focalisée — pas une boîte de dialogue.
 *
 * ═══ LES QUATRE ÉTATS ═══
 *
 * Vide : une ligne vierge et une invitation. Insuffisant : la colonne
 * « Historique depuis » montre, avant d'enregistrer, quelle ligne a un
 * historique court. En cours : le bouton dit ce qu'il fait et se désactive,
 * contre le double envoi. Erreur : chaque refus sous son champ, et leur liste
 * au-dessus du bouton ; une panne, par le message de l'API et sa suite.
 */
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'

import { ApiErreur, putPositions, versApiErreur } from '../api/client'
import type { PortfolioDetail } from '../api/types'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { MessageErreur, Segments } from '../components/MessageErreur'
import { AncresSections, pagesApplication, RailPages } from '../components/Navigation'
import { cleDeRefus, TableauSaisie } from '../components/TableauSaisie'
import { DepotCsv } from '../components/DepotCsv'
import { FormatCsv } from '../components/FormatCsv'
import { useLangue } from '../lib/langue'
import { messageDeLigne } from '../lib/phrases'
import { cheminDe, memoriserPortefeuille, naviguer, poserGarde } from '../lib/route'
import {
  empreinteDesLignes,
  lignesDepuisPositions,
  ligneVide,
  lireNombreSaisi,
  preparerEnvoi,
  rangerRefus,
  type Champ,
  type LigneSaisie,
  type RefusDeCellule,
} from '../lib/saisie'
import { useUnivers } from '../lib/univers'
import controles from '../styles/controles.module.css'
import styles from './Pages.module.css'

interface Props {
  readonly portefeuille: PortfolioDetail
  readonly recharger: () => Promise<void>
  readonly annonce: string | null
  readonly annoncer: (texte: string, page: string) => void
}

type Saisissable = 'ticker' | 'quantite' | 'prixRevient'

/**
 * Le départ que la garde a retenu : un lien suivi (`cible`), ou la page
 * remplacée sur place par l'écran d'acceptation d'une autre langue (`suite`).
 */
interface Depart {
  readonly cible: string
  readonly suite: (() => void) | undefined
}

export function VuePositions({ portefeuille, recharger, annonce, annoncer }: Props) {
  const nom = portefeuille.name
  const page = cheminDe({ vue: 'positions', id: portefeuille.id })
  const { langue, libelles } = useLangue()
  const l = libelles.positions
  const pages = pagesApplication('positions', portefeuille.id, langue)
  const devise = portefeuille.valuation?.currency ?? 'USD'
  const { univers, erreur: erreurUnivers } = useUnivers(langue)

  // Les positions stockées, par leur CONTENU : une liste relue à l'identique
  // ne réinitialise pas le tableau.
  const stockees = JSON.stringify(portefeuille.positions)
  const initiales = useMemo(
    () => lignesDepuisPositions(JSON.parse(stockees) as PortfolioDetail['positions']),
    [stockees],
  )
  const [lignes, setLignes] = useState<LigneSaisie[]>(initiales)
  const [refusLocaux, setRefusLocaux] = useState<RefusDeCellule[]>([])
  const [refusServeur, setRefusServeur] = useState<RefusDeCellule[]>([])
  const [generaux, setGeneraux] = useState<string[]>([])
  const [erreur, setErreur] = useState<ApiErreur | null>(null)
  const [enCours, setEnCours] = useState(false)
  const [sortie, setSortie] = useState<Depart | null>(null)
  const resume = useRef<HTMLDivElement>(null)

  // Le focus se pose APRÈS le rendu qui fait apparaître sa cible : la liste
  // des refus après un envoi, le ticker d'une ligne ajoutée.
  const [cibleDuFocus, setCibleDuFocus] = useState<{ id: string } | null>(null)
  useEffect(() => {
    if (cibleDuFocus === null) return
    const noeud =
      cibleDuFocus.id === 'resume' ? resume.current : document.getElementById(cibleDuFocus.id)
    noeud?.focus()
  }, [cibleDuFocus])

  // Après un enregistrement ou un import, la liste relue ramène les
  // positions en base : le tableau repart d'elles.
  useEffect(() => {
    setLignes(initiales)
    setRefusLocaux([])
    setRefusServeur([])
    setGeneraux([])
  }, [initiales])

  useEffect(() => {
    memoriserPortefeuille(portefeuille.id)
  }, [portefeuille.id])

  const modifie = empreinteDesLignes(lignes) !== empreinteDesLignes(initiales)

  useEffect(() => {
    if (!modifie) return
    const avertir = (evenement: BeforeUnloadEvent) => {
      evenement.preventDefault()
      evenement.returnValue = ''
    }
    window.addEventListener('beforeunload', avertir)
    const retirerGarde = poserGarde((cible, suite) => {
      setSortie({ cible, suite })
      return false
    })
    return () => {
      window.removeEventListener('beforeunload', avertir)
      retirerGarde()
    }
  }, [modifie])

  const refus = useMemo(() => {
    const carte = new Map<string, string>()
    for (const r of [...refusServeur, ...refusLocaux]) carte.set(cleDeRefus(r.ligne, r.champ), r.message)
    return carte
  }, [refusLocaux, refusServeur])

  const effacerRefus = (numero: number, champ: Champ) => {
    const garder = (r: RefusDeCellule) => !(r.ligne === numero && r.champ === champ)
    setRefusLocaux((liste) => liste.filter(garder))
    setRefusServeur((liste) => liste.filter(garder))
  }

  const modifier = (rang: number, champ: Saisissable, valeur: string) => {
    setLignes((liste) => liste.map((ligne, i) => (i === rang ? { ...ligne, [champ]: valeur } : ligne)))
    effacerRefus(rang + 1, CHAMP_DE[champ])
  }

  /** À la sortie d'un champ numérique : le nombre se lit-il ? */
  const quitter = (rang: number, champ: Saisissable) => {
    if (champ === 'ticker') return
    const ligne = lignes[rang]
    if (ligne === undefined) return
    const texte = ligne[champ].trim()
    if (texte === '' || lireNombreSaisi(texte) !== null) return
    const refusLocal = preparerEnvoi([ligne]).refus.find((r) => r.champ === CHAMP_DE[champ])
    if (refusLocal === undefined) return
    setRefusLocaux((liste) => [
      ...liste.filter((r) => !(r.ligne === rang + 1 && r.champ === refusLocal.champ)),
      { ...refusLocal, ligne: rang + 1 },
    ])
  }

  const retirer = (rang: number) => {
    setLignes((liste) => {
      const reste = liste.filter((_, i) => i !== rang)
      return reste.length === 0 ? [ligneVide()] : reste
    })
    // Les numéros changent : les refus rangés par numéro ne valent plus.
    setRefusLocaux([])
    setRefusServeur([])
  }

  const ajouter = () => {
    const nouvelle = ligneVide()
    setLignes((liste) => [...liste, nouvelle])
    setCibleDuFocus({ id: `ticker-${nouvelle.cle}` })
  }

  const montrerResume = () => setCibleDuFocus({ id: 'resume' })

  const enregistrer = async (evenement: FormEvent<HTMLFormElement>) => {
    evenement.preventDefault()
    setErreur(null)
    setRefusServeur([])
    setGeneraux([])
    const { positions, refus: locaux } = preparerEnvoi(lignes, langue)
    setRefusLocaux(locaux)
    if (locaux.length > 0) {
      montrerResume()
      return
    }
    setEnCours(true)
    try {
      const ecrit = await putPositions(portefeuille.id, positions, langue)
      annoncer(l.enregistrees(ecrit.updated_at, ecrit.positions_count), page)
      await recharger()
      // Désactivé pendant l'envoi, le bouton a perdu le focus : il le
      // retrouve, plutôt que de laisser la tabulation repartir du début.
      setCibleDuFocus({ id: 'enregistrer-positions' })
    } catch (cause) {
      const refusApi = versApiErreur(cause, langue)
      if (refusApi.statut === 422 && refusApi.problems.length > 0) {
        const ranges = rangerRefus(refusApi.problems)
        setRefusServeur(ranges.parCellule)
        setGeneraux(ranges.generaux)
      } else {
        setErreur(refusApi)
      }
      montrerResume()
    } finally {
      setEnCours(false)
    }
  }

  const tousLesRefus = [...refusServeur, ...refusLocaux].sort(
    (a, b) => a.ligne - b.ligne || a.champ.localeCompare(b.champ),
  )

  return (
    <Cadre
      titre={l.titre(nom)}
      page={page}
      annonce={annonce}
      entete={<BandeauSimple portefeuille={nom} />}
      rail={<RailPages pages={pages} />}
    >
      <AncresSections pages={pages} sections={false} />
      <h1 tabIndex={-1} className={styles.titre}>
        {l.titre(nom)}
      </h1>

      {sortie !== null && (
        <ConfirmationSortie
          quitter={() =>
            sortie.suite !== undefined ? sortie.suite() : naviguer(sortie.cible, { forcer: true })
          }
          rester={() => setSortie(null)}
        />
      )}

      <p className={styles.texte}>
        {portefeuille.positions.length === 0 ? l.aucune(nom) : l.tableauEstLePortefeuille}
      </p>

      <form className={styles.saisie} onSubmit={(e) => void enregistrer(e)} noValidate>
        <h2 className={styles.sousTitreProche}>{l.saisir}</h2>
        <TableauSaisie
          legende={l.legende(nom)}
          lignes={lignes}
          refus={refus}
          univers={univers}
          devise={devise}
          modifier={modifier}
          quitter={quitter}
          retirer={retirer}
        />
        <p className={controles.aide}>{l.aide}</p>
        {erreurUnivers !== null && (
          <p className={controles.aide}>{l.universIllisible(erreurUnivers.detail)}</p>
        )}
        <div>
          <button type="button" className={controles.bouton} onClick={ajouter}>
            {l.ajouter}
          </button>
        </div>

        {(tousLesRefus.length > 0 || generaux.length > 0 || erreur !== null) && (
          // `MessageErreur` porte déjà `role="alert"` : pas deux alertes
          // imbriquées pour une même panne.
          <div
            ref={resume}
            tabIndex={-1}
            className={styles.resume}
            role={erreur === null ? 'alert' : undefined}
          >
            {erreur !== null ? (
              <MessageErreur erreur={erreur} />
            ) : (
              <>
                <p className={styles.question}>
                  {l.rienEnregistre}
                  {tousLesRefus.length > 0
                    ? l.aCorriger(new Set(tousLesRefus.map((r) => r.ligne)).size)
                    : l.saisieRefusee}
                </p>
                <ul className={styles.refusListe}>
                  {generaux.map((texte) => (
                    <li key={texte}>
                      <Segments message={texte} />
                    </li>
                  ))}
                  {tousLesRefus.map((r) => (
                    <li key={cleDeRefus(r.ligne, r.champ)}>
                      <Segments message={messageDeLigne(r.ligne, r.message, langue)} />
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <div className={controles.groupe}>
          <button
            id="enregistrer-positions"
            type="submit"
            className={`${controles.bouton} ${controles.principal}`}
            disabled={enCours}
          >
            {enCours ? l.enregistrementEnCours : l.enregistrer}
          </button>
          {modifie && <span className={controles.aide}>{l.nonEnregistrees}</span>}
        </div>
      </form>

      <h2 className={styles.sousTitre}>{l.importer}</h2>
      <DepotCsv
        portefeuilleId={portefeuille.id}
        nom={nom}
        positionsActuelles={portefeuille.positions.length}
        modifie={modifie}
        importe={async (lu) => {
          annoncer(l.importe(lu.source.filename, lu.positions_count), page)
          await recharger()
        }}
      />
      <FormatCsv niveau={3} />
    </Cadre>
  )
}

const CHAMP_DE: Record<Saisissable, Champ> = {
  ticker: 'ticker',
  quantite: 'quantity',
  prixRevient: 'cost_basis',
}

/**
 * La question posée quand on quitte un tableau modifié : sur place, en tête
 * de page, focalisée. « Rester sur la page » ne perd rien ; « Quitter sans
 * enregistrer » suit le lien retenu.
 */
function ConfirmationSortie({ quitter, rester }: { quitter: () => void; rester: () => void }) {
  const { libelles } = useLangue()
  const l = libelles.positions
  const question = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    question.current?.focus()
  }, [])
  return (
    <div className={styles.confirmation}>
      <p ref={question} tabIndex={-1} className={styles.question}>
        {l.quitterLesPerd}
      </p>
      <div className={controles.groupe}>
        <button type="button" className={`${controles.bouton} ${controles.principal}`} onClick={rester}>
          {l.rester}
        </button>
        <button type="button" className={controles.bouton} onClick={quitter}>
          {l.quitter}
        </button>
      </div>
    </div>
  )
}
