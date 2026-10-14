/**
 * Mémorisation de l'acceptation — DESIGN.md §15.
 *
 * §15 laissait le choix de l'endroit à la phase 7B. C'est le NAVIGATEUR, et la
 * raison tient à ce que l'acceptation décrit : elle n'est pas une propriété du
 * portefeuille, ni de la base, ni d'un utilisateur — le projet n'a pas de
 * notion d'utilisateur. Elle est le fait qu'une personne, devant cet écran, a
 * lu ce texte. La stocker dans la base la ferait porter au portefeuille de
 * quelqu'un d'autre le jour où le fichier est copié sur une autre machine.
 *
 * ═══ LA CLÉ PORTE L'EMPREINTE DU TEXTE ═══
 *
 * On ne mémorise pas « a accepté », on mémorise « a accepté CE texte-là ». Si
 * le bandeau change — une limite ajoutée, une fenêtre d'estimation modifiée —
 * l'empreinte change et l'écran revient. Une acceptation qui survivrait à la
 * réécriture du texte qu'elle vise ne voudrait rien dire.
 *
 * ═══ POURQUOI UNE EMPREINTE FNV-1a ET PAS `crypto.subtle` ═══
 *
 * Il ne s'agit pas de sécurité : personne n'a intérêt à forger une acceptation
 * sur sa propre machine, et le texte est public. Il s'agit de DÉTECTER UN
 * CHANGEMENT. `crypto.subtle.digest` est asynchrone et n'existe qu'en contexte
 * sécurisé — ce que `localhost` est, mais qui ferait dépendre l'affichage du
 * premier écran d'une promesse et d'une condition d'environnement, pour un
 * gain nul. FNV-1a est synchrone, tient en six lignes, et la longueur du texte
 * est jointe à l'empreinte : deux textes de longueurs différentes ne peuvent
 * pas se confondre, quoi qu'il arrive aux 32 bits.
 *
 * ═══ UNE ACCEPTATION PAR LANGUE (chantier 7D) ═══
 *
 * Le texte anglais est un autre texte : qui passe à l'anglais ne l'a pas lu.
 * Il le traverse une fois, et une fois seulement : chaque langue a sa clé, et
 * l'aller-retour entre les deux ne redemande rien. La clé française reste
 * celle d'avant le chantier, et son texte n'a pas changé : personne n'a à
 * réaccepter en français.
 */
import type { Langue } from './langue'

/** La clé du français, celle d'avant le chantier 7D. */
export const CLE_ACCEPTATION = 'mx-risk-acceptation'

/** La clé d'une langue : celle du français, suffixée pour les autres. */
export function cleAcceptation(langue: Langue = 'fr'): string {
  return langue === 'fr' ? CLE_ACCEPTATION : `${CLE_ACCEPTATION}-${langue}`
}

/**
 * Empreinte FNV-1a 32 bits, suffixée de la longueur du texte.
 *
 * `Math.imul` fait la multiplication 32 bits que `*` ne fait pas : au-delà de
 * 2^53 un produit JavaScript perd ses bits de poids faible, qui sont justement
 * ceux que l'empreinte diffuse. `>>> 0` ramène le résultat en non signé.
 */
export function empreinte(texte: string): string {
  let hachage = 0x811c9dc5
  for (let i = 0; i < texte.length; i += 1) {
    hachage ^= texte.charCodeAt(i)
    hachage = Math.imul(hachage, 0x01000193)
  }
  const hexa = (hachage >>> 0).toString(16).padStart(8, '0')
  return `${hexa}-${texte.length.toString(16)}`
}

/** L'empreinte acceptée, ou `null`. Le stockage bloqué se lit « pas accepté ». */
export function acceptationMemorisee(langue: Langue = 'fr'): string | null {
  try {
    return localStorage.getItem(cleAcceptation(langue))
  } catch {
    return null
  }
}

/**
 * Ce texte précis a-t-il été accepté ?
 *
 * Stockage bloqué : l'écran revient à chaque chargement. C'est le comportement
 * voulu — une acceptation qu'on ne peut pas mémoriser doit être redemandée, pas
 * supposée acquise.
 */
export function aAccepte(texte: string, langue: Langue = 'fr'): boolean {
  return acceptationMemorisee(langue) === empreinte(texte)
}

export function memoriserAcceptation(texte: string, langue: Langue = 'fr'): void {
  acceptesDansLaPage.set(langue, empreinte(texte))
  try {
    localStorage.setItem(cleAcceptation(langue), empreinte(texte))
  } catch {
    /* Rien à faire : l'écran reviendra au prochain chargement. */
  }
}

// ════════════════════════════════════════ La preuve d'acceptation (9.6) ══

/*
 * Sur le site, le portefeuille saisi part vers un serveur public. L'écran
 * d'acceptation garde les deux pages d'où il part ; `client.ts` ajoute une
 * seconde barrière : ses deux fonctions d'envoi demandent une PREUVE que le
 * texte de la langue de la requête a été accepté, et lèvent sans rien envoyer
 * sans elle. Seul ce module la délivre, d'après l'empreinte du texte accepté.
 *
 * Elle se délivre aussi pendant la page où le texte a été accepté, stockage
 * bloqué compris : l'acceptation y vaut jusqu'à la fermeture, et l'écran
 * revient au chargement suivant, comme dans l'application. `aAccepte` ne lit
 * que le stockage, et ne change pas.
 */

/** L'empreinte acceptée dans cette page, par langue. */
const acceptesDansLaPage = new Map<Langue, string>()

/** Ce que porte une preuve : la langue du texte accepté, et son empreinte. */
export interface PreuveDAcceptation {
  readonly langue: Langue
  readonly empreinte: string
}

/** Les preuves délivrées par ce module, et elles seules. */
const delivrees = new WeakSet<PreuveDAcceptation>()

/**
 * La preuve que `texte` a été accepté dans `langue`, ou `null`. Le texte est
 * celui que l'écran a montré : une acceptation d'un autre texte ne prouve rien.
 */
export function preuveDAcceptation(texte: string, langue: Langue): PreuveDAcceptation | null {
  const attendue = empreinte(texte)
  if (acceptationMemorisee(langue) !== attendue && acceptesDansLaPage.get(langue) !== attendue) {
    return null
  }
  const preuve: PreuveDAcceptation = Object.freeze({ langue, empreinte: attendue })
  delivrees.add(preuve)
  return preuve
}

/** Une preuve délivrée ici, pour cette langue. Un objet de même forme n'en est pas une. */
export function estUnePreuve(preuve: unknown, langue: Langue): boolean {
  return (
    typeof preuve === 'object' &&
    preuve !== null &&
    delivrees.has(preuve as PreuveDAcceptation) &&
    (preuve as PreuveDAcceptation).langue === langue
  )
}
