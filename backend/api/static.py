"""Service des fichiers statiques du frontend, en production.

    frontend/dist/  →  /

En développement, c'est Vite qui sert la page et relaie `/api` vers cette
application (voir `frontend/vite.config.ts`). En production il n'y a qu'un seul
processus : FastAPI sert le bundle à la racine, donc à la MÊME ORIGINE que
l'API. C'est la raison pour laquelle le backend n'a et n'aura pas de middleware
CORS — il n'y a pas deux origines à réconcilier.

═══ DEUX PROPRIÉTÉS, ET ELLES SE CONTREDISENT SI ON N'Y PREND PAS GARDE ═══

1. **Le repli sur `index.html`.** Les routes du client n'existent pas sur le
   serveur : `/methodologie` doit rendre l'application, pas un 404, sinon un
   rechargement ou un lien partagé tombe sur une page d'erreur.

2. **Le repli ne masque JAMAIS l'API.** Un repli écrit naïvement rend
   `index.html` pour TOUT chemin inconnu, `/api/nexiste-pas` compris. Le client
   reçoit alors 200 et du HTML là où il attendait du JSON, `JSON.parse` échoue
   sur « <!doctype », et l'erreur qu'il affiche ne parle plus de la requête qui
   a échoué. Une faute de frappe dans une URL d'API deviendrait indébogable.

D'où le contrôle explicite sur le préfixe : sous `/api`, ce module refuse en
JSON, dans la même forme que le reste de l'API (`errors.py`).

═══ POURQUOI UNE ROUTE ATTRAPE-TOUT ET PAS UN `Mount` ═══

Un `Mount("/", StaticFiles(html=True))` répondrait FULL MATCH à n'importe quel
chemin, pour n'importe quelle méthode. Starlette ne retient le « 405 méthode
non autorisée » que s'il ne trouve AUCUNE correspondance complète : le montage
transformerait donc tout `POST /api/meta` en 404, en écrasant un diagnostic
juste par un faux.

La route attrape-tout ci-dessous est limitée à GET et HEAD. Une méthode
d'écriture sur un chemin d'API existant ne lui correspond donc pas plus qu'à la
vraie route, les deux restent des correspondances partielles, et Starlette rend
bien 405.

═══ SANS `dist`, L'APPLICATION DÉMARRE QUAND MÊME ═══

Rien n'est monté si le dossier n'existe pas. La suite Python tourne sans Node
installé, et `python -m backend.api` sur une machine où le frontend n'a jamais
été construit sert l'API seule au lieu de refuser de démarrer.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import FileResponse, JSONResponse

from backend.langue import Langue
from backend.textes import textes

from .langue import langue_de_la_requete

# `joinpath` plutôt que l'opérateur `/` de pathlib, dans tout ce module : la
# garde d'arithmétique de `tests/test_api_discipline.py` lit l'arbre syntaxique,
# où une division de chemins et une division de nombres sont le MÊME nœud. La
# garde ne peut pas les distinguer, et l'assouplir pour ce cas rouvrirait la
# porte à la division qu'elle existe pour interdire. C'est donc le code qui
# s'adapte, et il y gagne en intention explicite.
RACINE = Path(__file__).resolve().parents[2]
DEFAUT = RACINE.joinpath("frontend", "dist")

#: Surcharge du dossier servi, comme `MX_RISK_DB_PATH` pour la base. Les tests
#: s'en servent pour décrire les deux états — avec et sans bundle — sans
#: dépendre de ce qui traîne dans l'arborescence de développement.
VARIABLE = "MX_RISK_FRONTEND_DIST"

INDEX = "index.html"
PREFIXE_API = "api"


def dossier_dist() -> Path:
    surcharge = os.environ.get(VARIABLE)
    return Path(surcharge) if surcharge else DEFAUT


def _fichier_servi(dist: Path, chemin: str) -> Path | None:
    """Le fichier demandé, ou `None` s'il n'y en a pas.

    `resolve()` puis contrôle d'appartenance : sans lui, une requête vers
    `../../.env` sortirait du dossier servi. Le contrôle porte sur le chemin
    RÉSOLU, seul état où « .. » et les liens symboliques ont déjà été
    interprétés — filtrer la chaîne d'entrée laisserait passer les formes
    encodées.
    """
    if not chemin:
        return None
    try:
        candidat = dist.joinpath(chemin).resolve()
    except OSError:
        return None
    if not candidat.is_relative_to(dist.resolve()):
        return None
    return candidat if candidat.is_file() else None


def _refus_api(chemin: str, langue: Langue) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": textes(langue).api.route_inconnue(chemin),
            "problems": [],
        },
    )


def register_frontend(app: FastAPI) -> bool:
    """Branche le service du bundle. Rend False si `dist` est absent."""
    dist = dossier_dist()
    index = dist.joinpath(INDEX)
    if not index.is_file():
        return False

    @app.get("/{chemin_complet:path}", include_in_schema=False)
    def servir(chemin_complet: str, request: Request):
        """Un fichier du bundle, ou `index.html` — sauf sous `/api`, où le
        refus est rédigé dans la langue de l'adresse (`?lang=en`)."""
        segments = chemin_complet.split("/")
        if segments[0] == PREFIXE_API:
            return _refus_api(chemin_complet, langue_de_la_requete(request))

        fichier = _fichier_servi(dist, chemin_complet)
        if fichier is not None:
            return FileResponse(fichier)

        # Les noms des ressources construites portent leur empreinte : un
        # `index.html` gardé en cache pointerait sur des fichiers qui n'existent
        # plus après une reconstruction, et la page resterait blanche jusqu'à un
        # rechargement forcé.
        return FileResponse(index, headers={"Cache-Control": "no-store"})

    return True
