/**
 * `<Measure>` — le composant central, DESIGN.md §9.1.
 *
 * Il rend un chiffre ET ses conditions comme un objet indissociable. C'est le
 * composant sur lequel repose la thèse du produit : une interface qui
 * afficherait « 1,38 % » en gros et cacherait la fenêtre d'estimation dans une
 * infobulle détruirait six phases de travail.
 *
 * ═══ CE COMPOSANT NE FORMATE RIEN, ET NE COMPOSE AUCUNE PROVENANCE ═══
 *
 * `valeur` arrive DÉJÀ ÉCRITE, par `lib/format`. `provenance` arrive déjà
 * construite, par `lib/provenance`, à partir des champs réels du backend. Les
 * deux séparations tiennent la même règle : un composant qui formaterait un
 * nombre lui-même en produirait un deuxième format, et un composant qui
 * saisirait « Fenêtre : 504 séances » à la main écrirait un jour une fenêtre
 * qui n'est pas celle du calcul.
 *
 * ═══ LES QUATRE RÈGLES DURES DE §9.1 ═══
 *
 * 1. La provenance ne peut pas être masquée — elle est dans le flux.
 * 2. Convention de signe : une VaR est une PERTE POSITIVE, l'interface
 *    n'ajoute jamais de « − ». Une valeur négative est un gain, et c'est la
 *    PHRASE DE LECTURE qui change — d'où `lecture`, que l'appelant choisit.
 * 3. Une mesure indéfinie s'affiche indéfinie : `valeur` vaut alors le tiret
 *    cadratin et `lecture` porte la raison, en toutes lettres. Jamais 0.
 * 4. Une réserve méthodologique met un point devant le libellé et sa phrase
 *    sous la provenance.
 *
 * ═══ LES TEXTES DE LECTURE ═══
 *
 * Sous le chiffre, la phrase concrète (`lecture`) et, s'il y en a une, la ligne
 * qui dit ce que le chiffre ne dit pas (`neDitPas`) ; puis la provenance, sous
 * l'intertitre « Détails du calcul ». L'intertitre NOMME le bloc, il ne le
 * replie pas : la provenance reste dans le flux (règle 1).
 */
import type { LigneProvenance } from './Provenance'
import { Provenance } from './Provenance'
import styles from './Measure.module.css'

interface Props {
  /** Ce que le chiffre mesure. Casse phrase, jamais de capitales (§12). */
  readonly libelle: string
  /** Le chiffre, DÉJÀ formaté par `lib/format`. */
  readonly valeur: string
  /** La phrase de lecture, en langage courant (§15). */
  readonly lecture: string
  /** Ce que le chiffre ne dit pas, en une ligne courte. */
  readonly neDitPas?: string | null
  readonly provenance: readonly LigneProvenance[]
  /** Réserve méthodologique, telle que le backend l'écrit. */
  readonly caveat?: string | null
  /**
   * `principal` pour le chiffre que la section met en avant, `secondaire` pour
   * ceux qui le commentent. Rien d'autre : la hiérarchie se dit par la taille,
   * pas par la couleur (§3.1).
   */
  readonly niveau?: 'principal' | 'secondaire'
}

export function Measure({
  libelle,
  valeur,
  lecture,
  neDitPas = null,
  provenance,
  caveat = null,
  niveau = 'principal',
}: Props) {
  const classes = [styles.bloc, niveau === 'principal' ? styles.principal : styles.secondaire]

  return (
    <figure className={classes.join(' ')}>
      <figcaption className={styles.libelle}>
        {/* Le point est un ÉLÉMENT, pas une couleur de texte : en niveaux de
            gris il reste visible, et l'information ne disparaît pas (§5.3). */}
        {caveat !== null && <span className={styles.point} aria-hidden="true" />}
        {libelle}
      </figcaption>

      <p className={styles.valeur}>{valeur}</p>
      <p className={styles.lecture}>{lecture}</p>
      {neDitPas !== null && <p className={styles.neDitPas}>{neDitPas}</p>}

      <div className={styles.details}>
        <p className={styles.detailsTitre}>Détails du calcul</p>
        <Provenance lignes={provenance} />
      </div>

      {caveat !== null && <p className={styles.reserve}>{caveat}</p>}
    </figure>
  )
}
