/**
 * Les routes du client — History API, sans bibliothèque.
 *
 * Huit adresses, et c'est tout :
 *
 *   /                              le dernier portefeuille ouvert, ou le premier
 *   /portefeuilles                 la liste : choisir, créer, supprimer
 *   /portefeuilles/<id>            l'analyse
 *   /portefeuilles/<id>/positions  la saisie et l'import
 *   /portefeuilles/saisi           l'analyse du portefeuille saisi (9.6)
 *   /portefeuilles/saisi/positions sa saisie et son import (9.6)
 *   /methodologie                  comment chaque chiffre est calculé (7B.3b)
 *   /avertissement                 le texte de l'acceptation, à lire (9.4)
 *
 * Les deux builds lisent les mêmes adresses ; ce que chacune rend se décide
 * dans `App.tsx` : `/avertissement` et les deux adresses du portefeuille
 * saisi ne sont des pages que dans la démonstration, où `/` rend la
 * présentation du projet au lieu de rediriger (DESIGN.md §19). Le mot
 * `saisi` ne se confond pas avec un numéro : un numéro n'a que des chiffres.
 *
 * De VRAIES adresses et non des fragments : les fragments servent déjà aux
 * ancres des six sections (`#en-crise`) et des entrées de la méthodologie
 * (`#cvar`), et une adresse se recharge, se partage, s'ouvre dans un nouvel
 * onglet. FastAPI rend `index.html` pour toute adresse hors de `/api`
 * (`backend/api/static.py`), Vite aussi en développement.
 *
 * ═══ LA GARDE ═══
 *
 * Une page qui a des modifications non enregistrées pose une garde. Toute
 * navigation INTERNE la consulte avant de changer d'adresse : si elle refuse,
 * rien ne bouge, et c'est la page qui affiche sa confirmation, sur place — pas
 * une boîte de dialogue du navigateur. Le retour arrière du navigateur ne se
 * laisse pas annuler (l'adresse a déjà changé quand `popstate` arrive) : la
 * page courante est alors remise dans l'historique, puis la garde consultée.
 * Quitter l'application, ou recharger, relève de `beforeunload`, que pose la
 * page elle-même.
 */
import { useMemo, useSyncExternalStore } from 'react'

import { noteDeRetour, type NoteDeRetour } from './focus'

export type Route =
  | { readonly vue: 'accueil' }
  | { readonly vue: 'portefeuilles' }
  | { readonly vue: 'analyse'; readonly id: number }
  | { readonly vue: 'positions'; readonly id: number }
  | { readonly vue: 'saisi' }
  | { readonly vue: 'saisi-positions' }
  | { readonly vue: 'methodologie' }
  | { readonly vue: 'avertissement' }
  | { readonly vue: 'inconnue'; readonly chemin: string }

/** Un identifiant tel que la base les attribue : entier, à partir de 1. */
const IDENTIFIANT = /^[1-9][0-9]*$/

/**
 * Le portefeuille saisi sur le site (chantier 9.6) : le segment de ses deux
 * adresses, et la valeur que prend le dernier portefeuille consulté quand
 * c'est lui.
 */
export const SAISI = 'saisi'

/**
 * Le portefeuille que nomme le bandeau d'une page qui n'en dépend pas, et où
 * mène « Analyse » : un portefeuille de la liste, ou, sur le site, le
 * portefeuille saisi.
 */
export interface PortefeuilleEnVue {
  readonly id: number | typeof SAISI
  readonly name: string
}

/** L'adresse lue en route. Pure : ni `window`, ni historique. */
export function lireRoute(chemin: string): Route {
  const segments = chemin.split('/').filter((segment) => segment.length > 0)
  const [premier, identifiant, suite, ...reste] = segments
  if (premier === undefined) return { vue: 'accueil' }
  if (premier === 'methodologie') {
    return identifiant === undefined ? { vue: 'methodologie' } : { vue: 'inconnue', chemin }
  }
  if (premier === 'avertissement') {
    return identifiant === undefined ? { vue: 'avertissement' } : { vue: 'inconnue', chemin }
  }
  if (premier !== 'portefeuilles' || reste.length > 0) return { vue: 'inconnue', chemin }
  if (identifiant === undefined) return { vue: 'portefeuilles' }
  if (identifiant === SAISI) {
    if (suite === undefined) return { vue: 'saisi' }
    if (suite === 'positions') return { vue: 'saisi-positions' }
    return { vue: 'inconnue', chemin }
  }
  if (!IDENTIFIANT.test(identifiant)) return { vue: 'inconnue', chemin }
  const id = Number(identifiant)
  if (suite === undefined) return { vue: 'analyse', id }
  if (suite === 'positions') return { vue: 'positions', id }
  return { vue: 'inconnue', chemin }
}

/** L'adresse d'une route. `lireRoute(cheminDe(r))` rend `r`. */
export function cheminDe(route: Exclude<Route, { vue: 'inconnue' }>): string {
  switch (route.vue) {
    case 'accueil':
      return '/'
    case 'portefeuilles':
      return '/portefeuilles'
    case 'analyse':
      return `/portefeuilles/${route.id}`
    case 'positions':
      return `/portefeuilles/${route.id}/positions`
    case 'saisi':
      return `/portefeuilles/${SAISI}`
    case 'saisi-positions':
      return `/portefeuilles/${SAISI}/positions`
    case 'methodologie':
      return '/methodologie'
    case 'avertissement':
      return '/avertissement'
  }
}

// ═══════════════════════════════════════════════════ L'adresse courante ══

/**
 * Consultée avant toute navigation interne. Rend `true` pour laisser passer ;
 * `false` pour la retenir — la page qui l'a posée affiche alors sa propre
 * confirmation, avec `cible` comme destination.
 *
 * `suite` existe quand le départ n'est pas un changement d'adresse : la page
 * remplacée sur place par l'écran d'acceptation d'une autre langue
 * (`remplacerLaPage`). Si l'utilisateur confirme, c'est elle qui s'exécute, à
 * la place de la navigation vers `cible`.
 */
export type Garde = (cible: string, suite?: () => void) => boolean

let garde: Garde | null = null
let cheminCourant: string | null = null
const abonnes = new Set<() => void>()

/**
 * Navigations DÉCIDÉES par l'utilisateur : un lien suivi, un retour arrière.
 * Une redirection (`remplacer`) n'en est pas une. Tant qu'il n'y en a eu
 * aucune, un changement de page vient du chargement lui-même, et le focus
 * n'a pas à être déplacé.
 */
let navigationsUtilisateur = 0

/**
 * La dernière navigation : un lien suivi, un pas dans l'historique, ou une
 * page remplacée par un geste (`marquerGesteDecide`).
 */
let derniereNavigation: 'lien' | 'historique' | 'geste' | null = null

export function aDejaNavigue(): boolean {
  return navigationsUtilisateur > 0
}

/**
 * La page affichée vient-elle d'un retour arrière (ou d'un pas en avant) ?
 * C'est le seul cas où elle rend la place qu'avait quittée un lien vers la
 * méthode (chantier 7E, `components/Cadre`).
 */
export function navigationParHistorique(): boolean {
  return derniereNavigation === 'historique'
}

/** La note de retour de l'entrée d'historique courante, si un lien vers la méthode l'a laissée. */
export function noteDeRetourCourante(): NoteDeRetour | null {
  return noteDeRetour(window.history.state)
}

/**
 * Une page remplacée par un geste de l'utilisateur, sans changement
 * d'adresse : l'acceptation traversée, un changement de langue (chantier
 * 7E). La page qui s'affiche ensuite est traitée comme une navigation
 * décidée : elle s'ouvre en haut, et son titre reçoit le focus. Sans cela,
 * l'analyse s'ouvrait, à 390 px, à la hauteur où l'on avait coché la case.
 * Même juste après un retour arrière : elle ne rend pas la place qu'avait
 * quittée un lien vers la méthode, dont la note reste dans l'historique.
 */
export function marquerGesteDecide(): void {
  navigationsUtilisateur += 1
  derniereNavigation = 'geste'
}

function prevenir(): void {
  cheminCourant = window.location.pathname
  for (const abonne of abonnes) abonne()
}

/**
 * Le retour arrière du navigateur. L'adresse a déjà changé : si la garde
 * refuse, la page courante est remise dans l'historique, et la garde a reçu
 * la cible pour la proposer dans sa confirmation.
 */
function surRetour(): void {
  const cible = window.location.pathname
  if (cible === cheminCourant) return
  if (garde !== null && cheminCourant !== null && !garde(cible)) {
    window.history.pushState(null, '', cheminCourant)
    return
  }
  navigationsUtilisateur += 1
  derniereNavigation = 'historique'
  prevenir()
}

function abonner(abonne: () => void): () => void {
  if (abonnes.size === 0) {
    cheminCourant = window.location.pathname
    window.addEventListener('popstate', surRetour)
  }
  abonnes.add(abonne)
  return () => {
    abonnes.delete(abonne)
    if (abonnes.size === 0) window.removeEventListener('popstate', surRetour)
  }
}

/**
 * Change d'adresse sans recharger la page. `remplacer` réécrit l'entrée
 * courante de l'historique — pour une redirection, qu'un retour arrière ne
 * doit pas rejouer. `forcer` passe outre la garde : c'est ce que fait la
 * confirmation « Quitter sans enregistrer ».
 *
 * `retour` est la clé d'un lien vers la méthode (chantier 7E). Avant de
 * partir, la page la note dans son entrée d'historique, avec sa position ;
 * au retour arrière, le lien suivi reprend le focus. Un lien sans clé efface
 * la note : un retour ne rend pas une place qu'un autre lien a quittée.
 */
export function naviguer(
  chemin: string,
  options: { readonly remplacer?: boolean; readonly forcer?: boolean; readonly retour?: string } = {},
): void {
  if (!options.forcer && garde !== null && !garde(chemin)) return
  if (!options.remplacer) navigationsUtilisateur += 1
  derniereNavigation = 'lien'
  if (chemin !== window.location.pathname) {
    if (options.remplacer) {
      window.history.replaceState(null, '', chemin)
    } else {
      const note =
        options.retour === undefined ? null : { cle: options.retour, y: Math.round(window.scrollY) }
      window.history.replaceState({ retour: note }, '')
      window.history.pushState(null, '', chemin)
    }
  }
  prevenir()
}

/**
 * Remplace la page affichée sans changer d'adresse : passer à une langue dont
 * l'écran d'acceptation reste à traverser (chantier 7D). Les modifications non
 * enregistrées de la page se perdraient comme à un départ : la garde est donc
 * consultée comme pour un départ, avec l'adresse courante et `action` comme
 * suite. Sans garde, ou si elle laisse passer, l'action s'exécute aussitôt.
 */
export function remplacerLaPage(action: () => void): void {
  if (garde !== null && !garde(window.location.pathname, action)) return
  action()
}

/** Pose une garde ; la fonction rendue la retire. Une seule à la fois. */
export function poserGarde(nouvelle: Garde): () => void {
  garde = nouvelle
  return () => {
    if (garde === nouvelle) garde = null
  }
}

/** La route courante, recalculée à chaque navigation. */
export function useRoute(): Route {
  const chemin = useSyncExternalStore(
    abonner,
    () => window.location.pathname,
    () => '/',
  )
  return useMemo(() => lireRoute(chemin), [chemin])
}

// ════════════════════════════════════════ Le dernier portefeuille ouvert ══

/**
 * Mémorisé dans le navigateur, comme le thème : c'est une préférence de cet
 * écran, pas une donnée du portefeuille. Stockage bloqué : `/` ouvre alors le
 * premier de la liste, sans erreur.
 */
export const CLE_DERNIER_PORTEFEUILLE = 'mx-risk-portefeuille'

export function dernierPortefeuille(): number | null {
  try {
    const brut = localStorage.getItem(CLE_DERNIER_PORTEFEUILLE)
    return brut !== null && IDENTIFIANT.test(brut) ? Number(brut) : null
  } catch {
    return null
  }
}

export function memoriserPortefeuille(id: number): void {
  try {
    localStorage.setItem(CLE_DERNIER_PORTEFEUILLE, String(id))
  } catch {
    /* Stockage bloqué : `/` ouvrira le premier portefeuille. */
  }
}

/** Oublie `id` s'il est le portefeuille mémorisé — après sa suppression. */
export function oublierPortefeuille(id: number): void {
  if (dernierPortefeuille() !== id) return
  try {
    localStorage.removeItem(CLE_DERNIER_PORTEFEUILLE)
  } catch {
    /* Rien à faire. */
  }
}

/**
 * Le portefeuille saisi est-il le dernier consulté ? (chantier 9.6) Sur le
 * site, la même mémoire vaut `saisi` quand c'est lui : le bandeau des autres
 * pages le nomme, et « Analyse » y mène. `dernierPortefeuille` ne lit qu'un
 * numéro, et ne change pas.
 */
export function saisiEnVue(): boolean {
  try {
    return localStorage.getItem(CLE_DERNIER_PORTEFEUILLE) === SAISI
  } catch {
    return false
  }
}

export function memoriserLeSaisi(): void {
  try {
    localStorage.setItem(CLE_DERNIER_PORTEFEUILLE, SAISI)
  } catch {
    /* Stockage bloqué : aucune page ne nommera le portefeuille saisi. */
  }
}

/** Oublie le portefeuille saisi s'il est le dernier consulté : après son effacement. */
export function oublierLeSaisi(): void {
  if (!saisiEnVue()) return
  try {
    localStorage.removeItem(CLE_DERNIER_PORTEFEUILLE)
  } catch {
    /* Rien à faire. */
  }
}

/**
 * Le portefeuille que `/` ouvre : le mémorisé s'il existe encore, sinon le
 * premier de la liste, sinon aucun. Un portefeuille mémorisé puis supprimé
 * ailleurs n'est pas une erreur : on retombe sur le premier, sans rien dire.
 */
export function portefeuilleDAccueil(
  existants: readonly number[],
  memorise: number | null,
): number | null {
  if (memorise !== null && existants.includes(memorise)) return memorise
  return existants[0] ?? null
}
