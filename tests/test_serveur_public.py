"""Le serveur public : ce qu'il sert, ce qu'il refuse, ce qu'il ne rend jamais.

`backend/public_api/` (chantier 9.6) analyse le portefeuille qu'un visiteur
du site compose parmi les titres de la base figée. Ce fichier tient ce que
ses en-têtes de module affirment :

* trois routes, et elles seules ; ni `/docs`, ni liste, ni écriture ;
* `X-Robots-Tag` et `Cache-Control` sur CHAQUE réponse ;
* CORS à une origine, sans identifiants ; une origine étrangère refusée ;
* des bornes : lignes, corps, fichier, requêtes par adresse, analyses à la
  fois ;
* des refus dans les textes du serveur public, sans commande ;
* l'INVARIANT : pour chaque composition de la démonstration, la réponse
  publique est l'analyse exportée, aux trois champs retirés près ;
* AUCUNE LISTE DE POINTS DATÉS, dans le modèle comme dans les réponses, et la
  garde est vue échouer quand on y remet `series` ;
* ni fenêtre ni indice en paramètre ;
* la discipline de la couche API : ni calcul, ni SQL.

La base du serveur est bâtie par `tools.base_serveur` depuis la copie figée
de `conftest.py` ; l'export, par `tools.export_demo`, depuis la même copie.
Aucun de ces tests n'ouvre la base réelle.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import sqlite3
import threading
import types
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Union, get_args, get_origin

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend.api.schemas import AnalysisOut, PortfolioSeriesOut
from backend.public_api import routes as routes_publiques
from backend.public_api.app import (
    ORIGINE_DU_SITE,
    VARIABLE_ORIGINE_DE_DEVELOPPEMENT,
    create_public_app,
)
from backend.public_api.base import VARIABLE_BASE, BaseRefusee, charger
from backend.public_api.empreinte import empreinte_du_code
from backend.public_api.limites import (
    OCTETS_DU_CORPS_CSV,
    OCTETS_DU_CORPS_D_ANALYSE,
    OCTETS_DU_FICHIER_CSV,
    PERIODE_EN_MINUTES,
    RANG_DE_L_ADRESSE,
    REQUETES_PAR_PERIODE,
    CompteurParAdresse,
    FileDAnalyses,
    ServeurOccupe,
    adresse_du_client,
)
from backend.public_api.schemas import CHAMPS_RETIRES, PublicAnalysisOut
from backend.risk_engine.portfolio import PortfolioError
from backend.textes import textes
from backend.typography import prose
from tests.conftest import DATE_GEL
from tools.base_serveur import construire
from tools.export_demo import exporter, lire_compositions

from .comparaison_d_analyses import ecarts, listes_de_points
from .test_api_discipline import (
    CALCUL_INTERDIT,
    EXCLUSIONS_INTERDITES,
    MOTS_SQL,
    TYPES_AUTORISES,
    arbre,
    calculs_dans,
    chaines_de_code,
    imports_de,
)
from .test_textes_publics import interdits_dans

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "backend" / "public_api"
LANGUES = ("fr", "en")
AUTRE_ORIGINE = "https://ailleurs.example"
DEMO = {"AAPL": 40, "MSFT": 25, "JPM": 60, "JNJ": 50, "XOM": 80, "KO": 120}

# Les deux en-têtes que porte chaque réponse.
EN_TETES = {"x-robots-tag": "noindex", "cache-control": "no-store"}


def corps(composition: dict[str, float]) -> dict:
    return {
        "positions": [
            {"ticker": ticker, "quantity": quantite, "line": rang}
            for rang, (ticker, quantite) in enumerate(composition.items(), start=1)
        ]
    }


def fichier(contenu: bytes, nom: str = "positions.csv") -> dict:
    return {"file": (nom, contenu, "text/csv")}


# ════════════════════════════════════════════════════════════ La base ══


def _md5(chemin: Path) -> str:
    return hashlib.md5(chemin.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def base_du_serveur(base_figee_partagee, tmp_path_factory) -> Path:
    """La base du serveur, bâtie par l'outil depuis la copie figée."""
    sortie = tmp_path_factory.mktemp("base_du_serveur") / "serveur.sqlite"
    construire(source=base_figee_partagee, sortie=sortie, md5_attendu=_md5(base_figee_partagee))
    return sortie


@contextmanager
def serveur(base: Path, **options):
    """Un client sur une application neuve, la base désignée par la variable
    le temps du contexte."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(VARIABLE_BASE, str(base))
        patch.delenv(VARIABLE_ORIGINE_DE_DEVELOPPEMENT, raising=False)
        with TestClient(create_public_app(**options)) as client:
            yield client


@pytest.fixture(scope="module")
def client(base_du_serveur):
    """Le client partagé par le module. Sa limite par adresse est levée : ce
    module fait plus de requêtes qu'une adresse n'en a le droit, et la limite
    a ses propres tests, sur une application à elle."""
    with serveur(base_du_serveur, compteur=CompteurParAdresse(maximum=10**9)) as partage:
        yield partage


@pytest.fixture(scope="module")
def catalogue(base_du_serveur) -> list[str]:
    return [titre.ticker for titre in charger(base_du_serveur).catalogue]


# ═══════════════════════════════════════════ Trois routes, et elles seules ══

ROUTES = {("/health", ("GET",)), ("/analysis", ("POST",)), ("/csv", ("POST",))}


def routes_de(application) -> set[tuple[str, tuple[str, ...]]]:
    """Chaque route que l'application branche, routeurs inclus compris."""
    trouvees: set[tuple[str, tuple[str, ...]]] = set()

    def parcourir(routes) -> None:
        for route in routes:
            if getattr(route, "path", None) is not None and getattr(route, "methods", None):
                trouvees.add((route.path, tuple(sorted(route.methods))))
            for attribut in ("routes", "original_router", "router"):
                sous = getattr(route, attribut, None)
                sous = getattr(sous, "routes", sous)
                if isinstance(sous, list):
                    parcourir(sous)

    parcourir(application.routes)
    return trouvees


def test_l_application_ne_branche_que_ses_trois_routes():
    application = create_public_app()
    assert routes_de(application) == ROUTES
    # Le schéma dit la même liste : aucune route n'est cachée de lui.
    assert {
        (chemin, tuple(sorted(methode.upper() for methode in methodes)))
        for chemin, methodes in application.openapi()["paths"].items()
    } == ROUTES


def test_la_lecture_des_routes_voit_une_route_de_plus():
    """La mutation : une quatrième route, et la liste n'est plus la bonne."""
    application = create_public_app()

    @application.get("/portfolios")
    def _liste() -> list:
        return []

    assert routes_de(application) == ROUTES | {("/portfolios", ("GET",))}


def test_l_application_locale_en_a_bien_davantage():
    """Le témoin : la même lecture, sur l'application locale."""
    from backend.api.app import create_app

    locales = routes_de(create_app())
    assert len(locales) > 10
    assert any(chemin == "/docs" for chemin, _ in locales)


@pytest.mark.parametrize(
    "chemin",
    (
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs/oauth2-redirect",
        "/api/portfolios",
        "/api/portfolios/1/analysis",
        "/api/securities",
        "/api/meta",
        "/portfolios",
        "/securities",
        "/robots.txt",
        "/health/",
        "/analysis/1",
    ),
)
@pytest.mark.parametrize("langue", LANGUES)
def test_tout_autre_chemin_est_inconnu(client, chemin, langue):
    reponse = client.get(f"{chemin}?lang={langue}", follow_redirects=False)
    assert reponse.status_code == 404, chemin
    assert reponse.json() == {
        "detail": prose(textes(langue).public.ROUTE_INCONNUE),
        "problems": [],
    }


@pytest.mark.parametrize(
    "methode, chemin",
    (
        ("GET", "/analysis"),
        ("PUT", "/analysis"),
        ("DELETE", "/analysis"),
        ("PATCH", "/analysis"),
        ("GET", "/csv"),
        ("PUT", "/csv"),
        ("POST", "/health"),
        ("DELETE", "/health"),
    ),
)
def test_une_autre_methode_est_refusee(client, methode, chemin):
    reponse = client.request(methode, chemin)
    assert reponse.status_code == 405
    assert reponse.json()["detail"] == prose(textes("fr").public.METHODE_REFUSEE)


# ════════════════════════════════════════════════════════════ Le réveil ══


def test_le_reveil_dit_ce_que_le_serveur_sert(client, base_du_serveur):
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {
        "status": "ready",
        "freeze_date": DATE_GEL,
        "database_sha256": hashlib.sha256(base_du_serveur.read_bytes()).hexdigest(),
        "code_sha256": empreinte_du_code(),
    }
    temoin = base_du_serveur.with_name(base_du_serveur.name + ".sha256")
    assert reponse.json()["database_sha256"] == temoin.read_text(encoding="ascii").strip()


def test_le_reveil_ne_lit_ni_parametre_ni_corps(client):
    nu = client.get("/health").content
    assert client.get("/health?lang=en&window=60&x=1").content == nu


def test_le_reveil_ne_lit_pas_la_base(base_du_serveur, monkeypatch):
    """Ses valeurs sont établies au démarrage : la route n'ouvre rien."""
    with serveur(base_du_serveur) as essai:
        monkeypatch.setattr(routes_publiques, "ouvrir", lambda chemin: pytest.fail("base ouverte"))
        assert essai.get("/health").status_code == 200


# ══════════════════════════════════════════════════════════ L'invariant ══


@pytest.fixture(scope="module")
def export(base_figee_partagee, tmp_path_factory) -> Path:
    """L'export de la démonstration, depuis la même copie figée."""
    dossier = tmp_path_factory.mktemp("export_pour_l_invariant")
    exporter(source=base_figee_partagee, sortie=dossier / "export", garder_les_copies=dossier / "copies")
    return dossier / "export"


@pytest.fixture(scope="module")
def compositions():
    return lire_compositions()


@pytest.mark.parametrize("langue", LANGUES)
@pytest.mark.parametrize("rang", (1, 2, 3))
def test_la_reponse_publique_est_l_analyse_exportee_aux_champs_retires_pres(
    client, export, compositions, rang, langue
):
    composition = compositions[rang - 1]
    exportee = json.loads(
        (export / langue / "portfolios" / str(rang) / "analysis.json").read_text(encoding="utf-8")
    )
    reponse = client.post(f"/analysis?lang={langue}", json=corps(composition.positions))
    assert reponse.status_code == 200, reponse.text
    publique = reponse.json()

    assert set(exportee) - set(publique) == set(CHAMPS_RETIRES)
    assert set(publique) - set(exportee) == set()
    attendue = {cle: valeur for cle, valeur in exportee.items() if cle not in CHAMPS_RETIRES}
    assert ecarts(attendue, publique) == []


def test_l_ordre_des_lignes_soumises_ne_change_rien(client, compositions):
    positions = compositions[0].positions
    a_l_endroit = client.post("/analysis", json=corps(positions)).json()
    a_l_envers = client.post("/analysis", json=corps(dict(reversed(list(positions.items()))))).json()
    assert ecarts(a_l_endroit, a_l_envers) == []


@pytest.mark.parametrize(
    "attendu, constate, vu",
    (
        ({"a": 1.0}, {"a": 1.0000001}, False),
        ({"a": 1.0}, {"a": 1.00001}, True),
        ({"a": 0.0}, {"a": 1e-15}, False),
        ({"a": "1,06 %"}, {"a": "1,07 %"}, True),
        ({"a": "x"}, {"a": "x", "series": {}}, True),
        ({"a": "x", "b": 1}, {"a": "x"}, True),
        ({"a": [1, 2]}, {"a": [1, 2, 3]}, True),
        ({"a": 3}, {"a": 4}, True),
        ({"a": None}, {"a": 0}, True),
        ({"a": True}, {"a": 1}, True),
        ({"a": {"b": [{"c": -0.44}]}}, {"a": {"b": [{"c": -0.44}]}}, False),
    ),
)
def test_la_comparaison_voit_un_ecart_et_tolere_un_arrondi(attendu, constate, vu):
    assert bool(ecarts(attendu, constate)) is vu


# ═══════════════════════════════════════ Aucune liste de points datés ══

# Les deux seuls champs de type date qu'un élément de liste porte dans la
# réponse publique : la date d'entrée en cotation d'un TITRE détenu, une par
# titre. Un fait de marché, pas un point d'une série du portefeuille.
DATES_ADMISES_EN_LISTE = {
    ("ExcludedPositionOut", "first_available"),
    ("LimitingPositionOut", "first_available"),
}

# Les seules listes d'une réponse publique qui ont l'allure d'une série : les
# niveaux de confiance demandés, et les lignes des deux matrices, longues du
# nombre de lignes du portefeuille.
LISTES_ADMISES = {
    "parameters.confidence_levels[]",
    "risk.matrices.correlation.values[][]",
    "risk.matrices.covariance.values[][]",
}


def cles_de(document) -> set[str]:
    """Toutes les clés d'un document, à toute profondeur."""
    if isinstance(document, dict):
        return set(document) | {c for valeur in document.values() for c in cles_de(valeur)}
    if isinstance(document, list):
        return {c for element in document for c in cles_de(element)}
    return set()


def _deplier(annotation):
    """Les types que couvre une annotation, `Annotated` et unions dépliés."""
    origine = get_origin(annotation)
    if origine is Annotated:
        yield from _deplier(get_args(annotation)[0])
    elif origine in (Union, types.UnionType):
        for membre in get_args(annotation):
            yield from _deplier(membre)
    else:
        yield annotation


def dates_en_liste(modele: type[BaseModel]) -> set[tuple[str, str]]:
    """Chaque champ de type date porté DIRECTEMENT par l'élément d'une liste,
    où que soit cette liste dans le modèle : (modèle de l'élément, champ)."""
    trouvees: set[tuple[str, str]] = set()
    vus: set[tuple[type, bool]] = set()

    def visiter(annotation, element_de_liste: bool) -> None:
        for sorte in _deplier(annotation):
            if get_origin(sorte) in (list, tuple, set, frozenset):
                for membre in get_args(sorte):
                    visiter(membre, True)
            elif isinstance(sorte, type) and issubclass(sorte, BaseModel):
                if (sorte, element_de_liste) in vus:
                    continue
                vus.add((sorte, element_de_liste))
                for nom, champ in sorte.model_fields.items():
                    if element_de_liste and date in set(_deplier(champ.annotation)):
                        trouvees.add((sorte.__name__, nom))
                    visiter(champ.annotation, False)

    visiter(modele, False)
    return trouvees


def test_le_modele_public_n_a_aucune_liste_de_points_dates():
    assert dates_en_liste(PublicAnalysisOut) == DATES_ADMISES_EN_LISTE


def test_la_garde_du_modele_echoue_si_l_on_y_remet_series():
    """La mutation demandée : `series` de retour dans la réponse publique."""

    class AvecSeries(PublicAnalysisOut):
        series: PortfolioSeriesOut

    assert dates_en_liste(AvecSeries) == DATES_ADMISES_EN_LISTE | {("PointOut", "date")}
    # Et la réponse de l'application, qui les porte, ne passerait pas.
    assert ("PointOut", "date") in dates_en_liste(AnalysisOut)


@pytest.mark.parametrize("langue", LANGUES)
def test_aucune_reponse_publique_ne_porte_de_serie(client, compositions, catalogue, langue):
    """Sur les trois compositions de la démonstration, sur une seule ligne, et
    sur tous les titres de la base à la fois."""
    essais = [c.positions for c in compositions]
    essais.append({"KO": 10})
    essais.append({ticker: 10 for ticker in catalogue})
    for composition in essais:
        reponse = client.post(f"/analysis?lang={langue}", json=corps(composition))
        assert reponse.status_code == 200, reponse.text
        publique = reponse.json()
        assert "series" not in publique
        assert listes_de_points(publique) == LISTES_ADMISES
        # Une ligne de matrice a la longueur du portefeuille, jamais celle
        # d'une fenêtre.
        for matrice in publique["risk"]["matrices"].values():
            if isinstance(matrice, dict) and "values" in matrice:
                assert all(len(ligne) == len(composition) for ligne in matrice["values"])
        assert not {"series", "returns", "wealth"} & cles_de(publique)


def test_la_garde_des_reponses_echoue_sur_une_reponse_qui_porte_series(export):
    """La mutation, sur une vraie réponse : l'analyse de l'application."""
    locale = json.loads((export / "fr" / "portfolios" / "1" / "analysis.json").read_text(encoding="utf-8"))
    assert listes_de_points(locale) == LISTES_ADMISES | {"series.returns[]", "series.wealth[]"}
    # Des rendements nus, sans date, seraient vus aussi.
    assert listes_de_points({"risk": {"returns": [0.01, -0.02, 0.005]}}) == {"risk.returns[]"}
    assert listes_de_points({"risk": {"note": "texte", "bins": [{"lower": 0.0, "count": 3}]}}) == set()


# ═════════════════════════════════════ Le schéma public, champ par champ ══


def test_le_schema_public_est_celui_de_l_application_moins_trois_champs():
    locaux, publics = AnalysisOut.model_fields, PublicAnalysisOut.model_fields
    assert set(CHAMPS_RETIRES) == {"portfolio_id", "portfolio", "series"}
    assert set(locaux) - set(publics) == set(CHAMPS_RETIRES)
    assert set(publics) - set(locaux) == set()
    for nom, champ in publics.items():
        assert champ.annotation == locaux[nom].annotation, nom
    # Dans le même ordre : les deux réponses se lisent côte à côte.
    assert list(publics) == [nom for nom in locaux if nom not in CHAMPS_RETIRES]


def test_un_champ_ajoute_a_la_reponse_locale_ferait_echouer_le_test():
    """La mutation : un champ de plus dans `AnalysisOut`, pas encore classé."""

    class Demain(AnalysisOut):
        nouveau: int = 0

    assert set(Demain.model_fields) - set(PublicAnalysisOut.model_fields) != set(CHAMPS_RETIRES)


# ════════════════════════════════════════ Ni fenêtre, ni indice, ni autre ══


@pytest.mark.parametrize(
    "parametres",
    ("window=60", "window=1000", "benchmark=", "benchmark=XXX", "window=61&benchmark=KO", "confidence=0.9"),
)
def test_aucun_parametre_ne_change_un_octet_de_l_analyse(client, parametres):
    nue = client.post("/analysis", json=corps(DEMO))
    avec = client.post(f"/analysis?{parametres}", json=corps(DEMO))
    assert nue.status_code == avec.status_code == 200
    assert avec.content == nue.content
    assert avec.json()["parameters"]["window"] == 504
    assert avec.json()["estimation_window"]["observations"] == 504


def test_la_route_d_analyse_ne_declare_que_la_langue():
    """Ses paramètres de requête, lus dans le schéma."""
    operation = create_public_app().openapi()["paths"]["/analysis"]["post"]
    assert [p["name"] for p in operation.get("parameters", [])] == ["lang"]


def test_la_langue_change_les_textes_pas_les_nombres(client):
    francaise = client.post("/analysis?lang=fr", json=corps(DEMO)).json()
    anglaise = client.post("/analysis?lang=en", json=corps(DEMO)).json()
    assert francaise["estimation_period_label"] != anglaise["estimation_period_label"]
    assert francaise["total_value"] == anglaise["total_value"]
    assert francaise["weights"] == anglaise["weights"]
    assert francaise["histogram"] == anglaise["histogram"]
    assert client.post("/analysis", json=corps(DEMO)).json() == francaise


def test_une_langue_inconnue_est_refusee(client):
    assert client.post("/analysis?lang=de", json=corps(DEMO)).status_code == 422


# ══════════════════════════════════════════════════════════ Les en-têtes ══


def _toutes_sortes_de_reponses(client) -> dict[str, object]:
    """Une réponse de chaque sorte que le serveur sait faire."""
    return {
        "réveil": client.get("/health"),
        "analyse": client.post("/analysis", json=corps(DEMO)),
        "refus de lignes": client.post("/analysis", json=corps({"XYZ": 1})),
        "requête mal formée": client.post("/analysis", json={"positions": [{"ticker": "KO"}]}),
        "corps illisible": client.post(
            "/analysis", content=b"{", headers={"content-type": "application/json"}
        ),
        "chemin inconnu": client.get("/docs"),
        "méthode refusée": client.get("/analysis"),
        "corps trop gros": client.post(
            "/analysis",
            content=b"x" * (OCTETS_DU_CORPS_D_ANALYSE + 1),
            headers={"content-type": "application/json"},
        ),
        "origine étrangère": client.post(
            "/analysis", json=corps(DEMO), headers={"Origin": AUTRE_ORIGINE}
        ),
        "fichier lu": client.post("/csv", files=fichier(b"ticker;quantity\nKO;10\n")),
        "fichier refusé": client.post("/csv", files=fichier(b"")),
        "pré-requête admise": client.options(
            "/analysis",
            headers={"Origin": ORIGINE_DU_SITE, "Access-Control-Request-Method": "POST"},
        ),
        "pré-requête refusée": client.options(
            "/analysis",
            headers={"Origin": AUTRE_ORIGINE, "Access-Control-Request-Method": "POST"},
        ),
    }


def test_chaque_reponse_porte_les_deux_en_tetes(client):
    reponses = _toutes_sortes_de_reponses(client)
    statuts = {nom: reponse.status_code for nom, reponse in reponses.items()}
    assert statuts == {
        "réveil": 200,
        "analyse": 200,
        "refus de lignes": 422,
        "requête mal formée": 422,
        "corps illisible": 422,
        "chemin inconnu": 404,
        "méthode refusée": 405,
        "corps trop gros": 413,
        "origine étrangère": 403,
        "fichier lu": 200,
        "fichier refusé": 422,
        "pré-requête admise": 200,
        "pré-requête refusée": 400,
    }
    for nom, reponse in reponses.items():
        for en_tete, valeur in EN_TETES.items():
            assert reponse.headers.get(en_tete) == valeur, (nom, en_tete)


def test_les_refus_d_une_limite_et_d_une_panne_les_portent_aussi(base_du_serveur, monkeypatch):
    with serveur(base_du_serveur, compteur=CompteurParAdresse(maximum=0)) as essai:
        limite = essai.post("/analysis", json=corps(DEMO))
    with serveur(base_du_serveur) as essai:
        monkeypatch.setattr(routes_publiques, "run_all_scenarios", lambda *a, **k: 1 / 0)
        panne = essai.post("/analysis", json=corps(DEMO), headers={"Origin": ORIGINE_DU_SITE})
    assert (limite.status_code, panne.status_code) == (429, 500)
    for reponse in (limite, panne):
        for en_tete, valeur in EN_TETES.items():
            assert reponse.headers.get(en_tete) == valeur
    # Le site peut lire la panne : elle traverse CORS.
    assert panne.headers.get("access-control-allow-origin") == ORIGINE_DU_SITE


# ══════════════════════════════════════════════════════════════════ CORS ══


def test_l_origine_du_site_est_autorisee_sans_identifiants(client):
    for reponse in (
        client.get("/health", headers={"Origin": ORIGINE_DU_SITE}),
        client.post("/analysis", json=corps(DEMO), headers={"Origin": ORIGINE_DU_SITE}),
        client.post("/analysis", json=corps({"XYZ": 1}), headers={"Origin": ORIGINE_DU_SITE}),
    ):
        assert reponse.headers.get("access-control-allow-origin") == ORIGINE_DU_SITE
        assert "access-control-allow-credentials" not in reponse.headers


@pytest.mark.parametrize(
    "origine",
    (
        AUTRE_ORIGINE,
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://portfolio-risk-engine-lemaxoux.pages.dev.ailleurs.example",
        "http://portfolio-risk-engine-lemaxoux.pages.dev",
        "null",
    ),
)
def test_une_autre_origine_ne_recoit_aucune_autorisation(client, origine):
    lecture = client.get("/health", headers={"Origin": origine})
    assert lecture.status_code == 200
    assert "access-control-allow-origin" not in lecture.headers
    pre_requete = client.options(
        "/analysis", headers={"Origin": origine, "Access-Control-Request-Method": "POST"}
    )
    assert pre_requete.status_code == 400
    assert "access-control-allow-origin" not in pre_requete.headers


def test_la_pre_requete_du_site_dit_ce_qui_est_permis(client):
    reponse = client.options(
        "/analysis",
        headers={
            "Origin": ORIGINE_DU_SITE,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert reponse.status_code == 200
    assert reponse.headers["access-control-allow-origin"] == ORIGINE_DU_SITE
    assert reponse.headers["access-control-allow-methods"] == "GET, POST"
    assert "access-control-allow-credentials" not in reponse.headers
    assert int(reponse.headers["access-control-max-age"]) > 0


def test_l_origine_de_developpement_n_existe_que_par_sa_variable(base_du_serveur):
    locale = "http://localhost:4173"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(VARIABLE_BASE, str(base_du_serveur))
        patch.setenv(VARIABLE_ORIGINE_DE_DEVELOPPEMENT, locale)
        with TestClient(create_public_app()) as essai:
            assert essai.get("/health", headers={"Origin": locale}).headers[
                "access-control-allow-origin"
            ] == locale
            assert essai.post("/analysis", json=corps({"KO": 1}), headers={"Origin": locale}).status_code == 200
            # Le site reste autorisé, et un tiers ne l'est toujours pas.
            assert essai.get("/health", headers={"Origin": ORIGINE_DU_SITE}).headers[
                "access-control-allow-origin"
            ] == ORIGINE_DU_SITE
            assert "access-control-allow-origin" not in essai.get(
                "/health", headers={"Origin": AUTRE_ORIGINE}
            ).headers


def test_le_cors_n_est_jamais_ouvert_a_tous():
    """Dans le code : une liste d'origines, jamais le joker, jamais d'identifiants."""
    source = arbre(DOSSIER / "app.py")
    mots_cles = {n.arg: n.value for n in ast.walk(source) if isinstance(n, ast.keyword)}
    assert isinstance(mots_cles["allow_credentials"], ast.Constant)
    assert mots_cles["allow_credentials"].value is False
    assert "*" not in {c.value for c in chaines_de_code(DOSSIER / "app.py")}
    assert "allow_origin_regex" not in mots_cles


# ═══════════════════════════════════════════════ Une origine étrangère ══


@pytest.mark.parametrize("langue", LANGUES)
def test_une_ecriture_venue_d_une_autre_origine_est_refusee_avant_tout_calcul(
    base_du_serveur, monkeypatch, langue
):
    with serveur(base_du_serveur) as essai:
        monkeypatch.setattr(routes_publiques, "ouvrir", lambda chemin: pytest.fail("base ouverte"))
        for reponse in (
            essai.post(f"/analysis?lang={langue}", json=corps(DEMO), headers={"Origin": AUTRE_ORIGINE}),
            essai.post(f"/csv?lang={langue}", files=fichier(b"ticker;quantity\nKO;1\n"), headers={"Origin": AUTRE_ORIGINE}),
        ):
            assert reponse.status_code == 403
            assert reponse.json() == {
                "detail": prose(textes(langue).public.ORIGINE_REFUSEE),
                "problems": [],
            }
            assert "access-control-allow-origin" not in reponse.headers


def test_une_requete_sans_origine_passe(client):
    """Un outil en ligne de commande n'envoie pas d'origine, et n'engage le
    navigateur de personne."""
    assert client.post("/analysis", json=corps({"KO": 1})).status_code == 200


# ═══════════════════════════════════════════════════════════ Les bornes ══


@pytest.mark.parametrize("langue", LANGUES)
def test_un_titre_hors_base_est_refuse_a_sa_ligne(client, catalogue, langue):
    soumis = {"positions": [
        {"ticker": "KO", "quantity": 10, "line": 1},
        {"ticker": "XYZ", "quantity": 4, "line": 2},
        {"ticker": "TSLA", "quantity": 4, "line": 7},
    ]}
    reponse = client.post(f"/analysis?lang={langue}", json=soumis)
    assert reponse.status_code == 422
    refus = reponse.json()
    t = textes(langue).public
    assert refus["detail"] == prose(t.lignes_refusees(2))
    assert [(p["line"], p["field"], p["value"]) for p in refus["problems"]] == [
        (2, "ticker", "XYZ"),
        (7, "ticker", "TSLA"),
    ]
    assert refus["problems"][0]["problem"] == prose(t.titre_inconnu("XYZ", ", ".join(catalogue)))


def test_un_refus_unique_est_repris_tel_quel(client):
    refus = client.post("/analysis", json=corps({"KO": -3})).json()
    assert len(refus["problems"]) == 1
    assert refus["detail"] == refus["problems"][0]["problem"]


def test_les_autres_refus_de_ligne_sont_ceux_de_la_validation(client):
    soumis = {"positions": [
        {"ticker": "KO", "quantity": 10, "line": 1},
        {"ticker": " ko ", "quantity": 4, "line": 2},
        {"ticker": "  ", "quantity": 4, "line": 3},
        {"ticker": "PG", "quantity": 0, "line": 4},
        {"ticker": "JNJ", "quantity": 2, "cost_basis": -1, "line": 5},
    ]}
    refus = client.post("/analysis", json=soumis).json()
    assert [(p["line"], p["field"]) for p in refus["problems"]] == [
        (2, "ticker"),
        (3, "ticker"),
        (4, "quantity"),
        (5, "cost_basis"),
    ]


@pytest.mark.parametrize("langue", LANGUES)
def test_aucune_position_n_est_pas_un_portefeuille(client, langue):
    reponse = client.post(f"/analysis?lang={langue}", json={"positions": []})
    assert reponse.status_code == 422
    assert reponse.json()["detail"] == prose(textes(langue).public.AUCUNE_POSITION)


@pytest.mark.parametrize("langue", LANGUES)
def test_plus_de_lignes_que_la_base_n_a_de_titres_est_refuse(client, catalogue, langue):
    """La borne est DÉRIVÉE : le nombre de titres de la base."""
    trop = {"positions": [{"ticker": "KO", "quantity": 1, "line": rang} for rang in range(1, len(catalogue) + 2)]}
    reponse = client.post(f"/analysis?lang={langue}", json=trop)
    assert reponse.status_code == 422
    attendu = textes(langue).public.trop_de_positions(len(catalogue) + 1, len(catalogue))
    assert reponse.json() == {"detail": prose(attendu), "problems": []}
    # Autant de lignes que de titres : le portefeuille de toute la base passe.
    assert client.post("/analysis", json=corps({t: 1 for t in catalogue})).status_code == 200


@pytest.mark.parametrize("langue", LANGUES)
def test_un_corps_trop_gros_est_refuse_sur_son_en_tete(client, langue):
    reponse = client.post(
        f"/analysis?lang={langue}",
        content=b" " * (OCTETS_DU_CORPS_D_ANALYSE + 1),
        headers={"content-type": "application/json"},
    )
    assert reponse.status_code == 413
    attendu = textes(langue).public.corps_trop_volumineux(OCTETS_DU_CORPS_D_ANALYSE)
    assert reponse.json() == {"detail": prose(attendu), "problems": []}


def test_un_corps_trop_gros_envoye_par_morceaux_est_refuse_aussi(client):
    """Sans `Content-Length` : la borne compte les octets reçus."""

    def morceaux():
        for _ in range(40):
            yield b" " * 1_000

    reponse = client.post("/analysis", content=morceaux(), headers={"content-type": "application/json"})
    assert "content-length" not in {cle.lower() for cle in reponse.request.headers}
    assert reponse.status_code == 413
    attendu = textes("fr").public.corps_trop_volumineux(OCTETS_DU_CORPS_D_ANALYSE)
    assert reponse.json() == {"detail": prose(attendu), "problems": []}


def test_un_corps_a_la_borne_passe(client):
    plein = json.dumps(corps({"KO": 1})).encode("utf-8")
    plein += b" " * (OCTETS_DU_CORPS_D_ANALYSE - len(plein))
    assert len(plein) == OCTETS_DU_CORPS_D_ANALYSE
    reponse = client.post("/analysis", content=plein, headers={"content-type": "application/json"})
    assert reponse.status_code == 200


# ══════════════════════════════════════════════════════ Le fichier CSV ══

CSV_FR = "ticker;quantity;cost_basis\nAAPL;40;185,20\nMSFT;25;\n".encode("cp1252")


def test_un_fichier_lu_rend_ses_lignes_et_sa_provenance(client):
    reponse = client.post("/csv", files=fichier(CSV_FR, "été.csv"))
    assert reponse.status_code == 200
    assert reponse.json() == {
        "positions": [
            {"ticker": "AAPL", "quantity": 40.0, "cost_basis": 185.2},
            {"ticker": "MSFT", "quantity": 25.0, "cost_basis": None},
        ],
        "source": {
            "filename": "été.csv",
            "encoding": "utf-8",
            "delimiter": ";",
            "decimal_separator": ",",
            "rows_read": 2,
        },
    }


def test_la_lecture_d_un_fichier_n_analyse_rien_et_n_ouvre_pas_la_base(base_du_serveur, monkeypatch):
    with serveur(base_du_serveur) as essai:
        monkeypatch.setattr(routes_publiques, "ouvrir", lambda chemin: pytest.fail("base ouverte"))
        assert essai.post("/csv", files=fichier(CSV_FR)).status_code == 200


@pytest.mark.parametrize("langue", LANGUES)
def test_un_titre_hors_base_dans_un_fichier_est_refuse_a_sa_ligne_de_fichier(client, catalogue, langue):
    contenu = b"ticker,quantity\nKO,10\nXYZ,4\nPG,2\nTSLA,1\n"
    reponse = client.post(f"/csv?lang={langue}", files=fichier(contenu))
    assert reponse.status_code == 422
    refus = reponse.json()
    t = textes(langue).public
    assert refus["detail"] == prose(t.lignes_du_fichier_refusees(2))
    # La ligne du fichier, en-tête compris, telle qu'un tableur la montre.
    assert [(p["line"], p["value"]) for p in refus["problems"]] == [(3, "XYZ"), (5, "TSLA")]
    assert refus["problems"][0]["problem"] == prose(t.titre_inconnu("XYZ", ", ".join(catalogue)))


@pytest.mark.parametrize(
    "contenu, texte",
    (
        (b"", lambda t: t.FICHIER_VIDE),
        (b"   \n", lambda t: t.FICHIER_VIDE),
        (b"AAPL 40\nMSFT 25\n", lambda t: t.aucun_separateur("ticker;quantity[;cost_basis]")),
        (bytes([0x81, 0x8D, 0x8F, 0x90, 0x9D]) * 4, lambda t: t.FICHIER_ILLISIBLE),
    ),
)
@pytest.mark.parametrize("langue", LANGUES)
def test_un_fichier_illisible_est_refuse_dans_les_mots_du_serveur_public(client, contenu, texte, langue):
    reponse = client.post(f"/csv?lang={langue}", files=fichier(contenu))
    assert reponse.status_code == 422
    assert reponse.json() == {"detail": prose(texte(textes(langue).public)), "problems": []}


@pytest.mark.parametrize("langue", LANGUES)
def test_un_fichier_plus_gros_que_la_borne_publique_est_refuse(client, langue):
    """Sous la borne du corps, au-dessus de celle du fichier : c'est le
    lecteur qui refuse, avec la borne PUBLIQUE, pas celle de l'application."""
    contenu = b"ticker;quantity\n" + b"KO;1\n" * 13_000
    assert OCTETS_DU_FICHIER_CSV < len(contenu) < OCTETS_DU_CORPS_CSV - 1_000
    reponse = client.post(f"/csv?lang={langue}", files=fichier(contenu))
    assert reponse.status_code == 422
    attendu = textes(langue).public.fichier_trop_volumineux(OCTETS_DU_FICHIER_CSV)
    assert reponse.json() == {"detail": prose(attendu), "problems": []}


def test_une_requete_de_fichier_plus_grosse_que_son_corps_est_refusee(client):
    reponse = client.post("/csv", files=fichier(b"x" * (OCTETS_DU_CORPS_CSV + 1)))
    assert reponse.status_code == 413
    attendu = textes("fr").public.corps_trop_volumineux(OCTETS_DU_CORPS_CSV)
    assert reponse.json()["detail"] == prose(attendu)


def test_un_fichier_a_la_borne_est_lu(client):
    entete = b"ticker;quantity\nKO;1\n"
    contenu = entete + b"\n" * (OCTETS_DU_FICHIER_CSV - len(entete))
    assert len(contenu) == OCTETS_DU_FICHIER_CSV
    assert client.post("/csv", files=fichier(contenu)).status_code == 200


def test_sans_fichier_la_requete_est_refusee(client):
    assert client.post("/csv").status_code == 422


# ════════════════════════════════════════════════ La limite par adresse ══


def test_la_limite_est_celle_des_seuils_declares():
    compteur = CompteurParAdresse()
    assert (compteur.maximum, compteur.periode_en_minutes) == (REQUETES_PAR_PERIODE, PERIODE_EN_MINUTES)


@pytest.mark.parametrize("langue", LANGUES)
def test_au_dela_de_la_limite_une_adresse_est_refusee(base_du_serveur, langue):
    with serveur(base_du_serveur, compteur=CompteurParAdresse(maximum=2)) as essai:
        statuts = [
            essai.post(f"/analysis?lang={langue}", json=corps({"XYZ": 1})).status_code
            for _ in range(2)
        ]
        refus = essai.post(f"/analysis?lang={langue}", json=corps({"KO": 1}))
        # Les deux routes partagent le compte ; le réveil n'y entre pas.
        fichier_refuse = essai.post(f"/csv?lang={langue}", files=fichier(CSV_FR))
        reveils = [essai.get("/health").status_code for _ in range(5)]
    assert statuts == [422, 422]
    assert refus.status_code == fichier_refuse.status_code == 429
    attendu = textes(langue).public.limite_atteinte(2, PERIODE_EN_MINUTES)
    assert refus.json() == {"detail": prose(attendu), "problems": []}
    assert reveils == [200] * 5


def test_un_en_tete_forge_ne_remet_pas_le_compte_a_zero(base_du_serveur):
    """`X-Forwarded-For` s'allonge par la droite : ce qu'un client y écrit
    reste à gauche, et la clé est comptée depuis la droite."""
    relais = "172.71.0.1, 10.0.0.1"

    def adresse(forge: str, client: str) -> dict:
        return {"X-Forwarded-For": f"{forge}, {client}, {relais}"}

    with serveur(base_du_serveur, compteur=CompteurParAdresse(maximum=2)) as essai:
        statuts = [
            essai.post("/analysis", json=corps({"XYZ": 1}), headers=adresse(f"198.51.100.{n}", "203.0.113.7")).status_code
            for n in range(3)
        ]
        autre = essai.post("/analysis", json=corps({"XYZ": 1}), headers=adresse("198.51.100.0", "203.0.113.8"))
    assert statuts == [422, 422, 429]
    assert autre.status_code == 422


@pytest.mark.parametrize(
    "en_tete, pair, attendu",
    (
        ("203.0.113.7, 172.71.0.1, 10.0.0.1", "10.0.0.9", "203.0.113.7"),
        ("1.2.3.4, 203.0.113.7, 172.71.0.1, 10.0.0.1", "10.0.0.9", "203.0.113.7"),
        ("9.9.9.9,8.8.8.8 , 203.0.113.7 ,172.71.0.1,10.0.0.1", None, "203.0.113.7"),
        ("203.0.113.7, 10.0.0.1", "10.0.0.9", "203.0.113.7"),
        ("203.0.113.7", "10.0.0.9", "203.0.113.7"),
        (None, "127.0.0.1", "127.0.0.1"),
        ("", "127.0.0.1", "127.0.0.1"),
        (" , ", None, "inconnue"),
    ),
)
def test_l_adresse_du_client_se_compte_depuis_la_droite(en_tete, pair, attendu):
    assert RANG_DE_L_ADRESSE == 3
    assert adresse_du_client(en_tete, pair) == attendu


def test_le_compteur_repart_a_chaque_periode_et_borne_sa_table():
    heure = [0.0]
    compteur = CompteurParAdresse(maximum=2, periode_en_minutes=10, adresses=2, horloge=lambda: heure[0])
    assert [compteur.admet("a") for _ in range(3)] == [True, True, False]
    assert compteur.admet("b") is True
    # La table est pleine : une adresse nouvelle attend la période suivante.
    assert compteur.admet("c") is False
    heure[0] = 599.0
    assert compteur.admet("a") is False
    heure[0] = 600.0
    assert [compteur.admet("a"), compteur.admet("c")] == [True, True]


# ═══════════════════════════════════════════ Les analyses en même temps ══


def test_sans_place_d_attente_la_seconde_analyse_est_refusee_tout_de_suite():
    file = FileDAnalyses(en_attente=0)
    with file.tour():
        with pytest.raises(ServeurOccupe):
            with file.tour():
                pass
    # Le tour rendu, la place est libre de nouveau.
    with file.tour():
        pass


def test_avec_une_place_d_attente_la_seconde_analyse_attend_son_tour():
    file = FileDAnalyses(en_attente=1)
    passee = threading.Event()

    def attendre() -> None:
        with file.tour():
            passee.set()

    with file.tour():
        attente = threading.Thread(target=attendre)
        attente.start()
        # Elle a sa place, pas encore son tour.
        assert not passee.wait(timeout=0.3)
    assert passee.wait(timeout=10)
    attente.join(timeout=10)


@pytest.mark.parametrize("langue", LANGUES)
def test_un_serveur_occupe_le_dit(base_du_serveur, langue):
    file = FileDAnalyses(en_attente=0)
    with serveur(base_du_serveur, file=file) as essai:
        with file.tour():
            reponse = essai.post(f"/analysis?lang={langue}", json=corps(DEMO))
        apres = essai.post(f"/analysis?lang={langue}", json=corps({"KO": 1}))
    assert reponse.status_code == 503
    assert reponse.json() == {"detail": prose(textes(langue).public.SERVEUR_OCCUPE), "problems": []}
    assert apres.status_code == 200


def test_deux_analyses_demandees_en_meme_temps_rendent_chacune_la_sienne(client, compositions):
    """Par l'application entière, file comprise : deux compositions
    différentes, demandées par deux fils, égales à ce qu'elles rendent seules."""
    seules = [client.post("/analysis", json=corps(c.positions)).json() for c in compositions[:2]]
    assert ecarts(seules[0], seules[1]) != []
    ensemble: dict[int, dict] = {}
    depart = threading.Barrier(2)

    def demander(rang: int) -> None:
        depart.wait(timeout=30)
        ensemble[rang] = client.post("/analysis", json=corps(compositions[rang].positions)).json()

    fils = [threading.Thread(target=demander, args=(rang,)) for rang in (0, 1)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join(timeout=120)
    assert [ecarts(seules[rang], ensemble[rang]) for rang in (0, 1)] == [[], []]


# ══════════════════════════════════ Ce que le moteur dirait n'est pas publié ══


@pytest.mark.parametrize("langue", LANGUES)
def test_un_refus_du_moteur_prend_le_texte_du_serveur_public(base_du_serveur, monkeypatch, langue):
    def refuser(*arguments, **options):
        raise PortfolioError("prix_absents", ["SPY"])

    assert "python -m" in PortfolioError("prix_absents", ["SPY"]).texte(langue)
    with serveur(base_du_serveur) as essai:
        monkeypatch.setattr(routes_publiques, "analyse_portfolio", refuser)
        reponse = essai.post(f"/analysis?lang={langue}", json=corps(DEMO))
    assert reponse.status_code == 409
    assert reponse.json() == {
        "detail": prose(textes(langue).public.ANALYSE_IMPOSSIBLE),
        "problems": [],
    }


@pytest.mark.parametrize("langue", LANGUES)
def test_une_erreur_imprevue_rend_le_texte_du_serveur_jamais_sa_trace(
    base_du_serveur, monkeypatch, caplog, langue
):
    def planter(*arguments, **options):
        raise RuntimeError("secret interne 12345 : python -m backend.ingestion")

    with serveur(base_du_serveur) as essai:
        monkeypatch.setattr(routes_publiques, "compare_all_regimes", planter)
        with caplog.at_level(logging.ERROR, logger="backend.public_api"):
            reponse = essai.post(f"/analysis?lang={langue}", json=corps(DEMO))
    assert reponse.status_code == 500
    assert reponse.json() == {
        "detail": prose(textes(langue).public.ERREUR_INTERNE),
        "problems": [],
    }
    assert b"secret" not in reponse.content and b"Traceback" not in reponse.content
    # Le journal dit quoi et où, rien de ce que la requête ou l'erreur portait.
    assert [enregistrement.getMessage() for enregistrement in caplog.records] == [
        "RuntimeError sur /analysis"
    ]


# ═══════════════════════════════ Aucune réponse ne porte de commande ══


def _refus_reels(client, langue: str) -> dict[str, object]:
    suffixe = f"?lang={langue}"
    return {
        "titre inconnu": client.post(f"/analysis{suffixe}", json=corps({"XYZ": 1, "TSLA": 2})),
        "doublon": client.post(f"/analysis{suffixe}", json={"positions": [{"ticker": "KO", "quantity": 1, "line": 1}, {"ticker": "KO", "quantity": 1, "line": 2}]}),
        "quantité": client.post(f"/analysis{suffixe}", json=corps({"KO": -1})),
        "aucune position": client.post(f"/analysis{suffixe}", json={"positions": []}),
        "trop de lignes": client.post(f"/analysis{suffixe}", json={"positions": [{"ticker": "KO", "quantity": 1}] * 40}),
        "mal formée": client.post(f"/analysis{suffixe}", json={"positions": "x"}),
        "illisible": client.post(f"/analysis{suffixe}", content=b"{", headers={"content-type": "application/json"}),
        "trop gros": client.post(f"/analysis{suffixe}", content=b" " * 20_000, headers={"content-type": "application/json"}),
        "chemin": client.get(f"/api/portfolios{suffixe}"),
        "méthode": client.put(f"/analysis{suffixe}"),
        "origine": client.post(f"/analysis{suffixe}", json=corps(DEMO), headers={"Origin": AUTRE_ORIGINE}),
        "langue": client.post("/analysis?lang=de", json=corps(DEMO)),
        "fichier vide": client.post(f"/csv{suffixe}", files=fichier(b"")),
        "fichier sans séparateur": client.post(f"/csv{suffixe}", files=fichier(b"AAPL 40\n")),
        "fichier sans colonne": client.post(f"/csv{suffixe}", files=fichier(b"titre;nombre\nKO;1\n")),
        "fichier fautif": client.post(f"/csv{suffixe}", files=fichier(b"ticker,quantity\nALFA,1,5\nKO;dix\nKO,abc\n")),
        "fichier hors base": client.post(f"/csv{suffixe}", files=fichier(b"ticker;quantity\nXYZ;1\n")),
        "fichier trop gros": client.post(f"/csv{suffixe}", files=fichier(b"ticker;quantity\n" + b"KO;1\n" * 13_000)),
        "sans fichier": client.post(f"/csv{suffixe}"),
    }


@pytest.mark.parametrize("langue", LANGUES)
def test_aucun_refus_reel_ne_porte_de_commande_ni_ne_renvoie_a_l_application(client, langue):
    refus = _refus_reels(client, langue)
    for nom, reponse in refus.items():
        assert 400 <= reponse.status_code < 500, (nom, reponse.status_code)
        document = reponse.json()
        assert set(document) == {"detail", "problems"}, nom
        textes_publies = [document["detail"], *(p["problem"] for p in document["problems"])]
        for texte in textes_publies:
            assert interdits_dans(texte) == [], (langue, nom, texte)
    assert len({reponse.status_code for reponse in refus.values()}) >= 5


@pytest.mark.parametrize("langue", LANGUES)
def test_aucune_analyse_ne_porte_de_commande(client, catalogue, langue):
    """Les phrases d'une analyse sont celles du moteur et des règles. Sur la
    base du serveur, où chaque titre a tout l'historique, aucune ne dit quoi
    lancer : ni sur une ligne, ni sur toute la base."""
    for composition in ({"KO": 10}, {ticker: 10 for ticker in catalogue}):
        reponse = client.post(f"/analysis?lang={langue}", json=corps(composition))
        assert reponse.status_code == 200
        assert interdits_dans(reponse.text) == [], langue


def test_le_refus_local_du_meme_titre_porterait_la_commande(client_synthetique, portefeuille_synthetique):
    """Le témoin : l'application, elle, dit quoi lancer. C'est ce que le
    serveur public ne reprend pas."""
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": [{"ticker": "XYZ", "quantity": 1}]},
    )
    assert reponse.status_code == 422
    assert "python -m" in interdits_dans(reponse.json()["detail"])


# ═══════════════════════════════════════════════ Ce que le démarrage refuse ══


def _copie(base: Path, dossier: Path, modifier=None, empreinte: bool = True) -> Path:
    """Une copie de la base du serveur, modifiée, avec ou sans son empreinte."""
    copie = dossier / "serveur.sqlite"
    copie.write_bytes(base.read_bytes())
    if modifier is not None:
        with closing(sqlite3.connect(copie)) as conn, conn:
            modifier(conn)
    if empreinte:
        temoin = copie.with_name(copie.name + ".sha256")
        temoin.write_text(hashlib.sha256(copie.read_bytes()).hexdigest() + "\n", encoding="ascii")
    return copie


def test_une_copie_intacte_demarre(base_du_serveur, tmp_path):
    """Le témoin des refus qui suivent : la même copie, sans modification."""
    base = charger(_copie(base_du_serveur, tmp_path))
    assert base.date_gel == date.fromisoformat(DATE_GEL)
    assert len(base.catalogue) >= 2


@pytest.mark.parametrize(
    "modifier, attendu",
    (
        (
            lambda conn: conn.execute("INSERT INTO portfolios (owner, name) VALUES ('x', 'Privé')"),
            "portefeuille",
        ),
        (
            lambda conn: conn.execute("DELETE FROM prices WHERE ticker = 'KO' AND date = (SELECT MIN(date) FROM prices)"),
            "KO",
        ),
        (
            lambda conn: conn.execute("DELETE FROM prices WHERE ticker = 'PG'"),
            "PG",
        ),
        (
            lambda conn: conn.execute("DELETE FROM prices WHERE ticker = 'SPY'"),
            "SPY",
        ),
        (
            lambda conn: conn.execute("DELETE FROM prices WHERE date < '2010-01-01'"),
            "crise",
        ),
        (
            lambda conn: conn.execute("DELETE FROM prices WHERE date < '2026-01-01'"),
            "crise",
        ),
        (
            lambda conn: conn.execute("DELETE FROM prices"),
            "aucun",
        ),
    ),
    ids=("un portefeuille", "une séance manquante", "un titre sans prix", "sans l'indice", "après 2008", "trop court", "vide"),
)
def test_une_base_qu_un_serveur_public_ne_peut_pas_servir_est_refusee(
    base_du_serveur, tmp_path, modifier, attendu
):
    copie = _copie(base_du_serveur, tmp_path, modifier)
    with pytest.raises(BaseRefusee, match=attendu):
        charger(copie)
    # Et l'application ne démarre pas dessus.
    with pytest.raises(BaseRefusee):
        with serveur(copie):
            pass


def test_une_base_qui_n_a_pas_l_empreinte_ecrite_a_cote_d_elle_est_refusee(base_du_serveur, tmp_path):
    copie = _copie(base_du_serveur, tmp_path)
    copie.with_name(copie.name + ".sha256").write_text("0" * 64 + "\n", encoding="ascii")
    with pytest.raises(BaseRefusee, match="empreinte"):
        charger(copie)


def test_une_base_sans_empreinte_est_refusee(base_du_serveur, tmp_path):
    with pytest.raises(BaseRefusee, match="absente"):
        charger(_copie(base_du_serveur, tmp_path, empreinte=False))


def test_sans_la_variable_le_serveur_ne_demarre_pas(monkeypatch):
    """Aucun défaut : ni `MX_RISK_DB_PATH`, ni la base du dépôt."""
    monkeypatch.delenv(VARIABLE_BASE, raising=False)
    monkeypatch.setenv("MX_RISK_DB_PATH", "une-base-locale.sqlite")
    with pytest.raises(BaseRefusee, match=VARIABLE_BASE):
        with TestClient(create_public_app()):
            pass


def test_une_base_absente_est_refusee(monkeypatch, tmp_path):
    monkeypatch.setenv(VARIABLE_BASE, str(tmp_path / "absente.sqlite"))
    with pytest.raises(BaseRefusee, match="absente"):
        with TestClient(create_public_app()):
            pass


# ═════════════════════════════════════ La discipline de la couche API ══

MODULES_TENUS = tuple(DOSSIER / nom for nom in ("app.py", "routes.py", "schemas.py"))


def test_les_modules_tenus_existent_et_limites_n_en_est_pas():
    assert all(chemin.is_file() for chemin in MODULES_TENUS)
    # `limites.py` compte des requêtes : c'est de l'arithmétique, et il le dit.
    assert calculs_dans((DOSSIER / "limites.py").read_text(encoding="utf-8")) != []


@pytest.mark.parametrize("chemin", MODULES_TENUS, ids=lambda p: p.name)
def test_la_couche_publique_ne_fait_aucun_calcul(chemin):
    assert calculs_dans(chemin.read_text(encoding="utf-8"), chemin.name) == []


@pytest.mark.parametrize("chemin", MODULES_TENUS, ids=lambda p: p.name)
def test_la_couche_publique_n_ecrit_aucun_sql_et_n_ouvre_rien_d_elle_meme(chemin):
    assert [
        noeud.lineno
        for noeud in chaines_de_code(chemin)
        if any(mot in noeud.value.upper() for mot in MOTS_SQL)
    ] == []
    appels = {
        getattr(noeud.func, "attr", getattr(noeud.func, "id", None))
        for noeud in ast.walk(arbre(chemin))
        if isinstance(noeud, ast.Call)
    }
    assert "connect" not in appels


@pytest.mark.parametrize("chemin", MODULES_TENUS, ids=lambda p: p.name)
def test_la_couche_publique_n_exclut_aucun_champ_et_ne_convertit_rien_en_bloc(chemin):
    source = arbre(chemin)
    assert [n.arg for n in ast.walk(source) if isinstance(n, ast.keyword) and n.arg in EXCLUSIONS_INTERDITES] == []
    appels = {
        getattr(noeud.func, "attr", getattr(noeud.func, "id", None))
        for noeud in ast.walk(source)
        if isinstance(noeud, ast.Call)
    }
    assert not appels & {"asdict", "astuple"}


@pytest.mark.parametrize("chemin", sorted(DOSSIER.glob("*.py")), ids=lambda p: p.name)
def test_le_serveur_public_n_importe_aucun_module_de_calcul(chemin):
    for module, noms in imports_de(chemin):
        assert module not in CALCUL_INTERDIT, (chemin.name, module)
        if module in TYPES_AUTORISES:
            assert noms is not None and noms <= TYPES_AUTORISES[module], (chemin.name, module)


def test_limites_n_importe_rien_du_moteur():
    modules = {module for module, _ in imports_de(DOSSIER / "limites.py")}
    assert not any(module.startswith("backend") for module in modules), modules


def test_la_garde_des_calculs_mord():
    assert calculs_dans("perte = -report.total_value") != []
    assert calculs_dans("recus += len(corps)") != []


# ════════════════════════════════════════════════════ Le point d'entrée ══


def test_le_point_d_entree_ecoute_partout_sur_un_seul_processus_sans_journal_d_acces():
    source = arbre(DOSSIER / "__main__.py")
    mots_cles = {
        n.arg: n.value.value
        for n in ast.walk(source)
        if isinstance(n, ast.keyword) and isinstance(n.value, ast.Constant)
    }
    assert mots_cles["workers"] == 1
    assert mots_cles["access_log"] is False
    assert mots_cles["proxy_headers"] is False
    hotes = [
        n.value.value
        for n in ast.walk(source)
        if isinstance(n, ast.Assign)
        and any(getattr(c, "id", None) == "HOST" for c in n.targets)
    ]
    assert hotes == ["0.0.0.0"]
    assert "backend.public_api.app:app" in {c.value for c in chaines_de_code(DOSSIER / "__main__.py")}
