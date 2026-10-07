/**
 * La grammaire fermée des contenus rédigés : ce qu'elle lit, et tout ce
 * qu'elle refuse, avec la ligne fautive.
 */
import { describe, expect, it } from 'vitest'

import { ESPACE_FINE, ESPACE_INSECABLE } from './format'
import { ErreurDeContenu, lireContenu, texteDe, type Bloc } from './contenu'

const NBSP = ESPACE_INSECABLE
const NNBSP = ESPACE_FINE

const MODELE = [
  '# Méthodologie',
  '',
  "L'introduction, sur deux",
  'lignes&nbsp;: S&P 500.',
  '',
  '## Une partie {#une-partie}',
  '',
  '### Une entrée {#une-entree}',
  '',
  '**Hypothèses.** Un texte avec $σ_{p}$ et [un lien](#une-partie).',
  '',
  '- **Au point bas**&nbsp;: un élément.',
  '- Un autre, à 95&#x202F;%.',
  '',
  '$$VaR_{α} = z_{α} × σ_{p}^{2}$$',
  '',
].join('\n')

function bloc(rang: number): Bloc {
  const trouve = lireContenu(MODELE).blocs[rang]
  if (trouve === undefined) throw new Error(`pas de bloc ${rang}`)
  return trouve
}

describe('ce que le lecteur lit', () => {
  it('le titre de la page, les parties et les ancres, dans l’ordre', () => {
    const contenu = lireContenu(MODELE)
    expect(contenu.titre).toBe('Méthodologie')
    expect(contenu.parties).toEqual([{ ancre: 'une-partie', titre: 'Une partie' }])
    expect(contenu.ancres).toEqual(['une-partie', 'une-entree'])
    expect(contenu.blocs.map((b) => b.type)).toEqual([
      'titre',
      'paragraphe',
      'titre',
      'titre',
      'paragraphe',
      'liste',
      'formule',
    ])
  })

  it('un paragraphe sur plusieurs lignes, les entités décodées, « S&P » tel quel', () => {
    const intro = bloc(1)
    expect(intro.type === 'paragraphe' && texteDe(intro.contenu)).toBe(
      `L'introduction, sur deux lignes${NBSP}: S&P 500.`,
    )
  })

  it('une étiquette en tête, une formule en ligne, un lien vers une ancre', () => {
    const corps = bloc(4)
    if (corps.type !== 'paragraphe') throw new Error('paragraphe attendu')
    expect(corps.etiquette).toBe('Hypothèses.')
    expect(corps.contenu).toEqual([
      { type: 'texte', texte: ' Un texte avec ' },
      {
        type: 'formule',
        morceaux: [
          { texte: 'σ', position: 'ligne' },
          { texte: 'p', position: 'indice' },
        ],
      },
      { type: 'texte', texte: ' et ' },
      { type: 'lien', cible: 'une-partie', contenu: [{ type: 'texte', texte: 'un lien' }] },
      { type: 'texte', texte: '.' },
    ])
  })

  it('une liste, chaque élément avec son étiquette éventuelle', () => {
    const liste = bloc(5)
    if (liste.type !== 'liste') throw new Error('liste attendue')
    expect(liste.elements.map((e) => [e.etiquette, texteDe(e.contenu)])).toEqual([
      ['Au point bas', `${NBSP}: un élément.`],
      [null, `Un autre, à 95${NNBSP}%.`],
    ])
  })

  it('une formule en bloc, ses indices et ses exposants', () => {
    const formule = bloc(6)
    if (formule.type !== 'formule') throw new Error('formule attendue')
    expect(formule.morceaux).toEqual([
      { texte: 'VaR', position: 'ligne' },
      { texte: 'α', position: 'indice' },
      { texte: ' = z', position: 'ligne' },
      { texte: 'α', position: 'indice' },
      { texte: ' × σ', position: 'ligne' },
      { texte: 'p', position: 'indice' },
      { texte: '2', position: 'exposant' },
    ])
  })

  it('les fins de ligne CRLF valent LF', () => {
    expect(lireContenu(MODELE.replaceAll('\n', '\r\n'))).toEqual(lireContenu(MODELE))
  })
})

describe('ce que le lecteur refuse, avec la ligne fautive', () => {
  const refus: [string, string, number][] = [
    ['sans titre de page', 'Un paragraphe.\n\n## P {#p}', 1],
    ['un second titre de page', '# A\n\n# B', 3],
    ['un titre de page avec ancre', '# A {#a}', 1],
    ['une partie sans ancre', '# A\n\n## Partie', 3],
    ['une ancre mal formée', '# A\n\n## Partie {#Partie}', 3],
    ['un quatrième niveau de titre', '# A\n\n## P {#p}\n\n#### Q {#q}', 5],
    ['une entrée avant toute partie', '# A\n\n### E {#e}', 3],
    ['une ancre en double', '# A\n\n## P {#p}\n\n### E {#p}', 5],
    ['un lien vers une ancre absente', '# A\n\n## P {#p}\n\nVoir [là](#ailleurs).', 5],
    ['un lien vers une page', '# A\n\n## P {#p}\n\nVoir [là](/ailleurs).', 5],
    ['un lien dans un titre', '# A\n\n## P [x](#p) {#p}', 3],
    ['une formule non fermée', '# A\n\nUn $σ sans fin.', 3],
    ['un indice sans accolade', '# A\n\nUn $σ_p$ nu.', 3],
    ['une accolade isolée dans une formule', '# A\n\nUn $σ}$ fautif.', 3],
    ['une entité hors liste', '# A\n\nUn &amp; ici.', 3],
    ['du HTML', '# A\n\nUn <b>gras</b> ici.', 3],
    ['de l’italique', '# A\n\nUn *mot* ici.', 3],
    ['un trait bas hors formule', '# A\n\nUn _mot_ ici.', 3],
    ['un tableau', '# A\n\n| a | b |', 3],
    ['une liste numérotée', '# A\n\n1. un', 3],
    ['une liste qui se poursuit en texte', '# A\n\n- un\nsuite', 4],
    ['un titre suivi d’une ligne', '# A\nsuite', 1],
    ['une formule en bloc suivie de texte', '# A\n\n$$x$$\nsuite', 3],
    ['un blanc en fin de ligne', '# A\n\nUn texte. ', 3],
    ['une ligne en retrait', '# A\n\n    du code', 3],
    ['une accolade dans le texte', '# A\n\nUn {mot} ici.', 3],
  ]

  it.each(refus)('%s', (_libelle, source, ligne) => {
    let erreur: unknown = null
    try {
      lireContenu(source)
    } catch (e) {
      erreur = e
    }
    expect(erreur).toBeInstanceOf(ErreurDeContenu)
    expect((erreur as ErreurDeContenu).ligne).toBe(ligne)
    expect((erreur as ErreurDeContenu).message).toMatch(new RegExp(`^Ligne ${ligne}, `))
  })
})
