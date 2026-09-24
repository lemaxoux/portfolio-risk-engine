/**
 * Construction des blocs de provenance — DESIGN.md §9.1.
 *
 * « Le bloc de provenance est généré depuis les champs réels du backend, jamais
 * saisi à la main. » Ce module est l'endroit où cette phrase devient du code :
 * chaque ligne rendue sort d'un champ de la réponse, et rien ne s'écrit à côté.
 *
 * LA DIFFÉRENCE N'EST PAS COSMÉTIQUE. Une provenance saisie à la main dit ce
 * qu'on croyait au moment de l'écrire. Le jour où une mesure change de fenêtre
 * — parce qu'une ligne est entrée en cotation tardivement, ce qui arrive sans
 * qu'aucun paramètre ne bouge — le texte saisi continue d'annoncer 504 séances
 * pour un calcul qui en a utilisé 40. Le chiffre serait juste, sa provenance
 * fausse, et rien ne le signalerait.
 *
 * AUCUN CALCUL ICI NON PLUS : ces fonctions lisent des champs et les donnent à
 * `lib/format`. Pas de somme, pas d'écart, pas de moyenne.
 */
import type { LigneProvenance } from '../components/Provenance'
import type {
  ExpectedShortfall,
  Var,
  Volatility,
  Window,
} from '../api/types'
import { dateISO, decimal, pourcentage, seances } from './format'

/**
 * Les deux lignes que porte TOUTE mesure estimée : combien d'observations, et
 * sur quelles dates. Elles viennent de la fenêtre DE CETTE MESURE, jamais de
 * celle du document — le beta est régressé sous une contrainte d'échantillon
 * qui lui est propre.
 */
export function lignesDeFenetre(fenetre: Window): LigneProvenance[] {
  return [
    { libelle: 'Fenêtre', valeur: seances(fenetre.observations) },
    {
      libelle: 'Période',
      valeur: `${dateISO(fenetre.start)} → ${dateISO(fenetre.end)}`,
    },
  ]
}

/**
 * Provenance d'une VaR.
 *
 * `controle` est le résultat Monte Carlo du même niveau, quand il existe. Il
 * n'apparaît QUE dans la provenance, jamais comme un chiffre de la section :
 * le Monte Carlo normal reproduit la paramétrique par construction. En faire
 * un bloc mesure le présenterait comme une troisième opinion, alors que c'est
 * une vérification de calcul — et deux chiffres qui disent la même chose côte
 * à côte se lisent comme deux mesures indépendantes qui concordent.
 */
export function provenanceDeVar(
  resultat: Var,
  controle: Var | null = null,
): LigneProvenance[] {
  const lignes: LigneProvenance[] = [{ libelle: 'Méthode', valeur: resultat.method }]

  // ν n'apparaît que sur les VaR de Student, où il EST l'information (§11.5) :
  // c'est le degré de liberté ajusté sur les données, donc l'épaisseur de queue
  // que l'hypothèse de normalité refusait de voir.
  //
  // NOMMÉ AVANT D'ÊTRE ÉCRIT SEUL. En IBM Plex Sans, ν (nu) et v se ressemblent
  // au point de se confondre : « ν = 4,07 » se lirait « v = 4,07 ». Le premier
  // usage du bloc dit donc « degrés de liberté », et il précède la ligne
  // « Calcul », dont le texte rédigé par le backend cite ν sans le nommer.
  if (resultat.nu !== null) {
    lignes.push({
      libelle: 'Degrés de liberté',
      valeur: `ν = ${decimal(resultat.nu, 2)}`,
    })
  }

  lignes.push({ libelle: 'Calcul', valeur: resultat.detail })
  lignes.push(...lignesDeFenetre(resultat.window))

  if (controle !== null) {
    lignes.push({
      libelle: 'Contrôle',
      valeur: `${resultat.method === controle.method ? '' : `${controle.method} : `}${pourcentage(controle.value, 2)} — ${controle.detail}`,
    })
  }

  return lignes
}

/**
 * Provenance d'une CVaR.
 *
 * `tail_observations` est en tête, et c'est délibéré : une CVaR est une MOYENNE
 * de queue, et le nombre de séances qu'elle moyenne dit à lui seul ce qu'on
 * peut en attendre. Six séances sur 504, chacune pèse 17 % du chiffre.
 *
 * `threshold` change de convention en cours d'objet — c'est un RENDEMENT, donc
 * négatif, là que `value` est une perte positive. Le libellé le dit, parce que
 * deux conventions dans le même bloc sans étiquette seraient un piège.
 */
export function provenanceDeCVaR(resultat: ExpectedShortfall): LigneProvenance[] {
  return [
    // « Séances dans la queue » et non « Queue moyennée » : le libellé dit ce
    // que COMPTE le nombre, des séances. « Moyennée » décrivait l'opération
    // faite sur elles, et se lisait comme un adjectif de la valeur.
    { libelle: 'Séances dans la queue', valeur: seances(resultat.tail_observations) },
    {
      libelle: 'Seuil (rendement)',
      valeur: pourcentage(resultat.threshold, 2),
    },
    ...lignesDeFenetre(resultat.window),
  ]
}

export function provenanceDeVolatilite(resultat: Volatility): LigneProvenance[] {
  return [
    { libelle: 'Méthode', valeur: resultat.method },
    { libelle: 'Quotidienne', valeur: pourcentage(resultat.daily, 2) },
    ...lignesDeFenetre(resultat.window),
  ]
}
