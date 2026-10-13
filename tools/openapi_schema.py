"""Écrit le schéma OpenAPI de l'API dans `frontend/src/api/openapi.json`, et
celui du serveur public dans `frontend/src/api/openapi.public.json`.

    python -m tools.openapi_schema

═══ POURQUOI UN FICHIER COMMITÉ, ET PAS UN SERVEUR QU'ON INTERROGE ═══

Les types TypeScript du frontend sont ENGENDRÉS, jamais écrits à la main : un
type de réponse recopié à la main diverge du schéma dès la première migration,
et le compilateur, lui, continue de dire que tout va bien. `openapi-typescript`
sait lire un serveur en marche — et c'est exactement ce qu'on ne veut pas :

* un `npm run build` dépendrait d'un `uvicorn` allumé, donc d'une base à jour,
  donc d'une machine particulière ;
* le contrat engendré ne serait vérifiable par personne après coup, puisque la
  source aurait disparu avec le processus ;
* rien ne dirait, en relisant un commit, quel schéma le frontend compilait.

Le fichier est donc commité, et un test Python le compare OCTET POUR OCTET à ce
que l'application produit aujourd'hui. Un champ ajouté à un schéma pydantic sans
régénération fait échouer la suite Python — du côté qui a changé, pas six mois
plus tard dans le navigateur.

═══ LA SÉRIALISATION EST FIXÉE ICI ═══

`indent=2`, `ensure_ascii=False`, ordre des clés préservé, une ligne vide
finale. Elle est écrite dans `serialiser()` plutôt que dans l'appel, pour que le
test et l'outil ne puissent pas en avoir deux idées différentes — c'est tout
l'intérêt d'une comparaison octet pour octet.

═══ LE SERVEUR PUBLIC NE SERT PAS SON SCHÉMA ═══

Le serveur public (`backend/public_api/`, chantier 9.6) n'a ni `/docs` ni
`/openapi.json`. Son schéma n'existe donc qu'ici, commité comme l'autre et
tenu de même (`tests/test_openapi_public.py`) : le client y engendre le type
de la réponse d'analyse publique, qui n'est pas celui de l'application.
"""

from __future__ import annotations

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "frontend" / "src" / "api" / "openapi.json"
DESTINATION_PUBLIQUE = RACINE / "frontend" / "src" / "api" / "openapi.public.json"


def schema() -> dict:
    """Le schéma que l'application publie, tel quel.

    L'import est local : charger l'application au niveau du module ferait payer
    FastAPI et pydantic à quiconque importe ce fichier pour lire `DESTINATION`.
    """
    from backend.api.app import app

    return app.openapi()


def schema_public() -> dict:
    """Le schéma du serveur public, qu'aucune de ses routes ne sert."""
    from backend.public_api.app import app

    return app.openapi()


def serialiser(document: dict) -> str:
    """Le texte exact du fichier commité."""
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def ecrire() -> Path:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(serialiser(schema()), encoding="utf-8", newline="\n")
    return DESTINATION


def ecrire_public() -> Path:
    DESTINATION_PUBLIQUE.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION_PUBLIQUE.write_text(
        serialiser(schema_public()), encoding="utf-8", newline="\n"
    )
    return DESTINATION_PUBLIQUE


if __name__ == "__main__":
    chemin = ecrire()
    print(f"Schéma OpenAPI écrit : {chemin.relative_to(RACINE)}")
    chemin = ecrire_public()
    print(f"Schéma du serveur public écrit : {chemin.relative_to(RACINE)}")
    print("Régénérer les types : cd frontend && npm run api:types")
