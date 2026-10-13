"""Comparer deux analyses champ par champ, et lire ce qu'une réponse porte.

Deux outils pour les tests du serveur public (chantier 9.6), réunis ici parce
que les relevés faits sur le serveur déployé les réemploient
(`docs/9.6/outils/`, hors dépôt) : la même règle juge une réponse dans la
suite et chez l'hébergeur.

═══ `ecarts` ═══

L'invariant du serveur public : pour une même composition, sa réponse est
celle de l'application, aux champs retirés près. « Égale » veut dire : les
mêmes clés, les mêmes types, les mêmes textes au caractère près, les mêmes
entiers, et des nombres décimaux égaux à 1e-7 en relatif. La tolérance ne
sert pas dans la suite, où les deux réponses sortent du même poste ; elle
sert entre l'export, fait sous Windows, et le serveur, qui tourne sous Linux.

═══ `listes_de_points` ═══

Aucune série d'un titre en ligne : la réponse publique ne porte aucune liste
de points datés. Cette fonction rend le chemin de chaque liste d'une réponse
qui en a l'allure : une liste d'objets dont un champ est une date, ou une
liste de nombres nus. Le test dit lesquelles sont admises, et pourquoi.
"""

from __future__ import annotations

import math
import re

TOLERANCE_RELATIVE = 1e-7
# Deux nombres que tout sépare de zéro de moins que cela sont égaux : un
# écart relatif n'a pas de sens autour de zéro.
TOLERANCE_ABSOLUE = 1e-12

DATE_ISO = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def ecarts(attendu, constate, chemin: str = "") -> list[str]:
    """Ce qui distingue deux documents JSON décodés. Liste vide s'ils sont
    égaux au sens de l'en-tête."""
    ou = chemin or "(racine)"
    if isinstance(attendu, bool) or isinstance(constate, bool) or attendu is None or constate is None:
        return [] if attendu is constate else [f"{ou} : {attendu!r} contre {constate!r}"]
    if isinstance(attendu, dict) and isinstance(constate, dict):
        trouves = []
        for cle in sorted(set(attendu) - set(constate)):
            trouves.append(f"{chemin}.{cle} : absent de la seconde")
        for cle in sorted(set(constate) - set(attendu)):
            trouves.append(f"{chemin}.{cle} : absent de la première")
        for cle in attendu:
            if cle in constate:
                trouves += ecarts(attendu[cle], constate[cle], f"{chemin}.{cle}")
        return trouves
    if isinstance(attendu, list) and isinstance(constate, list):
        if len(attendu) != len(constate):
            return [f"{ou} : {len(attendu)} éléments contre {len(constate)}"]
        trouves = []
        for rang, (a, b) in enumerate(zip(attendu, constate)):
            trouves += ecarts(a, b, f"{chemin}[{rang}]")
        return trouves
    if isinstance(attendu, str) and isinstance(constate, str):
        return [] if attendu == constate else [f"{ou} : texte {attendu!r} contre {constate!r}"]
    if isinstance(attendu, int) and isinstance(constate, int):
        return [] if attendu == constate else [f"{ou} : entier {attendu} contre {constate}"]
    if isinstance(attendu, (int, float)) and isinstance(constate, (int, float)):
        proches = math.isclose(
            attendu, constate, rel_tol=TOLERANCE_RELATIVE, abs_tol=TOLERANCE_ABSOLUE
        )
        return [] if proches else [f"{ou} : nombre {attendu!r} contre {constate!r}"]
    return [f"{ou} : {type(attendu).__name__} contre {type(constate).__name__}"]


def _generique(chemin: str) -> str:
    """Le chemin sans ses rangs : `scenarios[2].coverage` devient
    `scenarios[].coverage`."""
    return re.sub(r"\[[0-9]+\]", "[]", chemin)


def listes_de_points(document, chemin: str = "") -> set[str]:
    """Les chemins des listes d'un document qui ont l'allure d'une série :
    des objets dont un champ est une date ISO, ou des nombres nus."""
    trouvees: set[str] = set()
    if isinstance(document, dict):
        for cle, valeur in document.items():
            trouvees |= listes_de_points(valeur, f"{chemin}.{cle}" if chemin else cle)
    elif isinstance(document, list):
        dates = any(
            isinstance(element, dict)
            and any(isinstance(v, str) and DATE_ISO.match(v) for v in element.values())
            for element in document
        )
        nombres = any(
            isinstance(element, (int, float)) and not isinstance(element, bool)
            for element in document
        )
        if dates or nombres:
            trouvees.add(_generique(f"{chemin}[]"))
        for rang, element in enumerate(document):
            trouvees |= listes_de_points(element, f"{chemin}[{rang}]")
    return trouvees
