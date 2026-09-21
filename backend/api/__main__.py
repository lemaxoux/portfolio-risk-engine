"""Lancement local de l'API.

    python -m backend.api

L'adresse d'écoute est ÉCRITE ICI, pas laissée en option. L'API n'a ni
authentification ni notion d'utilisateur : la lier à `0.0.0.0` donnerait à
quiconque partage le réseau le droit de lire et de supprimer les portefeuilles.
Un défaut qu'on peut contredire d'un argument de ligne de commande est un défaut
qu'on finit par contredire.
"""

from __future__ import annotations

import uvicorn

HOST = "127.0.0.1"
PORT = 8000

if __name__ == "__main__":
    uvicorn.run("backend.api.app:app", host=HOST, port=PORT, reload=False)
