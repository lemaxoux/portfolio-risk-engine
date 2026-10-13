"""Le schéma commité du serveur public et le serveur ne peuvent pas diverger.

Le serveur public ne sert ni `/docs` ni `/openapi.json` (chantier 9.6). Son
schéma n'existe que dans le dépôt, dans
`frontend/src/api/openapi.public.json`, d'où le client engendre le type de la
réponse d'analyse publique. Comme pour l'application
(`tests/test_openapi_schema.py`), le fichier est comparé OCTET POUR OCTET à ce
que le serveur produirait : un champ ajouté sans régénération fait échouer la
suite Python, du côté qui a changé.

Le fichier est aussi lu pour ce qu'il ne doit pas contenir : une route de
plus, un identifiant de portefeuille, une série.
"""

from __future__ import annotations

import json

import pytest

from tools.openapi_schema import (
    DESTINATION,
    DESTINATION_PUBLIQUE,
    schema_public,
    serialiser,
)

COMMANDE = "python -m tools.openapi_schema"


@pytest.fixture(scope="module")
def commite() -> str:
    if not DESTINATION_PUBLIQUE.exists():
        pytest.fail(f"{DESTINATION_PUBLIQUE} est absent. Le produire : {COMMANDE}")
    return DESTINATION_PUBLIQUE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def document(commite) -> dict:
    return json.loads(commite)


def test_le_schema_public_commite_est_celui_du_serveur(commite):
    attendu = serialiser(schema_public())
    assert commite == attendu, (
        "Le schéma commité du serveur public ne correspond plus au serveur. "
        f"Le régénérer : {COMMANDE}, puis « cd frontend && npm run api:types »."
    )


def test_il_est_ecrit_en_fins_de_ligne_unix():
    assert b"\r" not in DESTINATION_PUBLIQUE.read_bytes()


def test_il_ne_decrit_que_les_trois_routes(document):
    assert {
        (chemin, methode) for chemin, methodes in document["paths"].items() for methode in methodes
    } == {("/health", "get"), ("/analysis", "post"), ("/csv", "post")}
    assert document["openapi"].startswith("3.")


def test_la_reponse_d_analyse_publique_n_a_ni_identifiant_ni_serie(document):
    schemas = document["components"]["schemas"]
    champs = set(schemas["PublicAnalysisOut"]["properties"])
    assert not champs & {"portfolio_id", "portfolio", "series"}
    assert {"as_of", "risk", "histogram", "scenarios", "regimes", "observations", "disclaimer"} <= champs
    # Les modèles que seule une série ou un portefeuille stocké emploient
    # n'entrent pas dans le schéma : rien ne les y référence.
    assert not set(schemas) & {"PointOut", "PortfolioSeriesOut", "PortfolioOut", "PortfolioDetailOut"}
    texte = json.dumps(document)
    assert "PortfolioSeriesOut" not in texte and "PointOut" not in texte


def test_la_route_d_analyse_ne_prend_que_la_langue(document):
    parametres = document["paths"]["/analysis"]["post"].get("parameters", [])
    assert [(p["name"], p["in"]) for p in parametres] == [("lang", "query")]
    assert document["paths"]["/health"]["get"].get("parameters", []) == []


def test_les_sous_objets_sont_ceux_de_l_application(document):
    """La même mesure se publie de la même façon des deux côtés : un schéma
    de même nom a la même définition dans les deux fichiers."""
    locaux = json.loads(DESTINATION.read_text(encoding="utf-8"))["components"]["schemas"]
    publics = document["components"]["schemas"]
    communs = sorted(set(locaux) & set(publics))
    assert len(communs) >= 30
    assert [nom for nom in communs if locaux[nom] != publics[nom]] == []
    assert sorted(set(publics) - set(locaux)) == [
        "Body_lire_un_fichier_csv_post",
        "HealthOut",
        "PublicAnalysisIn",
        "PublicAnalysisOut",
        "PublicCsvOut",
    ]
