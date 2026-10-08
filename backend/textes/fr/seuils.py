"""Les seuils du moteur de règles, en français.

Le nom et la justification d'un seuil ne sont écrits qu'à un seul endroit :
dans `rules/thresholds.py`, avec sa valeur et sa provenance, où des tests les
lisent. Ce module les lit de là, sur le seuil qu'il reçoit ; il n'en garde
aucune copie (chantier 7D). L'étiquette « Seuil » ou « Référence » est de même
la valeur de `ThresholdRole`.

Il rédige le reste : la provenance, accordée au genre du nom du seuil, et la
ligne entière, « corrélation forte = 0,70, choisi à la main (non dérivé des
données). Convention usuelle… ».
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.rules.thresholds import Threshold


def nom(seuil: Threshold) -> str:
    """« corrélation forte », « part de JPM dans la valeur » : `Threshold.name`."""
    return seuil.name


def justification(seuil: Threshold) -> str:
    """En minuscule et sans point final, telle que publiée à part
    (`rationale`) : `Threshold.rationale`."""
    return seuil.rationale


def etiquette(role: Enum) -> str:
    """« Seuil » ou « Référence » : la valeur de `ThresholdRole`."""
    return role.value


CHOISI = "choisi à la main (non dérivé des données)"


def origine(choisi: bool, reference: bool, feminin: bool) -> str:
    """D'où vient la valeur, dit au lecteur après la virgule de la ligne.

    - Choisi à la main : la formule validée le 2026-10-05, qui ne s'accorde
      pas.
    - Une RÉFÉRENCE, dérivée ou relative au portefeuille, est calculée sur CE
      portefeuille, accordé avec le nom (décision du 2026-10-06).
    - Un seuil DÉMONTRÉ, dérivé mais posé d'avance, n'est calculé sur aucun
      portefeuille : « Calculé sur ce portefeuille » dirait faux au lecteur
      d'un refus sous trois séances.
    """
    if choisi:
        return CHOISI
    accord = "e" if feminin else ""
    if reference:
        return f"calculé{accord} sur ce portefeuille"
    meme = "la même" if feminin else "le même"
    return f"démontré{accord} ({meme} pour tout portefeuille)"


def ligne(intitule: str, valeur: str, provenance: str, raison: str) -> str:
    """La ligne de seuil : la valeur, puis sa provenance après une virgule,
    puis la justification en phrase, capitale initiale et point final. Casse
    phrase, sans mot en capitales (DESIGN.md §6.3, décision du 2026-10-05)."""
    return f"{intitule} = {valeur}, {provenance}. {_phrase(raison)}"


def _phrase(texte: str) -> str:
    """La justification d'un seuil, déclarée en minuscule et sans point final,
    écrite en phrase : capitale initiale, point final."""
    return texte[0].upper() + texte[1:] + "."
