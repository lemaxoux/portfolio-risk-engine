/**
 * Les libellés de l'interface, en français : la langue par défaut. Chaque
 * libellé y est recopié tel qu'il était écrit dans son composant avant le
 * chantier 7D, octet pour octet, sauf les trois exceptions décidées le
 * 2026-10-08 : le bouton de langue, le bouton de l'écran d'acceptation selon
 * la page d'arrivée, et « Bêta » dans le tableau de la section 5.
 */
import {
  compte,
  dateEnToutesLettres,
  dateISO,
  decimal,
  lignes,
  points,
  pourcentage,
  seances,
} from '../lib/format'
import { cite } from '../lib/phrases'
import type { Libelles } from './libelles'

export const LIBELLES_FR: Libelles = {
  langue: {
    explication: '(le site passe en anglais)',
  },
  acceptation: {
    ouvrir: {
      analyse: "Ouvrir l'analyse",
      positions: 'Ouvrir les positions',
      portefeuilles: 'Ouvrir les portefeuilles',
      methodologie: 'Ouvrir la méthodologie',
      page: 'Ouvrir la page demandée',
    },
    condition: {
      analyse: "La case doit être cochée pour ouvrir l'analyse.",
      positions: 'La case doit être cochée pour ouvrir les positions.',
      portefeuilles: 'La case doit être cochée pour ouvrir les portefeuilles.',
      methodologie: 'La case doit être cochée pour ouvrir la méthodologie.',
      page: 'La case doit être cochée pour ouvrir la page demandée.',
    },
  },
  application: {
    chargement: 'Chargement',
    apiInjoignable: 'API injoignable',
    rechargerLaPage: 'Recharger la page',
    portefeuillesIllisibles: 'Portefeuilles illisibles',
    rechargerLaListe: 'Recharger la liste',
  },
  api: {
    serveurInjoignable: "L'API ne répond pas. La démarrer\u00a0: python -m backend.api",
    erreurDuClient: (cause) => `Erreur inattendue du client\u00a0: ${cause}`,
    reponseInattendue: (statut) => `Réponse ${statut} inattendue de l'API.`,
    corpsVide: "L'API a répondu un corps vide.",
  },
  cadre: {
    allerAuContenu: 'Aller au contenu',
  },
  bandeau: {
    portefeuilles: 'Portefeuilles',
    changerDePortefeuille: 'Changer de portefeuille',
    valoriseAu: 'Valorisé au',
    fenetreDEstimation: "Fenêtre d'estimation",
  },
  theme: {
    clair: 'clair',
    sombre: 'sombre',
    suivreLeSysteme: 'Suivre le système',
    vers: (nom) => `Thème ${nom}`,
    commeLeSysteme: (nom) => `thème ${nom}, comme le système`,
    fige: (nom) => `thème ${nom}, figé`,
    nomAccessible: (libelle, etat) => `${libelle} (actuellement ${etat})`,
  },
  navigation: {
    pages: {
      analyse: 'Analyse',
      positions: 'Positions et import',
      portefeuilles: 'Portefeuilles',
      methodologie: 'Méthodologie',
    },
    etiquettePages: 'Pages',
    sections: [
      'Le portefeuille',
      'Un jour ordinaire',
      'Au pire',
      'Qui porte le risque',
      'En crise',
      'Ce que le moteur en dit',
    ],
    sectionsDeLAnalyse: "Sections de l'analyse",
    partiesDeLaMethodologie: 'Parties de la méthodologie',
  },
  mesure: {
    detailsDuCalcul: 'Détails du calcul',
    nonDisponible: 'non disponible',
  },
  provenance: {
    fenetre: 'Fenêtre',
    periode: 'Période',
    methode: 'Méthode',
    degresDeLiberte: 'Degrés de liberté',
    calcul: 'Calcul',
    controle: 'Contrôle',
    controleIndisponible: (raison) => `indisponible. ${raison}`,
    controleDe: (methode) => `${methode}\u00a0: `,
    seancesDansLaQueue: 'Séances dans la queue',
    seuilRendement: 'Seuil (rendement)',
    quotidienne: 'Quotidienne',
    unite: 'Unité',
    valoriseAu: 'Valorisé au',
  },
  observation: {
    seuil: 'Seuil\u00a0: ',
    reference: 'Référence\u00a0: ',
  },
  sections: [
    'Le portefeuille',
    "Ce qu'il perd un jour ordinaire",
    "Ce qu'il a perdu au pire",
    'Qui porte le risque',
    'Ce qui se passe en crise',
    'Ce que le moteur en dit',
  ],
  portefeuille: {
    colonnes: {
      ticker: 'Ticker',
      nom: 'Nom',
      quantite: 'Quantité',
      prix: (devise) => `Prix (${devise})`,
      valeur: (devise) => `Valeur (${devise})`,
      poids: 'Poids',
    },
    total: 'Total',
    prix: 'Prix',
    prixLu: 'dernière clôture brute, non ajustée',
    devise: 'Devise',
    legende:
      'Positions détenues, désignées par leur ticker (le code du titre en bourse), valorisées à la dernière clôture',
  },
  jourOrdinaire: {
    observes: 'Les jours réellement observés',
    chapeauObserves:
      'La VaR, ou valeur à risque, répond à une question\u00a0: à partir de quelle perte ' +
      'une journée devient-elle rare\u00a0? Ici, la réponse vient des jours réellement ' +
      'observés, sans formule.',
    varHistorique: (niveau) => `VaR ${niveau} historique, horizon 1 séance`,
    titreHistogramme: 'Variations de valeur, jour par jour',
    uniteHistogramme: (largeur) => `séances par classe de ${points(largeur, 2)}`,
    courbe: 'Avec une courbe mathématique',
    chapeauCourbe:
      "La même question, posée à une courbe ajustée sur vos variations plutôt qu'aux " +
      'jours observés. La loi normale rend les très mauvais jours très rares\u00a0; la ' +
      'loi de Student leur laisse plus de place.',
    varNormale: (niveau) => `VaR ${niveau} paramétrique, loi normale`,
    varStudent: (niveau) => `VaR ${niveau} paramétrique, loi de Student`,
    studentSansRaison: "Le volet Student n'a pas pu être ajusté, sans raison publiée.",
    ampleur: "L'ampleur habituelle des variations",
    volatilite: 'Volatilité annualisée',
    piresJours: 'Les pires jours',
    chapeauPiresJours:
      'Les jours où le seuil est franchi, combien perd-on en moyenne\u00a0? ' +
      "C'est la CVaR\u00a0: la perte moyenne des pires jours.",
    cvar: (niveau) => `CVaR ${niveau}, horizon 1 séance`,
  },
  auPire: {
    perteMaximale: 'Perte maximale pic-creux',
    pic: 'Pic',
    creux: 'Creux',
    retourAuPic: 'Retour au pic',
    niveaux: 'Niveaux',
    ou: "Où ce creux s'est produit",
    titreSansDepart: "Valeur d'une unité investie",
    titre: (devise, depart) =>
      `Valeur de 1\u00a0${devise} placé le ${dateEnToutesLettres(depart)}`,
    unite: (depart) => `base 1${depart === null ? '' : ` le ${dateISO(depart)}`}, poids actuels`,
    descriptionVide: 'Courbe de richesse vide.',
    description: (depart, valeurFinale, arrivee, creux, pic, fond) =>
      `Une unité investie le ${dateISO(depart)} vaut ${decimal(valeurFinale, 2)} ` +
      `le ${dateISO(arrivee)}\u00a0; perte maximale de ${pourcentage(creux, 1)} ` +
      `entre le pic du ${dateISO(pic)} et le creux du ${dateISO(fond)}.`,
  },
  risque: {
    introduction:
      'Quelles lignes font le plus bouger votre portefeuille\u00a0? Leur poids en argent ne ' +
      "suffit pas à le dire\u00a0: certaines bougent plus que d'autres, ou en même temps.",
    combien: 'Combien de lignes, en réalité',
    enCapital: 'Lignes effectives en capital',
    enRisque: 'Lignes effectives en risque',
    lignes: 'Lignes',
    nonEstimable: 'non estimable, sans raison publiée',
    poids: 'Le poids de chaque ligne dans les variations',
    contributionsNonEstimables: 'Contributions non estimables, sans raison publiée.',
    chapeauPoids:
      "La barre montre la part d'une ligne dans les variations du portefeuille, le " +
      'trait sa part dans sa valeur. Quand la barre dépasse le trait, la ligne le ' +
      'fait bouger plus que son poids ne le laisse croire.',
    titreBarres: 'Part de chaque ligne dans les variations et dans la valeur',
    uniteBarres: '% de la variance du portefeuille, % de sa valeur\u00a0; écart en points',
    descriptionBarres: (nombre, ecarts) =>
      `Parts des variations comparées aux parts de la valeur, ${lignes(nombre)}\u00a0: ${ecarts}`,
    cleBarre: 'barre\u00a0: part dans les variations',
    cleTrait: 'trait\u00a0: part dans la valeur',
    legendeTableau:
      "Part de chaque ligne dans les variations et dans la valeur, puis ce qu'elle " +
      'a apporté au portefeuille dans chaque crise rejouée, en points\u00a0: ' +
      'un point vaut 1\u202f% de sa valeur au début de la crise',
    colonnes: {
      ticker: 'Ticker',
      variance: 'Part des variations',
      capital: 'Part de la valeur',
      ecart: 'Écart',
    },
    nonCouverte: ' non couverte',
    ensemble: 'Ce qui bouge ensemble',
    chapeauEnsemble:
      "Deux lignes qui montent et baissent les mêmes jours s'amortissent mal l'une " +
      "l'autre. La corrélation mesure ce lien, de \u22121 à +1.",
    correlationNonEstimable: 'Corrélation non estimable, sans raison publiée.',
    titreCarte: 'Corrélation des variations quotidiennes',
    uniteCarte: 'coefficient de corrélation, sans unité',
    descriptionCarte: (nombre) =>
      `Corrélations deux à deux de ${lignes(nombre)}, valeur écrite dans chaque cellule.`,
    lectureEchelle:
      '+1\u00a0: les deux lignes bougent toujours dans le même sens. 0\u00a0: aucun lien ' +
      'visible. \u22121\u00a0: toujours en sens inverse. Plus les nombres approchent +1, moins ' +
      'détenir les deux amortit les variations. Les couleurs suivent une échelle fixe, la ' +
      'même pour tout portefeuille.',
    diagonale: 'diagonale\u00a0: chaque ligne avec elle-même, 1 par définition, hors échelle',
  },
  crise: {
    introduction:
      "Qu'aurait perdu votre portefeuille d'aujourd'hui dans les grandes crises passées\u00a0? " +
      'Chaque crise est rejouée avec ses montants actuels au départ, sans rien acheter ni ' +
      'vendre ensuite.',
    regimeIndisponible: 'Comparaison de régimes indisponible, sans raison publiée.',
    legendeRegime: (indice) =>
      `Sensibilité à ${indice}, en temps ordinaire et en crise (jamais moyennées)`,
    periodeDEstimation: "période d'estimation",
    colonnes: { mesure: 'Mesure', crise: 'Crise' },
    lignesRegime: { beta: 'Bêta', r2: 'R²', seances: 'Séances', periode: 'Période' },
    auPointBas: 'Au point bas du marché',
    pireMoment: 'Pire moment traversé',
    couverture: 'Couverture',
    couvertes: (couvertes, total) => `${lignes(couvertes)} sur ${total}`,
    exclue: (poids) => `${pourcentage(poids, 1)} de la valeur\u00a0: `,
    seances: 'Séances',
    poids: 'Poids',
    poidsFiges: (date) => `ceux du ${dateISO(date)}, quantités figées ensuite`,
    reference: 'Référence',
  },
  moteur: {
    introduction:
      "Ce que l'outil retient des sections précédentes. Des constats, pas des conseils\u00a0: " +
      'il décrit votre portefeuille, il ne recommande rien. Quand une phrase repose sur un ' +
      'seuil, il est indiqué\u00a0; un seuil choisi à la main le dit.',
  },
  graphiques: {
    partDeLaVariance: 'part de la variance',
    partDuCapital: 'part du capital',
    ecartEnPoints: 'écart en points',
    infobulleContribution: (ticker, variance, capital, ecart) =>
      `${ticker}\npart de la variance ${variance}\npart du capital ${capital}\nécart ${ecart}`,
    correlations: 'corrélations',
    diagonale: 'diagonale',
    valeursDeLaDiagonale: 'valeurs de la diagonale',
    valeurs: 'valeurs',
    infobulleCorrelation: (ligne, colonne, valeur) => `${ligne} et ${colonne}\ncorrélation ${valeur}`,
    classe: (nombre, bas, haut) =>
      `${seances(nombre)}\nde ${pourcentage(bas, 2)} inclus à ${pourcentage(haut, 2)} exclu`,
    queueDeLaCVaR: 'queue de la CVaR à 95 %',
    queue: (niveau, nombre) => `queue à ${pourcentage(niveau, 0)}\u00a0:\n${seances(nombre)}`,
    classesDeRendements: 'classes de rendements',
    creuxMaximal: 'creux maximal',
    courbeDeValeur: 'courbe de richesse',
    pic: 'pic',
    creux: 'creux',
  },
  analyse: {
    titre: (nom) => `Analyse de ${cite(nom)}`,
    vide: (nom) => `${cite(nom)} n'a encore aucune position`,
    decritDesPositions: "L'analyse décrit des positions\u00a0: ce portefeuille n'en a aucune.",
    saisirOuImporter: 'Saisir ou importer les positions',
    insuffisant: (nom) => `${cite(nom)} ne s'analyse pas en l'état`,
    ditPourquoi:
      "Ses positions sont en base, mais le moteur n'en tire pas d'analyse. Il dit " +
      "pourquoi, et ce qu'il faut faire\u00a0:",
    revoirLesPositions: 'Revoir les positions',
    rechargerLAnalyse: "Recharger l'analyse",
  },
  introuvable: {
    page: 'Page introuvable',
    aucunePage: 'Aucune page à cette adresse',
    adresse: (chemin) => `${cite(chemin)} ne correspond à aucune page de l'application.`,
    voirLesPortefeuilles: 'Voir les portefeuilles',
    portefeuille: 'Portefeuille introuvable',
    numero: (id) => `Aucun portefeuille ne porte le numéro ${id}\u00a0: il a peut-être été supprimé.`,
  },
  portefeuilles: {
    titre: 'Portefeuilles',
    aucun:
      "Aucun portefeuille en base. L'analyse décrit un portefeuille\u00a0: il faut " +
      "d'abord en créer un, puis saisir ou importer ses positions.",
    creerUn: 'Créer un portefeuille',
    suiteDeLaCreation:
      "Ses positions se saisissent ligne à ligne, ou s'importent d'un fichier CSV (par " +
      "exemple l'export d'un tableur) sur la page qui s'ouvre à la création.",
    colonnes: {
      nom: 'Portefeuille',
      lignes: 'Lignes',
      valeur: 'Valeur',
      valorise: 'Valorisé au',
      modifie: 'Positions modifiées le',
      actions: 'Actions',
    },
    jamais: 'jamais',
    positionsDe: 'Positions',
    deNom: (nom) => ` de ${cite(nom)}`,
    supprimer: 'Supprimer',
    nomCite: (nom) => ` ${cite(nom)}`,
    chacun: "Chaque portefeuille s'analyse à part. Son nom ouvre son analyse.",
    legende: 'Portefeuilles en base',
    supprime: (nom) => `Portefeuille ${cite(nom)} supprimé.`,
    nouveau: 'Nouveau portefeuille',
    aucunePosition: 'Aucune position',
    nonValorise: (raison) => `Non valorisé\u00a0: ${raison ?? 'raison non publiée.'}`,
    question: (nom, positions) =>
      `Supprimer ${cite(nom)}\u00a0? ` +
      (positions === 0
        ? "Il n'a aucune position."
        : `Ses ${lignes(positions)} seront effacées avec lui.`) +
      ' La suppression est définitive.',
    suppressionEnCours: 'Suppression en cours…',
    supprimerDefinitivement: 'Supprimer définitivement',
    annuler: 'Annuler',
    nomVide: 'Le nom est vide\u00a0: il en faut un pour reconnaître le portefeuille.',
    cree: (nom) => `Portefeuille ${cite(nom)} créé.`,
    nom: 'Nom',
    aideNom: "120 caractères au plus. Il apparaît dans le bandeau de l'analyse.",
    creationEnCours: 'Création en cours…',
    creer: 'Créer le portefeuille',
  },
  positions: {
    titre: (nom) => `Positions de ${cite(nom)}`,
    aucune: (nom) =>
      `${cite(nom)} n'a encore aucune position. Les saisir ci-dessous, une ligne par titre, ou importer un fichier.`,
    tableauEstLePortefeuille:
      "Le tableau est le portefeuille\u00a0: l'enregistrer remplace toutes ses positions par les lignes affichées.",
    saisir: 'Saisir les positions',
    legende: (nom) => `Positions de ${cite(nom)}, une ligne par titre`,
    aide:
      'Le prix de revient est facultatif\u00a0: il ne sert à aucune mesure de risque. ' +
      '«\u00a0Historique depuis\u00a0» est la première séance de prix du titre en base\u00a0; ' +
      "une ligne cotée depuis peu raccourcit la fenêtre de toute l'analyse.",
    universIllisible: (detail) =>
      `Les noms des titres n'ont pas pu être lus (${detail}). La saisie reste ` +
      "possible\u00a0: chaque ticker est vérifié à l'enregistrement.",
    ajouter: 'Ajouter une ligne',
    rienEnregistre: "Rien n'a été enregistré\u00a0: ",
    aCorriger: (nombre) => `${lignes(nombre)} à corriger.`,
    saisieRefusee: 'la saisie est refusée.',
    enregistrementEnCours: 'Enregistrement en cours…',
    enregistrer: 'Enregistrer les positions',
    nonEnregistrees: 'Modifications non enregistrées.',
    importer: 'Importer un fichier CSV',
    enregistrees: (date, positions) =>
      `Positions enregistrées le ${dateEnToutesLettres(date)}\u00a0: ${lignes(positions)}.`,
    importe: (fichier, positions) =>
      `Portefeuille importé depuis ${cite(fichier ?? 'le fichier')}\u00a0: ${lignes(positions)}.`,
    quitterLesPerd:
      'Les modifications du tableau ne sont pas enregistrées. Quitter cette page les perd.',
    rester: 'Rester sur la page',
    quitter: 'Quitter sans enregistrer',
  },
  saisie: {
    ticker: 'Ticker',
    nom: 'Nom',
    historique: 'Historique depuis',
    quantite: 'Quantité',
    prix: (devise) => `Prix de revient (${devise}), facultatif`,
    numero: 'N°',
    retirer: 'Retirer',
    ligne: 'ligne ',
    retirerLaLigne: (numero) => ` la ligne ${numero}`,
    titreInconnu: 'Titre inconnu',
    ligneDeRefus: (ligne, message) => `Ligne ${ligne}\u00a0: ${message}`,
    quantiteManquante: 'Quantité manquante.',
    quantiteIllisible: (saisi) =>
      `${cite(saisi)} n'est pas une quantité lisible. Écrire par exemple 40 ou 12,5.`,
    prixIllisible: (saisi) =>
      `${cite(saisi)} n'est pas un prix de revient lisible. Écrire par exemple 185,20, ou laisser vide.`,
  },
  csv: {
    deposer: 'Déposer un fichier CSV ici, ou le choisir\u00a0:',
    fichierCsv: 'Fichier CSV',
    fichierChoisi: (nom, octets) => `${nom}, ${compte(octets, 'octet')}`,
    donne: (nom) => `L'import donne à ${cite(nom)}, encore vide, les positions du fichier.`,
    remplace: (positions, nom) =>
      `L'import remplace les ${lignes(positions)} actuelles de ${cite(nom)} par celles du fichier.`,
    modificationsPerdues: ' Les modifications non enregistrées du tableau seront perdues.',
    importEnCours: 'Import en cours…',
    importer: 'Importer le portefeuille',
    lu: 'Lu dans le fichier\u00a0:',
    fichier: 'Fichier',
    sansNom: 'sans nom',
    encodage: 'Encodage',
    separateur: 'Séparateur',
    decimale: 'Décimale',
    lignesLues: 'Lignes lues',
    lignes: (nombre) => lignes(nombre),
    format: 'Format du fichier',
    formatIllisible: "Le format n'a pas pu être lu\u00a0: ",
    exemple: "Par exemple, tel qu'un tableur l'enregistre\u00a0:",
    enTete: "Une ligne d'en-tête, puis une ligne par titre. Colonnes obligatoires\u00a0: ",
    facultative: '\u00a0; facultative\u00a0: ',
    sansEffet: " (le prix de revient, sans effet sur l'analyse)",
    separateurEt: (separateur, decimales) =>
      `Séparateur ${cite(separateur)}\u00a0: décimale ${decimales.map((d) => cite(d)).join(' ou ')}.`,
    espaces: 'Espaces de milliers admises\u00a0: ',
    encodages: 'Encodage\u00a0: ',
    auPlus: (octets, positions) => `Au plus ${compte(octets, 'octet')} et ${lignes(positions)}.`,
    remplaceTout: "L'import remplace toutes les positions du portefeuille.",
    nomsEncodages: {
      'utf-8': 'UTF-8',
      'utf-8-sig': "UTF-8 avec marque d'ordre des octets (BOM)",
      cp1252: 'Windows-1252 (CP1252)',
    },
    nomsDecimales: {
      ',': cite(','),
      '.': cite('.'),
      mixte: 'mixte\u00a0: virgules et points dans le même fichier',
      aucune: 'aucune\u00a0: tous les nombres sont entiers',
    },
    nomsEspaces: {
      ' ': 'ordinaire',
      '\u00a0': 'insécable',
      '\u202f': 'fine insécable',
    },
  },
}
