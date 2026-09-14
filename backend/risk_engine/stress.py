"""Rejeu de scénarios historiques sur le portefeuille actuel. Fonctions pures.

═══ CE QUI EST REJOUÉ ═══

Le portefeuille ACTUEL entre dans l'épisode : au premier jour de la fenêtre,
chaque ligne pèse son poids d'aujourd'hui en valeur de marché. On en déduit un
nombre d'unités par ligne, puis ces quantités restent FIGÉES jusqu'à la fin de
la fenêtre.

Appliquer les quantités d'aujourd'hui aux cours de 2007 serait une erreur : les
titres ont connu des trajectoires très différentes depuis, et le portefeuille
qui entrerait dans la crise n'aurait plus rien à voir avec celui qu'on détient.
Une ligne qui pèse 15 % aujourd'hui en pèserait 2 % au départ du scénario, et le
résultat répondrait à une question que personne ne pose.

═══ RUPTURE DE CONVENTION ASSUMÉE AVEC LA PHASE 4 ═══

La Phase 4 calcule la série de rendements du portefeuille à POIDS CONSTANTS. Ici,
une fois l'épisode commencé, ce sont les QUANTITÉS qui restent constantes —
achat-conservation — et les poids dérivent. Ce n'est pas une incohérence mais
deux questions différentes, dont l'écart n'apparaît qu'aux horizons longs.

* À un jour, l'écart est nul en pratique : les poids n'ont pas le temps de
  dériver. Les poids constants sont alors le bon choix, parce qu'ils répondent à
  « quel risque porte l'allocation que je détiens aujourd'hui ? ».
* Sur les dix-sept mois de la crise 2008, des poids constants supposent un
  rééquilibrage QUOTIDIEN : vendre chaque jour ce qui a le mieux tenu pour
  racheter ce qui vient de chuter, pendant toute la descente. Ce n'est pas ce
  que fait un porteur passif, qui ne touche à rien et regarde ses poids dériver.

Prêter au porteur un rééquilibrage qu'il ne fera pas donnerait un résultat plus
flatteur que la réalité : le rééquilibrage rachète mécaniquement au plus bas et
amortit la baisse.

═══ POURQUOI `adj_close` ═══

Sur dix-sept mois, les dividendes ne sont pas un détail : ignorer un rendement
de 3 % l'an sur une ligne défensive fausse sa contribution de plusieurs points.
Les trajectoires utilisent donc `adj_close`, comme tout le reste du moteur. Les
quantités s'entendent en unités de cet indice de performance totale, ce qui
revient à réinvestir les dividendes — la convention standard de
l'achat-conservation.

La trajectoire est exprimée en base 1 au premier jour : seuls les rapports de
valeur ont un sens, ce qui suffit pour un rendement, un drawdown et une
décomposition.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PositionContribution:
    """Ce qu'une ligne a apporté ou coûté pendant l'épisode.

    `contribution` est exprimée en fraction de la valeur rejouée au DÉBUT de la
    fenêtre, de sorte que la somme des contributions redonne exactement le
    rendement de bout en bout. `own_return` est le rendement de la ligne prise
    isolément — une petite ligne peut s'effondrer sans peser.

    `start_weight` est le poids actuel de la ligne (renormalisé sur les lignes
    couvertes) ; `end_weight` est celui où l'a menée l'achat-conservation.
    """

    ticker: str
    start_value: float
    end_value: float
    own_return: float
    contribution: float
    start_weight: float
    end_weight: float

    @property
    def pnl(self) -> float:
        return self.end_value - self.start_value

    @property
    def weight_drift(self) -> float:
        """Dérive du poids sur l'épisode, effet direct de l'achat-conservation."""
        return self.end_weight - self.start_weight


def _validate(panel: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """Contrôles communs, et poids normalisés à 1 appariés par ÉTIQUETTE."""
    if not weights:
        raise ValueError("Aucun poids fourni : portefeuille vide.")

    manquants = set(weights) - set(panel.columns)
    if manquants:
        raise KeyError(f"Titres absents du panel : {sorted(manquants)}")
    if panel.isna().any().any():
        raise ValueError(
            "Le panel contient des NaN : aligner les dates avant de rejouer "
            "un scénario (voir returns.align_panel)."
        )
    if len(panel) < 2:
        raise ValueError(
            f"Au moins deux séances sont nécessaires (reçu : {len(panel)})."
        )

    poids = pd.Series({t: float(weights[t]) for t in weights})
    if (poids < 0).any():
        raise ValueError(
            "Poids négatif : l'achat-conservation est défini ici pour des "
            "positions longues."
        )
    total = float(poids.sum())
    if total <= 0.0:
        raise ValueError("La somme des poids doit être strictement positive.")

    depart = panel[list(weights)].iloc[0]
    if (depart <= 0).any():
        raise ValueError("Cours de départ nul ou négatif : trajectoire indéfinie.")
    return poids / total


def held_quantities(
    panel: pd.DataFrame, weights: Mapping[str, float]
) -> pd.Series:
    """Unités détenues pendant tout l'épisode, déduites des poids de départ.

    `qᵢ = wᵢ / adj_closeᵢ,début` : au premier jour, la ligne i pèse exactement
    son poids actuel. Ces quantités ne sont plus jamais modifiées ensuite.

    Les poids sont normalisés à 1, et l'appariement poids/colonnes se fait par
    ÉTIQUETTE, jamais par position.
    """
    poids = _validate(panel, weights)
    return poids / panel[poids.index].iloc[0]


def buy_and_hold_value(
    panel: pd.DataFrame, weights: Mapping[str, float]
) -> pd.Series:
    """Trajectoire de valeur, base 1, à quantités figées après le départ.

    `V_t = Σ qᵢ · adj_closeᵢ,t`, avec `V_0 = 1`. Seuls les cours bougent ; les
    poids dérivent donc d'eux-mêmes à mesure que les lignes baissent à des
    rythmes différents.
    """
    quantites = held_quantities(panel, weights)
    return panel[quantites.index].mul(quantites, axis=1).sum(axis=1)


def end_to_end_return(values: pd.Series) -> float:
    """Rendement du premier au dernier point de la fenêtre.

    « Ce que vaudrait le portefeuille à la sortie de l'épisode. » À distinguer du
    drawdown maximum, qui mesure le pire moment TRAVERSÉ et peut être plus
    profond : un portefeuille peut finir à −20 % après être passé par −35 %.
    """
    if len(values) < 2:
        raise ValueError("Au moins deux points sont nécessaires.")
    depart = float(values.iloc[0])
    if depart <= 0.0:
        raise ValueError(f"Valeur de départ nulle ou négative : {depart}")
    return float(values.iloc[-1]) / depart - 1.0


def position_contributions(
    panel: pd.DataFrame, weights: Mapping[str, float]
) -> list[PositionContribution]:
    """Décomposition de la perte ligne par ligne.

    C'est ce qui rend un scénario actionnable plutôt qu'alarmant : « −38 % »
    n'indique rien à faire, « −38 % dont 22 points venus de deux lignes
    financières » indique où regarder. C'est aussi la matière première des
    règles de la Phase 6.

    Les contributions somment exactement au rendement de bout en bout, par
    construction : chacune vaut `(valeur_fin − valeur_début) / valeur_début_totale`.
    """
    quantites = held_quantities(panel, weights)
    valeurs = panel[quantites.index].mul(quantites, axis=1)
    debut_total = float(valeurs.iloc[0].sum())
    fin_total = float(valeurs.iloc[-1].sum())

    resultats = []
    for ticker in quantites.index:
        debut = float(valeurs[ticker].iloc[0])
        fin = float(valeurs[ticker].iloc[-1])
        resultats.append(
            PositionContribution(
                ticker=ticker,
                start_value=debut,
                end_value=fin,
                own_return=fin / debut - 1.0,
                contribution=(fin - debut) / debut_total,
                start_weight=debut / debut_total,
                end_weight=(fin / fin_total) if fin_total > 0 else 0.0,
            )
        )

    return sorted(resultats, key=lambda c: c.contribution)
