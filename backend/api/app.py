"""Application FastAPI — la seule porte d'entrée HTTP du moteur.

LIÉE À 127.0.0.1 UNIQUEMENT. Le projet est mono-utilisateur et local : il n'a ni
authentification, ni notion d'utilisateur, ni contrôle d'accès. Exposer une API
sans authentification sur une interface réseau donnerait à quiconque partage le
réseau le droit de lire et de supprimer les portefeuilles. L'adresse est donc
imposée par `backend/api/__main__.py` plutôt que laissée à une option de ligne
de commande qu'on oublie.

CE QUE CETTE COUCHE NE FAIT PAS — aucun calcul, aucune arithmétique, aucun SQL.
Elle valide ce qui entre, appelle le moteur, sérialise ce qui sort et traduit les
exceptions en codes HTTP. Chaque nombre publié vient d'une fonction du moteur
déjà testée ; un test le vérifie en inspectant l'arbre syntaxique des modules de
`backend/api/`.

LE FRONTEND EST SERVI PAR CETTE MÊME APPLICATION — `backend/api/static.py`
rend `frontend/dist` à la racine quand le bundle existe. Il n'y a donc qu'une
origine en production, et AUCUN middleware CORS : en développement c'est Vite
qui relaie `/api`, ce qui garde la permission du côté qui en a besoin plutôt
que de la laisser en place dans le serveur, où elle ne servirait jamais.

NaN ET INFINITY — `json.dumps` les écrit tels quels, et `JSON.parse` côté
navigateur plante dessus. Deux gardes se complètent : les schémas pydantic les
refusent à la construction, en nommant le champ fautif, et le rendu JSON de
Starlette refuse de les écrire. Un test relit les OCTETS d'une vraie réponse avec
un analyseur strict, parce que c'est le seul endroit où la garantie compte.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.db.init_db import connect, get_db_path
from backend.db.migrate import missing_schema_hint

from .errors import register_handlers
from .routes import (
    analysis_router,
    meta_router,
    portfolios_router,
    securities_router,
)
from .static import register_frontend

API_PREFIX = "/api"

DESCRIPTION = """
Moteur de risque de portefeuille, exposé en lecture et en écriture locale.

**Toutes les valeurs sont des fractions**, jamais des pourcentages : une VaR de
1,38 % se lit `0.0138`. Le formatage — pourcentage, virgule décimale, arrondi —
est décidé côté client, à un seul endroit.

**Chaque mesure porte sa propre fenêtre d'estimation.** Il n'y a délibérément
aucune fenêtre au niveau du document : le beta est régressé sous une contrainte
d'échantillon qui lui est propre, et un scénario à couverture partielle a sa
propre portée.

**L'analyse est un seul endpoint.** Une page assemblée à partir de plusieurs
appels pourrait mélanger deux états de la base sans le signaler.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Refuse de démarrer sur une base dont le schéma n'est pas à jour.

    Sans ce contrôle, la panne se produirait à la première requête, sous la
    forme d'un « no such column: portfolios.name » en 500 — un message qui ne
    dit pas quoi faire. Ici elle se produit au démarrage, avec la commande à
    lancer. Aucune écriture : migrer la base de quelqu'un sans le lui demander
    n'appartient pas à un serveur web.
    """
    conn = connect()
    try:
        manque = missing_schema_hint(conn)
    finally:
        conn.close()
    if manque is not None:
        raise RuntimeError(f"{manque} (base : {get_db_path()})")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Portfolio Risk Engine",
        description=DESCRIPTION,
        version="0.7.0",
        lifespan=lifespan,
    )
    register_handlers(app)
    for router in (
        meta_router,
        securities_router,
        portfolios_router,
        analysis_router,
    ):
        app.include_router(router, prefix=API_PREFIX)

    # APRÈS les routeurs, jamais avant : la route attrape-tout du frontend
    # correspond à n'importe quel chemin, et Starlette retient la PREMIÈRE
    # correspondance complète. Déclarée en tête, elle avalerait l'API entière.
    register_frontend(app)
    return app


app = create_app()
