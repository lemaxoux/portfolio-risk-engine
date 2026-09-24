"""Seuils du moteur de règles, et leur provenance.

Les seuils sont le point faible de tout moteur de règles : un nombre rond fixé à
la main prend vite l'apparence d'une vérité. Ils sont donc traités explicitement,
par ordre de préférence :

1. **Pas de seuil du tout** quand la mesure parle d'elle-même. Une observation
   sans seuil porte un tuple vide ; c'est le cas de la concentration effective
   (« tes 6 lignes se comportent comme 5,7 ») et de la part systématique.
2. **Un seuil dérivé d'une référence calculée**, comme l'équipondération 1/N ou
   la part de capital d'une ligne. Entre aussi dans cette catégorie le seuil
   qui vient de l'ALGÈBRE de l'estimateur et non d'une convention : le nombre
   d'observations en deçà duquel une statistique cesse d'être une mesure n'a
   pas été choisi, il se démontre (voir `MIN_ESTIMABLE_SAMPLE`).
3. **Un seuil relatif au portefeuille lui-même**, comme la corrélation de sa paire
   la plus corrélée.
4. **En dernier recours seulement, un nombre rond choisi à la main.** Le résultat
   porte alors que ce seuil a été CHOISI et non découvert : même règle de
   provenance que pour les fenêtres d'estimation et les dates de valorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend import typography
from backend.risk_engine.config import (
    MIN_ESTIMABLE_OBSERVATIONS,
    MIN_REGRESSION_OBSERVATIONS,
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
        valeur = (
            typography.percent(self.value, 1, trim=True)
            if self.percent
            else typography.compact(self.value)
        )
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
    value=0.80,
    rationale=(
        "le biais de la renormalisation est orienté — la partie exclue est plus "
        "récente, donc en moyenne plus spéculative —, un seuil plus strict qu'un "
        "pile ou face s'impose ; à 80 %, même si la partie exclue avait perdu deux "
        "fois plus que la partie couverte, la perte de l'ensemble ne dépasserait le "
        "chiffre affiché que d'un cinquième, contre moitié plus à 50 %"
    ),
    percent=True,
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

# Le seul seuil du projet qui ne soit pas une convention : il se démontre.
#
# À deux observations, le centrage ne laisse qu'une SEULE direction — les deux
# écarts à la moyenne valent ±δ/2, où δ est la différence entre les deux
# rendements. Corrélation, beta et contributions à la variance s'y calculent donc
# tous à partir de ce seul δ, et ne portent aucune information que δ ne porte
# déjà. Chacun dégénère ensuite à sa manière : |ρ| = 1 par colinéarité, une pente
# sans erreur type faute de résidu, une covariance de rang 1 dont les
# contributions valent `wᵢδᵢ / (wᵀδ)`. Voir `MIN_ESTIMABLE_OBSERVATIONS` dans la
# configuration du moteur pour le détail des trois.
#
# C'est ce qui sépare ce seuil de `MIN_REGRESSION_SAMPLE`. À 40 séances, un R²
# est une estimation BRUYANTE : le chiffre dit quelque chose, mal. À 2 séances,
# ce n'est pas une estimation du tout, c'est une identité arithmétique — et
# aucune mention d'« échantillon mince » ne répare une phrase qui affirme
# l'identité comme si elle décrivait le portefeuille. D'où deux régimes : en
# deçà de ce seuil la règle REFUSE de chiffrer, au-dessus elle chiffre en
# signalant.
#
# Le moteur connaît déjà cette frontière : `covariance.Beta.standard_error` est
# documenté « None en dessous de trois observations, où elle n'est pas définie ».
# Nommé comme `MIN_REGRESSION_SAMPLE` : la CONSTANTE vit dans le moteur, le
# SEUIL — le nombre plus sa provenance — vit ici. Deux objets, deux noms.
MIN_ESTIMABLE_SAMPLE = Threshold(
    name="nombre minimal de séances estimables",
    kind=ThresholdKind.DERIVED,
    value=float(MIN_ESTIMABLE_OBSERVATIONS),
    rationale=(
        "à deux observations, le centrage ne laisse qu'une seule direction : "
        "corrélation, beta et contributions à la variance s'y calculent tous à "
        "partir d'un unique écart journalier et ne portent aucune information "
        "qu'il ne porte déjà — ce ne sont plus des statistiques bruyantes mais "
        "des identités arithmétiques"
    ),
)



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
