"""Les gardes des textes publiés, en un seul endroit, dans les deux langues.

Chantier 7D. Les expressions de la première partie vivaient dans cinq
fichiers de test, et `test_methodologie.py` en importait de trois d'entre
eux : `test_textes_publies.py` (ponctuation, glyphes, paires, dates, durées),
`test_api_analysis.py` (espaces avant « % » et avant le mot compté),
`test_rules.py` (formulation prescriptive, score), `test_nombres_publies.py`
(point décimal, trait d'union pris pour un signe moins). Elles sont ici sans
qu'un caractère ait changé, et chaque fichier les importe.

La seconde partie les double pour l'anglais (anglais américain, ponctuation de
Chicago : `anglais-proposition.md`, §c et §d, hors dépôt). Un texte anglais
qu'aucune garde ne lirait serait le seul texte du produit que rien ne
contrôle.

Chaque garde a ses témoins, fautifs et légitimes, dans le fichier qui
l'emploie ou dans `test_gardes_texte.py` : une garde qu'on n'a jamais vue
échouer ne prouve rien.
"""

from __future__ import annotations

import ast
import re

from backend.typography import MINUS, NARROW_NBSP, NBSP, WORD_JOINER


def toutes_les_chaines(noeud, chemin=""):
    """Chaque chaîne d'une réponse, avec son chemin — pour nommer la fautive."""
    if isinstance(noeud, str):
        yield chemin, noeud
    elif isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield from toutes_les_chaines(valeur, f"{chemin}.{cle}")
    elif isinstance(noeud, list):
        for rang, valeur in enumerate(noeud):
            yield from toutes_les_chaines(valeur, f"{chemin}[{rang}]")


def chaines_publiables(source: str) -> list[tuple[int, str]]:
    """Chaque chaîne d'un module, avec sa ligne, hors docstrings et hors
    documentation OpenAPI."""
    arbre = ast.parse(source)
    ecartees: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = noeud.body
            if corps and isinstance(corps[0], ast.Expr) and isinstance(corps[0].value, ast.Constant):
                ecartees.add(id(corps[0].value))
        elif isinstance(noeud, ast.keyword) and noeud.arg == "description":
            ecartees.update(id(n) for n in ast.walk(noeud.value))
        elif isinstance(noeud, ast.Assign) and any(
            isinstance(cible, ast.Name) and cible.id == "DESCRIPTION" for cible in noeud.targets
        ):
            ecartees.update(id(n) for n in ast.walk(noeud.value))
    return [
        (noeud.lineno, noeud.value)
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in ecartees
    ]


# ═══════════════════════════════════════════════════════════════ Français ══
#
# Ponctuation, glyphes, paires, dates et durées (venues de
# `test_textes_publies.py`).

# Une espace ORDINAIRE (U+0020) avant « : », « ; », « ? » ou « ! » suivi d'un
# blanc ou de la fin, après « « », avant « » ». Le motif est celui de
# `typography.prose`.
ESPACE_ORDINAIRE = re.compile(r".{0,30}(?: [:;?!](?=\s|$)|« | »).{0,10}")

GREC = re.compile(f"[{chr(0x370)}-{chr(0x3FF)}]")

# Écrit par son point de code : ce fichier ne doit pas contenir, dans une
# chaîne, le caractère qu'il interdit.
CADRATIN = chr(0x2014)

# La provenance d'une mesure : écrite en Plex Sans, qui a le grec.
PROVENANCE = re.compile(r"\.risk\..*\.(method|detail)$")

# Un tiret court pris entre deux caractères qui ne sont pas des blancs, sans le
# caractère de liaison qui interdit la coupure après lui.
TIRET_COURT = chr(0x2013)
PAIRE_SECABLE = re.compile(rf"\S{TIRET_COURT}(?=[^\s{WORD_JOINER}])")

# Des données ou un identifiant, pas de la prose : la paire d'un fait, le
# sujet d'une observation.
HORS_PROSE = re.compile(r"\.facts\.|\.subject$")

# Une date ISO citée dans un texte : chacun de ses deux traits d'union porte
# le caractère de liaison. Un champ qui n'est qu'une date (`as_of`, `start`,
# `end`, la date d'une séance) est une donnée, pas de la prose : il reste nu.
DATE_ISO = re.compile(rf"[0-9]{{4}}-{WORD_JOINER}?[0-9]{{2}}-{WORD_JOINER}?[0-9]{{2}}")
DATE_NUE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def dates_secables(texte: str) -> list[str]:
    """Les dates ISO d'un texte dont un trait d'union au moins est sans liaison."""
    return [d.group(0) for d in DATE_ISO.finditer(texte) if d.group(0).count(WORD_JOINER) < 2]

# Un nombre, une espace ORDINAIRE, puis l'unité de durée qu'il compte ou le
# mois dont il est le jour ; un mois, une espace ordinaire, puis son année.
MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
DUREES = ("ans", "an", "mois", "semaines", "semaine", "jours", "jour")
LIEN_SECABLE = re.compile(
    rf".{{0,30}}(?:\d (?:{'|'.join(DUREES + MOIS)})\b"
    rf"|\b(?:{'|'.join(MOIS)}) \d{{4}}\b).{{0,10}}"
)

# Ce que le moteur ne mesure pas, dit d'une couverture partielle (textes de
# lecture, 2026-10-05) : « en moyenne plus spéculative », « probablement
# sous-estimée », « plus jeune ».
GENERALITES = ("spéculati", "sous-estimée", "plus jeune")

# Les espaces d'un nombre (venues de `test_api_analysis.py`).

MOTS_COMPTES = ("points", "point", "pts", "séances", "séance", "lignes", "ligne")

ESPACE_AVANT_POURCENT = re.compile(r".{0,45}\u0020%")
ESPACE_AVANT_MOT = re.compile(
    rf".{{0,45}}\d\u0020(?:{'|'.join(MOTS_COMPTES)})\b"
)

# Le registre (venu de `test_rules.py`).

# Garde lexicale : formes qui transformeraient une observation en consigne.
PRESCRIPTIF = re.compile(
    r"\b(devr\w*|doi(s|t|vent)|il faut|faudr\w*|recommand\w*|conseill\w*|"
    r"rédui\w*|allég\w*|allège\w*|vend(s|ez|re)|achèt\w*|achet(er|ez)|"
    r"renforc\w*|privilégi\w*|évit(e|ez|er)|envisag\w*|rééquilibr\w*|"
    r"diversifi(e|es|ez|er))\b",
    re.IGNORECASE,
)

# Motif d'un score ramené sur 100 (« 72/100 », « 7,5 / 100 »).
SCORE_SUR_100 = re.compile(r"\b\d+(,\d+)?\s*/\s*100\b")

# L'écriture d'un nombre (venue de `test_nombres_publies.py`).

# Un chiffre, un point, un chiffre : « 4.07 », « -43.9 ». Ni une date ISO
# (tirets), ni « BRK.B » (lettres), ni « backend.ingestion » (lettres).
POINT_DECIMAL = re.compile(r".{0,40}\d\.\d.{0,10}")

# Un trait d'union qui sert de signe moins : précédé d'un blanc, d'une
# parenthèse ou du début de chaîne, suivi d'un chiffre. Le tiret d'une date
# (« 2024-09-05 ») suit un chiffre et n'est pas pris.
TRAIT_D_UNION_SIGNE = re.compile(r".{0,40}(?<![\w−-])-\d.{0,10}")

# Un nombre écrit en lettres, suivi de ce qu'il compte (chantier 7D). La liste
# fermée des nombres de la méthodologie ne voyait que les chiffres : « environ
# trois ans » à la place de « environ deux ans » passait. Un tel nombre se
# vérifie désormais comme un chiffre. « Un » et « une » n'en sont pas : ce sont
# aussi des articles (« le rendement d'un jour », « un jour de bourse sur
# vingt »), et les compter ferait déclarer une dizaine de faux nombres.
# « derniers » ou « dernières » peuvent séparer le nombre de son unité.
NOMBRE_EN_LETTRES = re.compile(
    r"\b(deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|vingt|cent)"
    r"(?:\s+(?:derniers|dernières|dernier|dernière|autres|seuls|seules))?"
    r"\s+(?:ans?|années?|mois|semaines?|jours?|journées?|séances?)\b",
    re.IGNORECASE,
)


# ════════════════════════════════════════════════════════════════ Anglais ══
#
# Les mêmes règles, transposées : anglais américain, ponctuation de Chicago,
# aucune espace avant la ponctuation haute, guillemets doubles, aucune espace
# avant « % », virgule des milliers, point décimal, « April 4, 2025 ».

# Toute espace, ordinaire ou insécable, avant « : », « ; », « ? » ou « ! »
# suivi d'un blanc ou de la fin ; tout guillemet français ; toute espace collée
# à l'intérieur de guillemets anglais. L'espace insécable compte : posée par
# `typography.prose` sur un anglais fautif, elle cacherait la faute.
PONCTUATION_EN = re.compile(r".{0,30}(?:\s[:;?!](?=\s|$)|[«»]|“\s|\s”).{0,10}")

# Un nombre, une espace ORDINAIRE, puis l'unité qu'il compte (« 2 years »,
# « 7 trading days ») ; un mois, une espace ordinaire, puis son jour ; le jour,
# sa virgule, une espace ordinaire, puis l'année. « April 4, 2025 » ne se coupe
# ni après le mois ni après la virgule.
MOIS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
DUREES_EN = ("years", "year", "months", "month", "weeks", "week", "days", "day", "trading")
LIEN_SECABLE_EN = re.compile(
    rf".{{0,30}}(?:\d (?:{'|'.join(DUREES_EN)})\b"
    rf"|\b(?:{'|'.join(MOIS_EN)}) \d"
    rf"|\b(?:{'|'.join(MOIS_EN)})\s\d{{1,2}}, \d{{4}}\b).{{0,10}}"
)

GENERALITES_EN = ("speculat", "underestimat", "younger", "riskier on average")

MOTS_COMPTES_EN = ("points", "point", "pts", "sessions", "session", "holdings", "holding")

# Rien avant « % », ni espace ordinaire, ni fine, ni insécable : « 1.06% ».
ESPACE_AVANT_POURCENT_EN = re.compile(r".{0,45}\s%")
ESPACE_AVANT_MOT_EN = re.compile(
    rf".{{0,45}}\d\u0020(?:{'|'.join(MOTS_COMPTES_EN)})\b"
)

# Formes qui transformeraient une observation en consigne. « Diversify » n'est
# admis sous aucune forme verbale : « they diversify less » se lit comme un
# impératif. « Diversification » reste permis.
PRESCRIPTIF_EN = re.compile(
    r"\b(should|shall|must|ought|needs? to|needed to|ha(ve|s|d) to|recommend\w*|"
    r"advis\w*|suggest\w*|consider(s|ed|ing)?|reduc\w*|trim\w*|lighten\w*|"
    r"sell(s|ing)?|buy(s|ing)?|purchas\w*|strengthen\w*|favou?r\w*|prefer\w*|"
    r"avoid\w*|rebalanc\w*|diversif(y|ies|ying))\b",
    re.IGNORECASE,
)

# « 72/100 », « 7.5 / 100 ».
SCORE_SUR_100_EN = re.compile(r"\b\d+(\.\d+)?\s*/\s*100\b")

# Une virgule entre deux chiffres qui n'est pas suivie d'exactement trois
# chiffres : une virgule décimale (« 1,06 », « 0,5 »), pas le séparateur des
# milliers (« 1,420 », « 100,000 »).
VIRGULE_DECIMALE = re.compile(r".{0,40}\d,(?!\d{3}(?!\d))\d.{0,10}")

# Le même principe qu'en français, et la même exclusion : « one » est aussi
# un article ou un pronom (« one trading day in twenty »). « past », « last »
# ou « trading » peuvent séparer le nombre de son unité.
NOMBRE_EN_LETTRES_EN = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|hundred)"
    r"(?:\s+(?:more|other|past|last|extra))?"
    r"(?:\s+trading)?"
    r"\s+(?:years?|months?|weeks?|days?|sessions?)\b",
    re.IGNORECASE,
)

# Du français dans un texte anglais : un guillemet français, une lettre
# accentuée, un mot-outil ou un terme du produit. Ne s'applique qu'à la prose :
# un nom de portefeuille ou de titre est une donnée, il s'écrit comme on l'a
# saisi.
FRANCAIS = re.compile(
    r"[«»]|[àâçéèêëîïôùûüÿœæ]|\b(le|la|les|des|du|une|est|sont|sur|pour|avec|"
    r"sans|aucun|aucune|séances?|portefeuilles?|jours? de bourse)\b",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════ Par langue ══

LANGUES = ("fr", "en")

PONCTUATION = {"fr": ESPACE_ORDINAIRE, "en": PONCTUATION_EN}
LIENS_SECABLES = {"fr": LIEN_SECABLE, "en": LIEN_SECABLE_EN}
ESPACES_AVANT_POURCENT = {"fr": ESPACE_AVANT_POURCENT, "en": ESPACE_AVANT_POURCENT_EN}
ESPACES_AVANT_MOT = {"fr": ESPACE_AVANT_MOT, "en": ESPACE_AVANT_MOT_EN}
NOMBRES_MAL_ECRITS = {"fr": POINT_DECIMAL, "en": VIRGULE_DECIMALE}
PRESCRIPTIONS = {"fr": PRESCRIPTIF, "en": PRESCRIPTIF_EN}
NOTES_SUR_100 = {"fr": SCORE_SUR_100, "en": SCORE_SUR_100_EN}
GENERALITES_PAR_LANGUE = {"fr": GENERALITES, "en": GENERALITES_EN}
NOMBRES_EN_LETTRES = {"fr": NOMBRE_EN_LETTRES, "en": NOMBRE_EN_LETTRES_EN}

GARDES_PAR_LANGUE = {
    "ponctuation": PONCTUATION,
    "liens sécables": LIENS_SECABLES,
    "espaces avant %": ESPACES_AVANT_POURCENT,
    "espaces avant le mot compté": ESPACES_AVANT_MOT,
    "nombres mal écrits": NOMBRES_MAL_ECRITS,
    "prescriptions": PRESCRIPTIONS,
    "notes sur 100": NOTES_SUR_100,
    "généralités": GENERALITES_PAR_LANGUE,
    "nombres en lettres": NOMBRES_EN_LETTRES,
}


def fautes_de_forme(texte: str, langue: str, *, grec_admis: bool = False, prose: bool = True) -> list[str]:
    """Les gardes de forme d'une langue, sur un texte : ponctuation haute et
    guillemets, tiret cadratin, lettre grecque, paire et date sécables, durée
    ou date séparée de son unité, espace avant « % » et avant le mot compté,
    nombre mal écrit, trait d'union pris pour un signe moins.

    `grec_admis` : la provenance d'une mesure, écrite en IBM Plex Sans.
    `prose=False` : une donnée (un fait, un sujet), où une paire et une date
    restent nues.
    """
    fautes = [f"ponctuation : {e!r}" for e in PONCTUATION[langue].findall(texte)]
    if CADRATIN in texte:
        fautes.append(f"tiret cadratin : {texte[:60]!r}")
    if not grec_admis and GREC.search(texte):
        fautes.append(f"lettre grecque : {texte[:60]!r}")
    if prose:
        if PAIRE_SECABLE.search(texte):
            fautes.append(f"paire sécable : {texte[:60]!r}")
        if not DATE_NUE.match(texte):
            fautes += [f"date sécable : {d}" for d in dates_secables(texte)]
    fautes += [f"lien sécable : {e!r}" for e in LIENS_SECABLES[langue].findall(texte)]
    fautes += [f"espace avant % : {e!r}" for e in ESPACES_AVANT_POURCENT[langue].findall(texte)]
    fautes += [f"espace avant le mot compté : {e!r}" for e in ESPACES_AVANT_MOT[langue].findall(texte)]
    fautes += [f"nombre mal écrit : {e!r}" for e in NOMBRES_MAL_ECRITS[langue].findall(texte)]
    fautes += [f"trait d'union pour signe moins : {e!r}" for e in TRAIT_D_UNION_SIGNE.findall(texte)]
    return fautes


def fautes_de_registre(texte: str, langue: str) -> list[str]:
    """Les gardes de registre : rien de prescriptif, aucune note globale,
    aucune généralité que le moteur ne mesure pas."""
    fautes = [
        f"prescriptif : {texte[max(0, m.start() - 25):m.end() + 10]!r}"
        for m in PRESCRIPTIONS[langue].finditer(texte)
    ]
    if "score" in texte.lower() or NOTES_SUR_100[langue].search(texte):
        fautes.append(f"note globale : {texte[:60]!r}")
    fautes += [f"généralité : {g}" for g in GENERALITES_PAR_LANGUE[langue] if g in texte]
    return fautes


def fautes_de_francais(texte: str) -> list[str]:
    """Du français dans un texte anglais."""
    return [
        f"français : {texte[max(0, m.start() - 25):m.end() + 10]!r}"
        for m in FRANCAIS.finditer(texte)
    ]


# ═════════════════════════════════════════════ Les nombres d'une traduction ══
#
# Une phrase anglaise ne dit ni plus ni moins que la française : pour ses
# nombres, cela se vérifie. `nombres` ramène ceux d'un texte à une écriture
# commune aux deux langues : « 1 234,5 % » et « 1,234.5% » donnent « 1234.5 »,
# « −5,0 » et « −5.0 » donnent « -5.0 ». Une date ISO compte pour un nombre,
# « 1er » pour 1. Un nombre écrit en lettres n'en est pas un ici : « deux » et
# « two » se relisent dans le tableau du rapport de chaque lot.

DATE_EN_CHIFFRES = re.compile(r"\d{4}-\d{2}-\d{2}")
NOMBRES_ECRITS = {
    "fr": re.compile(
        rf"[{MINUS}-]?\d{{1,3}}(?:[{NARROW_NBSP}{NBSP}]\d{{3}})+(?:,\d+)?|[{MINUS}-]?\d+(?:,\d+)?"
    ),
    "en": re.compile(rf"[{MINUS}-]?\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|[{MINUS}-]?\d+(?:\.\d+)?"),
}


def nombres(texte: str, langue: str) -> list[str]:
    """Les nombres d'un texte, triés, dans l'écriture commune aux deux langues."""
    texte = texte.replace(WORD_JOINER, "")
    trouves = DATE_EN_CHIFFRES.findall(texte)
    for ecrit in NOMBRES_ECRITS[langue].findall(DATE_EN_CHIFFRES.sub(" ", texte)):
        ecrit = ecrit.replace(MINUS, "-")
        if langue == "fr":
            ecrit = ecrit.replace(NARROW_NBSP, "").replace(NBSP, "").replace(",", ".")
        else:
            ecrit = ecrit.replace(",", "")
        trouves.append(ecrit)
    return sorted(trouves)
