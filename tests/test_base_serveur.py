"""L'outil qui bâtit la base du serveur public (`tools/base_serveur.py`).

Ce que la base du serveur ne doit jamais laisser sortir de sa source : un
portefeuille, une séance postérieure au gel, ni dans ses tables ni dans les
octets de son fichier. Et ce que l'outil ne doit jamais faire : toucher à la
source, écrire dans le dépôt, bâtir depuis une autre base que celle de
l'export de la démonstration.

LA SOURCE EST UNE COPIE, comme partout : la copie figée de `conftest.py`, à
laquelle ce fichier ajoute les témoins de `tests/test_export_demo.py` (un
portefeuille privé, une séance après le gel), puis qu'il met en lecture
seule. Chaque appel à l'outil désigne sa source ; une garde le tient en bas
du fichier, parce que le défaut de l'outil est la base réelle.

L'empreinte attendue de la source est passée en paramètre : dans la commande,
elle se lit dans le manifeste de l'export.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

import pytest

from backend.db.init_db import connect
from tests.conftest import DATE_GEL, copier_base_reelle_figee
from tools import base_serveur
from tools.base_serveur import BaseError, construire, md5_de_l_export

from .test_export_demo import (
    NOM_PRIVE,
    QUANTITE_PRIVEE,
    SEANCE_APRES_LE_GEL,
    imports_interdits,
)

RACINE = Path(__file__).resolve().parents[1]


def _md5(chemin: Path) -> str:
    return hashlib.md5(chemin.read_bytes()).hexdigest()


def _sha256(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    """Une copie figée de la base, avec ses témoins, en lecture seule."""
    chemin = copier_base_reelle_figee(tmp_path_factory.mktemp("source_serveur") / "source.sqlite")
    with closing(connect(chemin)) as conn, conn:
        prive = conn.execute(
            "INSERT INTO portfolios (owner, name, updated_at) VALUES ('local', ?, '2026-10-01')",
            (NOM_PRIVE,),
        ).lastrowid
        conn.execute(
            "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (?, 'BAC', ?)",
            (prive, QUANTITE_PRIVEE),
        )
        conn.execute(
            "INSERT INTO prices (ticker, date, close, adj_close) VALUES ('KO', ?, 1.0, 1.0)",
            (SEANCE_APRES_LE_GEL,),
        )
    chemin.chmod(stat.S_IREAD)
    return chemin


@pytest.fixture(scope="module")
def construite(source, tmp_path_factory) -> tuple[Path, dict]:
    """La base du serveur, bâtie une fois pour le module."""
    sortie = tmp_path_factory.mktemp("base_serveur") / "serveur.sqlite"
    bilan = construire(source=source, sortie=sortie, md5_attendu=_md5(source))
    return sortie, bilan


def _lire(chemin: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{chemin.resolve().as_uri()}?mode=ro", uri=True)


# ═══════════════════════════════════════════════════════════ La source ══


def test_la_source_porte_bien_ses_temoins(source):
    """Sans eux, les tests qui suivent ne prouveraient rien."""
    assert NOM_PRIVE.encode("utf-8") in source.read_bytes()
    with closing(_lire(source)) as conn:
        assert conn.execute("SELECT MAX(date) FROM prices").fetchone()[0] == SEANCE_APRES_LE_GEL
        assert conn.execute("SELECT COUNT(*) FROM portfolios").fetchone()[0] >= 1


def test_la_source_n_est_pas_modifiee(source, tmp_path):
    avant = _md5(source)
    construire(source=source, sortie=tmp_path / "s.sqlite", md5_attendu=avant)
    assert _md5(source) == avant
    assert not source.stat().st_mode & stat.S_IWRITE


# ═════════════════════════════════════════════════ Ce que la base contient ══


def test_la_base_s_arrete_au_gel(construite):
    sortie, bilan = construite
    with closing(_lire(sortie)) as conn:
        assert conn.execute("SELECT MAX(date) FROM prices").fetchone()[0] == DATE_GEL
        apres = conn.execute("SELECT COUNT(*) FROM prices WHERE date > ?", (DATE_GEL,)).fetchone()[0]
    assert apres == 0
    assert bilan["date_gel"] == DATE_GEL


def test_la_coupe_est_celle_de_conftest(construite, base_figee_partagee):
    """Les mêmes cours que la copie figée des tests, séance pour séance."""
    sortie, _ = construite
    requete = "SELECT ticker, date, close, adj_close FROM prices ORDER BY ticker, date"
    with closing(_lire(sortie)) as conn, closing(_lire(base_figee_partagee)) as figee:
        assert conn.execute(requete).fetchall() == figee.execute(requete).fetchall()
        titres = "SELECT ticker, name, sector FROM securities ORDER BY ticker"
        assert conn.execute(titres).fetchall() == figee.execute(titres).fetchall()


def test_aucun_portefeuille_ne_sort(construite):
    sortie, _ = construite
    with closing(_lire(sortie)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM portfolios").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 0
        compteurs = conn.execute(
            "SELECT COUNT(*) FROM sqlite_sequence WHERE name IN ('portfolios', 'positions')"
        ).fetchone()[0]
    assert compteurs == 0


def test_rien_de_supprime_ne_reste_dans_les_octets(construite):
    """Le nom du portefeuille privé n'est plus dans le fichier, pas seulement
    plus dans la table : la base a été réécrite."""
    sortie, _ = construite
    assert NOM_PRIVE.encode("utf-8") not in sortie.read_bytes()


def test_sans_reecriture_le_nom_supprime_resterait_lisible(source, tmp_path, monkeypatch):
    """La mutation : sans `VACUUM`, le test précédent échoue. Le nom reste
    dans une page libre du fichier."""
    monkeypatch.setattr(base_serveur, "_compacter", lambda conn: None)
    sortie = tmp_path / "sans-vacuum.sqlite"
    construire(source=source, sortie=sortie, md5_attendu=_md5(source))
    assert NOM_PRIVE.encode("utf-8") in sortie.read_bytes()


def test_sans_la_coupe_l_outil_refuse_sa_propre_base(source, tmp_path, monkeypatch):
    """La mutation : sans la coupe, la vérification arrête la commande, et
    rien n'est écrit."""
    monkeypatch.setattr(base_serveur, "_couper", lambda conn: None)
    sortie = tmp_path / "sans-coupe.sqlite"
    with pytest.raises(BaseError, match="portefeuilles"):
        construire(source=source, sortie=sortie, md5_attendu=_md5(source))
    assert list(tmp_path.iterdir()) == []


def test_le_bilan_dit_ce_que_la_base_contient(construite):
    sortie, bilan = construite
    with closing(_lire(sortie)) as conn:
        assert bilan["titres"] == conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0]
        assert bilan["seances"] == conn.execute("SELECT COUNT(DISTINCT date) FROM prices").fetchone()[0]
    assert bilan["octets"] == sortie.stat().st_size
    assert bilan["titres"] >= 2 and bilan["seances"] > 504


# ═══════════════════════════════════════════════════════════ L'empreinte ══


def test_l_empreinte_ecrite_est_celle_du_fichier(construite):
    sortie, bilan = construite
    temoin = sortie.with_name(sortie.name + ".sha256")
    assert temoin.read_bytes() == f"{_sha256(sortie)}\n".encode("ascii")
    assert bilan["sha256"] == _sha256(sortie)
    assert len(bilan["sha256"]) == 64


def test_deux_constructions_donnent_le_meme_fichier(source, construite, tmp_path):
    sortie, _ = construite
    seconde = tmp_path / "bis.sqlite"
    construire(source=source, sortie=seconde, md5_attendu=_md5(source))
    assert seconde.read_bytes() == sortie.read_bytes()


def test_aucun_brouillon_ne_reste_a_cote(construite):
    sortie, _ = construite
    assert sorted(f.name for f in sortie.parent.iterdir()) == ["serveur.sqlite", "serveur.sqlite.sha256"]


# ══════════════════════════════════ La même source que l'export, ou rien ══


def test_une_source_qui_n_est_pas_celle_de_l_export_est_refusee(source, tmp_path):
    sortie = tmp_path / "refusee.sqlite"
    with pytest.raises(BaseError, match="export de la démonstration"):
        construire(source=source, sortie=sortie, md5_attendu="0" * 32)
    assert list(tmp_path.iterdir()) == []


def test_l_empreinte_attendue_se_lit_dans_le_manifeste_de_l_export(tmp_path):
    manifeste = tmp_path / "manifeste.json"
    manifeste.write_text(json.dumps({"base_source_md5": "a" * 32, "date_gel": DATE_GEL}), encoding="utf-8")
    assert md5_de_l_export(manifeste) == "a" * 32


@pytest.mark.parametrize("contenu", ('{"date_gel": "2026-09-09"}', '{"base_source_md5": 12}', "[]", "{"))
def test_un_manifeste_qui_ne_la_donne_pas_arrete_la_commande(tmp_path, contenu):
    manifeste = tmp_path / "manifeste.json"
    manifeste.write_text(contenu, encoding="utf-8")
    with pytest.raises(BaseError):
        md5_de_l_export(manifeste)


def test_sans_export_la_commande_dit_de_le_faire(tmp_path):
    with pytest.raises(BaseError, match="python -m tools.export_demo"):
        md5_de_l_export(tmp_path / "absent.json")


def test_la_commande_lit_le_manifeste_et_refuse_une_autre_source(source, tmp_path, capsys):
    manifeste = tmp_path / "manifeste.json"
    manifeste.write_text(json.dumps({"base_source_md5": "b" * 32}), encoding="utf-8")
    sortie = tmp_path / "base" / "serveur.sqlite"
    code = base_serveur.main(
        ["--source", str(source), "--sortie", str(sortie), "--manifeste", str(manifeste)]
    )
    assert code == 1
    assert "Base refusée" in capsys.readouterr().err
    assert not sortie.exists()

    manifeste.write_text(json.dumps({"base_source_md5": _md5(source)}), encoding="utf-8")
    code = base_serveur.main(
        ["--source", str(source), "--sortie", str(sortie), "--manifeste", str(manifeste)]
    )
    assert code == 0
    affiche = capsys.readouterr().out
    assert _sha256(sortie) in affiche
    assert _md5(source) in affiche


# ═════════════════════════════════════════════ Jamais dans le dépôt ══


@pytest.mark.parametrize("dans_le_depot", ("data/serveur.sqlite", "serveur.sqlite", "demo/export/s.sqlite"))
def test_une_sortie_dans_le_depot_est_refusee(source, dans_le_depot):
    sortie = RACINE / dans_le_depot
    with pytest.raises(BaseError, match="dépôt"):
        construire(source=source, sortie=sortie, md5_attendu=_md5(source))
    assert not sortie.exists()
    assert not sortie.with_name(sortie.name + ".sha256").exists()


def test_la_sortie_n_a_pas_de_defaut():
    """Sans `--sortie`, la commande s'arrête : aucun emplacement n'est supposé."""
    with pytest.raises(SystemExit):
        base_serveur.main(["--source", "nulle-part.sqlite"])


# ═══════════════════════════════════════════════════════════ Les gardes ══


def test_l_outil_n_importe_ni_le_fournisseur_ni_l_ingestion_ni_le_reseau():
    assert imports_interdits(Path(base_serveur.__file__).read_text(encoding="utf-8")) == []


def constructions_sans_source(source: str) -> list[int]:
    """Les lignes où ce source appelle l'outil sans désigner sa source : le
    défaut de l'outil est la base réelle."""
    fautes = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Call):
            continue
        nom = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
        if nom == "construire" and not any(k.arg == "source" for k in noeud.keywords):
            fautes.append(noeud.lineno)
        if nom == "main" and not any(
            isinstance(n, ast.Constant) and n.value == "--source" for n in ast.walk(noeud)
        ):
            fautes.append(noeud.lineno)
    return fautes


def test_chaque_construction_de_ces_tests_recoit_sa_source():
    assert constructions_sans_source("construire(sortie=x, md5_attendu=y)") == [1]
    assert constructions_sans_source("base_serveur.main(['--sortie', 'x'])") == [1]
    assert constructions_sans_source("construire(source=copie, sortie=x, md5_attendu=y)") == []
    assert constructions_sans_source("main(['--source', str(copie)])") == []
    assert constructions_sans_source(Path(__file__).read_text(encoding="utf-8")) == []
