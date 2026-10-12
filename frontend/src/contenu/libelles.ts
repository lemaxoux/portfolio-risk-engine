/**
 * Les libellés de l'interface, un objet par langue (chantier 7D) : sans
 * bibliothèque, une interface typée que `libelles.fr.ts` et `libelles.en.ts`
 * remplissent. TypeScript refuse une clé manquante dans une langue, et
 * `libelles.test.ts` une traduction oubliée.
 *
 * Un libellé qui cite un nombre, une date ou un nom est une fonction : chaque
 * langue l'écrit avec `lib/format` dans sa propre écriture (« 6 lignes »,
 * « 6 holdings »), et cite un nom avec ses propres guillemets. Ce module ne
 * décide rien : quel libellé afficher se décide dans les composants, sur des
 * champs publiés ; ici, chaque langue l'écrit.
 *
 * Les phrases de lecture des mesures, qui choisissent leur tournure sur un
 * signe publié, sont dans `lib/phrases.fr.ts` et `lib/phrases.en.ts`.
 */
import { LIBELLES_EN } from './libelles.en'
import { LIBELLES_FR } from './libelles.fr'
import type { Langue } from '../lib/langue'

/**
 * La page où mène l'écran d'acceptation : celle de l'adresse d'arrivée. `/`
 * rouvre une analyse ; une adresse inconnue, la page qu'elle demandait.
 */
export type Destination = 'analyse' | 'positions' | 'portefeuilles' | 'methodologie' | 'page'

/**
 * Les pages que la navigation propose. « Présentation » et « Avertissement »
 * ne sont proposées que dans la démonstration (DESIGN.md §19.5).
 */
export type PageDuSite =
  | 'presentation'
  | 'analyse'
  | 'positions'
  | 'portefeuilles'
  | 'methodologie'
  | 'avertissement'

/** Un trait de l'histogramme : son niveau, la VaR qu'il porte, son rendement sur l'axe. */
export interface TraitDuGraphique {
  readonly niveau: number
  readonly varHistorique: number
  readonly seuil: number
}

/** La zone ombrée de l'histogramme : la queue d'un niveau, et ses séances. */
export interface QueueDuGraphique {
  readonly niveau: number
  readonly seances: number
}

export interface Libelles {
  /** Le bouton qui passe à l'autre langue. */
  readonly langue: {
    /** Lu par un lecteur d'écran après le nom de l'autre langue. */
    readonly explication: string
  }
  readonly acceptation: {
    /** Le bouton dit la page où il mène, comme son message. */
    readonly ouvrir: Readonly<Record<Destination, string>>
    readonly condition: Readonly<Record<Destination, string>>
  }
  /** Le démarrage : avant l'acceptation, ou quand la liste ne se lit pas. */
  readonly application: {
    readonly chargement: string
    readonly apiInjoignable: string
    readonly rechargerLaPage: string
    readonly portefeuillesIllisibles: string
    readonly rechargerLaListe: string
    /** Le fichier d'une page chargée à la demande n'est pas arrivé (chantier 9.4). */
    readonly pageNonChargee: string
  }
  /** Ce que le client de l'API dit d'un échec qui n'a pas de corps du serveur. */
  readonly api: {
    readonly serveurInjoignable: string
    readonly erreurDuClient: (cause: string) => string
    readonly reponseInattendue: (statut: number) => string
    readonly corpsVide: string
  }
  /**
   * Les textes propres à la démonstration (`npm run build:demo`) : ce qu'elle
   * est, et ce qu'elle dit d'un échec. Ses données sont des fichiers, il n'y
   * a ni API ni serveur à démarrer.
   */
  readonly demo: {
    /** Le titre de la page quand le démarrage échoue. */
    readonly indisponible: string
    /** La requête n'aboutit pas. */
    readonly injoignable: string
    /** Le fichier manque ou n'est pas du JSON ; son nom, entre accents graves, est rendu en code. */
    readonly fichierIllisible: (fichier: string) => string
    /** Ce qu'est le site, en tête de chaque page : le nombre de portefeuilles, leur date de valorisation en ISO. */
    readonly mention: (portefeuilles: number, date: string) => string
    /** Le lien qui termine la mention, vers la page de l'avertissement (§19.6). */
    readonly lireLAvertissement: string
  }
  /** La page de l'avertissement de la démonstration (DESIGN.md §19.6). */
  readonly avertissement: {
    /** Sous le titre : pourquoi la page n'a rien à accepter. */
    readonly pourquoi: string
  }
  /**
   * La page de présentation de la démonstration, à l'adresse `/` (DESIGN.md
   * §19). Sa prose ne contient aucun nombre, ni en chiffres ni en lettres :
   * `presentation.test.ts` le tient. Les nombres affichés viennent de
   * l'export ou de `contenu/demo.ts`, écrits par `format.ts`.
   */
  readonly presentation: {
    readonly titre: string
    readonly chapeau: string
    readonly demonstration: {
      readonly titre: string
      readonly texte: string
    }
    readonly tableau: {
      /** La légende du tableau ; la date de valorisation, en ISO. */
      readonly legende: (date: string) => string
      readonly colonnes: {
        readonly portefeuille: string
        readonly titres: string
        readonly valeur: string
      }
    }
    /** Trois points : une phrase d'attaque, puis son paragraphe. */
    readonly distingue: {
      readonly titre: string
      readonly conditions: { readonly attaque: string; readonly texte: string }
      readonly note: { readonly attaque: string; readonly texte: string }
      readonly refus: { readonly attaque: string; readonly texte: string }
      /** La capture d'un bloc de mesure : sa légende, puis ce que montre l'image. */
      readonly figure: { readonly legende: string; readonly alternative: string }
    }
    readonly resultat: {
      readonly titre: string
      readonly texte: string
      /** Le titre du bloc : la crise rejouée, puis le portefeuille. */
      readonly titreDuBloc: (crise: string, portefeuille: string) => string
      /** Les deux conditions que la provenance d'une mesure ne nomme pas. */
      readonly conditions: { readonly portefeuille: string; readonly crise: string }
      readonly lien: string
    }
    /** La section « How it was built » du README, ni plus ni moins. */
    readonly construit: {
      readonly titre: string
      readonly texte: string
    }
    readonly neMontrePas: {
      readonly titre: string
      readonly texte: string
      /** La capture du tableau de saisie : sa légende, puis ce que montre l'image. */
      readonly figure: { readonly legende: string; readonly alternative: string }
      readonly installer: string
    }
    /** Les textes des liens ; leurs adresses sont dans `contenu/liens.ts`. */
    readonly liens: {
      readonly titre: string
      readonly code: string
      readonly methodologie: string
      readonly methodologieTechnique: string
      readonly architecture: string
      readonly avertissement: string
    }
    readonly auteur: string
  }
  readonly cadre: {
    readonly allerAuContenu: string
  }
  readonly bandeau: {
    readonly portefeuilles: string
    readonly changerDePortefeuille: string
    readonly valoriseAu: string
    readonly fenetreDEstimation: string
  }
  readonly theme: {
    readonly clair: string
    readonly sombre: string
    readonly suivreLeSysteme: string
    /** Le libellé d'action : « Thème sombre ». */
    readonly vers: (nom: string) => string
    /** L'état courant : « thème sombre, comme le système ». */
    readonly commeLeSysteme: (nom: string) => string
    /** L'état courant, figé : « thème sombre, figé ». */
    readonly fige: (nom: string) => string
    /** Le nom accessible : le libellé, puis l'état. */
    readonly nomAccessible: (libelle: string, etat: string) => string
  }
  readonly navigation: {
    readonly pages: Readonly<Record<PageDuSite, string>>
    readonly etiquettePages: string
    /** Les six sections de l'analyse, dans l'ordre, telles que le rail les nomme. */
    readonly sections: readonly [string, string, string, string, string, string]
    readonly sectionsDeLAnalyse: string
    readonly partiesDeLaMethodologie: string
  }
  readonly mesure: {
    readonly detailsDuCalcul: string
    /** Ce qu'un lecteur d'écran lit à la place du tiret d'une valeur absente. */
    readonly nonDisponible: string
  }
  readonly provenance: {
    readonly fenetre: string
    readonly periode: string
    readonly methode: string
    readonly degresDeLiberte: string
    readonly calcul: string
    readonly controle: string
    /** La ligne de contrôle quand le moteur dit pourquoi il manque. */
    readonly controleIndisponible: (raison: string) => string
    /** Le contrôle d'une autre méthode : « Monte Carlo : ». */
    readonly controleDe: (methode: string) => string
    readonly seancesDansLaQueue: string
    readonly seuilRendement: string
    readonly quotidienne: string
    readonly unite: string
    readonly valoriseAu: string
  }
  readonly observation: {
    /** L'étiquette d'une ligne de seuil, ponctuation comprise. */
    readonly seuil: string
    readonly reference: string
  }
  /** Le titre de chaque section, numéro à part. */
  readonly sections: readonly [string, string, string, string, string, string]
  /** Section 1. */
  readonly portefeuille: {
    readonly colonnes: {
      readonly ticker: string
      readonly nom: string
      readonly quantite: string
      readonly prix: (devise: string) => string
      readonly valeur: (devise: string) => string
      readonly poids: string
    }
    readonly total: string
    readonly prix: string
    readonly prixLu: string
    readonly devise: string
    readonly legende: string
  }
  /** Section 2. */
  readonly jourOrdinaire: {
    readonly observes: string
    readonly chapeauObserves: string
    readonly varHistorique: (niveau: string) => string
    readonly titreHistogramme: string
    readonly uniteHistogramme: (largeur: number) => string
    readonly courbe: string
    readonly chapeauCourbe: string
    readonly varNormale: (niveau: string) => string
    readonly varStudent: (niveau: string) => string
    readonly studentSansRaison: string
    readonly ampleur: string
    readonly volatilite: string
    readonly piresJours: string
    readonly chapeauPiresJours: string
    readonly cvar: (niveau: string) => string
  }
  /** Section 3. */
  readonly auPire: {
    readonly perteMaximale: string
    readonly pic: string
    readonly creux: string
    readonly retourAuPic: string
    readonly niveaux: string
    readonly ou: string
    readonly titreSansDepart: string
    readonly titre: (devise: string, depart: string) => string
    readonly unite: (depart: string | null) => string
    readonly descriptionVide: string
    readonly description: (
      depart: string,
      valeurFinale: number,
      arrivee: string,
      creux: number,
      pic: string,
      fond: string,
    ) => string
  }
  /** Section 4. */
  readonly risque: {
    readonly introduction: string
    readonly combien: string
    readonly enCapital: string
    readonly enRisque: string
    readonly lignes: string
    readonly nonEstimable: string
    readonly poids: string
    readonly contributionsNonEstimables: string
    readonly chapeauPoids: string
    readonly titreBarres: string
    readonly uniteBarres: string
    readonly descriptionBarres: (lignes: number, ecarts: string) => string
    readonly cleBarre: string
    readonly cleTrait: string
    readonly legendeTableau: string
    readonly colonnes: {
      readonly ticker: string
      readonly variance: string
      readonly capital: string
      readonly ecart: string
    }
    readonly nonCouverte: string
    readonly ensemble: string
    readonly chapeauEnsemble: string
    readonly correlationNonEstimable: string
    readonly titreCarte: string
    readonly uniteCarte: string
    readonly descriptionCarte: (lignes: number) => string
    readonly lectureEchelle: string
    readonly diagonale: string
  }
  /** Section 5. */
  readonly crise: {
    readonly introduction: string
    readonly regimeIndisponible: string
    readonly legendeRegime: (indice: string) => string
    readonly periodeDEstimation: string
    readonly colonnes: { readonly mesure: string; readonly crise: string }
    readonly lignesRegime: {
      readonly beta: string
      readonly r2: string
      readonly seances: string
      readonly periode: string
    }
    readonly auPointBas: string
    readonly pireMoment: string
    readonly couverture: string
    readonly couvertes: (couvertes: number, total: number) => string
    readonly exclue: (poids: number) => string
    readonly seances: string
    readonly poids: string
    readonly poidsFiges: (date: string) => string
    readonly reference: string
  }
  /** Section 6. */
  readonly moteur: {
    readonly introduction: string
  }
  /** Les annotations et infobulles des graphiques. */
  readonly graphiques: {
    readonly partDeLaVariance: string
    readonly partDuCapital: string
    readonly ecartEnPoints: string
    readonly infobulleContribution: (ticker: string, variance: string, capital: string, ecart: string) => string
    readonly correlations: string
    readonly diagonale: string
    readonly valeursDeLaDiagonale: string
    readonly valeurs: string
    readonly infobulleCorrelation: (ligne: string, colonne: string, valeur: string) => string
    readonly classe: (seances: number, bas: number, haut: number) => string
    readonly queueDeLaCVaR: string
    readonly queue: (niveau: number, seances: number) => string
    readonly classesDeRendements: string
    readonly creuxMaximal: string
    readonly courbeDeValeur: string
    readonly pic: string
    readonly creux: string
    /**
     * Les valeurs d'un graphique, en tableau replié sous lui (chantier 7E,
     * DESIGN.md §9.4) : le libellé du repli, le même sous chaque graphique.
     */
    readonly valeursEnTableau: string
    /** La légende du tableau de l'histogramme : la largeur publiée des tranches. */
    readonly tableauHistogramme: (largeur: number) => string
    readonly tranche: string
    readonly seances: string
    /** Une tranche, de sa borne basse à sa borne haute. */
    readonly trancheDe: (bas: number, haut: number) => string
    /**
     * Ce que le dessin de l'histogramme porte en plus de ses barres : les traits
     * des niveaux tracés et la zone ombrée. `null` quand il n'y en a aucun.
     */
    readonly traitsDuGraphique: (
      traits: readonly TraitDuGraphique[],
      queue: QueueDuGraphique | null,
    ) => string | null
    /** La légende du tableau de la courbe : le titre du graphique, séance par séance. */
    readonly tableauCourbe: (titre: string) => string
    readonly seance: string
    readonly valeur: string
    readonly repere: string
    readonly tableauCorrelation: string
  }
  readonly analyse: {
    readonly titre: (nom: string) => string
    readonly vide: (nom: string) => string
    readonly decritDesPositions: string
    readonly saisirOuImporter: string
    readonly insuffisant: (nom: string) => string
    readonly ditPourquoi: string
    readonly revoirLesPositions: string
    readonly rechargerLAnalyse: string
  }
  readonly introuvable: {
    readonly page: string
    readonly aucunePage: string
    readonly adresse: (chemin: string) => string
    readonly voirLesPortefeuilles: string
    readonly portefeuille: string
    readonly numero: (id: number) => string
  }
  readonly portefeuilles: {
    readonly titre: string
    readonly aucun: string
    readonly creerUn: string
    readonly suiteDeLaCreation: string
    readonly colonnes: {
      readonly nom: string
      readonly lignes: string
      readonly valeur: string
      readonly valorise: string
      readonly modifie: string
      readonly actions: string
    }
    readonly jamais: string
    readonly positionsDe: string
    readonly deNom: (nom: string) => string
    readonly supprimer: string
    readonly nomCite: (nom: string) => string
    readonly chacun: string
    readonly legende: string
    readonly supprime: (nom: string) => string
    readonly nouveau: string
    readonly aucunePosition: string
    readonly nonValorise: (raison: string | null) => string
    readonly question: (nom: string, positions: number) => string
    readonly suppressionEnCours: string
    readonly supprimerDefinitivement: string
    readonly annuler: string
    readonly nomVide: string
    readonly cree: (nom: string) => string
    readonly nom: string
    readonly aideNom: string
    readonly creationEnCours: string
    readonly creer: string
  }
  readonly positions: {
    readonly titre: (nom: string) => string
    readonly aucune: (nom: string) => string
    readonly tableauEstLePortefeuille: string
    readonly saisir: string
    readonly legende: (nom: string) => string
    readonly aide: string
    readonly universIllisible: (detail: string) => string
    readonly ajouter: string
    readonly rienEnregistre: string
    readonly aCorriger: (lignes: number) => string
    readonly saisieRefusee: string
    readonly enregistrementEnCours: string
    readonly enregistrer: string
    readonly nonEnregistrees: string
    readonly importer: string
    readonly enregistrees: (date: string, positions: number) => string
    readonly importe: (fichier: string | null, positions: number) => string
    readonly quitterLesPerd: string
    readonly rester: string
    readonly quitter: string
  }
  readonly saisie: {
    readonly ticker: string
    readonly nom: string
    readonly historique: string
    readonly quantite: string
    readonly prix: (devise: string) => string
    readonly numero: string
    readonly retirer: string
    readonly ligne: string
    readonly retirerLaLigne: (numero: number) => string
    readonly titreInconnu: string
    readonly ligneDeRefus: (ligne: number, message: string) => string
    readonly quantiteManquante: string
    readonly quantiteIllisible: (saisi: string) => string
    readonly prixIllisible: (saisi: string) => string
  }
  readonly csv: {
    readonly deposer: string
    readonly fichierCsv: string
    readonly fichierChoisi: (nom: string, octets: number) => string
    readonly donne: (nom: string) => string
    readonly remplace: (positions: number, nom: string) => string
    readonly modificationsPerdues: string
    readonly importEnCours: string
    readonly importer: string
    readonly lu: string
    readonly fichier: string
    readonly sansNom: string
    readonly encodage: string
    readonly separateur: string
    readonly decimale: string
    readonly lignesLues: string
    readonly lignes: (nombre: number) => string
    readonly format: string
    readonly formatIllisible: string
    readonly exemple: string
    readonly enTete: string
    readonly facultative: string
    readonly sansEffet: string
    readonly separateurEt: (separateur: string, decimales: readonly string[]) => string
    readonly espaces: string
    readonly encodages: string
    readonly auPlus: (octets: number, positions: number) => string
    readonly remplaceTout: string
    readonly nomsEncodages: Readonly<Record<'utf-8' | 'utf-8-sig' | 'cp1252', string>>
    readonly nomsDecimales: Readonly<Record<',' | '.' | 'mixte' | 'aucune', string>>
    readonly nomsEspaces: Readonly<Record<string, string>>
  }
}

export const LIBELLES: Readonly<Record<Langue, Libelles>> = { fr: LIBELLES_FR, en: LIBELLES_EN }

/** Le nom de chaque langue, dans cette langue : le libellé du bouton. */
export const NOMS_DES_LANGUES: Readonly<Record<Langue, string>> = {
  fr: 'Français',
  en: 'English',
}
