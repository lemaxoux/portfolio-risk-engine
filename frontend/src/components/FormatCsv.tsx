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
import { compte, lignes } from '../lib/format'
import { nomEncodage, nomEspace, useFormatCsv } from '../lib/csv'
import { cite } from '../lib/phrases'
import styles from './FormatCsv.module.css'

export function FormatCsv({ niveau }: { niveau: 2 | 3 }) {
  const { format, erreur } = useFormatCsv()
  const Titre = niveau === 2 ? 'h2' : 'h3'
  return (
    <div className={styles.bloc}>
      <Titre className={styles.titre}>Format du fichier</Titre>
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
  return (
    // Aucune description de repli : elle serait la copie que la publication
    // du format existe pour éviter. Un import tenté dira, ligne par ligne, ce
    // qui ne va pas.
    <p className={styles.texte}>Le format n'a pas pu être lu&nbsp;: {erreur.detail}</p>
  )
}

function Regles({ format }: { format: CsvFormat }) {
  return (
    <>
      <p className={styles.texte}>Par exemple, tel qu'un tableur l'enregistre&nbsp;:</p>
      <pre className={styles.exemple}>
        <code>{format.example.trimEnd()}</code>
      </pre>
      <ul className={styles.regles}>
        <li>
          Une ligne d'en-tête, puis une ligne par titre. Colonnes obligatoires&nbsp;:{' '}
          {format.required_columns.map((colonne, rang) => (
            <span key={colonne}>
              {rang > 0 && ', '}
              <code>{colonne}</code>
            </span>
          ))}
          {format.optional_columns.length > 0 && (
            <>
              &nbsp;; facultative&nbsp;:{' '}
              {format.optional_columns.map((colonne, rang) => (
                <span key={colonne}>
                  {rang > 0 && ', '}
                  <code>{colonne}</code>
                </span>
              ))}{' '}
              (le prix de revient, sans effet sur l'analyse)
            </>
          )}
          .
        </li>
        {format.delimiters.map((regle) => (
          <li key={regle.delimiter}>
            Séparateur {cite(regle.delimiter)}&nbsp;: décimale{' '}
            {regle.decimal_separators.map((decimale) => cite(decimale)).join(' ou ')}.
          </li>
        ))}
        <li>
          Espaces de milliers admises&nbsp;:{' '}
          {format.thousands_separators.map((espace) => nomEspace(espace)).join(', ')}.
        </li>
        <li>Encodage&nbsp;: {format.encodings.map((code) => nomEncodage(code)).join(', ')}.</li>
        <li>
          Au plus {compte(format.max_bytes, 'octet')} et {lignes(format.max_positions)}.
        </li>
        <li>L'import remplace toutes les positions du portefeuille.</li>
      </ul>
    </>
  )
}
