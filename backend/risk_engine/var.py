"""VaR, Expected Shortfall et Monte Carlo. Fonctions pures.

CONVENTION DE SIGNE — toutes les valeurs de ce module sont des PERTES
POSITIVES. Une VaR 95 % de 0,021 se lit « une perte d'au moins 2,1 % est
attendue une séance sur vingt ».

Ce choix est fixé une fois pour toutes parce que l'alternative — rendre le
rendement négatif du quantile — coexiste dans la littérature et dans les
bibliothèques, et que mélanger les deux est la source classique des bugs de
signe : les deux conventions produisent des nombres plausibles, comparables, et
qui ne se contredisent que dans les inégalités (VaR 99 % « supérieure » à la
VaR 95 % change de sens selon la convention). Une valeur NÉGATIVE rendue par ce
module signifie donc un gain à ce niveau de confiance, pas une erreur.

Toutes les VaR sont à horizon UNE SÉANCE et exprimées en fraction de la valeur
du portefeuille.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import DDOF, MONTE_CARLO_SEED, MONTE_CARLO_SIMULATIONS
from .covariance import _aligned_weights, is_positive_definite

# Méthode d'interpolation du quantile empirique.
#
# "lower" rend une STATISTIQUE D'ORDRE OBSERVÉE : la valeur est un rendement qui
# a réellement eu lieu, pas une moyenne entre deux séances voisines. Deux
# conséquences voulues — la perte annoncée est défendable (« ce jour-là, voilà
# ce qui s'est passé ») et l'estimation est conservatrice, puisqu'on prend
# l'observation la plus basse des deux qui encadrent le quantile.
#
# L'interpolation linéaire (défaut de numpy) est tout aussi standard et
# légèrement moins bruitée sur petits échantillons. Ce qui compte est que le
# choix soit explicite : laissé implicite, il change silencieusement selon la
# bibliothèque appelée.
QUANTILE_METHOD = "lower"


@dataclass(frozen=True)
class TailEstimate:
    """Expected Shortfall et la taille de queue qui le soutient.

    `tail_observations` fait partie du résultat, pas du journal : à 99 % sur une
    fenêtre de 504 séances, la moyenne porte sur environ 5 points. Le chiffre
    reste calculable mais devient une estimation fragile, d'une façon que le
    même calcul à 95 % — une trentaine de points — n'est pas. Cette fragilité
    doit être lisible dans la sortie, au même titre que la fenêtre ou la date de
    valorisation.
    """

    value: float
    threshold: float
    tail_observations: int
    observations: int


@dataclass(frozen=True)
class MonteCarloEstimate:
    value: float
    simulations: int
    seed: int


def _alpha(confidence: float) -> float:
    if not 0.0 < confidence < 1.0:
        raise ValueError(
            f"Le niveau de confiance doit être strictement entre 0 et 1 "
            f"(reçu : {confidence}). Pour 95 %, passer 0.95."
        )
    return 1.0 - confidence


def _as_array(returns) -> np.ndarray:
    tableau = np.asarray(
        returns.to_numpy() if isinstance(returns, pd.Series) else returns,
        dtype=float,
    )
    if tableau.size == 0:
        raise ValueError("Série de rendements vide.")
    if np.isnan(tableau).any():
        raise ValueError("La série contient des NaN : aligner avant de mesurer.")
    return tableau


# ------------------------------------------------------------ VaR historique --


def historical_var(
    returns,
    confidence: float = 0.95,
    method: str = QUANTILE_METHOD,
) -> float:
    """Quantile empirique des rendements, rendu en perte positive.

    Aucune hypothèse de distribution : c'est sa force — les queues épaisses et
    l'asymétrie réellement observées sont dedans — et sa limite, puisqu'elle ne
    peut rien dire d'un choc plus violent que le pire de la fenêtre.

    Voir `QUANTILE_METHOD` pour le choix d'interpolation.
    """
    tableau = _as_array(returns)
    quantile = float(np.quantile(tableau, _alpha(confidence), method=method))
    return -quantile


# ---------------------------------------------------------- VaR paramétrique --


def parametric_var(
    sigma_daily: float,
    confidence: float = 0.95,
    mean_daily: float = 0.0,
) -> float:
    """`VaR = −(μ + z_α·σ)`, hypothèse de rendements normaux.

    `z_α` vient de `scipy.stats.norm.ppf`, jamais d'une table codée en dur : un
    −1,645 écrit dans le code devient faux dès qu'on change de niveau de
    confiance, et personne ne le remarque.

    POURQUOI μ = 0 PAR DÉFAUT — sur 504 séances, l'erreur type de la moyenne
    vaut σ/√504 ≈ σ/22. La dérive estimée est donc du même ordre de grandeur que
    l'incertitude sur son estimation : on ne mesure pas une tendance, on mesure
    le bruit qui l'entoure. À un horizon d'une séance, ce terme pèse de toute
    façon environ 1/22 de σ dans le résultat, soit beaucoup moins que l'erreur
    qu'il introduit. L'exclure est le choix conservateur et le plus honnête.

    `mean_daily` reste disponible pour qui veut l'inclure — utile à des horizons
    plus longs, où la dérive croît en T tandis que la volatilité ne croît qu'en
    √T et finit par être dominée.
    """
    if sigma_daily < 0.0:
        raise ValueError(f"Volatilité négative : {sigma_daily}")
    z = float(norm.ppf(_alpha(confidence)))
    return -(mean_daily + z * sigma_daily)


# ---------------------------------------------------- Expected Shortfall --


def expected_shortfall(
    returns,
    confidence: float = 0.95,
    method: str = QUANTILE_METHOD,
) -> TailEstimate:
    """Perte moyenne au-delà du quantile de VaR, rendue en perte positive.

    Là où la VaR dit « on ne perdra pas plus que X dans 95 % des cas » sans rien
    dire du 5 % restant, le CVaR répond « et quand ça arrive, on perd Y en
    moyenne ». C'est la raison pour laquelle la réglementation (Bâle, FRTB) a
    migré du VaR vers l'Expected Shortfall : deux portefeuilles peuvent afficher
    la même VaR avec des queues radicalement différentes.

    `CVaR ≥ VaR` toujours, par construction : la moyenne de valeurs toutes
    inférieures ou égales au seuil ne peut pas dépasser ce seuil.
    """
    tableau = _as_array(returns)
    seuil = float(np.quantile(tableau, _alpha(confidence), method=method))
    queue = tableau[tableau <= seuil]

    if queue.size == 0:
        # Impossible avec method="lower", qui rend toujours une observation ;
        # garde-fou si une autre méthode d'interpolation est passée.
        raise ValueError(
            f"Aucune observation au niveau de confiance {confidence:.0%} : "
            "queue vide, l'Expected Shortfall n'est pas estimable."
        )

    return TailEstimate(
        value=float(-queue.mean()),
        threshold=seuil,
        tail_observations=int(queue.size),
        observations=int(tableau.size),
    )


# ------------------------------------------------------------- Monte Carlo --


def monte_carlo_var(
    weights: Mapping[str, float],
    cov: pd.DataFrame,
    confidence: float = 0.95,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
    mean_daily: float = 0.0,
    method: str = QUANTILE_METHOD,
) -> MonteCarloEstimate:
    """VaR par simulation de rendements normaux corrélés.

    La matrice de covariance est décomposée par Cholesky (`Σ = L·Lᵀ`) ; des
    tirages normaux indépendants multipliés par `L` acquièrent exactement la
    structure de corrélation estimée.

    GRAINE FIXE par défaut : un chiffre de risque qui change à chaque exécution
    ne peut ni être audité, ni être comparé à celui de la veille.

    Sous hypothèse de normalité, cette VaR converge vers la VaR paramétrique
    quand le nombre de tirages augmente. Ce n'est pas une redondance mais une
    vérification croisée : deux implémentations indépendantes de la même
    hypothèse doivent se rejoindre, et un écart persistant signale une erreur
    dans l'une des deux.
    """
    if simulations < 2:
        raise ValueError(f"Au moins 2 simulations (reçu : {simulations}).")

    vecteur, sous_matrice = _aligned_weights(weights, cov)
    matrice = sous_matrice.to_numpy()

    _SINGULIERE = (
        "Matrice de covariance non définie positive : la décomposition de "
        "Cholesky ne donnerait pas un facteur exploitable. Causes habituelles — "
        "deux titres parfaitement corrélés (une ligne en double dans le "
        "portefeuille), un titre à variance nulle, ou moins de séances que de "
        "titres dans la fenêtre. Vérifier le panel avant de simuler."
    )

    # Vérification AVANT le Cholesky, et non par capture de son exception : sur
    # une matrice exactement singulière, numpy ne lève pas. Il rend un facteur
    # dégénéré (zéro sur la diagonale) avec lequel la simulation tournerait en
    # silence sur une distribution de rang déficient.
    if not is_positive_definite(sous_matrice):
        raise ValueError(_SINGULIERE)

    try:
        cholesky = np.linalg.cholesky(matrice)
    except np.linalg.LinAlgError as exc:
        raise ValueError(_SINGULIERE) from exc

    generateur = np.random.default_rng(seed)
    tirages = generateur.standard_normal((simulations, matrice.shape[0]))
    rendements_titres = tirages @ cholesky.T
    rendements_portefeuille = rendements_titres @ vecteur + mean_daily

    quantile = float(np.quantile(rendements_portefeuille, _alpha(confidence), method=method))
    return MonteCarloEstimate(
        value=-quantile, simulations=simulations, seed=seed
    )


def annualise_daily_loss(daily_loss: float, horizon_days: int) -> float:
    """Met une perte quotidienne à l'échelle d'un horizon, en `√T`.

    Même hypothèse i.i.d. que la volatilité annualisée du bloc 4A, avec la même
    limite : le regroupement de volatilité fait que les grandes pertes se
    suivent, donc que la règle du √T sous-estime le risque multi-jours en
    période agitée. À utiliser en connaissance de cause.
    """
    if horizon_days < 1:
        raise ValueError(f"Horizon en séances ≥ 1 attendu (reçu : {horizon_days}).")
    return daily_loss * math.sqrt(horizon_days)
