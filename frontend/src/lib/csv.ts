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
import type { Langue } from './langue'
import { cite } from './phrases'

const ENCODAGES: Record<CsvSource['encoding'], string> = {
  'utf-8': 'UTF-8',
  'utf-8-sig': "UTF-8 avec marque d'ordre des octets (BOM)",
  cp1252: 'Windows-1252 (CP1252)',
}

export function nomEncodage(code: string): string {
  return code in ENCODAGES ? ENCODAGES[code as CsvSource['encoding']] : code
}

const DECIMALES: Record<CsvSource['decimal_separator'], string> = {
  ',': cite(','),
  '.': cite('.'),
  mixte: 'mixte\u00a0: virgules et points dans le même fichier',
  aucune: 'aucune\u00a0: tous les nombres sont entiers',
}

/** La décimale OBSERVÉE dans un fichier importé. */
export function nomDecimale(code: CsvSource['decimal_separator']): string {
  return DECIMALES[code]
}

const ESPACES: Record<string, string> = {
  ' ': 'ordinaire',
  '\u00A0': 'insécable',
  '\u202F': 'fine insécable',
}

/** Une espace de milliers admise, nommée — elle ne se voit pas écrite. */
export function nomEspace(caractere: string): string {
  return ESPACES[caractere] ?? `U+${caractere.codePointAt(0)?.toString(16).toUpperCase() ?? '?'}`
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
        if (vivant) setErreur(versApiErreur(cause))
      },
    )
    return () => {
      vivant = false
    }
  }, [langue])

  return { format, erreur }
}
