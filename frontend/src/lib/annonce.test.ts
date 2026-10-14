/**
 * L'annonce d'un geste : sur sa page, dans sa langue (chantier 9.6).
 *
 * Constaté par Cowork le 2026-10-14 : sur `/portefeuilles/saisi`, après le
 * passage du français à l'anglais (l'acceptation anglaise, puis l'analyse
 * anglaise), « Positions gardées dans ce navigateur […] » restait en français.
 * Changer de langue retire l'annonce, et revenir à la première ne la rend pas.
 */
import { describe, expect, it } from 'vitest'

import { LIBELLES } from '../contenu/libelles'
import { annonceDeLaPage, annonceGardee, type Annonce } from './annonce'

const ANALYSE_DU_SAISI = '/portefeuilles/saisi'

/** L'annonce de l'analyse acceptée, écrite en français. */
const GARDEES: Annonce = {
  texte: LIBELLES.fr.positionsDuSite.gardees('2026-10-14', 2),
  page: ANALYSE_DU_SAISI,
  langue: 'fr',
}

describe('une annonce', () => {
  it('s’affiche sur sa page, dans la langue de son geste', () => {
    expect(annonceDeLaPage(GARDEES, ANALYSE_DU_SAISI, 'fr')).toBe(GARDEES.texte)
    expect(GARDEES.texte).toContain('Positions gardées dans ce navigateur')
  })

  it('ne s’affiche pas sur une autre page', () => {
    expect(annonceDeLaPage(GARDEES, '/portefeuilles', 'fr')).toBeNull()
    expect(annonceDeLaPage(GARDEES, '/portefeuilles/saisi/positions', 'fr')).toBeNull()
  })

  it('ne s’affiche pas dans l’autre langue, dans un sens comme dans l’autre', () => {
    expect(annonceDeLaPage(GARDEES, ANALYSE_DU_SAISI, 'en')).toBeNull()
    const anglaise: Annonce = {
      texte: LIBELLES.en.positionsDuSite.gardees('2026-10-14', 2),
      page: ANALYSE_DU_SAISI,
      langue: 'en',
    }
    expect(annonceDeLaPage(anglaise, ANALYSE_DU_SAISI, 'fr')).toBeNull()
    expect(annonceDeLaPage(anglaise, ANALYSE_DU_SAISI, 'en')).toBe(anglaise.texte)
  })

  it('changer de langue la retire, et revenir à la première ne la rend pas', () => {
    // L'état de l'application, langue après langue : français, anglais, français.
    let etat: Annonce | null = GARDEES
    etat = annonceGardee(etat, 'en')
    expect(etat).toBeNull()
    etat = annonceGardee(etat, 'fr')
    expect(annonceDeLaPage(etat, ANALYSE_DU_SAISI, 'fr')).toBeNull()
  })

  it('dans la langue du geste, elle reste telle quelle', () => {
    // Le même objet : l'état ne change pas, la page ne se rend pas de nouveau.
    expect(annonceGardee(GARDEES, 'fr')).toBe(GARDEES)
    expect(annonceGardee(null, 'fr')).toBeNull()
  })
})
