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
 */

export const CLE_ACCEPTATION = 'mx-risk-acceptation'

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
export function acceptationMemorisee(): string | null {
  try {
    return localStorage.getItem(CLE_ACCEPTATION)
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
export function aAccepte(texte: string): boolean {
  return acceptationMemorisee() === empreinte(texte)
}

export function memoriserAcceptation(texte: string): void {
  try {
    localStorage.setItem(CLE_ACCEPTATION, empreinte(texte))
  } catch {
    /* Rien à faire : l'écran reviendra au prochain chargement. */
  }
}
