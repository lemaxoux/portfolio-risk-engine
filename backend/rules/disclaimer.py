"""Texte du bandeau d'acceptation.

Seulement le texte : l'écran qui le portera relève de la Phase 7. Il est tenu ici,
à côté des règles, parce qu'il en est la borne — les observations décrivent, et
ce texte dit ce qu'elles ne sont pas.

La taille de la fenêtre d'estimation n'est pas écrite en dur : elle vient de la
configuration du moteur, pour que le texte ne puisse pas dire « 504 séances » le
jour où le calcul en utiliserait un autre nombre.

DEUX LANGUES (chantier 7D). Ce module décide — la durée de la fenêtre se dit en
années ou en mois, et combien — et lit le texte de la langue demandée dans
`backend/textes/<langue>/bandeau.py`, « fr » par défaut. Le texte français y a
été déplacé tel quel : son empreinte n'a pas changé, personne n'a à réaccepter.
Le texte anglais a la sienne. Ni l'un ni l'autre n'a été relu par un juriste.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.langue import Langue
from backend.risk_engine.config import DEFAULT_WINDOW, TRADING_DAYS_PER_YEAR
from backend.textes import textes

ACCEPTANCE_TITLE = textes("fr").bandeau.TITRE

ACCEPTANCE_CONFIRMATION = textes("fr").bandeau.CONFIRMATION


def acceptance_title(langue: Langue = "fr") -> str:
    return textes(langue).bandeau.TITRE


def acceptance_confirmation(langue: Langue = "fr") -> str:
    return textes(langue).bandeau.CONFIRMATION


@dataclass(frozen=True)
class DisclaimerSection:
    title: str
    body: str


def _duree(seances: int, langue: Langue = "fr") -> str:
    """« environ 2 ans », « environ 6 mois », « about 2 years » : en années
    quand la fenêtre en tombe à moins d'un vingtième près, en mois sinon. La
    décision est ici ; l'écriture, nombre et unité liés par une espace
    insécable, est dans le module de la langue."""
    bandeau = textes(langue).bandeau
    annees = seances / TRADING_DAYS_PER_YEAR
    if abs(annees - round(annees)) < 0.05 and round(annees) >= 1:
        return bandeau.duree_en_annees(round(annees))
    return bandeau.duree_en_mois(round(seances / 21))


def acceptance_sections(
    window: int = DEFAULT_WINDOW, *, langue: Langue = "fr"
) -> tuple[DisclaimerSection, ...]:
    return tuple(
        DisclaimerSection(title=titre, body=corps)
        for titre, corps in textes(langue).bandeau.sections(window, _duree(window, langue))
    )


def acceptance_text(window: int = DEFAULT_WINDOW, *, langue: Langue = "fr") -> str:
    """Texte complet du bandeau, prêt à afficher."""
    sections = "\n\n".join(
        f"{section.title}\n{section.body}"
        for section in acceptance_sections(window, langue=langue)
    )
    return f"{acceptance_title(langue)}\n\n{sections}\n\n{acceptance_confirmation(langue)}"


ACCEPTANCE_TEXT = acceptance_text()
