/**
 * Ce que la page fait défiler, et ce qui reste collant (chantier 7E,
 * DESIGN.md §8.1, §13).
 *
 * Ce qui est vérifié, sur les feuilles de style lues comme fichiers,
 * commentaires blanchis : la page réserve la hauteur du bandeau à ce qu'elle
 * fait défiler (ancres, tabulation) ; les ancres n'y ajoutent que leur écart ;
 * le bandeau ne colle qu'à partir de 900 px ; un titre qui reçoit le focus a
 * la largeur de son texte ; aucun défilement n'est adouci, ni en CSS ni dans
 * le code. Le comportement lui-même se vérifie dans Chrome
 * (`docs/outils/clavier.mjs`, `bandeau-320.mjs`, hors dépôt).
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const SRC = fileURLToPath(new URL('..', import.meta.url))

function sansCommentaires(texte: string): string {
  return texte.replace(/\/\*[\s\S]*?\*\//g, '')
}

function feuille(chemin: string): string {
  return sansCommentaires(readFileSync(join(SRC, chemin), 'utf-8'))
}

/** Le corps de la première règle hors requête dont le sélecteur est exactement `selecteur`. */
function regle(css: string, selecteur: string): string {
  for (const [, tete, corps] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (tete?.trim() === selecteur) return corps ?? ''
  }
  throw new Error(`Règle introuvable : ${selecteur}`)
}

/** Le bloc d'une requête de média, accolades comprises. */
function blocDeMedia(css: string, requete: string): string {
  const debut = css.indexOf(requete)
  if (debut < 0) return ''
  let profondeur = 0
  for (let i = css.indexOf('{', debut); i < css.length; i++) {
    if (css[i] === '{') profondeur++
    if (css[i] === '}') {
      profondeur--
      if (profondeur === 0) return css.slice(debut, i + 1)
    }
  }
  return ''
}

function fichiers(dossier: string, extensions: readonly string[]): string[] {
  return readdirSync(dossier, { withFileTypes: true }).flatMap((entree) => {
    const chemin = join(dossier, entree.name)
    if (entree.isDirectory()) return fichiers(chemin, extensions)
    return extensions.some((extension) => entree.name.endsWith(extension)) ? [chemin] : []
  })
}

const COLLANT = /position\s*:\s*sticky/

describe('la page réserve la hauteur du bandeau', () => {
  it('`html` porte un scroll-padding sur --hauteur-bandeau', () => {
    const css = feuille('styles/reset.css')
    // Toutes les règles dont le sélecteur est `html` : il y en a deux.
    const regles = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
      .filter((m) => m[1]?.trim() === 'html')
      .map((m) => m[2] ?? '')
    expect(regles.join(' ')).toMatch(/scroll-padding-block-start\s*:\s*var\(--hauteur-bandeau/)
  })

  it("les ancres n'y ajoutent que leur écart, sans recompter le bandeau", () => {
    const section = regle(feuille('components/Section.module.css'), '.section')
    expect(section).toMatch(/scroll-margin-block-start\s*:\s*var\(--space-4\)/)
    expect(section).not.toContain('--hauteur-bandeau')
    const methodologie = regle(feuille('views/Methodologie.module.css'), '.titrePartie,\n.entree')
    expect(methodologie).toMatch(/scroll-margin-block-start\s*:\s*var\(--space-4\)/)
    expect(methodologie).not.toContain('--hauteur-bandeau')
  })
})

describe('le bandeau ne colle qu’à partir de 900 px', () => {
  const css = feuille('components/Bandeau.module.css')

  it('hors requête, il défile avec la page', () => {
    expect(regle(css, '.bandeau')).not.toMatch(COLLANT)
  })

  it('à partir de 900 px, il colle en haut', () => {
    const large = blocDeMedia(css, '@media (width >= 900px)')
    expect(large).toContain('.bandeau')
    expect(large).toMatch(COLLANT)
    expect(css.replace(large, '')).not.toMatch(COLLANT)
  })
})

describe('un titre qui reçoit le focus a la largeur de son texte', () => {
  it.each([
    ['views/Pages.module.css', '.titre'],
    ['components/Section.module.css', '.titre'],
    ['views/Acceptation.module.css', '.titre'],
    ['components/charts/Graphique.module.css', '.ouvrir'],
  ])('%s %s', (chemin, selecteur) => {
    expect(regle(feuille(chemin), selecteur)).toMatch(/inline-size\s*:\s*fit-content/)
  })
})

describe('aucun défilement adouci', () => {
  it('ni en CSS', () => {
    for (const chemin of fichiers(SRC, ['.css'])) {
      expect(sansCommentaires(readFileSync(chemin, 'utf-8')), chemin).not.toMatch(/scroll-behavior\s*:\s*smooth/)
    }
  })

  it('ni dans le code', () => {
    for (const chemin of fichiers(SRC, ['.ts', '.tsx']).filter((c) => !c.endsWith('.test.ts'))) {
      expect(sansCommentaires(readFileSync(chemin, 'utf-8')), chemin).not.toMatch(/behavior\s*:\s*['"]smooth/)
    }
  })
})
