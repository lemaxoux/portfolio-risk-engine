"""Traduction des erreurs en réponses HTTP utilisables.

LE PRINCIPE — le moteur porte déjà des messages actionnables. `PortfolioError`
dit « Aucun prix en base pour ['SPY']. Lancer : python -m backend.ingestion add
SPY » : c'est exactement ce que l'utilisateur a besoin de lire. Les écraser en
« 500 Internal Server Error » remplacerait une instruction par un aveu
d'impuissance. Ce module relaie donc le texte du moteur MOT POUR MOT et se
contente de choisir le code. Seules les espaces avant « : » et dans les
guillemets deviennent insécables (`typography.prose`), comme dans tout texte
publié.

LA CORRESPONDANCE, et pourquoi :

* **404** — le portefeuille n'existe pas. Vérifié explicitement par une lecture
  de `portfolios` AVANT d'appeler le moteur, jamais en cherchant le mot
  « introuvable » dans un message français. Un code HTTP qui dépendrait de la
  langue d'un message serait cassé par une reformulation.
* **409** — le portefeuille existe mais n'est pas analysable en l'état : aucune
  position, aucun prix pour une ligne, valeur totale nulle, benchmark absent de
  la base, moins de trois séances communes à tous les titres. Ce n'est pas la requête qui est malformée, c'est l'état de la base ;
  et la suite est une action de l'utilisateur, décrite dans le message.
* **422** — la requête elle-même est refusée : paramètre hors domaine, CSV
  invalide, ticker inconnu dans les positions soumises. `problems` détaille
  alors ligne à ligne.

Une seule forme de corps d'erreur pour toute l'API, y compris pour les refus de
validation de FastAPI, pour qu'un client n'ait pas deux formats à gérer :

    {"detail": "<une phrase>", "problems": [{"line": 4, "field": "ticker",
                                             "value": "XYZ", "problem": "..."}]}
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend import typography
from backend.langue import Langue
from backend.textes import textes

from .langue import langue_de_la_requete


@dataclass(frozen=True)
class Problem:
    """Un refus précis, localisé. Tous les champs sauf `problem` sont optionnels.

    `line` est le numéro de ligne DU FICHIER tel que l'utilisateur le voit dans
    son tableur — en-tête compris —, pas un indice de tableau. Une erreur
    signalée « ligne 3 » pour la quatrième ligne du fichier fait perdre plus de
    temps qu'elle n'en fait gagner.
    """

    problem: str
    line: int | None = None
    field: str | None = None
    value: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "line": self.line,
            "field": self.field,
            "value": self.value,
            "problem": typography.prose(self.problem),
        }


class ApiError(Exception):
    """Erreur destinée au client, avec son code et son détail."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        problems: tuple[Problem, ...] = (),
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.problems = problems


def not_found(portfolio_id: int, langue: Langue = "fr") -> ApiError:
    """Le message du moteur, le même que celui d'une `PortfolioError` : il
    n'est écrit qu'une fois (`textes/{fr,en}/moteur.py`)."""
    return ApiError(
        status.HTTP_404_NOT_FOUND,
        textes(langue).moteur.portefeuille_introuvable(portfolio_id),
    )


def unprocessable(detail: str, problems: tuple[Problem, ...] = ()) -> ApiError:
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, detail, problems)


def _body(detail: str, problems: tuple[Problem, ...]) -> dict[str, object]:
    return {
        "detail": typography.prose(detail),
        "problems": [p.as_dict() for p in problems],
    }


def register_handlers(app: FastAPI) -> None:
    """Branche les gestionnaires sur l'application."""

    @app.exception_handler(ApiError)
    def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.detail, exc.problems)
        )

    @app.exception_handler(RequestValidationError)
    def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Les refus de FastAPI prennent la même forme que les nôtres. `loc` est
        # un chemin (« body », « positions », 0, « quantity ») : on n'en garde
        # que le dernier segment nommé, qui est le champ fautif. Le message de
        # pydantic est publié tel quel, dans les deux langues ; seuls ses
        # replis sont rédigés ici.
        t = textes(langue_de_la_requete(request)).api
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


def _champ(loc: object) -> str | None:
    if not isinstance(loc, (list, tuple)):
        return None
    noms = [str(element) for element in loc if isinstance(element, str)]
    return noms[-1] if noms else None


def _valeur(brut: object) -> str | None:
    """Représentation textuelle courte de l'entrée refusée, ou None."""
    if brut is None:
        return None
    texte = str(brut)
    return texte if len(texte) <= 120 else f"{texte[:117]}..."
