"""Convention typographique du texte rédigé par le backend.

Le backend écrit des phrases — observations du moteur de règles, `summary()` des
scénarios, `caveat` du CVaR, provenance des seuils, bandeau d'acceptation — et
ces phrases contiennent des nombres collés à un symbole ou à un mot. En
typographie française, ces liens ne se coupent pas.

    U+202F  ESPACE FINE INSÉCABLE   avant « % », et comme séparateur de milliers
    U+00A0  ESPACE INSÉCABLE        entre un nombre et le mot qu'il compte

INSÉCABLE est le mot important, pas la largeur. Avec une espace ordinaire,
« 25,6 % » se coupe en fin de ligne et le « % » part seul à la ligne suivante ;
« 504 séances » devient « 504 » puis « séances ». Le texte reste lisible, mais
il a l'air composé à la main — exactement ce qu'un outil dont l'argument est la
rigueur ne peut pas se permettre d'avoir l'air d'être.

POURQUOI ICI — ces deux caractères servent au moteur (`engine`), aux règles, aux
seuils et au bandeau. Les définir dans chacun les ferait diverger, et il n'y a
pas de couche à qui la typographie appartienne plus qu'aux autres : elle est au
projet. D'où un module à part, que les quatre importent.

LE FRONTEND FAIT LE MÊME CHOIX, de son côté, pour les nombres qu'il formate
lui-même (`frontend/DESIGN.md` §6). Ce module ne concerne que le texte déjà
rédigé côté serveur, qu'une interface affiche tel quel.
"""

from __future__ import annotations

NARROW_NBSP = " "
NBSP = " "


def counted(
    nombre: float | int,
    singulier: str,
    pluriel: str | None = None,
    affiche: str | None = None,
) -> str:
    """Un nombre et le mot qu'il compte, liés par une espace insécable.

    Pluriel au-delà de deux exclu, singulier en deçà : « 0 séance »,
    « 1 séance », « 2 séances ». C'est la règle française, où zéro et un
    prennent le singulier.

    `affiche` remplace l'écriture du nombre sans toucher à l'accord : c'est
    `nombre` qui décide du pluriel, pas la chaîne rendue. Un « 100 000 » groupé
    ne doit pas avoir à être réinterprété pour savoir s'il prend un « s ».
    """
    mot = singulier if abs(nombre) < 2 else (pluriel or f"{singulier}s")
    return f"{nombre if affiche is None else affiche}{NBSP}{mot}"


def sessions(nombre: int) -> str:
    """« 504 séances », insécable."""
    return counted(nombre, "séance")


def lines(nombre: int) -> str:
    """« 6 lignes », insécable."""
    return counted(nombre, "ligne")


def thousands(nombre: int) -> str:
    """Entier groupé par milliers à l'espace fine insécable : « 100 000 »."""
    return f"{nombre:,}".replace(",", NARROW_NBSP)


def grouped(nombre: int, singulier: str, pluriel: str | None = None) -> str:
    """Un grand nombre groupé, et le mot qu'il compte : « 100 000 tirages »."""
    return counted(nombre, singulier, pluriel, affiche=thousands(nombre))
