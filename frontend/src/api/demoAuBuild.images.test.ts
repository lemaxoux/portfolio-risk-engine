/**
 * Les images de la page de présentation, hors du build ordinaire
 * (DESIGN.md §19.4, `demoAuBuild.ts`).
 *
 * Ce qui se teste ici est le tri : quels fichiers d'un build viennent du
 * dossier des captures, et le refus quand un autre fichier en nomme un. Que
 * `dist/` n'en contienne aucun se constate sur un vrai build.
 */
import { sep } from 'node:path'
import { describe, expect, it } from 'vitest'

import {
  IMAGES_DE_LA_PRESENTATION,
  imagesDeLaPresentation,
  type FichierDuBuild,
} from './demoAuBuild'

const capture = (nom: string, origine: string): FichierDuBuild => ({
  type: 'asset',
  fileName: `assets/${nom}`,
  originalFileNames: [origine],
  source: new Uint8Array([137, 80, 78, 71]),
})

const CLAIRE = capture('mesure-fr-clair-BN10UVd6.png', `${IMAGES_DE_LA_PRESENTATION}mesure-fr-clair.png`)
const SOMBRE = capture('mesure-fr-sombre-C2GYxOl5.png', `${IMAGES_DE_LA_PRESENTATION}mesure-fr-sombre.png`)

const POLICE: FichierDuBuild = {
  type: 'asset',
  fileName: 'assets/spectral-latin-400-normal-CTVgUekv.woff2',
  originalFileNames: ['node_modules/@fontsource/spectral/files/spectral-latin-400-normal.woff2'],
  source: new Uint8Array([119, 79, 70, 50]),
}

const entree = (code: string): FichierDuBuild => ({
  type: 'chunk',
  fileName: 'assets/index-BR0TmROf.js',
  code,
})

const feuille = (source: string): FichierDuBuild => ({
  type: 'asset',
  fileName: 'assets/index-Cqj2Cudc.css',
  originalFileNames: [],
  source,
})

describe('les images de la présentation dans un build', () => {
  it('le dossier des captures est celui que la vue importe', () => {
    expect(IMAGES_DE_LA_PRESENTATION).toBe('src/images/presentation/')
  })

  it('rend les fichiers émis depuis le dossier des captures, et eux seuls', () => {
    const fichiers = [entree('const a = 1'), POLICE, CLAIRE, feuille('.a{color:red}'), SOMBRE]
    expect(imagesDeLaPresentation(fichiers)).toEqual([CLAIRE.fileName, SOMBRE.fileName])
  })

  it('reconnaît le dossier quel que soit le séparateur du système', () => {
    const origine = ['C:', 'depot', 'frontend', 'src', 'images', 'presentation', 'saisie-en-clair.png']
    const image = capture('saisie-en-clair-BlbXwPdf.png', origine.join(sep))
    expect(imagesDeLaPresentation([image])).toEqual([image.fileName])
  })

  it('un build sans capture ne rend rien', () => {
    expect(imagesDeLaPresentation([entree('const a = 1'), POLICE])).toEqual([])
  })

  it('refuse un fichier JavaScript qui nomme une capture', () => {
    const fichiers = [entree(`const image = "/${CLAIRE.fileName}"`), CLAIRE, SOMBRE]
    expect(() => imagesDeLaPresentation(fichiers)).toThrow(CLAIRE.fileName)
    expect(() => imagesDeLaPresentation(fichiers)).toThrow('assets/index-BR0TmROf.js')
  })

  it('refuse une feuille de style qui nomme une capture', () => {
    const fichiers = [CLAIRE, SOMBRE, feuille(`.a{background:url(/${SOMBRE.fileName})}`)]
    expect(() => imagesDeLaPresentation(fichiers)).toThrow(SOMBRE.fileName)
  })
})
