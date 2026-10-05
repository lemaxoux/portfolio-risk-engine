/**
 * `<Measure>` et les textes de lecture : le chiffre, la phrase concrète, la
 * ligne de ce que le chiffre ne dit pas, puis les « Détails du calcul ».
 *
 * L'intertitre NOMME la provenance, il ne la replie pas : §9.1, règle 1, ne
 * veut ni infobulle ni accordéon ni « voir les détails ». Rendu côté serveur.
 */
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { Measure } from './Measure'
import styles from './Measure.module.css'

function rendre(neDitPas: string | null): string {
  return renderToStaticMarkup(
    createElement(Measure, {
      libelle: 'VaR 95 historique',
      valeur: '1,06',
      lecture: 'Ces deux dernières années, environ un jour de bourse sur vingt.',
      neDitPas,
      provenance: [{ libelle: 'Méthode', valeur: 'historique' }],
    }),
  ).replaceAll('&#x27;', "'")
}

describe('<Measure> et sa lecture', () => {
  it('dans l’ordre : le chiffre, la lecture, ce qu’il ne dit pas, les détails', () => {
    const html = rendre("Ce n'est pas un plafond.")
    const positions = [
      '1,06',
      'Ces deux dernières années',
      "Ce n'est pas un plafond.",
      'Détails du calcul',
      'Méthode',
    ].map((texte) => html.indexOf(texte))
    expect(positions.every((position) => position >= 0)).toBe(true)
    expect([...positions].sort((a, b) => a - b)).toEqual(positions)
  })

  it('les détails du calcul restent dans le flux, jamais repliés', () => {
    const html = rendre(null)
    expect(html).toContain('Détails du calcul')
    expect(html).not.toContain('<details')
    expect(html).not.toContain('<summary')
  })

  it('sans ligne « ne dit pas », aucun paragraphe vide', () => {
    expect(rendre(null)).not.toContain(styles.neDitPas)
    expect(rendre('Une ligne.')).toContain(styles.neDitPas)
  })
})
