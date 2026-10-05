/**
 * `<Absent>` : le seul tiret isolé de l'interface, et son texte pour lecteur
 * d'écran (DESIGN.md §6.3, §9.1 règle 3). Rendu côté serveur.
 *
 * Un tiret seul ne se lit pas : le bloc mesure, la cellule de tableau et le
 * chiffre d'une crise le rendent tous par `avecAbsence`, qui lui joint « non
 * disponible ».
 */
import { createElement, type ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ESPACE_FINE, TIRET_INDEFINI } from '../lib/format'
import { Absent, TEXTE_ABSENT, avecAbsence } from './Absent'
import { DataTable, type Colonne } from './DataTable'
import { Measure } from './Measure'

const ATTENDU =
  '<span aria-hidden="true">\u2013</span><span class="visuellement-cache">non disponible</span>'

describe('une valeur absente', () => {
  it('se voit comme un tiret court et se lit « non disponible »', () => {
    expect(TIRET_INDEFINI).toBe('\u2013')
    expect(TEXTE_ABSENT).toBe('non disponible')
    expect(renderToStaticMarkup(createElement(Absent))).toBe(ATTENDU)
  })

  it('le tiret d’indéfini reçoit son texte, tout autre contenu passe tel quel', () => {
    const rendre = (contenu: ReactNode) =>
      renderToStaticMarkup(createElement('p', null, avecAbsence(contenu)))
    expect(rendre(TIRET_INDEFINI)).toBe(`<p>${ATTENDU}</p>`)
    expect(rendre(`1,06${ESPACE_FINE}%`)).toBe(`<p>1,06${ESPACE_FINE}%</p>`)
    expect(rendre(null)).toBe('<p></p>')
  })

  it('un bloc mesure refusé ne l’affiche jamais sans son texte', () => {
    const html = renderToStaticMarkup(
      createElement(Measure, {
        libelle: 'VaR 99 historique',
        valeur: TIRET_INDEFINI,
        lecture: 'Sur 60 jours de bourse, aucun ne tombe dans le 1 % le plus mauvais.',
        provenance: [{ libelle: 'Méthode', valeur: 'historique' }],
      }),
    )
    expect(html).toContain(ATTENDU)
    expect(html.split('\u2013')).toHaveLength(2)
  })

  it('une cellule de tableau non plus, pied compris', () => {
    interface Ligne {
      readonly nom: string
      readonly valeur: string
    }
    const colonnes: Colonne<Ligne>[] = [
      { cle: 'nom', titre: 'Nom', nature: 'texte', cellule: (l) => l.nom },
      { cle: 'valeur', titre: 'Valeur', nature: 'nombre', cellule: (l) => l.valeur },
    ]
    const html = renderToStaticMarkup(
      createElement(DataTable<Ligne>, {
        legende: 'Portefeuilles',
        colonnes,
        lignes: [{ nom: 'Vide', valeur: TIRET_INDEFINI }],
        cleDeLigne: (l: Ligne) => l.nom,
        pied: ['Total', TIRET_INDEFINI],
      }),
    )
    expect(html.split(ATTENDU)).toHaveLength(3)
    expect(html.split('\u2013')).toHaveLength(3)
  })
})
