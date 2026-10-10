/**
 * Les libellés de l'interface, en anglais américain (chantier 7D) :
 * ponctuation de Chicago, casse phrase, aucune contraction, « you » pour le
 * vouvoiement, aucune espace avant « : », « ; », « ? » ou « ! », guillemets
 * doubles. Les termes sont ceux du glossaire (`anglais-proposition.md` §c.2,
 * hors dépôt) : « holding » pour une ligne du portefeuille, « line » pour une
 * ligne d'un fichier ou du tableau, « security » pour un titre,
 * « fluctuations » pour les variations. Un terme nouveau est listé dans le
 * rapport de la session.
 */
import {
  compte,
  dateEnToutesLettres,
  dateISOLiee,
  decimal,
  lignes,
  pointsEnAdjectif,
  pourcentage,
  seances,
} from '../lib/format'
import { cite, majuscule } from '../lib/phrases'
import type { Libelles } from './libelles'

const EN = 'en' as const

/** « 6 lines » : une ligne d'un fichier ou du tableau, pas une ligne du portefeuille. */
function lignesDeFichier(nombre: number): string {
  return compte(nombre, 'line', undefined, EN)
}

const citer = (texte: string) => cite(texte, EN)

export const LIBELLES_EN: Libelles = {
  langue: {
    explication: '(the site switches to French)',
  },
  acceptation: {
    ouvrir: {
      analyse: 'Open the analysis',
      positions: 'Open the positions',
      portefeuilles: 'Open the portfolios',
      methodologie: 'Open the methodology',
      page: 'Open the requested page',
    },
    condition: {
      analyse: 'The box must be checked to open the analysis.',
      positions: 'The box must be checked to open the positions.',
      portefeuilles: 'The box must be checked to open the portfolios.',
      methodologie: 'The box must be checked to open the methodology.',
      page: 'The box must be checked to open the requested page.',
    },
  },
  application: {
    chargement: 'Loading',
    apiInjoignable: 'API unreachable',
    rechargerLaPage: 'Reload the page',
    portefeuillesIllisibles: 'Portfolios could not be read',
    rechargerLaListe: 'Reload the list',
  },
  api: {
    serveurInjoignable: 'The API is not responding. Start it: python -m backend.api',
    erreurDuClient: (cause) => `Unexpected client error: ${cause}`,
    reponseInattendue: (statut) => `Unexpected ${statut} response from the API.`,
    corpsVide: 'The API returned an empty body.',
  },
  demo: {
    indisponible: 'Demonstration unavailable',
    injoignable:
      'The demonstration data could not be loaded. Check the connection, then reload ' +
      'the page.',
    fichierIllisible: (fichier) =>
      `The demonstration file \`${fichier}\` is missing or cannot be read. Reload the page.`,
    mention: (portefeuilles, date) =>
      `Demonstration: ${compte(portefeuilles, 'fixed portfolio', undefined, EN)}, ` +
      `valued as of ${dateEnToutesLettres(date, EN)}.`,
  },
  cadre: {
    allerAuContenu: 'Skip to content',
  },
  bandeau: {
    portefeuilles: 'Portfolios',
    changerDePortefeuille: 'Switch portfolio',
    valoriseAu: 'Valued as of',
    fenetreDEstimation: 'Estimation window',
  },
  theme: {
    clair: 'light',
    sombre: 'dark',
    suivreLeSysteme: 'Follow the system',
    vers: (nom) => `${majuscule(nom)} theme`,
    commeLeSysteme: (nom) => `${nom} theme, following the system`,
    fige: (nom) => `${nom} theme, fixed`,
    nomAccessible: (libelle, etat) => `${libelle} (currently ${etat})`,
  },
  navigation: {
    pages: {
      analyse: 'Analysis',
      positions: 'Positions and import',
      portefeuilles: 'Portfolios',
      methodologie: 'Methodology',
    },
    etiquettePages: 'Pages',
    sections: [
      'The portfolio',
      'An ordinary day',
      'At worst',
      'What carries the risk',
      'In a crisis',
      'What the engine says',
    ],
    sectionsDeLAnalyse: 'Sections of the analysis',
    partiesDeLaMethodologie: 'Parts of the methodology',
  },
  mesure: {
    detailsDuCalcul: 'Calculation details',
    nonDisponible: 'not available',
  },
  provenance: {
    fenetre: 'Window',
    periode: 'Period',
    methode: 'Method',
    degresDeLiberte: 'Degrees of freedom',
    calcul: 'Calculation',
    controle: 'Cross-check',
    controleIndisponible: (raison) => `unavailable. ${raison}`,
    controleDe: (methode) => `${methode}: `,
    seancesDansLaQueue: 'Sessions in the tail',
    seuilRendement: 'Threshold (return)',
    quotidienne: 'Daily',
    unite: 'Unit',
    valoriseAu: 'Valued as of',
  },
  observation: {
    seuil: 'Threshold: ',
    reference: 'Reference: ',
  },
  sections: [
    'The portfolio',
    'What it loses on an ordinary day',
    'What it would have lost at worst',
    'What carries the risk',
    'What happens in a crisis',
    'What the engine says',
  ],
  portefeuille: {
    colonnes: {
      ticker: 'Ticker',
      nom: 'Name',
      quantite: 'Quantity',
      prix: (devise) => `Price (${devise})`,
      valeur: (devise) => `Value (${devise})`,
      poids: 'Weight',
    },
    total: 'Total',
    prix: 'Price',
    prixLu: 'last raw close, unadjusted',
    devise: 'Currency',
    legende:
      "Positions held, identified by their ticker (the security's stock market code), valued at the last close",
  },
  jourOrdinaire: {
    observes: 'The days actually observed',
    chapeauObserves:
      'VaR, or value at risk, answers one question: from what loss does a day become rare? ' +
      'Here, the answer comes from the days actually observed, with no formula.',
    varHistorique: (niveau) => `Historical VaR ${niveau}, 1-session horizon`,
    titreHistogramme: 'Changes in value, day by day',
    uniteHistogramme: (largeur) => `sessions per ${pointsEnAdjectif(largeur, 2)} bin`,
    courbe: 'With a mathematical curve',
    chapeauCourbe:
      'The same question, put to a curve fitted to your fluctuations rather than to the ' +
      'observed days. The normal distribution makes very bad days very rare; ' +
      "Student's t-distribution leaves them more room.",
    varNormale: (niveau) => `Parametric VaR ${niveau}, normal distribution`,
    varStudent: (niveau) => `Parametric VaR ${niveau}, Student's t-distribution`,
    studentSansRaison: "The Student's t part could not be fitted, and no reason was published.",
    ampleur: 'The usual size of the fluctuations',
    volatilite: 'Annualized volatility',
    piresJours: 'The worst days',
    chapeauPiresJours:
      'On the days the threshold is crossed, how much is lost on average? ' +
      'That is CVaR: the average loss on the worst days.',
    cvar: (niveau) => `CVaR ${niveau}, 1-session horizon`,
  },
  auPire: {
    perteMaximale: 'Maximum drawdown, peak to trough',
    pic: 'Peak',
    creux: 'Trough',
    retourAuPic: 'Recovery to the peak',
    niveaux: 'Levels',
    ou: 'Where this trough occurred',
    titreSansDepart: 'Value of one unit invested',
    titre: (devise, depart) =>
      `Value of 1\u00a0${devise} invested on ${dateEnToutesLettres(depart, EN)}`,
    unite: (depart) => `base 1${depart === null ? '' : ` on ${dateISOLiee(depart)}`}, current weights`,
    descriptionVide: 'Empty value curve.',
    description: (depart, valeurFinale, arrivee, creux, pic, fond) =>
      `One unit invested on ${dateISOLiee(depart)} would be worth ${decimal(valeurFinale, 2, EN)} ` +
      `on ${dateISOLiee(arrivee)}; maximum drawdown of ${pourcentage(creux, 1, EN)} ` +
      `between the peak of ${dateISOLiee(pic)} and the trough of ${dateISOLiee(fond)}.`,
  },
  risque: {
    introduction:
      'Which holdings move your portfolio the most? Their weight in money is not enough ' +
      'to tell: some move more than others, or at the same time.',
    combien: 'How many holdings, really',
    enCapital: 'Effective holdings by value',
    enRisque: 'Effective holdings by risk',
    lignes: 'Holdings',
    nonEstimable: 'not estimable, no reason published',
    poids: 'The weight of each holding in the fluctuations',
    contributionsNonEstimables: 'Contributions not estimable, no reason published.',
    chapeauPoids:
      "The bar shows a holding's share of the portfolio's fluctuations, the line its " +
      'share of its value. When the bar goes past the line, the holding moves the ' +
      'portfolio more than its weight implies.',
    titreBarres: "Each holding's share of the fluctuations and of the value",
    uniteBarres: "% of the portfolio's variance, % of its value; gap in points",
    descriptionBarres: (nombre, ecarts) =>
      `Shares of the fluctuations compared with shares of the value, ${lignes(nombre, EN)}: ${ecarts}`,
    cleBarre: 'bar: share of the fluctuations',
    cleTrait: 'line: share of the value',
    legendeTableau:
      "Each holding's share of the fluctuations and of the value, then what it " +
      'contributed to the portfolio in each replayed crisis, in points: a point is ' +
      '1% of its value at the start of the crisis',
    colonnes: {
      ticker: 'Ticker',
      variance: 'Share of the fluctuations',
      capital: 'Share of the value',
      ecart: 'Gap',
    },
    nonCouverte: ' not covered',
    ensemble: 'What moves together',
    chapeauEnsemble:
      'Two holdings that rise and fall on the same days do little to cushion each ' +
      'other. Correlation measures this link, from \u22121 to +1.',
    correlationNonEstimable: 'Correlation not estimable, no reason published.',
    titreCarte: 'Correlation of daily changes',
    uniteCarte: 'correlation coefficient, no unit',
    descriptionCarte: (nombre) =>
      `Pairwise correlations of ${lignes(nombre, EN)}, value written in each cell.`,
    lectureEchelle:
      '+1: the two holdings always move in the same direction. 0: no visible link. ' +
      '\u22121: always in opposite directions. The closer the numbers get to +1, the ' +
      'less holding both dampens the fluctuations. The colors follow a fixed scale, the ' +
      'same for every portfolio.',
    diagonale: 'diagonal: each holding with itself, 1 by definition, off the scale',
  },
  crise: {
    introduction:
      "What would today's portfolio have lost in the great crises of the past? Each " +
      "crisis is replayed from today's amounts, with nothing bought or sold afterward.",
    regimeIndisponible: 'Regime comparison unavailable, no reason published.',
    legendeRegime: (indice) =>
      `Sensitivity to ${indice}, in ordinary times and in a crisis (never averaged)`,
    periodeDEstimation: 'estimation period',
    colonnes: { mesure: 'Measure', crise: 'Crisis' },
    lignesRegime: { beta: 'Beta', r2: 'R²', seances: 'Sessions', periode: 'Period' },
    auPointBas: 'At the market low',
    pireMoment: 'Worst point along the way',
    couverture: 'Coverage',
    couvertes: (couvertes, total) => `${lignes(couvertes, EN)} out of ${total}`,
    exclue: (poids) => `${pourcentage(poids, 1, EN)} of the value: `,
    seances: 'Sessions',
    poids: 'Weights',
    poidsFiges: (date) => `those of ${dateISOLiee(date)}, quantities frozen afterward`,
    reference: 'Benchmark',
  },
  moteur: {
    introduction:
      'What the tool takes from the previous sections. Findings, not advice: it ' +
      'describes your portfolio, it recommends nothing. When a sentence rests on a ' +
      'threshold, the threshold is shown; a threshold chosen by hand says so.',
  },
  graphiques: {
    partDeLaVariance: 'share of the variance',
    partDuCapital: 'share of the capital',
    ecartEnPoints: 'gap in points',
    infobulleContribution: (ticker, variance, capital, ecart) =>
      `${ticker}\nshare of the variance ${variance}\nshare of the capital ${capital}\ngap ${ecart}`,
    correlations: 'correlations',
    diagonale: 'diagonal',
    valeursDeLaDiagonale: 'values of the diagonal',
    valeurs: 'values',
    infobulleCorrelation: (ligne, colonne, valeur) => `${ligne} and ${colonne}\ncorrelation ${valeur}`,
    classe: (nombre, bas, haut) =>
      `${seances(nombre, EN)}\nfrom ${pourcentage(bas, 2, EN)} inclusive to ${pourcentage(haut, 2, EN)} exclusive`,
    queueDeLaCVaR: 'CVaR tail at 95%',
    queue: (niveau, nombre) => `tail at ${pourcentage(niveau, 0, EN)}:\n${seances(nombre, EN)}`,
    classesDeRendements: 'return bins',
    creuxMaximal: 'maximum drawdown',
    courbeDeValeur: 'value curve',
    pic: 'peak',
    creux: 'trough',
    valeursEnTableau: "The chart's values, as a table",
    tableauHistogramme: (largeur) =>
      `Sessions per ${pointsEnAdjectif(largeur, 2)} bin; a bin includes its lower bound, ` +
      'not its upper bound',
    tranche: 'Bin',
    seances: 'Sessions',
    trancheDe: (bas, haut) => `${pourcentage(bas, 2, EN)} to ${pourcentage(haut, 2, EN)}`,
    traitsDuGraphique: (traits, queue) => {
      const morceaux: string[] = []
      if (traits.length > 0) {
        const tete = traits.length === 1 ? 'Line on the chart' : 'Lines on the chart'
        const liste = traits.map(
          (trait) =>
            `VaR ${pourcentage(trait.niveau, 0, EN)} (${pourcentage(trait.varHistorique, 2, EN)}), ` +
            `at a return of ${pourcentage(trait.seuil, 2, EN)}`,
        )
        morceaux.push(`${tete}: ${liste.join('; ')}.`)
      }
      if (queue !== null) {
        morceaux.push(
          `Shaded area: the tail at ${pourcentage(queue.niveau, 0, EN)}, ${seances(queue.seances, EN)}.`,
        )
      }
      return morceaux.length === 0 ? null : morceaux.join(' ')
    },
    tableauCourbe: (titre) => `${titre}, session by session`,
    seance: 'Session',
    valeur: 'Value',
    repere: 'Marker',
    tableauCorrelation: 'Correlation of daily changes, pair by pair; the diagonal is 1 by definition',
  },
  analyse: {
    titre: (nom) => `Analysis of ${citer(nom)}`,
    vide: (nom) => `${citer(nom)} has no positions yet`,
    decritDesPositions: 'The analysis describes positions: this portfolio has none.',
    saisirOuImporter: 'Enter or import the positions',
    insuffisant: (nom) => `${citer(nom)} cannot be analyzed as it stands`,
    ditPourquoi:
      'Its positions are in the database, but the engine draws no analysis from them. ' +
      'It says why, and what to do:',
    revoirLesPositions: 'Review the positions',
    rechargerLAnalyse: 'Reload the analysis',
  },
  introuvable: {
    page: 'Page not found',
    aucunePage: 'No page at this address',
    adresse: (chemin) => `${citer(chemin)} matches no page of the application.`,
    voirLesPortefeuilles: 'See the portfolios',
    portefeuille: 'Portfolio not found',
    numero: (id) => `No portfolio has the number ${id}: it may have been deleted.`,
  },
  portefeuilles: {
    titre: 'Portfolios',
    aucun:
      'No portfolio in the database. The analysis describes a portfolio: first create ' +
      'one, then enter or import its positions.',
    creerUn: 'Create a portfolio',
    suiteDeLaCreation:
      'Its positions are entered line by line, or imported from a CSV file (a spreadsheet ' +
      'export, for example), on the page that opens when it is created.',
    colonnes: {
      nom: 'Portfolio',
      lignes: 'Holdings',
      valeur: 'Value',
      valorise: 'Valued as of',
      modifie: 'Positions changed on',
      actions: 'Actions',
    },
    jamais: 'never',
    positionsDe: 'Positions',
    deNom: (nom) => ` of ${citer(nom)}`,
    supprimer: 'Delete',
    nomCite: (nom) => ` ${citer(nom)}`,
    chacun: 'Each portfolio is analyzed separately. Its name opens its analysis.',
    legende: 'Portfolios in the database',
    supprime: (nom) => `Portfolio ${citer(nom)} deleted.`,
    nouveau: 'New portfolio',
    aucunePosition: 'No positions',
    nonValorise: (raison) => `Not valued: ${raison ?? 'reason not published.'}`,
    question: (nom, positions) =>
      `Delete ${citer(nom)}? ` +
      (positions === 0
        ? 'It has no positions.'
        : `Its ${lignes(positions, EN)} will be erased with it.`) +
      ' Deletion is permanent.',
    suppressionEnCours: 'Deleting…',
    supprimerDefinitivement: 'Delete permanently',
    annuler: 'Cancel',
    nomVide: 'The name is empty: the portfolio needs one to be recognized.',
    cree: (nom) => `Portfolio ${citer(nom)} created.`,
    nom: 'Name',
    aideNom: 'At most 120 characters. It appears in the banner of the analysis.',
    creationEnCours: 'Creating…',
    creer: 'Create the portfolio',
  },
  positions: {
    titre: (nom) => `Positions of ${citer(nom)}`,
    aucune: (nom) =>
      `${citer(nom)} has no positions yet. Enter them below, one line per security, or import a file.`,
    tableauEstLePortefeuille:
      'The table is the portfolio: saving it replaces all its positions with the lines shown.',
    saisir: 'Enter the positions',
    legende: (nom) => `Positions of ${citer(nom)}, one line per security`,
    aide:
      'The cost basis is optional: no risk measure uses it. “History since” is the ' +
      "security's first price session in the database; a recently listed holding " +
      'shortens the window of the whole analysis.',
    universIllisible: (detail) =>
      `The security names could not be read (${detail}). Entry remains possible: each ` +
      'ticker is checked on saving.',
    ajouter: 'Add a line',
    rienEnregistre: 'Nothing was saved: ',
    aCorriger: (nombre) => `${lignesDeFichier(nombre)} to correct.`,
    saisieRefusee: 'the entry is rejected.',
    enregistrementEnCours: 'Saving…',
    enregistrer: 'Save the positions',
    nonEnregistrees: 'Unsaved changes.',
    importer: 'Import a CSV file',
    enregistrees: (date, positions) =>
      `Positions saved on ${dateEnToutesLettres(date, EN)}: ${lignes(positions, EN)}.`,
    importe: (fichier, positions) =>
      `Portfolio imported from ${citer(fichier ?? 'the file')}: ${lignes(positions, EN)}.`,
    quitterLesPerd: 'The changes to the table are not saved. Leaving this page loses them.',
    rester: 'Stay on the page',
    quitter: 'Leave without saving',
  },
  saisie: {
    ticker: 'Ticker',
    nom: 'Name',
    historique: 'History since',
    quantite: 'Quantity',
    prix: (devise) => `Cost basis (${devise}), optional`,
    numero: 'No.',
    retirer: 'Remove',
    ligne: 'line ',
    retirerLaLigne: (numero) => ` line ${numero}`,
    titreInconnu: 'Unknown security',
    ligneDeRefus: (ligne, message) => `Line ${ligne}: ${message}`,
    quantiteManquante: 'Quantity missing.',
    quantiteIllisible: (saisi) =>
      `${citer(saisi)} is not a readable quantity. Enter, for example, 40 or 12.5.`,
    prixIllisible: (saisi) =>
      `${citer(saisi)} is not a readable cost basis. Enter, for example, 185.20, or leave it empty.`,
  },
  csv: {
    deposer: 'Drop a CSV file here, or choose it:',
    fichierCsv: 'CSV file',
    fichierChoisi: (nom, octets) => `${nom}, ${compte(octets, 'byte', undefined, EN)}`,
    donne: (nom) => `The import gives ${citer(nom)}, still empty, the positions in the file.`,
    remplace: (positions, nom) =>
      `The import replaces the current ${lignes(positions, EN)} of ${citer(nom)} with those in the file.`,
    modificationsPerdues: ' The unsaved changes to the table will be lost.',
    importEnCours: 'Importing…',
    importer: 'Import the portfolio',
    lu: 'Read from the file:',
    fichier: 'File',
    sansNom: 'unnamed',
    encodage: 'Encoding',
    separateur: 'Separator',
    decimale: 'Decimal separator',
    lignesLues: 'Lines read',
    lignes: (nombre) => lignesDeFichier(nombre),
    format: 'File format',
    formatIllisible: 'The format could not be read: ',
    exemple: 'For example, as a spreadsheet saves it:',
    enTete: 'One header line, then one line per security. Required columns: ',
    facultative: '; optional: ',
    sansEffet: ' (the cost basis, with no effect on the analysis)',
    separateurEt: (separateur, decimales) =>
      `Separator ${citer(separateur)}: decimal separator ${decimales.map((d) => citer(d)).join(' or ')}.`,
    espaces: 'Thousands separators accepted: ',
    encodages: 'Encoding: ',
    auPlus: (octets, positions) =>
      `At most ${compte(octets, 'byte', undefined, EN)} and ${lignes(positions, EN)}.`,
    remplaceTout: 'The import replaces all the positions in the portfolio.',
    nomsEncodages: {
      'utf-8': 'UTF-8',
      'utf-8-sig': 'UTF-8 with byte order mark (BOM)',
      cp1252: 'Windows-1252 (CP1252)',
    },
    nomsDecimales: {
      ',': citer(','),
      '.': citer('.'),
      mixte: 'mixed: commas and dots in the same file',
      aucune: 'none: all numbers are whole',
    },
    nomsEspaces: {
      ' ': 'ordinary space',
      '\u00a0': 'non-breaking space',
      '\u202f': 'narrow non-breaking space',
    },
  },
}
