"""Constantes et hypothèses du moteur de risque.

Tout paramètre qui change un chiffre de risque vit ici, nommé et documenté,
plutôt qu'écrit en dur au milieu d'un calcul. Un lecteur doit pouvoir auditer
les hypothèses sans lire le code.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Nombre de séances par an. Convention de place (≈252 jours ouvrés hors
# fériés), utilisée pour toutes les annualisations.
TRADING_DAYS_PER_YEAR = 252

# Fenêtre d'estimation par défaut, en séances : 504 ≈ 2 ans.
#
# La base remonte à 2005, mais cet historique sert au REJEU DE SCÉNARIOS
# (Phase 5), pas à l'estimation courante. Une volatilité ou une VaR estimées
# sur 21 ans seraient dominées par 2008 et décriraient un régime de marché
# révolu. Deux ans est un compromis courant : assez d'observations pour que
# l'estimateur soit stable, assez court pour rester représentatif du régime
# actuel.
DEFAULT_WINDOW = 504

# Facteur de décroissance EWMA, convention RiskMetrics pour le quotidien.
# λ = 0,94 donne une demi-vie d'environ 11 séances : la volatilité réagit vite
# à un choc, là où l'écart-type sur fenêtre fixe met des mois à l'intégrer.
EWMA_LAMBDA = 0.94

# --------------------------------------------------------- Taux sans risque --
#
# ATTENTION — hypothèse statique à revoir.
#
# Proxy du taux court sans risque (bon du Trésor US 3 mois), exprimé en taux
# ANNUEL. Il n'est pas récupéré d'une source de marché : le fournisseur de
# données du projet ne sert que des actions et des ETF. C'est donc une valeur
# à ajuster à la main quand le régime de taux change, sous peine de fausser
# Sharpe et Sortino — un taux sans risque périmé de 200 points de base déplace
# un Sharpe de façon parfaitement silencieuse.
#
# Surchargeable sans toucher au code : MX_RISK_FREE_RATE=0.035 dans .env.
DEFAULT_RISK_FREE_RATE = 0.04


def risk_free_rate() -> float:
    """Taux sans risque annuel retenu (voir `DEFAULT_RISK_FREE_RATE`)."""
    brut = os.getenv("MX_RISK_FREE_RATE")
    if brut is None:
        return DEFAULT_RISK_FREE_RATE
    try:
        return float(brut)
    except ValueError as exc:
        raise ValueError(
            f"MX_RISK_FREE_RATE doit être un nombre décimal (reçu : {brut!r}). "
            "Exemple pour 3,5 % : MX_RISK_FREE_RATE=0.035"
        ) from exc


def daily_risk_free_rate(annual_rate: float | None = None) -> float:
    """Convertit un taux annuel en taux quotidien équivalent.

    Conversion géométrique — `(1 + annuel)^(1/252) − 1` — et non `annuel/252`.
    Les rendements manipulés par le moteur sont des rendements simples, qui se
    composent ; la division naïve ignore cette composition et surestime
    légèrement le taux quotidien, donc sous-estime les rendements excédentaires.
    L'écart est faible mais gratuit à éviter.
    """
    taux = risk_free_rate() if annual_rate is None else annual_rate
    return (1.0 + taux) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0
