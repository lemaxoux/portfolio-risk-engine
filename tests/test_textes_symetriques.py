"""Les textes du serveur existent dans les deux langues, et pas à moitié.

`backend/textes/fr/` et `backend/textes/en/` exposent les mêmes domaines, les
mêmes noms, avec les mêmes signatures (chantier 7D). C'est ce qui rend la
complétude vérifiable : une phrase oubliée en anglais fait échouer ce test,
même si aucune réponse de test ne la déclenche.

Chaque fonction de texte est EXERCÉE dans les deux langues, sur un catalogue de
cas qui couvre ses variantes (`CAS`) : une fonction sans cas échoue. Chaque
sortie, publiée comme l'API la publie (`typography.prose`), passe les gardes de
sa langue ; une sortie anglaise identique à la française est une traduction
oubliée. Chaque chaîne du code des deux langues est lue en plus : un cas
oublié ne cache pas une chaîne. Les noms et les descriptions anglaises du
catalogue des crises sont lus de même.

Seule la provenance d'une mesure — sa méthode, son détail, écrits en IBM Plex
Sans — cite des lettres grecques (« λ=0,94 », « ν = 4,07 », « μ = 0 »).
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

from backend.risk_engine.scenarios import SCENARIOS
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
)

LANGUES = {"fr": fr, "en": en}

# Les domaines dont le registre n'est pas celui d'un constat : l'écran
# d'acceptation dit à bon droit ce que l'outil n'est pas (« pas un conseil »,
# « acheter, de vendre ou de conserver un titre »). La garde prescriptive ne le
# lit pas, aujourd'hui non plus.
REGISTRE_EXEMPTE = {"bandeau"}


def est_provenance(nom: str) -> bool:
    """La méthode ou le détail d'une mesure : s'affiche en IBM Plex Sans, qui
    a le grec."""
    return nom.startswith(("METHODE_", "methode_", "detail_"))


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
    fautes = fautes_de_forme(publie, langue, grec_admis=est_provenance(nom))
    fautes += [
        f for f in fautes_de_registre(publie, langue)
        if not (domaine in REGISTRE_EXEMPTE and f.startswith("prescriptif"))
    ]
    if langue == "en":
        fautes += fautes_de_francais(publie)
    return fautes


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
        sorties = {}
        for langue in LANGUES:
            textes = module(langue, domaine)
            sortie = getattr(textes, nom)(*cas(textes, langue))
            assert chaines(sortie), (domaine, nom, "aucune chaîne")
            fautes = [
                (langue, f)
                for texte in chaines(sortie)
                for f in fautes_de_publication(texte, langue, domaine, nom)
            ]
            assert fautes == [], (domaine, nom, fautes[:5])
            sorties[langue] = chaines(sortie)
        oubliees = [a for f, a in zip(sorties["fr"], sorties["en"]) if f == a]
        assert oubliees == [], (domaine, nom, "traduction oubliée", oubliees)


@pytest.mark.parametrize("domaine", sorted(domaines(fr)))
def test_chaque_constante_passe_les_gardes_de_sa_langue(domaine):
    for langue in LANGUES:
        for nom, valeur in publics(module(langue, domaine)).items():
            if callable(valeur):
                continue
            for texte in chaines(valeur):
                assert fautes_de_publication(texte, langue, domaine, nom) == [], (langue, domaine, nom)


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
    cadratin, aucune lettre grecque hors de la provenance, rien de
    prescriptif ; en anglais, aucune ponctuation à la française et aucun mot
    français."""
    fautes = []
    for chemin in sources(langue):
        domaine = chemin.stem
        for nom, ligne, texte in chaines_du_module(chemin):
            ou = f"{langue}/{chemin.name}:{ligne} ({nom})"
            if CADRATIN in texte:
                fautes.append((ou, "tiret cadratin", texte[:60]))
            if GREC.search(texte) and not est_provenance(nom):
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
        assert {"__init__.py", "bandeau.py", "moteur.py"} <= noms, langue


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
