"""La langue des textes publiés : `?lang=fr` ou `?lang=en` (chantier 7D).

UN PARAMÈTRE DE REQUÊTE, PAS L'EN-TÊTE `Accept-Language`. Le navigateur envoie
celui-ci tout seul : un Chrome réglé en anglais recevrait l'anglais sans que
personne l'ait demandé, et la réponse française changerait sous les pieds du
client. Le paramètre se voit dans l'adresse, dans les journaux et dans les
tests, et OpenAPI le type.

LE FRANÇAIS PAR DÉFAUT. Sans `lang`, ou avec `lang=fr`, chaque réponse est
celle d'avant le chantier, octet pour octet. Une autre valeur est refusée en
422, comme tout paramètre hors domaine.

Deux réponses ne passent par aucune route qui déclare `lang` : le refus d'une
validation de FastAPI et le chemin d'API inconnu. Elles lisent la langue dans
l'adresse (`langue_de_la_requete`), sans la refuser : elles refusent déjà
autre chose.
"""

from __future__ import annotations

from fastapi import Query, Request

from backend.langue import LANGUE_PAR_DEFAUT, LANGUES, Langue


def langue_demandee(
    lang: Langue = Query(
        LANGUE_PAR_DEFAUT,
        description=(
            "Langue des textes rédigés de la réponse : `fr` (défaut) ou `en`. "
            "Sans elle, la réponse est en français."
        ),
    ),
) -> Langue:
    return lang


def langue_de_la_requete(request: Request) -> Langue:
    """`lang` lu dans l'adresse, le français s'il manque ou s'il est inconnu."""
    lang = request.query_params.get("lang")
    return lang if lang in LANGUES else LANGUE_PAR_DEFAUT

