"""Le serveur public : une application à part, ouverte à tous, sans état.

Le site de démonstration est statique. Pour qu'un visiteur y analyse SON
portefeuille, composé parmi les titres de la base figée, il faut un serveur
qui calcule : celui-ci (chantier 9.6). Il reçoit une composition, la fait
analyser par le moteur, rend l'analyse, et ne garde rien.

═══ UNE APPLICATION À PART, PAS L'APPLICATION LOCALE AMPUTÉE ═══

`backend/api/app.py` est une application pour UN utilisateur, sur SON poste :
elle écrit des portefeuilles, sert `/docs`, lit `.env`, et son ingestion
appelle un fournisseur de prix. En faire un serveur public par une
configuration qui retirerait des routes laisserait le reste à une option
d'être de retour. Ce module ne l'importe donc pas : il ne branche que ce qu'il
déclare, et un interpréteur qui le charge ne charge ni l'ingestion, ni le
fournisseur, ni sa bibliothèque réseau, ni de quoi lire `.env`
(`tests/test_serveur_public_frontiere.py`).

═══ CE QU'ELLE N'A PAS ═══

* Aucune route de liste, aucune route d'écriture : trois routes
  (`routes.py`).
* Ni `/docs`, ni `/redoc`, ni `/openapi.json`. Le schéma se lit dans le dépôt
  (`frontend/src/api/openapi.public.json`).
* Aucune écriture possible : la base est ouverte en lecture seule
  (`db/lecture_seule.py`).
* Aucun journal du corps des requêtes. Le filet des erreurs imprévues n'écrit
  que le nom de l'exception et le chemin : la trace d'une erreur de
  validation recopie ce qu'elle a reçu.

═══ CE QUE PORTE CHAQUE RÉPONSE ═══

`X-Robots-Tag: noindex` et `Cache-Control: no-store`, sur toutes : succès,
refus, chemin inconnu, pré-requête CORS. L'intergiciel qui les pose est le
plus extérieur.

═══ CORS : UNE ORIGINE, SANS IDENTIFIANTS ═══

Le site et ce serveur n'ont pas la même origine ; le navigateur ne laisse le
site lire une réponse que si le serveur l'y autorise. Une seule origine est
autorisée, celle du site, écrite ici. Une origine de développement ne s'y
ajoute que par une variable d'environnement, jamais par défaut.

CORS empêche un autre site de LIRE une réponse, pas de la faire calculer : un
formulaire part sans pré-requête. Une requête d'écriture qui porte une
origine autre que celle du site est donc refusée (403) avant tout calcul.
Une requête sans origine (un outil en ligne de commande) passe : elle n'engage
le navigateur de personne.

═══ L'ORDRE DES INTERGICIELS ═══

Du plus extérieur au plus intérieur : les en-têtes, CORS, le filet, l'origine,
la borne du corps, puis les routes. Un refus du filet ou de l'origine
traverse donc CORS et les en-têtes, et le site peut le lire.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from types import ModuleType

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from backend.api.errors import ApiError, Problem, _body, _champ, _valeur
from backend.api.langue import langue_de_la_requete
from backend.textes import textes

from .base import charger
from .limites import (
    DUREE_DU_CACHE_CORS,
    OCTETS_DU_CORPS_CSV,
    OCTETS_DU_CORPS_D_ANALYSE,
    Application,
    BorneDuCorps,
    CompteurParAdresse,
    CorpsTropVolumineux,
    Envoyer,
    FileDAnalyses,
    Portee,
    Recevoir,
)
from .routes import router

# La seule origine autorisée : le site de démonstration.
ORIGINE_DU_SITE = "https://portfolio-risk-engine-lemaxoux.pages.dev"

# Une origine de plus, pour essayer le site sur son poste. Sans défaut : un
# serveur déployé sans cette variable n'autorise que le site.
VARIABLE_ORIGINE_DE_DEVELOPPEMENT = "MX_RISK_ORIGINE_DE_DEVELOPPEMENT"

# La borne du corps de chaque route qui en lit un. Ailleurs, la plus petite :
# aucune autre route ne lit de corps.
BORNES_DU_CORPS = {"/analysis": OCTETS_DU_CORPS_D_ANALYSE, "/csv": OCTETS_DU_CORPS_CSV}

JOURNAL = logging.getLogger("backend.public_api")

DESCRIPTION = """
Le serveur public de Portfolio Risk Engine : l'analyse d'une composition,
choisie parmi les titres d'une base figée, sans rien enregistrer.

**Trois routes** : le réveil, l'analyse, la lecture d'un fichier CSV.

**Aucune série** : la réponse d'analyse ne porte aucune liste de points
datés, et la route n'a ni fenêtre ni indice en paramètre.
"""


def origines_admises() -> tuple[str, ...]:
    """L'origine du site, et celle de développement si la variable la donne."""
    developpement = os.environ.get(VARIABLE_ORIGINE_DE_DEVELOPPEMENT, "").strip()
    return (ORIGINE_DU_SITE, developpement) if developpement else (ORIGINE_DU_SITE,)


def _refus(
    scope: Portee, statut: int, texte: Callable[[ModuleType], str]
) -> JSONResponse:
    """Un refus rédigé hors des routes, dans la langue de l'adresse, avec le
    corps de tous les autres : `detail`, puis `problems`."""
    t = textes(langue_de_la_requete(Request(scope))).public
    return JSONResponse(status_code=statut, content=_body(texte(t), ()))


# ═══════════════════════════════════════════════════════ Les intergiciels ══


class EnTetes:
    """`X-Robots-Tag: noindex` et `Cache-Control: no-store` sur chaque réponse."""

    def __init__(self, app: Application) -> None:
        self.app = app

    async def __call__(self, scope: Portee, receive: Recevoir, send: Envoyer) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def envoyer(message) -> None:
            if message["type"] == "http.response.start":
                en_tetes = MutableHeaders(scope=message)
                en_tetes["X-Robots-Tag"] = "noindex"
                en_tetes["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, envoyer)


class Filet:
    """Une erreur imprévue rend le texte du serveur, jamais sa trace.

    Le journal reçoit le nom de l'exception et le chemin, rien de ce que la
    requête portait.
    """

    def __init__(self, app: Application) -> None:
        self.app = app

    async def __call__(self, scope: Portee, receive: Recevoir, send: Envoyer) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        commencee = False

        async def envoyer(message) -> None:
            nonlocal commencee
            if message["type"] == "http.response.start":
                commencee = True
            await send(message)

        try:
            await self.app(scope, receive, envoyer)
        except Exception as exc:
            JOURNAL.error("%s sur %s", type(exc).__name__, scope.get("path"))
            if commencee:
                raise
            reponse = _refus(
                scope, status.HTTP_500_INTERNAL_SERVER_ERROR, lambda t: t.ERREUR_INTERNE
            )
            await reponse(scope, receive, send)


class Origine:
    """Refuse une requête d'écriture venue d'une autre origine que le site."""

    def __init__(self, app: Application, admises: tuple[str, ...]) -> None:
        self.app = app
        self._admises = admises

    async def __call__(self, scope: Portee, receive: Recevoir, send: Envoyer) -> None:
        if scope["type"] == "http" and scope["method"] == "POST":
            origine = Headers(scope=scope).get("origin")
            if origine is not None and origine not in self._admises:
                reponse = _refus(scope, status.HTTP_403_FORBIDDEN, lambda t: t.ORIGINE_REFUSEE)
                await reponse(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _corps_refuse(scope: Portee, borne: int) -> JSONResponse:
    return _refus(
        scope, status.HTTP_413_CONTENT_TOO_LARGE, lambda t: t.corps_trop_volumineux(borne)
    )


# ═══════════════════════════════════════════════════════════ Les refus ══


def brancher_les_refus(app: FastAPI) -> None:
    """Les gestionnaires d'erreur : la forme de ceux de l'application, les
    textes du serveur public."""

    @app.exception_handler(ApiError)
    def _erreur(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.detail, exc.problems)
        )

    @app.exception_handler(RequestValidationError)
    def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Le message de pydantic est publié tel quel, en anglais dans les
        # deux langues, comme dans l'application ; seuls ses replis sont
        # rédigés.
        t = textes(langue_de_la_requete(request)).public
        problemes = tuple(
            Problem(
                problem=erreur.get("msg", t.VALEUR_REFUSEE),
                field=_champ(erreur.get("loc", ())),
                value=_valeur(erreur.get("input")),
            )
            for erreur in exc.errors()
        )
        detail = problemes[0].problem if problemes else t.REQUETE_REFUSEE
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_body(detail, problemes),
        )

    @app.exception_handler(HTTPException)
    def _http(request: Request, exc: HTTPException) -> JSONResponse:
        # Les refus de Starlette et de FastAPI (chemin inconnu, méthode,
        # corps illisible) prennent le corps des autres et un texte du
        # serveur public : jamais leur phrase d'origine.
        t = textes(langue_de_la_requete(request)).public
        if isinstance(exc, CorpsTropVolumineux):
            detail = t.corps_trop_volumineux(exc.borne)
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            detail = t.ROUTE_INCONNUE
        elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            detail = t.METHODE_REFUSEE
        else:
            detail = t.REQUETE_REFUSEE
        return JSONResponse(
            status_code=exc.status_code, content=_body(detail, ()), headers=exc.headers
        )


# ════════════════════════════════════════════════════════ L'application ══


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Contrôle la base avant la première requête, et refuse de démarrer sur
    une base qu'un serveur public ne peut pas servir (`base.py`)."""
    app.state.base = charger()
    yield


def create_public_app(
    *,
    compteur: CompteurParAdresse | None = None,
    file: FileDAnalyses | None = None,
) -> FastAPI:
    """L'application du serveur public. `compteur` et `file` se remplacent
    dans les tests ; par défaut, les seuils de `limites.py`."""
    app = FastAPI(
        title="Portfolio Risk Engine, serveur public",
        description=DESCRIPTION,
        version="0.7.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        # Un chemin à une barre près n'est pas redirigé : il est inconnu, et
        # reçoit le refus du serveur, pas une redirection de la bibliothèque.
        redirect_slashes=False,
    )
    app.state.compteur = CompteurParAdresse() if compteur is None else compteur
    app.state.file = FileDAnalyses() if file is None else file
    brancher_les_refus(app)
    app.include_router(router)

    # `add_middleware` empile : le dernier ajouté est le plus extérieur.
    admises = origines_admises()
    app.add_middleware(
        BorneDuCorps,
        bornes=BORNES_DU_CORPS,
        par_defaut=min(BORNES_DU_CORPS.values()),
        refuser=_corps_refuse,
    )
    app.add_middleware(Origine, admises=admises)
    app.add_middleware(Filet)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(admises),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        max_age=DUREE_DU_CACHE_CORS,
    )
    app.add_middleware(EnTetes)
    return app


app = create_public_app()
