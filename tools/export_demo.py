"""Écrit les réponses de l'API que lit la démonstration statique.

    python -m tools.export_demo            # écrit demo/export/

La démonstration est le client, servi sans serveur : il y lit des réponses de
l'API enregistrées en fichiers au lieu d'appeler l'API. Cet outil les
enregistre. Il ne calcule rien et ne rédige rien : chaque fichier porte les
OCTETS d'une réponse de l'application telle qu'elle est (`create_app()`,
interrogée en mémoire).

═══ CE QU'IL FAIT ═══

1. Il COPIE la base, une copie par langue. La source n'est jamais ouverte par
   SQLite, ni pour lire ni pour écrire : elle est lue comme un fichier, et son
   empreinte est relevée avant et après.
2. Il coupe chaque copie à `DATE_GEL`, par la règle de `tests/conftest.py` :
   les mesures de la démonstration sont celles que les tests recalculent.
3. Il vide les portefeuilles et les positions de la copie, et remet leurs
   compteurs à zéro : aucun portefeuille de la base ne sort, et ceux de la
   démonstration portent les numéros 1, 2, 3, dans l'ordre du fichier de
   compositions (`demo/compositions.json`).
4. Il crée les portefeuilles de ce fichier, sous leur nom dans la langue de
   la copie, puis interroge l'application : l'écran d'acceptation, la liste,
   et l'analyse de chacun. Rien d'autre n'est exporté.
5. Il vérifie ce qu'il vient de recevoir, écrit les fichiers et leur
   manifeste (`manifeste.json` : la date du gel, l'empreinte de la source, le
   commit, chaque fichier avec son SHA-256).

═══ UN NOM PAR LANGUE, SANS TOUCHER À L'API ═══

Le nom d'un portefeuille est une donnée : le serveur le rend tel qu'il est en
base, il ne le traduit pas. D'où une copie par langue. Les deux reçoivent les
mêmes compositions dans le même ordre, donc les mêmes numéros ; seul le nom
diffère. Les fichiers `fr/` viennent de la copie française interrogée avec
`lang=fr`, les fichiers `en/` de la copie anglaise avec `lang=en`.

═══ `updated_at` RESTE NUL ═══

Les positions sont écrites dans la copie par cet outil, pas par l'application :
passer par `PUT /positions` les daterait du jour de l'export, donc après leur
valorisation, et l'export changerait d'un jour à l'autre. La colonne reste à
NULL, qui se lit « jamais modifié depuis l'application » (`db/schema.sql`), ce
qui est le cas. Les contrôles de l'application servent quand même : le nom
passe par `PortfolioCreate`, les lignes par `api.validation.validate`.

═══ AUCUNE COMBINAISON N'ISOLE UN TITRE ═══

La démonstration publie des mesures de portefeuilles, jamais la série d'un
titre. `series.returns` est à poids constants (`returns.portfolio_returns`),
et `series.wealth` en est le produit cumulé : une combinaison linéaire des
séries de plusieurs portefeuilles est la série du portefeuille dont les poids
sont la même combinaison. Si le vecteur unitaire d'un titre est dans l'espace
qu'engendrent les lignes de la matrice des poids, les fichiers publiés
redonnent donc la série de ce titre. `titres_isoles` le refuse.

Le contrôle porte sur les NOMBRES DE TITRES, des entiers, en arithmétique
exacte, et il vaut pour les poids : le poids d'une ligne est son nombre de
titres, fois son prix, divisé par la valeur du portefeuille. Tant qu'un titre a
le même prix, strictement positif, d'un portefeuille à l'autre, les deux
matrices ont les mêmes vecteurs unitaires dans leur espace de lignes.
`verifier_export` tient ces deux conditions sur les fichiers. Des poids
arrondis, eux, demanderaient une tolérance, et une dépendance exacte entre
nombres de titres n'y serait plus qu'approchée.

═══ REPRODUCTIBLE ═══

Deux exports de la même source au même commit écrivent les mêmes octets : pas
d'horodatage dans le manifeste, et l'application rend la même réponse d'un
appel à l'autre.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from backend.db import portfolios as store
from backend.db.init_db import connect

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "data" / "mx_risk.sqlite"
COMPOSITIONS = RACINE / "demo" / "compositions.json"
SORTIE = RACINE / "demo" / "export"

# La dernière séance de la démonstration : celle de `tests/conftest.py`, que
# `tests/test_export_demo.py` tient égale. Un outil n'importe pas les tests.
DATE_GEL = "2026-09-09"

LANGUES = ("fr", "en")
MANIFESTE = "manifeste.json"
VARIABLE_BASE = "MX_RISK_DB_PATH"

COMMANDE = "python -m tools.export_demo"


class ExportError(Exception):
    """L'export est refusé : rien n'est écrit dans le dossier de sortie."""


# ══════════════════════════════════════════════════════════ Compositions ══


@dataclass(frozen=True)
class Composition:
    """Un portefeuille de la démonstration : son nom dans chaque langue, et
    ses lignes en nombres de titres."""

    noms: Mapping[str, str]
    positions: Mapping[str, int]


def _sans_doublon(paires: list[tuple[str, object]]) -> dict[str, object]:
    """Un objet JSON dont une clé revient est refusé : `json` garderait la
    dernière sans rien dire, et une ligne écrite deux fois se lirait une."""
    objet: dict[str, object] = {}
    for cle, valeur in paires:
        if cle in objet:
            raise ExportError(f"Compositions : la clé « {cle} » est écrite deux fois.")
        objet[cle] = valeur
    return objet


def lire_compositions(chemin: Path = COMPOSITIONS) -> tuple[Composition, ...]:
    """Les portefeuilles de la démonstration, dans l'ordre de leurs numéros."""
    try:
        document = json.loads(
            chemin.read_text(encoding="utf-8"), object_pairs_hook=_sans_doublon
        )
    except (OSError, ValueError) as exc:
        raise ExportError(f"Compositions illisibles ({chemin}) : {exc}") from exc

    decrits = document.get("portefeuilles") if isinstance(document, dict) else None
    if not isinstance(decrits, list) or not decrits:
        raise ExportError("Compositions : une liste « portefeuilles » non vide est attendue.")

    jeu: list[Composition] = []
    for rang, decrit in enumerate(decrits, start=1):
        noms = decrit.get("nom") if isinstance(decrit, dict) else None
        positions = decrit.get("positions") if isinstance(decrit, dict) else None
        if not isinstance(noms, dict) or sorted(noms) != sorted(LANGUES):
            raise ExportError(
                f"Compositions, portefeuille {rang} : un nom par langue "
                f"({', '.join(LANGUES)}), et rien d'autre."
            )
        if not all(isinstance(nom, str) and nom.strip() for nom in noms.values()):
            raise ExportError(f"Compositions, portefeuille {rang} : un nom est vide.")
        if not isinstance(positions, dict) or not positions:
            raise ExportError(f"Compositions, portefeuille {rang} : aucune ligne.")
        for ticker, nombre in positions.items():
            # `bool` est un `int` pour Python : `true` ne vaut pas un titre.
            if isinstance(nombre, bool) or not isinstance(nombre, int) or nombre <= 0:
                raise ExportError(
                    f"Compositions, portefeuille {rang}, {ticker} : le nombre de "
                    f"titres est un entier strictement positif, pas {nombre!r}."
                )
        jeu.append(Composition(noms=dict(noms), positions=dict(positions)))
    return tuple(jeu)


# ═════════════════════════════════════════════════ La règle d'isolement ══


def _rang(lignes: Sequence[Sequence[Fraction]]) -> int:
    """Le rang d'une matrice de fractions, par élimination de Gauss exacte."""
    matrice = [list(ligne) for ligne in lignes]
    rang = 0
    colonnes = len(matrice[0]) if matrice else 0
    for colonne in range(colonnes):
        pivot = next(
            (i for i in range(rang, len(matrice)) if matrice[i][colonne] != 0), None
        )
        if pivot is None:
            continue
        matrice[rang], matrice[pivot] = matrice[pivot], matrice[rang]
        for i in range(len(matrice)):
            if i != rang and matrice[i][colonne] != 0:
                facteur = matrice[i][colonne] / matrice[rang][colonne]
                matrice[i] = [a - facteur * b for a, b in zip(matrice[i], matrice[rang])]
        rang += 1
    return rang


def titres_isoles(portefeuilles: Sequence[Mapping[str, int]]) -> list[str]:
    """Les titres qu'une combinaison linéaire des portefeuilles isole.

    Un titre est isolé quand son vecteur unitaire est dans l'espace des lignes
    de la matrice des nombres de titres : ajouter ce vecteur aux lignes ne
    change alors pas le rang. Arithmétique exacte, aucune tolérance. Un
    portefeuille à une ligne isole sa ligne ; deux portefeuilles qui ne
    diffèrent que d'une ligne isolent celle-là.
    """
    titres = sorted({ticker for lignes in portefeuilles for ticker in lignes})
    matrice = [
        [Fraction(lignes.get(ticker, 0)) for ticker in titres] for lignes in portefeuilles
    ]
    rang = _rang(matrice)
    isoles = []
    for colonne, ticker in enumerate(titres):
        unitaire = [Fraction(int(i == colonne)) for i in range(len(titres))]
        if _rang([*matrice, unitaire]) == rang:
            isoles.append(ticker)
    return isoles


def verifier_isolement(jeu: Sequence[Composition]) -> None:
    isoles = titres_isoles([composition.positions for composition in jeu])
    if isoles:
        raise ExportError(
            "Une combinaison de ces portefeuilles isole "
            f"{', '.join(isoles)} : leurs séries publiées redonneraient celle "
            "du titre. Les compositions sont refusées."
        )


# ══════════════════════════════════════════════════════════ Les copies ══


def _md5(chemin: Path) -> str:
    return hashlib.md5(chemin.read_bytes()).hexdigest()


def _copier(source: Path, copie: Path) -> str:
    """Copie la source et rend l'empreinte de la copie, avant toute écriture.

    `copyfile` et non `copy` : le contenu seul. Une source en lecture seule
    donnerait sinon une copie en lecture seule, que la suite ne pourrait pas
    couper.
    """
    copie.unlink(missing_ok=True)
    shutil.copyfile(source, copie)
    return _md5(copie)


def _preparer(copie: Path, jeu: Sequence[Composition], langue: str) -> None:
    """Coupe la copie au gel, la vide de ses portefeuilles, crée ceux de la
    démonstration sous leur nom dans `langue`."""
    # Imports locaux, comme `tools/openapi_schema` : lire `DATE_GEL` ou
    # appeler `titres_isoles` ne fait pas payer FastAPI et pydantic.
    from backend.api.schemas import PortfolioCreate
    from backend.api.validation import SubmittedPosition, validate
    from backend.risk_engine.portfolio import load_securities

    with closing(connect(copie)) as conn:
        with conn:
            # La règle de `tests/conftest.py`, mot pour mot.
            conn.execute("DELETE FROM prices WHERE date > ?", (DATE_GEL,))
            conn.execute("DELETE FROM positions")
            conn.execute("DELETE FROM portfolios")
            # Sans cela, la clé AUTOINCREMENT reprendrait après le dernier
            # numéro que la base a connu.
            conn.execute(
                "DELETE FROM sqlite_sequence WHERE name IN ('portfolios', 'positions')"
            )
        # Les lignes supprimées restent lisibles dans les pages libres du
        # fichier : la copie est réécrite sans elles.
        conn.execute("VACUUM")

        catalogue = load_securities(conn)
        for rang, composition in enumerate(jeu, start=1):
            retenues, problemes = validate(
                [
                    SubmittedPosition(ticker=ticker, quantity=nombre)
                    for ticker, nombre in composition.positions.items()
                ],
                catalogue,
            )
            if problemes:
                raise ExportError(
                    f"Compositions, portefeuille {rang} : "
                    + " ".join(probleme.problem for probleme in problemes)
                )
            # `store.create` laisse `updated_at` à NULL. Les lignes sont
            # écrites par l'INSERT de `store.replace_positions`, sans la date
            # qu'il pose ensuite.
            cree = store.create(conn, PortfolioCreate(name=composition.noms[langue]).name)
            if cree.id != rang:
                raise ExportError(
                    f"Le portefeuille {rang} a reçu le numéro {cree.id} : la "
                    "copie n'a pas été vidée."
                )
            with conn:
                conn.executemany(
                    """
                    INSERT INTO positions (portfolio_id, ticker, quantity, cost_basis)
                    VALUES (?, ?, ?, ?)
                    """,
                    [(cree.id, p.ticker, p.quantity, p.cost_basis) for p in retenues],
                )


@contextmanager
def _base_designee(copie: Path) -> Iterator[None]:
    """`MX_RISK_DB_PATH` sur la copie le temps des appels, puis rendue."""
    avant = os.environ.get(VARIABLE_BASE)
    os.environ[VARIABLE_BASE] = str(copie)
    try:
        yield
    finally:
        if avant is None:
            os.environ.pop(VARIABLE_BASE, None)
        else:
            os.environ[VARIABLE_BASE] = avant


def _interroger(copie: Path, jeu: Sequence[Composition], langue: str) -> dict[str, bytes]:
    """Les réponses de l'application sur la copie, par chemin de fichier."""
    from fastapi.testclient import TestClient

    from backend.api.app import create_app

    def lire(client: TestClient, adresse: str) -> bytes:
        reponse = client.get(adresse)
        nature = reponse.headers.get("content-type", "")
        if reponse.status_code != 200 or not nature.startswith("application/json"):
            raise ExportError(
                f"{adresse} a répondu {reponse.status_code} ({nature}) : "
                f"{reponse.text[:300]}"
            )
        return reponse.content

    fichiers: dict[str, bytes] = {}
    with _base_designee(copie):
        # En gestionnaire de contexte : le `lifespan` de l'application
        # contrôle le schéma de la copie avant le premier appel.
        with TestClient(create_app()) as client:
            fichiers[f"{langue}/disclaimer.json"] = lire(
                client, f"/api/disclaimer?lang={langue}"
            )
            fichiers[f"{langue}/portfolios.json"] = lire(
                client, f"/api/portfolios?lang={langue}"
            )
            for rang in range(1, len(jeu) + 1):
                fichiers[f"{langue}/portfolios/{rang}/analysis.json"] = lire(
                    client, f"/api/portfolios/{rang}/analysis?lang={langue}"
                )
    return fichiers


# ═══════════════════════════════════════════════════════ Vérifications ══


def _refuser_constante(nom: str) -> float:
    raise ValueError(f"{nom} n'est pas du JSON")


def json_strict(octets: bytes) -> object:
    """Le document, lu comme le lira `JSON.parse` : ni NaN ni Infinity."""
    return json.loads(octets.decode("utf-8"), parse_constant=_refuser_constante)


def verifier_export(fichiers: Mapping[str, bytes], jeu: Sequence[Composition]) -> None:
    """Ce que les fichiers doivent dire avant d'être écrits.

    La liste ne contient que les portefeuilles des compositions ; chacun est
    valorisé au gel ; et les deux conditions qui font valoir la règle
    d'isolement pour les poids sont tenues : un titre a le même prix,
    strictement positif, dans tous les portefeuilles, et toutes les séries
    portent les mêmes dates.
    """
    prix: dict[str, set[float]] = {}
    dates: set[tuple[str, ...]] = set()

    for langue in LANGUES:
        liste = json_strict(fichiers[f"{langue}/portfolios.json"])
        json_strict(fichiers[f"{langue}/disclaimer.json"])
        if not isinstance(liste, list) or len(liste) != len(jeu):
            raise ExportError(f"{langue} : la liste ne porte pas {len(jeu)} portefeuilles.")

        for rang, (publie, composition) in enumerate(zip(liste, jeu), start=1):
            ou = f"{langue}, portefeuille {rang}"
            if publie["id"] != rang or publie["name"] != composition.noms[langue]:
                raise ExportError(f"{ou} : ce n'est pas celui des compositions.")
            if publie["updated_at"] is not None:
                raise ExportError(f"{ou} : `updated_at` devait rester nul.")
            lignes = {p["ticker"]: p["quantity"] for p in publie["positions"]}
            if lignes != composition.positions:
                raise ExportError(f"{ou} : ses lignes ne sont pas celles des compositions.")
            valorisation = publie["valuation"]
            if valorisation is None:
                raise ExportError(f"{ou} : non valorisé. {publie['valuation_error']}")
            if valorisation["as_of"] != DATE_GEL:
                raise ExportError(
                    f"{ou} : valorisé au {valorisation['as_of']}, pas au {DATE_GEL}."
                )
            for ligne in valorisation["positions"]:
                prix.setdefault(ligne["ticker"], set()).add(ligne["price"])

            analyse = json_strict(fichiers[f"{langue}/portfolios/{rang}/analysis.json"])
            if analyse["portfolio_id"] != rang or analyse["as_of"] != DATE_GEL:
                raise ExportError(f"{ou} : l'analyse n'est pas la sienne, au {DATE_GEL}.")
            dates.add(tuple(point["date"] for point in analyse["series"]["returns"]))

    for ticker, valeurs in sorted(prix.items()):
        if len(valeurs) != 1 or min(valeurs) <= 0:
            raise ExportError(
                f"{ticker} n'a pas un seul prix, strictement positif, dans tous "
                f"les portefeuilles : {sorted(valeurs)}."
            )
    if len(dates) != 1:
        raise ExportError("Les séries publiées ne portent pas toutes les mêmes dates.")


# ══════════════════════════════════════════════════════════ Le manifeste ══


def _git(*arguments: str) -> str | None:
    """Une ligne de git sur le dépôt, ou None sans git ni dépôt."""
    try:
        sortie = subprocess.run(
            ["git", *arguments],
            cwd=RACINE,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return sortie.stdout.strip()


def _manifeste(
    fichiers: Mapping[str, bytes], jeu: Sequence[Composition], empreinte: str
) -> dict[str, object]:
    etat = _git("status", "--porcelain")
    return {
        "date_gel": DATE_GEL,
        "base_source_md5": empreinte,
        "commit": _git("rev-parse", "HEAD"),
        # Faux quand l'arbre de travail diffère du commit : les fichiers ne
        # viennent alors pas du code que le commit désigne.
        "arbre_propre": None if etat is None else etat == "",
        "portefeuilles": [
            {"id": rang, "nom": dict(composition.noms), "positions": dict(composition.positions)}
            for rang, composition in enumerate(jeu, start=1)
        ],
        "fichiers": [
            {
                "chemin": chemin,
                "octets": len(octets),
                "sha256": hashlib.sha256(octets).hexdigest(),
            }
            for chemin, octets in sorted(fichiers.items())
        ],
    }


def serialiser(manifeste: Mapping[str, object]) -> bytes:
    """Les octets exacts de `manifeste.json`."""
    return (json.dumps(manifeste, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _ecrire(sortie: Path, fichiers: Mapping[str, bytes], manifeste: Mapping[str, object]) -> None:
    """Remplace le dossier de sortie, une fois tout vérifié.

    Un dossier qui n'est ni vide ni un export précédent n'est pas effacé :
    `--sortie` mal écrit ne doit rien détruire.
    """
    if sortie.exists():
        if not sortie.is_dir():
            raise ExportError(f"{sortie} n'est pas un dossier.")
        if any(sortie.iterdir()) and not (sortie / MANIFESTE).is_file():
            raise ExportError(
                f"{sortie} n'est pas vide et n'est pas un export précédent "
                f"(pas de {MANIFESTE}) : il n'est pas remplacé."
            )
        shutil.rmtree(sortie)
    for chemin, octets in fichiers.items():
        cible = sortie / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(octets)
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / MANIFESTE).write_bytes(serialiser(manifeste))


# ═════════════════════════════════════════════════════════════ L'export ══


def exporter(
    source: Path = SOURCE,
    sortie: Path = SORTIE,
    compositions: Path = COMPOSITIONS,
    garder_les_copies: Path | None = None,
) -> dict[str, object]:
    """Écrit les fichiers de la démonstration dans `sortie` et rend le
    manifeste.

    `garder_les_copies` : le dossier où laisser les deux copies de la base
    (`demo-fr.sqlite`, `demo-en.sqlite`), pour servir l'application sur l'état
    exact que la démonstration publie. Sans lui, elles sont supprimées.
    """
    jeu = lire_compositions(compositions)
    verifier_isolement(jeu)
    if not source.is_file():
        raise ExportError(f"Base source absente : {source}")

    with tempfile.TemporaryDirectory(prefix="export-demo-") as temporaire:
        dossier = Path(temporaire) if garder_les_copies is None else garder_les_copies
        dossier.mkdir(parents=True, exist_ok=True)

        empreintes: set[str] = set()
        fichiers: dict[str, bytes] = {}
        for langue in LANGUES:
            copie = dossier / f"demo-{langue}.sqlite"
            empreintes.add(_copier(source, copie))
            _preparer(copie, jeu, langue)
            fichiers.update(_interroger(copie, jeu, langue))

        # Une écriture dans la source pendant l'export, par l'application
        # ouverte à côté par exemple, donnerait deux copies de deux états.
        empreintes.add(_md5(source))
        if len(empreintes) != 1:
            raise ExportError(
                "La base source a changé pendant l'export. Le relancer : " + COMMANDE
            )

        verifier_export(fichiers, jeu)
        manifeste = _manifeste(fichiers, jeu, empreintes.pop())
        _ecrire(sortie, fichiers, manifeste)
    return manifeste


def main(arguments: Sequence[str] | None = None) -> int:
    lecteur = argparse.ArgumentParser(
        prog=COMMANDE, description="Écrit les réponses de l'API que lit la démonstration."
    )
    lecteur.add_argument("--source", type=Path, default=SOURCE, help="la base à copier")
    lecteur.add_argument("--sortie", type=Path, default=SORTIE, help="le dossier écrit")
    lecteur.add_argument(
        "--compositions", type=Path, default=COMPOSITIONS, help="les portefeuilles"
    )
    lecteur.add_argument(
        "--garder-les-copies",
        type=Path,
        default=None,
        metavar="DOSSIER",
        help="laisse les deux copies de la base dans ce dossier",
    )
    choix = lecteur.parse_args(arguments)

    try:
        manifeste = exporter(
            choix.source, choix.sortie, choix.compositions, choix.garder_les_copies
        )
    except ExportError as exc:
        print(f"Export refusé : {exc}", file=sys.stderr)
        return 1

    for fichier in manifeste["fichiers"]:
        print(f"{fichier['sha256']}  {fichier['octets']:>7}  {fichier['chemin']}")
    print(f"Manifeste : {choix.sortie / MANIFESTE}")
    print(
        f"Gel : {manifeste['date_gel']} ; base source (md5) : {manifeste['base_source_md5']} ; "
        f"commit : {manifeste['commit']} ; arbre propre : {manifeste['arbre_propre']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
