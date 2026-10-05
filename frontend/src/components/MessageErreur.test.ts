/**
 * `<MessageErreur>` : un refus précédé de son numéro de ligne s'écrit « Ligne
 * 4 : ticker inconnu », deux-points et minuscule, sans tiret (DESIGN.md §6.3).
 * Rendu côté serveur.
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ApiErreur } from '../api/client'
import { ESPACE_INSECABLE } from '../lib/format'
import { MessageErreur } from './MessageErreur'

/** Le texte rendu, balises retirées, apostrophes décodées (React écrit « &#x27; »). */
function texte(erreur: ApiErreur): string {
  return renderToStaticMarkup(createElement(MessageErreur, { erreur }))
    .replace(/<[^>]+>/g, '')
    .replaceAll('&#x27;', "'")
}

// Les messages du backend, tels que `backend/api/validation.py` les écrit.
const INCONNU = `XYZ n'est pas un titre connu. Titres disponibles${ESPACE_INSECABLE}: ALFA, MIKE.`
const DOUBLE = 'MSFT apparaît deux fois.'
const VIDE = 'Ticker vide.'

describe('un refus et son numéro de ligne', () => {
  it('un seul problème : la ligne, deux-points, puis le refus, sujet d’abord', () => {
    const erreur = new ApiErreur(422, INCONNU, [
      { line: 4, field: 'ticker', value: 'XYZ', problem: INCONNU },
    ])
    const rendu = texte(erreur)
    expect(rendu).toBe(
      `Ligne 4${ESPACE_INSECABLE}: XYZ n'est pas un titre connu. Titres disponibles${ESPACE_INSECABLE}: ALFA, MIKE.`,
    )
    // Pas de double deux-points : la première phrase n'en porte qu'un.
    expect(rendu.split('.')[0]?.split(':')).toHaveLength(2)
  })

  it('plusieurs problèmes : chacun sa ligne ; minuscule après le deux-points, sauf un ticker', () => {
    const erreur = new ApiErreur(422, '3 lignes refusées.', [
      { line: 4, field: 'ticker', value: 'XYZ', problem: INCONNU },
      { line: 7, field: 'ticker', value: 'MSFT', problem: DOUBLE },
      { line: 9, field: 'ticker', value: '', problem: VIDE },
    ])
    const rendu = texte(erreur)
    expect(rendu).toContain(`Ligne 4${ESPACE_INSECABLE}: XYZ n'est pas un titre connu.`)
    expect(rendu).toContain(`Ligne 7${ESPACE_INSECABLE}: MSFT apparaît deux fois.`)
    expect(rendu).toContain(`Ligne 9${ESPACE_INSECABLE}: ticker vide.`)
  })

  it('sans numéro de ligne, le message passe tel quel', () => {
    const detail = 'Aucune position soumise.'
    const erreur = new ApiErreur(422, detail, [
      { line: null, field: null, value: null, problem: detail },
    ])
    expect(texte(erreur)).toBe(detail)
  })

  it('n’écrit aucun tiret cadratin', () => {
    const erreur = new ApiErreur(422, INCONNU, [
      { line: 4, field: 'ticker', value: 'XYZ', problem: INCONNU },
    ])
    expect(texte(erreur)).not.toContain('\u2014')
  })
})
