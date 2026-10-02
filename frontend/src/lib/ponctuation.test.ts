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

function fichiers(dossier: string): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((entree) => {
    const chemin = join(dossier, entree.name)
    if (entree.isDirectory()) return fichiers(chemin)
    if (!/\.tsx?$/.test(entree.name)) return []
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

function fautesDe(chemin: string): Faute[] {
  const source = ts.createSourceFile(
    chemin,
    readFileSync(chemin, 'utf-8'),
    ts.ScriptTarget.Latest,
    true,
    chemin.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  const fautes: Faute[] = []
  const visiter = (noeud: ts.Node): void => {
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
    if (texte !== null && ESPACE_ORDINAIRE.test(texte)) {
      const { line } = source.getLineAndCharacterOfPosition(noeud.getStart(source))
      fautes.push({
        ou: `${relative(RACINE, chemin)}:${line + 1}`,
        texte: texte.trim().slice(0, 70),
      })
    }
    ts.forEachChild(noeud, visiter)
  }
  visiter(source)
  return fautes
}

describe('la garde', () => {
  const temoin = (code: string, nom = 'temoin.tsx') => {
    const source = ts.createSourceFile(nom, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const textes: string[] = []
    const visiter = (noeud: ts.Node): void => {
      if (ts.isJsxText(noeud)) textes.push(source.text.slice(noeud.pos, noeud.end))
      else if (ts.isStringLiteral(noeud) || ts.isNoSubstitutionTemplateLiteral(noeud)) {
        textes.push(noeud.text)
      }
      ts.forEachChild(noeud, visiter)
    }
    visiter(source)
    return textes.some((texte) => ESPACE_ORDINAIRE.test(texte))
  }

  it('voit une espace ordinaire dans une chaîne et dans le JSX', () => {
    expect(temoin(`const a = 'Contrôle : indisponible'`)).toBe(true)
    expect(temoin(`const b = <p>Colonnes obligatoires :</p>`)).toBe(true)
    expect(temoin(`const c = 'le séparateur « ; »'`)).toBe(true)
    expect(temoin(`const d = <span>de «&nbsp;{nom} »</span>`)).toBe(true)
    expect(temoin(`const e = 'capital ; risque'`)).toBe(true)
    expect(temoin(`const f = <p>Supprimer ce portefeuille ?</p>`)).toBe(true)
    expect(temoin(`const g = 'Attention !'`)).toBe(true)
  })

  it('laisse passer les ternaires, l’espace insécable et les heures', () => {
    expect(temoin(`const a = vrai ? 'oui' : 'non'`)).toBe(false)
    expect(temoin(`const b = <p>Colonnes obligatoires&nbsp;:</p>`)).toBe(false)
    expect(temoin(`const c = 'Contrôle\\u00a0: indisponible'`)).toBe(false)
    expect(temoin(`const d = 'à 10:30'`)).toBe(false)
    expect(temoin(`const e = 'capital\\u00a0; risque'`)).toBe(false)
    expect(temoin(`const f = <p>Supprimer ce portefeuille&nbsp;?</p>`)).toBe(false)
    expect(temoin(`const g = 'si x != y'`)).toBe(false)
  })
})

describe('les textes du frontend', () => {
  it('n’ont aucune espace ordinaire avant « : », « ; », « ? », « ! » ni dans des guillemets', () => {
    const fautes = fichiers(RACINE).flatMap(fautesDe)
    expect(fautes).toEqual([])
  })
})
