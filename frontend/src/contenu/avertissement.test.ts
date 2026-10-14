/**
 * La démonstration sans écran d'acceptation — DESIGN.md §19.5, §19.6
 * (chantier 9.4).
 *
 * Le texte de l'acceptation y reste lisible sur une page, `/avertissement`,
 * à un clic de chaque page : un lien termine la mention, et la liste des
 * pages finit par elle. Le rendu se vérifie dans un navigateur ; ici, les
 * fonctions pures qui décident des adresses et de la liste.
 */
import { describe, expect, it } from 'vitest'

import { pagesApplication } from '../components/Navigation'
import { cheminDe, lireRoute, type Route } from '../lib/route'
import { destinationDe } from '../views/Acceptation'
import { DATE_DE_LA_DEMO, PORTEFEUILLES_DE_LA_DEMO } from './demo'
import { LIBELLES, type PageDuSite } from './libelles'

const LANGUES = ['fr', 'en'] as const

describe('l’adresse de l’avertissement', () => {
  it('est la sixième adresse, lue avec ou sans barre finale', () => {
    expect(lireRoute('/avertissement')).toEqual({ vue: 'avertissement' })
    expect(lireRoute('/avertissement/')).toEqual({ vue: 'avertissement' })
    expect(cheminDe({ vue: 'avertissement' })).toBe('/avertissement')
    expect(lireRoute(cheminDe({ vue: 'avertissement' }))).toEqual({ vue: 'avertissement' })
  })

  it('ne devine rien au-delà', () => {
    for (const chemin of ['/avertissement/texte', '/avertissements', '/Avertissement', '/disclaimer']) {
      expect(lireRoute(chemin)).toEqual({ vue: 'inconnue', chemin })
    }
  })

  it('n’est celle d’aucune page pour l’écran d’acceptation : « la page demandée »', () => {
    const route: Route = { vue: 'avertissement' }
    for (const demo of [false, true]) {
      expect(destinationDe(route, demo)).toBe('page')
      expect(destinationDe(route, demo)).toBe(destinationDe({ vue: 'inconnue', chemin: '/rien' }, demo))
    }
  })
})

describe('la liste des pages de la démonstration', () => {
  const COURANTES: PageDuSite[] = ['presentation', 'analyse', 'portefeuilles', 'methodologie', 'avertissement']

  it('commence par « Présentation » et finit par « Avertissement »', () => {
    for (const courante of COURANTES) {
      for (const id of [2, null]) {
        const pages = pagesApplication(courante, id, 'fr', true)
        expect(pages[0], courante).toMatchObject({ vers: '/', libelle: 'Présentation' })
        expect(pages.at(-1), courante).toMatchObject({ vers: '/avertissement', libelle: 'Avertissement' })
      }
    }
    const anglaises = pagesApplication('presentation', null, 'en', true)
    expect(anglaises.map((page) => page.libelle)).toEqual(['Overview', 'Portfolios', 'Methodology', 'Disclaimer'])
  })

  it('ne propose « Analyse » qu’avec un portefeuille en vue', () => {
    expect(pagesApplication('presentation', null, 'fr', true).map((page) => page.vers)).toEqual([
      '/',
      '/portefeuilles',
      '/methodologie',
      '/avertissement',
    ])
    expect(pagesApplication('avertissement', 2, 'fr', true).map((page) => page.vers)).toEqual([
      '/',
      '/portefeuilles/2',
      '/portefeuilles',
      '/methodologie',
      '/avertissement',
    ])
  })

  it('marque la page courante, et elle seule, depuis chacune', () => {
    const attendue: Record<PageDuSite, string | null> = {
      presentation: '/',
      analyse: '/portefeuilles/2',
      // La démonstration n'a pas de page de saisie : rien n'est marqué.
      positions: null,
      portefeuilles: '/portefeuilles',
      methodologie: '/methodologie',
      avertissement: '/avertissement',
    }
    for (const [courante, vers] of Object.entries(attendue)) {
      const marquees = pagesApplication(courante as PageDuSite, 2, 'fr', true).filter((page) => page.courante)
      expect(marquees.map((page) => page.vers), courante).toEqual(vers === null ? [] : [vers])
    }
  })

  it('hors démonstration, ni « Présentation » ni « Avertissement » : c’est le défaut', () => {
    for (const langue of LANGUES) {
      const noms = LIBELLES[langue].navigation.pages
      for (const id of [2, null]) {
        const pages = pagesApplication('methodologie', id, langue)
        expect(pages).toEqual(pagesApplication('methodologie', id, langue, false))
        expect(pages.map((page) => page.libelle)).not.toContain(noms.presentation)
        expect(pages.map((page) => page.libelle)).not.toContain(noms.avertissement)
        expect(pages.map((page) => page.vers).filter((vers) => vers === '/' || vers === '/avertissement')).toEqual([])
      }
    }
  })
})

describe('le lien de la mention', () => {
  it('est un libellé à part : la phrase de la mention ne le contient pas', () => {
    for (const langue of LANGUES) {
      const l = LIBELLES[langue].demo
      const mention = l.mention(PORTEFEUILLES_DE_LA_DEMO, DATE_DE_LA_DEMO)
      expect(mention).not.toContain(l.lireLAvertissement)
      expect(mention.endsWith('.')).toBe(true)
      expect(l.lireLAvertissement.endsWith('.')).toBe(false)
    }
    expect(LIBELLES.fr.demo.lireLAvertissement).toBe("Lire l'avertissement")
    expect(LIBELLES.en.demo.lireLAvertissement).toBe('Read the disclaimer')
  })
})

describe('la phrase de la page', () => {
  it('dit quand le texte est à accepter, dans les deux langues', () => {
    expect(LIBELLES.fr.avertissement.pourquoi).toBe(
      "Le site demande d'accepter ce texte avant d'analyser un portefeuille que vous saisissez. " +
        "Les portefeuilles d'exemple se lisent sans l'accepter\u00a0: aucun n'est le vôtre.",
    )
    expect(LIBELLES.en.avertissement.pourquoi).toBe(
      'The site asks you to accept this text before it analyzes a portfolio that you enter. ' +
        'The sample portfolios can be read without accepting it: none of them is yours.',
    )
  })

  it('ne demande rien au lecteur : ni case, ni engagement à la première personne', () => {
    const mots = (texte: string) => texte.toLowerCase().split(/[^a-zà-ÿ]+/)
    for (const interdit of ['je', 'j', 'cocher', 'case']) {
      expect(mots(LIBELLES.fr.avertissement.pourquoi)).not.toContain(interdit)
    }
    for (const interdit of ['i', 'check', 'checked', 'box']) {
      expect(mots(LIBELLES.en.avertissement.pourquoi)).not.toContain(interdit)
    }
    // Le contrôle voit ce qu'il doit voir : la phrase de confirmation du fichier.
    expect(mots("J'ai lu ces limites")).toContain('j')
    expect(mots('I have read these limitations')).toContain('i')
  })
})
