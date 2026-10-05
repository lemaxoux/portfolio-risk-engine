"""Constantes et hypothèses du moteur de risque.

Tout paramètre qui change un chiffre de risque vit ici, nommé et documenté,
plutôt qu'écrit en dur au milieu d'un calcul. Un lecteur doit pouvoir auditer
les hypothèses sans lire le code.
"""

from __future__ import annotations

import math
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

# Nombre de séances par mois, 252 / 12. Il ne sert qu'à DIRE une durée en mois
# (`engine.period_label`) : aucun chiffre de risque n'en dépend.
TRADING_DAYS_PER_MONTH = 21

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

# ------------------------------------------------------------------ Devise --
#
# Devise de TOUS les prix en base, donc de toutes les valeurs de portefeuille.
#
# HYPOTHÈSE DU PÉRIMÈTRE v1, pas une donnée lue : l'univers ne contient que des
# titres cotés aux États-Unis, et Tiingo rend leurs cours en dollars
# américains sans publier la devise ligne à ligne. Aucune conversion n'est
# faite nulle part — un titre coté dans une autre devise ferait de cette
# constante un mensonge, et devrait entrer avec sa propre devise.
#
# Publiée sous son code ISO 4217 et non sous un symbole : à Montréal, « $ »
# sans qualificatif se lit dollar canadien. Une valeur de portefeuille écrite
# « 83 185,85 $ » y serait fausse de 30 % sans que rien ne le signale.
PRICE_CURRENCY = "USD"

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

# ----------------------------------- Séances minimales d'une mesure de queue --
#
# SEUIL DÉMONTRÉ, pas choisi : comme `MIN_ESTIMABLE_OBSERVATIONS`, il se lit dans
# la définition de l'estimateur.
#
# La VaR historique au niveau α est le quantile empirique à 1 − α : le seuil
# sous lequel tombe la part 1 − α des séances de la fenêtre. Sur n séances,
# cette queue en compte n·(1 − α). Sous une, AUCUNE séance n'y tombe, et le
# quantile « lower » rend le pire rendement de la fenêtre, quel que soit α :
# sur 7 séances, la VaR 95 % et la VaR 99 % valaient toutes deux le même
# minimum, 0,50 %, et la page lisait « une séance sur cent » sous un chiffre
# qui n'était que le pire de sept jours. Ce n'est plus la mesure annoncée. La
# CVaR du même niveau, qui moyenne cette queue, se réduisait au même minimum.
#
# D'où n ≥ 1/(1 − α) : 20 séances à 95 %, 100 à 99 %. En deçà, les deux sont
# refusées, avec leur raison. Déclaré comme seuil DÉRIVÉ dans
# `rules.thresholds.historical_var_sample`.
def historical_var_min_observations(confidence: float) -> int:
    """Séances minimales d'une VaR ou d'une CVaR historique : 1/(1 − α)."""
    if not 0.0 < confidence < 1.0:
        raise ValueError(
            f"Le niveau de confiance doit être strictement entre 0 et 1 "
            f"(reçu : {confidence})."
        )
    # `round` d'abord : 1 − 0,9 vaut 0,09999999999999998 en flottant, si bien que
    # 1/(1 − 0,9) dépasse 10 d'un rien, que le plafond porterait à 11.
    return math.ceil(round(1.0 / (1.0 - confidence), 9))

# ------------------------------------------ ν maximal d'une loi de Student --
#
# Au-delà de ν = 30, l'ajustement d'une loi de Student est REFUSÉ, avec sa
# raison : elle ne se distingue plus de la normale sur la fenêtre. SEUIL CHOISI
# À LA MAIN, le quatrième du projet, déclaré comme tel dans
# `rules.thresholds.STUDENT_NU_CEILING`.
#
# ── Le défaut qu'il corrige ──
#
# La normale est la limite de la Student quand ν tend vers l'infini. Sur des
# rendements sans queue épaisse, le maximum de vraisemblance pousse donc ν
# vers l'infini, et l'optimiseur s'arrête où il peut. Sur la base réelle, un
# titre seul sur une fenêtre courte : PG sur 60 séances rendait ν = 6 × 10¹⁵,
# CVX, PFE et SPY sur 60 à 120 séances de 10¹³ à 10¹⁴. La provenance de la VaR
# Student publiait ce nombre (DESIGN.md §9.1 : jamais un nombre astronomique),
# et au-delà de 10²⁷ son écriture faisait tomber l'analyse.
#
# ── Pourquoi 30 ──
#
# À variance égale, la VaR Student s'écarte de la VaR normale de +2,05 % à
# 99 % et de −0,31 % à 95 % pour ν = 30, en relatif, et de moins encore
# au-delà : 2,05 % au plus à 99 %, 0,31 % au plus à 95 %. C'est bien en deçà
# de l'erreur d'estimation elle-même : l'erreur type relative d'un écart-type
# d'échantillon vaut environ 1/√(2n) — 9 % sur 60 séances, 3,2 % encore sur
# 504. Ce chiffre est calculé SOUS NORMALITÉ ; avec des queues épaisses,
# l'erreur est plus grande encore, si bien que l'argument est prudent. Un ν
# au-delà de 30 ne dit rien que la normale ne dise déjà ; le publier ferait
# passer un nombre sans signification pour une mesure de la queue.
# `tests/test_student.py` vérifie ces écarts.
#
# ── Pourquoi un refus, et non un plafond ──
#
# Borner ν à 30 dans l'optimiseur publierait « ν = 30 » comme s'il avait été
# estimé : la borne deviendrait une mesure. Le refus garde l'estimateur
# honnête — `var.fit_student_t` rend toujours son maximum — et c'est le
# moteur (`engine.student_fit`) qui décide de ne pas s'en servir.
MAX_STUDENT_NU = 30.0

# ----------------------------------- Séances minimales pour estimer une loi --
#
# Sous 30 séances, deux décisions du moteur, sur le même nombre :
#
#   * la loi de Student n'est pas ajustée (`var.fit_student_t` refuse, et
#     `engine._raison_student` dit pourquoi en clair) : son maximum de
#     vraisemblance repose sur la queue, et trente séances n'en comptent
#     qu'une ou deux au-delà du quantile à 95 % ;
#   * la volatilité et la VaR paramétrique normale restent PUBLIÉES, mais
#     marquées comme estimation mince (`caveat`). Elles bougent avec les
#     données, elles ne sont donc pas refusées (README, « Où s'arrête le
#     refus ») ; mais sous normalité, l'écart-type d'échantillon qui les porte
#     varie d'environ 1/√(2n) d'une fenêtre à l'autre — 13 % sur 30 séances,
#     27 % sur 7. Le moteur de règles n'en tire aucune conclusion.
#
# SEUIL CHOISI À LA MAIN, le cinquième du projet, déclaré comme tel dans
# `rules.thresholds.MIN_DISTRIBUTION_SAMPLE` : trente est la convention
# usuelle du « grand échantillon », aucun calcul ne la produit.
MIN_DISTRIBUTION_OBSERVATIONS = 30

# ------------------------------------------- Couverture minimale d'un scénario --
#
# Sous 80 % de la valeur couverte, un scénario ne donne pas de chiffre
# principal : la partie rejouée est minoritaire dans la valeur. SEUIL CHOISI À
# LA MAIN, le deuxième du projet, déclaré avec sa justification dans
# `rules.thresholds.MIN_SCENARIO_COVERAGE`. La constante vit ici pour que le
# moteur publie le verdict avec chaque scénario
# (`ScenarioCoverage.sufficient`) : une phrase de lecture ne doit pas citer
# comme la perte du portefeuille ce que le moteur de règles refuse d'en dire.
MIN_SCENARIO_COVERAGE_SHARE = 0.80

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
