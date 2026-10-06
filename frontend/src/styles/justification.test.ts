/**
 * La justification de la prose longue — DESIGN.md §6.3, décisions du
 * 2026-10-06.
 *
 * Justifiés à partir de 900 px, avec coupure des mots : les chapeaux, et eux
 * seuls. Tout le reste est aligné à gauche, à toutes les largeurs, et passe
 * en `text-wrap: pretty`.
 *
 * Le reste a été essayé justifié, et mesuré dans Chrome. Les phrases de
 * lecture des mesures et les observations ouvraient des espaces de 2,8 à 4,9
 * fois la normale, à cause des groupes qui ne se coupent pas (un montant, une
 * date en toutes lettres, un nombre et son unité). Les introductions et
 * l'écran d'acceptation tenaient sous 2,5 avec le dictionnaire de césure
 * français, mais montaient à 3,0 et 2,9 sans lui : un visiteur dont le Chrome
 * ne l'a pas encore téléchargé verrait ces trous. Tous restent à gauche ; ce
 * test empêche qu'ils se justifient par mégarde, comme il empêche la
 * justification de passer sous 900 px.
 *
 * Ce qui se voit dans le navigateur, l'espace réelle des lignes justifiées,
 * est vérifié aux captures, par le contrôle automatique qui les accompagne.
 */
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const LARGE = '@media (width >= 900px)'

/** Le CSS sans ses commentaires, qui citent les règles qu'ils expliquent. */
function sansCommentaires(css: string): string {
  return css
    .split('/*')
    .map((morceau, rang) => (rang === 0 ? morceau : morceau.slice(morceau.indexOf('*/') + 2)))
    .join('')
}

/** Chaque bloc d'une requête de média, accolades comprises. */
function blocsDeMedia(css: string, requete: string): string[] {
  const blocs: string[] = []
  for (let debut = css.indexOf(requete); debut >= 0; debut = css.indexOf(requete, debut + 1)) {
    let profondeur = 0
    for (let i = css.indexOf('{', debut); i < css.length; i++) {
      if (css[i] === '{') profondeur++
      if (css[i] === '}') {
        profondeur--
        if (profondeur === 0) {
          blocs.push(css.slice(debut, i + 1))
          break
        }
      }
    }
  }
  return blocs
}

/** Toutes les feuilles de style du client, par chemin relatif à `src/`. */
const FEUILLES = new Map(
  readdirSync(SRC, { recursive: true })
    .map((chemin) => String(chemin).split(path.sep).join('/'))
    .filter((chemin) => chemin.endsWith('.css'))
    .map((chemin) => [chemin, sansCommentaires(readFileSync(path.join(SRC, chemin), 'utf-8'))]),
)

const JUSTIFIE = 'text-align: justify'

describe('la prose longue, justifiée à partir de 900 px', () => {
  it('seuls les chapeaux se justifient', () => {
    const justifiees = [...FEUILLES].filter(([, css]) => css.includes(JUSTIFIE)).map(([chemin]) => chemin)
    expect(justifiees).toEqual(['components/Section.module.css'])
    const section = blocsDeMedia(FEUILLES.get('components/Section.module.css') ?? '', LARGE).join('')
    expect(section).toContain('.chapeau')
    // Les introductions, essayées justifiées, montaient à 3,0 fois l'espace
    // normale sans dictionnaire de césure.
    expect(section).not.toContain('.introduction')
  })

  it('jamais sous 900 px, et toujours avec coupure des mots et coupure de lignes ordinaire', () => {
    for (const [chemin, css] of FEUILLES) {
      if (!css.includes(JUSTIFIE)) continue
      const blocs = blocsDeMedia(css, LARGE)
      const horsBlocs = blocs.reduce((reste, bloc) => reste.replace(bloc, ''), css)
      expect(horsBlocs, chemin).not.toContain(JUSTIFIE)
      for (const bloc of blocs.filter((b) => b.includes(JUSTIFIE))) {
        expect(bloc, chemin).toContain('hyphens: auto')
        // `pretty` raccourcit les lignes d'avant la dernière, que la
        // justification étire : mesuré, il doublait les lignes trop lâches.
        expect(bloc, chemin).toContain('text-wrap: wrap')
      }
    }
  })

  it('la page déclare le français, sans quoi aucun mot ne se coupe', () => {
    const page = readFileSync(path.join(SRC, '..', 'index.html'), 'utf-8')
    expect(page).toContain('<html lang="fr">')
  })
})

describe('le texte aligné à gauche', () => {
  it('évite une dernière ligne d’un seul mot, partout : `text-wrap: pretty` sur le corps de la page', () => {
    const typographie = FEUILLES.get('styles/typography.css') ?? ''
    const corps = typographie.slice(typographie.indexOf('body {'), typographie.indexOf('}', typographie.indexOf('body {')))
    expect(corps).toContain('text-wrap: pretty')
  })
})
