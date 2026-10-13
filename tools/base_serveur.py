"""Bâtit la base du serveur public.

    python -m tools.base_serveur --sortie ..\\serveur-prive\\base\\serveur.sqlite

Le serveur public (`backend/public_api/`) analyse le portefeuille qu'un
visiteur du site compose parmi les titres de la base figée. Cet outil écrit
cette base : la base locale, coupée à la date du gel, sans aucun portefeuille.

═══ CE QU'IL FAIT ═══

1. Il COPIE la source. Elle n'est jamais ouverte par SQLite, ni pour lire ni
   pour écrire : elle est lue comme un fichier, et son empreinte est relevée
   avant et après.
2. Il coupe la copie à `DATE_GEL`, par la règle de `tests/conftest.py`, celle
   de `tools/export_demo.py` : les mesures du serveur sont celles de la
   démonstration, et celles que les tests recalculent.
3. Il vide les portefeuilles et les positions, et remet leurs compteurs à
   zéro : aucun portefeuille de la base locale ne sort.
4. Il réécrit le fichier (`VACUUM`) : les lignes supprimées ne restent pas
   dans ses pages libres.
5. Il vérifie ce qu'il vient d'écrire, puis écrit à côté l'empreinte SHA-256
   du fichier (`<sortie>.sha256`). Le serveur refuse de démarrer sur une base
   qui n'a pas cette empreinte.

═══ LA MÊME BASE SOURCE QUE L'EXPORT DE LA DÉMONSTRATION ═══

La démonstration publie des analyses enregistrées ; le serveur en calcule
d'autres, sur la même page. Les deux doivent décrire les mêmes cours.
L'empreinte attendue de la source n'est donc pas écrite ici : elle se lit dans
le manifeste de l'export (`demo/export/manifeste.json`, `base_source_md5`).
Une source qui a changé depuis l'export arrête la commande : refaire l'export
d'abord, ou garder la base qui lui a servi.

═══ LA BASE NE S'ÉCRIT PAS DANS LE DÉPÔT ═══

`--sortie` est obligatoire, sans défaut, et un chemin sous la racine du dépôt
est refusé. La base du serveur vit dans un autre dépôt, privé.

═══ REPRODUCTIBLE SUR UN POSTE ═══

Deux constructions de la même source donnent le même fichier. D'un poste à
l'autre, ce n'est pas garanti : `VACUUM` écrit ce que sa version de SQLite
écrit. L'empreinte date un fichier, elle n'est pas une recette.

═══ L'EMPREINTE DU CODE D'UN COMMIT ═══

    python -m tools.base_serveur --empreinte-du-code [COMMIT]

Le serveur public dit, dans `GET /health`, l'empreinte du code qu'il exécute
(`backend/public_api/empreinte.py`). Cette commande calcule la même sur un
commit du dépôt, lue dans les OBJETS git et non dans l'arbre de travail : ce
que le commit contient, pas ce qu'un poste en a fait. Les deux calculs
portent sur le même ensemble de fichiers, défini une seule fois.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from tools.export_demo import DATE_GEL

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "data" / "mx_risk.sqlite"
MANIFESTE = RACINE / "demo" / "export" / "manifeste.json"
SUFFIXE_DE_L_EMPREINTE = ".sha256"

COMMANDE = "python -m tools.base_serveur"
COMMANDE_D_EXPORT = "python -m tools.export_demo"


class BaseError(Exception):
    """La base est refusée : rien n'est écrit à l'emplacement de sortie."""


def _md5(chemin: Path) -> str:
    return hashlib.md5(chemin.read_bytes()).hexdigest()


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def md5_de_l_export(manifeste: Path = MANIFESTE) -> str:
    """L'empreinte de la base source de l'export de la démonstration, lue
    dans son manifeste."""
    try:
        document = json.loads(manifeste.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BaseError(
            f"Manifeste de l'export illisible ({manifeste}) : {exc}. "
            f"Faire l'export d'abord : {COMMANDE_D_EXPORT}"
        ) from exc
    empreinte = document.get("base_source_md5") if isinstance(document, dict) else None
    if not isinstance(empreinte, str) or len(empreinte) != 32:
        raise BaseError(f"Le manifeste ne donne pas `base_source_md5` ({manifeste}).")
    return empreinte


def _dans_le_depot(chemin: Path, racine: Path) -> bool:
    return chemin == racine or racine in chemin.parents


def _couper(conn: sqlite3.Connection) -> None:
    """La coupe au gel, et aucun portefeuille."""
    with conn:
        # La règle de `tests/conftest.py`, mot pour mot.
        conn.execute("DELETE FROM prices WHERE date > ?", (DATE_GEL,))
        conn.execute("DELETE FROM positions")
        conn.execute("DELETE FROM portfolios")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('portfolios', 'positions')")


def _compacter(conn: sqlite3.Connection) -> None:
    """Réécrit le fichier sans ses pages libres : ce qui a été supprimé n'y
    reste pas lisible."""
    conn.execute("VACUUM")


def _verifier(conn: sqlite3.Connection) -> dict[str, object]:
    """Ce que la base doit dire avant d'être livrée."""
    portefeuilles = conn.execute("SELECT COUNT(*) FROM portfolios").fetchone()[0]
    positions = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
    if portefeuilles or positions:
        raise BaseError("Il reste des portefeuilles ou des positions dans la base.")
    derniere = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    if derniere != DATE_GEL:
        raise BaseError(f"La dernière séance est le {derniere}, pas le {DATE_GEL}.")
    sans_prix = [
        ticker
        for (ticker,) in conn.execute(
            "SELECT s.ticker FROM securities s "
            "WHERE NOT EXISTS (SELECT 1 FROM prices p WHERE p.ticker = s.ticker) "
            "ORDER BY s.ticker"
        )
    ]
    if sans_prix:
        raise BaseError(f"Titres sans aucun prix : {', '.join(sans_prix)}.")
    return {
        "titres": conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0],
        "seances": conn.execute("SELECT COUNT(DISTINCT date) FROM prices").fetchone()[0],
        "premiere_seance": conn.execute("SELECT MIN(date) FROM prices").fetchone()[0],
    }


def construire(
    source: Path,
    sortie: Path,
    *,
    md5_attendu: str,
    racine: Path = RACINE,
) -> dict[str, object]:
    """Écrit la base du serveur dans `sortie`, son empreinte à côté, et rend
    ce qu'il a constaté.

    `md5_attendu` est l'empreinte que la source doit avoir : celle de la base
    qui a servi à l'export de la démonstration. Rien n'est écrit à
    l'emplacement de sortie avant que tout soit vérifié.
    """
    sortie = sortie.resolve()
    if _dans_le_depot(sortie, racine.resolve()):
        raise BaseError(
            f"La base du serveur ne s'écrit pas dans le dépôt ({sortie}). "
            "Désigner un emplacement hors de lui."
        )
    if not source.is_file():
        raise BaseError(f"Base source absente : {source}")
    if _md5(source) != md5_attendu:
        raise BaseError(
            f"La base source n'est pas celle de l'export de la démonstration : "
            f"md5 {_md5(source)} au lieu de {md5_attendu}."
        )

    sortie.parent.mkdir(parents=True, exist_ok=True)
    brouillon = sortie.with_name(sortie.name + ".brouillon")
    brouillon.unlink(missing_ok=True)
    try:
        # `copyfile` et non `copy` : le contenu seul, pas la lecture seule
        # d'une source protégée.
        shutil.copyfile(source, brouillon)
        with closing(sqlite3.connect(brouillon)) as conn:
            _couper(conn)
            _compacter(conn)
            constate = _verifier(conn)

        # Une écriture dans la source pendant la construction donnerait la
        # base d'un autre état que celui de l'export.
        if _md5(source) != md5_attendu:
            raise BaseError("La base source a changé pendant la construction. Relancer : " + COMMANDE)

        empreinte = _sha256(brouillon)
        os.replace(brouillon, sortie)
    finally:
        brouillon.unlink(missing_ok=True)

    temoin = sortie.with_name(sortie.name + SUFFIXE_DE_L_EMPREINTE)
    temoin.write_bytes(f"{empreinte}\n".encode("ascii"))
    return {
        "sortie": str(sortie),
        "sha256": empreinte,
        "octets": sortie.stat().st_size,
        "date_gel": DATE_GEL,
        "base_source_md5": md5_attendu,
        **constate,
    }


def _git(racine: Path, *arguments: str, entree: bytes | None = None) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=racine,
            input=entree,
            capture_output=True,
            check=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BaseError(f"git {' '.join(arguments[:2])} a échoué dans {racine} : {exc}") from exc


def empreinte_du_code_au_commit(commit: str = "HEAD", racine: Path = RACINE) -> tuple[str, str]:
    """L'identifiant complet du commit, et l'empreinte de son code : celle que
    le serveur public annonce quand il sert ce commit.

    Les fichiers sont lus dans les objets git (`git cat-file`), et choisis par
    la règle du serveur (`appartient`).
    """
    # Import local : lire `DATE_GEL` ou bâtir une base ne charge pas le
    # serveur public.
    from backend.public_api.empreinte import appartient, empreinte

    identifiant = _git(racine, "rev-parse", "--verify", f"{commit}^{{commit}}").decode("ascii").strip()
    chemins = _git(racine, "ls-tree", "-r", "--name-only", "-z", identifiant).decode("utf-8").split("\0")
    retenus = sorted(chemin for chemin in chemins if chemin and appartient(chemin))
    demande = "".join(f"{identifiant}:{chemin}\n" for chemin in retenus).encode("utf-8")
    brut = _git(racine, "cat-file", "--batch", entree=demande)

    # Pour chaque objet : une ligne « identifiant blob taille », le contenu,
    # puis un saut de ligne.
    contenus: dict[str, bytes] = {}
    curseur = 0
    for chemin in retenus:
        fin = brut.index(b"\n", curseur)
        _, genre, taille = brut[curseur:fin].split()
        if genre != b"blob":
            raise BaseError(f"{chemin} n'est pas un fichier dans {identifiant}.")
        debut = fin + 1
        contenus[chemin] = brut[debut : debut + int(taille)]
        curseur = debut + int(taille) + 1
    return identifiant, empreinte(contenus)


def main(arguments: Sequence[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(
        prog=COMMANDE, description="Bâtit la base du serveur public, hors du dépôt."
    )
    lecteur.add_argument("--sortie", type=Path, default=None, help="le fichier écrit, hors du dépôt")
    lecteur.add_argument(
        "--empreinte-du-code",
        nargs="?",
        const="HEAD",
        default=None,
        metavar="COMMIT",
        help="affiche l'empreinte du code du serveur à ce commit (HEAD par défaut), sans rien bâtir",
    )
    lecteur.add_argument("--source", type=Path, default=SOURCE, help="la base à copier")
    lecteur.add_argument(
        "--manifeste",
        type=Path,
        default=MANIFESTE,
        help="le manifeste de l'export, qui dit l'empreinte attendue de la source",
    )
    choix = lecteur.parse_args(arguments)

    if choix.empreinte_du_code is not None:
        try:
            identifiant, code = empreinte_du_code_au_commit(choix.empreinte_du_code)
        except BaseError as exc:
            print(f"Empreinte refusée : {exc}", file=sys.stderr)
            return 1
        print(f"Commit : {identifiant}")
        print(f"Empreinte du code (code_sha256) : {code}")
        return 0

    # Aucun emplacement n'est supposé : sans `--sortie`, la commande s'arrête.
    if choix.sortie is None:
        lecteur.error("--sortie est obligatoire : la base du serveur s'écrit hors du dépôt.")

    try:
        bilan = construire(
            choix.source, choix.sortie, md5_attendu=md5_de_l_export(choix.manifeste)
        )
    except BaseError as exc:
        print(f"Base refusée : {exc}", file=sys.stderr)
        return 1

    print(f"Base du serveur : {bilan['sortie']}")
    print(f"SHA-256 : {bilan['sha256']}")
    print(
        f"{bilan['octets']} octets ; {bilan['titres']} titres ; {bilan['seances']} séances, "
        f"du {bilan['premiere_seance']} au {bilan['date_gel']}"
    )
    print(f"Base source (md5) : {bilan['base_source_md5']}, celle de l'export de la démonstration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
