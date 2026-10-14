/**
 * Les libellés existent dans les deux langues, et pas à moitié (chantier 7D).
 *
 * TypeScript refuse déjà une clé manquante. Ce test ajoute ce que le typage ne
 * voit pas : une chaîne anglaise identique à la française est une traduction
 * oubliée, hors d'une liste déclarée ; chaque libellé à paramètres est EXERCÉ
 * dans les deux langues, sur un cas, et une fonction sans cas échoue ; chaque
 * texte anglais suit les règles de l'anglais (aucune espace avant « : »,
 * guillemets doubles, aucune contraction, aucun mot français, rien de
 * prescriptif), et cite les mêmes nombres que le français.
 */
import { describe, expect, it } from 'vitest'

import { LIBELLES, type Libelles } from './libelles'

/** Les chaînes et les fonctions d'un objet de libellés, par chemin. */
function feuilles(objet: unknown, chemin = ''): Map<string, unknown> {
  const trouvees = new Map<string, unknown>()
  if (typeof objet === 'string' || typeof objet === 'function') {
    trouvees.set(chemin, objet)
  } else if (Array.isArray(objet)) {
    objet.forEach((valeur, rang) => {
      for (const [c, v] of feuilles(valeur, `${chemin}[${rang}]`)) trouvees.set(c, v)
    })
  } else if (typeof objet === 'object' && objet !== null) {
    for (const [cle, valeur] of Object.entries(objet)) {
      for (const [c, v] of feuilles(valeur, chemin === '' ? cle : `${chemin}.${cle}`)) {
        trouvees.set(c, v)
      }
    }
  }
  return trouvees
}

/**
 * Chaque libellé à paramètres, appelé sur un cas : un nom avec un accent, une
 * date, des nombres au-delà de mille pour voir les milliers.
 */
function appels(l: Libelles): Record<string, string> {
  return {
    'api.erreurDuClient': l.api.erreurDuClient('TypeError: x'),
    'api.reponseInattendue': l.api.reponseInattendue(409),
    'demo.fichierIllisible': l.demo.fichierIllisible('fr/portfolios.json'),
    'demo.mention': l.demo.mention(3, '2026-09-09'),
    'presentation.tableau.legende': l.presentation.tableau.legende('2026-09-09'),
    'presentation.resultat.titreDuBloc': l.presentation.resultat.titreDuBloc('Krach', 'Démo'),
    'theme.vers': l.theme.vers(l.theme.sombre),
    'theme.commeLeSysteme': l.theme.commeLeSysteme(l.theme.sombre),
    'theme.fige': l.theme.fige(l.theme.clair),
    'theme.nomAccessible': l.theme.nomAccessible('A', 'B'),
    'provenance.controleIndisponible': l.provenance.controleIndisponible('Raison.'),
    'provenance.controleDe': l.provenance.controleDe('Monte Carlo'),
    'portefeuille.colonnes.prix': l.portefeuille.colonnes.prix('USD'),
    'portefeuille.colonnes.valeur': l.portefeuille.colonnes.valeur('USD'),
    'jourOrdinaire.varHistorique': l.jourOrdinaire.varHistorique('95'),
    'jourOrdinaire.uniteHistogramme': l.jourOrdinaire.uniteHistogramme(0.0025),
    'jourOrdinaire.varNormale': l.jourOrdinaire.varNormale('95'),
    'jourOrdinaire.varStudent': l.jourOrdinaire.varStudent('95'),
    'jourOrdinaire.cvar': l.jourOrdinaire.cvar('95'),
    'auPire.titre': l.auPire.titre('USD', '2024-09-23'),
    'auPire.unite': l.auPire.unite('2024-09-23'),
    'auPire.description': l.auPire.description('2024-09-23', 1.23, '2026-09-25', -0.148, '2025-02-19', '2025-04-08'),
    'risque.descriptionBarres': l.risque.descriptionBarres(6, 'JPM +8'),
    'risque.descriptionCarte': l.risque.descriptionCarte(6),
    'crise.legendeRegime': l.crise.legendeRegime('SPY'),
    'crise.couvertes': l.crise.couvertes(4, 6),
    'crise.exclue': l.crise.exclue(0.123),
    'crise.poidsFiges': l.crise.poidsFiges('2026-09-25'),
    'graphiques.infobulleContribution': l.graphiques.infobulleContribution('JPM', 'a', 'b', 'c'),
    'graphiques.infobulleCorrelation': l.graphiques.infobulleCorrelation('JNJ', 'KO', '0'),
    'graphiques.classe': l.graphiques.classe(1234, -0.01, -0.0075),
    'graphiques.queue': l.graphiques.queue(0.95, 26),
    'graphiques.tableauHistogramme': l.graphiques.tableauHistogramme(0.0025),
    'graphiques.trancheDe': l.graphiques.trancheDe(-0.06, -0.0575),
    'graphiques.traitsDuGraphique':
      l.graphiques.traitsDuGraphique(
        [
          { niveau: 0.95, varHistorique: 0.0106, seuil: -0.0106 },
          { niveau: 0.99, varHistorique: 0.0169, seuil: -0.0169 },
        ],
        { niveau: 0.95, seances: 1234 },
      ) ?? '',
    'graphiques.tableauCourbe': l.graphiques.tableauCourbe('Démo'),
    'analyse.titre': l.analyse.titre('Démo'),
    'analyse.vide': l.analyse.vide('Démo'),
    'analyse.insuffisant': l.analyse.insuffisant('Démo'),
    'introuvable.adresse': l.introuvable.adresse('/rien'),
    'introuvable.numero': l.introuvable.numero(7),
    'portefeuilles.deNom': l.portefeuilles.deNom('Démo'),
    'portefeuilles.nomCite': l.portefeuilles.nomCite('Démo'),
    'portefeuilles.supprime': l.portefeuilles.supprime('Démo'),
    'portefeuilles.nonValorise': l.portefeuilles.nonValorise(null),
    'portefeuilles.question': `${l.portefeuilles.question('Démo', 0)} ${l.portefeuilles.question('Démo', 1200)}`,
    'portefeuilles.cree': l.portefeuilles.cree('Démo'),
    'positions.titre': l.positions.titre('Démo'),
    'positions.aucune': l.positions.aucune('Démo'),
    'positions.legende': l.positions.legende('Démo'),
    'positions.universIllisible': l.positions.universIllisible('API'),
    'positions.aCorriger': l.positions.aCorriger(2),
    'positions.enregistrees': l.positions.enregistrees('2026-10-01', 6),
    'positions.importe': `${l.positions.importe('p.csv', 6)} ${l.positions.importe(null, 6)}`,
    'saisi.resume': l.saisi.resume(6, '2026-10-14'),
    'saisi.question': l.saisi.question(6),
    'positionsDuSite.gardees': l.positionsDuSite.gardees('2026-10-14', 6),
    'positionsDuSite.universIllisible': l.positionsDuSite.universIllisible('API'),
    'saisie.prix': l.saisie.prix('USD'),
    'saisie.retirerLaLigne': l.saisie.retirerLaLigne(4),
    'saisie.ligneDeRefus': l.saisie.ligneDeRefus(4, 'x'),
    'saisie.quantiteIllisible': l.saisie.quantiteIllisible('dix'),
    'saisie.prixIllisible': l.saisie.prixIllisible('cher'),
    'csv.fichierChoisi': l.csv.fichierChoisi('p.csv', 2048),
    'csv.donne': l.csv.donne('Démo'),
    'csv.remplace': l.csv.remplace(6, 'Démo'),
    'csv.lignes': l.csv.lignes(6),
    'csv.separateurEt': l.csv.separateurEt(';', [',', '.']),
    'csv.auPlus': l.csv.auPlus(1_000_000, 200),
  }
}

/** Les textes d'une langue : chaque chaîne, puis chaque fonction sur son cas. */
function textes(langue: 'fr' | 'en'): Map<string, string> {
  const libelles = LIBELLES[langue]
  const sortie = new Map<string, string>()
  for (const [chemin, valeur] of feuilles(libelles)) {
    if (typeof valeur === 'string') sortie.set(chemin, valeur)
  }
  for (const [chemin, texte] of Object.entries(appels(libelles))) sortie.set(chemin, texte)
  return sortie
}

/**
 * Identiques dans les deux langues, et c'est juste : des noms propres, des
 * codes, des mots que l'anglais écrit comme le français.
 */
const IDENTIQUES = new Set([
  'navigation.etiquettePages',
  'portefeuille.colonnes.ticker',
  'portefeuille.total',
  'risque.colonnes.ticker',
  'crise.lignesRegime.r2',
  'portefeuilles.colonnes.actions',
  'portefeuilles.positionsDe',
  'saisie.ticker',
  'csv.nomsEncodages.utf-8',
  'csv.nomsEncodages.cp1252',
])

describe('les libellés, dans les deux langues', () => {
  it('ont les mêmes clés, et chaque fonction a un cas', () => {
    const fr = feuilles(LIBELLES.fr)
    const en = feuilles(LIBELLES.en)
    expect([...en.keys()].sort()).toEqual([...fr.keys()].sort())
    const fonctions = [...fr].filter(([, v]) => typeof v === 'function').map(([c]) => c)
    expect(fonctions.sort()).toEqual(Object.keys(appels(LIBELLES.fr)).sort())
  })

  it('aucune traduction oubliée : l’anglais diffère du français, hors liste déclarée', () => {
    const fr = textes('fr')
    const en = textes('en')
    const oubliees = [...fr].filter(([c, t]) => en.get(c) === t && !IDENTIQUES.has(c)).map(([c]) => c)
    expect(oubliees).toEqual([])
    // La liste ne cache rien : chacun de ses chemins est bien identique.
    for (const chemin of IDENTIQUES) expect(en.get(chemin), chemin).toBe(fr.get(chemin))
  })

  it('les mêmes nombres des deux côtés', () => {
    const nombres = (texte: string, langue: 'fr' | 'en') =>
      [...texte.replaceAll('\u2060', '').matchAll(langue === 'fr' ? /\d+(?:[\u202f\u00a0]\d{3})*(?:,\d+)?/g : /\d+(?:,\d{3})*(?:\.\d+)?/g)]
        .map((m) => (langue === 'fr' ? m[0].replace(/[\u202f\u00a0]/g, '').replace(',', '.') : m[0].replaceAll(',', '')))
        .sort()
    const fr = textes('fr')
    const en = textes('en')
    const ecarts = [...fr].filter(([c, t]) => {
      const anglais = en.get(c)
      return anglais !== undefined && nombres(anglais, 'en').join(' ') !== nombres(t, 'fr').join(' ')
    })
    expect(ecarts.map(([c]) => c)).toEqual([])
  })
})

// ════════════════════════════════════════ Les règles de l'anglais ══

/** Une espace, quelle qu'elle soit, avant une ponctuation haute suivie d'un blanc ou de la fin. */
const ESPACE_AVANT_PONCTUATION = /\s[:;?!](?=\s|$)/
const GUILLEMET_FRANCAIS = /[«»]/
const CADRATIN = /\u2014/
const ACCENT_FRANCAIS = /[àâçéèêëîïôùûüÿœæ]/i
const MOT_FRANCAIS =
  /\b(le|la|les|des|du|une|est|sont|sur|pour|avec|sans|aucun|aucune|séances?|portefeuilles?|jours? de bourse)\b/i
const CONTRACTION = /\b\w+n't\b|\b(it|that|there|what|here)'s\b|'(re|ll|ve|d)\b/i
const PRESCRIPTIF =
  /\b(should|shall|must|ought|needs? to|needed to|ha(ve|s|d) to|recommend\w*|advis\w*|suggest\w*|consider(s|ed|ing)?|reduc\w*|trim\w*|lighten\w*|sell(s|ing)?|buy(s|ing)?|purchas\w*|strengthen\w*|favou?r\w*|prefer\w*|avoid\w*|rebalanc\w*|diversif(y|ies|ying))\b/i

/**
 * Ce que la garde prescriptive lit comme une consigne et qui n'en est pas
 * une : l'introduction de la section 6 dit que l'outil NE recommande rien,
 * comme l'écran d'acceptation dit « not advice » ; la phrase sous le bouton
 * d'acceptation dit la condition d'un bouton (« The box must be checked »,
 * au glossaire), pas une consigne sur le portefeuille.
 */
const NON_PRESCRIPTIFS = new Set([
  'moteur.introduction',
  ...['analyse', 'positions', 'portefeuilles', 'methodologie', 'page'].map(
    (destination) => `acceptation.condition.${destination}`,
  ),
])

/**
 * Les noms propres que l'anglais écrit comme le français : le portefeuille
 * « Démo » des exemples, et l'école de l'auteur, qui garde son vrai nom
 * dans la ligne de l'auteur (DESIGN.md §19.10). Ces noms déclarés, et eux
 * seuls, sont retirés avant le contrôle des accents.
 */
const NOMS_PROPRES = ['Démo', 'HEC Montréal']

function fautesAnglaises(chemin: string, texte: string): string[] {
  const fautes: string[] = []
  if (ESPACE_AVANT_PONCTUATION.test(texte)) fautes.push('espace avant la ponctuation')
  if (GUILLEMET_FRANCAIS.test(texte)) fautes.push('guillemet français')
  if (CADRATIN.test(texte)) fautes.push('tiret cadratin')
  const sansNomsPropres = NOMS_PROPRES.reduce((reste, nom) => reste.replaceAll(nom, ''), texte)
  if (ACCENT_FRANCAIS.test(sansNomsPropres)) fautes.push('accent français')
  if (MOT_FRANCAIS.test(texte)) fautes.push('mot français')
  if (CONTRACTION.test(texte)) fautes.push('contraction')
  if (!NON_PRESCRIPTIFS.has(chemin) && PRESCRIPTIF.test(texte)) fautes.push('prescriptif')
  if (/score/i.test(texte)) fautes.push('note globale')
  return fautes.map((faute) => `${chemin} : ${faute} : ${texte.slice(0, 60)}`)
}

describe('les libellés anglais', () => {
  it('suivent les règles de l’anglais', () => {
    const fautes = [...textes('en')].flatMap(([chemin, texte]) => fautesAnglaises(chemin, texte))
    expect(fautes).toEqual([])
  })

  it('la garde voit ce qu’elle doit voir', () => {
    expect(fautesAnglaises('x', 'Threshold : 0.70')).not.toEqual([])
    expect(fautesAnglaises('x', '« Démo »')).not.toEqual([])
    expect(fautesAnglaises('x', 'It isn’t'.replace('’', "'"))).not.toEqual([])
    expect(fautesAnglaises('x', 'les positions')).not.toEqual([])
    expect(fautesAnglaises('x', 'You should sell JPM.')).not.toEqual([])
    expect(fautesAnglaises('moteur.introduction', 'it recommends nothing')).toEqual([])
    expect(fautesAnglaises('x', "The security's code: “Démo”.")).toEqual([])
  })

  it('ne laisse passer que les noms propres déclarés : l’école, pas la ville ni un mot français', () => {
    expect(fautesAnglaises('x', 'A student at HEC Montréal')).toEqual([])
    expect(fautesAnglaises('x', 'A student in Montréal')).not.toEqual([])
    expect(fautesAnglaises('x', 'A student at the école')).not.toEqual([])
    expect(fautesAnglaises('x', 'HEC Montréal, à côté')).not.toEqual([])
  })

  it('« Bêta » en français, « Beta » en anglais', () => {
    expect(LIBELLES.fr.crise.lignesRegime.beta).toBe('Bêta')
    expect(LIBELLES.en.crise.lignesRegime.beta).toBe('Beta')
  })
})
