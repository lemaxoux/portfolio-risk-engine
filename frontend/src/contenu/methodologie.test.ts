/**
 * Le texte de la page méthodologie, dans chaque langue : il se lit, ses ancres
 * sont celles que viseront les liens, chaque formule suit la phrase qui la
 * dit, et chaque caractère est dessiné par sa police.
 *
 * Sa typographie, ses mots et chaque nombre qu'il cite sont vérifiés côté
 * Python, par `tests/test_methodologie.py`, avec les gardes des textes publiés
 * et contre le moteur.
 */
import { describe, expect, it } from 'vitest'

import { lireContenu, type Bloc, type EnLigne } from '../lib/contenu'
import type { Langue } from '../lib/langue'
import { LIBELLES } from './libelles'
import { METHODOLOGIE } from './methodologie'

/** Le titre de la page, dans chaque langue. */
const TITRES: Readonly<Record<Langue, string>> = { fr: 'Méthodologie', en: 'Methodology' }

/**
 * Les ancres, dans l'ordre : les parties (`##`), puis les entrées (`###`) de
 * chacune. Elles sont un CONTRAT : le lien d'une mesure vers sa méthode les
 * visera (`/methodologie#cvar`), et elles sont les mêmes dans toutes les
 * langues. Les parties qui reprennent une section de l'analyse en reprennent
 * l'ancre.
 */
const ANCRES = [
  'principes',
  'donnees',
  'conventions',
  'portefeuille',
  'valeur-et-poids',
  'jour-ordinaire',
  'var-historique',
  'histogramme',
  'var-parametrique',
  'volatilite',
  'cvar',
  'au-pire',
  'perte-maximale',
  'courbe-de-valeur',
  'qui-porte',
  'lignes-effectives',
  'part-des-variations',
  'correlation',
  'en-crise',
  'rejeu',
  'trois-chiffres',
  'couverture',
  'sensibilite',
  'attendu',
  'moteur',
  'constats',
  'seuils-choisis',
  'seuils-demontres',
  'references',
  'refus',
]

const PARTIES = [
  'principes',
  'donnees',
  'conventions',
  'portefeuille',
  'jour-ordinaire',
  'au-pire',
  'qui-porte',
  'en-crise',
  'moteur',
]

// ════════════════════════════════════════════════════════════ Glyphes ══

/*
 * Les caractères que la page peut employer, ÉTABLIS LE 2026-10-07 en lisant
 * les tables `cmap` des fichiers `.woff` de @fontsource, aux versions figées
 * de package.json : Spectral 400 et 500 pour la prose (titres et étiquettes
 * compris), IBM Plex Sans 400 pour les formules. Le dépôt n'a pas de lecteur
 * de polices : un caractère hors de ces listes fait échouer le test, et l'on
 * vérifie la police à la main avant de l'ajouter (README, « La page
 * méthodologie »).
 *
 * Deux signes ne sont dessinés par AUCUNE police du produit : √ et ≥. Ils
 * viennent de la police de repli, comme le √ et le → des provenances
 * (DESIGN.md §6.3), et seulement dans une formule.
 */
const LETTRES = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
const CHIFFRES = '0123456789'
const ESPACE = ' '
const ESPACE_INSECABLE = String.fromCharCode(0x00a0)
/** Absente de Spectral : dessinée par `espace-fine.ttf`, déclarée dans sa famille. */
const ESPACE_FINE = String.fromCharCode(0x202f)

const PROSE = new Set([
  ...LETTRES,
  ...CHIFFRES,
  ESPACE,
  ESPACE_INSECABLE,
  ESPACE_FINE,
  ...".,;:!?()-+=%&/'",
  ...'àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ',
  ...'«»’−×·±²³°…',
])

const FORMULES = new Set([
  ...LETTRES,
  ...CHIFFRES,
  ESPACE,
  ...'(),./=+−×·…²±′éè',
  ...'αβγδεθλμνπρσφωΣΔ',
])

/*
 * L'anglais (chantier 7D) : ni lettre accentuée, ni « », ni espace fine, ni
 * « é » dans une formule ; ses guillemets “ ” et l'apostrophe ’, LUS LE
 * 2026-10-08 dans la table `cmap` de Spectral 400 et 500 (sous-ensemble
 * latin), et dans celle d'IBM Plex Sans 400, aux mêmes versions. Un caractère
 * français oublié dans le texte anglais fait donc échouer le test.
 */
const PROSE_EN = new Set([
  ...LETTRES,
  ...CHIFFRES,
  ESPACE,
  ESPACE_INSECABLE,
  ...".,;:!?()-+=%&/'",
  ...'“”’−×·±²³°…',
])

const FORMULES_EN = new Set([
  ...LETTRES,
  ...CHIFFRES,
  ESPACE,
  ...'(),./=+−×·…²±′',
  ...'αβγδεθλμνπρσφωΣΔ',
])

const PROSE_PAR_LANGUE: Readonly<Record<Langue, ReadonlySet<string>>> = { fr: PROSE, en: PROSE_EN }
const FORMULES_PAR_LANGUE: Readonly<Record<Langue, ReadonlySet<string>>> = {
  fr: FORMULES,
  en: FORMULES_EN,
}

const REPLI = new Set(['√', '≥'])

function pointDeCode(caractere: string): string {
  return `U+${(caractere.codePointAt(0) ?? 0).toString(16).toUpperCase().padStart(4, '0')}`
}

/** Les caractères de la prose et ceux des formules, séparés. */
function caracteres(blocs: readonly Bloc[]): { prose: Set<string>; formules: Set<string> } {
  const prose = new Set<string>()
  const formules = new Set<string>()
  const parcourir = (contenu: readonly EnLigne[]) => {
    for (const element of contenu) {
      if (element.type === 'texte') for (const c of element.texte) prose.add(c)
      else if (element.type === 'formule') {
        for (const morceau of element.morceaux) for (const c of morceau.texte) formules.add(c)
      } else parcourir(element.contenu)
    }
  }
  for (const bloc of blocs) {
    if (bloc.type === 'titre') parcourir(bloc.contenu)
    else if (bloc.type === 'formule') {
      for (const morceau of bloc.morceaux) for (const c of morceau.texte) formules.add(c)
    } else {
      const corps = bloc.type === 'liste' ? bloc.elements : [bloc]
      for (const element of corps) {
        for (const c of element.etiquette ?? '') prose.add(c)
        parcourir(element.contenu)
      }
    }
  }
  return { prose, formules }
}

for (const [langue, source] of Object.entries(METHODOLOGIE) as [Langue, string][]) {
  describe(`la méthodologie (${langue})`, () => {
    const contenu = lireContenu(source)

    it('se lit sans erreur, son titre en tête', () => {
      expect(contenu.titre).toBe(TITRES[langue])
    })

    it('a les ancres déclarées, dans l’ordre, et les parties que liste le rail', () => {
      expect(contenu.ancres).toEqual(ANCRES)
      expect(contenu.parties.map((p) => p.ancre)).toEqual(PARTIES)
    })

    it('ne lie qu’à ses propres ancres', () => {
      const cibles: string[] = []
      const parcourir = (elements: readonly EnLigne[]) => {
        for (const e of elements) if (e.type === 'lien') cibles.push(e.cible)
      }
      for (const bloc of contenu.blocs) {
        if (bloc.type === 'paragraphe') parcourir(bloc.contenu)
        if (bloc.type === 'liste') bloc.elements.forEach((e) => parcourir(e.contenu))
      }
      expect(cibles.length).toBeGreaterThan(0)
      expect(cibles.filter((c) => !ANCRES.includes(c))).toEqual([])
    })

    it('n’ouvre jamais une partie ni une entrée par une formule : elle suit la phrase qui la dit', () => {
      contenu.blocs.forEach((bloc, rang) => {
        if (bloc.type !== 'formule') return
        let avant = rang - 1
        while (contenu.blocs[avant]?.type === 'formule') avant -= 1
        expect(contenu.blocs[avant]?.type, `formule de la ligne ${bloc.ligne}`).not.toBe('titre')
      })
    })

    it('n’écrit dans la prose que des caractères que Spectral dessine', () => {
      const { prose } = caracteres(contenu.blocs)
      const admis = PROSE_PAR_LANGUE[langue]
      expect([...prose].filter((c) => !admis.has(c)).map(pointDeCode)).toEqual([])
    })

    it('n’écrit dans les formules que des caractères que Plex Sans dessine, √ et ≥ par la police de repli', () => {
      const { formules } = caracteres(contenu.blocs)
      const admis = FORMULES_PAR_LANGUE[langue]
      expect([...formules].filter((c) => !admis.has(c) && !REPLI.has(c)).map(pointDeCode)).toEqual(
        [],
      )
    })
  })
}

// ════════════════════════════════════════════ Deux langues, un texte ══

/**
 * La forme d'un bloc, sans ses mots : son type, son ancre, son étiquette
 * éventuelle, le nombre de ses formules en ligne et les ancres qu'il vise.
 * Une formule en bloc compte par sa seule présence : ses mots se traduisent
 * (« perte maximale », « maximum drawdown »).
 */
function forme(bloc: Bloc): string {
  const enLigne = (contenu: readonly EnLigne[]): string => {
    const formules = contenu.filter((e) => e.type === 'formule').length
    const liens = contenu.flatMap((e) => (e.type === 'lien' ? [e.cible] : []))
    return `${formules} formule(s)${liens.length > 0 ? ` vers #${liens.join(', #')}` : ''}`
  }
  switch (bloc.type) {
    case 'titre':
      return `titre ${bloc.niveau} #${bloc.ancre ?? ''}`
    case 'formule':
      return 'formule en bloc'
    case 'paragraphe':
      return `paragraphe${bloc.etiquette !== null ? ' étiqueté' : ''}, ${enLigne(bloc.contenu)}`
    case 'liste':
      return `liste : ${bloc.elements
        .map((e) => `${e.etiquette !== null ? 'étiqueté, ' : ''}${enLigne(e.contenu)}`)
        .join(' ; ')}`
  }
}

describe('les deux langues', () => {
  const francais = lireContenu(METHODOLOGIE.fr)
  const anglais = lireContenu(METHODOLOGIE.en)

  it('ont la même forme, bloc par bloc : un même texte, traduit', () => {
    expect(anglais.blocs.map(forme)).toEqual(francais.blocs.map(forme))
  })

  it('nomment les six parties reprises de l’analyse comme le rail de l’analyse', () => {
    // Après les trois parties propres à la page (principes, données,
    // conventions), chaque partie reprend une section de l'analyse, son
    // ancre et son nom court : « Au pire », « At worst ».
    for (const [langue, contenu] of [
      ['fr', francais],
      ['en', anglais],
    ] as const) {
      expect(contenu.parties.slice(3).map((p) => p.titre)).toEqual(
        LIBELLES[langue].navigation.sections,
      )
    }
  })
})

describe('la garde des glyphes', () => {
  it('voit un caractère hors liste, dans la prose comme dans une formule', () => {
    const fautif = lireContenu('# Méthodologie\n\nUn signe → ici, et $x ≤ y$.')
    const { prose, formules } = caracteres(fautif.blocs)
    expect([...prose].filter((c) => !PROSE.has(c))).toEqual(['→'])
    expect([...formules].filter((c) => !FORMULES.has(c) && !REPLI.has(c))).toEqual(['≤'])
  })

  it('n’admet √ et ≥ que dans une formule', () => {
    const fautif = lireContenu('# Méthodologie\n\nLa racine √ dans la prose.')
    expect([...caracteres(fautif.blocs).prose].filter((c) => !PROSE.has(c))).toEqual(['√'])
  })
})
