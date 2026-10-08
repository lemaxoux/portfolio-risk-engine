/**
 * La langue du site (chantier 7D) : le français, langue par défaut, et
 * l'anglais américain.
 *
 * ═══ QUI CHOISIT ═══
 *
 * Dans l'ordre : `?lang=fr` ou `?lang=en` dans l'adresse, qui sert au partage
 * d'un lien et vaut un choix ; sinon le choix mémorisé dans le navigateur
 * (`mx-risk-langue`) ; sinon la première langue du navigateur qui est du
 * français ou de l'anglais ; sinon le français. Rien n'est mémorisé tant que
 * l'utilisateur n'a pas choisi, comme le thème suit le système tant qu'on ne
 * l'a pas figé : sans cela, un visiteur anglophone tomberait sur un écran
 * d'acceptation en français et devrait trouver le bouton avant de pouvoir
 * lire.
 *
 * ═══ LE SCRIPT EN LIGNE DÉCIDE, UNE FOIS ═══
 *
 * Le choix est fait par un petit script bloquant de `index.html`, avant le
 * premier rendu, comme celui du thème : il pose l'attribut `lang` de la page
 * (`fr` ou `en-US`), dont dépendent la coupure des mots des chapeaux
 * (`hyphens: auto`), la voix des lecteurs d'écran et le dictionnaire du
 * navigateur. Une langue venue de l'adresse y est mémorisée, et le paramètre
 * retiré de l'adresse : recharger la page après un changement au bouton ne
 * doit pas rétablir l'ancienne. React lit ensuite l'attribut
 * (`langueDeLaPage`). `choisirLangue` est l'écriture testée de ce choix, et
 * `langue.test.ts` fait tourner le script de `index.html` sur les mêmes cas.
 *
 * ═══ LE BOUTON ═══
 *
 * Il dit l'autre langue, dans cette langue (« English », « Français »), et
 * mémorise le choix. Le changement passe par l'application
 * (`changerLangue`, App.tsx) : l'écran d'acceptation se traverse une fois par
 * langue, et chaque appel à l'API porte la langue affichée.
 */
import { createContext, useContext } from 'react'

import { LIBELLES, type Libelles } from '../contenu/libelles'
import type { Phrases } from './phrases'
import { PHRASES_EN } from './phrases.en'
import { PHRASES_FR } from './phrases.fr'

export type Langue = 'fr' | 'en'

export const LANGUES: readonly Langue[] = ['fr', 'en']

/** Le même nom que dans le script en ligne de `index.html`. */
export const CLE_LANGUE = 'mx-risk-langue'

/** L'attribut `lang` de la page : `en-US`, pour qui Chrome a un dictionnaire de coupure. */
export const ATTRIBUT_LANG: Readonly<Record<Langue, string>> = { fr: 'fr', en: 'en-US' }

export function estUneLangue(valeur: unknown): valeur is Langue {
  return valeur === 'fr' || valeur === 'en'
}

export function autreLangue(langue: Langue): Langue {
  return langue === 'fr' ? 'en' : 'fr'
}

/** `lang` dans la partie requête d'une adresse ; toute autre valeur est ignorée. */
export function langueDeLAdresse(requete: string): Langue | null {
  const valeur = new URLSearchParams(requete).get('lang')
  return estUneLangue(valeur) ? valeur : null
}

/**
 * La première langue du navigateur qui est du français ou de l'anglais, à sa
 * sous-étiquette près : « fr-CA » est du français, « en-GB » de l'anglais.
 */
export function langueDuNavigateur(langues: readonly string[]): Langue | null {
  for (const etiquette of langues) {
    const principale = etiquette.toLowerCase().split('-')[0]
    if (estUneLangue(principale)) return principale
  }
  return null
}

/** Le choix, dans l'ordre : l'adresse, la mémoire, le navigateur, le français. */
export function choisirLangue(sources: {
  readonly adresse: Langue | null
  readonly memorisee: Langue | null
  readonly navigateur: Langue | null
}): Langue {
  return sources.adresse ?? sources.memorisee ?? sources.navigateur ?? 'fr'
}

/** Le choix mémorisé, ou `null`. Le stockage bloqué se lit « aucun choix ». */
export function langueMemorisee(): Langue | null {
  try {
    const stockee = localStorage.getItem(CLE_LANGUE)
    return estUneLangue(stockee) ? stockee : null
  } catch {
    return null
  }
}

/** La langue que le script de `index.html` a posée sur la page. */
export function langueDeLaPage(): Langue {
  return document.documentElement.lang.toLowerCase().startsWith('en') ? 'en' : 'fr'
}

/**
 * Un choix de l'utilisateur : l'attribut de la page, puis sa mémoire. Stockage
 * bloqué : la langue s'applique quand même, et le prochain chargement suit le
 * navigateur.
 */
export function appliquerLangue(langue: Langue): void {
  document.documentElement.setAttribute('lang', ATTRIBUT_LANG[langue])
  try {
    localStorage.setItem(CLE_LANGUE, langue)
  } catch {
    /* Mieux vaut une préférence oubliée qu'une page en échec. */
  }
}

// ═══════════════════════════════════════════════════════════ Le contexte ══

export interface LangueDuSite {
  readonly langue: Langue
  /** Demande l'autre langue : l'application vérifie d'abord son acceptation. */
  readonly changerLangue: (langue: Langue) => void
  /** Les libellés de l'interface, dans cette langue. */
  readonly libelles: Libelles
  /** Les phrases de lecture des mesures, dans cette langue. */
  readonly phrases: Phrases
}

/** Les phrases de chaque langue (`phrases.fr.ts`, `phrases.en.ts`). */
export const PHRASES: Readonly<Record<Langue, Phrases>> = { fr: PHRASES_FR, en: PHRASES_EN }

/** Ce que le contexte fournit pour une langue. */
export function langueDuSite(langue: Langue, changerLangue: (langue: Langue) => void): LangueDuSite {
  return { langue, changerLangue, libelles: LIBELLES[langue], phrases: PHRASES[langue] }
}

/**
 * Le français par défaut : un composant rendu hors de l'application, dans un
 * test, est en français comme avant le chantier.
 */
export const ContexteDeLangue = createContext<LangueDuSite>(langueDuSite('fr', () => undefined))

export function useLangue(): LangueDuSite {
  return useContext(ContexteDeLangue)
}
