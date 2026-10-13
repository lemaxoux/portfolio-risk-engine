"""Lancement du serveur public.

    python -m backend.public_api

À L'INVERSE DE L'APPLICATION LOCALE, ce serveur écoute sur toutes les
interfaces : il est fait pour être joint de l'extérieur, derrière les relais
de son hébergeur, qui lui donne son port dans `PORT`. C'est sans danger pour
la même raison que l'application locale, elle, doit rester sur la boucle
locale : celle-ci n'a rien à protéger. Elle ne stocke aucun portefeuille, ne
lit sa base qu'en lecture seule, et n'a aucune route d'écriture
(`backend/public_api/app.py`).

Un seul processus : la machine n'a pas de quoi en porter deux, et la file des
analyses (`limites.py`) suppose qu'il n'y en a qu'un. Ni journal d'accès, ni
relecture des en-têtes de relais par uvicorn : l'adresse du client est lue à
un seul endroit (`limites.adresse_du_client`).
"""

from __future__ import annotations

import os

import uvicorn

HOST = "0.0.0.0"
PORT_PAR_DEFAUT = "10000"

if __name__ == "__main__":
    uvicorn.run(
        "backend.public_api.app:app",
        host=HOST,
        port=int(os.environ.get("PORT", PORT_PAR_DEFAUT)),
        workers=1,
        access_log=False,
        proxy_headers=False,
        server_header=False,
    )
