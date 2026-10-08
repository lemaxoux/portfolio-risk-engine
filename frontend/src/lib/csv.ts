/**
 * Ce que l'interface dit du format CSV — DESIGN.md §8.2, §13.
 *
 * LE FORMAT VIENT DU LECTEUR (`GET /api/csv-format`), pas d'ici : colonnes,
 * séparateurs, décimales, encodages, limites et exemple sont ceux que
 * `backend/api/csv_import.py` applique. Ce module ne fait que NOMMER en
 * français les codes qu'il publie — « cp1252 » devient « Windows-1252 » —, et
 * chaque `source` d'un import réussi se lit avec les mêmes mots. Un code
 * inconnu s'affiche tel quel : un nom inventé serait pire qu'un code brut.
 *
 * Les tables portant sur les valeurs FERMÉES de l'API (encodage et décimale
 * d'une `source`) sont typées sur leur union : une valeur ajoutée côté serveur
 * sans nom ici ne compile pas.
 */
import { useEffect, useState } from 'react'

import { ApiErreur, getCsvFormat, versApiErreur } from '../api/client'
import type { CsvFormat, CsvSource } from '../api/types'
import { LIBELLES } from '../contenu/libelles'
import type { Langue } from './langue'

/**
 * Les noms vivent dans les libellés de chaque langue (`contenu/libelles.*`) :
 * leurs tables sont typées sur les valeurs fermées de l'API, et une valeur
 * ajoutée côté serveur sans nom ne compile pas.
 */
export function nomEncodage(code: string, langue: Langue = 'fr'): string {
  const noms = LIBELLES[langue].csv.nomsEncodages
  return code in noms ? noms[code as CsvSource['encoding']] : code
}

/** La décimale OBSERVÉE dans un fichier importé. */
export function nomDecimale(code: CsvSource['decimal_separator'], langue: Langue = 'fr'): string {
  return LIBELLES[langue].csv.nomsDecimales[code]
}

/** Une espace de milliers admise, nommée — elle ne se voit pas écrite. */
export function nomEspace(caractere: string, langue: Langue = 'fr'): string {
  return (
    LIBELLES[langue].csv.nomsEspaces[caractere] ??
    `U+${caractere.codePointAt(0)?.toString(16).toUpperCase() ?? '?'}`
  )
}

// ═══════════════════════════════════════════════ Le format, une fois lu ══

// L'exemple publié dépend de la langue (celui d'un Excel français ou
// anglais) : une lecture par langue.
const enCours = new Map<Langue, Promise<CsvFormat>>()

function charger(langue: Langue): Promise<CsvFormat> {
  let lecture = enCours.get(langue)
  if (lecture === undefined) {
    lecture = getCsvFormat(langue).catch((cause: unknown) => {
      enCours.delete(langue) // un prochain affichage réessaiera
      throw cause
    })
    enCours.set(langue, lecture)
  }
  return lecture
}

/** Le format publié par le lecteur, lu une fois par session et par langue. */
export function useFormatCsv(langue: Langue = 'fr'): {
  format: CsvFormat | null
  erreur: ApiErreur | null
} {
  const [format, setFormat] = useState<CsvFormat | null>(null)
  const [erreur, setErreur] = useState<ApiErreur | null>(null)

  useEffect(() => {
    let vivant = true
    charger(langue).then(
      (lu) => {
        if (vivant) setFormat(lu)
      },
      (cause: unknown) => {
        if (vivant) setErreur(versApiErreur(cause, langue))
      },
    )
    return () => {
      vivant = false
    }
  }, [langue])

  return { format, erreur }
}
