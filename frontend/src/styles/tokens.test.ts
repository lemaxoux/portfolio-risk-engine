/**
 * La discipline des tokens, vérifiée mécaniquement — DESIGN.md §0 et §17.
 *
 * C'est le pendant frontend de `tests/test_api_discipline.py`, et il existe
 * pour la même raison : une règle écrite dans un document se contourne sans
 * bruit. Une couleur en dur glissée dans un module CSS « juste pour cette
 * bordure » ne suivra pas la bascule de thème, à côté de couleurs qui la
 * suivent, et rien ne les distingue à la lecture.
 *
 * Ces tests lisent les FICHIERS, pas le rendu. Ils sont volontairement rigides.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const TOKENS = join(SRC, 'styles', 'tokens.css')
const TYPOGRAPHIE = join(SRC, 'styles', 'typography.css')

function fichiers(racine: string, extensions: string[]): string[] {
  const trouves: string[] = []
  for (const entree of readdirSync(racine, { withFileTypes: true })) {
    const chemin = join(racine, entree.name)
    if (entree.isDirectory()) trouves.push(...fichiers(chemin, extensions))
    else if (extensions.some((e) => entree.name.endsWith(e))) trouves.push(chemin)
  }
  return trouves.sort()
}

/**
 * Les COMMENTAIRES sont retirés avant toute recherche, et les fichiers de test
 * sont exclus de l'inspection.
 *
 * Même raison que dans `tests/test_api_discipline.py` : un fichier qui
 * documente ce qu'il s'interdit cite forcément le motif interdit. Une garde qui
 * lirait le texte brut se déclencherait sur sa propre explication — et la façon
 * la plus simple de la faire taire serait d'effacer l'explication. La garde
 * porte donc sur le CODE.
 *
 * Les lignes sont préservées : un commentaire est blanchi, pas supprimé, pour
 * que le numéro de ligne rapporté soit celui du fichier.
 */
function sansCommentaires(source: string): string {
  const BLOC = /\/\*[\s\S]*?\*\//g
  const LIGNE = /^[ \t]*\/\/.*$/gm
  return source
    .replace(BLOC, (trouve) => trouve.replace(/[^\r\n]/g, ' '))
    .replace(LIGNE, '')
}

const SOURCES = fichiers(SRC, ['.css', '.ts', '.tsx'])
const A_INSPECTER = SOURCES.filter((chemin) => !chemin.endsWith('.test.ts'))

function codeDe(chemin: string): string[] {
  return sansCommentaires(readFileSync(chemin, 'utf-8')).split('\n')
}

describe('aucune valeur brute hors de tokens.css', () => {
  it('trouve bien des fichiers à inspecter', () => {
    // Sans ce témoin, une erreur de chemin rendrait tous les tests suivants
    // verts sur une liste vide — la façon la plus discrète dont une garde meurt.
    expect(A_INSPECTER.length).toBeGreaterThan(5)
    expect(A_INSPECTER).toContain(TOKENS)
  })

  it('aucun code hexadécimal de couleur en dehors de tokens.css', () => {
    // 3, 4, 6 ou 8 chiffres.
    const hexa = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g
    const fautes: string[] = []
    for (const chemin of A_INSPECTER) {
      if (chemin === TOKENS) continue
      codeDe(chemin).forEach((ligne, index) => {
        for (const trouve of ligne.matchAll(hexa)) {
          fautes.push(`${relative(SRC, chemin)}:${index + 1} ${trouve[0]}`)
        }
      })
    }
    expect(fautes).toEqual([])
  })

  it('la garde voit un hexadécimal quand il y en a un', () => {
    // Témoin POSITIF. Une garde qu'on n'a jamais vue échouer ne prouve rien.
    const hexa = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g
    const faux = sansCommentaires('.bloc { color: #2c3033; }')
    expect([...faux.matchAll(hexa)]).toHaveLength(1)
    // Témoin NÉGATIF : le même code dans un commentaire ne compte pas.
    const commente = sansCommentaires('/* jadis #2c3033 */\n.bloc { color: var(--x); }')
    expect([...commente.matchAll(hexa)]).toHaveLength(0)
    // Ni un fragment d'URL ou un identifiant CSS.
    expect([...sansCommentaires('a { color: var(--accent); }').matchAll(hexa)]).toHaveLength(0)
  })

  it('tokens.css porte bien les couleurs des deux thèmes', () => {
    // Si tokens.css se vidait, la garde ci-dessus passerait au vert sur un
    // projet entièrement en dur. Ce test tient l'autre bout.
    const source = readFileSync(TOKENS, 'utf-8')
    expect(source).toContain('#1b1d1f')
    expect(source).toContain('#f2f1ec')
    // §4 et §12 : ni noir pur, ni blanc pur, en fond comme en texte.
    expect(source).not.toMatch(/#(?:000{1,2}|000000)\b/)
    expect(source).not.toMatch(/#(?:fff{1,2}|ffffff)\b/i)
  })

  it('aucune taille de police en px, nulle part', () => {
    const fautes: string[] = []
    for (const chemin of A_INSPECTER) {
      codeDe(chemin).forEach((ligne, index) => {
        if (/font-size\s*:[^;]*\d+px/.test(ligne)) {
          fautes.push(`${relative(SRC, chemin)}:${index + 1}`)
        }
      })
    }
    expect(fautes).toEqual([])
    // L'échelle vit dans tokens.css, en rem, et les composants la lisent.
    expect(readFileSync(TOKENS, 'utf-8')).toContain('--text-2xl: 1.9375rem')
    expect(readFileSync(TYPOGRAPHIE, 'utf-8')).toContain('var(--text-body)')
  })
})

/**
 * Les deux affectations du thème sombre ne peuvent pas diverger.
 *
 * §4 impose trois points d'entrée, et CSS n'a aucun moyen de partager un bloc
 * de déclarations entre une requête de média et un sélecteur. Le sombre est
 * donc affecté deux fois. Ce test est ce qui rend la duplication sûre : une
 * couleur ajoutée à un bloc et oubliée dans l'autre ne se verrait autrement que
 * chez les utilisateurs ayant figé leur thème.
 */
describe('les trois blocs de thème déclarent le même jeu de tokens', () => {
  const source = readFileSync(TOKENS, 'utf-8')

  function tokensDe(debut: string): string[] {
    const depart = source.indexOf(debut)
    expect(depart, `bloc introuvable : ${debut}`).toBeGreaterThan(-1)
    const ouvrante = source.indexOf('{', depart + debut.length - 1)
    let profondeur = 0
    let fin = ouvrante
    for (let i = ouvrante; i < source.length; i += 1) {
      if (source[i] === '{') profondeur += 1
      if (source[i] === '}') {
        profondeur -= 1
        if (profondeur === 0) {
          fin = i
          break
        }
      }
    }
    return [...source.slice(ouvrante, fin).matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)]
      .map((trouve) => trouve[1] as string)
      .filter((nom) => !nom.startsWith('--clair-') && !nom.startsWith('--sombre-'))
      .sort()
  }

  const clair = tokensDe(':root {')
  const sombreSysteme = tokensDe(":root:not([data-theme='light'])")
  const sombreFige = tokensDe(":root[data-theme='dark']")

  it('le bloc sombre du système et le bloc sombre figé sont identiques', () => {
    expect(sombreSysteme).toEqual(sombreFige)
    // §5.1 en compte dix-huit. Le nombre est écrit pour qu'un token ajouté à la
    // palette sans être affecté fasse échouer le test plutôt que de disparaître.
    expect(sombreSysteme).toHaveLength(18)
  })

  it('tout token de couleur du thème clair est réaffecté en sombre', () => {
    // Les tokens NON colorés (typographie, espacement, mouvement, grille) ne
    // dépendent pas du thème : seuls ceux que le sombre redéfinit sont comparés.
    expect(clair.filter((nom) => sombreSysteme.includes(nom))).toEqual(sombreSysteme)
  })

  it('chaque token sombre pointe sur la palette, jamais sur un hexadécimal', () => {
    const depart = source.indexOf(":root[data-theme='dark']")
    const corps = source.slice(depart, source.indexOf('}', depart))
    expect(corps).not.toMatch(/#[0-9a-fA-F]{3}/)
    expect(corps).toContain('var(--sombre-surface-0)')
  })
})
