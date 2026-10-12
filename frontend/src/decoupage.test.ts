/**
 * Le découpage du bundle — DESIGN.md §19.9 (chantier 9.4).
 *
 * Le fichier d'entrée porte ce que toute page affiche, et rien de ce qui
 * dessine un graphique : seule l'analyse, avec la bibliothèque de graphiques,
 * se charge à la demande. Ce n'est pas laissé à la relecture d'un `import` :
 * un import statique de trop, n'importe où dans ce que charge `main.tsx`,
 * ramènerait tout dans le fichier d'entrée sans qu'aucun écran le montre.
 *
 * Le test suit donc les imports STATIQUES depuis `main.tsx`, lus par le
 * compilateur TypeScript : une recherche de texte prendrait un `import type`,
 * que le compilateur efface, pour un import.
 *
 * Rien ne se découpe par langue (§19.9, point 4) : il n'y a qu'un `import()`
 * dans le client, et les textes des deux langues restent dans l'entrée.
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const RACINE = import.meta.dirname

interface Liens {
  readonly statiques: string[]
  readonly dynamiques: string[]
}

/** Ce qu'un module importe : ce que le bundle lie d'office, et ce qu'il diffère. */
function liens(source: string, nom = 'module.tsx'): Liens {
  const arbre = ts.createSourceFile(nom, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const statiques: string[] = []
  const dynamiques: string[] = []
  const visiter = (noeud: ts.Node): void => {
    if (ts.isImportDeclaration(noeud) && ts.isStringLiteral(noeud.moduleSpecifier)) {
      // `import type { X } from` est effacé ; `import { type X } from` ne l'est
      // pas (`verbatimModuleSyntax`) : il reste un import du module.
      if (noeud.importClause?.isTypeOnly !== true) statiques.push(noeud.moduleSpecifier.text)
    } else if (
      ts.isExportDeclaration(noeud) &&
      noeud.moduleSpecifier !== undefined &&
      ts.isStringLiteral(noeud.moduleSpecifier)
    ) {
      if (!noeud.isTypeOnly) statiques.push(noeud.moduleSpecifier.text)
    } else if (
      ts.isCallExpression(noeud) &&
      noeud.expression.kind === ts.SyntaxKind.ImportKeyword &&
      noeud.arguments[0] !== undefined &&
      ts.isStringLiteralLike(noeud.arguments[0])
    ) {
      dynamiques.push(noeud.arguments[0].text)
    }
    ts.forEachChild(noeud, visiter)
  }
  visiter(arbre)
  return { statiques, dynamiques }
}

const EXTENSIONS = ['', '.ts', '.tsx', '/index.ts', '/index.tsx']

/**
 * Le module que désigne `cible` depuis `depuis` : un fichier de `src`, écrit
 * avec des barres obliques, ou le nom d'un paquet. Un suffixe de Vite
 * (`?raw`) ne change pas le fichier.
 */
function resoudre(depuis: string, cible: string): string {
  const [chemin = cible] = cible.split('?')
  if (!chemin.startsWith('.')) {
    const morceaux = chemin.split('/')
    return chemin.startsWith('@') ? morceaux.slice(0, 2).join('/') : (morceaux[0] ?? chemin)
  }
  const base = join(RACINE, dirname(depuis), chemin)
  for (const extension of EXTENSIONS) {
    const candidat = base + extension
    if (existsSync(candidat) && statSync(candidat).isFile()) {
      return relative(RACINE, candidat).split(sep).join('/')
    }
  }
  throw new Error(`import introuvable : ${cible}, depuis ${depuis}`)
}

const estDuCode = (module: string) => module.endsWith('.ts') || module.endsWith('.tsx')

const lus = new Map<string, Liens>()
function liensDe(module: string): Liens {
  let connus = lus.get(module)
  if (connus === undefined) {
    connus = liens(readFileSync(join(RACINE, module), 'utf-8'), module)
    lus.set(module, connus)
  }
  return connus
}

/** Tout ce qu'un module charge d'office, de proche en proche : fichiers et paquets. */
function atteints(depart: string): Set<string> {
  const vus = new Set<string>([depart])
  const file = [depart]
  for (let module = file.pop(); module !== undefined; module = file.pop()) {
    if (!estDuCode(module) || !existsSync(join(RACINE, module))) continue
    for (const cible of liensDe(module).statiques) {
      const voisin = resoudre(module, cible)
      if (!vus.has(voisin)) {
        vus.add(voisin)
        file.push(voisin)
      }
    }
  }
  return vus
}

/** Les modules du client, tests exclus. */
function modules(dossier = RACINE): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((entree) => {
    const chemin = join(dossier, entree.name)
    if (entree.isDirectory()) return modules(chemin)
    const module = relative(RACINE, chemin).split(sep).join('/')
    return estDuCode(module) && !module.includes('.test.') && !module.endsWith('.d.ts') ? [module] : []
  })
}

const ENTREE = 'main.tsx'
const ANALYSE = 'views/Analyse.tsx'
const GRAPHIQUES = '@observablehq/plot'

describe('le fichier d’entrée', () => {
  const entree = atteints(ENTREE)

  it('ne charge ni l’analyse ni la bibliothèque de graphiques', () => {
    expect(entree.has(ANALYSE)).toBe(false)
    expect(entree.has(GRAPHIQUES)).toBe(false)
    expect([...entree].filter((module) => module.startsWith('components/charts/'))).toEqual([])
    expect([...entree].filter((module) => module.startsWith('views/Section'))).toEqual([])
  })

  it('le parcours voit ce qu’il doit voir : depuis l’analyse, il atteint les graphiques', () => {
    const analyse = atteints(ANALYSE)
    expect(analyse.has(GRAPHIQUES)).toBe(true)
    expect(analyse.has('views/SectionCrise.tsx')).toBe(true)
    // Et depuis l'entrée, ce qu'elle charge vraiment.
    expect(entree.has('App.tsx')).toBe(true)
    expect(entree.has('react')).toBe(true)
  })

  it('garde la méthodologie et les deux langues : rien ne se découpe par langue', () => {
    for (const module of [
      'contenu/methodologie.fr.md',
      'contenu/methodologie.en.md',
      'contenu/libelles.fr.ts',
      'contenu/libelles.en.ts',
      'lib/phrases.fr.ts',
      'lib/phrases.en.ts',
      'views/Methodologie.tsx',
    ]) {
      expect(entree.has(module), module).toBe(true)
    }
  })
})

describe('ce qui se charge à la demande', () => {
  it('un seul import() dans le client, celui de l’analyse', () => {
    const differes = modules().flatMap((module) =>
      liensDe(module).dynamiques.map((cible) => `${module} -> ${resoudre(module, cible)}`),
    )
    expect(differes).toEqual([`views/AnalyseALaDemande.tsx -> ${ANALYSE}`])
  })

  it('le module qui la demande est dans l’entrée, et ne l’importe que pour son type', () => {
    expect(atteints(ENTREE).has('views/AnalyseALaDemande.tsx')).toBe(true)
    expect(liensDe('views/AnalyseALaDemande.tsx').statiques).not.toContain('./Analyse')
  })
})

describe('la lecture des imports', () => {
  it('un import ordinaire est statique, un import de type est effacé', () => {
    expect(liens("import { VueAnalyse } from './views/Analyse'").statiques).toEqual(['./views/Analyse'])
    expect(liens("import type { VueAnalyse } from './views/Analyse'").statiques).toEqual([])
    expect(liens("import './styles/tokens.css'").statiques).toEqual(['./styles/tokens.css'])
    expect(liens("export { VueAnalyse } from './views/Analyse'").statiques).toEqual(['./views/Analyse'])
    expect(liens("export type { Props } from './views/Analyse'").statiques).toEqual([])
  })

  it('un type importé dans une clause ordinaire laisse l’import du module', () => {
    expect(liens("import { type VueAnalyse } from './views/Analyse'").statiques).toEqual([
      './views/Analyse',
    ])
  })

  it('un import() est différé, où qu’il soit écrit', () => {
    const lu = liens("const charger = () => import('./views/Analyse').then((m) => m.VueAnalyse)")
    expect(lu.dynamiques).toEqual(['./views/Analyse'])
    expect(lu.statiques).toEqual([])
  })

  it('un paquet se reconnaît à son nom, sous-chemin et suffixe compris', () => {
    expect(resoudre('App.tsx', '@observablehq/plot')).toBe(GRAPHIQUES)
    expect(resoudre('App.tsx', 'react-dom/client')).toBe('react-dom')
    expect(resoudre('contenu/methodologie.ts', './methodologie.fr.md?raw')).toBe(
      'contenu/methodologie.fr.md',
    )
  })
})
