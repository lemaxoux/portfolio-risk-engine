"""Lecture d'un CSV de positions, y compris celui qu'exporte un Excel français.

═══ CE QU'EXPORTE VRAIMENT EXCEL ═══

« Un CSV » n'est pas un format. Sur un Windows français, « Enregistrer sous →
CSV » produit un fichier en séparateur POINT-VIRGULE, encodé en CP1252, avec la
VIRGULE comme séparateur décimal. Un lecteur qui suppose `,` et UTF-8 — c'est
à dire le lecteur par défaut de tout le monde — n'y voit qu'une seule colonne,
ou plante sur le premier accent. L'utilisateur, lui, a exporté depuis le tableur
qu'il avait, et il a raison.

Trois choses sont donc DEVINÉES à partir des octets, puis RENDUES dans la
réponse : l'encodage, le séparateur de champs, le séparateur décimal. Les
afficher est de la provenance, au même titre qu'une fenêtre d'estimation : un
utilisateur qui lit « cp1252, séparateur `;`, décimale `,` » comprend un
résultat inattendu au lieu de le subir.

ATTENTION À CE QUE « DÉCIMALE » DÉSIGNE. Le séparateur rendu est celui qui a été
OBSERVÉ dans les nombres du fichier, pas celui qui était admis. Avec `;` en
séparateur de champs, la virgule EST acceptée comme décimale — mais un fichier
`;` dont les quantités s'écrivent `40.5` n'en contient aucune, et annoncer `,`
décrirait la règle de lecture plutôt que le fichier. Ce serait une provenance
fausse, au même titre qu'annoncer « utf-8-sig » pour un fichier sans BOM.

Quatre valeurs possibles, donc : `,`, `.`, `mixte` quand le fichier mélange les
deux, et `aucune` quand tous les nombres sont entiers. Les deux dernières sont
des informations en soi : un fichier mixte sort d'un assemblage à la main, et
c'est utile à savoir.

═══ ORDRE DE DÉCODAGE ═══

utf-8-sig, puis utf-8, puis cp1252 — mais la marque d'ordre des octets (BOM) est
cherchée explicitement plutôt que tentée en premier. `bytes.decode("utf-8-sig")`
réussit sur n'importe quel UTF-8 valide, avec ou sans BOM : l'essayer d'abord
ferait annoncer « utf-8-sig » pour un fichier qui n'a pas de BOM. Ce serait une
provenance fausse, et ce projet n'en publie pas.

CP1252 en dernier recours seulement : il décode presque n'importe quelle suite
d'octets sans lever, et le placer plus haut masquerait un vrai UTF-8.

═══ CE QUE CE MODULE NE FAIT PAS ═══

Il ne valide pas les tickers ni les quantités — c'est `validation.validate`, qui
sert aussi au `PUT` JSON. Il ne touche pas la base. Il ne convertit aucune unité.
Il ne rédige pas ses refus : `textes/{fr,en}/api.py` les écrit dans la langue
demandée (chantier 7D).
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass
from typing import Literal

from backend.langue import Langue
from backend.textes import ErreurRedigee, textes

from .errors import Problem
from .validation import SubmittedPosition

# Un portefeuille tient en quelques kilo-octets. La borne existe pour qu'un
# fichier arbitraire ne se retrouve pas en mémoire, pas pour limiter l'usage.
MAX_BYTES = 1_000_000

# Un octet de plus que la limite : c'est tout ce qu'il faut lire pour savoir
# qu'un fichier la dépasse. L'appelant lit jusque-là plutôt que d'aspirer le
# fichier entier avant de le refuser.
#
# Portée exacte de cette borne : le serveur ASGI a déjà reçu le corps de la
# requête quand la route s'exécute, et Starlette l'a déversé dans un fichier
# temporaire au-delà de son propre seuil. Ce qui est évité ici, c'est de
# matérialiser ce corps en un objet `bytes` de taille arbitraire. Un vrai
# plafond de charge utile relèverait du serveur, pas de ce module.
PROBE_BYTES = 1_000_001

DELIMITERS: tuple[str, ...] = (";", ",")
COLONNE_TICKER = "ticker"
COLONNE_QUANTITE = "quantity"
COLONNE_PRIX_REVIENT = "cost_basis"
COLONNES_REQUISES: tuple[str, ...] = (COLONNE_TICKER, COLONNE_QUANTITE)
COLONNES_FACULTATIVES: tuple[str, ...] = (COLONNE_PRIX_REVIENT,)

EN_TETE_ATTENDU = "ticker;quantity[;cost_basis]"

# Séparateurs décimaux ADMIS selon le séparateur de champs. La virgule n'est une
# décimale qu'avec `;` : avec `,`, elle termine une colonne (voir `_nombre`).
# Le lecteur tranche avec CETTE table, et `GET /api/csv-format` la publie : la
# règle affichée à l'utilisateur est celle qui est appliquée, pas une copie.
DECIMALES_ADMISES: dict[str, tuple[str, ...]] = {";": (",", "."), ",": (".",)}

# La marque d'ordre des octets est cherchée à part (voir `decode`) ; les deux
# autres encodages sont essayés dans cet ordre.
ENCODAGE_BOM = "utf-8-sig"
ENCODAGES_ESSAYES: tuple[str, ...] = ("utf-8", "cp1252")

# L'exemple publié avec le format : ce qu'exporte un Excel français —
# point-virgule, virgule décimale —, avec un prix de revient laissé vide.
# `tests/test_api_csv.py` le fait lire par ce lecteur et importer sur la copie
# figée : un exemple qui ne s'importerait pas serait pire que pas d'exemple.
EXEMPLE = "ticker;quantity;cost_basis\nAAPL;40;185,20\nMSFT;25;\n"

# Le même, dans chaque langue de la réponse : à un lecteur anglophone, ce
# qu'exporte un Excel anglais — virgule, point décimal. Une donnée, pas une
# phrase : il ne se traduit pas, il change de format.
# `tests/test_langue_api.py` le fait lire et importer de même.
EXEMPLES: dict[str, str] = {
    "fr": EXEMPLE,
    "en": "ticker,quantity,cost_basis\nAAPL,40,185.20\nMSFT,25,\n",
}

# Séparateurs décimaux tels qu'ils peuvent être OBSERVÉS dans un fichier.
# `mixte` et `aucune` ne sont pas des cas d'erreur : le premier signale un
# fichier assemblé à la main, le second un fichier sans aucune décimale.
DECIMALES_OBSERVEES = ("." , "," , "mixte", "aucune")

# Ce qu'est un nombre, une fois ses espaces de milliers retirées : un signe
# facultatif, des chiffres LATINS, et au plus une décimale — virgule ou point —
# suivie de chiffres. Ni exposant, ni « inf », ni « nan », ni souligné. Le
# signe moins est admis ici pour que la VALIDATION, et non la lecture, refuse
# une quantité négative avec la bonne explication. Le client applique la même
# expression (`frontend/src/lib/saisie.ts`).
NOMBRE = re.compile(r"[+-]?[0-9]+(?:[.,][0-9]+)?")

# Espaces qu'un tableur glisse dans les milliers : fine insécable, insécable,
# ordinaire. Retirées avant lecture d'un nombre.
ESPACES = (" ", " ", " ")


@dataclass(frozen=True)
class CsvSource:
    """Comment le fichier a été lu.

    `decimal_separator` est OBSERVÉ, pas déduit du séparateur de champs :
    annoncer `,` pour un fichier `;` qui ne contient que des entiers, ou que des
    nombres écrits `40.5`, décrirait la règle de lecture et non le fichier.
    """

    filename: str | None
    encoding: Literal["utf-8", "utf-8-sig", "cp1252"]
    delimiter: Literal[",", ";"]
    decimal_separator: Literal[".", ",", "mixte", "aucune"]
    rows_read: int


@dataclass(frozen=True)
class CsvReading:
    positions: tuple[SubmittedPosition, ...]
    source: CsvSource
    problems: tuple[Problem, ...]


class CsvError(ErreurRedigee):
    """Le fichier n'est pas lisible du tout : ni encodage, ni en-tête exploitable.

    Distinct d'une liste de problèmes ligne à ligne : ici il n'y a pas de lignes
    à commenter, seulement un fichier qu'on ne peut pas ouvrir. Une erreur
    rédigée : `str()` rend le français, la route la rédige dans la langue de
    la réponse (`texte(langue)`).
    """

    def __init__(self, redaction: str, *arguments: object) -> None:
        super().__init__("api", redaction, *arguments)


def decode(payload: bytes) -> tuple[str, str]:
    """Texte et nom de l'encodage retenu. Lève `CsvError` si aucun ne convient."""
    if payload.startswith(codecs.BOM_UTF8):
        return payload.decode(ENCODAGE_BOM), ENCODAGE_BOM
    for encodage in ENCODAGES_ESSAYES:
        try:
            return payload.decode(encodage), encodage
        except UnicodeDecodeError:
            continue
    raise CsvError("FICHIER_ILLISIBLE")


def sniff_delimiter(entete: str) -> str:
    """Séparateur de champs, d'après la seule ligne d'en-tête.

    Le plus fréquent des deux l'emporte. `csv.Sniffer` est écarté : il inspecte
    tout le fichier et se laisse tromper par une virgule décimale dans une
    colonne de nombres, ce qui est exactement le cas que ce module doit gérer.
    """
    occurrences = {separateur: entete.count(separateur) for separateur in DELIMITERS}
    meilleur = max(DELIMITERS, key=lambda separateur: occurrences[separateur])
    if occurrences[meilleur] == 0:
        raise CsvError("aucun_separateur", EN_TETE_ATTENDU)
    return meilleur


def _nombre(brut: str, virgule_admise: bool) -> tuple[float, str | None]:
    """Lit un nombre ; rend sa valeur et le séparateur décimal OBSERVÉ.

    Le second membre vaut `","`, `"."`, ou None quand le nombre est entier.
    C'est ce qui permet à la réponse de décrire le fichier plutôt que la règle
    de lecture.

    La virgule n'est acceptée comme décimale que lorsque le séparateur de champs
    est `;`. Avec `,` en séparateur de champs, une virgule dans un nombre est une
    fin de colonne, pas une décimale : accepter les deux sens du même caractère
    dans le même fichier rendrait `1,5` indécidable.

    UNE GRAMMAIRE, PAS `float()`. `float()` accepte aussi `1e3`, `inf`, `nan`,
    `1_000` et des chiffres d'autres écritures : ce n'est pas ce qu'un tableur
    écrit, et le tableau de saisie ne saurait pas lire la même chose. Le nombre
    doit donc correspondre à `NOMBRE` une fois ses espaces de milliers
    retirées. Le lecteur du client (`frontend/src/lib/saisie.ts`) applique la
    même grammaire, et `tests/test_nombres_saisis.py` fait lire aux deux la
    même liste de cas.
    """
    texte = brut.strip()
    for espace in ESPACES:
        texte = texte.replace(espace, "")
    if NOMBRE.fullmatch(texte) is None:
        raise ValueError(f"Nombre illisible : {brut!r}")

    observee: str | None = None
    if virgule_admise and "," in texte:
        observee = ","
        texte = texte.replace(",", ".")
    elif "." in texte:
        observee = "."

    return float(texte), observee


def _admise(virgule_admise: bool) -> str:
    """Le séparateur décimal accepté, pour un message d'erreur."""
    return "," if virgule_admise else "."


def _decimale_observee(vues: set[str]) -> str:
    """Ce que les nombres du fichier contenaient réellement.

    `aucune` quand tous les nombres sont entiers, `mixte` quand le fichier
    mélange les deux écritures. Aucun des deux n'est une erreur : ce sont des
    faits sur le fichier, et le second signale un assemblage à la main.
    """
    if not vues:
        return "aucune"
    if len(vues) > 1:
        return "mixte"
    return vues.pop()


def _largeur(champs: list[str]) -> int:
    """Nombre de colonnes, colonnes VIDES finales exclues.

    Un séparateur en fin de ligne, fréquent dans un export de tableur, ajoute
    une colonne vide qui n'est pas une donnée. Même compte pour l'en-tête et
    pour les lignes, pour qu'une colonne vide de chaque côté ne décale rien.
    """
    # Le rang, compté depuis 1, de la dernière colonne non vide : sa position
    # EST la largeur. Écrit sans arithmétique, comme tout `backend/api/`.
    return max(
        (rang for rang, champ in enumerate(champs, start=1) if champ.strip()),
        default=0,
    )


def _colonnes_en_trop(
    ligne: list[str], largeur_entete: int, separateur: str, langue: Langue
) -> str | None:
    """Le refus d'une ligne plus large que l'en-tête, ou None.

    Sans ce contrôle, le lecteur lisait les colonnes qu'il connaissait et
    ignorait les autres : avec `,` en séparateur, « ALFA,1,5 » donnait la
    quantité 1, et « 185,20 » le prix de revient 185, sans un mot. Une lecture
    fausse et silencieuse est le pire des deux mondes.

    L'indice sur la virgule décimale n'est ajouté que lorsqu'il a un sens : le
    séparateur est la virgule, et ce qui déborde n'est fait que de chiffres.
    """
    largeur = _largeur(ligne)
    if largeur <= largeur_entete:
        return None
    en_trop = [champ.strip() for champ in ligne[largeur_entete:largeur]]
    decimale_coupee = separateur == "," and all(
        champ.isdigit() for champ in en_trop if champ
    )
    return textes(langue).api.colonnes_en_trop(largeur, largeur_entete, decimale_coupee)


def _colonnes(entete: list[str]) -> dict[str, int]:
    noms = [champ.strip().lower().lstrip("﻿") for champ in entete]
    index = {nom: position for position, nom in enumerate(noms)}
    manquantes = [nom for nom in COLONNES_REQUISES if nom not in index]
    if manquantes:
        raise CsvError("colonnes_manquantes", manquantes, EN_TETE_ATTENDU, noms)
    return index


def read(
    payload: bytes, filename: str | None = None, *, langue: Langue = "fr"
) -> CsvReading:
    """Lit le fichier et rend les positions soumises, sans rien valider d'autre.

    Lève `CsvError` quand le fichier est inexploitable dans son ensemble
    (trop gros, encodage inconnu, en-tête absent) ; rend des `Problem` quand ce
    sont des lignes précises qui sont en cause, rédigés dans `langue`.
    """
    t = textes(langue).api
    if len(payload) > MAX_BYTES:
        # La taille reçue n'est pas annoncée : l'appelant n'a lu que
        # `PROBE_BYTES` octets, et citer ce nombre décrirait la sonde plutôt
        # que le fichier.
        raise CsvError("fichier_trop_volumineux", MAX_BYTES)
    if not payload.strip():
        raise CsvError("FICHIER_VIDE")

    texte, encodage = decode(payload)
    premiere = texte.splitlines()[0] if texte.splitlines() else ""
    separateur = sniff_delimiter(premiere)
    # Avec `;`, la virgule est ADMISE comme décimale ; ce qui sera ANNONCÉ
    # dépend de ce que les nombres contiennent réellement.
    virgule_admise = "," in DECIMALES_ADMISES[separateur]

    lecteur = csv.reader(io.StringIO(texte), delimiter=separateur)
    lignes = [ligne for ligne in lecteur]
    if not lignes:
        raise CsvError("FICHIER_VIDE")

    index = _colonnes(lignes[0])
    largeur_entete = _largeur(lignes[0])
    positions: list[SubmittedPosition] = []
    problemes: list[Problem] = []
    vues: set[str] = set()

    # `start=2` : la première ligne de données est la ligne 2 du fichier, en-tête
    # compris — le numéro que l'utilisateur lit dans son tableur.
    for numero, ligne in enumerate(lignes[1:], start=2):
        if not any(champ.strip() for champ in ligne):
            continue

        debord = _colonnes_en_trop(ligne, largeur_entete, separateur, langue)
        if debord is not None:
            problemes.append(Problem(line=numero, problem=debord))
            continue

        if len(ligne) <= index[COLONNE_QUANTITE]:
            problemes.append(
                Problem(
                    line=numero,
                    problem=t.quantite_absente(len(ligne), separateur, EN_TETE_ATTENDU),
                )
            )
            continue

        ticker = ligne[index[COLONNE_TICKER]].strip()
        brut_quantite = ligne[index[COLONNE_QUANTITE]]
        try:
            quantite, vue = _nombre(brut_quantite, virgule_admise)
            if vue is not None:
                vues.add(vue)
        except ValueError:
            problemes.append(
                Problem(
                    line=numero,
                    field=COLONNE_QUANTITE,
                    value=brut_quantite.strip(),
                    # La valeur est citée entre guillemets, comme dans le
                    # tableau de saisie ; `prose` rend insécables les espaces
                    # des guillemets français à la publication.
                    problem=t.quantite_illisible(
                        brut_quantite.strip(), _admise(virgule_admise)
                    ),
                )
            )
            continue

        prix_revient: float | None = None
        position_prix = index.get(COLONNE_PRIX_REVIENT)
        if position_prix is not None and len(ligne) > position_prix:
            brut_prix = ligne[position_prix].strip()
            if brut_prix:
                try:
                    prix_revient, vue = _nombre(brut_prix, virgule_admise)
                    if vue is not None:
                        vues.add(vue)
                except ValueError:
                    problemes.append(
                        Problem(
                            line=numero,
                            field=COLONNE_PRIX_REVIENT,
                            value=brut_prix,
                            problem=t.prix_de_revient_illisible(
                                brut_prix, _admise(virgule_admise)
                            ),
                        )
                    )
                    continue

        positions.append(
            SubmittedPosition(
                ticker=ticker,
                quantity=quantite,
                cost_basis=prix_revient,
                line=numero,
            )
        )

    lues = len(positions)
    return CsvReading(
        positions=tuple(positions),
        source=CsvSource(
            filename=filename,
            encoding=encodage,
            delimiter=separateur,
            decimal_separator=_decimale_observee(vues),
            rows_read=lues,
        ),
        problems=tuple(problemes),
    )
