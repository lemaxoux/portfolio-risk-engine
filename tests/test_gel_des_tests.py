"""Aucun fichier de tests n'ouvre `data/mx_risk.sqlite` directement.

La base réelle est un fichier VIVANT : `refresh` y ajoute des séances, et
`rebuild` la réécrit. Un test qui la lit vérifie l'état du fichier, pas le
code, et tombe le lendemain d'un rattrapage sans qu'une ligne ait changé.
C'est arrivé à cinq tests de `test_api_analysis.py` en 7B.2.

Le seul accès permis passe par `conftest.py`, qui copie la base et la tronque
à `DATE_GEL` (fixtures `base_figee`, `base_figee_partagee`, `analyse_reelle`).
Ce fichier vérifie que les autres fichiers de tests ne l'ouvrent pas autrement.

Comme `test_api_discipline.py`, la garde lit l'arbre syntaxique et non le
texte brut : une docstring qui NOMME la base ne l'ouvre pas. Et elle est
exercée par deux jeux de témoins, dans les deux sens.
"""

from __future__ import annotations

import ast
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from backend.db.init_db import connect
from tests.conftest import DATE_GEL

DOSSIER_TESTS = Path(__file__).resolve().parent

# Noms qui désignent la base réelle, ou le chemin par défaut qui y mène
# quand MX_RISK_DB_PATH n'est pas posée.
NOMS_INTERDITS = frozenset({"BASE_REELLE", "DEFAULT_DB_PATH", "get_db_path"})

# Appelées sans chemin, ces fonctions ouvrent `get_db_path()`, donc la base
# réelle hors variable d'environnement.
OUVERTURES_PAR_DEFAUT = frozenset({"connect", "init_db"})


def _docstrings(arbre: ast.AST) -> set[int]:
    """Identifiants des constantes qui sont des docstrings ou du texte seul."""
    ignorees = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant):
            ignorees.add(id(noeud.value))
    return ignorees


def _nom_appele(appel: ast.Call) -> str | None:
    if isinstance(appel.func, ast.Name):
        return appel.func.id
    if isinstance(appel.func, ast.Attribute):
        return appel.func.attr
    return None


def acces_directs(source: str) -> list[str]:
    """Ce qui, dans `source`, ouvre ou désigne la base réelle.

    Quatre formes :

    * un nom qui la désigne (`BASE_REELLE`, `DEFAULT_DB_PATH`,
      `get_db_path`), qu'il soit lu, importé ou appelé ;
    * `connect()` ou `init_db()` sans chemin ;
    * une chaîne qui vaut `mx_risk.sqlite` ou s'achève en `/mx_risk.sqlite` ;
    * `MX_RISK_DB_PATH` retirée de l'environnement, ce qui ramène les
      ouvertures suivantes vers la base réelle.
    """
    arbre = ast.parse(source)
    textes = _docstrings(arbre)
    trouves: list[str] = []

    for noeud in ast.walk(arbre):
        ligne = getattr(noeud, "lineno", 0)
        if isinstance(noeud, ast.Name) and noeud.id in NOMS_INTERDITS:
            trouves.append(f"ligne {ligne} : {noeud.id}")
        elif isinstance(noeud, ast.Attribute) and noeud.attr in NOMS_INTERDITS:
            trouves.append(f"ligne {ligne} : .{noeud.attr}")
        elif isinstance(noeud, ast.alias) and noeud.name in NOMS_INTERDITS:
            trouves.append(f"ligne {ligne} : import de {noeud.name}")
        elif isinstance(noeud, ast.Call):
            nom = _nom_appele(noeud)
            if nom in OUVERTURES_PAR_DEFAUT and not noeud.args and not noeud.keywords:
                trouves.append(f"ligne {ligne} : {nom}() sans chemin")
            if nom == "delenv" and any(
                isinstance(a, ast.Constant) and a.value == "MX_RISK_DB_PATH"
                for a in noeud.args
            ):
                trouves.append(f"ligne {ligne} : MX_RISK_DB_PATH retirée")
        elif (
            isinstance(noeud, ast.Constant)
            and isinstance(noeud.value, str)
            and id(noeud) not in textes
        ):
            valeur = noeud.value.replace("\\", "/")
            if valeur == "mx_risk.sqlite" or valeur.endswith("/mx_risk.sqlite"):
                trouves.append(f"ligne {ligne} : chaîne {noeud.value!r}")
    return trouves


# ------------------------------------------------------------------ Témoins --

DOIVENT_ETRE_DETECTES = [
    "BASE_REELLE.exists()",
    "connexion = connect(BASE_REELLE)",
    "from tests.conftest import BASE_REELLE",
    "import tests.conftest as c\nc.BASE_REELLE",
    "connect()",
    "init_db()",
    "conn = sqlite3.connect(RACINE / 'data' / 'mx_risk.sqlite')",
    "chemin = 'data/mx_risk.sqlite'",
    "chemin = r'data\\mx_risk.sqlite'",
    "from backend.db.init_db import DEFAULT_DB_PATH",
    "chemin = get_db_path()",
    "monkeypatch.delenv('MX_RISK_DB_PATH')",
]

NE_DOIVENT_PAS_ETRE_DETECTES = [
    '"""Ne lit jamais data/mx_risk.sqlite : une copie figée."""',
    "def f():\n    'Copie de data/mx_risk.sqlite.'\n    return 1",
    "connect(base_figee)",
    "connect(tmp_path / 'base.sqlite')",
    "init_db(chemin)",
    "chemin = tmp_path / 'autre_mx_risk.sqlite.bak'",
    "monkeypatch.setenv('MX_RISK_DB_PATH', str(copie))",
    "copier_base_reelle_figee(tmp_path / 'copie.sqlite')",
]


@pytest.mark.parametrize("extrait", DOIVENT_ETRE_DETECTES)
def test_la_garde_voit_un_acces_direct(extrait):
    assert acces_directs(extrait), f"non détecté : {extrait!r}"


@pytest.mark.parametrize("extrait", NE_DOIVENT_PAS_ETRE_DETECTES)
def test_la_garde_ne_crie_pas_au_loup(extrait):
    assert acces_directs(extrait) == []


# -------------------------------------------------------------------- Garde --


# conftest.py est le seul accès permis : il copie et tronque. Ce fichier-ci
# nomme la base pour la reconnaître ; ce sont ses témoins qui l'exercent.
EXEMPTES = frozenset({"conftest.py", Path(__file__).name})


def fichiers_de_tests() -> list[Path]:
    return sorted(f for f in DOSSIER_TESTS.rglob("*.py") if f.name not in EXEMPTES)


def test_la_garde_parcourt_bien_les_fichiers_de_tests():
    # Un glob vide passerait au vert sur tout le dossier.
    noms = {f.name for f in fichiers_de_tests()}
    assert {"test_api_analysis.py", "test_stress.py", "test_student.py"} <= noms


@pytest.mark.parametrize("fichier", fichiers_de_tests(), ids=lambda f: f.name)
def test_aucun_fichier_de_tests_n_ouvre_la_base_reelle(fichier):
    trouves = acces_directs(fichier.read_text(encoding="utf-8"))
    assert trouves == [], (
        f"{fichier.name} ouvre la base réelle sans passer par la copie figée "
        f"de conftest.py (base_figee, base_figee_partagee) : {trouves}"
    )


# --------------------------------------------------- Les copies elles-mêmes --


def test_la_copie_partagee_s_arrete_au_gel(base_figee_partagee):
    with closing(connect(base_figee_partagee)) as c:
        assert c.execute("SELECT MAX(date) FROM prices").fetchone()[0] == DATE_GEL


def test_la_copie_partagee_refuse_l_ecriture(base_figee_partagee):
    # Partagée par toute la session : un test qui y écrirait fausserait les
    # suivants sans qu'aucun ne le voie.
    with closing(connect(base_figee_partagee)) as c:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            c.execute("INSERT INTO portfolios (owner) VALUES ('intrus')")


def test_une_copie_propre_au_test_accepte_l_ecriture(base_figee):
    with closing(connect(base_figee)) as c, c:
        c.execute("INSERT INTO portfolios (owner) VALUES ('test')")
        assert c.execute("SELECT MAX(date) FROM prices").fetchone()[0] == DATE_GEL
