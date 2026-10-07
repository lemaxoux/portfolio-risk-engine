/**
 * Les pages que la navigation propose, depuis chacune.
 *
 * La méthodologie est toujours proposée, en dernier : elle ne dépend d'aucun
 * portefeuille. L'analyse et la saisie ne le sont qu'avec un portefeuille en
 * vue, et mènent à lui. La page courante est marquée, et elle seule.
 */
import { describe, expect, it } from 'vitest'

import { pagesApplication } from './Navigation'

describe('pagesApplication', () => {
  it('propose la méthodologie en dernier, avec ou sans portefeuille', () => {
    expect(pagesApplication('analyse', 3).map((page) => page.libelle)).toEqual([
      'Analyse',
      'Positions et import',
      'Portefeuilles',
      'Méthodologie',
    ])
    expect(pagesApplication('methodologie', null).map((page) => page.libelle)).toEqual([
      'Portefeuilles',
      'Méthodologie',
    ])
  })

  it('sans portefeuille en vue, ni analyse ni saisie', () => {
    for (const courante of ['portefeuilles', 'methodologie'] as const) {
      expect(pagesApplication(courante, null).map((page) => page.vers)).toEqual([
        '/portefeuilles',
        '/methodologie',
      ])
    }
  })

  it('l’analyse et la saisie mènent au portefeuille en vue', () => {
    expect(pagesApplication('methodologie', 7).map((page) => page.vers)).toEqual([
      '/portefeuilles/7',
      '/portefeuilles/7/positions',
      '/portefeuilles',
      '/methodologie',
    ])
  })

  it('marque la page courante, et elle seule', () => {
    const attendue = {
      analyse: '/portefeuilles/7',
      positions: '/portefeuilles/7/positions',
      portefeuilles: '/portefeuilles',
      methodologie: '/methodologie',
    } as const
    for (const [courante, vers] of Object.entries(attendue)) {
      const marquees = pagesApplication(courante as keyof typeof attendue, 7).filter(
        (page) => page.courante,
      )
      expect(marquees.map((page) => page.vers), courante).toEqual([vers])
    }
  })
})
