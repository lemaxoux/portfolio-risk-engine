/**
 * Les coupures conditionnelles de la prose de la méthodologie — DESIGN.md
 * §6.3, décision du 2026-10-08.
 *
 * ═══ POURQUOI ═══
 *
 * Une ligne justifiée n'ouvre aucune espace de plus de 2,5 fois la normale,
 * avec ou sans dictionnaire de césure. Justifiée avec `hyphens: auto`, la
 * méthodologie montait à 3,35 (français) et 3,16 (anglais) sans dictionnaire,
 * celui que Chrome télécharge après coup : un mot long (« appliquent »,
 * « inconsistent ») qu'aucune coupure ne venait rompre. Les coupures sont donc
 * posées dans le texte, au build, par les motifs de césure de TeX : la
 * justification ne dépend plus du navigateur du visiteur.
 *
 * ═══ OÙ ═══
 *
 * Dans les paragraphes, et nulle part ailleurs : ni dans les titres, ni dans
 * les listes, ni dans les formules (en bloc ou dans la phrase), ni dans le
 * texte d'un lien, ni dans une entité. Un paragraphe est ce que lit
 * `lireContenu` : un bloc dont la première ligne n'est ni un titre, ni une
 * formule en bloc, ni un élément de liste. Son étiquette en tête
 * (`**Hypothèses.**`) est de la prose : elle se coupe comme le reste.
 *
 * ═══ LES RÈGLES ═══
 *
 * Au moins deux lettres avant une coupure et trois après. Aucune coupure
 * dans un mot qui porte une capitale ou un chiffre (« VaR », « CVaR »,
 * « Student », « Monte Carlo », « S&P 500 »). Les coupures que les motifs ne
 * trouvent pas sont données à la main, dans une liste unique, `EXCEPTIONS`.
 *
 * Ce module ne fait que poser les coupures qu'on lui donne : les motifs, une
 * dépendance de développement, ne servent qu'au build
 * (`coupuresAuBuild.ts`). La source ne change pas : retirées, les coupures
 * rendent le fichier tel qu'il est écrit (`coupures.test.ts`).
 */

/** La coupure conditionnelle, U+00AD : invisible, sauf en fin de ligne, où elle s'écrit « - ». */
export const COUPURE = String.fromCharCode(0xad)

/** Au moins deux lettres avant une coupure. */
export const AVANT = 2

/** Au moins trois lettres après une coupure. */
export const APRES = 3

export type LangueDesCoupures = 'fr' | 'en'

/**
 * Les coupures données à la main, en forme `ar-ranged`, pour un mot que les
 * motifs de sa langue ne coupent pas.
 */
export const EXCEPTIONS: Readonly<Record<LangueDesCoupures, readonly string[]>> = {
  fr: [],
  // Les motifs anglais ne coupent pas « arranged » : sans dictionnaire, une
  // ligne de « Parametric VaR » s'ouvrait à 2,59 fois l'espace normale.
  en: ['ar-ranged'],
}

/** Un mot : des lettres et des chiffres, d'un seul tenant. */
const MOT = /[\p{L}\p{N}]+/gu

/** Ce qui rend un mot insécable : une capitale ou un chiffre. */
const INSECABLE = /[\p{Lu}\p{N}]/u

/**
 * Ce que la coupure ne touche pas dans un paragraphe : une formule en ligne,
 * un lien, son texte compris, une entité.
 */
const PROTEGE = /(\$[^$]*\$|\[[^\][]*\]\(#[^)]*\)|&[#a-zA-Z0-9]+;)/

/** La première ligne d'un bloc qui n'est pas un paragraphe : titre, formule en bloc, liste. */
const AUTRE_BLOC = /^(?:#|\$\$|- )/

/** Un mot se coupe-t-il ? Pas s'il porte une capitale ou un chiffre. */
export function secable(mot: string): boolean {
  return !INSECABLE.test(mot)
}

/**
 * Les coupures d'un mot, ramenées aux longueurs minimales : celles qui
 * laisseraient moins de deux lettres avant elles, ou moins de trois après,
 * sont retirées.
 */
export function borner(coupe: string): string {
  const morceaux = coupe.split(COUPURE)
  const total = [...morceaux.join('')].length
  let rendu = ''
  let avant = 0
  for (const [rang, morceau] of morceaux.entries()) {
    rendu += morceau
    avant += [...morceau].length
    const derniere = rang === morceaux.length - 1
    if (!derniere && avant >= AVANT && total - avant >= APRES) rendu += COUPURE
  }
  return rendu
}

/** Le texte d'un paragraphe, ses mots coupés hors de ce qui est protégé. */
function couperParagraphe(texte: string, couper: (mot: string) => string): string {
  return texte
    .split(PROTEGE)
    .map((morceau, rang) =>
      rang % 2 === 1 ? morceau : morceau.replace(MOT, (mot) => (secable(mot) ? borner(couper(mot)) : mot)),
    )
    .join('')
}

/**
 * Pose les coupures dans les paragraphes d'un contenu (la grammaire de
 * `lib/contenu.ts`). `couper` rend un mot avec ses coupures, U+00AD. Tout le
 * reste du fichier est rendu à l'identique.
 */
export function poserCoupures(source: string, couper: (mot: string) => string): string {
  const sortie: string[] = []
  let bloc: string[] = []
  const vider = () => {
    const [premiere] = bloc
    if (premiere === undefined) return
    const texte = bloc.join('\n')
    sortie.push(AUTRE_BLOC.test(premiere) ? texte : couperParagraphe(texte, couper))
    bloc = []
  }
  for (const ligne of source.split('\n')) {
    if (ligne.trim() === '') {
      vider()
      sortie.push(ligne)
    } else {
      bloc.push(ligne)
    }
  }
  vider()
  return sortie.join('\n')
}
