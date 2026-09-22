/**
 * Les phrases que l'interface COMPOSE — DESIGN.md §8.1 et §15.
 *
 * Elles sont ici, et pas dans les composants, pour deux raisons : elles sont
 * testables sans rendu, et les avoir au même endroit rend visible le peu qu'il
 * y en a. Tout le reste de ce que le produit affirme est RÉDIGÉ PAR LE
 * BACKEND — observations du moteur de règles, `caveat` du CVaR, provenance des
 * seuils, bandeau d'acceptation — et s'affiche tel quel.
 *
 * AUCUNE DE CES PHRASES NE CALCULE. La lecture d'un niveau de confiance passe
 * par une TABLE et non par une division : « une séance sur vingt » n'est pas
 * dérivé de 0,95, il y est associé.
 */
import type { LimitingPosition, Window } from '../api/types'
import { ESPACE_FINE, compte, dateISO, pourcentage, seances } from './format'

/**
 * « Perte attendue une séance sur vingt » (§15).
 *
 * Une TABLE, pas un calcul. Écrire `1 / (1 - confiance)` produirait 20 pour
 * 0,95 et 100 pour 0,99, mais aussi 6,67 pour 0,85 — et il faudrait alors
 * décider comment l'écrire, c'est-à-dire inventer une lecture que personne n'a
 * validée. Un niveau absent de la table n'a pas de traduction : le terme
 * technique s'affiche seul, ce qui est moins parlant mais jamais faux.
 *
 * Les clés sont les niveaux que `routes/analysis.CONFIDENCE_LEVELS` publie.
 */
const LECTURE_CONFIANCE: Record<string, string> = {
  '0.95': 'une séance sur vingt',
  '0.99': 'une séance sur cent',
}

export function frequenceLue(confiance: number): string | null {
  return LECTURE_CONFIANCE[String(confiance)] ?? null
}

/**
 * La phrase de lecture d'une VaR.
 *
 * Une VaR est une PERTE POSITIVE. Une valeur négative signifie un gain à ce
 * niveau de confiance, et c'est la phrase qui doit le dire — le nombre, lui,
 * s'affiche tel que le moteur l'a rendu (§9.1, règle 2).
 */
export function lectureDeVar(valeur: number, confiance: number): string {
  const frequence = frequenceLue(confiance)
  if (valeur < 0) {
    return frequence === null
      ? `gain à ce niveau de confiance, et non une perte`
      : `gain ${frequence} : à ce niveau, le portefeuille ne perd pas`
  }
  return frequence === null
    ? `perte attendue au niveau ${pourcentage(confiance, 0)}`
    : `perte attendue ${frequence}`
}

/**
 * La phrase de lecture d'une CVaR : ce qu'elle MOYENNE, pas un quantile.
 *
 * Deuxième table, pour la même raison que la première : la part de queue est
 * associée au niveau de confiance, pas dérivée de lui. Un niveau absent des
 * deux tables retombe sur une formulation qui ne cite que le niveau publié.
 */
const PART_DE_QUEUE: Record<string, string> = {
  '0.95': `5${ESPACE_FINE}%`,
  '0.99': `1${ESPACE_FINE}%`,
}

export function lectureDeCVaR(confiance: number): string {
  const part = PART_DE_QUEUE[String(confiance)]
  return part === undefined
    ? `perte moyenne des séances qui dépassent la VaR ${pourcentage(confiance, 0)}`
    : `perte moyenne des ${part} de séances les pires`
}

/** Fraîcheur des positions (§8.1) : l'`as_of` date les prix, pas les quantités. */
export function phraseFraicheurPositions(updatedAt: string | null): string {
  return updatedAt === null
    ? "Positions jamais modifiées depuis l'application"
    : `Positions modifiées le ${dateISO(updatedAt)}`
}

/**
 * Fenêtre réduite (§8.1).
 *
 * C'est le SEUL endroit du bandeau où le nombre de séances DEMANDÉ apparaît :
 * partout ailleurs le bandeau annonce la fenêtre obtenue, sous peine de
 * promettre une profondeur d'historique que le calcul n'a pas eue.
 *
 * Quand `limitantes` est vide, aucune ligne n'est nommée. Ce n'est pas une
 * négligence : le backend ne remplit cette liste que lorsqu'il a PROUVÉ qu'une
 * entrée en cotation tardive borne la fenêtre. Une troncature venue d'un trou
 * au milieu d'une série ne désigne personne, et mieux vaut ne nommer personne
 * que nommer à tort.
 */
export function phraseFenetreReduite(
  fenetre: Window,
  limitantes: readonly LimitingPosition[],
): string | null {
  if (fenetre.complete) return null

  const tete =
    `Fenêtre réduite à ${seances(fenetre.observations)} ` +
    `sur ${compte(fenetre.requested, 'demandée')}`

  if (limitantes.length === 0) {
    return `${tete} (historique incomplet).`
  }

  const [premiere, ...suivantes] = limitantes
  if (premiere === undefined) return `${tete} (historique incomplet).`

  const morceaux = [
    `${premiere.ticker} n'est coté que depuis le ${dateISO(premiere.first_available)}`,
    ...suivantes.map(
      (ligne) => `${ligne.ticker}, depuis le ${dateISO(ligne.first_available)}`,
    ),
  ]
  return `${tete} : ${morceaux.join(' ; ')}.`
}
