/**
 * Les phrases du bandeau et des blocs mesure.
 *
 * Ce qui est vérifié : les formulations exactes de §8.1, le fait qu'aucune
 * lecture de niveau de confiance ne soit DÉRIVÉE, et le changement de phrase
 * quand une perte est négative.
 */
import { describe, expect, it } from 'vitest'

import type { LimitingPosition, Window } from '../api/types'
import { ESPACE_FINE, ESPACE_INSECABLE } from './format'
import {
  cite,
  frequenceLue,
  lectureDeCVaR,
  lectureDeVar,
  phraseFenetreReduite,
  phraseFraicheurPositions,
} from './phrases'

const PLEINE: Window = {
  requested: 504,
  observations: 504,
  start: '2024-09-05',
  end: '2026-09-09',
  complete: true,
}

const REDUITE: Window = {
  requested: 504,
  observations: 40,
  start: '2026-07-15',
  end: '2026-09-09',
  complete: false,
}

const NEWCO: LimitingPosition = {
  ticker: 'NEWCO',
  first_available: '2026-07-14',
}

describe('lecture d’un niveau de confiance', () => {
  it('traduit les niveaux que l’API publie', () => {
    expect(frequenceLue(0.95)).toBe('une séance sur vingt')
    expect(frequenceLue(0.99)).toBe('une séance sur cent')
  })

  it('n’invente pas de traduction pour un niveau inconnu', () => {
    // Une table, pas une division : 1/(1−0,85) vaudrait 6,67, et il faudrait
    // décider comment l'écrire — c'est-à-dire inventer une lecture.
    expect(frequenceLue(0.85)).toBeNull()
    expect(lectureDeVar(0.02, 0.85, 2)).toBe(
      `perte d'au moins 2,00${ESPACE_FINE}%, au niveau de confiance 85${ESPACE_FINE}%`,
    )
  })

  it('accompagne le terme technique, il ne le remplace pas', () => {
    expect(lectureDeVar(0.0138, 0.95, 2)).toBe(
      `perte d'au moins 1,38${ESPACE_FINE}%, une séance sur vingt`,
    )
    expect(lectureDeCVaR(0.99)).toBe(
      `perte moyenne des 1${ESPACE_FINE}% de séances les pires`,
    )
  })
})

describe('une VaR est un seuil dépassé, pas une perte attendue', () => {
  it('dit « d’au moins », comme la convention de risk_engine/var.py', () => {
    // Une séance sur vingt, la perte ATTEINT OU DÉPASSE le seuil. Ce qu'elle
    // vaut en moyenne ces jours-là est la CVaR : « perte attendue » ferait lire
    // le seuil comme cette moyenne, et sous-estimerait la queue.
    for (const confiance of [0.95, 0.99, 0.85]) {
      const phrase = lectureDeVar(0.0138, confiance, 2)
      expect(phrase).toMatch(/^perte d'au moins /)
      expect(phrase).not.toContain('attendue')
    }
  })

  it('écrit le seuil avec les décimales du chiffre affiché au-dessus', () => {
    expect(lectureDeVar(0.013849, 0.95, 2)).toContain(`1,38${ESPACE_FINE}%`)
    expect(lectureDeVar(0.013849, 0.95, 1)).toContain(`1,4${ESPACE_FINE}%`)
  })

  it('ne se confond pas avec la phrase de la CVaR, qui est une moyenne', () => {
    expect(lectureDeCVaR(0.95)).toContain('moyenne')
    expect(lectureDeVar(0.0138, 0.95, 2)).not.toContain('moyenne')
  })
})

describe('convention de signe (§9.1, règle 2)', () => {
  it('change la PHRASE quand la perte est négative', () => {
    // Une valeur négative ne veut pas dire « petite perte » : elle veut dire
    // qu'à ce niveau de confiance, le quantile est un gain.
    const phrase = lectureDeVar(-0.0021, 0.95, 2)
    expect(phrase).toContain('gain')
    expect(phrase).not.toContain("perte d'au moins")
  })

  it('ne retourne pas le signe du chiffre affiché, et ne promet pas l’absence de perte', () => {
    // Le chiffre s'affiche tel que le moteur l'a rendu, « −0,21 % » ; la
    // phrase qui l'accompagne n'en écrit pas une deuxième version, positive.
    // Et un quantile positif laisse une séance sur vingt sous lui : certaines
    // peuvent être des pertes, « le portefeuille ne perd pas » serait faux.
    const phrase = lectureDeVar(-0.0021, 0.95, 2)
    expect(phrase).not.toMatch(/\d/)
    expect(phrase).not.toContain('ne perd pas')
    expect(lectureDeVar(-0.0021, 0.85, 2)).toContain(`85${ESPACE_FINE}%`)
  })

  it('garde la phrase de perte pour une valeur nulle ou positive', () => {
    expect(lectureDeVar(0, 0.95, 2)).toBe(
      `perte d'au moins 0,00${ESPACE_FINE}%, une séance sur vingt`,
    )
    expect(lectureDeVar(0.0138, 0.99, 2)).toBe(
      `perte d'au moins 1,38${ESPACE_FINE}%, une séance sur cent`,
    )
  })
})

describe('fraîcheur des positions (§8.1)', () => {
  it('dit quand les positions ont été modifiées', () => {
    expect(phraseFraicheurPositions('2026-09-21')).toBe(
      'Positions modifiées le 2026-09-21',
    )
  })

  it('dit explicitement qu’elles ne l’ont jamais été', () => {
    // `updated_at` nul est une information, pas un blanc : l'`as_of` date les
    // prix, pas les quantités.
    expect(phraseFraicheurPositions(null)).toBe(
      "Positions jamais modifiées depuis l'application",
    )
  })
})

describe('fenêtre réduite (§8.1)', () => {
  it('ne dit rien quand la fenêtre est pleine', () => {
    expect(phraseFenetreReduite(PLEINE, [])).toBeNull()
  })

  it('nomme la ligne limitante et la date depuis laquelle elle est cotée', () => {
    expect(phraseFenetreReduite(REDUITE, [NEWCO])).toBe(
      `Fenêtre réduite à 40${ESPACE_INSECABLE}séances ` +
        `sur 504${ESPACE_INSECABLE}demandées : ` +
        "NEWCO n'est coté que depuis le 2026-07-14.",
    )
  })

  it('ne nomme personne quand le backend n’a nommé personne', () => {
    // Liste vide : la troncature vient d'un trou au milieu d'une série plutôt
    // que d'une entrée en cotation tardive. Mieux vaut ne désigner personne que
    // désigner à tort.
    const phrase = phraseFenetreReduite(REDUITE, [])
    expect(phrase).toBe(
      `Fenêtre réduite à 40${ESPACE_INSECABLE}séances ` +
        `sur 504${ESPACE_INSECABLE}demandées (historique incomplet).`,
    )
    expect(phrase).not.toContain('NEWCO')
  })

  it('énumère plusieurs lignes limitantes sans en oublier', () => {
    const phrase = phraseFenetreReduite(REDUITE, [
      NEWCO,
      { ticker: 'ACME', first_available: '2026-06-02' },
    ])
    expect(phrase).toContain('NEWCO')
    expect(phrase).toContain('ACME, depuis le 2026-06-02')
  })

  it('est le SEUL endroit du bandeau qui cite la fenêtre demandée', () => {
    // Partout ailleurs le bandeau annonce la fenêtre OBTENUE : annoncer 504
    // quand le calcul a tourné sur 40 promettrait une profondeur d'historique
    // que le rapport n'a pas.
    expect(phraseFenetreReduite(REDUITE, [NEWCO])).toContain('504')
    expect(phraseFenetreReduite(REDUITE, [NEWCO])).toContain('40')
  })
})

describe('cite', () => {
  it('relie les guillemets au nom par des espaces insécables', () => {
    expect(cite('Démo')).toBe('«\u00A0Démo\u00A0»')
  })
})
