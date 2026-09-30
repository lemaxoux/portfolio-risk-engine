import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  cheminDe,
  lireRoute,
  naviguer,
  portefeuilleDAccueil,
  poserGarde,
  type Route,
} from './route'

describe('lireRoute', () => {
  it('lit les quatre adresses', () => {
    expect(lireRoute('/')).toEqual({ vue: 'accueil' })
    expect(lireRoute('/portefeuilles')).toEqual({ vue: 'portefeuilles' })
    expect(lireRoute('/portefeuilles/3')).toEqual({ vue: 'analyse', id: 3 })
    expect(lireRoute('/portefeuilles/3/positions')).toEqual({ vue: 'positions', id: 3 })
  })

  it('tolère une barre oblique finale', () => {
    expect(lireRoute('/portefeuilles/')).toEqual({ vue: 'portefeuilles' })
    expect(lireRoute('/portefeuilles/12/')).toEqual({ vue: 'analyse', id: 12 })
  })

  it('ne devine pas une adresse qu’elle ne connaît pas', () => {
    for (const chemin of [
      '/methodologie',
      '/portefeuilles/abc',
      '/portefeuilles/0',
      '/portefeuilles/07',
      '/portefeuilles/3/analyse',
      '/portefeuilles/3/positions/1',
    ]) {
      expect(lireRoute(chemin)).toEqual({ vue: 'inconnue', chemin })
    }
  })

  it('cheminDe est l’inverse de lireRoute', () => {
    const routes: Exclude<Route, { vue: 'inconnue' }>[] = [
      { vue: 'accueil' },
      { vue: 'portefeuilles' },
      { vue: 'analyse', id: 7 },
      { vue: 'positions', id: 7 },
    ]
    for (const route of routes) expect(lireRoute(cheminDe(route))).toEqual(route)
  })
})

describe('portefeuilleDAccueil', () => {
  it('rouvre le portefeuille mémorisé s’il existe encore', () => {
    expect(portefeuilleDAccueil([1, 4, 9], 4)).toBe(4)
  })

  it('retombe sur le premier, sans erreur, si le mémorisé a disparu', () => {
    expect(portefeuilleDAccueil([1, 4, 9], 5)).toBe(1)
    expect(portefeuilleDAccueil([1, 4, 9], null)).toBe(1)
  })

  it('ne rend rien quand il n’y a aucun portefeuille', () => {
    expect(portefeuilleDAccueil([], 4)).toBeNull()
  })
})

describe('naviguer et la garde', () => {
  function simulerFenetre(depart: string) {
    const location = { pathname: depart }
    const history = {
      pushState: vi.fn((_etat: unknown, _titre: string, chemin: string) => {
        location.pathname = chemin
      }),
      replaceState: vi.fn((_etat: unknown, _titre: string, chemin: string) => {
        location.pathname = chemin
      }),
    }
    vi.stubGlobal('window', {
      location,
      history,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    return { location, history }
  }

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('change d’adresse sans garde', () => {
    const { location, history } = simulerFenetre('/portefeuilles')
    naviguer('/portefeuilles/2')
    expect(location.pathname).toBe('/portefeuilles/2')
    expect(history.pushState).toHaveBeenCalledOnce()
  })

  it('une garde qui refuse retient la navigation, et reçoit la cible', () => {
    const { location } = simulerFenetre('/portefeuilles/2/positions')
    const cibles: string[] = []
    const retirer = poserGarde((cible) => {
      cibles.push(cible)
      return false
    })
    naviguer('/portefeuilles')
    expect(location.pathname).toBe('/portefeuilles/2/positions')
    expect(cibles).toEqual(['/portefeuilles'])

    // « Quitter sans enregistrer » force la navigation.
    naviguer('/portefeuilles', { forcer: true })
    expect(location.pathname).toBe('/portefeuilles')
    retirer()
  })

  it('une garde retirée ne retient plus rien', () => {
    const { location } = simulerFenetre('/portefeuilles/2/positions')
    const retirer = poserGarde(() => false)
    retirer()
    naviguer('/portefeuilles')
    expect(location.pathname).toBe('/portefeuilles')
  })

  it('une redirection remplace l’entrée d’historique au lieu d’en ajouter une', () => {
    const { history } = simulerFenetre('/')
    naviguer('/portefeuilles/1', { remplacer: true })
    expect(history.replaceState).toHaveBeenCalledOnce()
    expect(history.pushState).not.toHaveBeenCalled()
  })
})
