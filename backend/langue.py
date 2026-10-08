"""Les langues du site (chantier 7D, décidé le 2026-10-07).

Le français est la langue par défaut. Toute fonction qui rédige une phrase ou
écrit un nombre prend `langue="fr"` par défaut : un appel sans langue écrit
exactement ce qu'il écrivait avant le chantier, et une réponse de l'API sans
langue demandée reste celle d'avant, octet pour octet.

L'anglais est l'anglais américain, avec la ponctuation de Chicago : point
décimal, virgule des milliers, « 1.06% », « April 4, 2025 », guillemets
doubles, aucune espace avant la ponctuation haute (`anglais-proposition.md`,
hors dépôt, validé par Maxence le 2026-10-08).
"""

from __future__ import annotations

from typing import Literal

Langue = Literal["fr", "en"]

LANGUES: tuple[Langue, ...] = ("fr", "en")

LANGUE_PAR_DEFAUT: Langue = "fr"
