"""Texte du bandeau d'acceptation.

Seulement le texte : l'écran qui le portera relève de la Phase 7. Il est tenu ici,
à côté des règles, parce qu'il en est la borne — les observations décrivent, et
ce texte dit ce qu'elles ne sont pas.

La taille de la fenêtre d'estimation n'est pas écrite en dur : elle vient de la
configuration du moteur, pour que le texte ne puisse pas dire « 504 séances » le
jour où le calcul en utiliserait un autre nombre.

Ce texte VOUVOIE, là où les observations tutoient : c'est le seul endroit du
projet à portée quasi juridique, et un registre formel l'y distingue du reste.
Ce texte n'a pas été relu par un juriste.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.risk_engine.config import DEFAULT_WINDOW, TRADING_DAYS_PER_YEAR

ACCEPTANCE_TITLE = "Avant d'utiliser Mx Risk MGT"

ACCEPTANCE_CONFIRMATION = (
    "J'ai lu ces limites, je les comprends, et j'utilise cet outil en connaissance "
    "de cause."
)


@dataclass(frozen=True)
class DisclaimerSection:
    title: str
    body: str


def _duree(seances: int) -> str:
    annees = seances / TRADING_DAYS_PER_YEAR
    if abs(annees - round(annees)) < 0.05 and round(annees) >= 1:
        n = round(annees)
        return f"environ {n} an" if n == 1 else f"environ {n} ans"
    return f"environ {round(seances / 21)} mois"


def acceptance_sections(window: int = DEFAULT_WINDOW) -> tuple[DisclaimerSection, ...]:
    return (
        DisclaimerSection(
            title="Un outil informatif, pas un conseil",
            body=(
                "Mx Risk MGT décrit des propriétés statistiques de votre portefeuille. "
                "Il ne constitue pas un conseil en investissement réglementé, ni une "
                "recommandation d'acheter, de vendre ou de conserver un titre. Il ne "
                "connaît ni votre horizon de placement, ni vos objectifs, ni votre "
                "situation fiscale, ni le reste de votre patrimoine : aucune de ses "
                "observations ne peut en tenir compte."
            ),
        ),
        DisclaimerSection(
            title="Aucune garantie d'exactitude",
            body=(
                "Les données de marché proviennent d'un fournisseur tiers et peuvent "
                "comporter des erreurs, des retards ou des omissions. Les calculs "
                "reposent sur des hypothèses statistiques et peuvent eux-mêmes être "
                "erronés. Aucune garantie n'est donnée sur l'exactitude, "
                "l'exhaustivité ou l'actualité des données ni des calculs."
            ),
        ),
        DisclaimerSection(
            title="Les mesures décrivent un régime, pas un avenir",
            body=(
                "Les mesures de risque courantes — volatilité, VaR, CVaR, beta, "
                f"corrélations — sont estimées sur les {window} dernières séances de "
                f"bourse, soit {_duree(window)}. Elles décrivent le comportement du "
                "portefeuille pendant cette période. Elles ne prédisent pas son "
                "comportement futur, qui peut s'en écarter fortement, en particulier "
                "lors d'une crise."
            ),
        ),
        DisclaimerSection(
            title="Les scénarios rejouent des crises passées, ils ne prédisent pas les prochaines",
            body=(
                "Les scénarios de stress appliquent à votre portefeuille actuel les "
                "mouvements réellement observés pendant des crises passées. Ils ne "
                "prédisent ni la survenue, ni l'ampleur, ni la forme d'une prochaine "
                "crise, qui ne ressemblera pas nécessairement à celles-ci."
            ),
        ),
        DisclaimerSection(
            title="Utilisation à vos risques",
            body=(
                "Vous utilisez cet outil à vos propres risques, et les décisions que "
                "vous prenez relèvent de votre seule responsabilité. La responsabilité "
                "de l'auteur de l'outil ne peut être engagée pour les conséquences "
                "de décisions fondées sur les informations qu'il affiche."
            ),
        ),
    )


def acceptance_text(window: int = DEFAULT_WINDOW) -> str:
    """Texte complet du bandeau, prêt à afficher."""
    sections = "\n\n".join(
        f"{section.title}\n{section.body}" for section in acceptance_sections(window)
    )
    return f"{ACCEPTANCE_TITLE}\n\n{sections}\n\n{ACCEPTANCE_CONFIRMATION}"


ACCEPTANCE_TEXT = acceptance_text()
