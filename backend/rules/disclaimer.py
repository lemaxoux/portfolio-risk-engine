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
été déplacé tel quel : à ce déplacement, son empreinte n'a pas changé, et
personne n'a eu à réaccepter. Le texte anglais a la sienne. Le renommage du
produit (chantier 9.1b) a changé le nom dans les deux textes, donc les deux
empreintes : l'écran d'acceptation revient une fois par langue. Ni l'un ni
l'autre texte n'a été relu par un juriste.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.langue import Langue
from backend.risk_engine.config import DEFAULT_WINDOW, TRADING_DAYS_PER_YEAR
from backend.textes import textes

ACCEPTANCE_TITLE = textes("fr").bandeau.TITRE

ACCEPTANCE_CONFIRMATION = textes("fr").bandeau.CONFIRMATION


def acceptance_title(langue: Langue = "fr") -> str:
    """Le titre du texte d'acceptation, dans la langue demandée."""
    return textes(langue).bandeau.TITRE


def acceptance_confirmation(langue: Langue = "fr") -> str:
    """La phrase de confirmation qui clôt le texte d'acceptation, dans la
    langue demandée."""
    return textes(langue).bandeau.CONFIRMATION


@dataclass(frozen=True)
class DisclaimerSection:
    """Une section du texte d'acceptation : son titre et son corps, déjà
    rédigés dans une langue."""

    title: str
    body: str


def _duree(seances: int, langue: Langue = "fr") -> str:
    """« environ 2 ans », « environ 6 mois », « about 2 years » : en années
    quand la fenêtre en tombe à moins d'un vingtième près, en mois sinon. La
    décision est ici ; l'écriture, nombre et unité liés par une espace
    insécable, est dans le module de la langue.

    Ce n'est pas tout à fait la règle d'`engine.period_label`, qui attend 252
    séances pour parler d'années et compte en jours sous 21 séances : de 240
    à 251 séances, celle-ci écrit « environ 1 an » là où `period_label` dit
    « ces 11 derniers mois » ou « ces 12 derniers mois », et sous 21 séances
    elle compte en mois, « environ 0 mois » compris."""
    bandeau = textes(langue).bandeau
    annees = seances / TRADING_DAYS_PER_YEAR
    if abs(annees - round(annees)) < 0.05 and round(annees) >= 1:
        return bandeau.duree_en_annees(round(annees))
    return bandeau.duree_en_mois(round(seances / 21))


def acceptance_sections(
    window: int = DEFAULT_WINDOW, *, langue: Langue = "fr", en_ligne: bool = False
) -> tuple[DisclaimerSection, ...]:
    """Les sections du texte d'acceptation, dans l'ordre, dans la langue
    demandée.

    `window` est la fenêtre d'estimation, en séances, que le texte cite avec sa
    durée en années ou en mois (`_duree`) : elle vient de la configuration du
    moteur, jamais d'un nombre écrit dans le texte.

    `en_ligne` (chantier 9.6) : le texte du site, qui envoie le portefeuille
    saisi à un serveur public. Il gagne une section, placée avant la dernière.
    Faux par défaut : le texte de l'application est celui d'avant, octet pour
    octet, et son empreinte aussi.
    """
    bandeau = textes(langue).bandeau
    redigees = list(bandeau.sections(window, _duree(window, langue)))
    if en_ligne:
        redigees = [*redigees[:-1], bandeau.SECTION_EN_LIGNE, redigees[-1]]
    return tuple(DisclaimerSection(title=titre, body=corps) for titre, corps in redigees)


def acceptance_text(
    window: int = DEFAULT_WINDOW, *, langue: Langue = "fr", en_ligne: bool = False
) -> str:
    """Texte complet du bandeau, prêt à afficher."""
    sections = "\n\n".join(
        f"{section.title}\n{section.body}"
        for section in acceptance_sections(window, langue=langue, en_ligne=en_ligne)
    )
    return f"{acceptance_title(langue)}\n\n{sections}\n\n{acceptance_confirmation(langue)}"


ACCEPTANCE_TEXT = acceptance_text()
