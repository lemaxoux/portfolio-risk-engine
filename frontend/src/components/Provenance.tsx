/**
 * Grille libellé / valeur — DESIGN.md §9.1 et §12.
 *
 * UNE GRILLE, PAS UNE CHAÎNE DE MÉTA. §12 interdit explicitement
 * « A · B · C » : une suite jointe par des points médians se lit d'un bout à
 * l'autre ou pas du tout, alors qu'une grille se balaye — l'œil descend la
 * colonne des libellés et s'arrête sur celui qu'il cherche.
 *
 * La provenance N'EST JAMAIS MASQUÉE : ni infobulle, ni accordéon, ni « voir
 * les détails ». Elle est dans le flux, en `--text-2` — jamais en
 * `--text-muted`. Il n'existe volontairement pas de troisième niveau de gris
 * pour le texte de contenu, précisément pour qu'on ne puisse pas effacer la
 * provenance en la grisant.
 */
import styles from './Provenance.module.css'

export interface LigneProvenance {
  readonly libelle: string
  readonly valeur: string
}

export function Provenance({ lignes }: { lignes: readonly LigneProvenance[] }) {
  return (
    <dl className={styles.grille}>
      {lignes.map((ligne) => (
        <div key={ligne.libelle} className={styles.ligne}>
          <dt className={styles.libelle}>{ligne.libelle}</dt>
          <dd className={styles.valeur}>{ligne.valeur}</dd>
        </div>
      ))}
    </dl>
  )
}
