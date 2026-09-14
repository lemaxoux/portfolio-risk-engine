"""Construction des séries de rendements. Fonctions pures, sans base de données.

Deux conventions de rendement, deux usages, à ne pas confondre :

* **Rendements simples** — `r = P_t / P_{t-1} − 1`. Ils s'agrègent ENTRE TITRES :
  `r_p = Σ wᵢ·rᵢ`, parce que la valeur d'un portefeuille est la somme des
  valeurs de ses lignes et que cette additivité se transmet aux rendements
  simples. C'est la convention utilisée pour la série du portefeuille.
* **Rendements log** — `ln(P_t / P_{t-1})`. Ils s'agrègent DANS LE TEMPS : le
  rendement log sur N jours est la somme des rendements log quotidiens. C'est
  la propriété qui justifie la règle du √T.

Le log d'une somme pondérée n'est pas la somme pondérée des logs. Utiliser des
rendements log pour agréger entre titres sous-estimerait les grands mouvements
— précisément ceux que la mesure du risque cherche à capter.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


def simple_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Rendements simples `P_t/P_{t-1} − 1`, première observation retirée.

    À utiliser pour agréger entre titres.
    """
    return prices.pct_change().iloc[1:]


def log_returns(prices: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Rendements log `ln(P_t/P_{t-1})`, première observation retirée.

    À utiliser pour agréger dans le temps (changement d'horizon, règle du √T),
    jamais pour combiner plusieurs titres.
    """
    return np.log(prices / prices.shift(1)).iloc[1:]


def align_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les dates où TOUS les titres ont une observation.

    L'alignement se fait sur l'index de dates, jamais sur la position dans le
    tableau : une séance manquante sur un seul titre — suspension de cotation,
    trou de données, titre introduit plus tard — décalerait sinon toute sa série
    d'un cran par rapport aux autres. Le calcul continuerait de tourner et
    rendrait des corrélations et des rendements de portefeuille faux, sans rien
    signaler.

    L'intersection est le choix conservateur : mieux vaut moins d'observations,
    toutes datées correctement, qu'un panel complet mal aligné. Le nombre
    d'observations effectivement retenu est remonté dans chaque résultat.
    """
    if not panel.index.is_monotonic_increasing:
        panel = panel.sort_index()
    return panel.dropna(how="any")


def portfolio_returns(
    asset_returns: pd.DataFrame, weights: Mapping[str, float]
) -> pd.Series:
    """Série de rendements du portefeuille, à poids constants.

    `r_p,t = Σ wᵢ·rᵢ,t` avec les poids ACTUELS appliqués à tout l'historique.

    C'est l'hypothèse de rééquilibrage quotidien : chaque jour, le portefeuille
    est ramené aux poids d'aujourd'hui. Elle répond à la question « quel risque
    porte l'allocation que je détiens maintenant ? », qui est celle que pose une
    mesure de risque prospective.

    L'alternative — buy-and-hold, poids laissés dériver depuis une date d'achat
    — répond à une autre question : « qu'a fait ce portefeuille depuis que je
    l'ai constitué ? ». C'est une mesure de performance réalisée, dont les poids
    récents sont dominés par les titres qui ont le plus monté. Les deux sont
    légitimes ; les confondre ne l'est pas.

    Les scénarios de stress (Phase 5) utilisent délibérément l'autre convention
    — quantités figées pendant l'épisode — parce que sur dix-sept mois des poids
    constants supposeraient un rééquilibrage quotidien que personne ne fait.
    Voir l'en-tête de `risk_engine.stress`.

    L'appariement poids/colonnes se fait par ÉTIQUETTE de colonne, pas par
    position : un réordonnancement des colonnes ne peut pas attribuer
    silencieusement le poids d'un titre à un autre.
    """
    if not weights:
        raise ValueError("Aucun poids fourni : portefeuille vide.")

    manquants = set(weights) - set(asset_returns.columns)
    if manquants:
        raise KeyError(
            f"Titres sans série de rendements : {sorted(manquants)}. "
            "Vérifier que leur historique est bien en base."
        )

    tickers = list(weights)
    poids = pd.Series({t: float(weights[t]) for t in tickers})
    return asset_returns[tickers].mul(poids, axis=1).sum(axis=1)


def wealth_curve(returns: pd.Series, initial_date=None) -> pd.Series:
    """Valeur cumulée d'une unité investie, base 1.

    `initial_date` insère le point de départ à 1,0 à cette date. Sans lui, la
    courbe démarre à la valeur du premier rendement et le pic initial est perdu
    : un drawdown mesuré sur une série qui ne commence à baisser qu'après le
    premier jour serait alors calculé depuis un sommet trop bas, donc
    sous-estimé.
    """
    courbe = (1.0 + returns).cumprod()
    if initial_date is None:
        return courbe
    depart = pd.Series([1.0], index=[initial_date])
    return pd.concat([depart, courbe])
