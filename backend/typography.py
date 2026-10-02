"""Convention typographique du texte rédigé par le backend.

Le backend écrit des phrases — observations du moteur de règles, `summary()` des
scénarios, `caveat` du CVaR, provenance des seuils, bandeau d'acceptation — et
ces phrases contiennent des nombres collés à un symbole ou à un mot. En
typographie française, ces liens ne se coupent pas.

    U+202F  ESPACE FINE INSÉCABLE   avant « % », et comme séparateur de milliers
    U+00A0  ESPACE INSÉCABLE        entre un nombre et le mot qu'il compte
    U+2212  SIGNE MOINS             jamais le trait d'union U+002D
    ,       VIRGULE DÉCIMALE        jamais le point

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

═══ TOUT NOMBRE ÉCRIT DANS UN TEXTE PASSE PAR ICI ═══

Pas seulement les espaces : la virgule décimale et le signe moins aussi. Un
`f"{nu:.2f}"` écrit dans une phrase publiée produit « ν = 4.07 » à côté du
« 4,07 » que le frontend affiche pour le même nombre — deux conventions dans
une même page. `number`, `percent`, `signed_points` et `compact` sont le
pendant exact de `frontend/src/lib/format.ts`, y compris l'ARRONDI : la moitié
s'arrondit en s'éloignant de zéro, sur la valeur binaire réelle du flottant,
comme `Number.prototype.toFixed`. Le `format` de Python arrondit au pair
(`f"{2.5:.0f}"` rend « 2 », `(2.5).toFixed(0)` rend « 3 ») : laissé tel quel,
il ferait écrire 12 % d'un côté et 13 % de l'autre pour une part de 12,5 %.

Seul le texte en PROSE est concerné. Un message d'erreur qui montre une
commande ou un littéral Python à recopier (« MX_RISK_FREE_RATE=0.035 ») garde
le point : c'est du code, et une virgule le rendrait faux.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal, localcontext

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


MINUS = "\u2212"


def number(
    valeur: float, decimales: int, *, signed: bool = False, trim: bool = False
) -> str:
    """Un nombre en écriture française : « 4,07 », « −0,36 », « 83 185,85 ».

    `decimales` n'a pas de défaut, comme dans `format.ts` : c'est l'appelant
    qui sait combien de décimales porte le nombre qu'il écrit.

    `signed` écrit le « + » d'une valeur positive, pour un écart. `trim` retire
    une partie décimale faite de zéros seulement : « 80 % » et non « 80,0 % »,
    mais « 25,6 % » reste intact.

    Une valeur qui s'arrondit à zéro ne porte AUCUN signe : « −0,0 » se lirait
    comme une perte alors que le chiffre dit qu'il n'y en a pas — même règle
    que `format.ts`.
    """
    if not math.isfinite(valeur):
        raise ValueError(f"Valeur non finie à écrire : {valeur!r}")
    # `Decimal(float)` est la valeur binaire EXACTE : les égalités à la moitié
    # sont de vraies égalités, et ROUND_HALF_UP les tranche comme `toFixed`.
    exacte = Decimal(abs(valeur))
    # La précision par défaut de `decimal` est de 28 chiffres, et `quantize`
    # lève `InvalidOperation` quand le résultat en demande davantage : un ν de
    # Student à 3,6 × 10²⁷ écrit à deux décimales faisait tomber l'analyse en
    # 500. La précision suit donc le nombre — chiffres de la partie entière,
    # plus les décimales demandées. Tout flottant fini s'écrit.
    chiffres = max(exacte.adjusted() + 1, 1) + decimales + 1
    with localcontext() as contexte:
        contexte.prec = max(contexte.prec, chiffres)
        arrondi = exacte.quantize(
            Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP
        )
    entier, _, fraction = f"{arrondi:f}".partition(".")
    if trim and not fraction.strip("0"):
        fraction = ""
    corps = thousands(int(entier)) + (f",{fraction}" if fraction else "")
    if arrondi == 0:
        return corps
    if valeur < 0:
        return f"{MINUS}{corps}"
    return f"+{corps}" if signed else corps


def percent(
    fraction: float, decimales: int, *, signed: bool = False, trim: bool = False
) -> str:
    """Une fraction en pourcentage : `0.439` → « 43,9 % », espace FINE avant « % »."""
    return (
        f"{number(fraction * 100.0, decimales, signed=signed, trim=trim)}"
        f"{NARROW_NBSP}%"
    )


def signed_points(ecart: float, decimales: int = 1) -> str:
    """Un écart entre deux parts, signé, en points : `0.098` → « +9,8 pts »."""
    return f"{number(ecart * 100.0, decimales, signed=True)}{NBSP}pts"


def exact(valeur: float) -> str:
    """Un nombre SAISI, cité dans un refus : « −3 », « 2,5 », « 0,1 ».

    La plus courte écriture décimale qui relit le même flottant — celle de
    `repr` —, passée par `number` : virgule, signe moins, milliers groupés.
    Ni décimale inventée (« −3,0 »), ni décimale perdue (« 0,1 » ne devient pas
    « 0 »), ni exposant (`repr(1e-07)` s'écrit « 0,0000001 »). C'est l'écriture
    que l'utilisateur reconnaît comme la sienne.
    """
    if not math.isfinite(valeur):
        raise ValueError(f"Valeur non finie à écrire : {valeur!r}")
    exposant = Decimal(repr(float(valeur))).as_tuple().exponent
    return number(valeur, max(-exposant, 0), trim=True)


def compact(valeur: float) -> str:
    """L'écriture la plus courte d'un paramètre : `0.94` → « 0,94 », `60.0` → « 60 ».

    Pour une constante que l'on CITE (λ de l'EWMA, valeur d'un seuil), dont le
    nombre de décimales n'est pas choisi mais celui de la constante elle-même.
    """
    if not math.isfinite(valeur):
        raise ValueError(f"Valeur non finie à écrire : {valeur!r}")
    return f"{valeur:g}".replace(".", ",").replace("-", MINUS)
