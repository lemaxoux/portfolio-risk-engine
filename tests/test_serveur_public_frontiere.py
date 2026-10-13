"""Ce que le serveur public ne charge pas, et ce qu'il dit exécuter.

Le serveur public (`backend/public_api/`, chantier 9.6) est ouvert à tous. Il
n'a le droit ni à l'ingestion, ni au fournisseur de prix, ni à sa
bibliothèque réseau, ni à la lecture d'un `.env`, ni à l'application locale
et à ses écritures. Ce fichier le tient de trois façons, sur le modèle de
`tests/test_frontiere_fournisseur.py` :

* dans le TEXTE de ses modules : aucun n'importe ce qui lui est interdit ;
* dans un INTERPRÉTEUR NEUF, qui importe l'application : ce qui lui est
  interdit n'y est pas chargé, par aucun chemin, même indirect. `dotenv` et
  `requests` y sont rendus impossibles à importer, comme ils le sont chez
  l'hébergeur, où ils ne sont pas installés ;
* dans ses DÉPENDANCES : `requirements-serveur.txt` est `requirements.txt`
  moins ces deux-là.

Il tient aussi l'empreinte du code (`backend/public_api/empreinte.py`) : le
même ensemble de fichiers sur le disque et dans les objets git, qu'un `.pyc`
posé à côté ne change pas.

Chaque garde a ses témoins, dans les deux sens.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend import indice
from backend.ingestion import universe
from backend.public_api.empreinte import (
    appartient,
    empreinte,
    empreinte_du_code,
    fichiers_sur_le_disque,
)
from backend.risk_engine import config
from backend.textes import textes
from tools.base_serveur import empreinte_du_code_au_commit

RACINE = Path(__file__).resolve().parents[1]

# Les modules propres au serveur public : son paquet, son accès à la base, et
# le module de données que le moteur lit à la place de l'ingestion.
MODULES_DU_SERVEUR = sorted(
    [
        *(RACINE / "backend" / "public_api").glob("*.py"),
        RACINE / "backend" / "db" / "lecture_seule.py",
        RACINE / "backend" / "indice.py",
    ]
)

# Ce qu'aucun module chargé par le serveur public ne doit être, ni contenir.
INTERDITS = (
    "backend.ingestion",
    "backend.data_provider",
    "requests",
    "urllib3",
    "dotenv",
    "backend.api.app",
    "backend.api.routes",
    "backend.api.static",
    "backend.api.dependencies",
    "backend.api.__main__",
    "backend.db.init_db",
    "backend.db.migrate",
    "backend.db.backup",
)


def interdit(nom: str) -> bool:
    return any(nom == racine or nom.startswith(racine + ".") for racine in INTERDITS)


# ═══════════════════════════════════════════════ Dans le texte des modules ══


def imports_interdits(source: str, paquet: str = "backend.public_api") -> list[str]:
    """Les modules interdits qu'un module du paquet `paquet` importe : imports
    absolus et relatifs, faits au chargement ou dans une fonction, et imports
    dynamiques par leur nom."""
    trouves: dict[str, None] = {}

    def voir(nom: str) -> bool:
        if interdit(nom):
            trouves[nom] = None
        return interdit(nom)

    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                voir(alias.name)
        elif isinstance(noeud, ast.ImportFrom):
            base = noeud.module or ""
            if noeud.level:
                parties = paquet.split(".")
                parties = parties[: len(parties) - (noeud.level - 1)]
                base = ".".join(parties + ([base] if base else []))
            if not voir(base):
                for alias in noeud.names:
                    voir(f"{base}.{alias.name}")
        elif (
            isinstance(noeud, ast.Call)
            and getattr(noeud.func, "attr", getattr(noeud.func, "id", None))
            in ("import_module", "__import__")
            and noeud.args
            and isinstance(noeud.args[0], ast.Constant)
            and isinstance(noeud.args[0].value, str)
        ):
            voir(noeud.args[0].value)
    return list(trouves)


def paquet_de(chemin: Path) -> str:
    return ".".join(chemin.relative_to(RACINE).parent.parts)


def test_le_parcours_voit_les_modules_du_serveur():
    noms = {chemin.relative_to(RACINE).as_posix() for chemin in MODULES_DU_SERVEUR}
    assert {
        "backend/public_api/app.py",
        "backend/public_api/routes.py",
        "backend/public_api/base.py",
        "backend/public_api/limites.py",
        "backend/public_api/__main__.py",
        "backend/db/lecture_seule.py",
        "backend/indice.py",
    } <= noms


@pytest.mark.parametrize("chemin", MODULES_DU_SERVEUR, ids=lambda p: p.relative_to(RACINE).as_posix())
def test_aucun_module_du_serveur_n_importe_ce_qui_lui_est_interdit(chemin):
    assert imports_interdits(chemin.read_text(encoding="utf-8"), paquet_de(chemin)) == []


@pytest.mark.parametrize("chemin", MODULES_DU_SERVEUR, ids=lambda p: p.relative_to(RACINE).as_posix())
def test_aucun_module_du_serveur_ne_parle_au_reseau_ni_ne_nomme_le_fournisseur(chemin):
    """La garde de la frontière du fournisseur, appliquée ici nommément."""
    from .test_frontiere_fournisseur import contacts

    assert contacts(chemin.read_text(encoding="utf-8"), paquet_de(chemin)) == []


@pytest.mark.parametrize(
    "source, attendu",
    (
        ("from backend.ingestion.universe import BENCHMARK_TICKER", ["backend.ingestion.universe"]),
        ("from backend import ingestion", ["backend.ingestion"]),
        ("import backend.data_provider", ["backend.data_provider"]),
        ("from backend.data_provider import get_provider", ["backend.data_provider"]),
        ("import requests", ["requests"]),
        ("from dotenv import load_dotenv", ["dotenv"]),
        ("def f():\n    import dotenv\n", ["dotenv"]),
        ("from backend.api.app import create_app", ["backend.api.app"]),
        ("from backend.api import app", ["backend.api.app"]),
        ("from backend.api.routes.analysis import _analyse", ["backend.api.routes.analysis"]),
        ("from ..api.routes import analysis_router", ["backend.api.routes"]),
        ("from ..api import dependencies", ["backend.api.dependencies"]),
        ("from backend.db.init_db import connect", ["backend.db.init_db"]),
        ("from ..db import migrate", ["backend.db.migrate"]),
        ("import importlib\nimportlib.import_module('backend.ingestion')", ["backend.ingestion"]),
        ("__import__('requests')", ["requests"]),
    ),
)
def test_la_garde_voit_un_import_interdit_sous_toutes_ses_formes(source, attendu):
    assert imports_interdits(source) == attendu


@pytest.mark.parametrize(
    "source",
    (
        "from backend.api.schemas import RiskOut",
        "from backend.api.validation import validate",
        "from backend.api.csv_import import read",
        "from backend.api.errors import ApiError",
        "from backend.api.langue import langue_demandee",
        "from backend.db.lecture_seule import ouvrir",
        "from backend.db.portfolios import PositionRow",
        "from backend.indice import BENCHMARK_TICKER",
        "from backend.risk_engine.engine import analyse_portfolio",
        "from .base import charger",
        "from starlette.middleware.cors import CORSMiddleware",
        "import os",
    ),
)
def test_la_garde_laisse_passer_ce_que_le_serveur_partage(source):
    assert imports_interdits(source) == []


# ═════════════════════════════════════════════ Dans un interpréteur neuf ══

SONDE = """
import json, sys
for nom in {bloques!r}:
    sys.modules[nom] = None
import {module}
print(json.dumps(sorted(nom for nom, charge in sys.modules.items() if charge is not None)))
"""


def modules_charges(module: str, bloques: tuple[str, ...] = ()) -> set[str]:
    """Tout ce qu'un interpréteur neuf a chargé après avoir importé `module`.
    Un nom de `bloques` y est rendu impossible à importer, comme un paquet
    qui n'est pas installé."""
    environnement = {
        cle: valeur for cle, valeur in os.environ.items() if not cle.startswith("MX_RISK_")
    }
    resultat = subprocess.run(
        [sys.executable, "-c", SONDE.format(bloques=bloques, module=module)],
        cwd=RACINE,
        env=environnement,
        capture_output=True,
        text=True,
    )
    assert resultat.returncode == 0, resultat.stderr[-2000:]
    return set(json.loads(resultat.stdout.strip().splitlines()[-1]))


@pytest.fixture(scope="module")
def charges_par_le_serveur() -> set[str]:
    return modules_charges("backend.public_api.app", bloques=("dotenv", "requests", "urllib3"))


def test_le_serveur_public_se_charge_sans_dotenv_ni_requests(charges_par_le_serveur):
    """Ils ne sont pas installés chez l'hébergeur : il démarre sans eux."""
    assert "backend.public_api.app" in charges_par_le_serveur
    assert "backend.public_api.routes" in charges_par_le_serveur
    assert "backend.risk_engine.engine" in charges_par_le_serveur
    assert "backend.rules.rules" in charges_par_le_serveur
    assert "backend.db.lecture_seule" in charges_par_le_serveur


def test_le_serveur_public_ne_charge_rien_de_ce_qui_lui_est_interdit(charges_par_le_serveur):
    """Par aucun chemin : ni les siens, ni ceux du moteur, des règles et des
    textes qu'il charge."""
    assert sorted(nom for nom in charges_par_le_serveur if interdit(nom)) == []


def test_le_serveur_public_ne_charge_que_ce_qu_il_partage_de_l_api_locale(charges_par_le_serveur):
    locaux = {nom for nom in charges_par_le_serveur if nom.startswith("backend.api")}
    assert locaux == {
        "backend.api",
        "backend.api.csv_import",
        "backend.api.errors",
        "backend.api.langue",
        "backend.api.schemas",
        "backend.api.validation",
    }
    base = {nom for nom in charges_par_le_serveur if nom.startswith("backend.db")}
    assert base == {"backend.db", "backend.db.lecture_seule", "backend.db.portfolios"}


def test_la_sonde_voit_ce_que_chargent_l_application_locale_et_l_ingestion():
    """Les témoins : la même sonde trouve, dans l'application locale et dans
    l'ingestion, ce que le serveur public s'interdit. C'est ce qu'elle a à
    voir."""
    locale = {nom for nom in modules_charges("backend.api.app") if interdit(nom)}
    assert {
        "dotenv",
        "backend.api.app",
        "backend.api.routes",
        "backend.api.static",
        "backend.api.dependencies",
        "backend.db.init_db",
        "backend.db.migrate",
    } <= locale
    ingestion = {nom for nom in modules_charges("backend.ingestion") if interdit(nom)}
    assert {
        "backend.ingestion",
        "backend.ingestion.prices",
        "backend.data_provider",
        "backend.data_provider.tiingo",
        "requests",
        "dotenv",
    } <= ingestion


def test_charger_le_moteur_ne_charge_plus_l_ingestion():
    """La raison du module `backend/indice.py` : avant lui, lire le ticker de
    l'indice chargeait le rattrapage des prix et le fournisseur."""
    charges = modules_charges("backend.risk_engine", bloques=("dotenv", "requests"))
    assert sorted(nom for nom in charges if interdit(nom)) == []
    assert "backend.indice" in charges


# ══════════════════════════════════════════════ L'indice, déclaré une fois ══


def test_l_indice_est_declare_une_fois_et_lu_partout():
    assert universe.BENCHMARK_TICKER is indice.BENCHMARK_TICKER
    assert universe.BENCHMARK_NAMES is indice.BENCHMARK_NAMES
    assert config.DEFAULT_BENCHMARK == indice.BENCHMARK_TICKER
    assert textes("fr").moteur.NOMS_D_INDICE is indice.BENCHMARK_NAMES
    assert indice.BENCHMARK_TICKER in indice.BENCHMARK_NAMES


def test_le_module_de_l_indice_n_importe_rien():
    source = ast.parse((RACINE / "backend" / "indice.py").read_text(encoding="utf-8"))
    importes = [
        alias.name if isinstance(noeud, ast.Import) else noeud.module
        for noeud in ast.walk(source)
        if isinstance(noeud, (ast.Import, ast.ImportFrom))
        for alias in noeud.names
    ]
    assert set(importes) == {"__future__"}


# ═══════════════════════════════════════════════════ Les dépendances ══


def epingles(fichier: str) -> dict[str, str]:
    """Chaque dépendance d'un fichier de dépendances, avec sa version."""
    trouvees = {}
    for ligne in (RACINE / fichier).read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#")[0].strip()
        if ligne:
            nom, _, version = ligne.partition("==")
            assert version, f"{fichier} : {ligne} n'est pas épinglée"
            trouvees[nom.strip().lower()] = version.strip()
    return trouvees


def test_les_dependances_du_serveur_sont_celles_de_l_application_moins_deux():
    locales, publiques = epingles("requirements.txt"), epingles("requirements-serveur.txt")
    assert set(locales) - set(publiques) == {"requests", "python-dotenv"}
    assert set(publiques) - set(locales) == set()
    assert publiques == {nom: locales[nom] for nom in publiques}


# ═════════════════════════════════════════════════ L'empreinte du code ══


@pytest.mark.parametrize(
    "chemin",
    (
        "backend/__init__.py",
        "backend/public_api/app.py",
        "backend/risk_engine/engine.py",
        "backend/textes/fr/public.py",
        "backend/db/schema.sql",
        "requirements-serveur.txt",
    ),
)
def test_un_fichier_du_code_compte_dans_l_empreinte(chemin):
    assert appartient(chemin)


@pytest.mark.parametrize(
    "chemin",
    (
        "backend/__pycache__/indice.cpython-312.pyc",
        "backend/public_api/__pycache__/app.cpython-312.pyc",
        "backend/__pycache__/intrus.py",
        "backend/intrus.pyc",
        "backend/intrus.pyo",
        "backend/notes.txt",
        "backend/db/base.sqlite",
        "requirements.txt",
        "requirements-dev.txt",
        "tools/base_serveur.py",
        "tests/test_serveur_public.py",
        "frontend/src/api/client.ts",
        "README.md",
        "autre/backend/app.py",
    ),
)
def test_le_reste_ne_compte_pas(chemin):
    assert not appartient(chemin)


def test_l_empreinte_depend_du_contenu_et_du_chemin_pas_de_l_ordre():
    fichiers = {"backend/a.py": b"a = 1\n", "backend/b.py": b"b = 2\n"}
    reference = empreinte(fichiers)
    assert len(reference) == 64
    assert empreinte(dict(reversed(list(fichiers.items())))) == reference
    assert empreinte({**fichiers, "backend/a.py": b"a = 2\n"}) != reference
    assert empreinte({"backend/c.py": b"a = 1\n", "backend/b.py": b"b = 2\n"}) != reference
    assert empreinte({**fichiers, "backend/c.py": b""}) != reference


def test_le_serveur_calcule_l_empreinte_de_tout_son_code():
    fichiers = fichiers_sur_le_disque()
    assert len(fichiers) >= 60
    assert all(appartient(chemin) for chemin in fichiers)
    assert "requirements-serveur.txt" in fichiers
    assert "backend/public_api/app.py" in fichiers
    assert empreinte_du_code() == empreinte(fichiers)


GIT = shutil.which("git")


def _git(dossier: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *arguments],
        cwd=dossier,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def depot(tmp_path) -> Path:
    """Un petit dépôt git, avec le code d'un serveur de fantaisie, commité."""
    if GIT is None:
        pytest.skip("git absent")
    fichiers = {
        "backend/__init__.py": b"",
        "backend/app.py": b"valeur = 1\n",
        "backend/db/schema.sql": b"CREATE TABLE t (a);\n",
        "backend/notes.txt": b"hors de l'ensemble\n",
        "requirements-serveur.txt": b"fastapi==0.0.0\n",
        "requirements.txt": b"requests==0.0.0\n",
        "README.md": b"# Essai\n",
    }
    for relatif, contenu in fichiers.items():
        chemin = tmp_path / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)
    _git(tmp_path, "init", "--quiet")
    # Les octets tels quels : aucune conversion de fins de ligne.
    _git(tmp_path, "config", "core.autocrlf", "false")
    _git(tmp_path, "add", "--all")
    _git(tmp_path, "commit", "--quiet", "-m", "essai")
    return tmp_path


def test_le_calcul_sur_les_objets_git_et_celui_du_disque_donnent_la_meme_empreinte(depot):
    identifiant, au_commit = empreinte_du_code_au_commit("HEAD", depot)
    assert identifiant == _git(depot, "rev-parse", "HEAD")
    assert au_commit == empreinte_du_code(depot)
    # Les trois fichiers de l'ensemble, et eux seuls.
    assert sorted(fichiers_sur_le_disque(depot)) == [
        "backend/__init__.py",
        "backend/app.py",
        "backend/db/schema.sql",
        "requirements-serveur.txt",
    ]


def test_un_pyc_pose_dans_backend_ne_change_pas_l_empreinte(depot):
    """Python en écrit dès le premier import, chez l'hébergeur comme ailleurs :
    l'empreinte du serveur démarré reste celle du commit."""
    _, au_commit = empreinte_du_code_au_commit("HEAD", depot)
    cache = depot / "backend" / "__pycache__"
    cache.mkdir()
    (cache / "app.cpython-312.pyc").write_bytes(b"\x00octets compiles")
    (cache / "intrus.py").write_bytes(b"x = 1\n")
    (depot / "backend" / "app.pyc").write_bytes(b"\x00octets compiles")
    (depot / "backend" / "db" / "__pycache__").mkdir()
    (depot / "backend" / "db" / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\x00")
    assert empreinte_du_code(depot) == au_commit

    # Commités par mégarde, ils ne compteraient pas davantage.
    _git(depot, "add", "--all", "--force")
    _git(depot, "commit", "--quiet", "-m", "des pyc")
    assert empreinte_du_code_au_commit("HEAD", depot)[1] == au_commit


def test_un_fichier_de_code_change_sur_le_disque_change_l_empreinte(depot):
    """Le témoin : ce que l'empreinte existe pour voir."""
    _, au_commit = empreinte_du_code_au_commit("HEAD", depot)
    (depot / "backend" / "app.py").write_bytes(b"valeur = 2\n")
    assert empreinte_du_code(depot) != au_commit
    # Le commit, lui, n'a pas changé : l'outil lit les objets git.
    assert empreinte_du_code_au_commit("HEAD", depot)[1] == au_commit
    (depot / "backend" / "app.py").write_bytes(b"valeur = 1\n")
    (depot / "backend" / "nouveau.py").write_bytes(b"")
    assert empreinte_du_code(depot) != au_commit


def test_un_commit_inconnu_arrete_le_calcul(depot):
    from tools.base_serveur import BaseError

    with pytest.raises(BaseError):
        empreinte_du_code_au_commit("0000000000000000000000000000000000000000", depot)


def test_chaque_fichier_suivi_sous_backend_est_dans_l_ensemble():
    """Sur le vrai dépôt : rien de ce que git suit sous `backend/` n'échappe à
    l'empreinte. Un fichier d'une autre sorte demanderait d'être classé."""
    if GIT is None or not (RACINE / ".git").exists():
        pytest.skip("pas de dépôt git ici")
    suivis = _git(RACINE, "ls-files", "backend").splitlines()
    assert len(suivis) >= 60
    assert [chemin for chemin in suivis if not appartient(chemin)] == []
