"""L'écran d'acceptation, en anglais (chantier 7D).

Les cinq mêmes sections que `fr/bandeau.py`, traduites avec le glossaire
validé (`anglais-proposition.md`, §e.3, hors dépôt). Le texte anglais a sa
propre empreinte : un visiteur qui passe à l'anglais l'accepte une fois, et
l'acceptation française n'est pas touchée. Comme le français, il n'a pas été
relu par un juriste ; le lecteur anglophone prévu en 7E le lira en premier.

La garde prescriptive ne lit ni ce module ni son jumeau français : l'écran
d'acceptation dit à bon droit ce que l'outil n'est pas, « not advice », et
qu'il ne recommande ni « buy », ni « sell », ni « hold ».
"""

from __future__ import annotations

from backend import typography

TITRE = "Before using Mx Risk MGT"

CONFIRMATION = "I have read these limitations, I understand them, and I use this tool knowingly."


def duree_en_annees(annees: int) -> str:
    """« about 2 years » : le nombre et son unité liés par une espace insécable."""
    return f"about {typography.counted(annees, 'year', langue='en')}"


def duree_en_mois(mois: int) -> str:
    """« about 6 months », lié de même."""
    return f"about {typography.counted(mois, 'month', langue='en')}"


def sections(fenetre: int, duree: str) -> tuple[tuple[str, str], ...]:
    """Les cinq sections, titre et corps. `fenetre` est le nombre de séances
    demandé, `duree` sa durée déjà rédigée (« about 2 years »)."""
    return (
        (
            "An information tool, not advice",
            "Mx Risk MGT describes statistical properties of your portfolio. It is "
            "not regulated investment advice, nor a recommendation to buy, sell, or "
            "hold a security. It does not know your investment horizon, your "
            "objectives, your tax situation, or the rest of your wealth: none of its "
            "observations can take them into account.",
        ),
        (
            "No guarantee of accuracy",
            "Market data comes from a third-party provider and may contain errors, "
            "delays, or omissions. The calculations rest on statistical assumptions "
            "and may themselves be wrong. No guarantee is given as to the accuracy, "
            "completeness, or timeliness of the data or of the calculations.",
        ),
        (
            "The measures describe a regime, not the future",
            "The usual risk measures (volatility, VaR, CVaR, beta, correlations) are "
            "estimated over the last "
            f"{typography.grouped(fenetre, 'trading session', langue='en')}, {duree}. "
            "They describe how the portfolio behaved during that period. They do not "
            "predict its future behavior, which may differ sharply, especially "
            "during a crisis.",
        ),
        (
            "The scenarios replay past crises; they do not predict the next ones",
            "The stress scenarios apply the movements actually observed during past "
            "crises to your current portfolio. They do not predict the occurrence, "
            "size, or shape of a future crisis, which will not necessarily resemble "
            "these.",
        ),
        (
            "Use at your own risk",
            "You use this tool at your own risk, and the decisions you make are your "
            "sole responsibility. The author of the tool cannot be held liable for "
            "the consequences of decisions based on the information it displays.",
        ),
    )
