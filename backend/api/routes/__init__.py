"""Routes de l'API. Une route valide, appelle, sérialise — elle ne calcule pas.

Toutes sont écrites en `def` et non en `async def` : elles font du SQLite et du
pandas, deux travaux bloquants. FastAPI exécute une route synchrone dans un fil
du pool ; la déclarer `async` la ferait tourner dans la boucle d'événements, où
chaque analyse gèlerait toutes les autres requêtes pendant son calcul.
"""

from __future__ import annotations

from .analysis import router as analysis_router
from .meta import router as meta_router
from .portfolios import router as portfolios_router
from .securities import router as securities_router

__all__ = [
    "analysis_router",
    "meta_router",
    "portfolios_router",
    "securities_router",
]
