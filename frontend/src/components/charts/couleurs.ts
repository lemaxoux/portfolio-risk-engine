/**
 * Les couleurs d'un graphique, LUES dans les tokens — DESIGN.md §5.
 *
 * Observable Plot écrit ses couleurs dans le SVG : il a besoin de VALEURS, pas
 * de noms de variables. Une carte de chaleur interpole en Lab entre cinq
 * points (§5.4), et une interpolation ne sait rien faire de « var(--div-zero) ».
 * Les couleurs sont donc lues à l'instant du tracé dans les propriétés
 * calculées du document, qui suivent le thème — jamais recopiées ici.
 *
 * Ce module ne contient AUCUNE couleur : seulement les NOMS des tokens qu'un
 * graphique a le droit d'employer. `tokens.test.ts` interdit tout code
 * hexadécimal hors de `tokens.css`, et `couleurs.test.ts` vérifie que chaque
 * nom ci-dessous y est bien déclaré.
 */

/** Les tokens qu'un graphique peut lire, et rien d'autre (§5.3). */
export const JETONS = {
  surface0: '--surface-0',
  surface1: '--surface-1',
  surface2: '--surface-2',
  bordure: '--border',
  bordureForte: '--border-strong',
  texte1: '--text-1',
  texte2: '--text-2',
  reserve: '--caveat',
  serie1: '--series-1',
  divNegFort: '--div-neg-strong',
  divNegMoyen: '--div-neg-mid',
  divZero: '--div-zero',
  divPosMoyen: '--div-pos-mid',
  divPosFort: '--div-pos-strong',
} as const

export type Couleurs = { readonly [cle in keyof typeof JETONS]: string }

/**
 * Lit chaque token par la fonction donnée.
 *
 * Un token vide LÈVE : un nom mal orthographié rendrait sinon une chaîne vide,
 * que Plot remplacerait par sa couleur par défaut — un graphique juste, dans
 * une couleur que personne n'a choisie, et qui ne suivrait pas le thème.
 */
export function lireCouleurs(lire: (nom: string) => string): Couleurs {
  const couleurs = {} as Record<keyof typeof JETONS, string>
  for (const [cle, nom] of Object.entries(JETONS) as [keyof typeof JETONS, string][]) {
    const valeur = lire(nom).trim()
    if (valeur === '') throw new Error(`Token de couleur introuvable : ${nom}`)
    couleurs[cle] = valeur
  }
  return couleurs
}

/** Les couleurs du thème courant, telles que le navigateur les a calculées. */
export function couleursDuDocument(): Couleurs {
  const style = getComputedStyle(document.documentElement)
  return lireCouleurs((nom) => style.getPropertyValue(nom))
}

/**
 * Luminance relative WCAG d'une couleur « #rrggbb » ou « rgb(r, g, b) ».
 *
 * Présentation, pas mesure : elle ne sert qu'à choisir l'encre d'une valeur
 * écrite SUR une cellule colorée.
 */
export function luminance(couleur: string): number {
  const canaux = composantes(couleur).map((octet) => {
    const c = octet / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  const [r = 0, v = 0, b = 0] = canaux
  return 0.2126 * r + 0.7152 * v + 0.0722 * b
}

function composantes(couleur: string): number[] {
  const hexa = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(couleur.trim())
  if (hexa) return hexa.slice(1, 4).map((paire) => parseInt(paire, 16))
  const rgb = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/i.exec(couleur.trim())
  if (rgb) return rgb.slice(1, 4).map(Number)
  throw new Error(`Couleur illisible : « ${couleur} »`)
}

/** Rapport de contraste WCAG entre deux couleurs. */
export function contraste(a: string, b: string): number {
  const [clair, fonce] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return ((clair ?? 0) + 0.05) / ((fonce ?? 0) + 0.05)
}

/** L'encre la plus lisible sur un fond, parmi des tokens candidats. */
export function encreLisible(fond: string, candidats: readonly string[]): string {
  let meilleure = candidats[0]
  if (meilleure === undefined) throw new Error('Aucune encre candidate.')
  for (const candidat of candidats) {
    if (contraste(fond, candidat) > contraste(fond, meilleure)) meilleure = candidat
  }
  return meilleure
}
