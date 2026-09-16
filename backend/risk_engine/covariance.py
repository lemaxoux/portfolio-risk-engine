"""Mesures multi-titres : covariance, corrélation, beta. Fonctions pures.

Toutes reposent sur la MÊME convention de degrés de liberté (`config.DDOF`) que
la volatilité du bloc 4A. Sans cela, `√(wᵀΣw)` ne retomberait pas sur la
volatilité de la série de rendements du portefeuille, alors que c'est la même
quantité calculée de deux façons.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DDOF, TRADING_DAYS_PER_YEAR


@dataclass(frozen=True)
class Beta:
    """Sensibilité au marché et part de variance qu'il explique.

    `standard_error` est l'erreur type de la pente MCO. C'est ce qui distingue
    un beta estimé d'un simple rapport de deux nombres : il a une incertitude
    mesurable, qui croît quand l'échantillon rétrécit ou que l'ajustement se
    dégrade. None en dessous de trois observations, où elle n'est pas définie.
    """

    beta: float
    r_squared: float
    observations: int
    standard_error: float | None = None


def _validate_panel(asset_returns: pd.DataFrame, ddof: int) -> pd.DataFrame:
    if asset_returns.isna().any().any():
        raise ValueError(
            "Le panel contient des NaN. La covariance doit être estimée sur "
            "données COMPLÈTES : aligner d'abord avec returns.align_panel."
        )
    if asset_returns.shape[1] == 0:
        raise ValueError("Aucun titre dans le panel.")
    if len(asset_returns) <= ddof:
        raise ValueError(
            f"Au moins {ddof + 1} observations sont nécessaires "
            f"(reçu : {len(asset_returns)})."
        )
    return asset_returns


def covariance_matrix(
    asset_returns: pd.DataFrame, ddof: int = DDOF
) -> pd.DataFrame:
    """Matrice de covariance des rendements, sur observations complètes.

    POURQUOI PAS `DataFrame.cov()` — pandas applique une suppression PAIRE À
    PAIRE : chaque couple (i, j) est estimé sur les dates où i et j sont
    simultanément renseignés, donc sur des échantillons différents selon le
    couple. Les blocs de la matrice ne décrivent alors plus la même période, et
    l'objet obtenu peut cesser d'être semi-défini positif — auquel cas la
    décomposition de Cholesky du Monte Carlo échoue, souvent longtemps après
    l'endroit où le problème a été introduit.

    Ici, un NaN dans le panel est une erreur, pas une donnée à contourner :
    l'alignement se fait en amont (`returns.align_panel`), explicitement, et
    toutes les cellules de la matrice reposent sur les mêmes dates.
    """
    panel = _validate_panel(asset_returns, ddof)

    # Chaque colonne est décalée de sa première valeur avant estimation. Cela ne
    # change pas la covariance — elle est invariante par translation — mais
    # supprime l'annulation catastrophique : sur une colonne constante, le calcul
    # direct rend une variance de l'ordre de 1e-36 au lieu de zéro. Positive et
    # minuscule, elle échappe à tout test « variance nulle » et fait diviser la
    # corrélation par de la poussière. Même procédé que `measures._sample_std`.
    valeurs = panel.to_numpy()
    brut = np.cov(valeurs - valeurs[0], rowvar=False, ddof=ddof)
    # np.cov rend un scalaire 0-d pour une seule colonne.
    matrice = np.atleast_2d(brut)
    return pd.DataFrame(matrice, index=panel.columns, columns=panel.columns)


def correlation_matrix(
    asset_returns: pd.DataFrame, ddof: int = DDOF
) -> pd.DataFrame:
    """Matrice de corrélation de Pearson, dérivée de la covariance.

    Calculée comme `D⁻¹ Σ D⁻¹` avec `D = diag(σ)` plutôt que par un estimateur
    séparé : la corrélation reste ainsi cohérente avec la covariance à la
    cellule près, et hérite de sa propriété d'être semi-définie positive.

    La diagonale est fixée à 1 et les termes hors diagonale bornés à [−1, 1].
    Ce n'est pas un rattrapage de calcul mais l'application d'une définition :
    `Corr(X, X) = 1` par construction, et aucune corrélation ne peut sortir de
    [−1, 1]. Sans cela, `σᵢ²/(σᵢ·σᵢ)` rendrait 0,9999999999999999 en virgule
    flottante et un test d'invariant échouerait sur du bruit.
    """
    cov = covariance_matrix(asset_returns, ddof=ddof)
    variances = np.diag(cov.to_numpy())

    if (variances <= 0).any():
        constants = [
            t for t, v in zip(cov.columns, variances, strict=True) if v <= 0
        ]
        raise ValueError(
            f"Variance nulle pour {constants} : la corrélation n'est pas "
            "définie pour un titre dont le cours ne bouge pas sur la fenêtre."
        )

    inverse_sigma = 1.0 / np.sqrt(variances)
    corr = cov.to_numpy() * np.outer(inverse_sigma, inverse_sigma)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=cov.index, columns=cov.columns)


# ------------------------------------------------------- Risque de portefeuille --


def _aligned_weights(
    weights: Mapping[str, float], cov: pd.DataFrame
) -> tuple[np.ndarray, pd.DataFrame]:
    """Vecteur de poids et sous-matrice, appariés par ÉTIQUETTE.

    Jamais par position : un réordonnancement des colonnes attribuerait sinon
    le poids d'un titre à un autre, et la variance obtenue resterait
    parfaitement plausible.
    """
    manquants = set(weights) - set(cov.columns)
    if manquants:
        raise KeyError(f"Titres absents de la matrice : {sorted(manquants)}")
    tickers = list(weights)
    vecteur = np.array([float(weights[t]) for t in tickers])
    return vecteur, cov.loc[tickers, tickers]


def portfolio_variance(weights: Mapping[str, float], cov: pd.DataFrame) -> float:
    """Variance quotidienne du portefeuille : `wᵀΣw`."""
    vecteur, sous_matrice = _aligned_weights(weights, cov)
    return float(vecteur @ sous_matrice.to_numpy() @ vecteur)


def variance_contributions(
    weights: Mapping[str, float], cov: pd.DataFrame
) -> dict[str, float]:
    """Part de chaque ligne dans la variance du portefeuille.

    `cᵢ = wᵢ·(Σw)ᵢ / (wᵀΣw)` — décomposition d'Euler de la variance.

    Là où le poids ne dit que la part du CAPITAL, la contribution dit la part du
    RISQUE, parce que `(Σw)ᵢ` fait intervenir la covariance de la ligne avec
    tout le reste du portefeuille. Une ligne de 10 % très corrélée aux autres
    contribue davantage qu'une ligne de 10 % décorrélée, ce que le poids seul ne
    montre pas.

    Les contributions somment exactement à 1 : ce sont les termes d'une même
    somme `Σ wᵢ·(Σw)ᵢ = wᵀΣw`, divisés par leur total. Une contribution peut être
    NÉGATIVE : la ligne a alors évolué, en moyenne sur la fenêtre, à rebours du
    reste du portefeuille, et sa présence réduit la variance totale.

    Appariement poids / matrice par ÉTIQUETTE, jamais par position.
    """
    vecteur, sous_matrice = _aligned_weights(weights, cov)
    marginales = sous_matrice.to_numpy() @ vecteur
    variance = float(vecteur @ marginales)
    if variance <= 0.0:
        raise ValueError(
            "Variance du portefeuille nulle : la part de chaque ligne dans une "
            "variance nulle n'est pas définie."
        )
    parts = vecteur * marginales / variance
    return {ticker: float(part) for ticker, part in zip(weights, parts, strict=True)}


def parametric_volatility(
    weights: Mapping[str, float],
    cov: pd.DataFrame,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Volatilité annualisée par la matrice : `√(wᵀΣw) × √252`.

    IDENTITÉ, pas approximation : à convention de ddof identique, cette valeur
    est celle que `measures.annualised_volatility` rend sur la série `w·r`.
    Ce sont deux chemins de calcul vers la même quantité, et un test les
    compare à la tolérance flottante près.
    """
    variance = portfolio_variance(weights, cov)
    if variance < 0.0:
        # Ne peut venir que d'un bruit d'arrondi sur une matrice quasi
        # dégénérée ; une vraie variance négative n'existe pas.
        variance = 0.0
    return float(math.sqrt(variance) * math.sqrt(periods_per_year))


# ------------------------------------------------------------------- Beta --


def beta(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    ddof: int = DDOF,
) -> Beta:
    """Beta et R² du portefeuille contre un indice de référence.

    `β = Cov(r_p, r_m) / Var(r_m)`

    BASE DE RÉGRESSION — rendements BRUTS, pas excédentaires. Le beta théorique
    du MEDAF se définit sur des rendements excédentaires (`r − rf`), mais à
    l'horizon quotidien le taux sans risque vaut ici environ 1,5 point de base
    par séance, soit deux ordres de grandeur sous la volatilité quotidienne.
    Retrancher une quasi-constante des deux côtés d'une régression ne déplace
    pratiquement pas la pente. Le choix est fait pour la simplicité, et écrit
    ici pour qu'il ne soit pas à deviner.

    Le R² est la part de la variance du portefeuille expliquée par le marché :
    `R² = β²·Var(r_m)/Var(r_p)`. C'est la séparation entre risque systématique
    (subi par tout le marché, non diversifiable) et risque idiosyncratique
    (propre aux titres détenus, lui diversifiable). Un R² de 0,85 dit que 15 %
    de la variance vient de choix de titres, pas du marché.

    Les deux séries sont appariées par JOINTURE sur leurs index de dates. Un
    appariement positionnel comparerait des séances différentes dès que l'une
    des deux a un trou, et rendrait un beta parfaitement plausible mais faux.
    """
    panel = pd.concat(
        {"portefeuille": portfolio_returns, "marche": benchmark_returns},
        axis=1,
        join="inner",
    ).dropna()

    if len(panel) <= ddof:
        raise ValueError(
            f"Au moins {ddof + 1} séances communes au portefeuille et au "
            f"benchmark sont nécessaires (trouvé : {len(panel)}). "
            "Vérifier que l'historique du benchmark couvre la fenêtre."
        )

    valeurs = panel.to_numpy()
    matrice = np.cov(valeurs - valeurs[0], rowvar=False, ddof=ddof)
    var_portefeuille = float(matrice[0, 0])
    var_marche = float(matrice[1, 1])
    covariance = float(matrice[0, 1])

    if var_marche <= 0.0:
        raise ValueError(
            "Variance du benchmark nulle : le beta n'est pas défini contre un "
            "indice qui ne bouge pas."
        )

    pente = covariance / var_marche
    if var_portefeuille <= 0.0:
        # Portefeuille constant : aucune variance à expliquer.
        r_carre = 0.0
    else:
        # Formulé comme β²·Var(m)/Var(p) plutôt que ρ² : sur un portefeuille
        # identique au benchmark, les deux variances sont le même flottant et
        # le rapport vaut exactement 1, là où ρ² passerait par deux racines
        # carrées et rendrait 0,9999999999999998.
        r_carre = pente**2 * var_marche / var_portefeuille

    r_carre = min(r_carre, 1.0)
    n = len(panel)

    # Erreur type de la pente : SE² = Var(p)·(1 − R²) / ((n − 2)·Var(m)).
    # La convention de ddof s'annule dans le rapport des deux variances ; seuls
    # les n − 2 degrés de liberté résiduels de la régression comptent.
    erreur_type = None
    if n > 2:
        erreur_type = float(
            np.sqrt(
                max(var_portefeuille * (1.0 - r_carre), 0.0)
                / ((n - 2) * var_marche)
            )
        )

    return Beta(
        beta=float(pente),
        r_squared=float(r_carre),
        observations=n,
        standard_error=erreur_type,
    )


def smallest_eigenvalue(cov: pd.DataFrame) -> float:
    """Plus petite valeur propre de la matrice, signée."""
    return float(np.linalg.eigvalsh(cov.to_numpy()).min())


def is_positive_definite(cov: pd.DataFrame) -> bool:
    """Vrai si la matrice est définie positive, au sens numérique.

    Test de rang par valeurs propres plutôt que par échec du Cholesky : sur une
    matrice singulière « propre » — deux colonnes identiques, par exemple —
    `np.linalg.cholesky` ne lève PAS. Il réussit en posant un zéro sur la
    diagonale, et rend un facteur dégénéré avec lequel la simulation tourne
    sans rien signaler. S'en remettre à l'exception laisserait donc passer
    exactement le cas qu'on veut attraper.

    Le seuil est relatif à la plus grande valeur propre : une matrice de
    covariance quotidienne a des valeurs propres de l'ordre de 1e-4, et un seuil
    absolu la déclarerait singulière à tort.
    """
    valeurs_propres = np.linalg.eigvalsh(cov.to_numpy())
    plus_grande = float(valeurs_propres.max())
    if plus_grande <= 0.0:
        return False
    seuil = plus_grande * len(valeurs_propres) * np.finfo(float).eps
    return bool(valeurs_propres.min() > seuil)
