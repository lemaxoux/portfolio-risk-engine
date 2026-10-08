"""Les phrases du serveur, un module par langue et par domaine (chantier 7D).

    backend/textes/fr/   le français, langue par défaut, déplacé tel quel
    backend/textes/en/   l'anglais américain : mêmes noms, mêmes signatures

LE MOTEUR ET LES RÈGLES DÉCIDENT, CES MODULES RÉDIGENT. Quelle variante dire,
sur quel signe, pour quelle crise : c'est décidé une seule fois, dans le
moteur, les règles ou le bandeau, qui passent les faits à la fonction de leur
langue. Ce qui ne se décide qu'en rédigeant, la grammaire propre à une langue
(un accord, un article, une contraction), vit ici.

UN SEUL TEXTE PAR LANGUE. Le français n'existe qu'à un endroit : ici. Les noms
qu'on lisait ailleurs, et que des tests lisent encore
(`rules.disclaimer.ACCEPTANCE_TITLE`…), lisent ce module.

`tests/test_textes_symetriques.py` vérifie que les deux langues exposent les
mêmes noms, avec les mêmes signatures, exerce chaque fonction dans les deux,
et passe chaque sortie aux gardes de sa langue.
"""

from __future__ import annotations

from types import ModuleType

from backend.langue import Langue

from . import en, fr

PAR_LANGUE: dict[str, ModuleType] = {"fr": fr, "en": en}


def textes(langue: Langue) -> ModuleType:
    """Les textes d'une langue, par domaine : `textes("en").bandeau.TITRE`."""
    return PAR_LANGUE[langue]


class ErreurRedigee(Exception):
    """Une erreur dont le message est rédigé par un module de texte.

    Elle garde le domaine, le nom de la fonction ou de la constante qui rédige
    son message, et ses arguments : `str()` rend le français, comme avant le
    chantier, et `texte(langue)` la langue demandée. Celui qui l'attrape — une
    route, le moteur qui range la raison d'un volet indisponible — la rédige
    dans la langue de la réponse, sans que celui qui la lève ait à la connaître.
    """

    def __init__(self, domaine: str, redaction: str, *arguments: object) -> None:
        self.domaine = domaine
        self.redaction = redaction
        self.arguments = arguments
        super().__init__(self.texte("fr"))

    def texte(self, langue: Langue = "fr") -> str:
        source = getattr(getattr(textes(langue), self.domaine), self.redaction)
        return source(*self.arguments) if callable(source) else source


class ValeurRefusee(ErreurRedigee, ValueError):
    """Un refus du moteur, une `ValueError` comme avant le chantier, dont le
    message est rédigé dans `moteur` : ceux qu'une réponse peut publier comme
    raison d'un volet simulé indisponible."""

    def __init__(self, redaction: str, *arguments: object) -> None:
        super().__init__("moteur", redaction, *arguments)


def texte_d_erreur(erreur: Exception, langue: Langue = "fr") -> str:
    """Le message d'une erreur dans la langue demandée : celui d'une erreur
    rédigée, le message tel quel sinon (un garde-fou interne, en français)."""
    return erreur.texte(langue) if isinstance(erreur, ErreurRedigee) else str(erreur)
