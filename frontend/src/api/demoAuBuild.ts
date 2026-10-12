/**
 * Le build de démonstration (`npm run build:demo`, mode Vite `demo`) : ce qui
 * s'ajoute au bundle pour en faire un site statique, et ce qui le refuse.
 *
 * Le greffon `demonstration` ne sert qu'à ce build. Ni les données ni la
 * balise ne vont dans `dist/`, le build ordinaire, que FastAPI sert : rien
 * n'est posé dans `public/`, et `index.html` n'est pas modifié à la source.
 *
 * ═══ LES DONNÉES ═══
 *
 * `python -m tools.export_demo` écrit dans `demo/export/` les réponses de
 * l'API que lit la démonstration, et leur manifeste. Le greffon les relit,
 * les VÉRIFIE, puis les émet telles quelles sous `donnees/` :
 *
 * - chaque fichier a l'empreinte SHA-256 que dit le manifeste : un export
 *   retouché à la main, ou à moitié réécrit, arrête le build ;
 * - le manifeste liste exactement les fichiers que `client.ts` demandera,
 *   dans les deux langues, pour chaque portefeuille ;
 * - sa date et son nombre de portefeuilles sont ceux que la mention affiche
 *   (`contenu/demo.ts`).
 *
 * Sans export, le build échoue en donnant la commande. Le manifeste, lui,
 * n'est pas émis : rien dans le site ne le lit.
 *
 * ═══ PAS D'INDEXATION ═══
 *
 * `<meta name="robots" content="noindex">` dans `index.html`, et un fichier
 * `_headers` qui pose `X-Robots-Tag: noindex` sur toutes les adresses. C'est
 * le seul fichier propre à l'hébergeur. Pas de `404.html` : il casserait les
 * adresses du client, que l'hébergeur ne connaît pas (`/portefeuilles/1`).
 *
 * ═══ LA GARDE DU BUNDLE ═══
 *
 * La démonstration n'a aucun chemin d'écriture, et n'appelle aucune API. Ce
 * n'est pas laissé à la relecture : le build échoue si un de ses fichiers
 * JavaScript contient `/api`, ou le nom d'une méthode d'écriture entre
 * guillemets ou accents graves. Dans le build ordinaire, ces chaînes ne
 * viennent que de `client.ts`.
 *
 * ═══ LES IMAGES DE LA PRÉSENTATION, HORS DU BUILD ORDINAIRE ═══
 *
 * La page de présentation importe ses captures (`src/images/presentation/`).
 * Elle n'existe que dans la démonstration ; mais Vite émet un fichier importé
 * dès qu'il le lit, que la vue reste ou non dans le bundle. Un second
 * greffon, `sansLaDemonstration`, sert donc au build ordinaire, et à lui
 * seul : il retire ces images de `dist/`, et échoue si un fichier du build
 * en nomme une, car la page y serait alors entrée.
 */
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { join, sep } from 'node:path'

import type { Plugin } from 'vite'

import { DATE_DE_LA_DEMO, PORTEFEUILLES_DE_LA_DEMO } from '../contenu/demo'

/**
 * Les langues de l'export. Écrites ici plutôt qu'importées de `lib/langue` :
 * ce module est chargé par la configuration de Vite, et n'y fait pas entrer
 * le client. `demoAuBuild.test.ts` les tient égales à celles du site.
 */
export const LANGUES_DE_L_EXPORT = ['fr', 'en'] as const

/** La commande qui écrit l'export : citée par chaque refus. */
export const COMMANDE_D_EXPORT = 'python -m tools.export_demo'

export const MANIFESTE = 'manifeste.json'

/** Le dossier du site où `client.ts` demande les réponses enregistrées. */
export const DOSSIER_DES_DONNEES = 'donnees'

/** Le fichier d'en-têtes de l'hébergeur : pas d'indexation, sur toute adresse. */
export const EN_TETES = '/*\n  X-Robots-Tag: noindex\n'

/** La balise ajoutée à `index.html`. */
export const BALISE_ROBOTS = { name: 'robots', content: 'noindex' } as const

interface FichierDuManifeste {
  readonly chemin: string
  readonly octets: number
  readonly sha256: string
}

interface Manifeste {
  readonly date_gel: string
  readonly portefeuilles: readonly unknown[]
  readonly fichiers: readonly FichierDuManifeste[]
}

function refus(message: string): Error {
  return new Error(`${message} Refaire l'export\u00a0: ${COMMANDE_D_EXPORT}`)
}

/** Les fichiers que `client.ts` demandera, pour `portefeuilles` portefeuilles. */
export function fichiersAttendus(portefeuilles: number): string[] {
  return LANGUES_DE_L_EXPORT.flatMap((langue) => [
    `${langue}/disclaimer.json`,
    `${langue}/portfolios.json`,
    ...Array.from(
      { length: portefeuilles },
      (_, rang) => `${langue}/portfolios/${rang + 1}/analysis.json`,
    ),
  ]).sort()
}

function lireManifeste(dossier: string): Manifeste {
  const chemin = join(dossier, MANIFESTE)
  if (!existsSync(chemin)) {
    throw refus(`L'export de la démonstration est absent (${chemin}).`)
  }
  let lu: unknown
  try {
    lu = JSON.parse(readFileSync(chemin, 'utf-8'))
  } catch {
    throw refus(`Le manifeste de l'export ne se lit pas (${chemin}).`)
  }
  const manifeste = lu as Partial<Manifeste> | null
  if (
    manifeste === null ||
    typeof manifeste !== 'object' ||
    typeof manifeste.date_gel !== 'string' ||
    !Array.isArray(manifeste.portefeuilles) ||
    !Array.isArray(manifeste.fichiers)
  ) {
    throw refus(`Le manifeste de l'export n'a pas la forme attendue (${chemin}).`)
  }
  return manifeste as Manifeste
}

/**
 * Les fichiers de l'export, vérifiés, par chemin (`fr/portfolios.json`).
 * Toute erreur dit ce qui ne va pas et la commande qui refait l'export.
 */
export function lireExport(
  dossier: string,
  attendu: { readonly date: string; readonly portefeuilles: number } = {
    date: DATE_DE_LA_DEMO,
    portefeuilles: PORTEFEUILLES_DE_LA_DEMO,
  },
): Map<string, Buffer> {
  const manifeste = lireManifeste(dossier)

  if (manifeste.date_gel !== attendu.date) {
    throw refus(
      `L'export est gelé au ${manifeste.date_gel}, et la mention du site dit ${attendu.date} ` +
        '(contenu/demo.ts).',
    )
  }
  if (manifeste.portefeuilles.length !== attendu.portefeuilles) {
    throw refus(
      `L'export porte ${manifeste.portefeuilles.length} portefeuilles, et la mention du site ` +
        `en dit ${attendu.portefeuilles} (contenu/demo.ts).`,
    )
  }

  const listes = manifeste.fichiers.map((fichier) => fichier.chemin).sort()
  const attendus = fichiersAttendus(attendu.portefeuilles)
  if (listes.join(' ') !== attendus.join(' ')) {
    throw refus(
      `Le manifeste ne liste pas exactement les fichiers que lit la démonstration\u00a0: ` +
        `${listes.join(', ')} au lieu de ${attendus.join(', ')}.`,
    )
  }

  const fichiers = new Map<string, Buffer>()
  for (const { chemin, octets, sha256 } of manifeste.fichiers) {
    const sur_disque = join(dossier, chemin)
    if (!existsSync(sur_disque)) throw refus(`Le fichier ${chemin} de l'export manque.`)
    const contenu = readFileSync(sur_disque)
    const empreinte = createHash('sha256').update(contenu).digest('hex')
    if (contenu.length !== octets || empreinte !== sha256) {
      throw refus(`Le fichier ${chemin} de l'export n'est pas celui que décrit son manifeste.`)
    }
    fichiers.set(chemin, contenu)
  }
  return fichiers
}

/** Le nom d'une méthode d'écriture, cité comme une chaîne : guillemets ou accents graves. */
const METHODE_D_ECRITURE =
  /"(?:POST|PUT|DELETE|PATCH)"|'(?:POST|PUT|DELETE|PATCH)'|`(?:POST|PUT|DELETE|PATCH)`/g

/**
 * Ce qui, dans un fichier JavaScript du build de démonstration, nomme l'API
 * ou une écriture. Vide pour un fichier qui ne fait que lire ses données.
 */
export function fautesDuBundle(code: string): string[] {
  const fautes: string[] = []
  if (code.includes('/api')) fautes.push('la chaîne /api')
  for (const methode of new Set(code.match(METHODE_D_ECRITURE) ?? [])) {
    fautes.push(`la méthode d'écriture ${methode}`)
  }
  return fautes
}

/** Le dossier des captures de la page de présentation, depuis la racine du client. */
export const IMAGES_DE_LA_PRESENTATION = 'src/images/presentation/'

/** Ce que le contrôle lit d'un fichier du build. */
export interface FichierDuBuild {
  readonly type: 'asset' | 'chunk'
  readonly fileName: string
  /** Les fichiers d'origine d'une ressource émise, tels que Vite les nomme. */
  readonly originalFileNames?: readonly string[]
  readonly code?: string
  readonly source?: string | Uint8Array
}

function texteDe(fichier: FichierDuBuild): string {
  if (fichier.type === 'chunk') return fichier.code ?? ''
  return typeof fichier.source === 'string' ? fichier.source : ''
}

/**
 * Les images de la page de présentation qu'un build a émises, par le nom
 * qu'il leur a donné. Lève une erreur si un autre fichier du build nomme
 * l'une d'elles : elle ne serait plus un fichier que rien ne demande.
 */
export function imagesDeLaPresentation(fichiers: readonly FichierDuBuild[]): string[] {
  const images = fichiers
    .filter(
      (fichier) =>
        fichier.type === 'asset' &&
        (fichier.originalFileNames ?? []).some((origine) =>
          origine.split(sep).join('/').includes(IMAGES_DE_LA_PRESENTATION),
        ),
    )
    .map((fichier) => fichier.fileName)

  for (const fichier of fichiers) {
    if (images.includes(fichier.fileName)) continue
    const texte = texteDe(fichier)
    const nommee = images.find((image) => texte.includes(image))
    if (nommee !== undefined) {
      throw new Error(
        `Le build ordinaire ne montre pas la page de présentation\u00a0: ${fichier.fileName} nomme ` +
          `${nommee}. La vue n'est pas masquée derrière DEMO (api/client.ts).`,
      )
    }
  }
  return images
}

/**
 * Le greffon du build ordinaire : les images de la page de présentation n'y
 * entrent pas.
 */
export function sansLaDemonstration(): Plugin {
  return {
    name: 'mx-risk-sans-la-demonstration',
    apply: 'build',
    generateBundle(_options, bundle) {
      let images: string[]
      try {
        images = imagesDeLaPresentation(Object.values(bundle))
      } catch (cause) {
        this.error(cause instanceof Error ? cause.message : String(cause))
      }
      for (const image of images) delete bundle[image]
    },
  }
}

/** Le greffon du build de démonstration ; `dossier` est celui de l'export. */
export function demonstration(dossier: string): Plugin {
  return {
    name: 'mx-risk-demonstration',
    apply: 'build',
    transformIndexHtml() {
      return [{ tag: 'meta', attrs: { ...BALISE_ROBOTS }, injectTo: 'head' }]
    },
    generateBundle(_options, bundle) {
      for (const [nom, sortie] of Object.entries(bundle)) {
        if (sortie.type !== 'chunk') continue
        const fautes = fautesDuBundle(sortie.code)
        if (fautes.length > 0) {
          this.error(
            `Le build de démonstration ne doit ni appeler l'API ni écrire\u00a0: ${nom} contient ` +
              `${fautes.join(', ')}. Un écran qui écrit n'est pas masqué derrière DEMO ` +
              '(api/client.ts).',
          )
        }
      }
      for (const [chemin, contenu] of lireExport(dossier)) {
        this.emitFile({
          type: 'asset',
          fileName: `${DOSSIER_DES_DONNEES}/${chemin}`,
          source: contenu,
        })
      }
      this.emitFile({ type: 'asset', fileName: '_headers', source: EN_TETES })
    },
  }
}
