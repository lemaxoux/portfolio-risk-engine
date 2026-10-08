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
  HistoricalVar,
  Var,
  Volatility,
  Window,
} from '../api/types'
import { LIBELLES } from '../contenu/libelles'
import { dateISO, decimal, pourcentage, seances } from './format'
import type { Langue } from './langue'

/**
 * Les deux lignes que porte TOUTE mesure estimée : combien d'observations, et
 * sur quelles dates. Elles viennent de la fenêtre DE CETTE MESURE, jamais de
 * celle du document — le beta est régressé sous une contrainte d'échantillon
 * qui lui est propre.
 */
export function lignesDeFenetre(fenetre: Window, langue: Langue = 'fr'): LigneProvenance[] {
  const l = LIBELLES[langue].provenance
  return [
    { libelle: l.fenetre, valeur: seances(fenetre.observations, langue) },
    {
      libelle: l.periode,
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
  resultat: Var | HistoricalVar,
  controle: Var | null = null,
  raisonSansControle: string | null = null,
  langue: Langue = 'fr',
): LigneProvenance[] {
  const l = LIBELLES[langue].provenance
  const lignes: LigneProvenance[] = [{ libelle: l.methode, valeur: resultat.method }]

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
      libelle: l.degresDeLiberte,
      valeur: `ν = ${decimal(resultat.nu, 2, langue)}`,
    })
  }

  lignes.push({ libelle: l.calcul, valeur: resultat.detail })
  lignes.push(...lignesDeFenetre(resultat.window, langue))

  if (controle !== null) {
    lignes.push({
      libelle: l.controle,
      valeur: `${resultat.method === controle.method ? '' : l.controleDe(controle.method)}${pourcentage(controle.value, 2, langue)}, ${controle.detail}`,
    })
  } else if (raisonSansControle !== null) {
    // Le contrôle manque, et le moteur dit pourquoi
    // (`monte_carlo_unavailable_reason`) : une ligne absente sans raison
    // serait un blanc inexpliqué.
    lignes.push({ libelle: l.controle, valeur: l.controleIndisponible(raisonSansControle) })
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
export function provenanceDeCVaR(resultat: ExpectedShortfall, langue: Langue = 'fr'): LigneProvenance[] {
  const l = LIBELLES[langue].provenance
  // Refusée sous 1/(1 − α) séances : il n'y a ni queue à compter ni seuil à
  // écrire. Reste la fenêtre, sur laquelle le refus a été prononcé.
  if (resultat.tail_observations === null || resultat.threshold === null) {
    return lignesDeFenetre(resultat.window, langue)
  }
  return [
    // « Séances dans la queue » et non « Queue moyennée » : le libellé dit ce
    // que COMPTE le nombre, des séances. « Moyennée » décrivait l'opération
    // faite sur elles, et se lisait comme un adjectif de la valeur.
    { libelle: l.seancesDansLaQueue, valeur: seances(resultat.tail_observations, langue) },
    {
      libelle: l.seuilRendement,
      valeur: pourcentage(resultat.threshold, 2, langue),
    },
    ...lignesDeFenetre(resultat.window, langue),
  ]
}

export function provenanceDeVolatilite(resultat: Volatility, langue: Langue = 'fr'): LigneProvenance[] {
  const l = LIBELLES[langue].provenance
  return [
    { libelle: l.methode, valeur: resultat.method },
    { libelle: l.quotidienne, valeur: pourcentage(resultat.daily, 2, langue) },
    ...lignesDeFenetre(resultat.window, langue),
  ]
}

/**
 * Ce qu'un graphique porte sous son titre (§9.4, modèle FRED) : l'unité, la
 * fenêtre, et la date de valorisation. Les trois sont OBLIGATOIRES — c'est la
 * signature de `<Graphique>` qui l'impose, et c'est ici qu'elles s'écrivent.
 */
export function provenanceDeGraphique(
  unite: string,
  fenetre: Window,
  asOf: string,
  langue: Langue = 'fr',
): LigneProvenance[] {
  const l = LIBELLES[langue].provenance
  return [
    { libelle: l.unite, valeur: unite },
    ...lignesDeFenetre(fenetre, langue),
    { libelle: l.valoriseAu, valeur: dateISO(asOf) },
  ]
}
