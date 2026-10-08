"""L'écran d'acceptation, en français.

Déplacé tel quel de `rules/disclaimer.py` (chantier 7D), qui garde la
décision — quelle durée, en années ou en mois — et lit ici le texte. Un octet
de plus dans ce texte changerait son empreinte, et ferait réaccepter tout le
monde : rien n'y a changé.

Ce texte VOUVOIE, comme toute la page depuis les textes de lecture du
2026-10-05. C'est le seul endroit du projet à portée quasi juridique. Ce texte
n'a pas été relu par un juriste.
"""

from __future__ import annotations

from backend import typography

TITRE = "Avant d'utiliser Mx Risk MGT"

CONFIRMATION = (
    "J'ai lu ces limites, je les comprends, et j'utilise cet outil en connaissance "
    "de cause."
)


def duree_en_annees(annees: int) -> str:
    """« environ 2 ans » : le nombre et son unité liés par une espace insécable
    (`typography.counted`). Avec une espace ordinaire, « soit environ 2 »
    finissait une ligne que « ans. » commençait."""
    return f"environ {typography.counted(annees, 'an')}"


def duree_en_mois(mois: int) -> str:
    """« environ 6 mois », lié de même."""
    return f"environ {typography.counted(mois, 'mois', 'mois')}"


def sections(fenetre: int, duree: str) -> tuple[tuple[str, str], ...]:
    """Les cinq sections, titre et corps. `fenetre` est le nombre de séances
    demandé, `duree` sa durée déjà rédigée (« environ 2 ans »)."""
    return (
        (
            "Un outil informatif, pas un conseil",
            "Mx Risk MGT décrit des propriétés statistiques de votre portefeuille. "
            "Il ne constitue pas un conseil en investissement réglementé, ni une "
            "recommandation d'acheter, de vendre ou de conserver un titre. Il ne "
            "connaît ni votre horizon de placement, ni vos objectifs, ni votre "
            "situation fiscale, ni le reste de votre patrimoine : aucune de ses "
            "observations ne peut en tenir compte.",
        ),
        (
            "Aucune garantie d'exactitude",
            "Les données de marché proviennent d'un fournisseur tiers et peuvent "
            "comporter des erreurs, des retards ou des omissions. Les calculs "
            "reposent sur des hypothèses statistiques et peuvent eux-mêmes être "
            "erronés. Aucune garantie n'est donnée sur l'exactitude, "
            "l'exhaustivité ou l'actualité des données ni des calculs.",
        ),
        (
            "Les mesures décrivent un régime, pas un avenir",
            "Les mesures de risque courantes (volatilité, VaR, CVaR, beta, "
            f"corrélations) sont estimées sur les {fenetre}\u00a0dernières "
            "séances de "
            f"bourse, soit {duree}. Elles décrivent le comportement du "
            "portefeuille pendant cette période. Elles ne prédisent pas son "
            "comportement futur, qui peut s'en écarter fortement, en particulier "
            "lors d'une crise.",
        ),
        (
            "Les scénarios rejouent des crises passées, ils ne prédisent pas les prochaines",
            "Les scénarios de stress appliquent à votre portefeuille actuel les "
            "mouvements réellement observés pendant des crises passées. Ils ne "
            "prédisent ni la survenue, ni l'ampleur, ni la forme d'une prochaine "
            "crise, qui ne ressemblera pas nécessairement à celles-ci.",
        ),
        (
            "Utilisation à vos risques",
            "Vous utilisez cet outil à vos propres risques, et les décisions que "
            "vous prenez relèvent de votre seule responsabilité. La responsabilité "
            "de l'auteur de l'outil ne peut être engagée pour les conséquences "
            "de décisions fondées sur les informations qu'il affiche.",
        ),
    )
