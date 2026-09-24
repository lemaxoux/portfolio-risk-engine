"""Constantes et hypothèses du moteur de risque.

Tout paramètre qui change un chiffre de risque vit ici, nommé et documenté,
plutôt qu'écrit en dur au milieu d'un calcul. Un lecteur doit pouvoir auditer
les hypothèses sans lire le code.
"""

from __future__ import annotations

import os
from datetime import date

from dotenv import load_dotenv

# `universe` est un module de données pur (aucune I/O, aucune dépendance) :
# l'importer ici ne crée pas de couplage entre le moteur et l'ingestion.
from backend.ingestion.universe import BENCHMARK_TICKER

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

# ------------------------------------------------ Classes de l'histogramme --
#
# Largeur des classes de l'histogramme des rendements quotidiens : 0,25 point
# (0,0025 en fraction). PARAMÈTRE CHOISI, pas estimé — il ne change aucun
# chiffre de risque, seulement la façon de compter les séances pour les
# dessiner. Il est publié avec l'histogramme (`bin_width`).
#
# ── Pourquoi une largeur FIXE, la même pour tous les portefeuilles ──
#
# Pour la raison qui fixe à [−1, +1] le domaine de la carte de corrélation :
# deux portefeuilles doivent se lire sur la MÊME grille. Une largeur ajustée
# aux données (règle de Freedman–Diaconis, de Scott, `binX` d'Observable Plot)
# donnerait à un portefeuille calme et à un portefeuille agité des
# histogrammes de même allure, chacun étiré à sa propre dispersion —
# exactement la comparaison que l'outil existe pour permettre.
#
# ── Pourquoi 0,25 point ──
#
# * Sur le portefeuille de démonstration (σ quotidien 0,84 %, écart
#   interquartile 0,85 %, 504 séances), les deux règles usuelles encadrent
#   cette valeur : Freedman–Diaconis donne 0,21 point, Scott 0,37 point. Une
#   largeur d'usage, donc, sur un portefeuille diversifié d'actions.
# * Environ trois classes et demie par écart-type : assez pour que la forme de
#   la queue se voie, assez peu pour que la classe centrale compte une
#   trentaine de séances et pas trois.
# * Quatre classes par point de pourcentage : les bornes tombent sur des
#   valeurs rondes (0,25 %, 0,5 %, 0,75 %), lisibles sur l'axe sans décimale
#   inventée. Et les VaR 95 % et 99 % usuelles (1 à 2 %) se situent à quatre à
#   huit classes de zéro : la queue au-delà du quantile en occupe plusieurs.
#
# Sur un titre seul et agité (σ quotidien de 2,5 %), la même largeur donne un
# histogramme plus étalé et plus plat. C'est voulu : c'est ce qui le
# distingue, à l'œil, d'un portefeuille diversifié.
HISTOGRAM_BIN_WIDTH = 0.0025

# ------------------------------------------------------ Degrés de liberté --
#
# UNE SEULE convention pour TOUTE estimation de dispersion du moteur :
# écart-type, variance, covariance, beta. `ddof=1`, estimateur d'échantillon.
#
# Cette constante existe parce que numpy n'est pas cohérent avec lui-même :
# `np.cov` utilise ddof=1 par défaut, `np.std` et `np.var` utilisent ddof=0.
# Mélanger les deux casse une identité algébrique dont dépend tout le bloc
# multi-titres : √(wᵀΣw) doit retomber EXACTEMENT sur la volatilité de la série
# de rendements du portefeuille, puisque c'est la même quantité calculée de deux
# façons.
#
# L'écart qu'introduirait une incohérence vaut N/(N−1), soit 0,1 % sur 504
# séances : assez petit pour passer pour un arrondi, assez réel pour être une
# incohérence qu'on ne retrouverait jamais. D'où la constante partagée plutôt
# qu'un défaut répété à chaque appel — et un test qui verrouille l'identité.
DDOF = 1

# ------------------------------------------- Taille minimale d'une régression --
#
# En dessous de 60 séances (≈ 3 mois), un beta régressé est signalé comme reposant
# sur un échantillon trop mince. Seuil de convention, pas loi statistique : son
# rôle est d'empêcher qu'un beta estimé sur les 23 rendements du krach COVID soit
# présenté avec la même apparence de solidité qu'un beta sur 355 séances. Sur une
# fenêtre aussi courte, quelques jours extrêmes dictent la pente à eux seuls.
# L'erreur type, portée par chaque beta, chiffre l'incertitude quel que soit le
# seuil.
MIN_REGRESSION_OBSERVATIONS = 60

# ------------------------------------- Taille minimale d'une ESTIMATION --
#
# En deçà de trois observations, corrélation, beta et contributions à la variance
# cessent d'être des estimations. Ce n'est pas une convention comme
# `MIN_REGRESSION_OBSERVATIONS` : c'est de l'algèbre, et c'est le seul seuil du
# projet qui se démontre.
#
# CE QUI EST VRAI DES TROIS — à deux observations, le centrage ne laisse qu'une
# SEULE direction. Les deux écarts à la moyenne valent ±δ/2, où δ est la
# différence entre les deux rendements : tout ce qui se calcule sur l'échantillon
# centré est une fonction de ce seul δ, et ne porte donc aucune information que δ
# ne porte déjà.
#
# CE QUI EST PROPRE À CHACUNE — elles dégénèrent sous le même seuil, pas de la
# même façon, et il ne faut pas leur prêter la même raison :
#
#   * corrélation — deux points centrés sont colinéaires, donc |ρ| = 1 par
#     construction, quelles que soient les données ;
#   * beta — une régression avec constante a n − 2 degrés de liberté RÉSIDUELS ;
#     à deux points il n'en reste aucun, la droite passe exactement par eux et la
#     pente n'a pas d'erreur type. Elle ne vaut PAS ±1 pour autant : elle vaut
#     n'importe quoi, ce qui ne la rend pas plus estimée. C'est déjà écrit
#     ailleurs — `covariance.Beta.standard_error` est documenté « None en dessous
#     de trois observations, où elle n'est pas définie » ;
#   * contributions à la variance — il n'y a ici aucune régression. Une covariance
#     d'échantillon sur n observations est de rang au plus n − 1, le centrage
#     retirant une dimension : à n = 2 elle est de rang 1, Σ ∝ δδᵀ, et
#     `cᵢ = wᵢδᵢ / (wᵀδ)` est la part de chaque ligne dans cette seule différence
#     journalière. Vérifié à 1e-16 près.
#
# La singularité de Σ quand n ≤ k (nombre de lignes) ne produit PAS de seconde
# rupture, contrairement à ce qu'on pourrait craindre : les contributions n'ont
# besoin que de `wᵀΣw > 0`, jamais d'une inverse, et chaque covariance qui les
# compose garde ses n − 1 degrés de liberté. Mesuré sur un modèle à un facteur à
# 7 lignes, 3 000 tirages, contre une vérité connue — l'erreur absolue médiane
# passe de 0,034 à n = 7 (Σ singulière) à 0,031 à n = 8 (Σ inversible), sans
# rupture, là où elle vaut 0,122 à n = 2 contre 0,069 à n = 3.
MIN_ESTIMABLE_OBSERVATIONS = 3

# ------------------------------------------------------------ Monte Carlo --
#
# Graine fixe : un chiffre de risque qui change à chaque exécution n'est pas
# auditable et ne peut pas servir de référence d'un jour sur l'autre.
MONTE_CARLO_SEED = 20260910
MONTE_CARLO_SIMULATIONS = 100_000

# ------------------------------------------------------------- Benchmark --
#
# Indice de référence du beta, repris de l'univers d'ingestion plutôt que
# redéclaré : deux constantes pour un même ticker finiraient par diverger.
DEFAULT_BENCHMARK = BENCHMARK_TICKER

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
