"""Le schéma commité et l'application ne peuvent pas diverger.

Le frontend engendre ses types TypeScript depuis `frontend/src/api/openapi.json`
et jamais depuis un serveur en marche (voir `tools/openapi_schema`). Ce fichier
est donc un CONTRAT : tant qu'il est juste, un champ retiré d'un schéma pydantic
casse la compilation du frontend, ce qui est exactement ce qu'on veut. S'il
prend du retard, le frontend compile contre une API qui n'existe plus et ne le
découvre qu'à l'exécution, dans le navigateur.

La garde est ici, dans la suite Python, et pas côté Node : c'est le backend qui
change, et une erreur doit se produire du côté qui a changé. La suite Python
tourne sans Node installé.
"""

from __future__ import annotations

import json

import pytest

from tools.openapi_schema import DESTINATION, schema, serialiser

COMMANDE = "python -m tools.openapi_schema"


@pytest.fixture(scope="module")
def commite() -> str:
    if not DESTINATION.exists():
        pytest.fail(f"{DESTINATION} est absent. Le produire : {COMMANDE}")
    return DESTINATION.read_text(encoding="utf-8")


def test_le_schema_commite_est_celui_que_l_application_publie(commite):
    """Comparaison OCTET POUR OCTET, pas de dictionnaires.

    Comparer les documents décodés laisserait passer une réindentation ou un
    changement d'ordre de clés : le fichier commité cesserait d'être ce que
    l'outil produit, et le prochain `python -m tools.openapi_schema` créerait un
    diff que personne n'a demandé. La sérialisation est fixée dans l'outil, et
    le test en dépend — ils ne peuvent pas en avoir deux idées différentes.
    """
    attendu = serialiser(schema())
    assert commite == attendu, (
        "Le schéma OpenAPI commité ne correspond plus à l'application. "
        f"Le régénérer : {COMMANDE}, puis « cd frontend && npm run api:types »."
    )


def test_le_schema_commite_est_du_json_valide(commite):
    document = json.loads(commite)
    assert document["openapi"].startswith("3.")
    assert document["info"]["title"] == "Mx Risk MGT"


def test_le_schema_decrit_les_routes_dont_le_frontend_depend(commite):
    """Les chemins que l'interface appelle, nommés un par un.

    Un renommage de route passerait la comparaison octet pour octet — le fichier
    serait régénéré et resterait cohérent avec l'application — tout en cassant
    le frontend en silence. Ces noms sont donc écrits ici.
    """
    chemins = json.loads(commite)["paths"]
    assert "/api/meta" in chemins
    assert "/api/portfolios" in chemins
    assert "/api/portfolios/{portfolio_id}/analysis" in chemins


def test_les_champs_que_le_bandeau_lit_sont_dans_le_schema(commite):
    """§8.1 — le bandeau ne lit que des champs publiés, jamais déduits."""
    analyse = json.loads(commite)["components"]["schemas"]["AnalysisOut"]
    for champ in (
        "as_of",
        "total_value",
        "estimation_window",
        "limiting_positions",
        "portfolio",
        "parameters",
    ):
        assert champ in analyse["properties"], champ
        assert champ in analyse["required"], champ
