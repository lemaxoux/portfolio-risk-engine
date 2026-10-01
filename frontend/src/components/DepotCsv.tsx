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
 */
import { useRef, useState, type DragEvent, type FormEvent } from 'react'

import { ApiErreur, importCsv, versApiErreur } from '../api/client'
import type { CsvImport } from '../api/types'
import { nomDecimale, nomEncodage } from '../lib/csv'
import { compte, lignes } from '../lib/format'
import { cite } from '../lib/phrases'
import controles from '../styles/controles.module.css'
import { MessageErreur } from './MessageErreur'
import { Provenance } from './Provenance'
import styles from './DepotCsv.module.css'

interface Props {
  readonly portefeuilleId: number
  readonly nom: string
  /** Le nombre de positions actuellement en base : ce que l'import remplace. */
  readonly positionsActuelles: number
  /** Le tableau porte des modifications non enregistrées. */
  readonly modifie: boolean
  /** Après un import réussi : annoncer, et relire la liste. */
  readonly importe: (resultat: CsvImport) => Promise<void>
}

export function DepotCsv({ portefeuilleId, nom, positionsActuelles, modifie, importe }: Props) {
  const champ = useRef<HTMLInputElement>(null)
  const [fichier, setFichier] = useState<File | null>(null)
  const [survol, setSurvol] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState<ApiErreur | null>(null)
  const [resultat, setResultat] = useState<CsvImport | null>(null)

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

  const importer = async (evenement: FormEvent<HTMLFormElement>) => {
    evenement.preventDefault()
    if (fichier === null) return
    setEnCours(true)
    setErreur(null)
    try {
      const lu = await importCsv(portefeuilleId, fichier)
      setResultat(lu)
      setFichier(null)
      if (champ.current !== null) champ.current.value = ''
      await importe(lu)
    } catch (cause) {
      setErreur(versApiErreur(cause))
    } finally {
      setEnCours(false)
    }
  }

  return (
    <form className={styles.formulaire} onSubmit={(e) => void importer(e)}>
      <div
        className={survol ? `${styles.zone} ${styles.survol}` : styles.zone}
        onDragOver={(e) => {
          e.preventDefault()
          setSurvol(true)
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={deposer}
      >
        <p className={styles.consigne}>Déposer un fichier CSV ici, ou le choisir :</p>
        <label htmlFor="fichier-csv" className={controles.libelle}>
          Fichier CSV
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
          <p className={controles.aide}>
            {fichier.name}, {compte(fichier.size, 'octet')}
          </p>
        )}
      </div>

      {fichier !== null && (
        <div className={styles.confirmation}>
          <p className={styles.question}>
            {positionsActuelles === 0
              ? `L'import donne à ${cite(nom)}, encore vide, les positions du fichier.`
              : `L'import remplace les ${lignes(positionsActuelles)} actuelles de ${cite(nom)} par celles du fichier.`}
            {modifie && ' Les modifications non enregistrées du tableau seront perdues.'}
          </p>
          <div className={controles.groupe}>
            <button
              type="submit"
              className={`${controles.bouton} ${controles.principal}`}
              disabled={enCours}
            >
              {enCours ? 'Import en cours…' : 'Importer le portefeuille'}
            </button>
          </div>
        </div>
      )}

      {erreur !== null && <MessageErreur erreur={erreur} />}

      {resultat !== null && (
        <div className={styles.lu}>
          <p className={styles.consigne}>Lu dans le fichier :</p>
          <Provenance
            lignes={[
              { libelle: 'Fichier', valeur: resultat.source.filename ?? 'sans nom' },
              { libelle: 'Encodage', valeur: nomEncodage(resultat.source.encoding) },
              { libelle: 'Séparateur', valeur: cite(resultat.source.delimiter) },
              { libelle: 'Décimale', valeur: nomDecimale(resultat.source.decimal_separator) },
              { libelle: 'Lignes lues', valeur: lignes(resultat.source.rows_read) },
            ]}
          />
        </div>
      )}
    </form>
  )
}
