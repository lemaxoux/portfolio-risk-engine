/**
 * Thème — DESIGN.md §4.
 *
 * ═══ CE QUE LE CSS FAIT DÉJÀ, ET QUE CE MODULE NE REFAIT PAS ═══
 *
 * `tokens.css` suit le réglage du système sans la moindre ligne de
 * JavaScript : le thème clair est le défaut de `:root`, le sombre est posé par
 * `@media (prefers-color-scheme: dark)`. Ce module ne sert donc QU'À la
 * surcharge manuelle. Si le JavaScript ne s'exécute pas, la page suit le
 * système — ce qui est le comportement correct, pas un mode dégradé.
 *
 * ═══ BASCULE À DEUX ÉTATS, PAS TROIS ═══
 *
 * Les deux états sont « comme le système » et « l'autre ». Pas de troisième
 * choix « automatique » en plus de « clair » et « sombre » : deux des trois
 * options produiraient le même résultat visuel à tout instant, et l'on ne peut
 * pas demander à quelqu'un d'exprimer une intention sur un problème qu'il n'a
 * pas encore.
 *
 * LA VALEUR STOCKÉE EST LITTÉRALE — « light » ou « dark », jamais « l'inverse
 * du système » recalculé à l'affichage. Choisir l'autre FIGE ce thème précis :
 * si le système bascule ensuite, l'application ne suit pas. Revenir à « comme
 * le système » efface l'entrée.
 */

export type Theme = 'light' | 'dark'

/** Le même nom que dans le script en ligne de `index.html`. */
export const CLE_STOCKAGE = 'mx-risk-theme'

const REQUETE_SOMBRE = '(prefers-color-scheme: dark)'

/**
 * Thème figé, ou `null` quand on suit le système.
 *
 * `localStorage` LÈVE — il ne rend pas `null` — quand le stockage est bloqué
 * (navigation privée verrouillée, cookies tiers refusés, politique
 * d'entreprise). Sans le `try/catch`, l'application ne démarrerait pas du tout
 * chez ces utilisateurs, pour une préférence d'affichage.
 */
export function themeFige(): Theme | null {
  try {
    const stocke = localStorage.getItem(CLE_STOCKAGE)
    return stocke === 'light' || stocke === 'dark' ? stocke : null
  } catch {
    return null
  }
}

/** Préférence du système, à cet instant. */
export function themeDuSysteme(): Theme {
  return window.matchMedia(REQUETE_SOMBRE).matches ? 'dark' : 'light'
}

/**
 * Applique un choix : `null` efface la surcharge et rend la main au système.
 *
 * L'attribut `data-theme` gouverne les tokens (`tokens.css`) ; le `<meta>`
 * gouverne le canevas que le navigateur peint avant même le premier rendu. Les
 * deux sont tenus ensemble, sinon un rechargement montrerait le fond du
 * navigateur dans un thème et la page dans l'autre.
 */
export function appliquerTheme(choix: Theme | null): void {
  const racine = document.documentElement
  if (choix === null) racine.removeAttribute('data-theme')
  else racine.setAttribute('data-theme', choix)

  const meta = document.querySelector('meta[name="color-scheme"]')
  if (meta) meta.setAttribute('content', choix ?? 'light dark')

  try {
    if (choix === null) localStorage.removeItem(CLE_STOCKAGE)
    else localStorage.setItem(CLE_STOCKAGE, choix)
  } catch {
    /* Stockage bloqué : le thème s'applique quand même, il ne survit pas au
     * rechargement. Mieux vaut une préférence oubliée qu'une page en échec. */
  }
}

/** Le contraire d'un thème. */
export function contraire(theme: Theme): Theme {
  return theme === 'dark' ? 'light' : 'dark'
}
