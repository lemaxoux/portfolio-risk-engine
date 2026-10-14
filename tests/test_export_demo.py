"""L'export de la démonstration : ce qui sort, et ce qui ne sort jamais.

`tools/export_demo` écrit les réponses de l'API que lit le site de
démonstration. Ces tests tiennent ce qu'il promet :

* la source n'est pas modifiée, et aucun de ses portefeuilles ne sort ;
* la copie est coupée au gel par la règle de `conftest.py` ;
* la liste, les analyses et l'univers sont des réponses de l'application,
  octet pour octet ; le texte d'acceptation et le format du fichier CSV sont
  ceux du site : la réponse locale, plus une section pour l'un, avec les deux
  bornes du serveur public pour l'autre, et rien d'autre ;
* l'export ne contient que les portefeuilles de `demo/compositions.json`, le
  premier étant la démonstration que datent le README et METHODOLOGY.md ;
* aucune combinaison des portefeuilles publiés n'isole un titre ;
* deux exports donnent les mêmes octets, sans une connexion hors de la machine ;
* la mention que le client affiche (`frontend/src/contenu/demo.ts`) dit la
  date du gel et le nombre de portefeuilles des compositions.

LA SOURCE DE CES TESTS EST UNE COPIE FIGÉE de `conftest.py`, jamais la base
réelle : `exporter` la reçoit en `source`, et la dernière garde de ce fichier
refuse un appel qui s'en passerait. Elle porte trois témoins que l'export ne
doit pas laisser passer : un portefeuille privé au nom et à la quantité
uniques, et une séance postérieure au gel.

Comme ailleurs, chaque garde est vue échouer : la mutation des compositions,
le filet du réseau, la garde des sources.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import socket
import stat
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

from backend.api.schemas import DisclaimerOut
from backend.db.init_db import connect
from backend.public_api.base import charger
from backend.public_api.limites import OCTETS_DU_FICHIER_CSV
from backend.textes import textes
from backend.typography import prose
from tests.conftest import DATE_GEL, PORTEFEUILLE_DEMO, copier_base_reelle_figee
from tools import export_demo
from tools.base_serveur import construire
from tools.export_demo import (
    LANGUES,
    MANIFESTE,
    ExportError,
    exporter,
    json_strict,
    lire_compositions,
    titres_isoles,
)

# Ce que l'export ne doit jamais laisser sortir de sa source.
NOM_PRIVE = "TEMOIN_PRIVE_7f3a9c"
QUANTITE_PRIVEE = 7919.125
SEANCE_APRES_LE_GEL = "2026-09-10"

FICHIERS_PAR_LANGUE = (
    "csv-format.json",
    "disclaimer.json",
    "portfolios.json",
    "portfolios/1/analysis.json",
    "portfolios/2/analysis.json",
    "portfolios/3/analysis.json",
    "securities.json",
)

# Les deux fichiers qui ne sont pas des réponses de l'application : le texte
# d'acceptation du site et le format du fichier, aux bornes du serveur public.
FICHIERS_DU_SITE = ("csv-format.json", "disclaimer.json")


# ------------------------------------------------------------------ Réseau --


def _locale(adresse: object) -> bool:
    hote = adresse[0] if isinstance(adresse, tuple) else adresse
    return hote in ("127.0.0.1", "::1", "localhost")


@contextmanager
def sans_reseau() -> Iterator[list[object]]:
    """Refuse toute connexion et toute résolution de nom hors de la machine,
    et note chaque tentative.

    La boucle locale reste ouverte : sous Windows, la boucle d'événements du
    client de test s'en sert pour se réveiller elle-même.
    """
    tentatives: list[object] = []
    connexion = socket.socket.connect
    resolution = socket.getaddrinfo

    def connecter(self, adresse, *reste):
        if not _locale(adresse):
            tentatives.append(adresse)
            raise OSError(f"connexion refusée par le test : {adresse!r}")
        return connexion(self, adresse, *reste)

    def resoudre(hote, *reste, **options):
        if not _locale(hote):
            tentatives.append(hote)
            raise OSError(f"résolution refusée par le test : {hote!r}")
        return resolution(hote, *reste, **options)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", connecter)
        patch.setattr(socket.socket, "connect_ex", connecter)
        patch.setattr(socket, "getaddrinfo", resoudre)
        yield tentatives


def test_le_filet_du_reseau_arrete_une_connexion_hors_de_la_machine():
    # 192.0.2.1 : une adresse réservée à la documentation (RFC 5737).
    with sans_reseau() as tentatives:
        with pytest.raises(OSError, match="refusée par le test"):
            socket.create_connection(("192.0.2.1", 80), timeout=1)
        with pytest.raises(OSError, match="refusée par le test"):
            socket.getaddrinfo("exemple.invalid", 443)
    assert len(tentatives) == 2


# ------------------------------------------------------------------ Export --


@dataclass(frozen=True)
class Export:
    source: Path
    empreinte_de_la_source: str
    sortie: Path
    copies: Path
    manifeste: dict
    tentatives_reseau: tuple[object, ...]

    def octets(self, chemin: str) -> bytes:
        return (self.sortie / chemin).read_bytes()

    def document(self, chemin: str):
        return json_strict(self.octets(chemin))

    def fichiers(self) -> dict[str, bytes]:
        return {
            fichier.relative_to(self.sortie).as_posix(): fichier.read_bytes()
            for fichier in sorted(self.sortie.rglob("*"))
            if fichier.is_file()
        }


def _md5(chemin: Path) -> str:
    return hashlib.md5(chemin.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    """Une copie figée de la base, avec ses trois témoins, en lecture seule."""
    chemin = copier_base_reelle_figee(tmp_path_factory.mktemp("source_export") / "source.sqlite")
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


def _exporter(source: Path, dossier: Path) -> Export:
    empreinte = _md5(source)
    with sans_reseau() as tentatives:
        manifeste = exporter(
            source=source,
            sortie=dossier / "export",
            garder_les_copies=dossier / "copies",
        )
    return Export(
        source=source,
        empreinte_de_la_source=empreinte,
        sortie=dossier / "export",
        copies=dossier / "copies",
        manifeste=manifeste,
        tentatives_reseau=tuple(tentatives),
    )


@pytest.fixture(scope="module")
def export(source, tmp_path_factory) -> Export:
    """L'export des compositions du dépôt, une fois pour le module."""
    return _exporter(source, tmp_path_factory.mktemp("export_demo"))


@pytest.fixture(scope="module")
def second_export(source, export, tmp_path_factory) -> Export:
    """Le même export, refait : pour comparer les octets."""
    return _exporter(source, tmp_path_factory.mktemp("export_demo_bis"))


@pytest.fixture(scope="module")
def compositions():
    return lire_compositions()


# ------------------------------------------------ La source et la coupe --


def test_la_date_de_gel_de_l_outil_est_celle_des_tests():
    assert export_demo.DATE_GEL == DATE_GEL


def test_la_source_n_est_pas_modifiee(export):
    assert _md5(export.source) == export.empreinte_de_la_source
    assert export.manifeste["base_source_md5"] == export.empreinte_de_la_source
    # La source porte toujours ses témoins : ils n'ont pas été retirés d'elle.
    with closing(connect(export.source)) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM portfolios WHERE name = ?", (NOM_PRIVE,)
        ).fetchone()[0] == 1
        assert conn.execute("SELECT MAX(date) FROM prices").fetchone()[0] == SEANCE_APRES_LE_GEL


@pytest.mark.parametrize("langue", LANGUES)
def test_la_coupe_de_l_outil_est_celle_de_conftest(export, base_figee_partagee, langue):
    """La copie de l'outil et celle de `copier_base_reelle_figee` portent la
    même table de prix : la séance ajoutée après le gel n'y est pas."""
    resume = (
        "SELECT ticker, COUNT(*), MIN(date), MAX(date) FROM prices "
        "GROUP BY ticker ORDER BY ticker"
    )
    with closing(connect(export.copies / f"demo-{langue}.sqlite")) as conn:
        obtenu = [tuple(ligne) for ligne in conn.execute(resume)]
    with closing(connect(base_figee_partagee)) as conn:
        attendu = [tuple(ligne) for ligne in conn.execute(resume)]
    assert obtenu == attendu
    assert {ligne[3] for ligne in obtenu} == {DATE_GEL}


def test_aucun_portefeuille_de_la_source_ne_sort(export):
    """Ni dans les fichiers, ni dans les copies gardées, réécrites sans les
    lignes supprimées."""
    prive = NOM_PRIVE.encode("ascii")
    quantite = str(QUANTITE_PRIVEE).encode("ascii")
    for chemin, octets in export.fichiers().items():
        assert prive not in octets, chemin
        assert quantite not in octets, chemin
    for langue in LANGUES:
        copie = export.copies / f"demo-{langue}.sqlite"
        assert prive not in copie.read_bytes(), copie.name
        with closing(connect(copie)) as conn:
            assert [ligne[0] for ligne in conn.execute("SELECT id FROM portfolios ORDER BY id")] == [1, 2, 3]
            assert conn.execute("SELECT COUNT(*) FROM positions WHERE ticker = 'BAC'").fetchone()[0] == 0


# ---------------------------------------------------------- Les fichiers --


def test_l_export_ecrit_les_fichiers_que_lit_la_demonstration_et_eux_seuls(export):
    attendus = {f"{langue}/{fichier}" for langue in LANGUES for fichier in FICHIERS_PAR_LANGUE}
    assert set(export.fichiers()) == attendus | {MANIFESTE}


def test_chaque_fichier_est_du_json_strict(export):
    for chemin, octets in export.fichiers().items():
        json_strict(octets)
        assert b"NaN" not in octets and b"Infinity" not in octets, chemin


def test_json_strict_refuse_ce_que_le_navigateur_refuse():
    with pytest.raises(ValueError):
        json_strict(b'{"x": NaN}')
    with pytest.raises(ValueError):
        json_strict(b'{"x": -Infinity}')


@pytest.mark.parametrize("langue", LANGUES)
def test_chaque_fichier_est_la_reponse_de_l_api_octet_pour_octet(export, client_factory, langue):
    """L'application, interrogée de nouveau sur la copie de la langue, rend
    les octets du fichier. Les deux fichiers du site ont leurs tests plus
    bas."""
    with client_factory(export.copies / f"demo-{langue}.sqlite") as client:
        adresses = {
            "portfolios.json": f"/api/portfolios?lang={langue}",
            **{
                f"portfolios/{numero}/analysis.json": f"/api/portfolios/{numero}/analysis?lang={langue}"
                for numero in (1, 2, 3)
            },
            "securities.json": f"/api/securities?lang={langue}",
        }
        assert set(adresses) == set(FICHIERS_PAR_LANGUE) - set(FICHIERS_DU_SITE)
        for fichier, adresse in adresses.items():
            reponse = client.get(adresse)
            assert reponse.status_code == 200, adresse
            assert reponse.content == export.octets(f"{langue}/{fichier}"), adresse


# ------------------------------------- Les deux fichiers propres au site --


@pytest.mark.parametrize("langue", LANGUES)
def test_le_rendu_de_l_outil_redonne_les_octets_d_une_vraie_reponse(export, client_factory, langue):
    """`rendre` écrit les deux fichiers du site. Appliqué au document d'une
    vraie réponse de l'application, ou au modèle qu'elle sérialise, il en
    redonne les octets : ce qu'il écrit a la forme d'une réponse."""
    with client_factory(export.copies / f"demo-{langue}.sqlite") as client:
        for adresse in (
            f"/api/disclaimer?lang={langue}",
            f"/api/csv-format?lang={langue}",
            f"/api/securities?lang={langue}",
            f"/api/portfolios/1/analysis?lang={langue}",
        ):
            reponse = client.get(adresse)
            assert reponse.status_code == 200, adresse
            assert export_demo.rendre(json_strict(reponse.content)) == reponse.content, adresse
        locale = client.get(f"/api/disclaimer?lang={langue}").content
    assert export_demo.rendre(DisclaimerOut.seul(langue=langue).model_dump(mode="json")) == locale


@pytest.mark.parametrize("langue", LANGUES)
def test_le_texte_d_acceptation_du_site_est_le_texte_local_plus_sa_section(
    export, client_factory, langue
):
    """`disclaimer.json` : la réponse de l'application, une section de plus,
    placée avant la dernière, et rien d'autre."""
    with client_factory(export.copies / f"demo-{langue}.sqlite") as client:
        local = client.get(f"/api/disclaimer?lang={langue}").json()
    site = export.document(f"{langue}/disclaimer.json")
    titre, corps = textes(langue).bandeau.SECTION_EN_LIGNE
    en_ligne = {"title": prose(titre), "body": prose(corps)}

    assert list(site) == list(local)
    assert site["title"] == local["title"]
    assert site["confirmation"] == local["confirmation"]
    assert site["sections"] == [*local["sections"][:-1], en_ligne, local["sections"][-1]]
    # Le texte à plat, dont le client prend l'empreinte, porte la section au
    # même endroit : entre l'avant-dernière et la dernière du texte local.
    derniere = f"\n\n{local['sections'][-1]['title']}\n"
    debut, fin = local["text"].split(derniere)
    assert site["text"] == f"{debut}\n\n{en_ligne['title']}\n{en_ligne['body']}{derniere}{fin}"
    assert site["text"] != local["text"]


@pytest.mark.parametrize("langue", LANGUES)
def test_le_format_du_site_est_le_format_local_aux_bornes_du_serveur_public(
    export, client_factory, base_figee_partagee, tmp_path, langue
):
    """`csv-format.json` : la réponse de l'application, où seules les deux
    bornes changent. Ce sont celles que le serveur public applique : la
    taille du fichier, et le nombre de titres de sa base, bâtie depuis la
    même copie figée."""
    with client_factory(export.copies / f"demo-{langue}.sqlite") as client:
        local = client.get(f"/api/csv-format?lang={langue}").json()
    site = export.document(f"{langue}/csv-format.json")

    bornes = ("max_bytes", "max_positions")
    assert list(site) == list(local)
    assert {c: v for c, v in site.items() if c not in bornes} == {
        c: v for c, v in local.items() if c not in bornes
    }

    serveur = tmp_path / "serveur.sqlite"
    construire(
        source=base_figee_partagee, sortie=serveur, md5_attendu=_md5(base_figee_partagee)
    )
    assert site["max_bytes"] == OCTETS_DU_FICHIER_CSV
    assert site["max_positions"] == len(charger(serveur).catalogue)
    assert site["max_positions"] == len(export.document(f"{langue}/securities.json"))
    # Les bornes de l'application auraient été fausses sur le site.
    assert (site["max_bytes"], site["max_positions"]) != (local["max_bytes"], local["max_positions"])


def test_un_format_sans_ses_bornes_est_refuse():
    with pytest.raises(ExportError, match="deux bornes"):
        export_demo.format_du_site(b'{"max_bytes": 1}', 14)
    with pytest.raises(ExportError, match="deux bornes"):
        export_demo.format_du_site(b"[]", 14)


def test_le_manifeste_decrit_l_export(export, compositions):
    manifeste = export.document(MANIFESTE)
    assert manifeste == export.manifeste
    assert manifeste["date_gel"] == DATE_GEL
    assert manifeste["portefeuilles"] == [
        {"id": numero, "nom": dict(c.noms), "positions": dict(c.positions)}
        for numero, c in enumerate(compositions, start=1)
    ]
    fichiers = {chemin: octets for chemin, octets in export.fichiers().items() if chemin != MANIFESTE}
    assert manifeste["fichiers"] == [
        {"chemin": chemin, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
        for chemin, octets in sorted(fichiers.items())
    ]
    # Ni heure ni date du jour : rien qui change d'un export à l'autre.
    assert set(manifeste) == {
        "date_gel",
        "base_source_md5",
        "commit",
        "arbre_propre",
        "portefeuilles",
        "fichiers",
    }


def test_deux_exports_donnent_les_memes_octets(export, second_export):
    assert second_export.fichiers() == export.fichiers()


def test_l_export_n_ouvre_aucune_connexion_hors_de_la_machine(export, second_export):
    assert export.tentatives_reseau == ()
    assert second_export.tentatives_reseau == ()


# Ce que l'outil lui-même ne doit pas importer. L'application, qu'il charge,
# connaît l'ingestion ; lui n'a rien à lui demander.
IMPORTS_INTERDITS = (
    "backend.data_provider",
    "backend.ingestion",
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "aiohttp",
    "socket",
    "http",
)


def imports_interdits(code: str) -> list[str]:
    trouves = []
    for noeud in ast.walk(ast.parse(code)):
        if isinstance(noeud, ast.Import):
            noms = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ""
            noms = [module, *(f"{module}.{alias.name}" for alias in noeud.names)]
        else:
            continue
        trouves += [
            nom
            for nom in noms
            for interdit in IMPORTS_INTERDITS
            if nom == interdit or nom.startswith(interdit + ".")
        ]
    return trouves


def test_l_outil_n_importe_ni_le_fournisseur_ni_l_ingestion_ni_le_reseau():
    assert imports_interdits("import requests") == ["requests"]
    assert imports_interdits("from backend import ingestion") == ["backend.ingestion"]
    assert imports_interdits("from backend.data_provider.tiingo import x")
    assert imports_interdits("from backend.db import portfolios as store") == []
    assert imports_interdits(Path(export_demo.__file__).read_text(encoding="utf-8")) == []


# ------------------------------------------------------ Les portefeuilles --


def test_la_premiere_composition_est_la_demonstration_des_documents(compositions):
    assert dict(compositions[0].positions) == PORTEFEUILLE_DEMO


def test_les_compositions_ont_un_nom_dans_chaque_langue(compositions):
    assert len(compositions) == 3
    for composition in compositions:
        assert set(composition.noms) == set(LANGUES)


@pytest.mark.parametrize("langue", LANGUES)
def test_l_export_ne_contient_que_les_portefeuilles_des_compositions(export, compositions, langue):
    liste = export.document(f"{langue}/portfolios.json")
    assert [p["id"] for p in liste] == [1, 2, 3]
    assert [p["name"] for p in liste] == [c.noms[langue] for c in compositions]
    for publie, composition in zip(liste, compositions):
        assert {p["ticker"]: p["quantity"] for p in publie["positions"]} == composition.positions
        assert all(p["cost_basis"] is None for p in publie["positions"])
        # Jamais écrites par l'application : aucune date à annoncer.
        assert publie["updated_at"] is None
        assert publie["valuation"]["as_of"] == DATE_GEL
        analyse = export.document(f"{langue}/portfolios/{publie['id']}/analysis.json")
        assert analyse["portfolio"] == {
            "id": publie["id"],
            "name": composition.noms[langue],
            "owner": "local",
            "updated_at": None,
        }
        assert analyse["tickers"] == sorted(composition.positions)


IDENTITE = ("portfolio_id", "portfolio")


def _sans_identite(analyse: dict) -> dict:
    return {cle: valeur for cle, valeur in analyse.items() if cle not in IDENTITE}


def test_la_demonstration_exportee_est_celle_que_datent_les_documents(
    export, analyse_reelle, analyse_reelle_en
):
    """`test_documents_publics.py` compare le README et METHODOLOGY.md à
    l'analyse de cette fixture. L'analyse exportée est la même, à l'identité
    du portefeuille près : son numéro, son nom, la date de ses positions."""
    assert _sans_identite(export.document("fr/portfolios/1/analysis.json")) == _sans_identite(
        analyse_reelle.json()
    )
    assert _sans_identite(export.document("en/portfolios/1/analysis.json")) == _sans_identite(
        analyse_reelle_en.json()
    )


def _ecarts_de_nombres(a: object, b: object, chemin: str = "") -> list[str]:
    """Ce qui diffère entre deux documents, hors de leurs textes : une clé,
    une longueur, un nombre, un booléen, un nul."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return [f"{chemin} : clés"]
        return [e for cle in a for e in _ecarts_de_nombres(a[cle], b[cle], f"{chemin}.{cle}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{chemin} : longueur"]
        return [
            e for rang, (x, y) in enumerate(zip(a, b)) for e in _ecarts_de_nombres(x, y, f"{chemin}[{rang}]")
        ]
    if isinstance(a, str) and isinstance(b, str):
        return []
    return [] if type(a) is type(b) and a == b else [f"{chemin} : {a!r} et {b!r}"]


def test_la_comparaison_des_nombres_voit_un_ecart():
    assert _ecarts_de_nombres({"a": [1.0, "x"]}, {"a": [1.0, "y"]}) == []
    assert _ecarts_de_nombres({"a": [1.0]}, {"a": [1.5]}) == [".a[0] : 1.0 et 1.5"]
    assert _ecarts_de_nombres({"a": None}, {"a": 0}) != []
    assert _ecarts_de_nombres({"a": 1}, {"b": 1}) != []


@pytest.mark.parametrize("fichier", [f for f in FICHIERS_PAR_LANGUE if f != "disclaimer.json"])
def test_les_deux_langues_ne_different_par_aucun_nombre(export, fichier):
    assert _ecarts_de_nombres(export.document(f"fr/{fichier}"), export.document(f"en/{fichier}")) == []


# ------------------------------------------------- La règle d'isolement --


def _publies(export: Export, langue: str) -> list[dict[str, int]]:
    """Les nombres de titres publiés : des entiers, lus dans la liste."""
    portefeuilles = []
    for publie in export.document(f"{langue}/portfolios.json"):
        quantites = {p["ticker"]: p["quantity"] for p in publie["positions"]}
        assert all(float(q).is_integer() for q in quantites.values())
        portefeuilles.append({ticker: int(q) for ticker, q in quantites.items()})
    return portefeuilles


@pytest.mark.parametrize("langue", LANGUES)
def test_aucune_combinaison_des_portefeuilles_publies_n_isole_un_titre(export, langue):
    assert titres_isoles(_publies(export, langue)) == []


@pytest.mark.parametrize("langue", LANGUES)
def test_la_regle_vaut_pour_les_poids_publies(export, langue):
    """Les séries sont à poids constants. La règle, tenue sur les nombres de
    titres, vaut pour les poids tant qu'un titre a le même prix, strictement
    positif, dans tous les portefeuilles, et que les séries portent les mêmes
    dates."""
    prix: dict[str, set[float]] = {}
    dates = set()
    for numero in (1, 2, 3):
        analyse = export.document(f"{langue}/portfolios/{numero}/analysis.json")
        assert analyse["as_of"] == DATE_GEL
        for ligne in analyse["valuation"]["positions"]:
            prix.setdefault(ligne["ticker"], set()).add(ligne["price"])
        rendements = tuple(point["date"] for point in analyse["series"]["returns"])
        valeurs = tuple(point["date"] for point in analyse["series"]["wealth"])
        assert valeurs[1:] == rendements
        dates.add(rendements)
    assert all(len(valeurs) == 1 and min(valeurs) > 0 for valeurs in prix.values())
    assert len(dates) == 1


def test_un_quatrieme_portefeuille_voisin_de_la_demonstration_isole_un_titre(compositions):
    """La mutation : un portefeuille qui ne diffère de la démonstration que
    d'une ligne. La différence des deux est cette ligne seule."""
    publies = [dict(c.positions) for c in compositions]
    assert titres_isoles(publies) == []
    assert titres_isoles([*publies, {**PORTEFEUILLE_DEMO, "KO": 121}]) == ["KO"]
    sans_ko = {ticker: n for ticker, n in PORTEFEUILLE_DEMO.items() if ticker != "KO"}
    assert titres_isoles([*publies, sans_ko]) == ["KO"]
    # Un titre de plus, que personne d'autre ne détient, est isolé de même.
    assert titres_isoles([*publies, {**PORTEFEUILLE_DEMO, "BAC": 10}]) == ["BAC"]


def test_des_portefeuilles_qui_se_recoupent_isolent_tout():
    assert titres_isoles([{"A": 1, "B": 2}, {"A": 3, "C": 1}, {"B": 1, "C": 5}]) == ["A", "B", "C"]


def test_un_portefeuille_a_une_ligne_isole_sa_ligne(compositions):
    assert titres_isoles([{"AAPL": 10}]) == ["AAPL"]
    assert titres_isoles([*(dict(c.positions) for c in compositions), {"CVX": 3}]) == ["CVX"]


def test_deux_portefeuilles_proportionnels_n_isolent_rien():
    # Le rang ne monte pas : la règle ne confond pas « dépendants » et « isolé ».
    assert titres_isoles([{"A": 1, "B": 2}, {"A": 2, "B": 4}]) == []


def _compositions_mutees(dossier: Path, compositions) -> Path:
    document = {
        "portefeuilles": [
            {"nom": dict(c.noms), "positions": dict(c.positions)} for c in compositions
        ]
        + [{"nom": {"fr": "Voisin", "en": "Neighbor"}, "positions": {**PORTEFEUILLE_DEMO, "KO": 121}}]
    }
    chemin = dossier / "compositions.json"
    chemin.write_bytes(json.dumps(document, ensure_ascii=False).encode("utf-8"))
    return chemin


def test_l_outil_refuse_d_exporter_des_compositions_qui_isolent_un_titre(tmp_path, compositions, capsys):
    mutees = _compositions_mutees(tmp_path, compositions)
    sortie = tmp_path / "export"
    absente = tmp_path / "absente.sqlite"
    with pytest.raises(ExportError, match="isole KO"):
        exporter(source=absente, sortie=sortie, compositions=mutees)
    assert not sortie.exists()
    # La commande rend un code d'échec, et dit pourquoi.
    code = export_demo.main(
        ["--source", str(absente), "--sortie", str(sortie), "--compositions", str(mutees)]
    )
    assert code == 1
    assert "Export refusé" in capsys.readouterr().err
    assert not sortie.exists()


# ------------------------------------------------------- Les compositions --


@pytest.mark.parametrize(
    "document, attendu",
    [
        ('{"portefeuilles": []}', "non vide"),
        ('{"portefeuilles": [{"nom": {"fr": "A"}, "positions": {"KO": 1}}]}', "un nom par langue"),
        ('{"portefeuilles": [{"nom": {"fr": "A", "en": " "}, "positions": {"KO": 1}}]}', "nom est vide"),
        ('{"portefeuilles": [{"nom": {"fr": "A", "en": "A"}, "positions": {}}]}', "aucune ligne"),
        ('{"portefeuilles": [{"nom": {"fr": "A", "en": "A"}, "positions": {"KO": 0}}]}', "strictement positif"),
        ('{"portefeuilles": [{"nom": {"fr": "A", "en": "A"}, "positions": {"KO": 1.5}}]}', "strictement positif"),
        ('{"portefeuilles": [{"nom": {"fr": "A", "en": "A"}, "positions": {"KO": true}}]}', "strictement positif"),
        ('{"portefeuilles": [{"nom": {"fr": "A", "en": "A"}, "positions": {"KO": 1, "KO": 2}}]}', "deux fois"),
        ("{", "illisibles"),
    ],
)
def test_des_compositions_mal_ecrites_sont_refusees(tmp_path, document, attendu):
    chemin = tmp_path / "compositions.json"
    chemin.write_bytes(document.encode("utf-8"))
    with pytest.raises(ExportError, match=attendu):
        lire_compositions(chemin)


def test_un_dossier_qui_n_est_pas_un_export_n_est_pas_efface(tmp_path):
    autre = tmp_path / "autre"
    autre.mkdir()
    (autre / "a-garder.txt").write_bytes(b"x")
    with pytest.raises(ExportError, match="n'est pas remplacé"):
        export_demo._ecrire(autre, {"fr/disclaimer.json": b"{}"}, {})
    assert (autre / "a-garder.txt").read_bytes() == b"x"
    # Un export précédent, lui, est remplacé en entier.
    (autre / MANIFESTE).write_bytes(b"{}")
    export_demo._ecrire(autre, {"fr/disclaimer.json": b"{}"}, {})
    assert sorted(f.relative_to(autre).as_posix() for f in autre.rglob("*") if f.is_file()) == [
        "fr/disclaimer.json",
        MANIFESTE,
    ]


# ------------------------------------------- Ce que la mention affirme --

CONTENU_DE_LA_DEMO = (
    Path(__file__).resolve().parents[1] / "frontend" / "src" / "contenu" / "demo.ts"
)


def valeurs_de_la_mention(code: str) -> tuple[str, int]:
    """La date et le nombre que le client écrit dans sa mention."""
    date = re.search(r"^export const DATE_DE_LA_DEMO = '([0-9-]+)'$", code, re.M)
    nombre = re.search(r"^export const PORTEFEUILLES_DE_LA_DEMO = ([0-9]+)$", code, re.M)
    assert date is not None and nombre is not None, "constantes de la mention illisibles"
    return date.group(1), int(nombre.group(1))


def test_la_mention_du_client_dit_la_date_du_gel_et_le_nombre_de_portefeuilles(compositions):
    """« 3 portefeuilles fixes, valorisés au 9 septembre 2026 » : les deux
    valeurs sont écrites dans le client, et tenues ici."""
    temoin = """
export const DATE_DE_LA_DEMO = '2020-01-31'
export const PORTEFEUILLES_DE_LA_DEMO = 12
"""
    assert valeurs_de_la_mention(temoin) == ("2020-01-31", 12)
    date, nombre = valeurs_de_la_mention(CONTENU_DE_LA_DEMO.read_text(encoding="utf-8"))
    assert date == DATE_GEL
    assert nombre == len(compositions)


# ------------------------------------------------ La source de ces tests --


def exports_sans_source(code: str) -> list[int]:
    """Les lignes où un export est lancé sans source désignée : il prendrait
    celle de l'outil, la base réelle."""
    lignes = []
    for noeud in ast.walk(ast.parse(code)):
        if not isinstance(noeud, ast.Call):
            continue
        nom = getattr(noeud.func, "id", getattr(noeud.func, "attr", None))
        if nom == "exporter" and not any(k.arg == "source" for k in noeud.keywords):
            lignes.append(noeud.lineno)
        if nom == "main":
            arguments = noeud.args[0] if noeud.args else None
            designee = isinstance(arguments, ast.List) and any(
                isinstance(e, ast.Constant) and e.value == "--source" for e in arguments.elts
            )
            if not designee:
                lignes.append(noeud.lineno)
    return lignes


def test_chaque_export_de_ces_tests_recoit_sa_source():
    assert exports_sans_source("exporter(sortie=dossier)") == [1]
    assert exports_sans_source("exporter(sortie, source)") == [1]
    assert exports_sans_source("export_demo.main(['--sortie', 'x'])") == [1]
    assert exports_sans_source("main()") == [1]
    assert exports_sans_source("exporter(source=copie, sortie=dossier)") == []
    assert exports_sans_source("main(['--source', str(copie)])") == []
    assert exports_sans_source(Path(__file__).read_text(encoding="utf-8")) == []
