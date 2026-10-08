"""Convention typographique du texte rédigé par le backend.

Le backend écrit des phrases — observations du moteur de règles, `summary()` des
scénarios, `caveat` du CVaR, provenance des seuils, bandeau d'acceptation — et
ces phrases contiennent des nombres collés à un symbole ou à un mot. En
typographie française, ces liens ne se coupent pas.

    U+202F  ESPACE FINE INSÉCABLE   avant « % », et comme séparateur de milliers
    U+00A0  ESPACE INSÉCABLE        entre un nombre et le mot qu'il compte
    U+2212  SIGNE MOINS             jamais le trait d'union U+002D
    U+00A0  ESPACE INSÉCABLE        avant « : », « ; », « ? », « ! » ; après « « »
                                    et avant « » »
    U+2060  CARACTÈRE DE LIAISON    après le tiret court d'une paire (« JNJ–KO »)
                                    et chaque trait d'union d'une date ISO citée
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

═══ L'ANGLAIS (chantier 7D) ═══

Chaque fonction prend `langue`, « fr » par défaut : un appel sans langue écrit
exactement ce qu'il écrivait. En anglais (américain, ponctuation de Chicago) :

    .       POINT DÉCIMAL           « 1.06 »
    ,       SÉPARATEUR DE MILLIERS  à partir de quatre chiffres : « 1,000 », « 504 »
            AUCUNE ESPACE           avant « % » : « 1.06% »
    U+2212  SIGNE MOINS             comme en français
    U+00A0  ESPACE INSÉCABLE        entre un nombre et le mot qu'il compte, et
                                    dans une date : « April 4, 2025 »

Le singulier y est réservé au nombre qui s'écrit exactement « 1 » : « 1 point »,
« 1.9 points », « 0 sessions ». `prose` ne change pas : sur un anglais correct,
il ne pose que les caractères de liaison des paires et des dates ISO.
`frontend/src/lib/format.ts` écrit les mêmes caractères, et
`frontend/src/lib/typographie-partagee.json` liste les cas que les deux côtés
doivent écrire à l'identique.
"""

from __future__ import annotations

import math
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from backend.langue import Langue

NARROW_NBSP = " "
NBSP = " "


# Une espace ORDINAIRE avant une ponctuation haute — « : », « ; », « ? », « ! » —
# suivie d'un blanc ou de la fin du texte : « reçu : 7 », « La démarrer : »,
# « capital … ; risque … ». Pas « 10:30 », ni « http:// », ni « != ».
_PONCTUATION_HAUTE = re.compile(r" ([:;?!])(?=\s|$)")


# Un tiret court pris entre deux caractères qui ne sont pas des blancs : une
# paire de titres, « JNJ–KO ». Une coupure de ligne est permise juste APRÈS ce
# tiret (UAX #14, classe BA), et la paire se retrouvait en deux morceaux :
# « JNJ– » en fin de ligne, « KO » au début de la suivante. Le caractère de
# liaison (U+2060), invisible et sans largeur, interdit cette coupure.
WORD_JOINER = chr(0x2060)
_TIRET_DE_PAIRE = re.compile(r"(?<=\S)\u2013(?=[^\s\u2060])")

# Une date ISO cit\u00e9e dans une phrase, \u00ab valorisation au 2026-09-25 \u00bb : une
# coupure est permise apr\u00e8s chacun de ses traits d'union, et \u00ab 2026-09- \u00bb
# finissait une ligne que \u00ab 25 \u00bb commen\u00e7ait. Le m\u00eame caract\u00e8re de liaison,
# apr\u00e8s chaque trait. Une date qui est \u00e0 elle seule un champ (`as_of`,
# `start`, `end`) n'est pas de la prose et ne passe pas ici : elle reste nue.
# Appliqu\u00e9e deux fois, la r\u00e8gle n'ajoute rien : un trait d\u00e9j\u00e0 suivi du
# caract\u00e8re de liaison n'est plus suivi d'un chiffre.
_DATE_ISO = re.compile(r"(?<![0-9])([0-9]{4})-([0-9]{2})-([0-9]{2})(?![0-9])")


def prose(texte: str) -> str:
    """Les espaces de la ponctuation française, rendues insécables, et les
    paires de titres, rendues insécables elles aussi.

    Avant « : », « ; », « ? » et « ! », et à l'intérieur des guillemets « » :
    avec une espace ordinaire, le signe ou le guillemet fermant part seul en
    début de ligne, et « Colonnes obligatoires » finit une ligne que
    « : ticker » commence. Seule l'espace change.

    Après le tiret court d'une paire (« JNJ–KO ») et après chaque trait
    d'union d'une date ISO (« 2026-09-25 »), un caractère de liaison
    invisible : ni la paire ni la date ne se coupent plus en fin de ligne.
    Aucun mot, aucun caractère VISIBLE n'est ajouté ni retiré.

    Appliquée UNE fois, à la publication, à chaque champ de texte rédigé
    (`api.schemas.Texte`) et aux corps d'erreur : les phrases du moteur et des
    règles s'écrivent avec des espaces lisibles dans le code, et la convention
    tient pour toutes, y compris celles qui restent à écrire.
    `tests/test_textes_publies.py` la vérifie sur les réponses.
    """
    espace = (
        _PONCTUATION_HAUTE.sub(lambda signe: NBSP + signe.group(1), texte)
        .replace("« ", f"«{NBSP}")
        .replace(" »", f"{NBSP}»")
    )
    paires = _TIRET_DE_PAIRE.sub(lambda tiret: tiret.group(0) + WORD_JOINER, espace)
    return _DATE_ISO.sub(
        lambda d: f"{d.group(1)}-{WORD_JOINER}{d.group(2)}-{WORD_JOINER}{d.group(3)}", paires
    )


def counted(
    nombre: float | int,
    singulier: str,
    pluriel: str | None = None,
    affiche: str | None = None,
    *,
    langue: Langue = "fr",
) -> str:
    """Un nombre et le mot qu'il compte, liés par une espace insécable.

    Pluriel au-delà de deux exclu, singulier en deçà : « 0 séance »,
    « 1 séance », « 2 séances ». C'est la règle française, où zéro et un
    prennent le singulier.

    Sans `affiche`, le nombre s'écrit comme `compte` côté client : entier,
    groupé par milliers à partir de quatre chiffres (« 2 520 séances »,
    « 2,520 sessions »). Il s'écrivait nu (« 2520 séances »), à côté d'un
    « 2 520 » du client pour le même nombre (chantier 7D, session 2).

    `affiche` remplace l'écriture du nombre sans toucher à l'accord : c'est
    `nombre` qui décide du pluriel, pas la chaîne rendue. Un « 100 000 » groupé
    ne doit pas avoir à être réinterprété pour savoir s'il prend un « s ».

    En anglais, le singulier est réservé au nombre qui s'écrit exactement
    « 1 » : « 1 session », mais « 0 sessions » et « 1.0 holdings ». C'est
    alors l'écriture qui décide, signe à part.
    """
    ecrit = number(nombre, 0, langue=langue) if affiche is None else affiche
    if langue == "en":
        au_singulier = str(ecrit).lstrip("+-" + MINUS) == "1"
    else:
        au_singulier = abs(nombre) < 2
    mot = singulier if au_singulier else (pluriel or f"{singulier}s")
    return f"{ecrit}{NBSP}{mot}"


def sessions(nombre: int, *, langue: Langue = "fr") -> str:
    """« 504 séances », « 504 sessions », insécable."""
    return counted(nombre, "session" if langue == "en" else "séance", langue=langue)


def lines(nombre: int, *, langue: Langue = "fr") -> str:
    """« 6 lignes », « 6 holdings », insécable."""
    return counted(nombre, "holding" if langue == "en" else "ligne", langue=langue)


def thousands(nombre: int, *, langue: Langue = "fr") -> str:
    """Entier groupé par milliers : « 100 000 » à l'espace fine insécable,
    « 100,000 » à la virgule en anglais."""
    return f"{nombre:,}".replace(",", "," if langue == "en" else NARROW_NBSP)


def grouped(
    nombre: int, singulier: str, pluriel: str | None = None, *, langue: Langue = "fr"
) -> str:
    """Un grand nombre groupé, et le mot qu'il compte : « 100 000 tirages »."""
    return counted(
        nombre, singulier, pluriel, affiche=thousands(nombre, langue=langue), langue=langue
    )


_EN_LETTRES = (
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
)

_IN_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
)


_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def long_date(jour: date, *, langue: Langue = "fr") -> str:
    """Une date en toutes lettres, pour la prose : « 4 janvier 2010 »,
    « 1er janvier 2005 » ; en anglais, « January 4, 2010 ».

    Insécable entre le jour, le mois et l'année, comme `dateEnToutesLettres`
    côté client : les deux moitiés du produit écrivent une date de la même
    façon. En anglais, l'espace insécable suit le mois et la virgule :
    « April 4, » ne finit pas une ligne que « 2025 » commencerait. Le premier
    du mois s'écrit « 1er » en français (chantier 7D), « 1 » en anglais. Les
    dates de provenance, elles, restent en ISO (DESIGN.md §6.3).
    """
    if langue == "en":
        return f"{_MONTHS[jour.month - 1]}{NBSP}{jour.day},{NBSP}{jour.year}"
    quantieme = "1er" if jour.day == 1 else jour.day
    return f"{quantieme}{NBSP}{_MOIS[jour.month - 1]}{NBSP}{jour.year}"


def cardinal(nombre: int, *, langue: Langue = "fr") -> str:
    """Un entier dans une phrase de lecture : en lettres jusqu'à dix, en
    chiffres au-delà — « ces deux dernières années », « ces 14 derniers mois »,
    « the past two years ».

    Seulement là où une phrase se lit comme de la prose. Un chiffre de mesure,
    un nombre de séances dans une provenance, restent en chiffres.
    """
    if 0 <= nombre <= 10:
        return (_IN_WORDS if langue == "en" else _EN_LETTRES)[nombre]
    return thousands(nombre, langue=langue)


MINUS = "\u2212"


def number(
    valeur: float,
    decimales: int,
    *,
    signed: bool = False,
    trim: bool = False,
    langue: Langue = "fr",
) -> str:
    """Un nombre en écriture française : « 4,07 », « −0,36 », « 83 185,85 » ;
    en anglais : « 4.07 », « −0.36 », « 83,185.85 ».

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
    decimale = "." if langue == "en" else ","
    corps = thousands(int(entier), langue=langue) + (f"{decimale}{fraction}" if fraction else "")
    if arrondi == 0:
        return corps
    if valeur < 0:
        return f"{MINUS}{corps}"
    return f"+{corps}" if signed else corps


def percent(
    fraction: float,
    decimales: int,
    *,
    signed: bool = False,
    trim: bool = False,
    langue: Langue = "fr",
) -> str:
    """Une fraction en pourcentage : `0.439` → « 43,9 % », espace FINE avant
    « % » ; en anglais, « 43.9% », sans espace."""
    ecrit = number(fraction * 100.0, decimales, signed=signed, trim=trim, langue=langue)
    if langue == "en":
        return f"{ecrit}%"
    return f"{ecrit}{NARROW_NBSP}%"


def signed_points(ecart: float, decimales: int = 1, *, langue: Langue = "fr") -> str:
    """Un écart entre deux parts, signé, en points : `0.098` → « +9,8 pts »,
    « +9.8 pts » en anglais."""
    return f"{number(ecart * 100.0, decimales, signed=True, langue=langue)}{NBSP}pts"


def exact(valeur: float, *, langue: Langue = "fr") -> str:
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
    return number(valeur, max(-exposant, 0), trim=True, langue=langue)


def compact(valeur: float, *, langue: Langue = "fr") -> str:
    """L'écriture la plus courte d'un paramètre : `0.94` → « 0,94 », `60.0` → « 60 » ;
    « 0.94 » en anglais.

    Pour une constante que l'on CITE (λ de l'EWMA, valeur d'un seuil), dont le
    nombre de décimales n'est pas choisi mais celui de la constante elle-même.
    """
    if not math.isfinite(valeur):
        raise ValueError(f"Valeur non finie à écrire : {valeur!r}")
    ecrit = f"{valeur:g}"
    if langue != "en":
        ecrit = ecrit.replace(".", ",")
    return ecrit.replace("-", MINUS)
