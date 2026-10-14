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
 *
 * ═══ LA MÊME PAGE SUR LE SITE (chantier 9.6) ═══
 *
 * Le site a sa saisie : celle du portefeuille du visiteur, que le serveur
 * public analyse sans rien garder. La page est la même (`PageDesPositions`),
 * le tableau, la zone de dépôt et le format aussi ; ce qui change lui est
 * donné par qui la monte : où elle lit les positions, ce que fait son bouton,
 * où part le fichier, et les phrases qui le disent. Dans l'application, rien
 * ne change à l'écran.
 *
 * Sur le site, « Analyser ces positions » est le seul geste qui garde :
 * refusé, rien n'est gardé ; accepté, les lignes sont gardées dans ce
 * navigateur avec la date du jour, et l'analyse s'ouvre, avec la réponse même
 * de l'envoi. Un fichier lu par le serveur est gardé de même, et le tableau
 * repart de lui. Pendant un envoi, la page dit où en est le serveur
 * (`EtatDuServeur`), sans saut de mise en page.
 */
import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'

import {
  analyserLeSaisi,
  ApiErreur,
  attendreLeServeur,
  estUnRefus,
  importCsv,
  lireUnFichier,
  putPositions,
  versApiErreur,
} from '../api/client'
import type { CsvSource, PortfolioDetail, Position, PositionIn } from '../api/types'
import { BandeauSimple } from '../components/Bandeau'
import { Cadre } from '../components/Cadre'
import { DepotCsv } from '../components/DepotCsv'
import { EtatDuServeur, type EtapeDuServeur } from '../components/EtatDuServeur'
import { FormatCsv } from '../components/FormatCsv'
import { MessageErreur, Segments } from '../components/MessageErreur'
import {
  AncresSections,
  pagesApplication,
  RailPages,
  type PageApplication,
} from '../components/Navigation'
import { cleDeRefus, TableauSaisie } from '../components/TableauSaisie'
import type { PreuveDAcceptation } from '../lib/acceptation'
import { rangeeApresRetrait } from '../lib/focus'
import { useLangue } from '../lib/langue'
import { messageDeLigne } from '../lib/phrases'
import {
  cheminDe,
  memoriserLeSaisi,
  memoriserPortefeuille,
  naviguer,
  poserGarde,
  SAISI,
} from '../lib/route'
import { deposerLAnalyse, garderLeSaisi, lireLeSaisi, stockageDisponible } from '../lib/saisi'
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

type Saisissable = 'ticker' | 'quantite' | 'prixRevient'

/**
 * Le départ que la garde a retenu : un lien suivi (`cible`), ou la page
 * remplacée sur place par l'écran d'acceptation d'une autre langue (`suite`).
 */
interface Depart {
  readonly cible: string
  readonly suite: (() => void) | undefined
}

/** Ce qui se dit autrement sur le site, où le tableau ne s'enregistre nulle part. */
interface TextesDeLaPage {
  readonly tableauEstLePortefeuille: string
  readonly universIllisible: (detail: string) => string
  readonly rien: string
  readonly enCours: string
  readonly bouton: string
  readonly nonGardees: string
  readonly quitterLesPerd: string
  readonly quitter: string
}

/** Ce que la page reçoit de qui la monte : l'application, ou le site. */
interface Usage {
  readonly nom: string
  readonly page: string
  readonly pages: readonly PageApplication[]
  readonly devise: string
  /** Les positions gardées, en base ou dans ce navigateur : le tableau s'ouvre sur elles. */
  readonly gardees: readonly Position[]
  readonly textes: TextesDeLaPage
  readonly annonce: string | null
  /**
   * L'envoi du tableau, une fois les nombres lus : l'enregistrement, ou
   * l'analyse. Lève une `ApiErreur` en cas de refus. `etape` dit où en est
   * le serveur public, sur le site.
   */
  readonly envoyer: (positions: PositionIn[], etape: (etape: EtapeDuServeur) => void) => Promise<void>
  /** Sur le site : l'état du serveur pendant l'envoi, et « Réessayer » après un échec. */
  readonly serveur: boolean
  /** Sous le premier paragraphe : ce que le site dit de plus. */
  readonly apresLeTexte?: ReactNode
  /** Au-dessus du bouton, sous les refus : ce que le site dit de l'envoi. */
  readonly avantLeBouton?: ReactNode
  /** La zone de dépôt, qui sait si le tableau porte des modifications. */
  readonly depot: (modifie: boolean) => ReactNode
}

// ════════════════════════════════════════════════════════ L'application ══

interface Props {
  readonly portefeuille: PortfolioDetail
  readonly recharger: () => Promise<void>
  readonly annonce: string | null
  readonly annoncer: (texte: string, page: string) => void
}

export function VuePositions({ portefeuille, recharger, annonce, annoncer }: Props) {
  const nom = portefeuille.name
  const page = cheminDe({ vue: 'positions', id: portefeuille.id })
  const { langue, libelles } = useLangue()
  const l = libelles.positions

  useEffect(() => {
    memoriserPortefeuille(portefeuille.id)
  }, [portefeuille.id])

  return (
    <PageDesPositions
      nom={nom}
      page={page}
      pages={pagesApplication('positions', portefeuille.id, langue)}
      devise={portefeuille.valuation?.currency ?? 'USD'}
      gardees={portefeuille.positions}
      textes={{
        tableauEstLePortefeuille: l.tableauEstLePortefeuille,
        universIllisible: l.universIllisible,
        rien: l.rienEnregistre,
        enCours: l.enregistrementEnCours,
        bouton: l.enregistrer,
        nonGardees: l.nonEnregistrees,
        quitterLesPerd: l.quitterLesPerd,
        quitter: l.quitter,
      }}
      annonce={annonce}
      serveur={false}
      envoyer={async (positions) => {
        const ecrit = await putPositions(portefeuille.id, positions, langue)
        annoncer(l.enregistrees(ecrit.updated_at, ecrit.positions_count), page)
        await recharger()
      }}
      depot={(modifie) => (
        <DepotCsv
          nom={nom}
          positionsActuelles={portefeuille.positions.length}
          modifie={modifie}
          envoyer={(fichier) => importCsv(portefeuille.id, fichier, langue)}
          importe={async (lu) => {
            annoncer(l.importe(lu.source.filename, lu.positions_count), page)
            await recharger()
          }}
        />
      )}
    />
  )
}

// ═══════════════════════════════════════════════════════════════ Le site ══

interface PropsDuSaisi {
  /** La preuve que le texte d'acceptation de la langue a été accepté : sans elle, rien ne part. */
  readonly preuve: PreuveDAcceptation
  readonly annonce: string | null
  readonly annoncer: (texte: string, page: string) => void
}

/** Un fichier lu par le serveur public : ses lignes, et comment il a été lu. */
interface FichierLu {
  readonly positions: readonly Position[]
  readonly source: CsvSource
}

/**
 * La page des positions du portefeuille saisi, sur le site. Le portefeuille
 * gardé dans ce navigateur ouvre le tableau ; analyser l'envoie au serveur
 * public, et l'analyse s'ouvre avec sa réponse.
 */
export function VuePositionsDuSaisi({ preuve, annonce, annoncer }: PropsDuSaisi) {
  const { langue, libelles } = useLangue()
  const l = libelles.positions
  const s = libelles.positionsDuSite
  const nom = libelles.saisi.nom
  const page = cheminDe({ vue: 'saisi-positions' })
  const [saisi, setSaisi] = useState(lireLeSaisi)
  const [stockage] = useState(stockageDisponible)
  const gardees = saisi?.positions ?? []

  useEffect(() => {
    memoriserLeSaisi()
  }, [])

  /** Attend le serveur, puis lui fait faire `envoi` : l'état suit chaque étape. */
  const parLeServeur = async <T,>(
    envoi: () => Promise<T>,
    etape: (etape: EtapeDuServeur) => void,
  ): Promise<T> => {
    await attendreLeServeur(langue, () => etape('reveil'))
    etape('calcul')
    return envoi()
  }

  return (
    <PageDesPositions
      nom={nom}
      page={page}
      pages={pagesApplication('positions', SAISI, langue)}
      // Comme l'application pour un portefeuille sans valorisation.
      devise="USD"
      gardees={gardees}
      textes={{
        tableauEstLePortefeuille: s.tableauEstLePortefeuille,
        universIllisible: s.universIllisible,
        rien: s.rienGarde,
        enCours: s.analyseEnCours,
        bouton: s.analyser,
        nonGardees: s.nonGardees,
        quitterLesPerd: s.quitterLesPerd,
        quitter: s.quitter,
      }}
      annonce={annonce}
      serveur
      apresLeTexte={
        <>
          <p className={styles.texte}>{s.listeFermee}</p>
          {!stockage && <p className={styles.texte}>{s.stockageBloque}</p>}
        </>
      }
      avantLeBouton={<p className={controles.aide}>{s.envoi}</p>}
      envoyer={async (positions, etape) => {
        const analyse = await parLeServeur(
          () => analyserLeSaisi(positions, langue, preuve),
          etape,
        )
        // Acceptées : les lignes sont gardées, datées du jour, et l'analyse
        // que la page suivante affiche est cette réponse même.
        const garde = garderLeSaisi(positions)
        deposerLAnalyse(garde.positions, langue, analyse)
        setSaisi(garde)
        const analyseDuSaisi = cheminDe({ vue: 'saisi' })
        annoncer(s.gardees(garde.modifie, garde.positions.length), analyseDuSaisi)
        // Le tableau est gardé : le quitter ne perd plus rien.
        naviguer(analyseDuSaisi, { forcer: true })
      }}
      depot={(modifie) => (
        <>
          <p className={controles.aide}>{s.fichierEnvoye}</p>
          <DepotCsv<FichierLu>
            nom={nom}
            positionsActuelles={gardees.length}
            modifie={modifie}
            serveur
            envoyer={(fichier, etape) =>
              parLeServeur(() => lireUnFichier(fichier, langue, preuve), etape)
            }
            importe={async (lu) => {
              setSaisi(garderLeSaisi(lu.positions))
              annoncer(l.importe(lu.source.filename, lu.positions.length), page)
            }}
          />
        </>
      )}
    />
  )
}

// ═════════════════════════════════════════════════════════ La page même ══

function PageDesPositions({
  nom,
  page,
  pages,
  devise,
  gardees,
  textes,
  annonce,
  envoyer,
  serveur,
  apresLeTexte,
  avantLeBouton,
  depot,
}: Usage) {
  const { langue, libelles } = useLangue()
  const l = libelles.positions
  const { univers, erreur: erreurUnivers } = useUnivers(langue)

  // Les positions gardées, par leur CONTENU : une liste relue à l'identique
  // ne réinitialise pas le tableau.
  const stockees = JSON.stringify(gardees)
  const initiales = useMemo(() => lignesDepuisPositions(JSON.parse(stockees) as Position[]), [stockees])
  const [lignes, setLignes] = useState<LigneSaisie[]>(initiales)
  const [refusLocaux, setRefusLocaux] = useState<RefusDeCellule[]>([])
  const [refusServeur, setRefusServeur] = useState<RefusDeCellule[]>([])
  const [generaux, setGeneraux] = useState<string[]>([])
  const [erreur, setErreur] = useState<ApiErreur | null>(null)
  const [enCours, setEnCours] = useState(false)
  const [etape, setEtape] = useState<EtapeDuServeur | null>(null)
  const [sortie, setSortie] = useState<Depart | null>(null)
  // Ce qui avait le focus quand la garde a retenu le départ : le lien suivi,
  // le bouton de langue. « Rester sur la page » le lui rend (chantier 7E).
  const origineDuDepart = useRef<HTMLElement | null>(null)
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

  // Après un enregistrement ou un import, les positions gardées reviennent :
  // le tableau repart d'elles.
  useEffect(() => {
    setLignes(initiales)
    setRefusLocaux([])
    setRefusServeur([])
    setGeneraux([])
  }, [initiales])

  const modifie = empreinteDesLignes(lignes) !== empreinteDesLignes(initiales)

  useEffect(() => {
    if (!modifie) return
    const avertir = (evenement: BeforeUnloadEvent) => {
      evenement.preventDefault()
      evenement.returnValue = ''
    }
    window.addEventListener('beforeunload', avertir)
    const retirerGarde = poserGarde((cible, suite) => {
      origineDuDepart.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null
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
    const refusLocal = preparerEnvoi([ligne], langue).refus.find((r) => r.champ === CHAMP_DE[champ])
    if (refusLocal === undefined) return
    setRefusLocaux((liste) => [
      ...liste.filter((r) => !(r.ligne === rang + 1 && r.champ === refusLocal.champ)),
      { ...refusLocal, ligne: rang + 1 },
    ])
  }

  const retirer = (rang: number) => {
    const reste = lignes.filter((_, i) => i !== rang)
    const nouvelles = reste.length === 0 ? [ligneVide()] : reste
    setLignes(nouvelles)
    // Les numéros changent : les refus rangés par numéro ne valent plus.
    setRefusLocaux([])
    setRefusServeur([])
    // Le bouton a disparu avec sa rangée : le focus va au ticker de celle qui
    // prend sa place, plutôt que de tomber au début du document (7E).
    const suivante = nouvelles[rangeeApresRetrait(rang, lignes.length)]
    if (suivante !== undefined) setCibleDuFocus({ id: `ticker-${suivante.cle}` })
  }

  /** « Rester sur la page » : le focus revient à ce qui l'avait, sinon au titre. */
  const rester = () => {
    setSortie(null)
    const origine = origineDuDepart.current
    if (origine !== null && origine.isConnected) origine.focus()
    else document.querySelector<HTMLElement>('main h1[tabindex="-1"]')?.focus()
  }

  const ajouter = () => {
    const nouvelle = ligneVide()
    setLignes((liste) => [...liste, nouvelle])
    setCibleDuFocus({ id: `ticker-${nouvelle.cle}` })
  }

  const montrerResume = () => setCibleDuFocus({ id: 'resume' })

  const envoyerLeTableau = async () => {
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
    setEtape(null)
    try {
      await envoyer(positions, setEtape)
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
      setEtape(null)
    }
  }

  const soumettre = (evenement: FormEvent<HTMLFormElement>) => {
    evenement.preventDefault()
    void envoyerLeTableau()
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
          textes={textes}
          quitter={() =>
            sortie.suite !== undefined ? sortie.suite() : naviguer(sortie.cible, { forcer: true })
          }
          rester={rester}
        />
      )}

      <p className={styles.texte}>
        {gardees.length === 0 ? l.aucune(nom) : textes.tableauEstLePortefeuille}
      </p>
      {apresLeTexte}

      <form className={styles.saisie} onSubmit={soumettre} noValidate>
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
          <p className={controles.aide}>{textes.universIllisible(erreurUnivers.detail)}</p>
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
              <MessageErreur
                erreur={erreur}
                action={
                  serveur && !estUnRefus(erreur) ? (
                    <button
                      type="button"
                      className={controles.bouton}
                      disabled={enCours}
                      onClick={() => void envoyerLeTableau()}
                    >
                      {libelles.serveur.reessayer}
                    </button>
                  ) : undefined
                }
              />
            ) : (
              <>
                <p className={styles.question}>
                  {textes.rien}
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

        {avantLeBouton}
        <div className={controles.groupe}>
          <button
            id="enregistrer-positions"
            type="submit"
            className={`${controles.bouton} ${controles.principal}`}
            disabled={enCours}
          >
            {enCours ? textes.enCours : textes.bouton}
          </button>
          {modifie && <span className={controles.aide}>{textes.nonGardees}</span>}
        </div>
        {serveur && enCours && <EtatDuServeur etape={etape} />}
      </form>

      <h2 className={styles.sousTitre}>{l.importer}</h2>
      {depot(modifie)}
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
function ConfirmationSortie({
  textes,
  quitter,
  rester,
}: {
  textes: TextesDeLaPage
  quitter: () => void
  rester: () => void
}) {
  const { libelles } = useLangue()
  const question = useRef<HTMLParagraphElement>(null)
  useEffect(() => {
    question.current?.focus()
  }, [])
  return (
    <div className={styles.confirmation}>
      <p ref={question} tabIndex={-1} className={styles.question}>
        {textes.quitterLesPerd}
      </p>
      <div className={controles.groupe}>
        <button type="button" className={`${controles.bouton} ${controles.principal}`} onClick={rester}>
          {libelles.positions.rester}
        </button>
        <button type="button" className={controles.bouton} onClick={quitter}>
          {textes.quitter}
        </button>
      </div>
    </div>
  )
}
