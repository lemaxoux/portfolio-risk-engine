"""Les textes de la couche API, en anglais américain (chantier 7D).

Les mêmes noms et les mêmes signatures que `fr/api.py`. « Line » pour une
ligne d'un fichier ou du tableau de saisie (« Line 4: »), « holding » pour une
ligne du portefeuille, « security » pour un titre, « cost basis » pour le prix
de revient. Une valeur citée l'est entre guillemets anglais, sans espace
intérieure ; un libellé d'un autre logiciel cité garde sa ponctuation dehors
(“CSV UTF-8”.). La première phrase d'un refus de ligne ne porte aucun
deux-points, comme en français.

Chaque nombre passe par `typography`, groupé à l'anglaise à partir de quatre
chiffres et lié au mot qu'il compte (« 1,000,000 bytes », « 2 lines »), comme
le français depuis la session 2 du chantier.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend import typography


def _milliers(nombre: int) -> str:
    return typography.thousands(nombre, langue="en")


def _compte(nombre: int, mot: str) -> str:
    """« 2 lines », « 1,500 positions » : groupé, lié à son mot."""
    return typography.counted(nombre, mot, affiche=_milliers(nombre), langue="en")


# ═══════════════════════════════════════════════════════ Corps d'erreur ══


def lignes_refusees(nombre: int) -> str:
    return f"{_compte(nombre, 'line')} rejected: no position was written."


def ecriture_refusee(raison: str) -> str:
    return f"Write rejected by the database: {raison}"


def route_inconnue(chemin: str) -> str:
    return f"No API route at this path: /{chemin}"


VALEUR_REFUSEE = "value rejected"

REQUETE_REFUSEE = "Request rejected by validation."


# ═══════════════════════════════════════════════════ Positions soumises ══

AUCUNE_POSITION = (
    "No position submitted. A portfolio without holdings has no risk to "
    "measure; to empty a portfolio, delete it."
)


def trop_de_positions(soumises: int, maximum: int) -> str:
    return (
        f"{_compte(soumises, 'position')} submitted, maximum {_milliers(maximum)}. "
        "This limit protects the memory of the process; it has no "
        "methodological justification."
    )


TICKER_VIDE = "Empty ticker."


def doublon(ticker: str, ligne_precedente: int | None) -> str:
    ou = "" if ligne_precedente is None else f" (already line {ligne_precedente})"
    return (
        f"{ticker} appears twice{ou}. One line per security: add up the "
        "quantities before submitting."
    )


def titre_inconnu(ticker: str, connus: str) -> str:
    return (
        f"{ticker} is not a known security. Available securities: {connus}. "
        f"To add one: python -m backend.ingestion add {ticker}"
    )


def titre_sans_prix(ticker: str) -> str:
    return (
        f"{ticker} is known but has no price history in the database. It can "
        "be neither valued nor analyzed. Load it with: "
        f"python -m backend.ingestion add {ticker}"
    )


def quantite_non_finie(ticker: str) -> str:
    return f"Non-finite quantity for {ticker}."


def quantite_non_positive(ticker: str, quantite: float) -> str:
    return (
        f"Zero or negative quantity for {ticker} "
        f"({typography.exact(quantite, langue='en')}). Weights are computed "
        "by market value: a short position is not supported in v1."
    )


def prix_de_revient_non_fini(ticker: str) -> str:
    return f"Non-finite cost basis for {ticker}."


def prix_de_revient_negatif(ticker: str) -> str:
    return f"Negative cost basis for {ticker}."


# ═══════════════════════════════════════════════════════════ Fichier CSV ══

FICHIER_ILLISIBLE = (
    "Unreadable file: neither UTF-8 nor CP1252. Save it again from the "
    "spreadsheet as “CSV UTF-8”."
)


def aucun_separateur(en_tete: str) -> str:
    return f"No `;` or `,` separator in the first line. Expected header: {en_tete}"


def colonnes_manquantes(manquantes: Sequence[str], en_tete: str, lues: Sequence[str]) -> str:
    return (
        f"Columns missing from the header: {', '.join(manquantes)}. "
        f"Expected header: {en_tete} "
        f"(read: {', '.join(lues) if lues else 'empty line'})"
    )


def fichier_trop_volumineux(maximum: int) -> str:
    return (
        f"File too large: maximum {_compte(maximum, 'byte')}. "
        "A portfolio fits in a few kilobytes."
    )


FICHIER_VIDE = "Empty file."


def colonnes_en_trop(lues: int, attendues: int, virgule_decimale_coupee: bool) -> str:
    indice = (
        " With the `,` separator, a decimal comma cuts the number in two."
        if virgule_decimale_coupee
        else ""
    )
    return f"{_compte(lues, 'column')} read, the header has {attendues}.{indice}"


def quantite_absente(colonnes: int, separateur: str, en_tete: str) -> str:
    return (
        f"Quantity missing, {_compte(colonnes, 'column')} "
        f"read with the `{separateur}` separator. Expected header: {en_tete}"
    )


def quantite_illisible(brut: str, decimale: str) -> str:
    return (
        f"“{brut}” is not a readable quantity. Accepted decimal separator: "
        f"`{decimale}`."
    )


def prix_de_revient_illisible(brut: str, decimale: str) -> str:
    return (
        f"“{brut}” is not a readable cost basis. Accepted decimal separator: "
        f"`{decimale}`."
    )
