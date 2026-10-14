/**
 * L'import d'un fichier CSV — DESIGN.md §8.2, §13, §15.
 *
 * ═══ UN VRAI CHAMP DE FICHIER, ET UNE ZONE DE DÉPÔT AUTOUR ═══
 *
 * Le champ natif `<input type="file">` reste visible : il se prend au
 * clavier, il annonce son état, il ouvre le sélecteur du système. La zone
 * autour accepte en plus un fichier glissé, qui est alors confié au même
 * champ — un seul endroit tient le fichier choisi.
 *
 * ═══ RIEN N'EST ÉCRIT SANS CONFIRMATION ═══
 *
 * Choisir un fichier ne l'importe pas. La confirmation dit ce qui sera
 * REMPLACÉ — les positions actuelles, nommées par leur nombre —, et si le
 * tableau porte des modifications non enregistrées, qui seront perdues. Le
 * bouton dit le geste : « Importer le portefeuille ». Pas d'aperçu : l'API
 * n'a pas de lecture à blanc, l'import écrit (point ouvert, noté).
 *
 * ═══ CE QUI A ÉTÉ LU ═══
 *
 * Après un import, la provenance du fichier est affichée comme celle d'une
 * mesure : encodage, séparateur, décimale OBSERVÉE, lignes lues. Un fichier
 * « mixte » se voit, et un résultat inattendu se comprend au lieu de se subir.
 *
 * ═══ SUR LE SITE (chantier 9.6) ═══
 *
 * La page qui la monte dit où part le fichier (`envoyer`) : l'import en base
 * de l'application, ou la lecture par le serveur public, qui rend les lignes
 * sans rien garder. Sur le site (`serveur`), l'envoi attend d'abord que le
 * serveur réponde, et la zone dit où il en est (`EtatDuServeur`) ; un échec
 * qui n'est pas un refus du fichier se réessaie sur place.
 */
import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'

import { ApiErreur, estUnRefus, versApiErreur } from '../api/client'
import type { CsvSource } from '../api/types'
import { nomDecimale, nomEncodage } from '../lib/csv'
import { useLangue } from '../lib/langue'
import { cite } from '../lib/phrases'
import controles from '../styles/controles.module.css'
import { EtatDuServeur, type EtapeDuServeur } from './EtatDuServeur'
import { MessageErreur } from './MessageErreur'
import { Provenance } from './Provenance'
import styles from './DepotCsv.module.css'

/** Ce que rend la lecture d'un fichier, import en base ou lecture du serveur public : comment il a été lu. */
interface Lu {
  readonly source: CsvSource
}

interface Props<R extends Lu> {
  readonly nom: string
  /** Le nombre de positions gardées : ce que l'import remplace. */
  readonly positionsActuelles: number
  /** Le tableau porte des modifications non enregistrées. */
  readonly modifie: boolean
  /** L'envoi du fichier. `etape` dit où en est le serveur public, sur le site. */
  readonly envoyer: (fichier: File, etape: (etape: EtapeDuServeur) => void) => Promise<R>
  /** Après un import réussi : garder, annoncer, relire. */
  readonly importe: (resultat: R) => Promise<void>
  /** Sur le site : l'état du serveur pendant l'envoi, et « Réessayer » après un échec. */
  readonly serveur?: boolean
}

export function DepotCsv<R extends Lu>({
  nom,
  positionsActuelles,
  modifie,
  envoyer,
  importe,
  serveur = false,
}: Props<R>) {
  const { langue, libelles } = useLangue()
  const l = libelles.csv
  const champ = useRef<HTMLInputElement>(null)
  const [fichier, setFichier] = useState<File | null>(null)
  const [survol, setSurvol] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [etape, setEtape] = useState<EtapeDuServeur | null>(null)
  const [erreur, setErreur] = useState<ApiErreur | null>(null)
  const [resultat, setResultat] = useState<R | null>(null)
  const blocLu = useRef<HTMLDivElement>(null)
  const bouton = useRef<HTMLButtonElement>(null)

  // Le focus après l'envoi. Réussi, l'import retire son bouton : le focus va
  // à ce qui a été lu, juste en dessous. Refusé, le bouton reste mais a été
  // désactivé pendant l'envoi, ce qui lui a fait perdre le focus : il le
  // retrouve. Dans les deux cas, la tabulation ne repart pas du haut de la
  // page. Un effet, et non un appel direct : l'élément visé n'existe, ou
  // n'est réactivé, qu'au rendu qui suit.
  const [cibleDuFocus, setCibleDuFocus] = useState<{ cible: 'lu' | 'bouton' } | null>(null)
  useEffect(() => {
    if (cibleDuFocus === null) return
    const noeud = cibleDuFocus.cible === 'lu' ? blocLu.current : bouton.current
    noeud?.focus()
  }, [cibleDuFocus])

  const choisir = (choisi: File | null) => {
    setFichier(choisi)
    setErreur(null)
    setResultat(null)
  }

  const deposer = (evenement: DragEvent<HTMLDivElement>) => {
    evenement.preventDefault()
    setSurvol(false)
    const fichiers = evenement.dataTransfer.files
    const depose = fichiers[0]
    if (depose === undefined) return
    // Le fichier glissé est confié au champ lui-même : il l'affiche, et il
    // reste la seule source du fichier choisi.
    if (champ.current !== null) champ.current.files = fichiers
    choisir(depose)
  }

  const importer = async () => {
    if (fichier === null) return
    setEnCours(true)
    setEtape(null)
    setErreur(null)
    try {
      const lu = await envoyer(fichier, setEtape)
      setResultat(lu)
      setFichier(null)
      if (champ.current !== null) champ.current.value = ''
      await importe(lu)
      setCibleDuFocus({ cible: 'lu' })
    } catch (cause) {
      setErreur(versApiErreur(cause, langue))
      setCibleDuFocus({ cible: 'bouton' })
    } finally {
      setEnCours(false)
      setEtape(null)
    }
  }

  const soumettre = (evenement: FormEvent<HTMLFormElement>) => {
    evenement.preventDefault()
    void importer()
  }

  return (
    <form className={styles.formulaire} onSubmit={soumettre}>
      <div
        className={survol ? `${styles.zone} ${styles.survol}` : styles.zone}
        onDragOver={(e) => {
          e.preventDefault()
          setSurvol(true)
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={deposer}
      >
        <p className={styles.consigne}>{l.deposer}</p>
        <label htmlFor="fichier-csv" className={controles.libelle}>
          {l.fichierCsv}
        </label>
        <input
          ref={champ}
          id="fichier-csv"
          name="fichier"
          type="file"
          accept=".csv,text/csv,text/plain"
          className={styles.champ}
          onChange={(e) => choisir(e.target.files?.[0] ?? null)}
        />
        {fichier !== null && (
          <p className={controles.aide}>{l.fichierChoisi(fichier.name, fichier.size)}</p>
        )}
      </div>

      {fichier !== null && (
        <div className={styles.confirmation}>
          <p className={styles.question}>
            {positionsActuelles === 0 ? l.donne(nom) : l.remplace(positionsActuelles, nom)}
            {modifie && l.modificationsPerdues}
          </p>
          <div className={controles.groupe}>
            <button
              ref={bouton}
              type="submit"
              className={`${controles.bouton} ${controles.principal}`}
              disabled={enCours}
            >
              {enCours ? l.importEnCours : l.importer}
            </button>
          </div>
          {serveur && enCours && <EtatDuServeur etape={etape} />}
        </div>
      )}

      {erreur !== null && (
        <MessageErreur
          erreur={erreur}
          action={
            serveur && !estUnRefus(erreur) && fichier !== null ? (
              <button
                type="button"
                className={controles.bouton}
                disabled={enCours}
                onClick={() => void importer()}
              >
                {libelles.serveur.reessayer}
              </button>
            ) : undefined
          }
        />
      )}

      {resultat !== null && (
        <div ref={blocLu} tabIndex={-1} className={styles.lu}>
          <p className={styles.consigne}>{l.lu}</p>
          <Provenance
            lignes={[
              { libelle: l.fichier, valeur: resultat.source.filename ?? l.sansNom },
              { libelle: l.encodage, valeur: nomEncodage(resultat.source.encoding, langue) },
              { libelle: l.separateur, valeur: cite(resultat.source.delimiter, langue) },
              {
                libelle: l.decimale,
                valeur: nomDecimale(resultat.source.decimal_separator, langue),
              },
              { libelle: l.lignesLues, valeur: l.lignes(resultat.source.rows_read) },
            ]}
          />
        </div>
      )}
    </form>
  )
}
