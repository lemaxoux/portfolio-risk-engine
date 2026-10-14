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
 * ═══ LES MÉTADONNÉES DE PARTAGE ═══
 *
 * `index.html`, qui n'a qu'une langue, reçoit par ce greffon la description
 * du site et les balises Open Graph, comme `noindex`. Un lien partagé se lit
 * hors contexte, sans JavaScript : l'anglais, la langue du dépôt (DESIGN.md
 * §19.7). AUCUNE ADRESSE N'EST ÉCRITE EN DUR. `og:url` et `og:image`
 * demandent une adresse absolue : elles ne sont écrites, et l'image de
 * prévisualisation n'est émise, que si l'origine du site est donnée par la
 * variable d'environnement `MX_RISK_ORIGINE_DU_SITE`. Une valeur qui n'est
 * pas une origine arrête le build.
 *
 * ═══ LA GARDE DU BUNDLE ═══
 *
 * La démonstration n'appelle pas l'API de l'application, et n'écrit rien dans
 * une base. Sa seule écriture est l'envoi au serveur public, qui analyse le
 * portefeuille qu'un visiteur saisit (chantier 9.6). Ce n'est pas laissé à
 * la relecture : le build échoue, sur ses fichiers JavaScript, si
 *
 * a. `/api` y est écrit, où que ce soit ;
 * b. PUT, DELETE ou PATCH y sont cités, entre guillemets ou accents graves ;
 * c. POST y est cité plus d'une fois dans tout le build, ou ailleurs que
 *    dans le fichier qui porte l'adresse du serveur public ;
 * d. une adresse absolue y nomme une autre origine que celles d'une liste
 *    fermée (`ORIGINES_ADMISES`, chacune avec sa raison) et celle du serveur
 *    public, qui doit y être.
 *
 * Dans le build ordinaire, ces chaînes ne viennent que de `client.ts`.
 *
 * ═══ L'ADRESSE DU SERVEUR PUBLIC ═══
 *
 * Elle arrive au build par la variable `MX_RISK_SERVEUR_PUBLIC`, obligatoire
 * pour la démonstration : sans elle, le site aurait des écrans de saisie sans
 * serveur. `https://hôte`, une origine sans chemin ni barre finale ; pour un
 * essai sur le poste, `http://127.0.0.1:<port>` ou `http://localhost:<port>`.
 * Le contrôle se fait au build, pas à la lecture de la configuration. Le
 * greffon la pose à la place de `import.meta.env.MX_RISK_SERVEUR_PUBLIC`, que
 * `client.ts` est le seul à lire.
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

/**
 * Les fichiers que `client.ts` demandera, pour `portefeuilles` portefeuilles :
 * dans chaque langue, le texte d'acceptation, la liste et l'analyse de chacun,
 * puis ce que lit la saisie du portefeuille du visiteur (chantier 9.6),
 * l'univers des titres et le format du fichier CSV.
 */
export function fichiersAttendus(portefeuilles: number): string[] {
  return LANGUES_DE_L_EXPORT.flatMap((langue) => [
    `${langue}/csv-format.json`,
    `${langue}/disclaimer.json`,
    `${langue}/portfolios.json`,
    ...Array.from(
      { length: portefeuilles },
      (_, rang) => `${langue}/portfolios/${rang + 1}/analysis.json`,
    ),
    `${langue}/securities.json`,
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

/**
 * Le nom d'une méthode d'écriture de l'application, cité comme une chaîne :
 * guillemets ou accents graves. POST est compté à part (contrôle c).
 */
const METHODE_D_ECRITURE = /"(?:PUT|DELETE|PATCH)"|'(?:PUT|DELETE|PATCH)'|`(?:PUT|DELETE|PATCH)`/g

/** POST, cité comme une chaîne. */
const POST_CITE = /"POST"|'POST'|`POST`/g

/**
 * Ce qui, dans UN fichier JavaScript du build de démonstration, nomme l'API
 * ou une écriture de l'application (contrôles a et b), ou cite POST plus
 * d'une fois. Vide pour un fichier qui ne fait que lire ses données, ou qui
 * porte le seul envoi au serveur public.
 */
export function fautesDuBundle(code: string): string[] {
  const fautes: string[] = []
  if (code.includes('/api')) fautes.push('la chaîne /api')
  for (const methode of new Set(code.match(METHODE_D_ECRITURE) ?? [])) {
    fautes.push(`la méthode d'écriture ${methode}`)
  }
  const posts = code.match(POST_CITE) ?? []
  if (posts.length > 1) fautes.push(`la méthode d'écriture POST, citée ${posts.length} fois`)
  return fautes
}

/**
 * Les origines qu'une adresse absolue du build peut nommer, en plus de celle
 * du serveur public : aucune n'est un serveur que le site appelle.
 */
export const ORIGINES_ADMISES: Readonly<Record<string, string>> = {
  'http://www.w3.org':
    "les espaces de noms de SVG et de XML (React, Observable Plot)\u00a0: des noms, qu'aucune requête ne vise",
  'https://github.com':
    "les liens de la page de présentation vers le dépôt, ses documents et le profil de l'auteur",
  'https://react.dev': "l'adresse que React cite dans ses messages d'erreur",
  'https://www.linkedin.com': "le lien de la page de présentation vers le profil de l'auteur",
}

/** Une adresse absolue écrite dans un fichier : son origine, port compris. */
const ADRESSE_ABSOLUE = /https?:\/\/[A-Za-z0-9.-]+(?::\d+)?/g

/** Un fichier JavaScript du build : son nom, et son code. */
export interface FichierJavaScript {
  readonly nom: string
  readonly code: string
}

/**
 * Les fautes du build de démonstration entier, `serveur` étant l'origine du
 * serveur public : les contrôles a et b, fichier par fichier ; c, le POST
 * unique, dans le fichier qui porte l'adresse du serveur ; d, les origines.
 */
export function fautesDuBuild(fichiers: readonly FichierJavaScript[], serveur: string): string[] {
  const fautes: string[] = []
  for (const { nom, code } of fichiers) {
    for (const faute of fautesDuBundle(code)) fautes.push(`${nom}\u00a0: ${faute}`)
  }

  const avecPost = fichiers.filter(({ code }) => (code.match(POST_CITE) ?? []).length > 0)
  if (avecPost.length > 1) {
    fautes.push(`POST est cité dans ${avecPost.length} fichiers\u00a0: ${avecPost.map((f) => f.nom).join(', ')}`)
  }
  for (const { nom, code } of avecPost) {
    if (!code.includes(serveur)) {
      fautes.push(`${nom}\u00a0: POST est cité dans un fichier qui ne porte pas l'adresse du serveur public`)
    }
  }

  const origines = new Set(fichiers.flatMap(({ code }) => code.match(ADRESSE_ABSOLUE) ?? []))
  for (const origine of [...origines].sort()) {
    if (origine !== serveur && !(origine in ORIGINES_ADMISES)) {
      fautes.push(`une adresse absolue nomme une origine qui n'est pas admise\u00a0: ${origine}`)
    }
  }
  if (!origines.has(serveur)) {
    fautes.push(`l'adresse du serveur public (${serveur}) n'est dans aucun fichier`)
  }
  return fautes
}

// ═════════════════════════════════════════════ L'adresse du serveur public ══

/** La variable d'environnement qui donne l'adresse du serveur public (chantier 9.6). */
export const VARIABLE_DU_SERVEUR = 'MX_RISK_SERVEUR_PUBLIC'

/** Ce que le greffon remplace par l'adresse, dans le code du client. */
export const CONSTANTE_DU_SERVEUR = 'import.meta.env.MX_RISK_SERVEUR_PUBLIC'

/**
 * L'adresse du serveur public, lue dans la variable : `https://hôte`, une
 * origine, sans chemin ni barre finale. Une exception déclarée, pour les
 * essais sur le poste : `http://127.0.0.1:<port>` et `http://localhost:<port>`.
 * Absente, vide ou d'une autre forme : une erreur, qui arrête le build.
 */
export function lireLeServeur(valeur: string | undefined): string {
  const forme =
    ' «\u00a0https://hôte\u00a0», sans chemin ni barre finale, ou, pour un essai sur le poste, ' +
    '«\u00a0http://127.0.0.1:port\u00a0»'
  if (valeur === undefined || valeur === '') {
    throw new Error(
      `${VARIABLE_DU_SERVEUR} est obligatoire pour le build de démonstration\u00a0: c'est l'adresse ` +
        `du serveur public,${forme}.`,
    )
  }
  let adresse: URL | null
  try {
    adresse = new URL(valeur)
  } catch {
    adresse = null
  }
  const essai =
    adresse !== null &&
    adresse.protocol === 'http:' &&
    (adresse.hostname === '127.0.0.1' || adresse.hostname === 'localhost') &&
    adresse.port !== ''
  if (adresse === null || adresse.origin !== valeur || (adresse.protocol !== 'https:' && !essai)) {
    throw new Error(
      `${VARIABLE_DU_SERVEUR} doit être l'origine du serveur public,${forme}\u00a0: ` +
        `«\u00a0${valeur}\u00a0» n'en est pas une.`,
    )
  }
  return valeur
}

// ═════════════════════════════════════════ Les métadonnées de partage ══

/** La variable d'environnement qui donne l'origine du site. */
export const VARIABLE_DE_L_ORIGINE = 'MX_RISK_ORIGINE_DU_SITE'

/** Le titre d'un lien partagé : celui de `<title>`. */
export const TITRE_DU_PARTAGE = 'Portfolio Risk Engine'

/**
 * La description d'un lien partagé : la première phrase du README, puis un
 * fragment de la deuxième, majuscule et point ajoutés (chantier 9.6). Elle dit
 * la thèse du produit, et passe la longueur qu'attend l'outil de LinkedIn.
 */
export const DESCRIPTION_DU_PARTAGE =
  'Portfolio Risk Engine measures the risk of a portfolio of US-listed stocks and ETFs. ' +
  'It shows every figure together with the conditions it was estimated under.'

/**
 * Ce que montre l'image de prévisualisation : le texte alternatif anglais de
 * la figure du bloc de mesure. Écrit ici plutôt qu'importé des libellés,
 * comme les langues de l'export : `demoAuBuild.partage.test.ts` les tient
 * égaux.
 */
export const ALTERNATIVE_DE_L_APERCU =
  'A value-at-risk block from the analysis: the figure, a sentence in plain words that ' +
  'states it as a frequency, in dollars, and over a period, then the calculation ' +
  'details (method, window, and period).'

/** Les dimensions de l'image de prévisualisation, que les balises déclarent. */
export const DIMENSIONS_DE_L_APERCU = { largeur: 1200, hauteur: 630 } as const

/**
 * L'origine du site, lue dans la variable d'environnement : `https://hôte`,
 * sans chemin ni barre finale. Absente ou vide : pas d'origine, et aucune
 * adresse absolue n'est écrite. Toute autre valeur lève une erreur.
 */
export function lireLOrigine(valeur: string | undefined): string | null {
  if (valeur === undefined || valeur === '') return null
  let adresse: URL | null
  try {
    adresse = new URL(valeur)
  } catch {
    adresse = null
  }
  if (adresse === null || adresse.protocol !== 'https:' || adresse.origin !== valeur) {
    throw new Error(
      `${VARIABLE_DE_L_ORIGINE} doit être l'origine du site, «\u00a0https://hôte\u00a0», sans chemin ni ` +
        `barre finale\u00a0: «\u00a0${valeur}\u00a0» n'en est pas une.`,
    )
  }
  return valeur
}

/** L'image de prévisualisation : son contenu, et son chemin dans le site. */
export interface Apercu {
  readonly fichier: string
  readonly contenu: Buffer
}

/**
 * L'image de prévisualisation, vérifiée : un PNG aux dimensions que les
 * balises déclarent. Son nom dans le site porte l'empreinte de son contenu.
 */
export function lireLApercu(chemin: string): Apercu {
  if (!existsSync(chemin)) {
    throw new Error(`L'image de prévisualisation est absente (${chemin}).`)
  }
  const contenu = readFileSync(chemin)
  const png = contenu.length >= 24 && contenu.subarray(1, 4).toString('latin1') === 'PNG'
  const largeur = png ? contenu.readUInt32BE(16) : 0
  const hauteur = png ? contenu.readUInt32BE(20) : 0
  if (largeur !== DIMENSIONS_DE_L_APERCU.largeur || hauteur !== DIMENSIONS_DE_L_APERCU.hauteur) {
    throw new Error(
      `L'image de prévisualisation doit être un PNG de ${DIMENSIONS_DE_L_APERCU.largeur} × ` +
        `${DIMENSIONS_DE_L_APERCU.hauteur}\u00a0: ${chemin} fait ${largeur} × ${hauteur}.`,
    )
  }
  const empreinte = createHash('sha256').update(contenu).digest('hex').slice(0, 8)
  return { fichier: `assets/apercu-${empreinte}.png`, contenu }
}

/** Une balise `<meta>` de `index.html`, telle que Vite l'attend. */
export interface BaliseMeta {
  readonly tag: 'meta'
  readonly attrs: Record<string, string>
  readonly injectTo: 'head'
}

function meta(attrs: Record<string, string>): BaliseMeta {
  return { tag: 'meta', attrs, injectTo: 'head' }
}

/**
 * Les balises de partage de `index.html`. `apercu` est le chemin de l'image
 * de prévisualisation dans le site. Sans origine, aucune adresse absolue : ni
 * `og:url` ni `og:image`, et la carte est la petite.
 */
export function balisesDePartage(origine: string | null, apercu: string | null): BaliseMeta[] {
  const communes = [
    meta({ name: 'description', content: DESCRIPTION_DU_PARTAGE }),
    meta({ property: 'og:type', content: 'website' }),
    meta({ property: 'og:title', content: TITRE_DU_PARTAGE }),
    meta({ property: 'og:description', content: DESCRIPTION_DU_PARTAGE }),
  ]
  if (origine === null || apercu === null) {
    return [...communes, meta({ name: 'twitter:card', content: 'summary' })]
  }
  return [
    ...communes,
    meta({ property: 'og:url', content: `${origine}/` }),
    meta({ property: 'og:image', content: `${origine}/${apercu}` }),
    meta({ property: 'og:image:type', content: 'image/png' }),
    meta({ property: 'og:image:width', content: String(DIMENSIONS_DE_L_APERCU.largeur) }),
    meta({ property: 'og:image:height', content: String(DIMENSIONS_DE_L_APERCU.hauteur) }),
    meta({ property: 'og:image:alt', content: ALTERNATIVE_DE_L_APERCU }),
    meta({ name: 'twitter:card', content: 'summary_large_image' }),
  ]
}

/** Ce qu'il faut pour les balises de partage (DESIGN.md §19.7). */
export interface Partage {
  /** L'origine du site, ou `null` : sans elle, aucune adresse absolue. */
  readonly origine: string | null
  /** Le fichier de l'image de prévisualisation : lu seulement avec une origine. */
  readonly apercu: string
}

// ══════════════════════════════════ Les images de la page de présentation ══

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

/**
 * Le greffon du build de démonstration ; `dossier` est celui de l'export.
 * Sans `partage`, il n'y a pas d'origine : aucune adresse absolue. `serveur`
 * est la valeur brute de `MX_RISK_SERVEUR_PUBLIC`, contrôlée au build.
 */
export function demonstration(
  dossier: string,
  partage: Partage = { origine: null, apercu: '' },
  serveur: string | undefined = undefined,
): Plugin {
  const apercu = partage.origine === null ? null : lireLApercu(partage.apercu)
  return {
    name: 'mx-risk-demonstration',
    apply: 'build',
    config() {
      return { define: { [CONSTANTE_DU_SERVEUR]: JSON.stringify(lireLeServeur(serveur)) } }
    },
    transformIndexHtml() {
      return [
        { tag: 'meta', attrs: { ...BALISE_ROBOTS }, injectTo: 'head' },
        ...balisesDePartage(partage.origine, apercu?.fichier ?? null),
      ]
    },
    generateBundle(_options, bundle) {
      const fichiers: FichierJavaScript[] = []
      for (const [nom, sortie] of Object.entries(bundle)) {
        if (sortie.type === 'chunk') fichiers.push({ nom, code: sortie.code })
      }
      const fautes = fautesDuBuild(fichiers, lireLeServeur(serveur))
      if (fautes.length > 0) {
        this.error(
          "Le build de démonstration n'appelle pas l'API, n'écrit dans aucune base, et n'a qu'un " +
            `serveur\u00a0: ${fautes.join('\u00a0; ')}. Un écran qui écrit n'est pas masqué derrière ` +
            'DEMO, ou une adresse a été écrite en dur (api/client.ts).',
        )
      }
      for (const [chemin, contenu] of lireExport(dossier)) {
        this.emitFile({
          type: 'asset',
          fileName: `${DOSSIER_DES_DONNEES}/${chemin}`,
          source: contenu,
        })
      }
      this.emitFile({ type: 'asset', fileName: '_headers', source: EN_TETES })
      if (apercu !== null) {
        this.emitFile({ type: 'asset', fileName: apercu.fichier, source: apercu.contenu })
      }
    },
  }
}
