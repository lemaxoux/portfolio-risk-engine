"""L'empreinte du code que le serveur public exécute.

Le serveur est bâti depuis un dépôt privé, qui porte l'arbre d'un commit du
dépôt public. `GET /health` rend une empreinte de son code, calculée au
démarrage sur les fichiers qu'il a sous lui : quiconque a le dépôt public
calcule la même sur le commit annoncé (`python -m tools.base_serveur
--empreinte-du-code <commit>`), et compare. C'est le serveur qui parle de
lui-même ; cela ne remplace pas la vérification du dépôt privé, cela la
rejoint depuis l'extérieur.

═══ UN ENSEMBLE DE FICHIERS DÉFINI ICI, ET UNE SEULE FOIS ═══

`appartient` dit quels fichiers comptent : ceux de `backend/` dont le nom
finit par `.py` ou `.sql`, hors de tout dossier `__pycache__`, plus
`requirements-serveur.txt`. Rien d'autre. Python écrit des `.pyc` dès le
premier import, chez l'hébergeur comme ailleurs : s'ils comptaient, l'empreinte
changerait d'un démarrage à l'autre sans qu'une ligne ait changé.

Les deux calculs, celui du serveur sur le disque et celui de l'outil sur les
objets git, passent par `appartient` et par `empreinte` : ils portent sur le
même ensemble, et `tests/test_serveur_public_frontiere.py` le tient avec un
`.pyc` posé exprès.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

DOSSIER = "backend"
SUFFIXES = (".py", ".sql")
FICHIERS_HORS_DU_DOSSIER = ("requirements-serveur.txt",)
ECARTE = "__pycache__"


def appartient(chemin: str) -> bool:
    """Ce fichier compte-t-il dans l'empreinte ? `chemin` est relatif à la
    racine du dépôt, écrit avec des barres obliques."""
    if chemin in FICHIERS_HORS_DU_DOSSIER:
        return True
    parties = chemin.split("/")
    return parties[0] == DOSSIER and ECARTE not in parties and chemin.endswith(SUFFIXES)


def empreinte(contenus: Mapping[str, bytes]) -> str:
    """L'empreinte d'un ensemble de fichiers : le SHA-256 de la liste triée
    « SHA-256 du contenu, deux espaces, chemin », une ligne par fichier."""
    lignes = [
        f"{hashlib.sha256(contenu).hexdigest()}  {chemin}\n"
        for chemin, contenu in sorted(contenus.items())
    ]
    return hashlib.sha256("".join(lignes).encode("utf-8")).hexdigest()


def fichiers_sur_le_disque(racine: Path = RACINE) -> dict[str, bytes]:
    """Les fichiers de l'ensemble tels qu'ils sont sous `racine`."""
    trouves: dict[str, bytes] = {}
    for chemin in sorted((racine / DOSSIER).rglob("*")):
        relatif = chemin.relative_to(racine).as_posix()
        if chemin.is_file() and appartient(relatif):
            trouves[relatif] = chemin.read_bytes()
    for nom in FICHIERS_HORS_DU_DOSSIER:
        trouves[nom] = (racine / nom).read_bytes()
    return trouves


def empreinte_du_code(racine: Path = RACINE) -> str:
    """L'empreinte du code sous `racine` : ce que le serveur exécute."""
    return empreinte(fichiers_sur_le_disque(racine))
