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
  it('lit les cinq adresses', () => {
    expect(lireRoute('/')).toEqual({ vue: 'accueil' })
    expect(lireRoute('/portefeuilles')).toEqual({ vue: 'portefeuilles' })
    expect(lireRoute('/portefeuilles/3')).toEqual({ vue: 'analyse', id: 3 })
    expect(lireRoute('/portefeuilles/3/positions')).toEqual({ vue: 'positions', id: 3 })
    expect(lireRoute('/methodologie')).toEqual({ vue: 'methodologie' })
  })

  it('tolère une barre oblique finale', () => {
    expect(lireRoute('/portefeuilles/')).toEqual({ vue: 'portefeuilles' })
    expect(lireRoute('/portefeuilles/12/')).toEqual({ vue: 'analyse', id: 12 })
    expect(lireRoute('/methodologie/')).toEqual({ vue: 'methodologie' })
  })

  it('ne devine pas une adresse qu’elle ne connaît pas', () => {
    for (const chemin of [
      '/methodologie/cvar',
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
      { vue: 'methodologie' },
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

function simulerFenetre(depart: string, scrollY = 0) {
  const location = { pathname: depart }
  const history = {
    pushState: vi.fn((_etat: unknown, _titre: string, chemin: string) => {
      location.pathname = chemin
    }),
    // Sans adresse, l'entrée garde la sienne, comme dans le navigateur.
    replaceState: vi.fn((_etat: unknown, _titre: string, chemin?: string) => {
      if (chemin !== undefined) location.pathname = chemin
    }),
  }
  vi.stubGlobal('window', {
    location,
    history,
    scrollY,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })
  return { location, history }
}

describe('naviguer et la garde', () => {
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

describe('la note d’un lien vers la méthode (chantier 7E)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('est écrite dans l’entrée quittée, avec la position, AVANT d’en ouvrir une autre', () => {
    const { location, history } = simulerFenetre('/portefeuilles/1', 4757.4)
    naviguer('/methodologie#var-historique', { retour: 'var-historique-0.99#var-historique' })
    expect(history.replaceState).toHaveBeenCalledExactlyOnceWith(
      { retour: { cle: 'var-historique-0.99#var-historique', y: 4757 } },
      '',
    )
    const [noter] = history.replaceState.mock.invocationCallOrder
    const [partir] = history.pushState.mock.invocationCallOrder
    expect(noter).toBeLessThan(partir ?? 0)
    expect(location.pathname).toBe('/methodologie#var-historique')
  })

  it('un lien sans clé l’efface : un retour ne rend pas une place qu’un autre lien a quittée', () => {
    const { history } = simulerFenetre('/portefeuilles/1', 900)
    naviguer('/portefeuilles')
    expect(history.replaceState).toHaveBeenCalledExactlyOnceWith({ retour: null }, '')
  })

  it('une redirection n’en écrit pas', () => {
    const { history } = simulerFenetre('/')
    naviguer('/portefeuilles/1', { remplacer: true })
    expect(history.replaceState).toHaveBeenCalledExactlyOnceWith(null, '', '/portefeuilles/1')
  })
})
