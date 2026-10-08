/**
 * La ponctuation haute — « : », « ; », « ? », « ! » — et les guillemets des
 * textes que le FRONTEND écrit lui-même — DESIGN.md §6.3.
 *
 * Le backend compose les siens à la publication (`typography.prose`, vérifié
 * par `tests/test_textes_publies.py`). Ceux du frontend sont dans son code : une
 * phrase de `phrases.ts`, une ligne de provenance, un paragraphe JSX. Avec une
 * espace ordinaire avant « : », le deux-points part seul en début de ligne :
 * « Colonnes obligatoires » finissait une ligne que « : ticker » commençait.
 *
 * ═══ POURQUOI LE COMPILATEUR, ET PAS UNE EXPRESSION RÉGULIÈRE ═══
 *
 * Le code TypeScript est plein de « : » précédés d'une espace : chaque
 * ternaire `a ? b : c`. Une recherche sur le texte du fichier se déclencherait
 * partout. Le compilateur, lui, sait ce qui est une CHAÎNE (littérale, gabarit)
 * et ce qui est du TEXTE JSX : seuls ceux-là sont lus. Pour une chaîne, c'est sa
 * valeur qui compte — «   » écrit dans le code y vaut une espace
 * insécable ; pour le JSX, son texte brut, où « &nbsp; » en vaut une.
 *
 * ═══ AUCUN TIRET CADRATIN, ET UN SEUL TIRET ISOLÉ ═══
 *
 * L'interface n'emploie aucun tiret cadratin (U+2014), sans exception
 * (DESIGN.md §6.3, décision du 2026-10-05) : ni dans une chaîne, ni dans le
 * JSX, ni dans un `content:` de feuille de style, ni dans `index.html`. Le
 * backend tient la même règle (`tests/test_textes_publies.py`).
 *
 * Le seul tiret isolé est celui d'une valeur absente : un tiret court, écrit
 * par `<Absent>` avec le texte qu'un lecteur d'écran lit à sa place. Le
 * poser à la main dans du JSX l'afficherait sans ce texte.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const RACINE = join(import.meta.dirname, '..')

/**
 * Une espace ORDINAIRE avant « : », « ; », « ? » ou « ! » suivi d'un blanc ou de
 * la fin, après « « », avant « » ». Le motif est celui de `typography.prose`.
 */
const ESPACE_ORDINAIRE = / [:;?!](?=\s|$)|« | »/

/** Le tiret cadratin, écrit tel quel, échappé, ou en entité HTML. */
const CADRATIN = /\u2014|&mdash;|&#8212;|&#x2014;/i

/** Le tiret d'une valeur absente, seul dans son texte. */
const TIRET_ISOLE = /^\s*(?:\u2013|&ndash;|&#8211;|&#x2013;)\s*$/i

/** Les deux seuls fichiers qui écrivent ce tiret : sa constante, son composant. */
const ECRIVENT_LE_TIRET = ['lib/format.ts', 'components/Absent.tsx']

function fichiers(dossier: string, motif = /\.tsx?$/): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((entree) => {
    const chemin = join(dossier, entree.name)
    if (entree.isDirectory()) return fichiers(chemin, motif)
    if (!motif.test(entree.name)) return []
    // Les tests citent les textes qu'ils attendent, bons ou fautifs ; le schéma
    // engendré recopie les descriptions du backend, jamais affichées.
    if (/\.test\.tsx?$/.test(entree.name) || entree.name === 'schema.ts') return []
    return [chemin]
  })
}

interface Faute {
  readonly ou: string
  readonly texte: string
}

/** Une espace d'un seul blanc écrite en expression JSX : `{' '}`. */
function estBlancEnExpression(noeud: ts.Node | undefined): boolean {
  return (
    noeud !== undefined &&
    ts.isJsxExpression(noeud) &&
    noeud.expression !== undefined &&
    ts.isStringLiteral(noeud.expression) &&
    noeud.expression.text.endsWith(' ')
  )
}

function fautesDuCode(code: string, chemin: string): Faute[] {
  const relatif = relative(RACINE, chemin).replaceAll('\\', '/')
  const ecritLeTiret = ECRIVENT_LE_TIRET.includes(relatif)
  const source = ts.createSourceFile(
    chemin,
    code,
    ts.ScriptTarget.Latest,
    true,
    chemin.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  const fautes: Faute[] = []
  const signaler = (noeud: ts.Node, texte: string) => {
    const { line } = source.getLineAndCharacterOfPosition(noeud.getStart(source))
    fautes.push({ ou: `${relative(RACINE, chemin)}:${line + 1}`, texte: texte.trim().slice(0, 70) })
  }
  const visiter = (noeud: ts.Node): void => {
    // Une espace écrite en expression — « {' '}; facultative » — échappe à la
    // lecture des textes : elle est seule dans sa chaîne, et le signe ouvre le
    // texte JSX suivant. On regarde donc les voisins.
    if (ts.isJsxElement(noeud) || ts.isJsxFragment(noeud)) {
      noeud.children.forEach((enfant, rang) => {
        const texteJsx = ts.isJsxText(enfant) ? source.text.slice(enfant.pos, enfant.end) : ''
        if (/^[:;?!»]/.test(texteJsx) && estBlancEnExpression(noeud.children[rang - 1])) {
          signaler(enfant, `{' '}${texteJsx}`)
        }
      })
    }
    let texte: string | null = null
    // Le texte JSX et les attributs JSX se lisent bruts : « &nbsp; » y est une
    // entité, et un attribut n'interprète pas les échappements JS. Le texte JSX
    // se lit depuis `pos` : `getStart` en sauterait l'espace de tête, celle
    // de « {nom} » ».
    if (ts.isJsxText(noeud)) texte = source.text.slice(noeud.pos, noeud.end)
    else if (ts.isStringLiteral(noeud) && ts.isJsxAttribute(noeud.parent)) {
      texte = noeud.getText(source)
    } else if (
      ts.isStringLiteral(noeud) ||
      ts.isNoSubstitutionTemplateLiteral(noeud) ||
      ts.isTemplateHead(noeud) ||
      ts.isTemplateMiddle(noeud) ||
      ts.isTemplateTail(noeud)
    ) {
      texte = noeud.text
    }
    if (texte !== null && ESPACE_ORDINAIRE.test(texte)) signaler(noeud, texte)
    if (texte !== null && CADRATIN.test(texte)) signaler(noeud, `tiret cadratin\u00a0: ${texte}`)
    if (texte !== null && !ecritLeTiret && TIRET_ISOLE.test(texte)) {
      signaler(noeud, 'tiret isolé\u00a0: une valeur absente s’écrit <Absent />')
    }
    // Le tiret d'indéfini posé à la main s'afficherait sans son texte de
    // lecteur d'écran : dans un gabarit (`${TIRET_INDEFINI} non couverte`), ou
    // n'importe où dans une expression ENFANT d'un élément JSX, ternaire
    // compris. Passé en attribut à un composant, il est rendu par
    // `avecAbsence` : c'est le seul chemin admis.
    if (!ecritLeTiret && ts.isIdentifier(noeud) && noeud.text === 'TIRET_INDEFINI') {
      let parent: ts.Node | undefined = noeud.parent
      while (parent !== undefined && !ts.isJsxExpression(parent) && !ts.isTemplateSpan(parent)) {
        parent = parent.parent
      }
      const affiche =
        parent !== undefined &&
        (ts.isTemplateSpan(parent) ||
          ts.isJsxElement(parent.parent) ||
          ts.isJsxFragment(parent.parent))
      if (affiche) signaler(noeud, 'TIRET_INDEFINI affiché sans <Absent />')
    }
    ts.forEachChild(noeud, visiter)
  }
  visiter(source)
  return fautes
}

function fautesDe(chemin: string): Faute[] {
  return fautesDuCode(readFileSync(chemin, 'utf-8'), chemin)
}

/**
 * Une feuille de style ou `index.html`, HORS COMMENTAIRES : un `content:` ou
 * un `<title>` s'affiche, un commentaire non.
 */
function cadratinsHorsCommentaires(texte: string): string[] {
  const affiche = texte.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')
  return affiche.split('\n').filter((ligne) => CADRATIN.test(ligne))
}

describe('la garde', () => {
  // Les témoins passent par la MÊME lecture que les fichiers du projet.
  const temoin = (code: string) => fautesDuCode(code, join(RACINE, 'temoin.tsx')).length > 0

  it('voit une espace ordinaire dans une chaîne et dans le JSX', () => {
    expect(temoin(`const a = 'Contrôle : indisponible'`)).toBe(true)
    expect(temoin(`const b = <p>Colonnes obligatoires :</p>`)).toBe(true)
    expect(temoin(`const c = 'le séparateur « ; »'`)).toBe(true)
    expect(temoin(`const d = <span>de «&nbsp;{nom} »</span>`)).toBe(true)
    expect(temoin(`const e = 'capital ; risque'`)).toBe(true)
    expect(temoin(`const f = <p>Supprimer ce portefeuille ?</p>`)).toBe(true)
    expect(temoin(`const g = 'Attention !'`)).toBe(true)
    expect(temoin(`const h = <p>quantity{' '}; facultative</p>`)).toBe(true)
  })

  it('laisse passer les ternaires, l’espace insécable et les heures', () => {
    expect(temoin(`const a = vrai ? 'oui' : 'non'`)).toBe(false)
    expect(temoin(`const b = <p>Colonnes obligatoires&nbsp;:</p>`)).toBe(false)
    expect(temoin(`const c = 'Contrôle\\u00a0: indisponible'`)).toBe(false)
    expect(temoin(`const d = 'à 10:30'`)).toBe(false)
    expect(temoin(`const e = 'capital\\u00a0; risque'`)).toBe(false)
    expect(temoin(`const f = <p>Supprimer ce portefeuille&nbsp;?</p>`)).toBe(false)
    expect(temoin(`const g = 'si x != y'`)).toBe(false)
    expect(temoin(`const h = <p>quantity&nbsp;; facultative</p>`)).toBe(false)
    expect(temoin(`const i = <p>valeur{' '}<b>forte</b></p>`)).toBe(false)
  })
})

describe('la garde du tiret cadratin', () => {
  const fautes = (code: string, fichier = 'temoin.tsx') =>
    fautesDuCode(code, join(RACINE, fichier)).map((faute) => faute.texte)

  it('le voit dans une chaîne, un gabarit, le JSX, un attribut, une entité', () => {
    expect(fautes(`const a = 'Ligne 4 \u2014 Ticker inconnu'`)).toHaveLength(1)
    expect(fautes('const b = `${titre} \u2014 Mx Risk MGT`')).toHaveLength(1)
    expect(fautes(`const c = <p>un fichier CSV \u2014 par exemple</p>`)).toHaveLength(1)
    expect(fautes(`const d = <button aria-label="Thème clair \u2014 actuellement sombre" />`)).toHaveLength(1)
    expect(fautes(`const e = <p>en crise &mdash; jamais moyennées</p>`)).toHaveLength(1)
    expect(fautes(`const f = '\\u2014'`)).toHaveLength(1)
  })

  it('laisse passer le tiret court d’une paire, le signe moins et la flèche', () => {
    expect(fautes(`const a = 'corrélation JNJ\u2013KO'`)).toEqual([])
    expect(fautes(`const b = '\u22123'`)).toEqual([])
    expect(fautes(`const c = <p>2024-09-05 → 2026-09-09</p>`)).toEqual([])
    // Un commentaire n'est pas affiché : il n'est pas lu.
    expect(fautes(`// un rang \u2014 par exemple\nconst d = 1`)).toEqual([])
  })

  it('refuse le tiret d’une valeur absente posé à la main', () => {
    expect(fautes(`const a = <td>\u2013</td>`)).toHaveLength(1)
    expect(fautes(`const b = <td>{vide ? '\u2013' : nom}</td>`)).toHaveLength(1)
    expect(fautes(`const c = <span>{TIRET_INDEFINI}</span>`)).toHaveLength(1)
    expect(fautes('const d = `${TIRET_INDEFINI} non couverte`')).toHaveLength(1)
    expect(fautes(`const g = <span>{v === null ? TIRET_INDEFINI : dateISO(v)}</span>`)).toHaveLength(1)
    expect(fautes(`const h = <ul>{l.map((v) => <li>{v ?? TIRET_INDEFINI}</li>)}</ul>`)).toHaveLength(1)
    // Passé comme valeur à un composant qui le rend par `avecAbsence`.
    expect(fautes(`const e = <Measure valeur={v === null ? TIRET_INDEFINI : pourcentage(v, 2)} />`)).toEqual([])
    expect(
      fautes(`const i = <DataTable colonnes={[{ cellule: (p) => (p.v === null ? TIRET_INDEFINI : montant(p.v)) }]} />`),
    ).toEqual([])
    expect(fautes(`const j = (v: number | null) => (v === null ? TIRET_INDEFINI : decimal(v, 1))`)).toEqual([])
    // Sa constante et son composant, eux, l'écrivent.
    expect(fautes(`export const TIRET_INDEFINI = '\\u2013'`, 'lib/format.ts')).toEqual([])
    expect(fautes(`const f = <span aria-hidden="true">{TIRET_INDEFINI}</span>`, 'components/Absent.tsx')).toEqual([])
  })

  it('lit les feuilles de style et index.html hors commentaires', () => {
    expect(cadratinsHorsCommentaires(`.refus::before {\n  content: '\u2014 ' / '';\n}`)).toHaveLength(1)
    expect(cadratinsHorsCommentaires(`/* 12px \u2014 unités */\n.a { color: red; }`)).toEqual([])
    expect(cadratinsHorsCommentaires(`<!-- §4 \u2014 obligatoire -->\n<title>Mx Risk MGT</title>`)).toEqual([])
    expect(cadratinsHorsCommentaires(`<title>Analyse \u2014 Mx Risk MGT</title>`)).toHaveLength(1)
  })
})

describe('les textes du frontend', () => {
  it('n’ont aucune espace ordinaire avant « : », « ; », « ? », « ! » ni dans des guillemets, aucun tiret cadratin, aucun tiret isolé', () => {
    const fautes = fichiers(RACINE).flatMap(fautesDe)
    expect(fautes).toEqual([])
  })

  it('n’affichent aucun tiret cadratin depuis une feuille de style ni depuis index.html', () => {
    const feuilles = fichiers(RACINE, /\.css$/).map((chemin) => ({
      ou: relative(RACINE, chemin),
      lignes: cadratinsHorsCommentaires(readFileSync(chemin, 'utf-8')),
    }))
    const page = {
      ou: 'index.html',
      lignes: cadratinsHorsCommentaires(readFileSync(join(RACINE, '..', 'index.html'), 'utf-8')),
    }
    expect([...feuilles, page].filter((fichier) => fichier.lignes.length > 0)).toEqual([])
  })
})

// ═══════════════════════════════════════════════ Les fichiers anglais (7D) ══

/**
 * Les fichiers anglais du client (chantier 7D) : `libelles.en.ts`,
 * `phrases.en.ts`. L'anglais n'a AUCUNE espace avant « : », « ; », « ? »
 * ou « ! », ni ordinaire ni insécable, et cite entre guillemets doubles,
 * jamais entre « ». La garde française ci-dessus ne voit que l'espace
 * ordinaire : une insécable posée par erreur en anglais lui échapperait.
 */
const FICHIER_ANGLAIS = /\.en\.tsx?$/
const PONCTUATION_ANGLAISE = /\s[:;?!](?=\s|$)|[«»]/

/** Les valeurs des chaînes et des gabarits d'un fichier, lues par le compilateur. */
function chainesDe(code: string, chemin: string): string[] {
  const source = ts.createSourceFile(chemin, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const chaines: string[] = []
  const visiter = (noeud: ts.Node): void => {
    if (
      ts.isStringLiteral(noeud) ||
      ts.isNoSubstitutionTemplateLiteral(noeud) ||
      ts.isTemplateHead(noeud) ||
      ts.isTemplateMiddle(noeud) ||
      ts.isTemplateTail(noeud)
    ) {
      chaines.push(noeud.text)
    }
    ts.forEachChild(noeud, visiter)
  }
  visiter(source)
  return chaines
}

function fautesAnglaises(code: string, chemin: string): string[] {
  return chainesDe(code, chemin).filter((texte) => PONCTUATION_ANGLAISE.test(texte))
}

describe('les textes anglais du frontend', () => {
  const anglais = fichiers(RACINE).filter((chemin) => FICHIER_ANGLAIS.test(chemin))

  it('existent : un glob vide passerait au vert', () => {
    expect(anglais.map((chemin) => relative(RACINE, chemin).replaceAll('\\', '/'))).toContain(
      'contenu/libelles.en.ts',
    )
  })

  it('n’ont aucune espace avant « : », « ; », « ? », « ! », ni guillemet français', () => {
    const fautes = anglais.flatMap((chemin) =>
      fautesAnglaises(readFileSync(chemin, 'utf-8'), chemin).map(
        (texte) => `${relative(RACINE, chemin)} : ${texte.slice(0, 70)}`,
      ),
    )
    expect(fautes).toEqual([])
  })

  it('la garde voit l’espace, ordinaire comme insécable, et le guillemet français', () => {
    const temoin = (code: string) => fautesAnglaises(code, 'temoin.en.ts').length > 0
    expect(temoin(`const a = 'Threshold : 0.70'`)).toBe(true)
    expect(temoin(`const b = 'Threshold\\u00a0: 0.70'`)).toBe(true)
    expect(temoin('const c = `${n}\\u202f%`')).toBe(false)
    expect(temoin(`const d = '« Demo »'`)).toBe(true)
    expect(temoin(`const e = 'Threshold: 0.70'`)).toBe(false)
    expect(temoin(`const f = 'Delete “Demo”?'`)).toBe(false)
    expect(temoin(`const g = vrai ? 'yes' : 'no'`)).toBe(false)
  })
})
