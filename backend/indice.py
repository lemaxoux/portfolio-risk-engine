"""L'indice de référence : son ticker, et ce qu'il suit.

Un module de données pur, sans import : ni entrée-sortie, ni dépendance. Le
moteur y lit le ticker de l'indice du beta, et les textes français le nom qui
se dit dans une phrase.

POURQUOI HORS DE L'INGESTION. Ces deux constantes vivaient dans
`backend/ingestion/universe.py`, déclarées avec l'univers de développement.
Les lire là chargeait le paquet `backend.ingestion`, donc le rattrapage des
prix, donc le fournisseur et sa bibliothèque réseau : quiconque importait le
moteur importait de quoi appeler le fournisseur. Le serveur public
(`backend/public_api/`) n'a le droit ni à l'un ni à l'autre, et
`tests/test_serveur_public_frontiere.py` le tient.

`backend/ingestion/universe.py` les réexporte : l'ingestion et les tests les
lisent encore à côté de l'univers.
"""

from __future__ import annotations

# Benchmark utilisé pour le beta du portefeuille (Phase 4).
BENCHMARK_TICKER = "SPY"

# Ce que suit un indice de référence, pour les phrases de lecture : le ticker
# ne dit rien à un particulier. Le nom se place après une préposition sans
# contraction (« pour le S&P 500 ») ; la description le présente à sa première
# apparition. Un indice absent de cette table est cité par son ticker, jamais
# sous un nom deviné.
#
# SPY est le fonds coté qui réplique le S&P 500, pas l'indice lui-même. Les
# phrases disent « le S&P 500 », comme les bornes des scénarios, relevées sur
# ses clôtures ; l'écart (frais, dividendes) ne change pas la lecture.
BENCHMARK_NAMES: dict[str, tuple[str, str]] = {
    "SPY": ("le S&P 500", "l'indice de 500 grandes entreprises américaines"),
}
