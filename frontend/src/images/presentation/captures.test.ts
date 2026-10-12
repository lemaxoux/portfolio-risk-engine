/**
 * Les images de la page de présentation — DESIGN.md §19.4 et §19.7.
 *
 * Ce qui se lit dans les fichiers : leur nombre, leur taille, leur poids.
 * Une image dont les dimensions déclarées ne sont pas celles du fichier
 * déplacerait le texte en arrivant, ou s'afficherait déformée. Ce qu'elles
 * montrent se relit à l'œil, et leur chargement dans un navigateur.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { CAPTURES } from './index'

const DOSSIER = join(process.cwd(), 'src', 'images', 'presentation')

/** Le plafond de §19.4, en octets. */
const POIDS_MAXIMAL = 100_000

/** Les captures sont prises à l'échelle 2 : le fichier a le double de l'affichage. */
const ECHELLE = 2

const SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10]

/** L'en-tête d'un PNG : ses dimensions, et son type de couleur (3 : une palette). */
function enTete(nom: string) {
  const octets = readFileSync(join(DOSSIER, nom))
  expect([...octets.subarray(0, 8)], nom).toEqual(SIGNATURE)
  expect(octets.subarray(12, 16).toString('latin1'), nom).toBe('IHDR')
  return {
    largeur: octets.readUInt32BE(16),
    hauteur: octets.readUInt32BE(20),
    profondeur: octets.readUInt8(24),
    couleur: octets.readUInt8(25),
    poids: octets.length,
  }
}

const FIGURES = ['mesure', 'saisie'] as const
const LANGUES = ['fr', 'en'] as const
const THEMES = [
  ['claire', 'clair'],
  ['sombre', 'sombre'],
] as const

const APERCU = 'apercu.png'

/** Chaque fichier d'une figure, avec la taille d'affichage que la page déclare. */
const DECLAREES = FIGURES.flatMap((figure) =>
  LANGUES.flatMap((langue) =>
    THEMES.map(([cle, suffixe]) => ({
      nom: `${figure}-${langue}-${suffixe}.png`,
      importe: CAPTURES[figure][langue][cle],
      largeur: CAPTURES[figure][langue].largeur,
      hauteur: CAPTURES[figure][langue].hauteur,
    })),
  ),
)

describe('les images de la page de présentation', () => {
  it('neuf fichiers : huit captures et l’image de prévisualisation', () => {
    const fichiers = readdirSync(DOSSIER)
      .filter((nom) => nom.endsWith('.png'))
      .sort()
    expect(fichiers).toEqual([APERCU, ...DECLAREES.map((capture) => capture.nom)].sort())
  })

  it('chaque figure importe le fichier de sa langue et de son thème', () => {
    for (const { nom, importe } of DECLAREES) {
      expect(importe.endsWith(`/${nom}`), `${nom} : ${importe}`).toBe(true)
    }
  })

  it('les dimensions déclarées sont celles du fichier, à l’échelle 2', () => {
    for (const { nom, largeur, hauteur } of DECLAREES) {
      const fichier = enTete(nom)
      expect({ nom, largeur: fichier.largeur, hauteur: fichier.hauteur }).toEqual({
        nom,
        largeur: largeur * ECHELLE,
        hauteur: hauteur * ECHELLE,
      })
    }
  })

  it('capturées à la largeur d’un téléphone, affichées à 390 px au plus', () => {
    for (const { nom, largeur } of DECLAREES) expect(largeur, nom).toBe(390)
  })

  it('l’image de prévisualisation fait 1200 × 630', () => {
    const fichier = enTete(APERCU)
    expect({ largeur: fichier.largeur, hauteur: fichier.hauteur }).toEqual({
      largeur: 1200,
      hauteur: 630,
    })
  })

  it('toutes en palette, 100 ko au plus', () => {
    for (const nom of [APERCU, ...DECLAREES.map((capture) => capture.nom)]) {
      const fichier = enTete(nom)
      expect({ nom, couleur: fichier.couleur, profondeur: fichier.profondeur }).toEqual({
        nom,
        couleur: 3,
        profondeur: 8,
      })
      expect(fichier.poids, nom).toBeLessThanOrEqual(POIDS_MAXIMAL)
    }
  })
})
