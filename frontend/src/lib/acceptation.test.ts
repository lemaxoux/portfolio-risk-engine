/**
 * L'empreinte de l'acceptation.
 *
 * Ce qui est vérifié n'est pas la qualité cryptographique du hachage — elle
 * n'entre pas en jeu — mais la seule propriété dont dépend l'écran : un texte
 * MODIFIÉ produit une empreinte DIFFÉRENTE, donc l'écran revient.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CLE_ACCEPTATION,
  aAccepte,
  acceptationMemorisee,
  cleAcceptation,
  empreinte,
  memoriserAcceptation,
} from './acceptation'

const TEXTE = [
  "Avant d'utiliser Mx Risk MGT",
  '',
  'Un outil informatif, pas un conseil',
  'Mx Risk MGT décrit des propriétés statistiques de votre portefeuille.',
].join('\n')

function stockageEnMemoire() {
  const donnees = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (cle: string) => donnees.get(cle) ?? null,
    setItem: (cle: string, valeur: string) => donnees.set(cle, valeur),
    removeItem: (cle: string) => donnees.delete(cle),
  })
  return donnees
}

describe('empreinte', () => {
  it('est stable pour un même texte', () => {
    expect(empreinte(TEXTE)).toBe(empreinte(TEXTE))
  })

  it('change dès qu’un caractère change', () => {
    // LA propriété qui compte : une limite reformulée fait revenir l'écran.
    expect(empreinte(TEXTE)).not.toBe(empreinte(`${TEXTE}.`))
    expect(empreinte('504 séances')).not.toBe(empreinte('252 séances'))
    expect(empreinte('a')).not.toBe(empreinte('b'))
  })

  it('distingue deux textes de longueurs différentes, quoi qu’il arrive', () => {
    // La longueur est jointe à l'empreinte : même en cas de collision des 32
    // bits, deux textes de tailles différentes ne peuvent pas se confondre.
    const court = empreinte('court')
    const long = empreinte('un texte nettement plus long')
    expect(court.split('-')[1]).not.toBe(long.split('-')[1])
  })

  it('ne dépend pas de l’encodage des accents en surface', () => {
    // « é » précomposé et « e » + accent combinant sont deux textes différents,
    // et ils DOIVENT produire deux empreintes différentes : l'octet qui change
    // est un octet du texte servi.
    expect(empreinte('propriété')).not.toBe(empreinte('propriété'))
  })
})

describe('mémorisation', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('mémorise l’empreinte, pas un simple « oui »', () => {
    const donnees = stockageEnMemoire()
    memoriserAcceptation(TEXTE)
    expect(donnees.get(CLE_ACCEPTATION)).toBe(empreinte(TEXTE))
    expect(donnees.get(CLE_ACCEPTATION)).not.toBe('true')
  })

  it('reconnaît le texte accepté', () => {
    stockageEnMemoire()
    expect(aAccepte(TEXTE)).toBe(false)
    memoriserAcceptation(TEXTE)
    expect(aAccepte(TEXTE)).toBe(true)
  })

  it('redemande quand le texte a changé depuis l’acceptation', () => {
    stockageEnMemoire()
    memoriserAcceptation(TEXTE)
    const reformule = TEXTE.replace(
      'des propriétés statistiques',
      'certaines propriétés statistiques',
    )
    expect(reformule).not.toBe(TEXTE)
    expect(aAccepte(reformule)).toBe(false)
    // Et le texte d'origine reste accepté : c'est bien le texte qui décide.
    expect(aAccepte(TEXTE)).toBe(true)
  })

  it('redemande quand le stockage est bloqué, sans lever', () => {
    // `localStorage` LÈVE quand le stockage est refusé — il ne rend pas null.
    // Une acceptation qu'on ne peut pas mémoriser doit être redemandée, pas
    // supposée acquise ; et l'application doit démarrer quand même.
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new DOMException('refusé')
      },
      setItem: () => {
        throw new DOMException('refusé')
      },
    })
    expect(() => memoriserAcceptation(TEXTE)).not.toThrow()
    expect(acceptationMemorisee()).toBeNull()
    expect(aAccepte(TEXTE)).toBe(false)
  })
})

describe('une acceptation par langue', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('la clé française est celle d’avant le chantier ; l’anglaise s’y ajoute', () => {
    expect(cleAcceptation('fr')).toBe('mx-risk-acceptation')
    expect(cleAcceptation()).toBe(CLE_ACCEPTATION)
    expect(cleAcceptation('en')).toBe('mx-risk-acceptation-en')
  })

  it('accepter l’anglais ne vaut pas pour le français, ni l’inverse', () => {
    const donnees = stockageEnMemoire()
    const anglais = 'Before using Mx Risk MGT'
    memoriserAcceptation(anglais, 'en')
    expect(aAccepte(anglais, 'en')).toBe(true)
    expect(aAccepte(TEXTE, 'fr')).toBe(false)
    expect(donnees.has(CLE_ACCEPTATION)).toBe(false)
    memoriserAcceptation(TEXTE, 'fr')
    expect(aAccepte(TEXTE)).toBe(true)
    expect(aAccepte(TEXTE, 'en')).toBe(false)
  })

  it('l’aller-retour entre les langues ne redemande rien', () => {
    stockageEnMemoire()
    memoriserAcceptation(TEXTE, 'fr')
    memoriserAcceptation('Before using Mx Risk MGT', 'en')
    expect(aAccepte(TEXTE, 'fr')).toBe(true)
    expect(aAccepte('Before using Mx Risk MGT', 'en')).toBe(true)
    expect(acceptationMemorisee('en')).toBe(empreinte('Before using Mx Risk MGT'))
  })
})
