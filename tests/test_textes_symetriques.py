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
oublié ne cache pas une chaîne.
"""

from __future__ import annotations

import inspect
import pkgutil
from collections.abc import Callable
from pathlib import Path

import pytest

from backend.textes import en, fr
from backend.typography import prose

from .gardes_texte import (
    CADRATIN,
    FRANCAIS,
    GREC,
    PONCTUATION_EN,
    PRESCRIPTIONS,
    chaines_publiables,
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

# Les cas de chaque fonction : chacun reçoit le module de texte de la langue et
# rend les arguments. Un argument qui est lui-même un texte rédigé (une durée)
# se rédige dans la langue du cas.
Cas = Callable[[object], tuple]
CAS: dict[tuple[str, str], list[Cas]] = {
    ("bandeau", "duree_en_annees"): [lambda t: (1,), lambda t: (2,), lambda t: (11,)],
    ("bandeau", "duree_en_mois"): [lambda t: (1,), lambda t: (6,), lambda t: (14,)],
    ("bandeau", "sections"): [
        lambda t: (504, t.duree_en_annees(2)),
        lambda t: (60, t.duree_en_mois(3)),
        lambda t: (2520, t.duree_en_annees(10)),
    ],
}


def domaines(paquet) -> set[str]:
    return {module.name for module in pkgutil.iter_modules(paquet.__path__)}


def publics(module) -> dict[str, object]:
    """Les noms publics d'un module de texte, hors imports."""
    return {
        nom: valeur
        for nom, valeur in vars(module).items()
        if not nom.startswith("_")
        and not inspect.ismodule(valeur)
        and nom != "annotations"
        and (not callable(valeur) or getattr(valeur, "__module__", None) == module.__name__)
    }


def module(langue: str, domaine: str):
    return getattr(LANGUES[langue], domaine)


def chaines(sortie) -> list[str]:
    """Les chaînes d'une sortie : une chaîne, ou des n-uplets de chaînes."""
    if isinstance(sortie, str):
        return [sortie]
    if isinstance(sortie, (tuple, list)):
        return [texte for element in sortie for texte in chaines(element)]
    return []


def fautes_de_publication(texte: str, langue: str, domaine: str) -> list[str]:
    """Les gardes de la langue, sur le texte tel que l'API le publie."""
    publie = prose(texte)
    fautes = fautes_de_forme(publie, langue)
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
            sortie = getattr(textes, nom)(*cas(textes))
            assert chaines(sortie), (domaine, nom, "aucune chaîne")
            fautes = [
                (langue, f) for texte in chaines(sortie) for f in fautes_de_publication(texte, langue, domaine)
            ]
            assert fautes == [], (domaine, nom, fautes[:5])
            sorties[langue] = chaines(sortie)
        oubliees = [a for f, a in zip(sorties["fr"], sorties["en"]) if f == a]
        assert oubliees == [], (domaine, nom, "traduction oubliée", oubliees)


@pytest.mark.parametrize("domaine", sorted(domaines(fr)))
def test_chaque_constante_passe_les_gardes_de_sa_langue(domaine):
    for langue in LANGUES:
        for nom, valeur in publics(module(langue, domaine)).items():
            if isinstance(valeur, str):
                assert fautes_de_publication(valeur, langue, domaine) == [], (langue, domaine, nom)


# ═══════════════════════════════════════════════ Chaque chaîne du code ══


def sources(langue: str) -> list[Path]:
    return sorted(Path(LANGUES[langue].__path__[0]).glob("*.py"))


@pytest.mark.parametrize("langue", sorted(LANGUES))
def test_chaque_chaine_du_code_passe_les_gardes_de_sa_langue(langue):
    """Ce que les cas n'exercent pas se lit dans le code : aucun tiret
    cadratin, aucune lettre grecque, rien de prescriptif ; en anglais, aucune
    ponctuation à la française et aucun mot français."""
    fautes = []
    for chemin in sources(langue):
        domaine = chemin.stem
        for ligne, texte in chaines_publiables(chemin.read_text(encoding="utf-8")):
            ou = f"{langue}/{chemin.name}:{ligne}"
            if CADRATIN in texte:
                fautes.append((ou, "tiret cadratin", texte[:60]))
            if GREC.search(texte):
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
        assert {"__init__.py", "bandeau.py"} <= noms, langue
