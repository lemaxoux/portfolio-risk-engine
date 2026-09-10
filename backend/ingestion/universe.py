"""Univers de titres de développement et leur secteur.

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

# Profondeur d'historique visée au backfill.
#
# ATTENTION pour la Phase 5 : 5 ans ne suffisent plus à atteindre le krach
# COVID. Depuis septembre 2026, la fenêtre démarre en septembre 2021, soit
# 18 mois APRÈS le décrochage de février-mars 2020. Elle couvre bien la baisse
# 2022, mais le scénario COVID demandera BACKFILL_YEARS = 7 (début 2019) et un
# nouveau backfill complet.
BACKFILL_YEARS = 5

# Benchmark utilisé pour le beta du portefeuille (Phase 4).
BENCHMARK_TICKER = "SPY"


def dev_tickers() -> list[str]:
    """Tickers de l'univers de développement, dans l'ordre de déclaration."""
    return list(DEV_UNIVERSE)
