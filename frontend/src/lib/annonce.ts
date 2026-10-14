/**
 * L'annonce d'un geste, adressée à une page — DESIGN.md §13 (chantier 9.6).
 *
 * Un geste qui réussit se dit dans la région d'annonce de la page où l'on
 * arrive (`components/Cadre`) : « Portefeuille « Démo » créé. », « Positions
 * gardées dans ce navigateur le 14 octobre 2026 : 2 lignes. ». L'annonce est
 * adressée à cette page, et ne s'affiche que là : elle ne suit pas
 * l'utilisateur de page en page.
 *
 * Elle est écrite dans la langue du geste, et ne se réécrit pas dans une
 * autre : changer de langue la retire, et revenir à la première ne la rend
 * pas. Le changement de langue est un geste à son tour ; réécrite, l'annonce
 * changerait le contenu de la région, qu'un lecteur d'écran lirait de
 * nouveau, comme si l'action venait d'avoir lieu.
 */
import type { Langue } from './langue'

export interface Annonce {
  readonly texte: string
  /** L'adresse de la page où elle s'affiche. */
  readonly page: string
  /** La langue de son texte : celle du geste. */
  readonly langue: Langue
}

/** L'annonce qui reste quand la langue affichée est `langue` : la même, ou aucune. */
export function annonceGardee(annonce: Annonce | null, langue: Langue): Annonce | null {
  return annonce !== null && annonce.langue === langue ? annonce : null
}

/** Ce que la page `chemin` annonce dans la langue `langue` : un texte, ou rien. */
export function annonceDeLaPage(
  annonce: Annonce | null,
  chemin: string,
  langue: Langue,
): string | null {
  const gardee = annonceGardee(annonce, langue)
  return gardee !== null && gardee.page === chemin ? gardee.texte : null
}
