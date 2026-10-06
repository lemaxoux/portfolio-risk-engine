"""Catalogue des scénarios de stress historiques.

Ce module ne contient QUE des données. Ajouter un épisode se fait en ajoutant
une entrée à `SCENARIOS` : aucune logique de calcul ne dépend de leur nombre ni
de leur contenu, et rien n'est à modifier ailleurs.

Les fenêtres sont bornées PIC À CREUX et non par année civile. Un scénario
« 2008 » calé sur le 1er janvier commencerait trois mois après le sommet du
marché et manquerait le premier quart de la baisse ; il mesurerait un épisode
plus court et moins profond que celui qu'il prétend décrire. Les bornes retenues
sont les extrema de clôture du S&P 500, et un test les vérifie contre les
données en base plutôt que de leur faire confiance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.typography import long_date


@dataclass(frozen=True)
class Scenario:
    """Un épisode de marché à rejouer sur le portefeuille actuel.

    `benchmark` sert à vérifier les bornes : c'est sur son cours que le pic et
    le creux ont été relevés, et c'est donc lui qui permet de contrôler que la
    fenêtre décrit bien l'épisode annoncé. `description` dit, en une phrase, ce
    qui borne la fenêtre.

    `article` est l'article défini du nom, élision comprise (« la », « le »,
    « l' ») : les phrases de lecture disent « pendant la Crise financière
    2008 », et le genre d'un nom ne se devine pas. Sans article déclaré, elles
    disent « l'épisode Choc bref », correct quel que soit le nom.
    """

    key: str
    name: str
    start: date
    end: date
    benchmark: str
    description: str
    article: str = "l'épisode"

    @property
    def calendar_days(self) -> int:
        return (self.end - self.start).days

    @property
    def with_article(self) -> str:
        """« la Crise financière 2008 », « l'épisode Choc bref »."""
        if self.article.endswith("'"):
            return f"{self.article}{self.name}"
        return f"{self.article} {self.name}"

    def __str__(self) -> str:
        return f"{self.name} ({self.start} → {self.end})"


def _du_sommet_au_point_bas(sommet: date, point_bas: date) -> str:
    """La phrase qui borne une crise. Ses dates passent par `long_date` : le
    jour, le mois et l'année ne se séparent pas. Écrites à la main, « (3 »
    finissait une ligne que « janvier 2022) » commençait."""
    return (
        f"Du sommet de clôture du S&P 500 ({long_date(sommet)}) à son point bas "
        f"de clôture ({long_date(point_bas)})."
    )


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        key="gfc_2008",
        name="Crise financière 2008",
        article="la",
        start=date(2007, 10, 9),
        end=date(2009, 3, 9),
        benchmark="SPY",
        description=_du_sommet_au_point_bas(date(2007, 10, 9), date(2009, 3, 9)),
    ),
    Scenario(
        key="covid_2020",
        name="Krach COVID",
        article="le",
        start=date(2020, 2, 19),
        end=date(2020, 3, 23),
        benchmark="SPY",
        description=_du_sommet_au_point_bas(date(2020, 2, 19), date(2020, 3, 23)),
    ),
    Scenario(
        key="tightening_2022",
        name="Resserrement monétaire 2022",
        article="le",
        start=date(2022, 1, 3),
        end=date(2022, 10, 12),
        benchmark="SPY",
        description=_du_sommet_au_point_bas(date(2022, 1, 3), date(2022, 10, 12)),
    ),
)

SCENARIOS_BY_KEY: dict[str, Scenario] = {s.key: s for s in SCENARIOS}


def get_scenario(key: str) -> Scenario:
    """Scénario par sa clé. Lève `KeyError` avec la liste des clés connues."""
    try:
        return SCENARIOS_BY_KEY[key]
    except KeyError:
        raise KeyError(
            f"Scénario inconnu : {key!r}. Disponibles : "
            f"{sorted(SCENARIOS_BY_KEY)}"
        ) from None
