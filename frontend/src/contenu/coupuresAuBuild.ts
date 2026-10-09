/**
 * Les coupures de la méthodologie, posées au build — DESIGN.md §6.3,
 * décision du 2026-10-08 ; les règles sont dans `coupures.ts`.
 *
 * ═══ AU BUILD SEULEMENT ═══
 *
 * Le greffon Vite (`vite.config.ts`) charge à sa place chacun des deux
 * fichiers de méthodologie importés bruts (`?raw`) : le texte livré est la
 * source, coupures posées. Il ne sert qu'au build (`apply: 'build'`) : en
 * développement et dans les tests, le texte est celui de la source, et les
 * gardes de `tests/test_methodologie.py` et de `methodologie.test.ts` lisent
 * le fichier tel qu'il est écrit.
 *
 * Ce module n'est importé que par la configuration de Vite et par les tests :
 * les motifs (le paquet `hyphen`, dépendance de développement) n'entrent pas
 * dans le bundle (`coupures.test.ts` le vérifie).
 *
 * ═══ LES MOTIFS ═══
 *
 * Ceux de TeX (hyph-utf8), portés en JavaScript par `hyphen` : le français
 * (Daniel Flipo, Bernard Gaulle, Arthur Reutenauer, licence MIT) et
 * l'anglais américain (Gerard D.C. Kuiken). Crédits et notice : README,
 * section 10.
 */
import { readFileSync } from 'node:fs'

import creerCoupeur from 'hyphen'
import motifsEn from 'hyphen/patterns/en-us'
import motifsFr from 'hyphen/patterns/fr'
import type { Plugin } from 'vite'

import { COUPURE, EXCEPTIONS, poserCoupures, type LangueDesCoupures } from './coupures'

const MOTIFS: Readonly<Record<LangueDesCoupures, unknown>> = { fr: motifsFr, en: motifsEn }

/**
 * Coupe un mot selon les motifs de sa langue et la liste d'exceptions.
 *
 * Sur une COPIE des motifs : `hyphen` fusionne les exceptions qu'on lui donne
 * dans le dictionnaire d'exceptions des motifs eux-mêmes, si bien que tout
 * coupeur créé ensuite sur les mêmes motifs en hériterait. La liste
 * `EXCEPTIONS` reste ainsi la seule source des coupures données à la main.
 */
export function coupeur(langue: LangueDesCoupures): (mot: string) => string {
  return creerCoupeur(structuredClone(MOTIFS[langue]), {
    hyphenChar: COUPURE,
    exceptions: EXCEPTIONS[langue],
    html: false,
  })
}

/** Le texte livré d'un fichier de méthodologie : la source, coupures posées. */
export function texteLivre(source: string, langue: LangueDesCoupures): string {
  return poserCoupures(source, coupeur(langue))
}

/** Un import brut de l'un des deux fichiers de méthodologie, et sa langue. */
const FICHIER = /[/\\]contenu[/\\]methodologie\.(fr|en)\.md\?raw$/

/**
 * Le module que Vite reçoit pour un import brut d'un fichier de
 * méthodologie ; `null` pour tout autre, que Vite charge lui-même.
 */
export function chargerMethodologie(id: string): string | null {
  const fichier = FICHIER.exec(id)
  const langue = fichier?.[1]
  if (langue !== 'fr' && langue !== 'en') return null
  const source = readFileSync(id.slice(0, -'?raw'.length), 'utf-8')
  return `export default ${JSON.stringify(texteLivre(source, langue))}`
}

/** Le greffon : avant ceux de Vite, au build seulement. */
export function coupuresDeLaMethodologie(): Plugin {
  return {
    name: 'mx-risk-coupures-de-la-methodologie',
    apply: 'build',
    enforce: 'pre',
    load: chargerMethodologie,
  }
}
