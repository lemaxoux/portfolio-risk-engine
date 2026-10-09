/**
 * Les POINTS DE CODE exacts, pas l'apparence.
 *
 * « 1,38 % » écrit avec U+00A0 et « 1,38 % » écrit avec U+202F sont
 * indiscernables à l'œil, dans un terminal comme dans un rapport de test. Seule
 * la comparaison des unités de code sépare les deux, et c'est précisément la
 * différence qui existe entre deux versions d'ICU. Ces tests écrivent donc les
 * échappements, jamais les caractères — un test qui contiendrait l'espace
 * littérale ne dirait pas laquelle il attend.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import type { Langue } from './langue'
import {
  ESPACE_FINE,
  ESPACE_INSECABLE,
  LIAISON,
  SIGNE_MOINS,
  TIRET_INDEFINI,
  compte,
  dateDepuisISO,
  dateEnToutesLettres,
  dateISO,
  dateISOLiee,
  decimal,
  decimalesDeColonne,
  decimalOuTiret,
  estUnGain,
  lignes,
  pourcentage,
  pourcentageOuTiret,
  pourcentageSigne,
  seances,
  moisISO,
  montant,
  montantArrondi,
  points,
  pointsAbsolus,
  pointsEnAdjectif,
  pointsSignes,
  pointsSignesEnToutesLettres,
  pourcentageAbsolu,
  valeurDePortefeuille,
} from './format'

describe('les caractères sont ceux de backend/typography.py', () => {
  it('les constantes sont les points de code annoncés', () => {
    expect(ESPACE_FINE).toBe('\u202F')
    expect(ESPACE_FINE.codePointAt(0)).toBe(0x202f)
    expect(ESPACE_INSECABLE).toBe('\u00A0')
    expect(ESPACE_INSECABLE.codePointAt(0)).toBe(0x00a0)
    expect(SIGNE_MOINS).toBe('\u2212')
    expect(SIGNE_MOINS.codePointAt(0)).toBe(0x2212)
    // Un tiret COURT : l'interface n'emploie aucun tiret cadratin (§6.3).
    expect(TIRET_INDEFINI.codePointAt(0)).toBe(0x2013)
  })

  it('aucune espace ordinaire ne sort de ce module', () => {
    // U+0020 et U+00A0 ont la même apparence dans un rapport d'échec. Le test
    // porte donc sur l'absence du point de code, pas sur ce qu'on croit lire.
    for (const texte of [
      pourcentage(0.0138, 2),
      seances(504),
      valeurDePortefeuille(83185.85),
      dateEnToutesLettres('2026-09-09'),
    ]) {
      expect(texte).not.toContain('\u0020')
    }
  })

  it("n'emploie jamais le trait d'union U+002D comme signe négatif", () => {
    expect(decimal(-8.7, 1)).not.toContain('\u002D')
    expect(pourcentage(-0.087, 1)).not.toContain('\u002D')
  })
})

describe('decimal', () => {
  it('écrit la virgule décimale française', () => {
    expect(decimal(1.38, 2)).toBe('1,38')
    expect(decimal(13.3, 1)).toBe('13,3')
    expect(decimal(5.65, 2)).toBe('5,65')
  })

  it('groupe les milliers par une espace FINE insécable', () => {
    expect(decimal(83185.85, 2)).toBe(`83${ESPACE_FINE}185,85`)
    expect(decimal(100000, 0)).toBe(`100${ESPACE_FINE}000`)
    expect(decimal(1000, 0)).toBe(`1${ESPACE_FINE}000`)
  })

  it('ne groupe pas en deçà de mille — comme backend.typography.thousands', () => {
    expect(decimal(504, 0)).toBe('504')
    expect(decimal(999, 0)).toBe('999')
  })

  it('ne groupe jamais les décimales', () => {
    // « 0,123456 » et non « 0,123 456 » : grouper à droite de la virgule est une
    // convention typographique différente, que le backend n'applique pas.
    expect(decimal(0.123456, 6)).toBe('0,123456')
  })

  it('emploie le SIGNE MOINS pour les valeurs négatives', () => {
    expect(decimal(-44, 1)).toBe(`${SIGNE_MOINS}44,0`)
    expect(decimal(-83185.85, 2)).toBe(`${SIGNE_MOINS}83${ESPACE_FINE}185,85`)
  })

  it("ne met pas de signe sur un négatif qui s'arrondit à zéro", () => {
    // « −0,0 % » se lit comme une perte alors que le chiffre dit qu'il n'y en a
    // pas. Le zéro signé est un artefact d'arrondi, pas une information.
    expect(decimal(-0.004, 2)).toBe('0,00')
    expect(decimal(-0.0, 1)).toBe('0,0')
  })

  it('refuse une valeur non finie plutôt que d’écrire « NaN »', () => {
    // Le backend garantit déjà qu'aucun NaN ne franchit la sérialisation. Si
    // l'un arrivait quand même, il doit faire du bruit ici et non s'afficher.
    expect(() => decimal(Number.NaN, 2)).toThrow()
    expect(() => decimal(Number.POSITIVE_INFINITY, 2)).toThrow()
  })
})

describe('pourcentage', () => {
  it('convertit la fraction publiée et pose une espace FINE avant le signe', () => {
    // Chiffres de référence de §16, recalculés depuis la base locale.
    expect(pourcentage(0.0138, 2)).toBe(`1,38${ESPACE_FINE}%`)
    expect(pourcentage(0.0195, 2)).toBe(`1,95${ESPACE_FINE}%`)
    expect(pourcentage(0.133, 1)).toBe(`13,3${ESPACE_FINE}%`)
    expect(pourcentage(0.256, 1)).toBe(`25,6${ESPACE_FINE}%`)
  })

  it('écrit un niveau de confiance sans décimale', () => {
    expect(pourcentage(0.95, 0)).toBe(`95${ESPACE_FINE}%`)
    expect(pourcentage(0.99, 0)).toBe(`99${ESPACE_FINE}%`)
  })

  it('survit à la représentation binaire de la multiplication par cent', () => {
    // 0.07 * 100 vaut 7.000000000000001 en double. L'arrondi doit absorber le
    // résidu et non le montrer.
    expect(pourcentage(0.07, 1)).toBe(`7,0${ESPACE_FINE}%`)
    expect(pourcentage(0.0138, 2)).not.toContain('0000')
  })

  it('écrit un rendement négatif de scénario avec le signe moins', () => {
    expect(pourcentage(-0.44, 1)).toBe(`${SIGNE_MOINS}44,0${ESPACE_FINE}%`)
    expect(pourcentage(-0.087, 1)).toBe(`${SIGNE_MOINS}8,7${ESPACE_FINE}%`)
  })
})

describe('compte — accord et espace insécable', () => {
  it('lie le nombre au mot par une espace INSÉCABLE', () => {
    expect(seances(504)).toBe(`504${ESPACE_INSECABLE}séances`)
    expect(lignes(6)).toBe(`6${ESPACE_INSECABLE}lignes`)
  })

  it('groupe les grands nombres comptés', () => {
    expect(compte(100000, 'tirage')).toBe(
      `100${ESPACE_FINE}000${ESPACE_INSECABLE}tirages`,
    )
  })

  it('met le singulier à zéro et à un, comme en français', () => {
    // Même règle que backend.typography.counted : pluriel au-delà de deux exclu.
    expect(seances(0)).toBe(`0${ESPACE_INSECABLE}séance`)
    expect(seances(1)).toBe(`1${ESPACE_INSECABLE}séance`)
    expect(seances(2)).toBe(`2${ESPACE_INSECABLE}séances`)
  })

  it('accepte un pluriel irrégulier', () => {
    expect(compte(3, 'œil', 'yeux')).toBe(`3${ESPACE_INSECABLE}yeux`)
  })
})

describe('valeur de portefeuille', () => {
  it("écrit le nombre seul, sans devise — le code ISO publié s'ajoute par montant()", () => {
    const ecrit = valeurDePortefeuille(83185.85)
    expect(ecrit).toBe(`83${ESPACE_FINE}185,85`)
    expect(ecrit).not.toContain('$')
    expect(ecrit).not.toContain('€')
  })
})

describe('dates', () => {
  it('laisse la date de provenance telle que l’API l’écrit', () => {
    expect(dateISO('2026-09-09')).toBe('2026-09-09')
  })

  it('écrit une largeur en points en adjectif anglais, le tiret lié (7D)', () => {
    expect(pointsEnAdjectif(0.0025, 2)).toBe('0.25-\u2060point')
    expect(pointsEnAdjectif(0.01, 0)).toBe('1-\u2060point')
  })

  it('lie la date ISO d’une phrase anglaise après ses tirets (7D), sans rien changer d’autre', () => {
    expect(dateISOLiee('2026-09-16')).toBe('2026-\u206009-\u206016')
    expect(dateISOLiee('2026-09-16').split(LIAISON).join('')).toBe(dateISO('2026-09-16'))
  })

  it('écrit la prose sans décaler la date d’un fuseau', () => {
    // `new Date('2026-09-09')` est interprété en UTC : affiché en heure locale à
    // l'ouest de Greenwich, il recule au 8 septembre. Le découpage est textuel.
    expect(dateEnToutesLettres('2026-09-09')).toBe(
      `9${ESPACE_INSECABLE}septembre${ESPACE_INSECABLE}2026`,
    )
    expect(dateEnToutesLettres('2007-10-09')).toBe(
      `9${ESPACE_INSECABLE}octobre${ESPACE_INSECABLE}2007`,
    )
    expect(dateEnToutesLettres('2020-01-01')).toBe(
      `1er${ESPACE_INSECABLE}janvier${ESPACE_INSECABLE}2020`,
    )
  })

  it('rend la chaîne telle quelle si elle n’a pas la forme attendue', () => {
    expect(dateEnToutesLettres('jamais')).toBe('jamais')
    expect(dateEnToutesLettres('2026-13-01')).toBe('2026-13-01')
  })
})

describe('une mesure indéfinie ne devient jamais un zéro', () => {
  it('rend le tiret d’indéfini sur null et undefined', () => {
    expect(pourcentageOuTiret(null, 2)).toBe(TIRET_INDEFINI)
    expect(pourcentageOuTiret(undefined, 2)).toBe(TIRET_INDEFINI)
    expect(decimalOuTiret(null, 2)).toBe(TIRET_INDEFINI)
  })

  it('ne rend ni « 0 », ni « ∞ », ni « NaN »', () => {
    // §9.1 règle 3, et la raison écrite dans le backend : deux annulations
    // catastrophiques y ont déjà produit des ratios absurdes. Rendre l'absurde
    // plausible par l'affichage réintroduirait le problème.
    const ecrit = pourcentageOuTiret(null, 2)
    expect(ecrit).not.toContain('0')
    expect(ecrit).not.toContain('∞')
    expect(ecrit).not.toContain('NaN')
  })

  it('distingue un zéro RÉEL du tiret', () => {
    // Un zéro mesuré s'affiche : c'est un résultat, pas une absence.
    expect(pourcentageOuTiret(0, 2)).toBe(`0,00${ESPACE_FINE}%`)
  })
})

describe('convention de signe des pertes (§9.1, règle 2)', () => {
  it('affiche une VaR telle quelle, sans ajouter de signe', () => {
    // 0.0138 se lit « perte d'au moins 1,38 % ». Le nombre part positif du
    // moteur et reste positif ici : ajouter « − » le ferait lire comme un gain.
    expect(pourcentage(0.0138, 2)).toBe(`1,38${ESPACE_FINE}%`)
    expect(pourcentage(0.0138, 2).startsWith(SIGNE_MOINS)).toBe(false)
  })

  it('signale qu’une perte négative est un gain, sans toucher au nombre', () => {
    expect(estUnGain(-0.0021)).toBe(true)
    expect(estUnGain(0.0138)).toBe(false)
    expect(estUnGain(0)).toBe(false)
    // Le nombre, lui, s'écrit tel qu'il est — c'est la phrase qui change.
    expect(pourcentage(-0.0021, 2)).toBe(`${SIGNE_MOINS}0,21${ESPACE_FINE}%`)
  })
})

describe('montant et devise', () => {
  it('écrit le code ISO publié, jamais un symbole : « 83 185,85 USD »', () => {
    const ecrit = montant(83185.85, 'USD')
    expect(ecrit).toBe(`83${ESPACE_FINE}185,85${ESPACE_INSECABLE}USD`)
    expect(ecrit).not.toContain('$')
  })

  it('refuse un symbole plutôt que de l’afficher', () => {
    // À Montréal, « $ » se lit dollar canadien : un montant américain écrit
    // « 83 185,85 $ » y serait faux de 30 %.
    expect(() => montant(83185.85, '$')).toThrow()
    expect(() => montant(83185.85, 'US$')).toThrow()
    expect(() => montant(83185.85, 'usd')).toThrow()
  })

  it('lie le nombre à sa devise par une espace insécable', () => {
    expect(montant(1000, 'USD')).not.toContain('\u0020')
  })
})

describe('décimales d’une colonne (§9.3)', () => {
  it('écrit des entiers sans décimale', () => {
    expect(decimalesDeColonne([40, 25, 120], 4)).toBe(0)
  })

  it('donne à toute la colonne les décimales de la plus précise', () => {
    expect(decimalesDeColonne([40, 0.5, 120], 4)).toBe(1)
    expect(decimalesDeColonne([40, 0.25], 4)).toBe(2)
  })

  it('plafonne', () => {
    expect(decimalesDeColonne([1 / 3], 4)).toBe(4)
  })
})

describe('points de pourcentage', () => {
  it('écrit une largeur en points, accordée au nombre affiché', () => {
    expect(points(0.0025, 2)).toBe(`0,25${ESPACE_INSECABLE}point`)
    expect(points(0.098, 1)).toBe(`9,8${ESPACE_INSECABLE}points`)
    expect(points(0.0196, 1)).toBe(`2,0${ESPACE_INSECABLE}points`)
  })

  it('écrit un écart signé comme le backend : « +9,8 pts », « −8,1 pts »', () => {
    expect(pointsSignes(0.098, 1)).toBe(`+9,8${ESPACE_INSECABLE}pts`)
    expect(pointsSignes(-0.081, 1)).toBe(`${SIGNE_MOINS}8,1${ESPACE_INSECABLE}pts`)
    expect(pointsSignes(0.0004, 1)).toBe(`0,0${ESPACE_INSECABLE}pts`)
  })

  it('écrit le même écart en toutes lettres, pour une étiquette lue à voix haute (7E)', () => {
    expect(pointsSignesEnToutesLettres(0.098, 1)).toBe(`+9,8${ESPACE_INSECABLE}points`)
    expect(pointsSignesEnToutesLettres(-0.081, 1)).toBe(`${SIGNE_MOINS}8,1${ESPACE_INSECABLE}points`)
    expect(pointsSignesEnToutesLettres(0.019, 1)).toBe(`+1,9${ESPACE_INSECABLE}point`)
    expect(pointsSignesEnToutesLettres(0.0004, 1)).toBe(`0,0${ESPACE_INSECABLE}point`)
    expect(pointsSignesEnToutesLettres(0.098, 1, 'en')).toBe(`+9.8${ESPACE_INSECABLE}points`)
    expect(pointsSignesEnToutesLettres(-0.019, 1, 'en')).toBe(`${SIGNE_MOINS}1.9${ESPACE_INSECABLE}points`)
  })
})

describe('dates d’un axe de temps', () => {
  it('positionne à minuit UTC et écrit le mois en composantes UTC', () => {
    // Quel que soit le fuseau de la machine qui exécute le test : la date lue
    // est celle qui a été reçue, pas la veille.
    const date = dateDepuisISO('2025-03-01')
    expect(date.toISOString()).toBe('2025-03-01T00:00:00.000Z')
    expect(moisISO(date)).toBe('2025-03')
  })
})

describe('rendement signé', () => {
  it('écrit le « + » d’un gain et le vrai signe moins d’une perte', () => {
    expect(pourcentageSigne(0.597, 1)).toBe(`+59,7${ESPACE_FINE}%`)
    expect(pourcentageSigne(-0.44, 1)).toBe(`${SIGNE_MOINS}44,0${ESPACE_FINE}%`)
    expect(pourcentageSigne(0.0001, 1)).toBe(`0,0${ESPACE_FINE}%`)
  })
})

describe('les formats des phrases de lecture : l’ampleur, le sens porté par le verbe', () => {
  it('un montant arrondi à la dizaine, sans signe, avec sa devise', () => {
    expect(montantArrondi(892.4152, 'USD')).toBe(`890${ESPACE_INSECABLE}USD`)
    expect(montantArrondi(-12483.03, 'USD')).toBe(`12${ESPACE_FINE}480${ESPACE_INSECABLE}USD`)
    expect(montantArrondi(895, 'USD')).toBe(`900${ESPACE_INSECABLE}USD`)
    expect(() => montantArrondi(890, '$')).toThrow()
  })

  it('l’ampleur d’un pourcentage et d’un écart en points, sans signe', () => {
    expect(pourcentageAbsolu(-0.4397, 1)).toBe(`44,0${ESPACE_FINE}%`)
    expect(pourcentageAbsolu(0.597, 1)).toBe(`59,7${ESPACE_FINE}%`)
    expect(pointsAbsolus(-0.0727, 1)).toBe(`7,3${ESPACE_INSECABLE}points`)
    expect(pointsAbsolus(0.013, 1)).toBe(`1,3${ESPACE_INSECABLE}point`)
  })
})

describe('les cas partagés avec backend/typography.py, dans les deux langues (7D)', () => {
  // Une seule table, lue aussi par tests/test_typographie_partagee.py : chaque
  // moitié du produit doit écrire, pour chaque cas, exactement la même chaîne.
  const table = JSON.parse(
    readFileSync(join(import.meta.dirname, 'typographie-partagee.json'), 'utf-8'),
  ) as { cas: { fonction: string; arguments: (number | string)[]; fr: string; en: string }[] }

  type Ecriture = (langue: Langue, args: readonly (number | string)[]) => string
  const ECRITURES: Record<string, Ecriture> = {
    nombre: (langue, [valeur, decimales]) => decimal(Number(valeur), Number(decimales), langue),
    pourcentage: (langue, [fraction, decimales]) =>
      pourcentage(Number(fraction), Number(decimales), langue),
    'pourcentage signé': (langue, [fraction, decimales]) =>
      pourcentageSigne(Number(fraction), Number(decimales), langue),
    'écart signé': (langue, [ecart, decimales]) =>
      pointsSignes(Number(ecart), Number(decimales), langue),
    séances: (langue, [nombre]) => seances(Number(nombre), langue),
    lignes: (langue, [nombre]) => lignes(Number(nombre), langue),
    'date longue': (langue, [iso]) => dateEnToutesLettres(String(iso), langue),
  }

  it('couvre chaque écriture', () => {
    expect(new Set(table.cas.map((cas) => cas.fonction))).toEqual(new Set(Object.keys(ECRITURES)))
  })

  for (const langue of ['fr', 'en'] as const) {
    it(`écrit chaque cas comme le backend, en ${langue}`, () => {
      for (const cas of table.cas) {
        const ecrire = ECRITURES[cas.fonction]
        expect(ecrire, cas.fonction).toBeDefined()
        expect(ecrire?.(langue, cas.arguments), `${cas.fonction} ${JSON.stringify(cas.arguments)}`).toBe(
          cas[langue],
        )
      }
    })
  }
})

describe('l’écriture anglaise (7D)', () => {
  it('pose le point décimal et groupe les milliers à la virgule, au même seuil', () => {
    expect(decimal(83185.85, 2, 'en')).toBe('83,185.85')
    expect(decimal(504, 0, 'en')).toBe('504')
    expect(valeurDePortefeuille(83185.85, 'en')).toBe('83,185.85')
  })

  it('n’écrit aucune espace avant « % »', () => {
    expect(pourcentage(0.0138, 2, 'en')).toBe('1.38%')
    expect(pourcentageOuTiret(0, 2, 'en')).toBe('0.00%')
  })

  it('réserve le singulier au nombre qui s’écrit « 1 »', () => {
    expect(seances(0, 'en')).toBe(`0${ESPACE_INSECABLE}sessions`)
    expect(seances(1, 'en')).toBe(`1${ESPACE_INSECABLE}session`)
    expect(compte(3, 'day', undefined, 'en')).toBe(`3${ESPACE_INSECABLE}days`)
    expect(compte(100000, 'draw', undefined, 'en')).toBe(`100,000${ESPACE_INSECABLE}draws`)
    expect(points(0.0025, 2, 'en')).toBe(`0.25${ESPACE_INSECABLE}points`)
    expect(points(0.01, 0, 'en')).toBe(`1${ESPACE_INSECABLE}point`)
    expect(points(0.0196, 1, 'en')).toBe(`2.0${ESPACE_INSECABLE}points`)
    expect(pointsAbsolus(-0.013, 1, 'en')).toBe(`1.3${ESPACE_INSECABLE}points`)
  })

  it('écrit un montant avec son code ISO', () => {
    expect(montant(83185.85, 'USD', 'en')).toBe(`83,185.85${ESPACE_INSECABLE}USD`)
    expect(montantArrondi(-12483.03, 'USD', 'en')).toBe(`12,480${ESPACE_INSECABLE}USD`)
    expect(() => montant(1, '$', 'en')).toThrow()
  })

  it('écrit « April 4, 2025 », lié après le mois et après la virgule', () => {
    expect(dateEnToutesLettres('2025-04-04', 'en')).toBe(
      `April${ESPACE_INSECABLE}4,${ESPACE_INSECABLE}2025`,
    )
    expect(dateEnToutesLettres('2026-13-01', 'en')).toBe('2026-13-01')
  })

  it('garde le tiret d’indéfini et le vrai signe moins', () => {
    expect(pourcentageOuTiret(null, 2, 'en')).toBe(TIRET_INDEFINI)
    expect(decimalOuTiret(4.071, 2, 'en')).toBe('4.07')
    expect(pourcentageSigne(-0.44, 1, 'en')).toBe(`${SIGNE_MOINS}44.0%`)
    expect(pourcentageAbsolu(-0.4397, 1, 'en')).toBe('44.0%')
    expect(pointsSignes(-0.081, 1, 'en')).toBe(`${SIGNE_MOINS}8.1${ESPACE_INSECABLE}pts`)
  })

  it('n’écrit aucune espace ordinaire', () => {
    for (const texte of [
      pourcentage(0.0138, 2, 'en'),
      seances(504, 'en'),
      montant(83185.85, 'USD', 'en'),
      dateEnToutesLettres('2026-09-09', 'en'),
    ]) {
      expect(texte).not.toContain('\u0020')
    }
  })
})
