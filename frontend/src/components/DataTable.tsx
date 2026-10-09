/**
 * `<DataTable>` — le tableau, DESIGN.md §9.3.
 *
 * « Le composant le plus utilisé du produit. Il mérite du soin. »
 *
 * ═══ CE QU'IL FAIT ═══
 *
 * - En-tête sur `--surface-2`, graisse 500, casse phrase. Il n'est pas
 *   collant (§9.3) : dans un cadre qui défile à l'horizontale, il collerait
 *   au cadre et non à la page. La première colonne, elle, reste collante à
 *   l'horizontale.
 * - Séparateurs HORIZONTAUX seulement : l'alignement des chiffres sépare les
 *   colonnes, une grille complète alourdirait sans rien dire.
 * - Colonnes de chiffres à droite, tabulaires. Le nombre de décimales est
 *   décidé par colonne, par l'appelant, avec `lib/format` : ce composant
 *   n'écrit aucun nombre.
 * - Tri au clic sur un en-tête triable : indicateur en `--accent` ET flèche
 *   ▲/▼, parce que la couleur seule ne suffit pas (§5.3). `aria-sort` dit la
 *   même chose aux lecteurs d'écran.
 * - `<caption>` et `<th scope>` (§13).
 *
 * ═══ LE CADRE QUI DÉFILE, AU CLAVIER (chantier 7E, §9.3, §13) ═══
 *
 * Tant que le tableau déborde, le cadre est une région que nomme la légende
 * (`role="region"`, `aria-labelledby`), et il se prend au clavier
 * (`tabIndex={0}`) : les flèches le font défiler. Chrome le faisait de
 * lui-même pour un cadre sans élément focalisable, sans nom ni rôle, et
 * Safari ne le fait pas. Un tableau qui tient dans sa colonne n'en a pas
 * besoin : la région y doublerait l'annonce de la légende, que le tableau
 * porte déjà. Quand un élément du tableau reçoit le focus, le
 * cadre l'amène en entier, à droite de la colonne collante : Chrome ne fait
 * pas défiler un cadre vers un élément déjà en partie visible (à 390 px,
 * l'en-tête « Nom » restait visible sur 11 px de ses 43), et la colonne
 * collante en cachait d'autres en arrière.
 *
 * ═══ CE QU'IL NE FAIT PAS ═══
 *
 * Aucun total, aucune moyenne, aucune ligne calculée. Trier est un ordre de
 * présentation ; additionner serait une mesure, et une mesure s'ajoute au
 * moteur. Une ligne de pied, quand il en faut une, arrive DÉJÀ écrite par
 * l'appelant, depuis un champ publié (`pied`).
 */
import { useEffect, useId, useRef, useState, type FocusEvent, type ReactNode } from 'react'

import { avecAbsence } from './Absent'
import styles from './DataTable.module.css'

export interface Colonne<T> {
  readonly cle: string
  /** En-tête, casse phrase ; porte l'unité quand la colonne en a une. */
  readonly titre: string
  /** `nombre` aligne à droite, en chiffres tabulaires (§7, §9.3). */
  readonly nature: 'texte' | 'nombre'
  /** Le contenu de la cellule, déjà écrit par `lib/format`. */
  readonly cellule: (ligne: T) => ReactNode
  /**
   * La valeur BRUTE par laquelle trier, si la colonne est triable. Comparer
   * deux valeurs publiées n'en calcule aucune.
   */
  readonly tri?: (ligne: T) => number | string
}

type Sens = 'croissant' | 'decroissant'

interface Props<T> {
  readonly legende: string
  /**
   * L'identifiant de la légende, quand un autre élément la désigne : le
   * graphique des parts dans les variations renvoie au tableau qui le suit
   * (`aria-describedby`, chantier 7E).
   */
  readonly idLegende?: string
  /**
   * `contenu` : le tableau prend la largeur de ses colonnes plutôt que celle
   * de la colonne de lecture. Pour les valeurs d'un graphique, deux ou trois
   * colonnes qui ne doivent pas s'écarter sur toute la page (§9.4).
   */
  readonly largeur?: 'colonne' | 'contenu'
  readonly colonnes: readonly Colonne<T>[]
  readonly lignes: readonly T[]
  readonly cleDeLigne: (ligne: T) => string
  /** Ordre initial ; sans lui, l'ordre reçu est conservé. */
  readonly triInitial?: { readonly cle: string; readonly sens: Sens }
  /** Ligne de pied, déjà écrite, cellule par cellule (une par colonne). */
  readonly pied?: readonly ReactNode[]
}

function comparer(a: number | string, b: number | string): number {
  if (typeof a === 'number' && typeof b === 'number') return a < b ? -1 : a > b ? 1 : 0
  return String(a).localeCompare(String(b), 'fr')
}

/**
 * Ce que reçoit le cadre d'un tableau qui déborde : une région nommée par la
 * légende, que la tabulation prend. Rien quand il tient dans sa colonne.
 */
export function attributsDuCadre(
  deborde: boolean,
  idLegende: string,
): { role?: 'region'; 'aria-labelledby'?: string; tabIndex?: 0 } {
  return deborde ? { role: 'region', 'aria-labelledby': idLegende, tabIndex: 0 } : {}
}

/**
 * Amène dans le cadre l'élément qui vient d'y recevoir le focus, en entier,
 * à droite de la colonne collante. Le défilement est instantané.
 */
function amenerDansLeCadre(evenement: FocusEvent<HTMLDivElement>): void {
  const cadre = evenement.currentTarget
  const cible = evenement.target
  if (cible === cadre || !(cible instanceof HTMLElement)) return
  const collee = cadre.querySelector('tr > :first-child')
  // La largeur de la colonne collante, mesurée : elle dépend des tickers.
  const largeur = collee instanceof HTMLElement ? collee.getBoundingClientRect().width : 0
  cadre.style.setProperty('--colonne-collee', `${Math.ceil(largeur)}px`)
  cible.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}

/** L'ordre d'affichage, sans toucher aux lignes reçues. */
export function lignesTriees<T>(
  lignes: readonly T[],
  colonne: Colonne<T> | undefined,
  sens: Sens,
): T[] {
  const copie = [...lignes]
  const cle = colonne?.tri
  if (cle === undefined) return copie
  copie.sort((a, b) => (sens === 'croissant' ? 1 : -1) * comparer(cle(a), cle(b)))
  return copie
}

export function DataTable<T>({
  legende,
  idLegende,
  largeur = 'colonne',
  colonnes,
  lignes,
  cleDeLigne,
  triInitial,
  pied,
}: Props<T>) {
  const [tri, setTri] = useState(triInitial ?? null)
  const idGenere = useId()
  const idDeLaLegende = idLegende ?? idGenere
  const cadre = useRef<HTMLDivElement>(null)
  const [deborde, setDeborde] = useState(false)
  const colonneTriee = colonnes.find((colonne) => colonne.cle === tri?.cle)

  // Le tableau déborde-t-il de son cadre ? Mesuré à chaque changement de
  // taille, du cadre (la page) comme du tableau (ses colonnes).
  useEffect(() => {
    const noeud = cadre.current
    if (noeud === null) return
    const mesurer = () => setDeborde(noeud.scrollWidth > noeud.clientWidth + 1)
    const observateur = new ResizeObserver(mesurer)
    observateur.observe(noeud)
    const table = noeud.firstElementChild
    if (table !== null) observateur.observe(table)
    return () => observateur.disconnect()
  }, [])
  const affichees = tri === null ? [...lignes] : lignesTriees(lignes, colonneTriee, tri.sens)

  const trier = (cle: string) =>
    setTri((courant) =>
      courant?.cle === cle
        ? { cle, sens: courant.sens === 'croissant' ? 'decroissant' : 'croissant' }
        : { cle, sens: 'decroissant' },
    )

  return (
    <div
      ref={cadre}
      className={styles.cadre}
      onFocus={amenerDansLeCadre}
      {...attributsDuCadre(deborde, idDeLaLegende)}
    >
      <table
        className={largeur === 'contenu' ? `${styles.tableau} ${styles.auContenu}` : styles.tableau}
      >
        <caption id={idDeLaLegende} className={styles.legende}>
          {legende}
        </caption>
        <thead>
          <tr>
            {colonnes.map((colonne) => {
              const actif = tri?.cle === colonne.cle
              const classes = [styles.entete, colonne.nature === 'nombre' ? styles.nombre : '']
              return (
                <th
                  key={colonne.cle}
                  scope="col"
                  className={classes.join(' ')}
                  aria-sort={
                    actif
                      ? tri?.sens === 'croissant'
                        ? 'ascending'
                        : 'descending'
                      : undefined
                  }
                >
                  {colonne.tri === undefined ? (
                    colonne.titre
                  ) : (
                    <button
                      type="button"
                      className={actif ? `${styles.tri} ${styles.triActif}` : styles.tri}
                      onClick={() => trier(colonne.cle)}
                    >
                      {colonne.titre}
                      <span className={styles.fleche} aria-hidden="true">
                        {actif ? (tri?.sens === 'croissant' ? '▲' : '▼') : ''}
                      </span>
                    </button>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {affichees.map((ligne) => (
            <tr key={cleDeLigne(ligne)} className={styles.ligne}>
              {colonnes.map((colonne, rang) => {
                const classes = [styles.cellule, colonne.nature === 'nombre' ? styles.nombre : '']
                return rang === 0 ? (
                  <th key={colonne.cle} scope="row" className={classes.join(' ')}>
                    {avecAbsence(colonne.cellule(ligne))}
                  </th>
                ) : (
                  <td key={colonne.cle} className={classes.join(' ')}>
                    {avecAbsence(colonne.cellule(ligne))}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
        {pied !== undefined && (
          <tfoot>
            <tr className={styles.pied}>
              {colonnes.map((colonne, rang) => {
                const classes = [styles.cellule, colonne.nature === 'nombre' ? styles.nombre : '']
                return (
                  <td key={colonne.cle} className={classes.join(' ')}>
                    {avecAbsence(pied[rang] ?? null)}
                  </td>
                )
              })}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
