"""Les textes d'erreur du serveur public, en français (chantier 9.6).

Le serveur public (`backend/public_api/`) analyse le portefeuille qu'un
visiteur du site saisit. Il a ses propres textes, et ce module les porte
TOUS : `tests/test_textes_publics.py` parcourt chaque nom défini ici.

AUCUN NE PORTE DE COMMANDE, AUCUN NE RENVOIE À L'APPLICATION INSTALLÉE. Les
refus de l'API locale disent quoi lancer sur le poste : c'est ce qu'un
utilisateur de l'application a besoin de lire, et ce qu'un visiteur du site
ne peut pas faire. La liste des titres est fermée, et les textes le disent
tel quel.

DEUX SORTES DE NOMS.

* Ceux que le serveur public REPREND de `api.py`, sans un mot changé : les
  refus d'une ligne ou d'un fichier qui ne disent rien de l'application. Ils
  sont liés ici par leur nom, pour que la liste de ce que le serveur public
  peut publier se lise à un seul endroit, et que le test les parcoure avec
  les autres.
* Ceux qui lui sont PROPRES : là où le texte local porte une commande, parle
  d'une écriture en base, ou d'une borne que le serveur public n'a pas.

`api/validation.py` et `api/csv_import.py` reçoivent ce module à la place de
`api.py` (leur paramètre `redaction`) : les mêmes décisions, d'autres phrases.
Les noms et les signatures qu'ils appellent sont donc ceux de `api.py`.

Comme dans `api.py` : la première phrase d'un refus de ligne ne porte aucun
deux-points, les espaces sont ordinaires, la publication les rend insécables.
"""

from __future__ import annotations

from backend import typography

from . import api

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
    """La liste des titres est fermée : elle est dite, et rien d'autre."""
    return f"{ticker} n'est pas un titre de la base. Titres disponibles : {connus}."


def titre_sans_prix(ticker: str) -> str:
    return (
        f"{ticker} n'a aucun historique de prix dans la base. Il ne peut être "
        "ni valorisé ni analysé."
    )


AUCUNE_POSITION = (
    "Aucune position soumise. Un portefeuille sans ligne n'a pas de risque à mesurer."
)


def trop_de_positions(soumises: int, maximum: int) -> str:
    """`maximum` est le nombre de titres de la base : une borne dérivée, pas
    choisie, puisqu'un titre ne figure qu'une fois dans un portefeuille."""
    return (
        f"{typography.counted(soumises, 'position soumise', 'positions soumises')}, "
        f"et la base compte {typography.counted(maximum, 'titre')}. "
        "Un portefeuille a une ligne par titre au plus."
    )


def lignes_refusees(nombre: int) -> str:
    """L'en-tête d'un refus de plusieurs lignes d'une saisie ; un refus unique
    est repris tel quel."""
    return (
        f"{typography.counted(nombre, 'ligne refusée', 'lignes refusées')} : "
        "le portefeuille n'a pas été analysé."
    )


def lignes_du_fichier_refusees(nombre: int) -> str:
    """Le même en-tête pour un fichier : le serveur l'a lu, il n'en rend rien."""
    return (
        f"{typography.counted(nombre, 'ligne refusée', 'lignes refusées')} : "
        "le fichier n'a pas été retenu."
    )


# ═════════════════════════════════════════════════════ Ce que le serveur refuse ══


def corps_trop_volumineux(maximum: int) -> str:
    return f"Requête trop volumineuse : maximum {typography.counted(maximum, 'octet')}."


def limite_atteinte(maximum: int, minutes: int) -> str:
    return (
        f"Trop de demandes depuis cette adresse : au plus {typography.thousands(maximum)} "
        f"par période de {typography.counted(minutes, 'minute')}. Réessayer plus tard."
    )


SERVEUR_OCCUPE = "Le serveur calcule déjà d'autres analyses. Réessayer dans un instant."

ANALYSE_IMPOSSIBLE = "Ce portefeuille ne peut pas être analysé sur la base du serveur."

ERREUR_INTERNE = "Le serveur n'a pas pu faire ce calcul."

ROUTE_INCONNUE = "Aucune route à cette adresse."

METHODE_REFUSEE = "Cette route n'accepte pas cette méthode."

ORIGINE_REFUSEE = "Cette origine n'est pas autorisée à appeler ce serveur."
