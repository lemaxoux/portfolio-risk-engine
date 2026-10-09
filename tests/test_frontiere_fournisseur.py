"""Seul `backend/data_provider` parle au fournisseur de prix.

ARCHITECTURE.md, « Module boundaries » : cette frontière reposait sur une
convention. Ce test lit chaque module de `backend/` hors de
`backend/data_provider/` et échoue sur ce qui donnerait à un autre module un
accès au fournisseur :

* l'import d'une bibliothèque réseau (`requests`, `httpx`, `urllib`,
  `urllib3`, `aiohttp`, `socket`, `http.client`), sous toutes ses formes ;
* l'import d'un sous-module du fournisseur (`backend.data_provider.tiingo`,
  `.base`) : seule la façade `backend.data_provider` est admise, ce que dit sa
  docstring ;
* l'import dynamique des mêmes modules, par leur nom ;
* le domaine du fournisseur, lu dans l'adresse de son API, n'importe où dans le
  texte du module.

LE DOMAINE SE CHERCHE DANS TOUT LE TEXTE, docstrings et commentaires compris,
au contraire des gardes de `test_api_discipline.py`. Une adresse n'est pas un
motif qu'un module citerait pour dire qu'il se l'interdit : la nommer, c'est
déjà connaître le fournisseur. Le nom « Tiingo » seul reste admis.

Chaque forme a ses témoins, dans les deux sens : une garde qu'on n'a jamais vue
échouer ne prouve rien.
"""

from __future__ import annotations

import ast
import pkgutil
from pathlib import Path
from urllib.parse import urlsplit

import pytest

import backend.data_provider as fournisseur
from backend.data_provider.tiingo import BASE_URL

RACINE = Path(__file__).resolve().parents[1]

RESEAU = ("requests", "httpx", "urllib", "urllib3", "aiohttp", "socket", "http.client")
FACADE = "backend.data_provider"
SOUS_MODULES = frozenset(module.name for module in pkgutil.iter_modules(fournisseur.__path__))
# Le domaine enregistré de l'adresse de l'API : ses deux derniers niveaux.
DOMAINE = ".".join(urlsplit(BASE_URL).hostname.split(".")[-2:])


def raison(nom: str) -> str | None:
    """Pourquoi importer le module `nom` donnerait accès au fournisseur, ou
    None."""
    for reseau in RESEAU:
        if nom == reseau or nom.startswith(reseau + "."):
            return "une bibliothèque réseau"
    parties = nom.split(".")
    if nom.startswith(FACADE + ".") and parties[2] in SOUS_MODULES:
        return "un sous-module du fournisseur, hors de sa façade"
    return None


def contacts(source: str, paquet: str = "backend") -> list[str]:
    """Ce qui, dans un module du paquet `paquet`, parle au fournisseur ou s'en
    donne le moyen : imports absolus et relatifs, faits au chargement ou dans
    une fonction, imports dynamiques par leur nom, et le domaine du
    fournisseur dans le texte."""
    fautes: dict[str, None] = {}

    def voir(nom: str) -> bool:
        pourquoi = raison(nom)
        if pourquoi:
            fautes[f"importe {nom} : {pourquoi}"] = None
        return pourquoi is not None

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
            # « from http import client » importe http.client ; « from
            # backend.data_provider import tiingo », le sous-module.
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
    if DOMAINE in source.lower():
        fautes[f"nomme le domaine du fournisseur, {DOMAINE}"] = None
    return list(fautes)


def modules_hors_du_fournisseur(racine: Path) -> list[Path]:
    dossier = racine / "backend" / "data_provider"
    return sorted(
        chemin
        for chemin in (racine / "backend").rglob("*.py")
        if "__pycache__" not in chemin.parts and dossier not in chemin.parents
    )


def paquet_de(chemin: Path, racine: Path) -> str:
    return ".".join(chemin.relative_to(racine).parent.parts)


def fautes_dans(racine: Path) -> dict[str, list[str]]:
    return {
        chemin.relative_to(racine).as_posix(): fautes
        for chemin in modules_hors_du_fournisseur(racine)
        if (fautes := contacts(chemin.read_text(encoding="utf-8"), paquet_de(chemin, racine)))
    }


# ═══════════════════════════════════════════════════════ La frontière ══


def test_seul_data_provider_parle_au_fournisseur():
    modules = modules_hors_du_fournisseur(RACINE)
    relatifs = {chemin.relative_to(RACINE).as_posix() for chemin in modules}
    assert len(modules) >= 50, "le parcours ne voit pas le serveur"
    # Le module qui importe la façade est bien lu, et le fournisseur ne l'est pas.
    assert "backend/ingestion/prices.py" in relatifs
    assert not any(relatif.startswith("backend/data_provider/") for relatif in relatifs)
    assert fautes_dans(RACINE) == {}


def test_l_adaptateur_lui_meme_serait_releve():
    """Le détecteur voit ce qu'il doit voir sur le vrai adaptateur, que le
    parcours écarte : `requests` et le domaine."""
    source = (RACINE / "backend" / "data_provider" / "tiingo.py").read_text(encoding="utf-8")
    fautes = contacts(source, "backend.data_provider")
    assert "importe requests : une bibliothèque réseau" in fautes
    assert f"nomme le domaine du fournisseur, {DOMAINE}" in fautes


def test_le_domaine_et_les_sous_modules_sont_lus_dans_le_fournisseur():
    assert DOMAINE == "tiingo.com"
    assert SOUS_MODULES == {"base", "tiingo"}


# ═══════════════════════════════════════════════════════ Les témoins ══


@pytest.mark.parametrize(
    "source",
    (
        "import requests",
        "import requests.adapters",
        "from requests import Session",
        "import httpx",
        "import urllib.request",
        "from urllib import parse",
        "from urllib.request import urlopen",
        "import urllib3",
        "import aiohttp",
        "import socket",
        "import http.client",
        "from http import client",
        "from http.client import HTTPSConnection",
        "def f():\n    import requests\n",
        "import importlib\nimportlib.import_module('requests')",
        "__import__('socket')",
    ),
)
def test_une_bibliotheque_reseau_est_relevee(source):
    assert contacts(source) and all("bibliothèque réseau" in f for f in contacts(source))


@pytest.mark.parametrize(
    "source",
    (
        "from backend.data_provider.tiingo import TiingoProvider",
        "from backend.data_provider.base import DailyBar",
        "import backend.data_provider.tiingo",
        "from backend.data_provider import tiingo",
        "from backend.data_provider import base",
        "from ..data_provider import tiingo",
        "from ..data_provider.tiingo import FREE_TIER_CALLS_PER_HOUR",
        "import importlib\nimportlib.import_module('backend.data_provider.tiingo')",
    ),
)
def test_un_sous_module_du_fournisseur_est_releve(source):
    fautes = contacts(source, "backend.ingestion")
    assert fautes and all("hors de sa façade" in f for f in fautes)


@pytest.mark.parametrize(
    "source",
    (
        'ADRESSE = "https://api.tiingo.com/tiingo/daily"',
        'url = f"https://api.TIINGO.com/{chemin}"',
        '"""Interroge api.tiingo.com."""',
        "# voir https://www.tiingo.com/documentation",
    ),
)
def test_le_domaine_est_releve_partout_dans_le_texte(source):
    assert contacts(source) == [f"nomme le domaine du fournisseur, {DOMAINE}"]


@pytest.mark.parametrize(
    "source",
    (
        "from backend.data_provider import get_daily_adjusted, get_provider",
        "from backend.data_provider import HOURLY_CALL_BUDGET",
        "import backend.data_provider",
        "from backend import data_provider",
        "from .. import data_provider",
        "from ..data_provider import ProviderError",
        "import json",
        "import http",
        "from http import HTTPStatus",
        'logging.getLogger("urllib3").setLevel(logging.WARNING)',
        'logger.error("%s : quota du fournisseur épuisé", ticker)',
        '"""Ce module ne connaît pas Tiingo."""',
        "import importlib\nimportlib.import_module('json')",
    ),
)
def test_ce_qui_ne_parle_pas_au_fournisseur_est_laisse(source):
    assert contacts(source, "backend.ingestion") == []


def test_le_parcours_ecarte_le_fournisseur_et_lui_seul(tmp_path):
    """Un arbre factice : le même import est admis dans le fournisseur et
    relevé ailleurs ; le domaine dans un commentaire est relevé aussi."""
    fichiers = {
        "backend/data_provider/x.py": "import requests\n",
        "backend/ingestion/y.py": "import requests\n",
        "backend/rules/z.py": "# voir https://api.tiingo.com\n",
        "backend/rules/sain.py": "from backend.data_provider import get_provider\n",
    }
    for relatif, texte in fichiers.items():
        chemin = tmp_path / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
    assert fautes_dans(tmp_path) == {
        "backend/ingestion/y.py": ["importe requests : une bibliothèque réseau"],
        "backend/rules/z.py": [f"nomme le domaine du fournisseur, {DOMAINE}"],
    }
