"""Univers de titres de développement, secteurs, et profondeur d'historique.

Le secteur est saisi à la main : Tiingo ne l'expose pas (l'endpoint de
métadonnées renvoie `name` et `exchangeCode`, pas de secteur), et aucun des
fournisseurs gratuits évalués ne le fait. La nomenclature suivie est celle des
secteurs GICS, au niveau le plus large.

Cette table n'est qu'un jeu de départ pour développer et tester. Un titre
ajouté à la demande par un utilisateur entre en base avec `sector` à NULL : le
flag de concentration sectorielle (Phase 6) doit donc traiter le cas NULL, pas
supposer la colonne renseignée.
"""

from __future__ import annotations

from datetime import date

# L'indice de référence est déclaré dans `backend/indice.py`, que le moteur lit
# sans charger l'ingestion. Il est réexporté ici, à côté de l'univers : c'est
# là que l'ingestion et les tests le lisent.
from backend.indice import BENCHMARK_NAMES, BENCHMARK_TICKER

__all__ = [
    "BACKFILL_START",
    "BENCHMARK_NAMES",
    "BENCHMARK_TICKER",
    "DEV_UNIVERSE",
    "dev_tickers",
]

# Ordre volontairement conservé tel que défini : lisible et facile à relire
# ligne à ligne, alors qu'un tri par secteur masquerait les oublis.
DEV_UNIVERSE: dict[str, str | None] = {
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "GOOGL": "Communication Services",
    "AMZN": "Consumer Discretionary",
    "NVDA": "Information Technology",
    "JPM": "Financials",
    "BAC": "Financials",
    "JNJ": "Health Care",
    "PFE": "Health Care",
    "XOM": "Energy",
    "CVX": "Energy",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    # SPY réplique le S&P 500 : il n'a pas de secteur propre, il les contient
    # tous. Lui en attribuer un fausserait le calcul de concentration.
    "SPY": None,
}

# Date d'ancrage du backfill — fixe, délibérément, et non un nombre d'années
# glissant.
#
# Une fenêtre glissante cesse silencieusement de couvrir un événement à mesure
# que le temps passe : « 5 ans » couvrait le krach COVID jusqu'en mars 2025,
# puis a cessé de le faire sans que rien ne change dans le code ni n'échoue.
# Le scénario de stress disparaît en douce, et le jour où on s'en aperçoit,
# c'est en lisant des résultats qui ne veulent plus dire ce qu'on croit.
#
# Une date d'ancrage n'a pas ce défaut : la couverture ne peut que s'étendre.
# 2005 fait entrer la crise financière de 2008 aux côtés du COVID (2020) et de
# la baisse 2022, avec trois ans de contexte avant 2008.
#
# Les titres dont la cotation commence après cette date entrent simplement avec
# l'historique qui existe : le fournisseur renvoie ce qu'il a, et `status`
# montre la couverture réelle titre par titre.
# ATTENTION (Phase 4) — cette profondeur sert au REJEU DE SCÉNARIOS, pas à
# l'estimation du risque courant.
#
# Une VaR historique ou une volatilité annualisée calculées sur les 21 ans
# complets seraient dominées par 2008 : elles décriraient un régime de marché
# révolu, pas le risque d'aujourd'hui. Le moteur de risque doit estimer sur une
# fenêtre récente (1 à 2 ans) ou pondérer les rendements exponentiellement
# (EWMA, façon RiskMetrics). L'historique long n'est là que pour rejouer des
# périodes de crise identifiées sur les poids actuels du portefeuille.
BACKFILL_START = date.fromisoformat("2005-01-01")


def dev_tickers() -> list[str]:
    """Tickers de l'univers de développement, dans l'ordre de déclaration."""
    return list(DEV_UNIVERSE)
