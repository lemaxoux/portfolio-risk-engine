"""Mesures de risque. Fonctions pures : tableaux et séries en entrée, nombres
en sortie, aucune base de données, aucun état.

Chaque fonction documente son hypothèse. Une mesure de risque sans ses
hypothèses n'est pas un résultat, c'est un chiffre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from .config import EWMA_LAMBDA, TRADING_DAYS_PER_YEAR


@dataclass(frozen=True)
class Drawdown:
    """Perte maximale pic-creux, avec les dates qui la produisent."""

    value: float
    peak_date: date
    trough_date: date
    peak_level: float
    trough_level: float


def _as_array(returns) -> np.ndarray:
    tableau = np.asarray(
        returns.to_numpy() if isinstance(returns, pd.Series) else returns,
        dtype=float,
    )
    if tableau.ndim != 1:
        raise ValueError("Une série de rendements unidimensionnelle est attendue.")
    if np.isnan(tableau).any():
        raise ValueError(
            "La série contient des NaN : aligner les dates avant de mesurer "
            "(voir returns.align_panel)."
        )
    return tableau


def _sample_std(values: np.ndarray, ddof: int = 1) -> float:
    """Écart-type d'échantillon, calculé sur données décalées.

    Retrancher une constante à toute la série ne change pas sa dispersion, mais
    supprime l'annulation catastrophique qui survient quand la moyenne est
    grande devant l'écart. Sur une série strictement constante, le calcul direct
    rend ~1e-17 au lieu de zéro : la volatilité n'est plus « exactement nulle »,
    et surtout un Sharpe divisé par cette poussière devient astronomique au lieu
    d'être signalé comme indéfini.

    C'est l'algorithme classique de la variance décalée, pas un contournement de
    test : le résultat est aussi plus juste sur des séries à moyenne élevée.
    """
    if values.size <= ddof:
        raise ValueError(
            f"Au moins {ddof + 1} observations sont nécessaires "
            f"(reçu : {values.size})."
        )
    return float(np.std(values - values[0], ddof=ddof))


# ------------------------------------------------------------- Volatilité --


def annualised_volatility(
    returns,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    ddof: int = 1,
) -> float:
    """Écart-type des rendements quotidiens × √252.

    HYPOTHÈSE — la règle du √T suppose des rendements indépendants et
    identiquement distribués. La variance d'une somme de N variables ne vaut N
    fois la variance individuelle que si leurs covariances sont nulles ; d'où
    l'écart-type en √N. Les rendements d'actions violent cette hypothèse de deux
    façons connues :

    * autocorrélation faible mais non nulle, qui biaise le √T dans un sens ou
      dans l'autre selon son signe ;
    * regroupement de volatilité (les grandes variations se suivent), qui rend
      la volatilité elle-même variable dans le temps — c'est ce que la variante
      EWMA cherche à capter.

    Le √T reste la convention de place et le point de comparaison attendu, mais
    il décrit un monde plus régulier que le vrai.

    `ddof=1` : estimateur d'échantillon (division par N−1), pas de population.
    """
    tableau = _as_array(returns)
    return float(_sample_std(tableau, ddof=ddof) * math.sqrt(periods_per_year))


def ewma_volatility(
    returns,
    lam: float = EWMA_LAMBDA,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Volatilité annualisée par lissage exponentiel, façon RiskMetrics.

    `σ²ₜ = λ·σ²ₜ₋₁ + (1−λ)·r²ₜ₋₁`

    Deux points de convention, tous deux volontaires :

    * **Pas de centrage.** On utilise `r²` et non `(r − r̄)²`. Sur données
      quotidiennes, la moyenne des rendements est d'un ordre de grandeur
      inférieur à leur écart-type ; l'estimer coûte un degré de liberté et
      ajoute plus de bruit qu'elle n'enlève de biais. C'est la convention
      RiskMetrics pour le pas quotidien.
    * **Amorçage** par la variance non centrée de la fenêtre. La récursion
      oublie son point de départ à mesure qu'elle avance : avec λ = 0,94, le
      poids de l'amorçage tombe sous 5 % après une cinquantaine de séances.

    La valeur rendue est la variance après intégration du dernier rendement
    observé, c'est-à-dire la prévision pour la séance suivante — contrairement
    à l'écart-type sur fenêtre fixe, qui décrit le passé.
    """
    if not 0.0 < lam < 1.0:
        raise ValueError(f"λ doit être strictement entre 0 et 1 (reçu : {lam}).")

    tableau = _as_array(returns)
    if tableau.size == 0:
        raise ValueError("Série de rendements vide.")

    variance = float(np.mean(tableau**2))
    for rendement in tableau:
        variance = lam * variance + (1.0 - lam) * rendement**2
    return float(math.sqrt(variance * periods_per_year))


# --------------------------------------------------------------- Drawdown --


def max_drawdown(levels: pd.Series) -> Drawdown:
    """Perte maximale pic-creux d'une série de valeur.

    Le pic est GLISSANT : à chaque date, la référence est le maximum atteint
    JUSQU'À cette date, pas le maximum global de la série. La différence n'est
    pas cosmétique — un maximum global situé après le creux mesurerait une
    perte qui n'a jamais pu être subie, puisqu'on ne peut pas décrocher d'un
    sommet qui n'existait pas encore.

    Attend une série de NIVEAUX (prix, ou valeur cumulée d'un portefeuille),
    pas de rendements. Voir `returns.wealth_curve` pour passer des seconds aux
    premiers.
    """
    if len(levels) == 0:
        raise ValueError("Série de niveaux vide.")
    if levels.isna().any():
        raise ValueError("La série de niveaux contient des NaN.")

    pic_glissant = levels.cummax()
    ecart = levels / pic_glissant - 1.0

    date_creux = ecart.idxmin()
    # Le pic de référence est le plus haut atteint AVANT le creux.
    date_pic = levels.loc[:date_creux].idxmax()

    return Drawdown(
        value=float(ecart.loc[date_creux]),
        peak_date=date_pic,
        trough_date=date_creux,
        peak_level=float(levels.loc[date_pic]),
        trough_level=float(levels.loc[date_creux]),
    )


# ----------------------------------------------------------------- Ratios --


def sharpe_ratio(
    returns,
    risk_free_daily: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Sharpe annualisé.

    `√252 × moyenne(r − rf) / écart-type(r − rf)`

    Numérateur et dénominateur portent sur la MÊME série de rendements
    excédentaires, et l'annualisation s'applique au ratio quotidien une seule
    fois. Deux erreurs courantes évitées ici :

    * retrancher le taux sans risque au numérateur mais mesurer la volatilité
      sur les rendements bruts — les deux termes ne décrivent alors pas la même
      grandeur ;
    * annualiser séparément moyenne (×252) et écart-type (×√252) puis en faire
      le rapport, ce qui revient à multiplier le ratio par √252 une fois de
      trop.

    `risk_free_daily` est un taux QUOTIDIEN (voir `config.daily_risk_free_rate`).
    """
    excedent = _as_array(returns) - risk_free_daily
    ecart_type = _sample_std(excedent, ddof=1)
    if ecart_type == 0.0:
        raise ValueError(
            "Écart-type des rendements excédentaires nul : le ratio de Sharpe "
            "n'est pas défini (série constante)."
        )
    return float(
        math.sqrt(periods_per_year) * float(np.mean(excedent)) / ecart_type
    )


def downside_deviation(returns, target_daily: float = 0.0) -> float:
    """Déviation à la baisse : `√( (1/N)·Σ min(rₜ − cible, 0)² )`.

    N est le nombre TOTAL d'observations, pas le nombre d'observations sous la
    cible. Diviser par le seul compte des périodes négatives est l'erreur
    classique : elle transforme la mesure en « ampleur moyenne des baisses »
    et gonfle mécaniquement le ratio de Sortino des portefeuilles qui baissent
    rarement mais fortement — exactement le profil de risque qu'on cherche à
    détecter.
    """
    ecarts = _as_array(returns) - target_daily
    if ecarts.size == 0:
        raise ValueError("Série de rendements vide.")
    sous_cible = np.minimum(ecarts, 0.0)
    return float(math.sqrt(float(np.sum(sous_cible**2)) / ecarts.size))


def sortino_ratio(
    returns,
    target_daily: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float | None:
    """Sortino annualisé : `√252 × moyenne(r − cible) / déviation à la baisse`.

    Variante du Sharpe qui ne pénalise que la volatilité subie sous la cible :
    un portefeuille qui monte brutalement n'est pas puni pour cela.

    Rend **None** quand la déviation à la baisse est nulle, c'est-à-dire quand
    aucune observation de la fenêtre ne passe sous la cible. Le ratio est alors
    indéfini, pas infini : le diviseur n'est pas « très petit », il est
    exactement zéro, et sa valeur ne renseigne sur rien puisqu'aucune baisse
    n'a été observée. Rendre `inf` ou `NaN` laisserait la valeur se propager
    dans un tableau de bord et s'y faire passer pour un résultat.
    """
    ecarts = _as_array(returns) - target_daily
    deviation = downside_deviation(returns, target_daily)
    if deviation == 0.0:
        return None
    return float(
        math.sqrt(periods_per_year) * float(np.mean(ecarts)) / deviation
    )


# ---------------------------------------------------------- Concentration --


def herfindahl_index(weights) -> float:
    """Indice de Herfindahl-Hirschman : `HHI = Σ wᵢ²`.

    Borné entre `1/N` (parfaitement équipondéré) et `1` (tout sur une ligne).
    Son inverse `1/HHI` s'interprète comme le nombre de positions
    « effectives » : un portefeuille de 10 lignes dont une pèse 80 % a un HHI
    proche de 0,65, soit environ 1,5 position effective.

    HYPOTHÈSE — positions longues uniquement. La mesure vient de l'économie
    industrielle, où les parts de marché sont positives par construction. Avec
    une position vendeuse, un poids négatif contribue positivement au carré :
    un portefeuille long/short parfaitement couvert afficherait une
    concentration élevée alors que son exposition nette est nulle. Le nombre
    rendu n'aurait alors aucun sens, c'est pourquoi un poids négatif lève une
    erreur au lieu d'être calculé.

    Les poids doivent sommer à 1 : ce sont des parts, et une normalisation
    silencieuse masquerait une erreur de construction en amont.
    """
    tableau = np.asarray(list(weights.values()) if isinstance(weights, dict) else weights, dtype=float)
    if tableau.size == 0:
        raise ValueError("Aucun poids fourni.")
    if (tableau < 0).any():
        raise ValueError(
            "Poids négatif : le HHI suppose des positions longues uniquement "
            "(voir la docstring). Une position vendeuse rendrait la mesure "
            "ininterprétable."
        )
    total = float(np.sum(tableau))
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise ValueError(
            f"Les poids doivent sommer à 1 (somme reçue : {total:.6f})."
        )
    return float(np.sum(tableau**2))


def equal_weight_reference(n_positions: int) -> float:
    """HHI d'un portefeuille parfaitement équipondéré à N lignes, soit `1/N`.

    Point de comparaison : un HHI de 0,25 ne dit rien seul ; rapporté au 0,10
    d'un portefeuille équipondéré à 10 lignes, il dit que la concentration
    équivaut à ne détenir que 4 positions.
    """
    if n_positions <= 0:
        raise ValueError("Un portefeuille comporte au moins une position.")
    return 1.0 / n_positions
