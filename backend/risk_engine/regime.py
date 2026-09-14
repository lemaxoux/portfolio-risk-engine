"""Comparaison régime calme / régime de crise. Fonctions pures.

C'est le résultat central de l'enchaînement Phase 4 → Phase 5 : le beta estimé en
régime calme, qui sert à la gestion courante, prédit-il la perte réellement subie
quand la crise arrive ?

Trois grandeurs, de natures différentes, à ne pas confondre.

* **Le ratio d'amplification réalisé** — `ln(1 + R_p) / ln(1 + R_b)`. Un RAPPORT
  de deux rendements cumulés : pas de régression, pas de résidu, pas d'erreur
  type. Il n'est délibérément pas appelé « beta de crise » : ce nom laisserait
  croire à une estimation qui n'a pas eu lieu, avec une précision qu'il n'a pas.
  Il répond à « de combien le portefeuille a-t-il amplifié le mouvement du marché,
  au final ? ».
* **Le beta régressé dans la fenêtre** — la pente de la régression des rendements
  quotidiens du portefeuille sur ceux du benchmark, avec son R², son erreur type
  et son nombre d'observations. Il répond à « jour après jour, comment le
  portefeuille a-t-il co-bougé avec le marché ? ».
* **La prédiction du beta calme** — `exp(β_calme · ln(1 + R_b)) − 1`, confrontée à
  la perte réelle. L'écart entre les deux est le livrable.

POURQUOI EN LOG — on met à l'échelle un rendement multi-périodes. Les rendements
log s'additionnent dans le temps (bloc 4A) ; multiplier un rendement log cumulé
par une sensibilité est cohérent, multiplier un rendement simple cumulé ne l'est
pas. Sur −50 %, la différence est nette : une sensibilité de 0,5 donne −29,3 % en
log contre −25 % en linéaire.

POURQUOI LE RATIO ET LE BETA PEUVENT DIVERGER — et pourquoi ce n'est pas une
anomalie à masquer. La régression mesure la co-variation des rendements
quotidiens autour de leurs moyennes : une dérive propre au portefeuille pendant
l'épisode (un titre qui monte régulièrement pendant que le marché baisse) ne
change pas la pente, mais elle change le rendement cumulé, donc le ratio. Un
portefeuille qui suit le marché au jour le jour tout en perdant moins que lui
au total affiche un beta proche de 1 et un ratio inférieur à 1. L'écart dit
qu'une partie du résultat vient d'autre chose que de la sensibilité au marché.
"""

from __future__ import annotations

import math

# En dessous de ce seuil, `ln(1 + R_b)` est trop proche de zéro pour qu'un rapport
# ait un sens : le dénominateur ne mesure plus un mouvement de marché mais du bruit.
# Un scénario de stress étant par définition un mouvement ample, le cas ne se
# présente pas sur le catalogue ; le garde-fou évite une division qui rendrait un
# nombre arbitrairement grand avec l'apparence d'un résultat.
MIN_BENCHMARK_LOG_MOVE = 1e-9


def log_return(simple_return: float) -> float:
    """`ln(1 + R)`. Lève si la perte atteint ou dépasse 100 %."""
    if simple_return <= -1.0:
        raise ValueError(
            f"Rendement de {simple_return:.2%} : une perte totale n'a pas de "
            "rendement log défini."
        )
    return math.log1p(simple_return)


def amplification_ratio(
    portfolio_return: float, benchmark_return: float
) -> float | None:
    """Ratio d'amplification réalisé : `ln(1 + R_p) / ln(1 + R_b)`.

    Un rapport de deux nombres, pas un beta. 1 signifie que le portefeuille a
    suivi le marché ; 0,7, qu'il a amorti 30 % du mouvement en log ; une valeur
    négative, qu'il a évolué en sens inverse.

    Rend None quand le benchmark n'a quasiment pas bougé : le rapport n'aurait
    alors pas de sens.
    """
    denominateur = log_return(benchmark_return)
    if abs(denominateur) < MIN_BENCHMARK_LOG_MOVE:
        return None
    return log_return(portfolio_return) / denominateur


def beta_implied_return(beta: float, benchmark_return: float) -> float:
    """Rendement que prédirait un beta face au mouvement du benchmark.

    `exp(β · ln(1 + R_b)) − 1`. Hypothèse implicite, et c'est précisément ce que
    la comparaison met à l'épreuve : que la sensibilité mesurée en régime calme
    reste valable pendant la crise, et que le portefeuille n'ait aucune dérive
    propre pendant l'épisode.
    """
    return math.expm1(beta * log_return(benchmark_return))
