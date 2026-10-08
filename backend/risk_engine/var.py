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
from scipy.optimize import minimize
from scipy.stats import norm
from scipy.stats import t as student_t

from backend import typography
from backend.textes import ValeurRefusee

from .config import (
    DDOF,
    MIN_DISTRIBUTION_OBSERVATIONS,
    MONTE_CARLO_SEED,
    MONTE_CARLO_SIMULATIONS,
)
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
    fenêtre de 504 séances, la moyenne porte sur 6 séances. Le chiffre reste
    calculable mais devient une estimation fragile, d'une façon que le même
    calcul à 95 % — 26 séances — n'est pas. Le quantile « lower » est la 6e (la
    26e) plus mauvaise séance, de rang ⌊(n − 1)·(1 − α)⌋ en comptant de zéro ;
    la queue la compte avec les plus mauvaises qu'elle, hors ex æquo. Cette
    fragilité doit être lisible dans la sortie, au même titre que la fenêtre ou
    la date de valorisation.
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
    nu: float | None = None


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
            f"Aucune observation au niveau de confiance "
            f"{typography.percent(confidence, 0)} : "
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

    # Vérification AVANT le Cholesky, et non par capture de son exception : sur
    # une matrice exactement singulière, numpy ne lève pas. Il rend un facteur
    # dégénéré (zéro sur la diagonale) avec lequel la simulation tournerait en
    # silence sur une distribution de rang déficient.
    if not is_positive_definite(sous_matrice):
        raise ValeurRefusee("COVARIANCE_NON_DEFINIE_POSITIVE")

    try:
        cholesky = np.linalg.cholesky(matrice)
    except np.linalg.LinAlgError as exc:
        raise ValeurRefusee("COVARIANCE_NON_DEFINIE_POSITIVE") from exc

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


# ======================================================== Loi de Student ==
#
# POURQUOI — le Monte Carlo normal converge vers la VaR paramétrique par
# construction : il valide la décomposition de Cholesky, pas le modèle. Tirer en
# loi de Student lui donne une raison d'exister : l'écart entre les deux chiffre
# le coût de l'hypothèse de normalité.
#
# MODÈLE — Student multivariée à ν commun. Toute combinaison linéaire `w·X` d'une
# telle loi est une Student univariée de MÊME ν : la série de rendements du
# portefeuille identifie donc directement ν, et c'est justement la quantité dont
# la queue nous intéresse. Les paramètres de position et d'échelle ajustés sont
# des paramètres de nuisance : la dispersion reste ancrée sur la matrice de
# covariance empirique (convention DDOF commune), si bien qu'entre la VaR normale
# et la VaR Student seule la FORME des queues diffère.

STUDENT_FIT_STARTS = (2.5, 4.0, 8.0, 30.0)
# Le même nombre que la frontière des estimations minces : voir
# `config.MIN_DISTRIBUTION_OBSERVATIONS`.
STUDENT_MIN_OBSERVATIONS = MIN_DISTRIBUTION_OBSERVATIONS


@dataclass(frozen=True)
class StudentFit:
    """Loi de Student ajustée par maximum de vraisemblance."""

    nu: float
    loc: float
    scale: float
    log_likelihood: float
    observations: int


def fit_student_t(returns) -> StudentFit:
    """Degrés de liberté ν par MAXIMUM DE VRAISEMBLANCE.

    POURQUOI PAS LA MÉTHODE DES MOMENTS — la relation `ν = 6/κ + 4`, où κ est le
    kurtosis en excès, n'est définie que pour ν > 4 : en dessous, le kurtosis
    théorique est infini. Elle ne peut structurellement jamais rendre ν ≤ 4, or
    les rendements actions quotidiens se situent typiquement entre 3 et 6.
    L'estimateur s'effondre donc exactement là où on en a besoin — et le
    kurtosis empirique d'une série à queues épaisses est de toute façon dominé
    par une poignée d'observations.

    POURQUOI PAS `scipy.stats.t.fit` TEL QUEL — sur la série réelle d'un
    portefeuille de six titres, son optimisation par défaut s'est arrêtée à
    ν = 2,01, avec une log-vraisemblance inférieure de 13 unités au vrai maximum
    situé vers ν = 4,1. Un ν aussi proche de 2 aurait fait s'effondrer la VaR
    Student (voir `student_t_var`) pour une raison purement numérique.

    D'où l'optimisation retenue : données standardisées par médiane et écart
    absolu médian (conditionnement), ν paramétré en log — ce qui laisse
    l'optimiseur trouver ν ≤ 2 si les données l'imposent, pour que ce cas soit
    signalé et non masqué par une contrainte —, Nelder-Mead depuis plusieurs
    valeurs de départ, meilleure vraisemblance retenue.
    """
    donnees = _as_array(returns)
    if donnees.size < STUDENT_MIN_OBSERVATIONS:
        raise ValueError(
            f"Au moins {STUDENT_MIN_OBSERVATIONS} observations sont nécessaires "
            f"pour estimer ν (reçu : {donnees.size})."
        )

    centre = float(np.median(donnees))
    echelle = float(np.median(np.abs(donnees - centre))) * 1.4826
    if echelle <= 0.0:
        echelle = float(np.std(donnees, ddof=DDOF))
    if echelle <= 0.0:
        raise ValeurRefusee("SERIE_CONSTANTE")

    z = (donnees - centre) / echelle

    def log_vraisemblance_negative(parametres: np.ndarray) -> float:
        nu = math.exp(parametres[0])
        valeur = -float(
            np.sum(student_t.logpdf(z, nu, parametres[1], math.exp(parametres[2])))
        )
        return valeur if math.isfinite(valeur) else 1e300

    meilleur = None
    for nu_depart in STUDENT_FIT_STARTS:
        essai = minimize(
            log_vraisemblance_negative,
            x0=np.array([math.log(nu_depart), 0.0, 0.0]),
            method="Nelder-Mead",
            options={"maxiter": 20_000, "maxfev": 20_000, "xatol": 1e-10, "fatol": 1e-10},
        )
        if meilleur is None or essai.fun < meilleur.fun:
            meilleur = essai

    nu = math.exp(meilleur.x[0])
    loc_z, echelle_z = meilleur.x[1], math.exp(meilleur.x[2])
    return StudentFit(
        nu=nu,
        loc=centre + echelle * loc_z,
        scale=echelle * echelle_z,
        # Changement de variable : la densité de x vaut celle de z divisée par
        # l'échelle de standardisation, d'où le terme −n·ln(échelle).
        log_likelihood=-meilleur.fun - donnees.size * math.log(echelle),
        observations=int(donnees.size),
    )


def _require_finite_variance(nu: float) -> None:
    if not nu > 2.0:
        raise ValueError(
            f"Degrés de liberté ν = {typography.number(nu, 3)} ≤ 2 : la loi de "
            "Student n'a pas de variance finie. "
            "Aucune matrice d'échelle ne peut reproduire la covariance observée, "
            "et une VaR « à variance ajustée » n'a pas de sens. Vérifier d'abord "
            "l'ajustement : un ν à peine supérieur à 2 est lui-même suspect."
        )


def student_scale_matrix(cov: pd.DataFrame, nu: float) -> pd.DataFrame:
    """Matrice d'échelle `S = Σ·(ν − 2)/ν`.

    LE PIÈGE — une Student multivariée de matrice d'échelle S a pour covariance
    `S·ν/(ν − 2)`, pas S. Passer directement la covariance empirique comme
    matrice d'échelle rendrait les simulations plus volatiles que les données
    d'un facteur `√(ν/(ν − 2))` : +29 % pour ν = 5, +41 % pour ν = 4. La VaR
    ressortirait gonflée pour une raison qui n'a rien à voir avec les queues
    épaisses, et l'on attribuerait à la forme de la loi ce qui n'est qu'une
    erreur d'échelle. Avec ce S, la covariance simulée égale Σ.
    """
    _require_finite_variance(nu)
    return cov * ((nu - 2.0) / nu)


def student_t_var(
    sigma_daily: float,
    nu: float,
    confidence: float = 0.95,
    mean_daily: float = 0.0,
) -> float:
    """VaR Student à variance ajustée, en forme fermée, en perte positive.

    `VaR = −(μ + σ·√((ν − 2)/ν)·t_ν⁻¹(α))`. C'est la limite vers laquelle le
    Monte Carlo Student doit converger — même rôle de vérification croisée que
    la VaR paramétrique pour le Monte Carlo normal.

    GÉOMÉTRIE ATTENDUE — à variance égale, une loi leptokurtique a des épaules
    plus minces et des extrêmes plus lourds. Le quantile à 95 % est une épaule :
    la VaR Student y est MOINS sévère que la normale. Le quantile à 99 % est déjà
    dans la queue : elle y est PLUS sévère.

    PRÈS DE ν = 2 — l'ajustement de variance concentre la masse au centre à mesure
    que ν décroît vers 2 : les quantiles modérés s'effondrent vers zéro tandis
    que les extrêmes lointains explosent. Un ν estimé à peine au-dessus de 2
    produit ainsi des VaR 95 % et 99 % très inférieures à la normale, à rebours
    de la géométrie attendue.
    """
    _require_finite_variance(nu)
    if sigma_daily < 0.0:
        raise ValueError(f"Volatilité négative : {sigma_daily}")
    quantile = float(student_t.ppf(_alpha(confidence), nu)) * math.sqrt((nu - 2.0) / nu)
    return -(mean_daily + quantile * sigma_daily)


def simulate_student_returns(
    cov: pd.DataFrame,
    nu: float,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
) -> np.ndarray:
    """Tirages de rendements Student multivariés dont la covariance vaut `cov`.

    `X = Z·√(ν/W)` avec `Z ~ N(0, S)` et `W ~ χ²_ν` indépendants. Le même W
    multiplie toutes les composantes d'un tirage : c'est ce qui fait que les
    titres subissent ENSEMBLE les jours extrêmes, comme dans une crise réelle —
    ce qu'un tirage indépendant par titre ne reproduirait pas.
    """
    if simulations < 2:
        raise ValueError(f"Au moins 2 simulations (reçu : {simulations}).")
    echelle = student_scale_matrix(cov, nu)
    if not is_positive_definite(echelle):
        raise ValeurRefusee("SIMULATION_STUDENT_IMPOSSIBLE")
    facteur = np.linalg.cholesky(echelle.to_numpy())
    generateur = np.random.default_rng(seed)
    normaux = generateur.standard_normal((simulations, facteur.shape[0])) @ facteur.T
    melange = np.sqrt(nu / generateur.chisquare(nu, simulations))
    return normaux * melange[:, None]


def monte_carlo_student_var(
    weights: Mapping[str, float],
    cov: pd.DataFrame,
    nu: float,
    confidence: float = 0.95,
    simulations: int = MONTE_CARLO_SIMULATIONS,
    seed: int = MONTE_CARLO_SEED,
    mean_daily: float = 0.0,
    method: str = QUANTILE_METHOD,
) -> MonteCarloEstimate:
    """VaR par simulation Student multivariée, graine fixe, en perte positive.

    La covariance simulée égale celle des données (voir `student_scale_matrix`) :
    l'écart avec le Monte Carlo normal mesure donc la forme des queues, et rien
    d'autre.
    """
    vecteur, sous_matrice = _aligned_weights(weights, cov)
    tirages = simulate_student_returns(sous_matrice, nu, simulations, seed)
    rendements = tirages @ vecteur + mean_daily
    quantile = float(np.quantile(rendements, _alpha(confidence), method=method))
    return MonteCarloEstimate(value=-quantile, simulations=simulations, seed=seed, nu=nu)
