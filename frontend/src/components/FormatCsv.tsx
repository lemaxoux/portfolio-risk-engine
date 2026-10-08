/**
 * Le format CSV, affiché en clair, SUR PLACE — DESIGN.md §8.2, §13.
 *
 * §13 le demande dans l'état vide : on invite à importer, on dit tout de suite
 * quoi préparer. Un seul composant, réutilisé partout où l'on peut arriver
 * sans portefeuille ou sans position, pour qu'il n'existe qu'une description.
 *
 * Tout vient de `GET /api/csv-format`, le format que le lecteur applique
 * lui-même : l'exemple en tête — un vrai fichier, que les tests du backend
 * importent —, puis les règles. L'exemple est en IBM Plex Mono, le seul usage
 * que §6.1 en permet avec les commandes : du contenu réellement code.
 */
import type { ApiErreur } from '../api/client'
import type { CsvFormat } from '../api/types'
import { nomEncodage, nomEspace, useFormatCsv } from '../lib/csv'
import { useLangue } from '../lib/langue'
import styles from './FormatCsv.module.css'

export function FormatCsv({ niveau }: { niveau: 2 | 3 }) {
  const { langue, libelles } = useLangue()
  const { format, erreur } = useFormatCsv(langue)
  const Titre = niveau === 2 ? 'h2' : 'h3'
  return (
    <div className={styles.bloc}>
      <Titre className={styles.titre}>{libelles.csv.format}</Titre>
      {format !== null ? (
        <Regles format={format} />
      ) : erreur !== null ? (
        <Indisponible erreur={erreur} />
      ) : (
        // En cours : la forme de l'exemple, sans animation (§10).
        <div className={styles.squelette} aria-hidden="true" />
      )}
    </div>
  )
}

function Indisponible({ erreur }: { erreur: ApiErreur }) {
  const { libelles } = useLangue()
  return (
    // Aucune description de repli : elle serait la copie que la publication
    // du format existe pour éviter. Un import tenté dira, ligne par ligne, ce
    // qui ne va pas.
    <p className={styles.texte}>
      {libelles.csv.formatIllisible}
      {erreur.detail}
    </p>
  )
}

function Regles({ format }: { format: CsvFormat }) {
  const { langue, libelles } = useLangue()
  const l = libelles.csv
  return (
    <>
      <p className={styles.texte}>{l.exemple}</p>
      <pre className={styles.exemple}>
        <code>{format.example.trimEnd()}</code>
      </pre>
      <ul className={styles.regles}>
        <li>
          {l.enTete}
          {format.required_columns.map((colonne, rang) => (
            <span key={colonne}>
              {rang > 0 && ', '}
              <code>{colonne}</code>
            </span>
          ))}
          {format.optional_columns.length > 0 && (
            <>
              {l.facultative}
              {format.optional_columns.map((colonne, rang) => (
                <span key={colonne}>
                  {rang > 0 && ', '}
                  <code>{colonne}</code>
                </span>
              ))}
              {l.sansEffet}
            </>
          )}
          .
        </li>
        {format.delimiters.map((regle) => (
          <li key={regle.delimiter}>{l.separateurEt(regle.delimiter, regle.decimal_separators)}</li>
        ))}
        <li>
          {l.espaces}
          {format.thousands_separators.map((espace) => nomEspace(espace, langue)).join(', ')}.
        </li>
        <li>
          {l.encodages}
          {format.encodings.map((code) => nomEncodage(code, langue)).join(', ')}.
        </li>
        <li>{l.auPlus(format.max_bytes, format.max_positions)}</li>
        <li>{l.remplaceTout}</li>
      </ul>
    </>
  )
}
