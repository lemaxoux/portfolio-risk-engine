"""Les textes de la couche API, en français : refus d'une saisie, refus d'un
fichier, corps d'erreur.

Déplacés tels quels (chantier 7D) de `api/validation.py`, `api/csv_import.py`,
`api/errors.py`, `api/static.py` et `api/routes/portfolios.py`, qui gardent
leurs décisions : quel refus, pour quelle ligne, sur quel champ. Le 404 d'un
portefeuille inexistant est le message du moteur
(`moteur.portefeuille_introuvable`) : il n'est écrit qu'une fois.

Un refus de ligne s'affiche après « Ligne 4 : » : sa première phrase ne porte
aucun deux-points. Les espaces avant « : » et dans les guillemets sont
ordinaires ici ; la publication (`typography.prose`) les rend insécables.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend import typography

# ═══════════════════════════════════════════════════════ Corps d'erreur ══


def lignes_refusees(nombre: int) -> str:
    """L'en-tête d'un refus de plusieurs lignes ; un refus unique est repris
    tel quel, sans décompte."""
    return f"{nombre} lignes refusées : aucune position n'a été écrite."


def ecriture_refusee(raison: str) -> str:
    """Le filet d'une contrainte de la base violée malgré la validation."""
    return f"Écriture refusée par la base : {raison}"


def route_inconnue(chemin: str) -> str:
    return f"Aucune route d'API à ce chemin : /{chemin}"


# Les replis d'un refus de validation de FastAPI sans message : celui de
# pydantic, quand il existe, est publié tel quel, dans les deux langues.
VALEUR_REFUSEE = "valeur refusée"

REQUETE_REFUSEE = "Requête refusée à la validation."


# ═══════════════════════════════════════════════════ Positions soumises ══

AUCUNE_POSITION = (
    "Aucune position soumise. Un portefeuille sans ligne n'a pas "
    "de risque à mesurer ; pour vider un portefeuille, le "
    "supprimer."
)


def trop_de_positions(soumises: int, maximum: int) -> str:
    return (
        f"{soumises} positions soumises, maximum {maximum}. "
        "Cette limite protège la mémoire du processus ; elle n'a pas "
        "de justification méthodologique."
    )


TICKER_VIDE = "Ticker vide."


def doublon(ticker: str, ligne_precedente: int | None) -> str:
    """La ligne où le titre est déjà apparu, quand le client numérote."""
    ou = "" if ligne_precedente is None else f" (déjà ligne {ligne_precedente})"
    return (
        f"{ticker} apparaît deux fois{ou}. Une ligne par titre : "
        "additionner les quantités avant de soumettre."
    )


def titre_inconnu(ticker: str, connus: str) -> str:
    return (
        f"{ticker} n'est pas un titre connu. Titres disponibles : "
        f"{connus}. Pour en ajouter un : "
        f"python -m backend.ingestion add {ticker}"
    )


def titre_sans_prix(ticker: str) -> str:
    return (
        f"{ticker} est connu mais n'a aucun historique de prix en "
        "base. Il ne peut être ni valorisé ni analysé. "
        f"Le charger avec : python -m backend.ingestion add {ticker}"
    )


def quantite_non_finie(ticker: str) -> str:
    return f"Quantité non finie pour {ticker}."


def quantite_non_positive(ticker: str, quantite: float) -> str:
    return (
        f"Quantité nulle ou négative pour {ticker} "
        f"({typography.exact(quantite)}). Les poids sont "
        "calculés en valeur "
        "de marché : une position vendue à découvert n'est pas "
        "prise en charge en v1."
    )


def prix_de_revient_non_fini(ticker: str) -> str:
    return f"Prix de revient non fini pour {ticker}."


def prix_de_revient_negatif(ticker: str) -> str:
    return f"Prix de revient négatif pour {ticker}."


# ═══════════════════════════════════════════════════════════ Fichier CSV ══

FICHIER_ILLISIBLE = (
    "Fichier illisible : ni UTF-8 ni CP1252. Le réenregistrer depuis le "
    "tableur en « CSV UTF-8 »."
)


def aucun_separateur(en_tete: str) -> str:
    return (
        "Aucun séparateur `;` ni `,` dans la première ligne. En-tête "
        f"attendu : {en_tete}"
    )


def colonnes_manquantes(manquantes: Sequence[str], en_tete: str, lues: Sequence[str]) -> str:
    return (
        f"Colonnes manquantes dans l'en-tête : {', '.join(manquantes)}. "
        f"En-tête attendu : {en_tete} "
        f"(lu : {', '.join(lues) if lues else 'ligne vide'})"
    )


def fichier_trop_volumineux(maximum: int) -> str:
    return (
        f"Fichier trop volumineux : maximum {maximum} octets. "
        "Un portefeuille tient en quelques kilo-octets."
    )


FICHIER_VIDE = "Fichier vide."


def colonnes_en_trop(lues: int, attendues: int, virgule_decimale_coupee: bool) -> str:
    """Une ligne plus large que l'en-tête. L'indice sur la virgule décimale
    n'est donné que lorsque le lecteur l'a jugé utile."""
    indice = (
        " Avec le séparateur `,`, une virgule décimale coupe le nombre en deux."
        if virgule_decimale_coupee
        else ""
    )
    return f"{lues} colonnes lues, l'en-tête en a {attendues}.{indice}"


def quantite_absente(colonnes: int, separateur: str, en_tete: str) -> str:
    return (
        f"Quantité absente, {colonnes} colonne(s) lue(s) avec "
        f"le séparateur `{separateur}`. En-tête attendu : "
        f"{en_tete}"
    )


def quantite_illisible(brut: str, decimale: str) -> str:
    """La valeur refusée est citée entre guillemets français, comme dans le
    tableau de saisie."""
    return (
        f"« {brut} » n'est pas une quantité "
        f"lisible. Décimale acceptée : `{decimale}`."
    )


def prix_de_revient_illisible(brut: str, decimale: str) -> str:
    return (
        f"« {brut} » n'est pas un prix de revient "
        f"lisible. Décimale acceptée : `{decimale}`."
    )
