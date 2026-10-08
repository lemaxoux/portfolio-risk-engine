"""Les textes du serveur existent dans les deux langues, et pas à moitié.

`backend/textes/fr/` et `backend/textes/en/` exposent les mêmes domaines, les
mêmes noms, avec les mêmes signatures (chantier 7D). C'est ce qui rend la
complétude vérifiable : une phrase oubliée en anglais fait échouer ce test,
même si aucune réponse de test ne la déclenche.

Chaque fonction de texte est EXERCÉE dans les deux langues, sur un catalogue de
cas qui couvre ses variantes (`CAS`) : une fonction sans cas échoue. Chaque
sortie, publiée comme l'API la publie (`typography.prose`), passe les gardes de
sa langue ; une sortie anglaise identique à la française est une traduction
oubliée, et une sortie anglaise qui n'a pas les nombres de la française une
traduction qui dit autre chose. Chaque chaîne du code des deux langues est lue
en plus : un cas oublié ne cache pas une chaîne. Les noms et les descriptions
anglaises du catalogue des crises sont lus de même.

Seule la provenance d'une mesure — sa méthode, son détail, écrits en IBM Plex
Sans — cite des lettres grecques (« λ=0,94 », « ν = 4,07 », « μ = 0 »). Un
seuil cite aussi les siennes dans son nom ou sa justification (« ν maximal
d'une loi de Student », « n·(1 − α) ») : l'anglais a celles du français, et
seulement celles-là.
"""

from __future__ import annotations

import ast
import inspect
import pkgutil
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from backend.api.csv_import import EN_TETE_ATTENDU
from backend.risk_engine.scenarios import SCENARIOS
from backend.rules import thresholds
from backend.rules.rules import RuleId
from backend.rules.thresholds import (
    MIN_ESTIMABLE_SAMPLE,
    MIN_REGRESSION_SAMPLE,
    MIN_SCENARIO_COVERAGE,
    STRONG_CORRELATION,
    Threshold,
    ThresholdRole,
)
from backend.textes import en, fr
from backend.typography import prose

from .gardes_texte import (
    CADRATIN,
    FRANCAIS,
    GREC,
    PONCTUATION_EN,
    PRESCRIPTIONS,
    fautes_de_forme,
    fautes_de_francais,
    fautes_de_registre,
    nombres,
)

LANGUES = {"fr": fr, "en": en}

# Les domaines dont le registre n'est pas celui d'un constat : l'écran
# d'acceptation dit à bon droit ce que l'outil n'est pas (« pas un conseil »,
# « acheter, de vendre ou de conserver un titre »). La garde prescriptive ne le
# lit pas, aujourd'hui non plus.
REGISTRE_EXEMPTE = {"bandeau"}

# Ce que la garde prescriptive lit comme une consigne et qui n'en est pas une,
# déclaré : dans la justification française du minimum d'une VaR historique,
# écrite avant le chantier, « se réduirait » est le verbe d'une définition (la
# CVaR se ramène au même minimum), pas le conseil de réduire une ligne.
NON_PRESCRIPTIFS = ("se réduirait au même minimum",)

# Le nom et la justification d'un seuil gardent ses formules : celles de sa
# déclaration française (`test_un_seuil_dit_les_memes_nombres_…`).
FORMULES_DES_SEUILS = {("seuils", "nom"), ("seuils", "justification"), ("seuils", "ligne")}


def est_provenance(nom: str) -> bool:
    """La méthode ou le détail d'une mesure : s'affiche en IBM Plex Sans, qui
    a le grec."""
    return nom.startswith(("METHODE_", "methode_", "detail_"))


def grec_admis(domaine: str, nom: str) -> bool:
    return est_provenance(nom) or (domaine, nom) in FORMULES_DES_SEUILS


# Chaque seuil que déclare `rules/thresholds.py` : ses constantes, et ce que
# fabriquent ses fonctions sur des paramètres d'exemple.
SEUILS: list[Threshold] = [
    *(valeur for valeur in vars(thresholds).values() if isinstance(valeur, Threshold)),
    thresholds.historical_var_sample(0.95),
    thresholds.historical_var_sample(0.99),
    thresholds.capital_share("JPM", 0.256),
    thresholds.capital_share("B", 0.25),
    thresholds.most_correlated_pair("JNJ", "KO", 0.42),
]


# Les cas de chaque fonction : chacun reçoit le module de texte et la langue,
# et rend les arguments. Un argument qui est lui-même un texte rédigé (une
# durée, un nom de crise, un bêta écrit) se rédige dans la langue du cas.
Cas = Callable[[ModuleType, str], tuple]
D1, D2 = date(2024, 9, 23), date(2026, 9, 25)
CRISE = SCENARIOS[0]


def _regime(t: ModuleType, langue: str, mince: bool, part: float | None, perte: bool) -> tuple:
    beta_crise = t.beta_regresse(1.07, 0.03, 0.98, 23, 60 if mince else None)
    beta_calme = t.beta_regresse(0.57, 0.03, 0.49, 504, None)
    return (
        CRISE.nom(langue), -0.44 if perte else 0.05, "SPY", -0.552, None if mince else 0.72,
        beta_crise, beta_calme, 0.49, 0.98, 0.49, mince, -0.366, -0.074, part, perte,
    )


def _periode(langue: str, annees: int = 2) -> str:
    """« ces deux dernières années », « the past two years »."""
    return LANGUES[langue].moteur.periode_en_annees(annees)


def _fenetre(langue: str, observations: int = 504, demandees: int | None = None) -> str:
    return LANGUES[langue].moteur.fenetre(observations, D1, D2, demandees)


def _crises(langue: str, *rangs: int) -> list[str]:
    """Les crises du catalogue, avec leur article : « la Crise financière
    2008 », « the 2008 Financial Crisis »."""
    return [SCENARIOS[rang].avec_article(langue) for rang in rangs]


CAS: dict[tuple[str, str], list[Cas]] = {
    ("bandeau", "duree_en_annees"): [lambda t, l: (1,), lambda t, l: (2,), lambda t, l: (11,)],
    ("bandeau", "duree_en_mois"): [lambda t, l: (1,), lambda t, l: (6,), lambda t, l: (14,)],
    ("bandeau", "sections"): [
        lambda t, l: (504, t.duree_en_annees(2)),
        lambda t, l: (60, t.duree_en_mois(3)),
        lambda t, l: (2520, t.duree_en_annees(10)),
    ],
    ("moteur", "periode_en_annees"): [lambda t, l: (1,), lambda t, l: (2,), lambda t, l: (11,)],
    ("moteur", "periode_en_mois"): [lambda t, l: (1,), lambda t, l: (3,), lambda t, l: (14,)],
    ("moteur", "periode_en_jours"): [lambda t, l: (1,), lambda t, l: (7,), lambda t, l: (20,)],
    ("moteur", "fenetre"): [
        lambda t, l: (504, D1, D2, None),
        lambda t, l: (40, D1, D2, 504),
        lambda t, l: (1, D2, D2, 504),
    ],
    ("moteur", "jours_de_bourse"): [lambda t, l: (0,), lambda t, l: (1,), lambda t, l: (7,)],
    ("moteur", "methode_ewma"): [lambda t, l: (0.94,)],
    ("moteur", "detail_historique"): [lambda t, l: ("lower",)],
    ("moteur", "detail_normale"): [lambda t, l: (False,), lambda t, l: (True,)],
    ("moteur", "detail_monte_carlo"): [lambda t, l: (100000, 20260910)],
    ("moteur", "detail_student"): [lambda t, l: (4.07, 504)],
    ("moteur", "detail_student_monte_carlo"): [lambda t, l: (4.07, 504, 100000, 20260910)],
    ("moteur", "estimation_mince"): [lambda t, l: (7, 30), lambda t, l: (1, 30)],
    ("moteur", "moyenne_de_la_queue"): [lambda t, l: (6, 504, 1 / 6), lambda t, l: (2, 1000, 0.5)],
    ("moteur", "refus_non_estimable"): [
        lambda t, l: (2, "correlation", 3),
        lambda t, l: (1, "beta", 3),
        lambda t, l: (2, "contributions", 3),
    ],
    ("moteur", "refus_queue_vide"): [
        lambda t, l: (7, 0.05, 20),
        lambda t, l: (60, 0.01, 100),
        lambda t, l: (1, 0.05, 20),
    ],
    ("moteur", "student_proche_de_la_normale"): [lambda t, l: (60,), lambda t, l: (504,)],
    ("moteur", "monte_carlo_fenetre_trop_courte"): [lambda t, l: (4, 6), lambda t, l: (1, 2)],
    ("moteur", "student_trop_peu_de_jours"): [lambda t, l: (30, 25)],
    ("moteur", "student_sans_variance_finie"): [lambda t, l: (504, 1.9)],
    ("moteur", "crise_avec_article"): [
        lambda t, l: (CRISE.nom(l), "la" if l == "fr" else "the"),
        lambda t, l: ("Choc bref", None),
    ],
    ("moteur", "du_sommet_au_point_bas"): [
        lambda t, l: (date(2007, 10, 9), date(2009, 3, 9)),
        lambda t, l: (date(2020, 1, 1), date(2020, 3, 1)),
    ],
    ("moteur", "exclusion_cotee_depuis"): [lambda t, l: (date(2009, 1, 1),), lambda t, l: (date(2021, 5, 12),)],
    ("moteur", "exclusion_plus_cotee"): [lambda t, l: (date(2021, 5, 12),)],
    ("moteur", "couverture"): [
        lambda t, l: (6, 6, None, ()),
        lambda t, l: (4, 6, 0.734, ("AAA", "BBB")),
        lambda t, l: (1, 2, 0.5, ("ZZZ",)),
    ],
    ("moteur", "ensemble_non_rejoue"): [lambda t, l: (True,), lambda t, l: (False,)],
    ("moteur", "resume_scenario_non_calculable"): [lambda t, l: (CRISE.nom(l), t.AUCUNE_LIGNE_COTEE)],
    ("moteur", "resume_scenario"): [
        lambda t, l: (CRISE.nom(l), -0.44, -0.477, 356, None, True),
        lambda t, l: (CRISE.nom(l), 0.05, -0.02, 24, 0.73, False),
        lambda t, l: (CRISE.nom(l), -0.1, -0.13, 196, 0.8, True),
    ],
    ("moteur", "beta_regresse"): [
        lambda t, l: (0.96, 0.02, 0.86, 355, None),
        lambda t, l: (1.07, 0.03, 0.98, 23, 60),
        lambda t, l: (2.5, None, 1.0, 2, 60),
    ],
    ("moteur", "pas_de_cours_de_l_indice"): [
        lambda t, l: ("SPY", t.NOMS_D_INDICE["SPY"][0]),
        lambda t, l: ("QQQ", None),
    ],
    ("moteur", "jours_communs_seulement"): [lambda t, l: (1,), lambda t, l: (3,)],
    ("moteur", "resume_regime_impossible"): [lambda t, l: (CRISE.nom(l), t.AUCUNE_LIGNE_COTEE)],
    ("moteur", "resume_regime"): [
        lambda t, l: _regime(t, l, mince=False, part=None, perte=True),
        lambda t, l: _regime(t, l, mince=True, part=0.73, perte=True),
        lambda t, l: _regime(t, l, mince=False, part=0.9, perte=False),
    ],
    ("moteur", "portefeuille_introuvable"): [lambda t, l: (999,)],
    ("moteur", "portefeuille_sans_position"): [lambda t, l: (3,)],
    ("moteur", "prix_absents"): [lambda t, l: (["XYZ"],), lambda t, l: (["ABC", "XYZ"],)],
    ("moteur", "valeur_totale_non_positive"): [lambda t, l: (0.0,), lambda t, l: (-1234.5,)],
    ("moteur", "prix_absents_sur_la_periode"): [lambda t, l: (["XYZ"],)],
    ("moteur", "prix_absents_du_panel"): [lambda t, l: (["SPY"], "SPY"), lambda t, l: (["XYZ"], None)],
    ("moteur", "seances_communes_insuffisantes"): [lambda t, l: (2, 3, 2)],
    # ── Les règles : chaque variante que décide `rules/rules.py`.
    ("regles", "libelle"): [lambda t, l, regle=regle: (regle,) for regle in RuleId],
    ("regles", "rendu"): [
        lambda t, l: (
            t.libelle(RuleId.APPARENT_DIVERSIFICATION), t.PORTEFEUILLE,
            t.montants_egaux(6), [(STRONG_CORRELATION.etiquette(l), STRONG_CORRELATION.ligne(l))],
            t.provenance_fenetre(_fenetre(l)),
        ),
        lambda t, l: (
            t.libelle(RuleId.EFFECTIVE_CONCENTRATION), t.PORTEFEUILLE,
            t.LIGNE_UNIQUE, [], t.provenance_concentration(D2, _fenetre(l)),
        ),
    ],
    ("regles", "mention_mince"): [
        lambda t, l: (23, MIN_REGRESSION_SAMPLE.affiche(l)),
        lambda t, l: (3, MIN_REGRESSION_SAMPLE.affiche(l)),
    ],
    ("regles", "refus"): [
        *(
            lambda t, l, mesure=mesure: (2, mesure, MIN_ESTIMABLE_SAMPLE.affiche(l))
            for mesure in ("calcul", "parts", "correlation", "part_du_marche")
        ),
        lambda t, l: (1, "calcul", MIN_ESTIMABLE_SAMPLE.affiche(l)),
    ],
    ("regles", "provenance_concentration"): [
        lambda t, l: (D2, _fenetre(l)),
        lambda t, l: (D2, _fenetre(l, 40, 504)),
    ],
    ("regles", "provenance_fenetre"): [lambda t, l: (_fenetre(l),), lambda t, l: (_fenetre(l, 2, 504),)],
    ("regles", "capital_seul"): [lambda t, l: (6, 5.65), lambda t, l: (2, 1.0)],
    ("regles", "concentration"): [
        lambda t, l, repartition=repartition: (6, 5.65, 4.4, repartition, _periode(l))
        for repartition in ("plus_concentre", "mieux_reparti", "pareil")
    ],
    ("regles", "montants_egaux"): [lambda t, l: (6,), lambda t, l: (2,)],
    ("regles", "contribution_negative"): [lambda t, l: (4.4, _periode(l))],
    ("regles", "contribution"): [
        lambda t, l: ("JPM", thresholds.capital_share("JPM", 0.256).affiche(l), 0.354, 0.098, "plus", _periode(l)),
        lambda t, l: ("KO", thresholds.capital_share("KO", 0.126).affiche(l), 0.053, -0.073, "moins", _periode(l)),
        lambda t, l: ("MSFT", thresholds.capital_share("MSFT", 0.148).affiche(l), 0.154, 0.006, "plus", _periode(l)),
        lambda t, l: ("B", thresholds.capital_share("B", 0.45).affiche(l), 0.45, 0.0, "egale", _periode(l)),
        lambda t, l: ("C", thresholds.capital_share("C", 0.15).affiche(l), -0.05, -0.2, "compense", _periode(l)),
    ],
    ("regles", "parcours_d_une_crise"): [
        lambda t, l: ("JPM", CRISE.nom(l), -0.166),
        lambda t, l: ("XOM", CRISE.nom(l), 0.094),
        lambda t, l: ("KO", CRISE.nom(l), -0.01),
        lambda t, l: ("KO", CRISE.nom(l), 0.0),
    ],
    ("regles", "parcours_des_crises"): [
        lambda t, l: ("XOM", "deux_sens", (SCENARIOS[1].nom(l), -0.076), (SCENARIOS[2].nom(l), 0.094)),
        lambda t, l: ("JPM", "cout", (SCENARIOS[0].nom(l), -0.166), (SCENARIOS[2].nom(l), -0.087)),
        lambda t, l: ("XOM", "gain", (SCENARIOS[1].nom(l), 0.004), (SCENARIOS[2].nom(l), 0.094)),
    ],
    ("regles", "paire_forte"): [
        lambda t, l: (_periode(l), "A", "B", 0.85),
        lambda t, l: (LANGUES[l].moteur.periode_en_jours(7), "AAPL", "MSFT", 0.7),
    ],
    ("regles", "aucune_paire_forte"): [
        lambda t, l: (
            _periode(l), STRONG_CORRELATION.affiche(l), "JNJ", "KO",
            thresholds.most_correlated_pair("JNJ", "KO", 0.42).affiche(l),
        ),
    ],
    ("regles", "part_systematique"): [
        lambda t, l: (_periode(l), 0.49, 0.51, "SPY", LANGUES[l].moteur.NOMS_D_INDICE["SPY"][0]),
        lambda t, l: (LANGUES[l].moteur.periode_en_mois(3), 0.3, 0.7, "QQQ", None),
    ],
    ("regles", "evolution_sans_crise"): [lambda t, l: (0.49, _periode(l))],
    ("regles", "evolution"): [
        lambda t, l: (0.49, _periode(l), list(zip((0.86,), _crises(l, 0)))),
        lambda t, l: (0.49, _periode(l), list(zip((0.86, 0.79), _crises(l, 0, 2)))),
        lambda t, l: (0.49, _periode(l), list(zip((0.86, 0.98, 0.79), _crises(l, 0, 1, 2)))),
    ],
    ("regles", "evolution_par_crise"): [
        lambda t, l: ([
            (0.45, _periode(l), 0.86, _crises(l, 0)[0]),
            (0.5, None, 0.79, _crises(l, 2)[0]),
        ],),
        lambda t, l: ([
            (0.45, _periode(l), 0.86, _crises(l, 0)[0]),
            (0.5, LANGUES[l].moteur.periode_en_mois(14), 0.98, _crises(l, 1)[0]),
            (0.5, None, 0.79, _crises(l, 2)[0]),
        ],),
    ],
    ("regles", "affaiblie"): [lambda t, l: (1,), lambda t, l: (2,), lambda t, l: (3,)],
    ("regles", "aucune_hausse"): [lambda t, l: (1,), lambda t, l: (3,)],
    ("regles", "hausse_partielle"): [lambda t, l: (1, 2), lambda t, l: (2, 3)],
    ("regles", "crise_mince_comme_les_autres"): [
        lambda t, l: (_crises(l, 1)[0], True, 0.98, None, 23),
        lambda t, l: (_crises(l, 1)[0], False, 0.30, 0.45, 23),
    ],
    ("regles", "crise_mince"): [
        lambda t, l: (_crises(l, 1)[0], True, 0.98, None, 23),
        lambda t, l: (_crises(l, 1)[0], False, 0.40, 0.45, 1),
    ],
    ("regles", "sans_comparaison"): [
        lambda t, l: (_crises(l, 0),),
        lambda t, l: (_crises(l, 0, 1),),
        lambda t, l: (_crises(l, 0, 1, 2),),
    ],
    ("regles", "provenance_regimes"): [
        lambda t, l: (504, D1, D2, [(s.nom(l), n) for s, n in zip(SCENARIOS, (355, 23, 195))]),
    ],
    ("regles", "lignes_absentes"): [
        lambda t, l: (["C"], True),
        lambda t, l: (["A", "B"], True),
        lambda t, l: (["A", "B", "C"], False),
        lambda t, l: (["Z"], False),
    ],
    ("regles", "crise_rejouee_en_partie"): [
        lambda t, l: (CRISE.avec_article(l), 0.9, 2, 3),
        lambda t, l: (CRISE.avec_article(l), 0.7, 1, 3),
    ],
    ("regles", "impossible"): [
        lambda t, l: (CRISE.avec_article(l), True),
        lambda t, l: (CRISE.avec_article(l), False),
    ],
    ("regles", "sous_le_seuil"): [
        lambda t, l: (t.crise_rejouee_en_partie(CRISE.avec_article(l), 0.7, 2, 3), MIN_SCENARIO_COVERAGE.affiche(l)),
    ],
    ("regles", "couverture_suffisante"): [
        lambda t, l: (t.crise_rejouee_en_partie(CRISE.avec_article(l), 0.9, 2, 3), t.lignes_absentes(["C"], True), -0.44, True),
        lambda t, l: (t.crise_rejouee_en_partie(CRISE.avec_article(l), 0.85, 5, 6), t.lignes_absentes(["A", "B"], False), 0.05, False),
    ],
    ("regles", "provenance_scenario"): [lambda t, l: (CRISE.start, CRISE.end)],
    # ── Les seuils : chacun, nom, justification et ligne.
    ("seuils", "nom"): [lambda t, l, seuil=seuil: (seuil,) for seuil in SEUILS],
    ("seuils", "justification"): [lambda t, l, seuil=seuil: (seuil,) for seuil in SEUILS],
    ("seuils", "etiquette"): [lambda t, l, role=role: (role,) for role in ThresholdRole],
    ("seuils", "origine"): [
        lambda t, l, faits=faits: faits
        for faits in (
            (True, False, False),
            (False, True, True),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        )
    ],
    ("seuils", "ligne"): [
        lambda t, l, seuil=seuil: (
            seuil.nom(l), seuil.affiche(l), seuil.origine(l), seuil.justification(l)
        )
        for seuil in SEUILS
    ],
    # ── La couche API : corps d'erreur, refus d'une saisie, refus d'un fichier.
    # Les valeurs refusées citées sont des mots : un nombre saisi est une
    # donnée, qui ne se lit pas pareil dans les deux langues.
    ("api", "lignes_refusees"): [lambda t, l: (2,), lambda t, l: (1234,)],
    ("api", "ecriture_refusee"): [lambda t, l: ("FOREIGN KEY constraint failed",)],
    ("api", "route_inconnue"): [lambda t, l: ("api/nexiste-pas",)],
    ("api", "trop_de_positions"): [lambda t, l: (201, 200), lambda t, l: (1500, 200)],
    ("api", "doublon"): [lambda t, l: ("ALFA", 6), lambda t, l: ("ALFA", None)],
    ("api", "titre_inconnu"): [lambda t, l: ("XYZ", "ALFA, NEUF")],
    ("api", "titre_sans_prix"): [lambda t, l: ("NEUF",)],
    ("api", "quantite_non_finie"): [lambda t, l: ("ALFA",)],
    ("api", "quantite_non_positive"): [
        lambda t, l: ("ALFA", 0.0),
        lambda t, l: ("ALFA", -3.0),
        lambda t, l: ("ALFA", -2.5),
    ],
    ("api", "prix_de_revient_non_fini"): [lambda t, l: ("ALFA",)],
    ("api", "prix_de_revient_negatif"): [lambda t, l: ("ALFA",)],
    ("api", "aucun_separateur"): [lambda t, l: (EN_TETE_ATTENDU,)],
    ("api", "colonnes_manquantes"): [
        lambda t, l: (["ticker", "quantity"], EN_TETE_ATTENDU, ["symbol", "count"]),
        lambda t, l: (["quantity"], EN_TETE_ATTENDU, []),
    ],
    ("api", "fichier_trop_volumineux"): [lambda t, l: (1_000_000,)],
    ("api", "colonnes_en_trop"): [lambda t, l: (3, 2, True), lambda t, l: (5, 3, False)],
    ("api", "quantite_absente"): [
        lambda t, l: (1, ",", EN_TETE_ATTENDU),
        lambda t, l: (2, ";", EN_TETE_ATTENDU),
    ],
    ("api", "quantite_illisible"): [lambda t, l: ("ten", ","), lambda t, l: ("abc", ".")],
    ("api", "prix_de_revient_illisible"): [lambda t, l: ("dear", ".")],
}


def domaines(paquet) -> set[str]:
    return {module.name for module in pkgutil.iter_modules(paquet.__path__)}


def module(langue: str, domaine: str) -> ModuleType:
    return getattr(LANGUES[langue], domaine)


def definitions(mod: ModuleType) -> dict[str, ast.AST]:
    """Les noms publics DÉFINIS par un module de texte, lus dans son arbre
    syntaxique : ses fonctions et ses constantes, pas ce qu'il importe."""
    arbre = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    noms: dict[str, ast.AST] = {}
    for noeud in arbre.body:
        if isinstance(noeud, ast.FunctionDef):
            noms[noeud.name] = noeud
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    noms[cible.id] = noeud
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
            noms[noeud.target.id] = noeud
    return {nom: noeud for nom, noeud in noms.items() if not nom.startswith("_")}


def publics(mod: ModuleType) -> dict[str, object]:
    return {nom: getattr(mod, nom) for nom in definitions(mod)}


def chaines(sortie) -> list[str]:
    """Les chaînes d'une sortie : une chaîne, des n-uplets, un dictionnaire."""
    if isinstance(sortie, str):
        return [sortie]
    if isinstance(sortie, dict):
        return [texte for valeur in sortie.values() for texte in chaines(valeur)]
    if isinstance(sortie, (tuple, list)):
        return [texte for element in sortie for texte in chaines(element)]
    return []


def fautes_de_publication(texte: str, langue: str, domaine: str, nom: str) -> list[str]:
    """Les gardes de la langue, sur le texte tel que l'API le publie."""
    publie = prose(texte)
    fautes = fautes_de_forme(publie, langue, grec_admis=grec_admis(domaine, nom))
    registre = publie
    for expression in NON_PRESCRIPTIFS:
        registre = registre.replace(expression, "")
    fautes += [
        f for f in fautes_de_registre(registre, langue)
        if not (domaine in REGISTRE_EXEMPTE and f.startswith("prescriptif"))
    ]
    if langue == "en":
        fautes += fautes_de_francais(publie)
    return fautes


def sorties(domaine: str, nom: str, cas: Cas) -> dict[str, list[str]]:
    """Les chaînes qu'écrit une fonction sur un cas, dans chaque langue."""
    ecrites = {}
    for langue in LANGUES:
        textes = module(langue, domaine)
        ecrites[langue] = chaines(getattr(textes, nom)(*cas(textes, langue)))
    return ecrites


# ═══════════════════════════════════════════════════════ Les mêmes noms ══


def test_les_deux_langues_ont_les_memes_domaines():
    assert domaines(fr) == domaines(en)
    assert domaines(fr), "aucun domaine : le test ne vérifierait rien"


@pytest.mark.parametrize("domaine", sorted(domaines(fr)))
def test_chaque_domaine_a_les_memes_noms_et_les_memes_signatures(domaine):
    francais, anglais = publics(module("fr", domaine)), publics(module("en", domaine))
    assert set(francais) == set(anglais), domaine
    for nom, valeur in francais.items():
        jumeau = anglais[nom]
        assert callable(valeur) == callable(jumeau), nom
        if callable(valeur):
            assert inspect.signature(valeur) == inspect.signature(jumeau), nom
        else:
            assert type(valeur) is type(jumeau), nom


# ═════════════════════════════════════ Chaque fonction, dans chaque langue ══


def test_chaque_fonction_a_ses_cas():
    """La complétude : une fonction de texte sans cas ne serait jamais lue."""
    fonctions = {
        (domaine, nom)
        for domaine in domaines(fr)
        for nom, valeur in publics(module("fr", domaine)).items()
        if callable(valeur)
    }
    assert fonctions - set(CAS) == set(), "fonctions sans cas"
    assert set(CAS) - fonctions == set(), "cas sans fonction"


@pytest.mark.parametrize("domaine, nom", sorted(CAS))
def test_chaque_fonction_ecrit_dans_les_deux_langues_et_passe_leurs_gardes(domaine, nom):
    for cas in CAS[(domaine, nom)]:
        ecrites = sorties(domaine, nom, cas)
        for langue, textes in ecrites.items():
            assert textes, (domaine, nom, "aucune chaîne")
            fautes = [
                (langue, f)
                for texte in textes
                for f in fautes_de_publication(texte, langue, domaine, nom)
            ]
            assert fautes == [], (domaine, nom, fautes[:5])
        oubliees = [a for f, a in zip(ecrites["fr"], ecrites["en"]) if f == a]
        assert oubliees == [], (domaine, nom, "traduction oubliée", oubliees)


@pytest.mark.parametrize("domaine, nom", sorted(CAS))
def test_chaque_fonction_dit_les_memes_nombres_dans_les_deux_langues(domaine, nom):
    """Une traduction ne perd, n'ajoute ni ne change aucun nombre : « 9,8
    points » et « 9.8 points », « 100 000 » et « 100,000 », les mêmes dates."""
    for cas in CAS[(domaine, nom)]:
        ecrites = sorties(domaine, nom, cas)
        francais = [nombres(texte, "fr") for texte in ecrites["fr"]]
        anglais = [nombres(texte, "en") for texte in ecrites["en"]]
        assert anglais == francais, (domaine, nom, ecrites["fr"], ecrites["en"])


@pytest.mark.parametrize("domaine", sorted(domaines(fr)))
def test_chaque_constante_passe_les_gardes_de_sa_langue(domaine):
    for langue in LANGUES:
        for nom, valeur in publics(module(langue, domaine)).items():
            if callable(valeur):
                continue
            for texte in chaines(valeur):
                assert fautes_de_publication(texte, langue, domaine, nom) == [], (langue, domaine, nom)


@pytest.mark.parametrize("domaine", sorted(domaines(fr)))
def test_chaque_constante_dit_les_memes_nombres_dans_les_deux_langues(domaine):
    francaises, anglaises = publics(module("fr", domaine)), publics(module("en", domaine))
    for nom, valeur in francaises.items():
        if callable(valeur):
            continue
        assert [nombres(texte, "en") for texte in chaines(anglaises[nom])] == [
            nombres(texte, "fr") for texte in chaines(valeur)
        ], (domaine, nom)


# ═══════════════════════════════════════════════ Chaque chaîne du code ══


def chaines_du_module(chemin: Path) -> list[tuple[str, int, str]]:
    """Chaque chaîne d'un module de texte, avec le nom de la définition qui la
    porte et sa ligne, hors docstrings."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.Module, ast.FunctionDef))
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    trouvees = []
    for noeud in arbre.body:
        nom = getattr(noeud, "name", None) or next(
            (c.id for c in getattr(noeud, "targets", []) if isinstance(c, ast.Name)),
            getattr(getattr(noeud, "target", None), "id", "<module>"),
        )
        for sous in ast.walk(noeud):
            if isinstance(sous, ast.Constant) and isinstance(sous.value, str) and id(sous) not in docstrings:
                trouvees.append((nom, sous.lineno, sous.value))
    return trouvees


def sources(langue: str) -> list[Path]:
    return sorted(Path(LANGUES[langue].__path__[0]).glob("*.py"))


@pytest.mark.parametrize("langue", sorted(LANGUES))
def test_chaque_chaine_du_code_passe_les_gardes_de_sa_langue(langue):
    """Ce que les cas n'exercent pas se lit dans le code : aucun tiret
    cadratin, aucune lettre grecque hors de la provenance et des formules d'un
    seuil, rien de prescriptif ; en anglais, aucune ponctuation à la
    française et aucun mot français."""
    fautes = []
    for chemin in sources(langue):
        domaine = chemin.stem
        for nom, ligne, texte in chaines_du_module(chemin):
            ou = f"{langue}/{chemin.name}:{ligne} ({nom})"
            if CADRATIN in texte:
                fautes.append((ou, "tiret cadratin", texte[:60]))
            if GREC.search(texte) and not grec_admis(domaine, nom):
                fautes.append((ou, "lettre grecque", texte[:60]))
            if domaine not in REGISTRE_EXEMPTE and PRESCRIPTIONS[langue].search(texte):
                fautes.append((ou, "prescriptif", texte[:60]))
            if langue == "en" and (PONCTUATION_EN.search(prose(texte)) or FRANCAIS.search(texte)):
                fautes.append((ou, "français", texte[:60]))
    assert fautes == []


def test_le_balayage_lit_bien_les_deux_langues():
    """Témoin : un glob vide passerait au vert."""
    for langue in LANGUES:
        noms = {chemin.name for chemin in sources(langue)}
        assert {"__init__.py", "api.py", "bandeau.py", "moteur.py", "regles.py", "seuils.py"} <= noms, langue


# ═══════════════════════════════════════════════ Le catalogue des crises ══


def test_chaque_crise_du_catalogue_a_son_nom_et_sa_description_en_anglais():
    """Les noms et les descriptions anglaises vivent dans le catalogue, avec
    les françaises : les gardes anglaises les lisent comme `textes/en/`."""
    for scenario in SCENARIOS:
        assert scenario.name_en is not None and scenario.description_en is not None, scenario.key
        for francais, anglais in (
            (scenario.name, scenario.name_en),
            (scenario.description, scenario.description_en),
            (scenario.avec_article("fr"), scenario.avec_article("en")),
        ):
            assert anglais != francais, scenario.key
            assert fautes_de_publication(anglais, "en", "moteur", "nom") == [], anglais
            assert fautes_de_publication(francais, "fr", "moteur", "nom") == [], francais
            assert nombres(anglais, "en") == nombres(francais, "fr"), scenario.key


# ═════════════════════════════════════════════════════════════ Les seuils ══


def test_chaque_seuil_nomme_la_declaration_qui_le_pose():
    """La clé d'un seuil, que lit `textes/en/seuils.py`, est le nom de sa
    déclaration dans `rules/thresholds.py` : la constante elle-même, ou la
    fonction qui le fabrique. Une fonction nouvelle qui fabrique un seuil doit
    entrer ici, et dans l'anglais."""
    constantes = {nom: v for nom, v in vars(thresholds).items() if isinstance(v, Threshold)}
    assert constantes, "aucune constante : le test ne vérifierait rien"
    for nom, seuil in constantes.items():
        assert seuil.key == nom, nom
    fabriques = {
        nom
        for nom, valeur in vars(thresholds).items()
        if inspect.isfunction(valeur)
        and valeur.__module__ == thresholds.__name__
        and not nom.startswith("_")
    }
    assert fabriques == {"historical_var_sample", "capital_share", "most_correlated_pair"}
    assert {seuil.key for seuil in SEUILS} == set(constantes) | fabriques


@pytest.mark.parametrize("seuil", SEUILS, ids=lambda seuil: f"{seuil.key}{list(seuil.params)}")
def test_un_seuil_dit_les_memes_nombres_et_les_memes_formules_dans_les_deux_langues(seuil):
    """Les nombres d'une justification sont écrits deux fois, une par langue
    (« 2,05 % » et « 2.05% ») : rien d'autre ne garantit qu'ils restent les
    mêmes. Les lettres grecques, de même, sont celles du français."""
    francaise, anglaise = seuil.ligne("fr"), seuil.ligne("en")
    assert francaise == str(seuil), "la ligne française est celle d'avant le chantier"
    assert nombres(anglaise, "en") == nombres(francaise, "fr")
    assert sorted(GREC.findall(anglaise)) == sorted(GREC.findall(francaise))


def test_l_exception_prescriptive_est_declaree_mot_pour_mot():
    """La définition passe ; « réduire » ailleurs reste vu."""
    assert fautes_de_publication("La CVaR se réduirait au même minimum.", "fr", "seuils", "nom") == []
    assert fautes_de_publication("Il faudrait réduire la ligne JPM.", "fr", "seuils", "nom")
    assert fautes_de_publication("Elle se réduirait de moitié.", "fr", "seuils", "nom")


def test_l_ecriture_francaise_d_avant_le_chantier_n_a_plus_d_exception():
    """« 2 lignes refusées », avec une espace ordinaire, était déclaré à la
    garde de l'espace avant le mot compté ; corrigé en session 2, il n'a plus
    d'exception : l'ancienne écriture est vue, dans les deux langues."""
    francais = "2 lignes refusées : aucune position n'a été écrite."
    assert fautes_de_publication(francais, "fr", "api", "lignes_refusees")
    assert fautes_de_publication("2 holdings rejected.", "en", "api", "lignes_refusees")
    assert fautes_de_publication(fr.api.lignes_refusees(2), "fr", "api", "lignes_refusees") == []
