/**
 * Ce que la démonstration montre de plus, et ce qu'elle ne propose pas
 * (chantier 9.2).
 *
 * Le rendu se vérifie dans un navigateur ; ici, les fonctions pures qui le
 * décident. Elles reçoivent le mode en paramètre, avec la constante du build
 * pour défaut : hors démonstration, rien ne change.
 */
import { describe, expect, it } from 'vitest'

import { pagesApplication } from '../components/Navigation'
import { SAISI, type Route } from '../lib/route'
import { destinationDe } from '../views/Acceptation'
import { DATE_DE_LA_DEMO, PORTEFEUILLES_DE_LA_DEMO } from './demo'
import { LIBELLES } from './libelles'

describe('la mention de la démonstration', () => {
  it('dit ce qu’est le site, en français', () => {
    expect(LIBELLES.fr.demo.mention(PORTEFEUILLES_DE_LA_DEMO, DATE_DE_LA_DEMO)).toBe(
      "Démonstration\u00a0: 3\u00a0portefeuilles d'exemple, ou le vôtre, valorisés au 9\u00a0septembre\u00a02026.",
    )
  })

  it('et en anglais', () => {
    expect(LIBELLES.en.demo.mention(PORTEFEUILLES_DE_LA_DEMO, DATE_DE_LA_DEMO)).toBe(
      'Demonstration: 3\u00a0sample portfolios, or your own, valued as of September\u00a09,\u00a02026.',
    )
  })

  it('écrit ses nombres par le formateur, quels qu’ils soient', () => {
    expect(LIBELLES.fr.demo.mention(1200, '2026-01-01')).toBe(
      "Démonstration\u00a0: 1\u202f200\u00a0portefeuilles d'exemple, ou le vôtre, valorisés au 1er\u00a0janvier\u00a02026.",
    )
    expect(LIBELLES.en.demo.mention(1200, '2026-01-01')).toBe(
      'Demonstration: 1,200\u00a0sample portfolios, or your own, valued as of January\u00a01,\u00a02026.',
    )
  })

  it('ne promet aucune fonction à venir', () => {
    const PROMESSE = /bientôt|prochain|à venir|plus tard|soon|coming|later|will\b|upcoming/i
    for (const langue of ['fr', 'en'] as const) {
      expect(LIBELLES[langue].demo.mention(PORTEFEUILLES_DE_LA_DEMO, DATE_DE_LA_DEMO)).not.toMatch(PROMESSE)
    }
    expect('Saisie bientôt disponible').toMatch(PROMESSE)
    expect('Entry coming soon').toMatch(PROMESSE)
  })

  it('porte une date ISO et un nombre entier de portefeuilles', () => {
    expect(DATE_DE_LA_DEMO).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(Number.isInteger(PORTEFEUILLES_DE_LA_DEMO) && PORTEFEUILLES_DE_LA_DEMO > 1).toBe(true)
  })
})

describe('la navigation de la démonstration', () => {
  const COURANTES = ['analyse', 'portefeuilles', 'methodologie'] as const

  it('ne propose pas « Positions et import »', () => {
    expect(pagesApplication('analyse', 3, 'fr', true).map((page) => page.libelle)).toEqual([
      'Présentation',
      'Analyse',
      'Portefeuilles',
      'Méthodologie',
      'Avertissement',
    ])
    expect(pagesApplication('methodologie', 3, 'en', true).map((page) => page.libelle)).toEqual([
      'Overview',
      'Analysis',
      'Portfolios',
      'Methodology',
      'Disclaimer',
    ])
  })

  it('ne mène à aucune adresse de saisie, depuis aucune page', () => {
    for (const courante of COURANTES) {
      for (const id of [1, 2, 3, null]) {
        for (const langue of ['fr', 'en'] as const) {
          const adresses = pagesApplication(courante, id, langue, true).map((page) => page.vers)
          expect(adresses.filter((adresse) => adresse.includes('positions'))).toEqual([])
        }
      }
    }
  })

  it('marque toujours la page courante, et elle seule', () => {
    for (const courante of COURANTES) {
      const marquees = pagesApplication(courante, 2, 'fr', true).filter((page) => page.courante)
      expect(marquees).toHaveLength(1)
    }
  })

  it('hors démonstration, la saisie reste proposée : c’est le défaut', () => {
    expect(pagesApplication('analyse', 3).map((page) => page.vers)).toContain('/portefeuilles/3/positions')
    expect(pagesApplication('analyse', 3, 'fr', false)).toEqual(pagesApplication('analyse', 3))
  })
})

describe('l’écran d’acceptation de la démonstration', () => {
  const POSITIONS: Route = { vue: 'positions', id: 1 }

  it('une adresse de saisie mène à « la page demandée », comme une adresse inconnue', () => {
    expect(destinationDe(POSITIONS, true)).toBe('page')
    expect(destinationDe(POSITIONS, true)).toBe(destinationDe({ vue: 'inconnue', chemin: '/rien' }, true))
    expect(LIBELLES.fr.acceptation.ouvrir[destinationDe(POSITIONS, true)]).toBe('Ouvrir la page demandée')
    expect(LIBELLES.en.acceptation.ouvrir[destinationDe(POSITIONS, true)]).toBe('Open the requested page')
  })

  it('les autres adresses gardent leur destination', () => {
    const routes: Route[] = [
      { vue: 'accueil' },
      { vue: 'analyse', id: 2 },
      { vue: 'portefeuilles' },
      { vue: 'methodologie' },
      { vue: 'inconnue', chemin: '/rien' },
    ]
    for (const route of routes) expect(destinationDe(route, true)).toBe(destinationDe(route, false))
  })

  it('hors démonstration, rien ne change : c’est le défaut', () => {
    expect(destinationDe(POSITIONS)).toBe('positions')
    expect(destinationDe(POSITIONS, false)).toBe('positions')
  })
})

describe('le portefeuille saisi, sur le site (chantier 9.6)', () => {
  it('en vue, il rend « Positions et import » à la navigation, vers ses adresses', () => {
    expect(pagesApplication('analyse', SAISI, 'fr', true).map((page) => [page.libelle, page.vers])).toEqual([
      ['Présentation', '/'],
      ['Analyse', '/portefeuilles/saisi'],
      ['Positions et import', '/portefeuilles/saisi/positions'],
      ['Portefeuilles', '/portefeuilles'],
      ['Méthodologie', '/methodologie'],
      ['Avertissement', '/avertissement'],
    ])
    const marquees = pagesApplication('positions', SAISI, 'en', true).filter((page) => page.courante)
    expect(marquees.map((page) => page.vers)).toEqual(['/portefeuilles/saisi/positions'])
  })

  it('ses deux pages mènent l’écran d’acceptation à leur page, sur le site', () => {
    expect(destinationDe({ vue: 'saisi' }, true)).toBe('analyse')
    expect(destinationDe({ vue: 'saisi-positions' }, true)).toBe('positions')
    expect(LIBELLES.fr.acceptation.ouvrir[destinationDe({ vue: 'saisi-positions' }, true)]).toBe(
      'Ouvrir les positions',
    )
    expect(LIBELLES.en.acceptation.ouvrir[destinationDe({ vue: 'saisi' }, true)]).toBe('Open the analysis')
  })

  it('hors du site, ses adresses sont celles d’aucune page', () => {
    for (const route of [{ vue: 'saisi' }, { vue: 'saisi-positions' }] as const) {
      expect(destinationDe(route)).toBe('page')
      expect(destinationDe(route, false)).toBe(destinationDe({ vue: 'inconnue', chemin: '/rien' }, false))
    }
  })

  it('son nom et le titre de son bloc ont la même valeur, en deux libellés', () => {
    expect(LIBELLES.fr.saisi.nom).toBe('Votre portefeuille')
    expect(LIBELLES.en.saisi.nom).toBe('Your portfolio')
    for (const langue of ['fr', 'en'] as const) {
      expect(LIBELLES[langue].saisi.titre).toBe(LIBELLES[langue].saisi.nom)
    }
  })
})
