/**
 * La page de présentation de la démonstration — DESIGN.md §19 (chantier 9.4).
 *
 * AUCUN NOMBRE DANS LA PROSE (§19.3). La page dit « des crises passées », pas
 * leur nombre, et « trop peu nombreux », pas un seuil : tout nombre affiché
 * est lu dans un fichier exporté ou dans `contenu/demo.ts`, et écrit par
 * `format.ts`. La garde lit les libellés de la page et de la page de
 * l'avertissement, dans les deux langues, et refuse un chiffre ou un nombre
 * écrit en lettres. Ce qu'un libellé à paramètres reçoit de `format.ts` est
 * retiré avant le contrôle : c'est un nombre affiché, pas un nombre écrit.
 *
 * « Un », « une » et « one » ne sont pas des nombres ici : ce sont aussi des
 * articles, comme dans la garde du serveur (`tests/gardes_texte.py`).
 * « Premier » et « first » ne disent aucun compte. Une seule locution est
 * admise, entière : « part de zéro », « starts from zero ».
 *
 * Le rendu se vérifie dans un navigateur ; ici, les textes et les adresses.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import { dateEnToutesLettres, ESPACE_INSECABLE } from '../lib/format'
import type { Langue } from '../lib/langue'
import { DATE_DE_LA_DEMO } from './demo'
import { LIBELLES, type Libelles } from './libelles'
import { ADRESSES, NOMS } from './liens'

const LANGUES = ['fr', 'en'] as const

// ═══════════════════════════════════════════ Aucun nombre dans la prose ══

/** Un mot entier : ni lettre avant, ni lettre après. Sans échappement. */
const mot = (mots: string) => new RegExp(`(?<![a-zà-ÿ])(${mots})(?![a-zà-ÿ])`, 'i')

const CHIFFRE = /[0-9]/

const EN_LETTRES: Record<Langue, RegExp> = {
  fr: mot(
    'zéro|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|' +
      'vingt|trente|quarante|cinquante|soixante|cent|cents|mille|millions?|milliards?|' +
      'deuxième|seconde?|troisième|quatrième|cinquième|sixième|dixième|' +
      'double|triple|dizaine|douzaine|centaine',
  ),
  en: mot(
    'zero|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|' +
      'sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|' +
      'hundred|thousand|millions?|billions?|second|third|fourth|fifth|sixth|tenth|' +
      'both|twice|double|triple|dozen|couple',
  ),
}

/** La seule locution admise, entière : elle ne compte rien. */
const LOCUTION: Record<Langue, string> = { fr: 'part de zéro', en: 'starts from zero' }

function nombres(texte: string, langue: Langue): string[] {
  const reste = texte.replaceAll(LOCUTION[langue], '')
  const trouves: string[] = []
  if (CHIFFRE.test(reste)) trouves.push('un chiffre')
  const enLettres = EN_LETTRES[langue].exec(reste)
  if (enLettres !== null) trouves.push(`« ${enLettres[0]} »`)
  return trouves
}

/** Les chaînes et les fonctions d'un groupe de libellés, par chemin. */
function feuilles(objet: unknown, chemin: string): Map<string, unknown> {
  if (typeof objet === 'string' || typeof objet === 'function') return new Map([[chemin, objet]])
  const trouvees = new Map<string, unknown>()
  if (typeof objet === 'object' && objet !== null) {
    for (const [cle, valeur] of Object.entries(objet)) {
      for (const [c, v] of feuilles(valeur, `${chemin}.${cle}`)) trouvees.set(c, v)
    }
  }
  return trouvees
}

/**
 * Chaque libellé à paramètres de la page, appelé comme la page l'appelle,
 * avec ce que `format.ts` y écrit : retiré avant le contrôle.
 */
function appels(l: Libelles, langue: Langue): Record<string, { texte: string; ecrit: string[] }> {
  const date = dateEnToutesLettres(DATE_DE_LA_DEMO, langue)
  return {
    'presentation.tableau.legende': {
      texte: l.presentation.tableau.legende(DATE_DE_LA_DEMO),
      ecrit: [date],
    },
    // Le nom de la crise et celui du portefeuille viennent de l'export.
    'presentation.resultat.titreDuBloc': {
      texte: l.presentation.resultat.titreDuBloc('Krach', 'Démo'),
      ecrit: [],
    },
  }
}

/** La prose de la page, dans une langue : chaque chaîne, puis chaque fonction sur son cas. */
function prose(langue: Langue): Map<string, string> {
  const l = LIBELLES[langue]
  const textes = new Map<string, string>()
  const cas = appels(l, langue)
  const groupes = { presentation: l.presentation, avertissement: l.avertissement }
  for (const [nom, groupe] of Object.entries(groupes)) {
    for (const [chemin, valeur] of feuilles(groupe, nom)) {
      if (typeof valeur === 'string') {
        textes.set(chemin, valeur)
        continue
      }
      const appel = cas[chemin]
      if (appel === undefined) throw new Error(`libellé à paramètres sans cas : ${chemin}`)
      textes.set(
        chemin,
        appel.ecrit.reduce((reste, ecrit) => reste.replaceAll(ecrit, ''), appel.texte),
      )
    }
  }
  return textes
}

describe('aucun nombre dans la prose de la page', () => {
  it('ni en chiffres ni en lettres, dans les deux langues', () => {
    for (const langue of LANGUES) {
      const fautes = [...prose(langue)].flatMap(([chemin, texte]) =>
        nombres(texte, langue).map((nombre) => `${langue} ${chemin} : ${nombre}`),
      )
      expect(fautes).toEqual([])
    }
  })

  it('la garde lit toute la page : ses titres, sa prose, ses liens, la ligne de l’auteur', () => {
    for (const langue of LANGUES) {
      const chemins = [...prose(langue).keys()]
      expect(chemins.length).toBeGreaterThan(25)
      for (const attendu of [
        'presentation.titre',
        'presentation.chapeau',
        'presentation.tableau.legende',
        'presentation.distingue.refus.texte',
        'presentation.resultat.titreDuBloc',
        'presentation.construit.texte',
        'presentation.liens.methodologieTechnique',
        'presentation.auteur',
        'avertissement.pourquoi',
      ]) {
        expect(chemins, attendu).toContain(attendu)
      }
    }
  })

  it('un texte fautif la fait échouer', () => {
    expect(nombres('L’analyse rejoue trois crises passées.', 'fr')).toEqual(['« trois »'])
    expect(nombres('Sous 30 jours de bourse, le chiffre est signalé.', 'fr')).toEqual(['un chiffre'])
    expect(nombres('Les deux lignes les plus liées.', 'fr')).toEqual(['« deux »'])
    expect(nombres('Le troisième portefeuille.', 'fr')).toEqual(['« troisième »'])
    expect(nombres('Zéro crise rejouée.', 'fr')).toEqual(['« Zéro »'])
    expect(nombres('The analysis replays three past crises.', 'en')).toEqual(['« three »'])
    expect(nombres('Below 30 trading days, the figure is flagged.', 'en')).toEqual(['un chiffre'])
    expect(nombres('Both holdings move together.', 'en')).toEqual(['« Both »'])
    expect(nombres('The second portfolio.', 'en')).toEqual(['« second »'])
    expect(nombres('From zero to a hundred.', 'en')).toEqual(['« zero »'])
  })

  it('laisse passer les articles, le premier, et la seule locution admise', () => {
    expect(nombres('Un chiffre et ses conditions, pour une estimation.', 'fr')).toEqual([])
    expect(nombres('Le premier portefeuille, la première crise.', 'fr')).toEqual([])
    expect(nombres('Pour un lecteur qui part de zéro.', 'fr')).toEqual([])
    expect(nombres('No one, and the first crisis it replays.', 'en')).toEqual([])
    expect(nombres('For a reader who starts from zero.', 'en')).toEqual([])
    // Le mot de la locution, hors d'elle, échoue toujours.
    expect(nombres('Un lecteur qui part de zéro, avec zéro ligne.', 'fr')).toEqual(['« zéro »'])
  })

  it('la date de la légende vient du formateur, pas du libellé', () => {
    for (const langue of LANGUES) {
      const legende = LIBELLES[langue].presentation.tableau.legende(DATE_DE_LA_DEMO)
      expect(legende).toContain(dateEnToutesLettres(DATE_DE_LA_DEMO, langue))
      expect(nombres(legende, langue)).toEqual(['un chiffre'])
    }
  })
})

// ════════════════════════════════════════════ Ce que la page affirme ══

describe('ce que la page dit', () => {
  it('l’outil décrit, il ne dit jamais quoi faire : la phrase fixée, dans les deux langues', () => {
    expect(LIBELLES.fr.presentation.distingue.note.texte.endsWith(
      `L'outil décrit${ESPACE_INSECABLE}: il ne dit jamais quoi faire.`,
    )).toBe(true)
    expect(LIBELLES.en.presentation.distingue.note.texte.endsWith(
      'The tool describes: it never says what to do.',
    )).toBe(true)
  })

  it('tout y décrit le passé : le chapeau se termine ainsi', () => {
    expect(LIBELLES.fr.presentation.chapeau.endsWith(
      `Tout y décrit le passé${ESPACE_INSECABLE}: rien n'y est une prévision.`,
    )).toBe(true)
    expect(LIBELLES.en.presentation.chapeau.endsWith(
      'Everything in it describes the past: nothing in it is a forecast.',
    )).toBe(true)
  })

  it('distingue le refus du signalement, comme le moteur', () => {
    const fr = LIBELLES.fr.presentation.distingue.refus.texte
    expect(fr).toContain("l'outil la refuse et dit pourquoi")
    expect(fr).toContain('il la donne, et la signale')
    const en = LIBELLES.en.presentation.distingue.refus.texte
    expect(en).toContain('the tool refuses it and says why')
    expect(en).toContain('it gives it, and flags it')
  })

  it('l’école garde son nom dans les deux langues', () => {
    for (const langue of LANGUES) {
      expect(LIBELLES[langue].presentation.auteur).toContain('Maxence Champlong')
      expect(LIBELLES[langue].presentation.auteur).toContain('HEC Montréal')
    }
  })
})

// ══════════════════════════════════════════ « How it was built », du README ══

const README = readFileSync(join(import.meta.dirname, '..', '..', '..', 'README.md'), 'utf-8')

/** Les paragraphes d'une section du README, chacun sur une ligne. */
function sectionDuReadme(titre: string): string[] {
  const lignes = README.split('\n')
  const debut = lignes.indexOf(`## ${titre}`)
  if (debut < 0) throw new Error(`section absente du README : ${titre}`)
  const suite = lignes.slice(debut + 1)
  const fin = suite.findIndex((ligne) => ligne.startsWith('## '))
  return suite
    .slice(0, fin < 0 ? undefined : fin)
    .join('\n')
    .split('\n\n')
    .map((paragraphe) => paragraphe.split('\n').join(' ').trim())
    .filter((paragraphe) => paragraphe !== '')
}

describe('« How it was built »', () => {
  it('est la section du README, mot pour mot, titre compris', () => {
    const l = LIBELLES.en.presentation.construit
    expect(sectionDuReadme(l.titre)).toEqual([l.texte])
  })

  it('le chapeau anglais commence par la première phrase du README', () => {
    const [premierParagraphe = ''] = README.split('\n\n').slice(1)
    const premierePhrase = `${premierParagraphe.split('\n').join(' ').split('. ')[0]}.`
    expect(premierePhrase).toBe(
      'Portfolio Risk Engine measures the risk of a portfolio of US-listed stocks and ETFs.',
    )
    expect(LIBELLES.en.presentation.chapeau.startsWith(premierePhrase)).toBe(true)
  })
})

// ════════════════════════════════════════════════ Les adresses des liens ══

describe('les adresses de la page', () => {
  it('sont celles du dépôt, de ses documents sur la branche principale, et de l’auteur', () => {
    expect(ADRESSES).toEqual({
      depot: 'https://github.com/lemaxoux/portfolio-risk-engine',
      installation: 'https://github.com/lemaxoux/portfolio-risk-engine/blob/main/README.md#getting-started',
      methodologieTechnique: 'https://github.com/lemaxoux/portfolio-risk-engine/blob/main/METHODOLOGY.md',
      architecture: 'https://github.com/lemaxoux/portfolio-risk-engine/blob/main/ARCHITECTURE.md',
      auteurSurGitHub: 'https://github.com/lemaxoux',
      auteurSurLinkedIn: 'https://www.linkedin.com/in/maxence-champlong-',
    })
  })

  it('le tiret final de l’adresse LinkedIn est gardé', () => {
    expect(ADRESSES.auteurSurLinkedIn.endsWith('-')).toBe(true)
  })

  it('le lien de l’auteur mène à son profil, celui de la liste au dépôt', () => {
    expect(ADRESSES.depot.startsWith(`${ADRESSES.auteurSurGitHub}/`)).toBe(true)
    expect(ADRESSES.auteurSurGitHub).not.toContain('portfolio-risk-engine')
  })

  it('la section visée du README existe, et ses documents aussi', () => {
    expect(README.split('\n')).toContain('## Getting started')
    for (const adresse of [ADRESSES.methodologieTechnique, ADRESSES.architecture]) {
      const fichier = adresse.split('/blob/main/')[1] ?? ''
      expect(() => readFileSync(join(import.meta.dirname, '..', '..', '..', fichier))).not.toThrow()
    }
  })

  it('aucune adresse électronique, nulle part : ni dans les adresses, ni dans les textes', () => {
    const tout = [
      ...Object.values(ADRESSES),
      ...Object.values(NOMS),
      ...LANGUES.flatMap((langue) => [...prose(langue).values()]),
    ]
    for (const texte of tout) {
      expect(texte, texte).not.toContain('@')
      expect(texte.toLowerCase(), texte).not.toContain('mailto')
    }
    for (const adresse of Object.values(ADRESSES)) expect(adresse.startsWith('https://')).toBe(true)
  })

  it('les noms propres ne sont pas des libellés : ils s’écrivent de même dans les deux langues', () => {
    expect(NOMS).toEqual({ gitHub: 'GitHub', linkedIn: 'LinkedIn' })
  })
})
