/**
 * Blocs de provenance : chaque ligne sort d'un champ de la réponse.
 *
 * Ce qui est vérifié ici : l'ordre et le libellé des lignes qui portent un
 * piège de lecture — ν, qui se confond avec v en IBM Plex Sans.
 */
import { describe, expect, it } from 'vitest'

import type { Var, Window } from '../api/types'
import { provenanceDeVar } from './provenance'

const FENETRE: Window = {
  requested: 504,
  observations: 504,
  start: '2024-09-05',
  end: '2026-09-09',
  complete: true,
}

const STUDENT: Var = {
  value: 0.0127,
  confidence: 0.95,
  method: 'Student paramétrique',
  detail: 'ν = 4,07 (MLE sur 504\u00a0séances), variance ajustée sur Σ',
  nu: 4.0731,
  window: FENETRE,
}

const NORMALE: Var = {
  value: 0.0138,
  confidence: 0.95,
  method: 'paramétrique',
  detail: 'normalité, μ = 0',
  nu: null,
  window: FENETRE,
}

describe('ν est nommé avant d’être écrit seul', () => {
  it('écrit « degrés de liberté ν = 4,07 »', () => {
    const lignes = provenanceDeVar(STUDENT)
    expect(lignes).toContainEqual({ libelle: 'Degrés de liberté', valeur: 'ν = 4,07' })
  })

  it('le nomme AVANT la ligne « Calcul », qui cite ν sans le nommer', () => {
    // Le texte rédigé par le backend commence par « ν = 4,07 » : s'il venait
    // en premier, ν serait lu « v » avant d'avoir été nommé.
    const libelles = provenanceDeVar(STUDENT).map((ligne) => ligne.libelle)
    expect(libelles.indexOf('Degrés de liberté')).toBeGreaterThanOrEqual(0)
    expect(libelles.indexOf('Degrés de liberté')).toBeLessThan(libelles.indexOf('Calcul'))
  })

  it('n’ajoute aucune ligne de ν hors loi de Student', () => {
    const lignes = provenanceDeVar(NORMALE)
    expect(lignes.map((ligne) => ligne.libelle)).not.toContain('Degrés de liberté')
    expect(lignes.some((ligne) => ligne.valeur.includes('ν'))).toBe(false)
  })
})
