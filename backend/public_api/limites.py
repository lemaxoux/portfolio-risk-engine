"""Les bornes du serveur public : ce qu'il accepte, et à quel rythme.

Le serveur public tourne sur une petite machine partagée, ouverte à tous. Ce
module porte ce qui le protège : les tailles admises et l'intergiciel qui les
tient, le nombre de requêtes par adresse, le nombre d'analyses en même temps.

═══ DES SEUILS CHOISIS, DÉCLARÉS COMME TELS ═══

Chaque constante ci-dessous dit si elle est CHOISIE ou DÉRIVÉE. Un seuil
choisi n'a pas de justification méthodologique : il borne une ressource, et
sa raison est écrite à côté de lui. La seule borne dérivée du serveur, le
nombre de lignes d'un portefeuille, n'est pas ici : c'est le nombre de titres
de la base, lu au démarrage (`base.py`).

═══ CE MODULE COMPTE, ET IL EST LE SEUL ═══

`app.py`, `routes.py` et `schemas.py` tiennent la discipline de la couche
API : ni arithmétique, ni SQL (`tests/test_serveur_public.py`). Compter des
requêtes et des octets est de l'arithmétique, donc ce module en est exclu
par son nom. En échange il ne publie aucun nombre, ne rédige aucun texte et
n'importe rien du moteur : il rend un booléen, une adresse, un tour de
calcul, ou passe la main à celui qui rédige le refus.

═══ L'ADRESSE DU CLIENT ═══

Le serveur est derrière les relais de son hébergeur : l'adresse de la
connexion est celle d'un relais. L'hébergeur écrit que l'adresse du client se
lit dans l'en-tête `X-Forwarded-For`, « not from the socket connection »
(Render, « How Render handles DDoS attacks », 2026-04-01). Il ne dit pas
QUELLE entrée de l'en-tête. Or cet en-tête ne fait que s'allonger par la
droite : ce qu'un client y écrit lui-même reste à gauche, et chaque relais
ajoute à droite l'adresse qu'il a vue. L'entrée de gauche se forge donc, et
la limite par adresse avec elle. La clé retenue est l'entrée comptée DEPUIS
LA DROITE, au rang `RANG_DE_L_ADRESSE`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Awaitable, Callable, Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from typing import Any

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException

# ═══════════════════════════════════════════════════════════ Les tailles ══

# Seuil CHOISI. Le corps d'une demande d'analyse, en octets. Une ligne de
# portefeuille fait moins de cent octets en JSON, et un portefeuille n'a pas
# plus de lignes que la base n'a de titres : dix fois la marge.
OCTETS_DU_CORPS_D_ANALYSE = 16_000

# Seuil CHOISI. Le fichier CSV lui-même. Un portefeuille tient en moins de
# mille octets ; un export de tableur traîne des lignes et des colonnes vides.
OCTETS_DU_FICHIER_CSV = 64_000

# Seuil CHOISI. Le corps de la requête qui porte ce fichier : le fichier,
# plus l'enveloppe `multipart/form-data`.
OCTETS_DU_CORPS_CSV = 80_000

# Ce que le lecteur lit du fichier : un octet de plus que la borne suffit à
# savoir qu'il la dépasse, comme dans `api/csv_import.py`.
SONDE_DU_FICHIER_CSV = OCTETS_DU_FICHIER_CSV + 1

# ═══════════════════════════════════════════════════════════ Les rythmes ══

# Seuils CHOISIS, provisoires : à relire avec la durée d'une analyse mesurée
# chez l'hébergeur. Le nombre de requêtes d'analyse ou de lecture de fichier
# qu'une même adresse peut faire par période. Une analyse prend quelques
# secondes d'un processeur que tous partagent : vingt par dix minutes
# laissent à une adresse une part du serveur, pas le serveur.
REQUETES_PAR_PERIODE = 20
PERIODE_EN_MINUTES = 10

# Seuil CHOISI. Le nombre d'adresses suivies pendant une période. Au-delà, une
# adresse nouvelle est refusée jusqu'à la période suivante : la table des
# compteurs ne grandit pas sans borne.
ADRESSES_SUIVIES = 10_000

# Seuil CHOISI, provisoire. Une analyse à la fois : la machine n'a pas de
# quoi en calculer deux. Trois peuvent attendre leur tour ; la suivante est
# refusée tout de suite, plutôt que de faire attendre un visiteur au-delà de
# ce qu'il attendra.
ANALYSES_EN_ATTENTE = 3

# Seuil CHOISI. La durée, en secondes, pendant laquelle un navigateur garde
# la réponse à une pré-requête CORS.
DUREE_DU_CACHE_CORS = 600

# Seuil CHOISI D'APRÈS UN RELEVÉ, non d'après la documentation de l'hébergeur,
# qui ne le donne pas : le rang, compté depuis la droite, de l'entrée de
# `X-Forwarded-For` qui porte l'adresse du client. À droite d'elle, les
# adresses que les relais de l'hébergeur ont ajoutées.
RANG_DE_L_ADRESSE = 3

ADRESSE_INCONNUE = "inconnue"


def adresse_du_client(x_forwarded_for: str | None, pair: str | None) -> str:
    """La clé du compteur : l'adresse du client telle que les relais l'ont vue.

    Sans l'en-tête (un essai sur le poste), l'adresse de la connexion. Avec
    moins d'entrées que le rang attendu, la première : il n'y a pas eu autant
    de relais, et rien n'a pu être écrit à gauche d'elle par un client.
    """
    entrees = [e.strip() for e in (x_forwarded_for or "").split(",") if e.strip()]
    if not entrees:
        return pair or ADRESSE_INCONNUE
    if len(entrees) < RANG_DE_L_ADRESSE:
        return entrees[0]
    return entrees[-RANG_DE_L_ADRESSE]


class CompteurParAdresse:
    """Au plus `maximum` requêtes par adresse et par période.

    Des périodes fixes, comptées depuis le démarrage : à chaque nouvelle
    période, tous les compteurs repartent de zéro. C'est plus simple qu'une
    fenêtre glissante et cela suffit à ce que la limite protège. `horloge` se
    remplace dans les tests.
    """

    def __init__(
        self,
        maximum: int = REQUETES_PAR_PERIODE,
        periode_en_minutes: int = PERIODE_EN_MINUTES,
        adresses: int = ADRESSES_SUIVIES,
        horloge: Callable[[], float] = time.monotonic,
    ) -> None:
        # Publics : le refus cite la limite qui est appliquée, pas une copie.
        self.maximum = maximum
        self.periode_en_minutes = periode_en_minutes
        self._periode = periode_en_minutes * 60
        self._adresses = adresses
        self._horloge = horloge
        self._verrou = threading.Lock()
        self._rang = 0
        self._comptes: dict[str, int] = {}

    def admet(self, adresse: str) -> bool:
        """Compte la requête, et dit si elle est dans la limite."""
        with self._verrou:
            rang = int(self._horloge() // self._periode)
            if rang != self._rang:
                self._rang = rang
                self._comptes = {}
            deja = self._comptes.get(adresse)
            if deja is None and len(self._comptes) >= self._adresses:
                return False
            compte = (deja or 0) + 1
            self._comptes[adresse] = compte
            return compte <= self.maximum


class ServeurOccupe(Exception):
    """Trop d'analyses attendent déjà leur tour."""


class FileDAnalyses:
    """Une analyse à la fois, et `en_attente` qui attendent leur tour.

    Les routes tournent dans des fils : celle qui obtient une place attend le
    verrou du calcul, les autres sont refusées sans attendre.
    """

    def __init__(self, en_attente: int = ANALYSES_EN_ATTENTE) -> None:
        self._places = threading.BoundedSemaphore(1 + en_attente)
        self._calcul = threading.Lock()

    @contextmanager
    def tour(self) -> Iterator[None]:
        if not self._places.acquire(blocking=False):
            raise ServeurOccupe()
        try:
            with self._calcul:
                yield
        finally:
            self._places.release()


# ════════════════════════════════════════════════════ La borne du corps ══

Portee = MutableMapping[str, Any]
Recevoir = Callable[[], Awaitable[MutableMapping[str, Any]]]
Envoyer = Callable[[MutableMapping[str, Any]], Awaitable[None]]
Application = Callable[[Portee, Recevoir, Envoyer], Awaitable[None]]

# Où la borne appliquée à une requête est notée, pour que le refus la cite.
CLE_DE_LA_BORNE = "mx_risk.borne_du_corps"


class CorpsTropVolumineux(HTTPException):
    """Le corps reçu dépasse la borne de sa route.

    Une `HTTPException` : levée pendant la lecture du corps, elle traverse
    FastAPI telle quelle, là où toute autre exception y deviendrait un 400
    sans raison lisible.
    """

    def __init__(self, borne: int) -> None:
        super().__init__(status_code=413)
        self.borne = borne


class BorneDuCorps:
    """Refuse un corps plus gros que la borne de sa route, AVANT de le lire.

    Deux contrôles, parce que l'en-tête `Content-Length` peut manquer : sur
    l'en-tête quand il est là, sans lire un octet ; puis sur les octets
    réellement reçus, comptés au fil de la lecture. Sans le second, un corps
    envoyé par morceaux passerait la borne sans la déclarer.

    `refuser` rend la réponse du refus : elle est rédigée par l'application,
    pas ici.
    """

    def __init__(
        self,
        app: Application,
        bornes: Mapping[str, int],
        par_defaut: int,
        refuser: Callable[[Portee, int], Application],
    ) -> None:
        self.app = app
        self._bornes = bornes
        self._par_defaut = par_defaut
        self._refuser = refuser

    async def __call__(self, scope: Portee, receive: Recevoir, send: Envoyer) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        borne = self._bornes.get(scope["path"], self._par_defaut)
        scope[CLE_DE_LA_BORNE] = borne
        declare = Headers(scope=scope).get("content-length", "")
        if declare.isdigit() and int(declare) > borne:
            await self._refuser(scope, borne)(scope, receive, send)
            return

        recus = 0

        async def recevoir() -> MutableMapping[str, Any]:
            nonlocal recus
            message = await receive()
            if message["type"] == "http.request":
                recus += len(message.get("body", b""))
                if recus > borne:
                    raise CorpsTropVolumineux(borne)
            return message

        await self.app(scope, recevoir, send)
