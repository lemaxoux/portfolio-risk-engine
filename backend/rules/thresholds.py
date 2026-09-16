"""Seuils du moteur de règles, et leur provenance.

Les seuils sont le point faible de tout moteur de règles : un nombre rond fixé à
la main prend vite l'apparence d'une vérité. Ils sont donc traités explicitement,
par ordre de préférence :

1. **Pas de seuil du tout** quand la mesure parle d'elle-même. Une observation
   sans seuil porte un tuple vide ; c'est le cas de la concentration effective
   (« tes 6 lignes se comportent comme 5,7 ») et de la part systématique.
2. **Un seuil dérivé d'une référence calculée**, comme l'équipondération 1/N ou
   la part de capital d'une ligne.
3. **Un seuil relatif au portefeuille lui-même**, comme la corrélation de sa paire
   la plus corrélée.
4. **En dernier recours seulement, un nombre rond choisi à la main.** Le résultat
   porte alors que ce seuil a été CHOISI et non découvert : même règle de
   provenance que pour les fenêtres d'estimation et les dates de valorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.risk_engine.config import (
    MIN_REGRESSION_OBSERVATIONS,
    THIN_TAIL_OBSERVATIONS,
)


class ThresholdKind(Enum):
    """D'où vient un seuil. L'ordre de déclaration est l'ordre de préférence."""

    DERIVED = "référence calculée"
    PORTFOLIO_RELATIVE = "relatif au portefeuille"
    CHOSEN = "choisi à la main"


@dataclass(frozen=True)
class Threshold:
    name: str
    kind: ThresholdKind
    value: float
    rationale: str
    percent: bool = False

    @property
    def chosen(self) -> bool:
        return self.kind is ThresholdKind.CHOSEN

    def __str__(self) -> str:
        if self.percent:
            valeur = f"{self.value * 100:.1f}".replace(".", ",").removesuffix(",0") + " %"
        else:
            valeur = f"{self.value:g}".replace(".", ",")
        if self.chosen:
            return (
                f"{self.name} = {valeur} — seuil CHOISI à la main, non dérivé des "
                f"données : {self.rationale}"
            )
        return f"{self.name} = {valeur} — {self.kind.value} : {self.rationale}"


# ------------------------------------------------ Seuils choisis à la main --

STRONG_CORRELATION = Threshold(
    name="corrélation forte",
    kind=ThresholdKind.CHOSEN,
    value=0.70,
    rationale=(
        "convention usuelle pour qualifier une corrélation de forte ; aucun calcul "
        "sur le portefeuille ne la produit"
    ),
)

MIN_SCENARIO_COVERAGE = Threshold(
    name="couverture minimale d'un scénario",
    kind=ThresholdKind.CHOSEN,
    value=0.50,
    rationale=(
        "en dessous, la partie rejouée devient minoritaire dans la valeur du "
        "portefeuille et son résultat ne peut plus tenir lieu de chiffre principal"
    ),
    percent=True,
)

THIN_TAIL = Threshold(
    name="nombre minimal d'observations de queue d'un CVaR",
    kind=ThresholdKind.CHOSEN,
    value=float(THIN_TAIL_OBSERVATIONS),
    rationale=(
        "marque le passage d'une moyenne sur quelques dizaines de journées à une "
        "moyenne sur une poignée"
    ),
)

MIN_REGRESSION_SAMPLE = Threshold(
    name="nombre minimal de séances d'une régression",
    kind=ThresholdKind.CHOSEN,
    value=float(MIN_REGRESSION_OBSERVATIONS),
    rationale=(
        "environ trois mois ; en deçà, quelques journées extrêmes dictent la pente "
        "à elles seules"
    ),
)


# --------------------------------------------- Seuils calculés ou relatifs --


def capital_share(ticker: str, weight: float) -> Threshold:
    """La part de capital d'une ligne, référence de sa part de risque."""
    return Threshold(
        name=f"part de {ticker} dans la valeur",
        kind=ThresholdKind.DERIVED,
        value=round(weight, 4),
        rationale=(
            "au-dessus, la ligne pèse davantage dans le risque que dans le capital ; "
            "en dessous, moins"
        ),
        percent=True,
    )


def most_correlated_pair(first: str, second: str, correlation: float) -> Threshold:
    """La corrélation de la paire la plus corrélée, propre à ce portefeuille."""
    return Threshold(
        name=f"corrélation {first}–{second}",
        kind=ThresholdKind.PORTFOLIO_RELATIVE,
        value=round(correlation, 2),
        rationale="corrélation de la paire la plus corrélée du portefeuille",
    )
