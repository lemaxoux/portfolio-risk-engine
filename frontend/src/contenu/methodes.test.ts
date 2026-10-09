/**
 * Le lien de chaque mesure vers sa méthode (chantier 7E, DESIGN.md §9.1 ;
 * annexe A de `methodologie-proposition.md`, hors dépôt).
 *
 * Ce qui est vérifié : la table `METHODES` place chaque rangée de l'annexe A,
 * et rien d'autre ; chaque ancre qu'un lien vise existe dans le texte des deux
 * langues ; le texte d'un lien est le titre de son entrée, dans la langue de
 * la page ; dans une même paire, les entrées qui suivent prennent une
 * minuscule initiale, sauf un sigle.
 */
import { describe, expect, it } from 'vitest'

import {
  METHODES,
  REFUS,
  avecRefus,
  enSuite,
  titreDeLEntree,
  titresDesEntrees,
  type Ancre,
} from './methodes'

/** L'annexe A : ce qui est affiché, et ses ancres. */
const ANNEXE_A: readonly (readonly [string, readonly Ancre[]])[] = [
  ['Section 1, tableau ; bandeau, « Valorisé au »', ['valeur-et-poids', 'donnees']],
  ['Bandeau, fenêtre d’estimation et fenêtre réduite', ['conventions']],
  ['VaR historique à 95 et 99 % ; pire jour', ['var-historique']],
  ['Histogramme', ['histogramme']],
  ['VaR paramétrique normale et Student ; contrôle Monte Carlo ; ν', ['var-parametrique']],
  ['Volatilité annualisée', ['volatilite']],
  ['CVaR à 95 et 99 %', ['cvar']],
  ['Perte maximale pic-creux', ['perte-maximale']],
  ['Courbe de valeur', ['courbe-de-valeur']],
  ['Lignes effectives en capital et en risque', ['lignes-effectives']],
  ['Part dans les variations, écart, graphique', ['part-des-variations']],
  ['Apports par crise (tableau de la section 4)', ['trois-chiffres']],
  ['Corrélation', ['correlation']],
  ['Bloc d’une crise : les trois chiffres', ['trois-chiffres']],
  ['Couverture, lignes écartées', ['couverture']],
  ['Bêta et R², temps ordinaire et crise', ['sensibilite']],
  ['Ce que la sensibilité laissait attendre', ['attendu']],
  ['Observations de la section 6', ['constats']],
  ['Ligne d’un seuil choisi, démontré, d’une référence', ['seuils-choisis', 'seuils-demontres', 'references']],
  ['Un refus (tiret et raison)', ['refus']],
]

const PLACEES = new Set<Ancre>([...Object.values(METHODES).flat(), REFUS])

describe('la table des méthodes suit l’annexe A', () => {
  it.each(ANNEXE_A)('%s', (_, ancres) => {
    for (const ancre of ancres) expect(PLACEES.has(ancre), ancre).toBe(true)
  })

  it('et ne vise rien que l’annexe ne nomme', () => {
    const annexe = new Set(ANNEXE_A.flatMap(([, ancres]) => ancres))
    expect([...PLACEES].filter((ancre) => !annexe.has(ancre))).toEqual([])
  })

  it('un refus ajoute son entrée à celles du bloc, et seulement alors', () => {
    expect(avecRefus(METHODES.cvar, false)).toEqual(['cvar'])
    expect(avecRefus(METHODES.cvar, true)).toEqual(['cvar', 'refus'])
  })
})

describe('chaque entrée visée existe, avec son titre, dans les deux langues', () => {
  it.each(['fr', 'en'] as const)('%s', (langue) => {
    const titres = titresDesEntrees(langue)
    for (const ancre of PLACEES) expect(titres.get(ancre), `${langue} #${ancre}`).toBeTruthy()
  })

  it('le texte d’un lien est le titre de son entrée, dans la langue de la page', () => {
    expect(titreDeLEntree('var-historique', 'fr')).toBe('La VaR historique')
    expect(titreDeLEntree('var-historique', 'en')).toBe('Historical VaR')
    expect(titreDeLEntree('cvar', 'fr')).toBe('La CVaR')
    expect(titreDeLEntree('donnees', 'fr')).toBe('Les données')
    expect(titreDeLEntree('refus', 'en')).toBe('When the tool refuses a figure')
  })
})

describe('les entrées qui suivent la première, dans une même paire', () => {
  it('prennent une minuscule initiale', () => {
    expect(enSuite('Les conventions')).toBe('les conventions')
    expect(enSuite('Ce que la sensibilité laissait attendre')).toBe('ce que la sensibilité laissait attendre')
    expect(enSuite('Quand l’outil refuse un chiffre')).toBe('quand l’outil refuse un chiffre')
    expect(enSuite('The data')).toBe('the data')
    expect(enSuite('Historical VaR')).toBe('historical VaR')
  })

  it('sauf un sigle', () => {
    expect(enSuite('CVaR')).toBe('CVaR')
    expect(enSuite('VaR historique')).toBe('VaR historique')
  })

  it('chaque paire de la table, écrite dans les deux langues', () => {
    for (const langue of ['fr', 'en'] as const) {
      for (const ancres of Object.values(METHODES)) {
        const textes = ancres.map((ancre, rang) => {
          const titre = titreDeLEntree(ancre, langue)
          return rang === 0 ? titre : enSuite(titre)
        })
        for (const texte of textes.slice(1)) expect(texte.charAt(0), texte).not.toMatch(/[A-ZÀ-Ý]/u)
      }
    }
  })
})
