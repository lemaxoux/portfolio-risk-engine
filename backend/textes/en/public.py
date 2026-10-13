"""Les textes d'erreur du serveur public, en anglais américain (chantier 9.6).

Les mêmes noms et les mêmes signatures que `fr/public.py` : ceux que le
serveur public reprend de `api.py`, liés par leur nom, et ceux qui lui sont
propres. Aucun ne porte de commande, aucun ne renvoie à l'application
installée. « Security » pour un titre, « holding » pour une ligne du
portefeuille, « line » pour une ligne de fichier ou de tableau, comme dans
`api.py`.
"""

from __future__ import annotations

from backend import typography

from . import api


def _milliers(nombre: int) -> str:
    return typography.thousands(nombre, langue="en")


def _compte(nombre: int, singulier: str, pluriel: str | None = None) -> str:
    """« 2 lines », « 14 securities », « 16,000 bytes » : groupé, lié à son mot."""
    return typography.counted(
        nombre, singulier, pluriel, affiche=_milliers(nombre), langue="en"
    )


# ═══════════════════════════════ Repris de l'API locale, sans un mot changé ══

VALEUR_REFUSEE = api.VALEUR_REFUSEE
REQUETE_REFUSEE = api.REQUETE_REFUSEE

TICKER_VIDE = api.TICKER_VIDE
doublon = api.doublon
quantite_non_finie = api.quantite_non_finie
quantite_non_positive = api.quantite_non_positive
prix_de_revient_non_fini = api.prix_de_revient_non_fini
prix_de_revient_negatif = api.prix_de_revient_negatif

FICHIER_ILLISIBLE = api.FICHIER_ILLISIBLE
FICHIER_VIDE = api.FICHIER_VIDE
aucun_separateur = api.aucun_separateur
colonnes_manquantes = api.colonnes_manquantes
fichier_trop_volumineux = api.fichier_trop_volumineux
colonnes_en_trop = api.colonnes_en_trop
quantite_absente = api.quantite_absente
quantite_illisible = api.quantite_illisible
prix_de_revient_illisible = api.prix_de_revient_illisible


# ═══════════════════════════════════════════════════ Positions soumises ══


def titre_inconnu(ticker: str, connus: str) -> str:
    return f"{ticker} is not a security of the database. Available securities: {connus}."


def titre_sans_prix(ticker: str) -> str:
    return (
        f"{ticker} has no price history in the database. It can be neither "
        "valued nor analyzed."
    )


AUCUNE_POSITION = (
    "No position submitted. A portfolio without holdings has no risk to measure."
)


def trop_de_positions(soumises: int, maximum: int) -> str:
    return (
        f"{_compte(soumises, 'position')} submitted, and the database holds "
        f"{_compte(maximum, 'security', 'securities')}. "
        "A portfolio has at most one line per security."
    )


def lignes_refusees(nombre: int) -> str:
    return f"{_compte(nombre, 'line')} rejected: the portfolio was not analyzed."


def lignes_du_fichier_refusees(nombre: int) -> str:
    return f"{_compte(nombre, 'line')} rejected: the file was not kept."


# ═════════════════════════════════════════════════════ Ce que le serveur refuse ══


def corps_trop_volumineux(maximum: int) -> str:
    return f"Request too large: maximum {_compte(maximum, 'byte')}."


def limite_atteinte(maximum: int, minutes: int) -> str:
    return (
        f"Too many requests from this address: at most {_milliers(maximum)} "
        f"per period of {_compte(minutes, 'minute')}. Try again later."
    )


SERVEUR_OCCUPE = "The server is already computing other analyses. Try again in a moment."

ANALYSE_IMPOSSIBLE = "This portfolio cannot be analyzed on the server's database."

ERREUR_INTERNE = "The server could not complete this calculation."

ROUTE_INCONNUE = "No route at this address."

METHODE_REFUSEE = "This route does not accept this method."

ORIGINE_REFUSEE = "This origin is not allowed to call this server."
