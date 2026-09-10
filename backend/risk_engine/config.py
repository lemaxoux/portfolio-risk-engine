"""Constantes et hypothèses du moteur de risque.

Tout paramètre qui change un chiffre de risque vit ici, nommé et documenté,
plutôt qu'écrit en dur au milieu d'un calcul. Un lecteur doit pouvoir auditer
les hypothèses sans lire le code.
"""

from __future__ import annotations

import os
from datetime import date

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
# Taux court sans risque ANNUEL : bons du Trésor américain à 13 semaines.
#
# Source : Trésor américain, **équivalent coupon** (coupon equivalent /
# bond equivalent yield), observé le 9 septembre 2026.
#
# ── Pourquoi l'équivalent coupon et pas le taux d'escompte ──
#
# Le Trésor publie deux chiffres pour le même titre, et prendre le mauvais
# gonfle mécaniquement le Sharpe :
#
#   * le **taux d'escompte** (discount rate) rapporte la décote à la valeur
#     FACIALE du bon et compte l'année sur 360 jours. Comme on achète en
#     dessous du pair, rapporter le gain au montant nominal plutôt qu'au
#     montant réellement investi sous-estime le rendement — et l'année à 360
#     jours accentue l'écart ;
#   * l'**équivalent coupon** rapporte ce même gain au prix effectivement payé,
#     sur une base 365 jours, ce qui le rend directement comparable au
#     rendement d'une action.
#
# Retenir l'escompte donnerait un taux sans risque trop bas, donc des
# rendements excédentaires trop élevés, donc un Sharpe flatteur — sans qu'aucun
# calcul ne soit faux par ailleurs. C'est exactement le genre d'erreur qui ne
# se voit pas dans les tests.
#
# ── Pourquoi la date est écrite à côté de la valeur ──
#
# Une constante non datée devient une hypothèse invisible : personne ne peut
# dire, six mois plus tard, si elle est encore valable. Ce taux a bougé de
# 6 points de base en une semaine ; sa péremption doit être auditable, pas
# devinée. `RISK_FREE_RATE_OBSERVED_ON` voyage avec le résultat (voir
# `SharpeResult.risk_free_observed_on`).
#
# Surchargeable sans toucher au code : MX_RISK_FREE_RATE=0.035 dans .env.
DEFAULT_RISK_FREE_RATE = 0.0390
RISK_FREE_RATE_OBSERVED_ON = date(2026, 9, 9)


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


def risk_free_observation_date() -> date | None:
    """Date d'observation du taux par défaut, ou None s'il a été surchargé.

    Un taux fourni via `MX_RISK_FREE_RATE` ou passé en argument n'a pas de date
    connue du moteur : c'est à celui qui le fixe de savoir d'où il vient. Rendre
    `None` plutôt que la date du défaut évite d'attribuer à une valeur
    quelconque une provenance qu'elle n'a pas.
    """
    return None if os.getenv("MX_RISK_FREE_RATE") else RISK_FREE_RATE_OBSERVED_ON


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
