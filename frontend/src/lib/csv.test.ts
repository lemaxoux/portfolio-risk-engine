import { describe, expect, it } from 'vitest'

import { nomDecimale, nomEncodage, nomEspace } from './csv'

describe('les codes du format CSV, nommés en français', () => {
  it('nomme les trois encodages que le lecteur reconnaît', () => {
    expect(nomEncodage('cp1252')).toBe('Windows-1252 (CP1252)')
    expect(nomEncodage('utf-8')).toBe('UTF-8')
    expect(nomEncodage('utf-8-sig')).toContain('BOM')
  })

  it('laisse un code inconnu tel quel plutôt que d’inventer un nom', () => {
    expect(nomEncodage('latin-9')).toBe('latin-9')
    expect(nomEspace('\u2009')).toBe('U+2009')
  })

  it('nomme les espaces de milliers, invisibles une fois écrites', () => {
    expect(nomEspace(' ')).toBe('ordinaire')
    expect(nomEspace('\u00A0')).toBe('insécable')
    expect(nomEspace('\u202F')).toBe('fine insécable')
  })

  it('dit ce que « mixte » et « aucune » veulent dire', () => {
    expect(nomDecimale('mixte')).toContain('virgules et points')
    expect(nomDecimale('aucune')).toContain('entiers')
    expect(nomDecimale(',')).toBe('«\u00A0,\u00A0»')
  })
})
