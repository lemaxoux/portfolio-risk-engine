/**
 * Le SEUL endroit du frontend qui écrit un nombre — DESIGN.md §6.3 et §14.
 *
 * C'est le pendant de la convention de signe du backend : un seul endroit
 * décide comment un pourcentage, une perte, une date et une valeur indéfinie
 * s'écrivent. Un composant qui formaterait un nombre lui-même est un bogue en
 * attente — il produira « 1.38% » à côté d'un « 1,38 % » rédigé par le moteur,
 * et le produit aura deux conventions.
 *
 * ═══ LES CARACTÈRES SONT FIXÉS ICI, PAS LAISSÉS À `Intl` ═══
 *
 * `Intl.NumberFormat('fr-FR')` produit le bon RÉSULTAT VISUEL, mais pas
 * toujours les mêmes POINTS DE CODE : la sortie pour `fr-FR` a changé d'espace
 * selon les versions d'ICU — U+00A0 dans les unes, U+202F dans les autres. Or
 * Node (où tournent les tests) et le navigateur embarquent des ICU différents.
 * Un test écrit contre `Intl` passerait sur la machine de développement et ne
 * prouverait rien sur ce que l'utilisateur voit.
 *
 * Et surtout : le backend RÉDIGE des phrases contenant des nombres
 * (`backend/typography.py`), avec ces caractères-là, choisis explicitement. Les
 * deux moitiés du produit doivent écrire « 25,6 % » de la même façon, octet
 * pour octet, sinon une phrase du moteur et le chiffre affiché à côté d'elle
 * se coupent différemment en fin de ligne.
 *
 *     U+202F  ESPACE FINE INSÉCABLE   séparateur de milliers, et avant « % »
 *     U+00A0  ESPACE INSÉCABLE        entre un nombre et le mot qu'il compte
 *     U+2212  SIGNE MOINS             jamais le trait d'union U+002D
 *     U+2014  TIRET CADRATIN          une mesure indéfinie
 *
 * ═══ CE MODULE NE CALCULE AUCUNE MESURE ═══
 *
 * Multiplier une fraction par cent et arrondir est du FORMATAGE, et l'API le
 * délègue explicitement au client : « toutes les valeurs sont des fractions
 * […] le formatage — pourcentage, virgule décimale, arrondi — est décidé côté
 * client, à un seul endroit ». Il n'y a ici ni somme, ni écart, ni moyenne :
 * une valeur qui manque s'ajoute au moteur avec son test, jamais ici.
 */

/** Espace fine insécable — milliers, et avant le signe pourcent. */
export const ESPACE_FINE = '\u202F'
/** Espace insécable — entre un nombre et le mot qu'il compte. */
export const ESPACE_INSECABLE = '\u00A0'
/** Signe moins typographique, à la même chasse que les chiffres. */
export const SIGNE_MOINS = '\u2212'
/** Une mesure indéfinie. Jamais « 0 », jamais « ∞ » (§9.1, règle 3). */
export const TIRET_INDEFINI = '\u2014'

/**
 * Groupe la partie entière par milliers.
 *
 * À partir de quatre chiffres, comme `backend.typography.thousands` : « 504 »
 * reste « 504 », « 1000 » devient « 1 000 ». Les deux moitiés du produit
 * groupent au même seuil.
 */
function grouper(entier: string): string {
  return entier.replace(/\B(?=(\d{3})+(?!\d))/g, ESPACE_FINE)
}

/**
 * Un nombre, en écriture française.
 *
 * `decimales` n'a pas de valeur par défaut, volontairement : §9.3 exige le même
 * nombre de décimales dans toute une colonne, et un défaut implicite fait
 * apparaître des colonnes mêlant « 1,4 » et « 1,38 » sans que personne l'ait
 * décidé. Le choix est donc pris à chaque appel, où le contexte est connu.
 *
 * L'ARRONDI EST CELUI DE `toFixed`, qui travaille sur la valeur binaire réelle
 * du nombre : `(1.005).toFixed(2)` rend « 1,00 », parce que 1,005 n'est pas
 * représentable et vaut en réalité 1,00499999999999989. Aucun formateur ne fait
 * mieux sans arithmétique décimale, et les mesures publiées portent assez de
 * décimales pour que ce demi-ulp ne déplace jamais un chiffre affiché.
 */
export function decimal(valeur: number, decimales: number): string {
  if (!Number.isFinite(valeur)) {
    throw new Error(`Valeur non finie à formater\u00a0: ${valeur}`)
  }
  const negatif = valeur < 0
  const [entier = '0', fraction] = Math.abs(valeur).toFixed(decimales).split('.')
  const corps = fraction === undefined ? grouper(entier) : `${grouper(entier)},${fraction}`
  // Une valeur négative qui s'arrondit à zéro ne porte pas de signe : « −0,0 % »
  // se lit comme une perte alors que le chiffre dit qu'il n'y en a pas.
  const nul = Number(Math.abs(valeur).toFixed(decimales)) === 0
  return negatif && !nul ? `${SIGNE_MOINS}${corps}` : corps
}

/**
 * Une fraction en pourcentage : `0.0138` → « 1,38 % ».
 *
 * L'espace avant le signe est FINE et INSÉCABLE : avec une espace ordinaire, le
 * « % » part seul à la ligne suivante.
 */
export function pourcentage(fraction: number, decimales: number): string {
  return `${decimal(fraction * 100, decimales)}${ESPACE_FINE}%`
}

/**
 * Un nombre et le mot qu'il compte : « 504 séances ».
 *
 * Copie exacte de `backend.typography.counted`, accord compris : pluriel au-delà
 * de deux exclu, singulier en deçà — « 0 séance », « 1 séance », « 2 séances ».
 * C'est la règle française, où zéro et un prennent le singulier.
 */
export function compte(nombre: number, singulier: string, pluriel?: string): string {
  const mot = Math.abs(nombre) < 2 ? singulier : (pluriel ?? `${singulier}s`)
  return `${decimal(nombre, 0)}${ESPACE_INSECABLE}${mot}`
}

/** Les deux usages les plus fréquents, nommés pour ne pas être réécrits. */
export function seances(nombre: number): string {
  return compte(nombre, 'séance')
}

export function lignes(nombre: number): string {
  return compte(nombre, 'ligne')
}

/**
 * Une valeur de portefeuille : le NOMBRE seul, à deux décimales.
 *
 * Sans devise : ce module n'en invente aucune. La devise est une donnée publiée
 * par l'API (`valuation.currency`), et c'est `montant` qui l'accole. Une
 * colonne de tableau, dont l'en-tête porte déjà la devise, n'a besoin que du
 * nombre.
 */
export function valeurDePortefeuille(valeur: number): string {
  return decimal(valeur, 2)
}

/**
 * Un montant et sa devise : « 83 185,85 USD ».
 *
 * La devise est le CODE ISO 4217 publié par l'API, jamais un symbole. À
 * Montréal, « $ » sans qualificatif se lit dollar canadien : « 83 185,85 $ »
 * y serait faux de 30 % sans que rien ne le signale. Un code qui n'a pas la
 * forme d'un code ISO est refusé plutôt qu'affiché — c'est le seul moyen
 * qu'un « $ » ne passe jamais, d'où qu'il vienne.
 *
 * U+00A0 entre le nombre et le code : c'est l'unité que le nombre compte, et
 * « USD » ne doit pas partir seul à la ligne.
 */
export function montant(valeur: number, devise: string): string {
  if (!/^[A-Z]{3}$/.test(devise)) {
    throw new Error(`Devise qui n'est pas un code ISO 4217\u00a0: «\u00a0${devise}\u00a0»`)
  }
  return `${valeurDePortefeuille(valeur)}${ESPACE_INSECABLE}${devise}`
}

const MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
] as const

/**
 * Date de provenance, telle que l'API l'écrit : `YYYY-MM-DD`.
 *
 * Non ambiguë, triable, et identique à ce que le client a reçu : un bloc de
 * provenance qui reformaterait la date rendrait sa comparaison avec la réponse
 * brute pénible, sans rien gagner.
 */
export function dateISO(iso: string): string {
  return iso
}

/**
 * Date en toutes lettres, pour la prose : « 9 septembre 2026 ».
 *
 * Le découpage est fait sur la chaîne et non par `new Date(iso)` : un
 * `Date` interprète « 2026-09-09 » en UTC puis l'affiche dans le fuseau local,
 * ce qui recule la date d'un jour à l'ouest de Greenwich. Une date de
 * valorisation fausse d'un jour est une faute, pas un détail d'affichage.
 */
export function dateEnToutesLettres(iso: string): string {
  const [annee, mois, jour] = iso.split('\u002D')
  if (annee === undefined || mois === undefined || jour === undefined) return iso
  const nom = MOIS[Number(mois) - 1]
  if (nom === undefined) return iso
  return `${Number(jour)}${ESPACE_INSECABLE}${nom}${ESPACE_INSECABLE}${annee}`
}

/**
 * Un pourcentage, ou le tiret d'indéfini.
 *
 * LE POINT DE CETTE FONCTION EST QU'ELLE NE PEUT PAS RENDRE « 0,00 % » SUR UN
 * `null`. Le backend a déjà été corrigé deux fois sur des annulations
 * catastrophiques produisant des ratios absurdes : rendre un zéro plausible à
 * la place d'une mesure absente réintroduirait le problème par l'affichage.
 * La RAISON de l'absence s'affiche à côté, elle n'est pas de ce module.
 */
export function pourcentageOuTiret(
  fraction: number | null | undefined,
  decimales: number,
): string {
  return fraction === null || fraction === undefined
    ? TIRET_INDEFINI
    : pourcentage(fraction, decimales)
}

export function decimalOuTiret(
  valeur: number | null | undefined,
  decimales: number,
): string {
  return valeur === null || valeur === undefined
    ? TIRET_INDEFINI
    : decimal(valeur, decimales)
}

/**
 * Une VaR ou une CVaR négative est un GAIN à ce niveau de confiance.
 *
 * Le backend rend ces mesures en PERTES POSITIVES : `0.0138` se lit « perte
 * d'au moins 1,38 % ». L'interface ne retourne jamais le signe et n'en ajoute
 * jamais un (§9.1, règle 2). Mais une valeur négative existe, et elle ne veut
 * pas dire « petite perte » : elle veut dire qu'à ce niveau de confiance, le
 * portefeuille gagne. C'est la PHRASE DE LECTURE qui doit changer, pas le
 * nombre — d'où ce prédicat, qui ne touche à rien et laisse le composant dire
 * la bonne chose.
 */
export function estUnGain(perte: number): boolean {
  return perte < 0
}

/**
 * Le nombre de décimales d'une COLONNE (§9.3) : le plus petit qui écrit
 * chaque valeur de la colonne sans l'arrondir, plafonné.
 *
 * Une colonne de quantités entières s'écrit « 40 », « 120 » — pas « 40,0000 ».
 * Qu'une seule quantité soit fractionnaire, et TOUTE la colonne prend ses
 * décimales : « 40,50 » au-dessus de « 120,00 », jamais « 40,5 » au-dessus de
 * « 120 ». Au-delà du plafond, les valeurs sont arrondies à lui.
 */
export function decimalesDeColonne(valeurs: readonly number[], plafond: number): number {
  for (let decimales = 0; decimales < plafond; decimales += 1) {
    if (valeurs.every((valeur) => Number(valeur.toFixed(decimales)) === valeur)) {
      return decimales
    }
  }
  return plafond
}

/**
 * Une fraction écrite en POINTS de pourcentage : `0.0025` → « 0,25 point ».
 *
 * L'accord suit le nombre AFFICHÉ, comme dans le moteur de règles
 * (`rules._points`) : « 1,9 point », « 2,0 points ».
 */
export function points(fraction: number, decimales: number): string {
  const ecrit = decimal(fraction * 100, decimales)
  const affiche = Number(Math.abs(fraction * 100).toFixed(decimales))
  return `${ecrit}${ESPACE_INSECABLE}${affiche >= 2 ? 'points' : 'point'}`
}

/**
 * Un écart signé, en points : `0.098` → « +9,8 pts », `-0.081` → « −8,1 pts ».
 *
 * Pendant exact de `backend.typography.signed_points` : le « + » d'un écart
 * positif est écrit, parce qu'un écart se lit par son signe ; une valeur qui
 * s'arrondit à zéro n'en porte aucun.
 */
export function pointsSignes(fraction: number, decimales: number): string {
  const ecrit = decimal(fraction * 100, decimales)
  const nul = Number(Math.abs(fraction * 100).toFixed(decimales)) === 0
  const signe = fraction > 0 && !nul ? '+' : ''
  return `${signe}${ecrit}${ESPACE_INSECABLE}pts`
}

/**
 * Une date ISO de l'API en `Date`, à minuit UTC — pour POSITIONNER un point
 * sur un axe de temps, jamais pour l'écrire.
 *
 * Le fuseau est explicite : `new Date('2026-09-09')` est déjà en UTC, mais
 * l'écrire ensuite avec les méthodes locales reculerait la date d'un jour à
 * l'ouest de Greenwich. Tout ce qui écrit une date lue ici passe donc par
 * `moisISO`, qui lit les composantes UTC.
 */
export function dateDepuisISO(iso: string): Date {
  return new Date(`${iso}T00:00:00Z`)
}

/** Graduation d'un axe de temps : « 2025-02 », en composantes UTC. */
export function moisISO(date: Date): string {
  const mois = String(date.getUTCMonth() + 1).padStart(2, '0')
  return `${date.getUTCFullYear()}\u002D${mois}`
}

/**
 * Un rendement SIGNÉ : « −44,0 % », « +59,7 % ».
 *
 * Pour un résultat qui peut être un gain comme une perte — une crise rejouée,
 * l'apport d'une ligne. Le « + » est écrit : sans lui, « 3,2 % » à côté de
 * « −44,0 % » se lirait comme une perte oubliée. Pendant de
 * `backend.typography.percent(..., signed=True)` ; une valeur qui s'arrondit
 * à zéro ne porte aucun signe.
 */
export function pourcentageSigne(fraction: number, decimales: number): string {
  const nul = Number(Math.abs(fraction * 100).toFixed(decimales)) === 0
  const signe = fraction > 0 && !nul ? '+' : ''
  return `${signe}${pourcentage(fraction, decimales)}`
}
