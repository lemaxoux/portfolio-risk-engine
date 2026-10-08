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
