"""Tous les textes d'erreur du serveur public, parcourus un par un.

Le serveur public (`backend/public_api/`, chantier 9.6) analyse le
portefeuille qu'un visiteur du site saisit. Un refus de l'API locale dit quoi
lancer sur le poste ; un visiteur n'a pas de poste où le lancer. Le serveur
public a donc ses textes, dans `backend/textes/<langue>/public.py`, et AUCUN
ne porte de commande ni ne renvoie à l'application installée.

Ce fichier le tient sur la liste entière, pas sur les réponses que les tests
déclenchent : chaque nom défini dans le module est lu, chaque fonction sur
ses cas (`tests/test_textes_symetriques.py`), dans les deux langues. Les
réponses réelles du serveur sont relues de leur côté
(`tests/test_serveur_public.py`).

La garde est vue mordre sur les textes locaux qu'elle existe pour écarter.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.textes import en, fr
from backend.typography import prose

from .test_textes_symetriques import CAS, REPRIS_PAR_LE_SERVEUR_PUBLIC, chaines, publics

RACINE = Path(__file__).resolve().parents[1]
LANGUES = {"fr": fr, "en": en}

# Ce qu'aucun texte du serveur public ne dit : une commande, le nom d'un
# module, un geste d'installation, l'application installée, une adresse du
# poste. Cherchés sans égard à la casse.
INTERDITS = (
    "python -m",
    "python.exe",
    "backend.",
    "ingestion",
    "refresh",
    "rebuild",
    "backfill",
    "pip install",
    "npm ",
    "install",
    "application locale",
    "local application",
    "127.0.0.1",
    "localhost",
    "port 8000",
    ".env",
)

# Les constantes que le serveur public reprend de l'API locale, à côté des
# fonctions de `REPRIS_PAR_LE_SERVEUR_PUBLIC`.
CONSTANTES_REPRISES = (
    "VALEUR_REFUSEE",
    "REQUETE_REFUSEE",
    "TICKER_VIDE",
    "FICHIER_ILLISIBLE",
    "FICHIER_VIDE",
)


def interdits_dans(texte: str) -> list[str]:
    """Les mots interdits qu'un texte contient."""
    bas = texte.lower()
    return [mot for mot in INTERDITS if mot in bas]


def textes_publics(langue: str) -> dict[str, list[str]]:
    """Chaque nom du module public d'une langue, avec tout ce qu'il écrit :
    une constante telle quelle, une fonction sur chacun de ses cas."""
    module = LANGUES[langue].public
    ecrits: dict[str, list[str]] = {}
    for nom, valeur in publics(module).items():
        if callable(valeur):
            ecrits[nom] = [
                texte
                for cas in CAS[("public", nom)]
                for texte in chaines(valeur(*cas(module, langue)))
            ]
        else:
            ecrits[nom] = chaines(valeur)
    return ecrits


# ═══════════════════════════════════════════════════════ La liste entière ══


@pytest.mark.parametrize("langue", sorted(LANGUES))
def test_aucun_texte_du_serveur_public_ne_porte_de_commande(langue):
    ecrits = textes_publics(langue)
    assert len(ecrits) >= 30, "le parcours ne voit pas le module"
    for nom, textes in ecrits.items():
        assert textes, (langue, nom, "aucun texte")
        for texte in textes:
            assert interdits_dans(prose(texte)) == [], (langue, nom, texte)


def test_les_deux_langues_parcourent_les_memes_noms():
    assert set(textes_publics("fr")) == set(textes_publics("en"))


@pytest.mark.parametrize("langue", sorted(LANGUES))
def test_les_textes_repris_sont_ceux_de_l_api_locale_et_pas_une_copie(langue):
    """Liés par leur nom : un mot changé dans `api.py` change ici aussi, et
    aucune copie ne peut prendre du retard."""
    textes = LANGUES[langue]
    for nom in (*REPRIS_PAR_LE_SERVEUR_PUBLIC, *CONSTANTES_REPRISES):
        assert getattr(textes.public, nom) is getattr(textes.api, nom), (langue, nom)


@pytest.mark.parametrize("langue", sorted(LANGUES))
def test_un_texte_local_qui_porte_une_commande_n_est_pas_repris(langue):
    """Tout nom de même orthographe dans les deux modules est soit repris
    parce qu'il ne dit rien de l'application, soit réécrit."""
    textes = LANGUES[langue]
    locaux = publics(textes.api)
    reecrits = []
    for nom, valeur in publics(textes.public).items():
        if nom not in locaux:
            continue
        if valeur is locaux[nom]:
            continue
        reecrits.append(nom)
    assert sorted(reecrits) == [
        "AUCUNE_POSITION",
        "lignes_refusees",
        "titre_inconnu",
        "titre_sans_prix",
        "trop_de_positions",
    ]


# ══════════════════════════════════════════════════════ La garde elle-même ══


@pytest.mark.parametrize("langue", sorted(LANGUES))
def test_la_garde_mord_sur_les_refus_de_l_api_locale(langue):
    """Les deux textes que le serveur public réécrit pour cette raison."""
    api = LANGUES[langue].api
    assert "python -m" in interdits_dans(api.titre_inconnu("XYZ", "ALFA, NEUF"))
    assert "ingestion" in interdits_dans(api.titre_sans_prix("NEUF"))


@pytest.mark.parametrize(
    "texte, attendu",
    (
        ("Lancer : python -m backend.api", ["python -m", "backend."]),
        ("Check coverage with `PYTHON -M backend.ingestion status`.", ["python -m", "backend.", "ingestion"]),
        ("Relancer le refresh de la base.", ["refresh"]),
        ("Voir l'application locale.", ["application locale"]),
        ("Install the application first.", ["install"]),
        ("L'API écoute sur 127.0.0.1, port 8000.", ["127.0.0.1", "port 8000"]),
        ("Renseigner la clé dans .env.", [".env"]),
    ),
)
def test_la_garde_voit_chaque_forme(texte, attendu):
    assert interdits_dans(texte) == attendu


@pytest.mark.parametrize(
    "texte",
    (
        "XYZ n'est pas un titre de la base. Titres disponibles : ALFA, NEUF.",
        "Trop de demandes depuis cette adresse : au plus 20 par période de 10 minutes.",
        "Unreadable file: neither UTF-8 nor CP1252.",
        "The server is already computing other analyses. Try again in a moment.",
    ),
)
def test_la_garde_laisse_passer_un_refus_sans_commande(texte):
    assert interdits_dans(texte) == []


# ═════════════════════ Les noms que la validation et le lecteur appellent ══


def noms_appeles(source: str) -> set[str]:
    """Les textes qu'un module de l'API demande à son module de rédaction :
    les attributs lus sur `t` ou sur `redaction`, et le nom que porte chaque
    `CsvError`."""
    noms: set[str] = set()
    for noeud in ast.walk(ast.parse(source)):
        if (
            isinstance(noeud, ast.Attribute)
            and isinstance(noeud.value, ast.Name)
            and noeud.value.id in ("t", "redaction")
        ):
            noms.add(noeud.attr)
        elif (
            isinstance(noeud, ast.Call)
            and getattr(noeud.func, "id", None) == "CsvError"
            and noeud.args
            and isinstance(noeud.args[0], ast.Constant)
        ):
            noms.add(noeud.args[0].value)
    return noms


def test_la_lecture_des_noms_voit_ce_qu_elle_doit_voir():
    source = 't = x\nt.doublon("A", 1)\nraise CsvError("FICHIER_VIDE")\nredaction.colonnes_en_trop(3, 2, True)\n'
    assert noms_appeles(source) == {"doublon", "FICHIER_VIDE", "colonnes_en_trop"}


@pytest.mark.parametrize("module", ("validation.py", "csv_import.py"))
def test_chaque_texte_que_l_api_partagee_demande_existe_dans_le_module_public(module):
    """`validate` et `read` reçoivent le module public à la place de celui de
    l'API : un texte ajouté d'un côté sans l'autre lèverait à la première
    requête qui le déclenche."""
    appeles = noms_appeles((RACINE / "backend" / "api" / module).read_text(encoding="utf-8"))
    assert len(appeles) >= 5, "la lecture ne voit pas les appels"
    for langue, textes in LANGUES.items():
        manquants = sorted(nom for nom in appeles if not hasattr(textes.public, nom))
        assert manquants == [], (langue, module)
