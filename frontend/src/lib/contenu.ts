/**
 * Le lecteur des contenus rédigés : la page méthodologie (chantier 7B.3b).
 *
 * ═══ UN MARKDOWN RESTREINT, ET RIEN D'AUTRE ═══
 *
 * Un contenu est un fichier `.md` par langue (`src/contenu/`), importé brut
 * (`?raw`) et lu ici. La grammaire est FERMÉE : onze constructions, et tout
 * ce qui en sort est une erreur, levée avec son numéro de ligne. Une
 * bibliothèque Markdown aurait tout accepté, rendu du HTML à injecter, et ne
 * savait ni les ancres fixes ni les formules.
 *
 *   # Titre                    une fois, en tête : le titre de la page
 *   ## Titre {#ancre}          une partie, que liste le rail
 *   ### Titre {#ancre}         une entrée, dans une partie
 *   lignes consécutives        un paragraphe
 *   **Étiquette.** texte       une étiquette, en tête de paragraphe ou d'élément
 *   - élément                  une liste, un élément par ligne
 *   $$formule$$                une formule en bloc, seule sur sa ligne
 *   $formule$                  une formule dans le texte
 *   _{…}  ^{…}                 un indice, un exposant, dans une formule
 *   [texte](#ancre)            un lien vers une ancre du contenu
 *   &nbsp; &#x202F; &#x2060;   U+00A0, U+202F, U+2060
 *
 * Les blocs sont séparés par une ligne vide. Pas de HTML, pas d'italique, pas
 * de tableau, pas de lien externe, pas d'image, pas de liste numérotée,
 * aucune autre entité.
 *
 * ═══ CE QUE LE LECTEUR NE FAIT PAS ═══
 *
 * Il ne pose aucune typographie : les espaces insécables sont ÉCRITES dans la
 * source, en entités, et vérifiées par `tests/test_methodologie.py`, comme le
 * JSX écrit `&nbsp;`. Il ne rend aucun HTML : il rend des blocs typés, que la
 * vue compose en éléments React.
 */
import { ESPACE_FINE, ESPACE_INSECABLE } from './format'

/** Le caractère de liaison, invisible : une date ou une paire ne se coupe pas. */
const LIAISON = String.fromCharCode(0x2060)

/** Les trois entités admises, et ce qu'elles valent. */
const ENTITES: ReadonlyMap<string, string> = new Map([
  ['&nbsp;', ESPACE_INSECABLE],
  ['&#x202F;', ESPACE_FINE],
  ['&#x2060;', LIAISON],
])

/** Une ancre : des minuscules et des chiffres, des traits d'union entre eux. */
const ANCRE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

/** Hors des constructions qui les emploient, ces caractères sont refusés. */
const RESERVES = /[*_`<>|\\{}~\]]/

/** Le début d'une ligne de paragraphe qui serait une autre construction. */
const DEBUT_INTERDIT = /^(?:#|- |\* |\+ |>|\||\d+[.)] |```|\$\$)/

export type Position = 'ligne' | 'indice' | 'exposant'

/** Un morceau de formule : en ligne, en indice ou en exposant. */
export interface Morceau {
  readonly texte: string
  readonly position: Position
}

export type EnLigne =
  | { readonly type: 'texte'; readonly texte: string }
  | { readonly type: 'formule'; readonly morceaux: readonly Morceau[] }
  | { readonly type: 'lien'; readonly cible: string; readonly contenu: readonly EnLigne[] }

/** Un élément de liste, ou le corps d'un paragraphe : une étiquette éventuelle, puis le texte. */
export interface Corps {
  readonly etiquette: string | null
  readonly contenu: readonly EnLigne[]
}

export type Bloc =
  | {
      readonly type: 'titre'
      readonly niveau: 1 | 2 | 3
      readonly ancre: string | null
      readonly contenu: readonly EnLigne[]
      readonly ligne: number
    }
  | ({ readonly type: 'paragraphe'; readonly ligne: number } & Corps)
  | { readonly type: 'liste'; readonly elements: readonly Corps[]; readonly ligne: number }
  | { readonly type: 'formule'; readonly morceaux: readonly Morceau[]; readonly ligne: number }

/** Une partie du contenu, telle que le rail la propose. */
export interface Partie {
  readonly ancre: string
  readonly titre: string
}

export interface Contenu {
  /** Le texte du titre de la page, le `#`. */
  readonly titre: string
  readonly blocs: readonly Bloc[]
  /** Les parties (`##`), dans l'ordre. */
  readonly parties: readonly Partie[]
  /** Toutes les ancres, parties et entrées, dans l'ordre. */
  readonly ancres: readonly string[]
}

export class ErreurDeContenu extends Error {
  readonly ligne: number

  constructor(ligne: number, message: string) {
    super(`Ligne ${ligne}, ${message}`)
    this.name = 'ErreurDeContenu'
    this.ligne = ligne
  }
}

function decoder(texte: string, ligne: number): string {
  return texte.replace(/&[#a-zA-Z0-9]+;/g, (entite) => {
    const caractere = ENTITES.get(entite)
    if (caractere === undefined) throw new ErreurDeContenu(ligne, `entité refusée ${entite}.`)
    return caractere
  })
}

/** Le texte brut d'une suite d'éléments en ligne, formules comprises. */
export function texteDe(contenu: readonly EnLigne[]): string {
  return contenu
    .map((element) => {
      if (element.type === 'texte') return element.texte
      if (element.type === 'formule') return element.morceaux.map((m) => m.texte).join('')
      return texteDe(element.contenu)
    })
    .join('')
}

function lireFormule(source: string, ligne: number): Morceau[] {
  const morceaux: Morceau[] = []
  const pousser = (texte: string, position: Position) => {
    if (texte === '') return
    const precedent = morceaux[morceaux.length - 1]
    if (precedent !== undefined && precedent.position === position) {
      morceaux[morceaux.length - 1] = { texte: precedent.texte + texte, position }
    } else {
      morceaux.push({ texte, position })
    }
  }
  let i = 0
  while (i < source.length) {
    const c = source.charAt(i)
    if (c === '_' || c === '^') {
      if (source.charAt(i + 1) !== '{') {
        throw new ErreurDeContenu(ligne, `${c} sans accolade dans une formule.`)
      }
      const fin = source.indexOf('}', i + 2)
      const dedans = fin === -1 ? '' : source.slice(i + 2, fin)
      if (fin === -1 || dedans === '' || /[{}_^]/.test(dedans)) {
        throw new ErreurDeContenu(ligne, 'indice ou exposant mal formé dans une formule.')
      }
      pousser(decoder(dedans, ligne), c === '_' ? 'indice' : 'exposant')
      i = fin + 1
      continue
    }
    if (c === '{' || c === '}') {
      throw new ErreurDeContenu(ligne, `accolade hors d'un indice ou d'un exposant.`)
    }
    pousser(c, 'ligne')
    i += 1
  }
  if (morceaux.length === 0) throw new ErreurDeContenu(ligne, 'formule vide.')
  return morceaux.map((m) => (m.position === 'ligne' ? { ...m, texte: decoder(m.texte, ligne) } : m))
}

function lireEnLigne(texte: string, ligne: number, liensPermis: boolean): EnLigne[] {
  const resultat: EnLigne[] = []
  let tampon = ''
  const vider = () => {
    if (tampon !== '') resultat.push({ type: 'texte', texte: decoder(tampon, ligne) })
    tampon = ''
  }
  let i = 0
  while (i < texte.length) {
    const c = texte.charAt(i)
    if (c === '$') {
      const fin = texte.indexOf('$', i + 1)
      if (fin === -1) throw new ErreurDeContenu(ligne, 'formule non fermée.')
      vider()
      resultat.push({ type: 'formule', morceaux: lireFormule(texte.slice(i + 1, fin), ligne) })
      i = fin + 1
      continue
    }
    if (c === '[') {
      if (!liensPermis) throw new ErreurDeContenu(ligne, 'lien dans un titre ou dans un lien.')
      const lien = /^\[([^\][]+)\]\(#([^)]*)\)/.exec(texte.slice(i))
      if (lien === null) {
        throw new ErreurDeContenu(ligne, "crochet qui n'ouvre pas un lien vers une ancre.")
      }
      const cible = lien[2] ?? ''
      if (!ANCRE.test(cible)) throw new ErreurDeContenu(ligne, `ancre mal formée #${cible}.`)
      vider()
      resultat.push({ type: 'lien', cible, contenu: lireEnLigne(lien[1] ?? '', ligne, false) })
      i += lien[0].length
      continue
    }
    if (RESERVES.test(c)) throw new ErreurDeContenu(ligne, `caractère réservé ${c}.`)
    tampon += c
    i += 1
  }
  vider()
  return resultat
}

/** Une étiquette en tête (`**Hypothèses.**`), puis le texte. */
function lireCorps(texte: string, ligne: number): Corps {
  const etiquette = /^\*\*([^*]+)\*\*/.exec(texte)
  if (etiquette === null) return { etiquette: null, contenu: lireEnLigne(texte, ligne, true) }
  return {
    etiquette: decoder(etiquette[1] ?? '', ligne),
    contenu: lireEnLigne(texte.slice(etiquette[0].length), ligne, true),
  }
}

function lireTitre(texte: string, ligne: number): Bloc {
  const titre = /^(#+) (\S.*?)(?: \{#([^}]*)\})?$/.exec(texte)
  const niveau = titre?.[1]?.length ?? 0
  if (titre === null || niveau > 3) throw new ErreurDeContenu(ligne, 'titre mal formé.')
  const ancre = titre[3] ?? null
  if (niveau === 1 && ancre !== null) {
    throw new ErreurDeContenu(ligne, "le titre de la page n'a pas d'ancre.")
  }
  if (niveau > 1 && (ancre === null || !ANCRE.test(ancre))) {
    throw new ErreurDeContenu(ligne, 'une partie ou une entrée demande une ancre {#ancre}.')
  }
  return {
    type: 'titre',
    niveau: niveau as 1 | 2 | 3,
    ancre,
    contenu: lireEnLigne(titre[2] ?? '', ligne, false),
    ligne,
  }
}

function lireBloc(lignes: readonly string[], debut: number): Bloc {
  const [premiere = '', ...suite] = lignes
  if (premiere.startsWith('#')) {
    if (suite.length > 0) throw new ErreurDeContenu(debut, 'un titre est seul dans son bloc.')
    return lireTitre(premiere, debut)
  }
  if (premiere.startsWith('$$')) {
    const formule = /^\$\$(.+)\$\$$/.exec(premiere)
    if (formule === null || suite.length > 0) {
      throw new ErreurDeContenu(debut, 'une formule en bloc tient seule sur sa ligne.')
    }
    return { type: 'formule', morceaux: lireFormule(formule[1] ?? '', debut), ligne: debut }
  }
  if (premiere.startsWith('- ')) {
    return {
      type: 'liste',
      elements: lignes.map((element, rang) => {
        if (!element.startsWith('- ')) {
          throw new ErreurDeContenu(debut + rang, "une liste n'a que des éléments.")
        }
        return lireCorps(element.slice(2), debut + rang)
      }),
      ligne: debut,
    }
  }
  lignes.forEach((texte, rang) => {
    if (DEBUT_INTERDIT.test(texte)) {
      throw new ErreurDeContenu(debut + rang, 'construction refusée en tête de ligne.')
    }
  })
  return { type: 'paragraphe', ...lireCorps(lignes.join(' '), debut), ligne: debut }
}

function liensDe(contenu: readonly EnLigne[]): { cible: string }[] {
  return contenu.flatMap((element) => (element.type === 'lien' ? [element] : []))
}

/**
 * Lit un contenu. Lève `ErreurDeContenu` sur la première construction hors de
 * la grammaire, sur une ancre en double et sur un lien sans ancre.
 */
export function lireContenu(source: string): Contenu {
  const lignes = source.replace(/\r\n?/g, '\n').split('\n')
  const bruts: { debut: number; lignes: string[] }[] = []
  let courant: { debut: number; lignes: string[] } | null = null
  for (let rang = 0; rang < lignes.length; rang += 1) {
    const texte = lignes[rang] ?? ''
    if (texte.trim() === '') {
      if (courant !== null) bruts.push(courant)
      courant = null
      continue
    }
    if (/^\s|\s$/.test(texte)) {
      throw new ErreurDeContenu(rang + 1, 'blanc en début ou en fin de ligne.')
    }
    if (courant === null) courant = { debut: rang + 1, lignes: [] }
    courant.lignes.push(texte)
  }
  if (courant !== null) bruts.push(courant)

  const blocs = bruts.map((brut) => lireBloc(brut.lignes, brut.debut))
  const [tete, ...reste] = blocs
  if (tete === undefined || tete.type !== 'titre' || tete.niveau !== 1) {
    throw new ErreurDeContenu(1, 'le contenu commence par son titre, #.')
  }

  const parties: Partie[] = []
  const ancres: string[] = []
  for (const bloc of reste) {
    if (bloc.type !== 'titre') continue
    if (bloc.niveau === 1) throw new ErreurDeContenu(bloc.ligne, 'un seul titre de page.')
    if (bloc.niveau === 3 && parties.length === 0) {
      throw new ErreurDeContenu(bloc.ligne, "une entrée appartient à une partie, ## d'abord.")
    }
    const ancre = bloc.ancre ?? ''
    if (ancres.includes(ancre)) throw new ErreurDeContenu(bloc.ligne, `ancre en double #${ancre}.`)
    ancres.push(ancre)
    if (bloc.niveau === 2) parties.push({ ancre, titre: texteDe(bloc.contenu) })
  }

  for (const bloc of blocs) {
    const contenus =
      bloc.type === 'paragraphe'
        ? [bloc.contenu]
        : bloc.type === 'liste'
          ? bloc.elements.map((element) => element.contenu)
          : []
    for (const lien of contenus.flatMap(liensDe)) {
      if (!ancres.includes(lien.cible)) {
        throw new ErreurDeContenu(bloc.ligne, `lien vers une ancre absente #${lien.cible}.`)
      }
    }
  }

  return { titre: texteDe(tete.contenu), blocs, parties, ancres }
}
