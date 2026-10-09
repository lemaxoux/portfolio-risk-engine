"""Seuils du moteur de règles, et leur provenance.

Les seuils sont le point faible de tout moteur de règles : un nombre rond fixé à
la main prend vite l'apparence d'une vérité. Ils sont donc traités explicitement,
par ordre de préférence :

1. **Pas de seuil du tout** quand la mesure parle d'elle-même. Une observation
   sans seuil porte un tuple vide ; c'est le cas de la concentration effective
   (« vos 6 lignes pèsent comme 5,7 lignes de même montant ») et de la part
   systématique.
2. **Un seuil dérivé d'une référence calculée**, comme l'équipondération 1/N ou
   la part de capital d'une ligne. Entrent aussi dans cette catégorie les seuils
   qui viennent de l'ALGÈBRE de l'estimateur et non d'une convention : le nombre
   d'observations en deçà duquel une statistique cesse d'être une mesure n'a
   pas été choisi, il se démontre (voir `MIN_ESTIMABLE_SAMPLE` et
   `historical_var_sample`).
3. **Un seuil relatif au portefeuille lui-même**, comme la corrélation de sa paire
   la plus corrélée.
4. **En dernier recours seulement, un nombre rond choisi à la main.** Le résultat
   porte alors que ce seuil a été CHOISI et non découvert : même règle de
   provenance que pour les fenêtres d'estimation et les dates de valorisation.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from enum import Enum

from backend import typography
from backend.langue import Langue
from backend.risk_engine.config import (
    DEFAULT_WINDOW,
    MAX_STUDENT_NU,
    MIN_DISTRIBUTION_OBSERVATIONS,
    MIN_ESTIMABLE_OBSERVATIONS,
    MIN_REGRESSION_OBSERVATIONS,
    MIN_SCENARIO_COVERAGE_SHARE,
    historical_var_min_observations,
    sample_std_relative_error,
)
from backend.textes import textes


class ThresholdKind(Enum):
    """D'où vient un seuil. L'ordre de déclaration est l'ordre de préférence.

    Les valeurs décrivent les catégories ; elles ne s'affichent pas. Ce que la
    ligne de seuil dit de la provenance est écrit par `Threshold.origin`, qui
    tient compte aussi du rôle : un seuil dérivé peut être une référence
    calculée sur ce portefeuille ou un seuil démontré, le même pour tous.
    """

    DERIVED = "référence calculée"
    PORTFOLIO_RELATIVE = "relatif au portefeuille"
    CHOSEN = "choisi à la main"


class ThresholdRole(Enum):
    """Ce que la valeur EST, indépendamment d'où elle vient.

    Un SEUIL est une frontière posée d'avance, la même pour tout portefeuille :
    choisi à la main (corrélation forte 0,70) ou démontré
    (`MIN_ESTIMABLE_SAMPLE`). Une RÉFÉRENCE est une valeur calculée sur CE
    portefeuille, à laquelle la mesure se compare : la part de capital d'une
    ligne, la corrélation de sa paire la plus corrélée. Appeler « seuil » une
    corrélation de 0,41 relevée sur le portefeuille la ferait passer pour une
    frontière choisie, ce qu'elle n'est pas (DESIGN.md §9.2).

    `kind` ne suffit pas à trancher : DERIVED couvre les deux cas. La valeur
    de l'énumération est l'étiquette française affichée devant la ligne, que
    `textes/fr/seuils.py` lit ici ; l'anglaise est rédigée par
    `textes/en/seuils.py`.
    """

    THRESHOLD = "Seuil"
    REFERENCE = "Référence"


@dataclass(frozen=True)
class Threshold:
    """Un seuil ou une référence, sa provenance, et la forme sous laquelle il
    s'écrit.

    `decimals` est la précision de l'ÉCRITURE, pas de la valeur : la phrase de
    l'observation et la ligne de seuil écrivent toutes deux `displayed`, si
    bien qu'un même nombre a la même forme dans un même bloc (« 0,70 » ici et
    là, et non « 0,70 » dans la phrase et « 0,7 » dessous). La valeur n'est
    jamais arrondie d'avance : `round()` tranche les égalités au pair,
    `typography` comme `toFixed`, et un double arrondi pourrait écrire
    « 0,12 » sous une phrase qui dit « 0,13 ».

    `feminine` est le genre du NOM du seuil, avec lequel s'accorde sa
    provenance : « part de JPM dans la valeur = 24,5 %, calculée sur ce
    portefeuille », mais « nombre minimal de séances estimables = 3,
    démontré ». « Choisi à la main » ne s'accorde pas : c'est la formule
    validée telle quelle, « corrélation forte = 0,70, choisi à la main ».

    ═══ DEUX LANGUES, UN SEUL FRANÇAIS ═══

    `name` et `rationale` sont le français, écrit ici et nulle part ailleurs :
    des tests les lisent, et `textes/fr/seuils.py` les lit de là (chantier
    7D). `key` nomme la déclaration de ce module qui pose le seuil, la
    constante ou la fonction qui le fabrique, et `params` ce qu'elle a reçu
    qui s'écrit dans le nom : le ticker d'une part de capital, la paire, le
    niveau d'une VaR. `textes/en/seuils.py` rédige l'anglais à partir des
    deux. Les propriétés françaises (`displayed`, `origin`, `__str__`)
    appellent la méthode qui prend la langue, avec « fr » : elles n'écrivent
    plus rien elles-mêmes.
    """

    name: str
    kind: ThresholdKind
    value: float
    decimals: int
    rationale: str
    percent: bool = False
    role: ThresholdRole = ThresholdRole.THRESHOLD
    feminine: bool = False
    _: KW_ONLY
    key: str
    params: tuple[str | float, ...] = ()

    def __post_init__(self) -> None:
        # Deux combinaisons n'ont pas de sens : une convention choisie à la
        # main n'est jamais calculée sur le portefeuille, et une valeur relative
        # au portefeuille n'est jamais une frontière posée d'avance.
        if self.kind is ThresholdKind.CHOSEN and self.role is ThresholdRole.REFERENCE:
            raise ValueError(f"{self.name} : un seuil choisi n'est pas une référence")
        if (
            self.kind is ThresholdKind.PORTFOLIO_RELATIVE
            and self.role is ThresholdRole.THRESHOLD
        ):
            raise ValueError(f"{self.name} : une valeur relative au portefeuille est une référence")

    @property
    def chosen(self) -> bool:
        """Vrai pour un seuil choisi à la main (`ThresholdKind.CHOSEN`)."""
        return self.kind is ThresholdKind.CHOSEN

    def nom(self, langue: Langue = "fr") -> str:
        """« corrélation forte », « strong correlation »."""
        return textes(langue).seuils.nom(self)

    def justification(self, langue: Langue = "fr") -> str:
        """En minuscule et sans point final, telle que publiée (`rationale`)."""
        return textes(langue).seuils.justification(self)

    def affiche(self, langue: Langue = "fr") -> str:
        """La valeur écrite, celle que la phrase de l'observation cite aussi."""
        if self.percent:
            return typography.percent(self.value, self.decimals, langue=langue)
        return typography.number(self.value, self.decimals, langue=langue)

    @property
    def displayed(self) -> str:
        """La valeur écrite en français (`affiche("fr")`)."""
        return self.affiche("fr")

    def origine(self, langue: Langue = "fr") -> str:
        """D'où vient la valeur, dit au lecteur après la virgule de la ligne :
        choisi à la main ; calculé sur ce portefeuille, pour une RÉFÉRENCE ;
        ou démontré, le même pour tout portefeuille, pour un seuil dérivé posé
        d'avance (voir `textes/fr/seuils.origine`)."""
        return textes(langue).seuils.origine(
            self.chosen, self.role is ThresholdRole.REFERENCE, self.feminine
        )

    @property
    def origin(self) -> str:
        """La provenance dite au lecteur, en français (`origine("fr")`)."""
        return self.origine("fr")

    def etiquette(self, langue: Langue = "fr") -> str:
        """« Seuil » ou « Référence », devant la ligne."""
        return textes(langue).seuils.etiquette(self.role)

    def ligne(self, langue: Langue = "fr") -> str:
        """La ligne de seuil : « corrélation forte = 0,70, choisi à la main
        (non dérivé des données). Convention usuelle… ». La valeur, puis sa
        provenance après une virgule, puis la justification en phrase. C'est
        le champ machine `kind`, pas un mot du texte, qui dit au client qu'un
        seuil est choisi."""
        return textes(langue).seuils.ligne(
            self.nom(langue),
            self.affiche(langue),
            self.origine(langue),
            self.justification(langue),
        )

    def __str__(self) -> str:
        return self.ligne("fr")


# ------------------------------------------------ Seuils choisis à la main --

STRONG_CORRELATION = Threshold(
    key="STRONG_CORRELATION",
    name="corrélation forte",
    kind=ThresholdKind.CHOSEN,
    value=0.70,
    decimals=2,  # comme toute corrélation écrite dans le projet
    rationale=(
        "convention usuelle pour qualifier une corrélation de forte ; aucun calcul "
        "sur le portefeuille ne la produit"
    ),
)

# La constante vit dans le moteur, qui publie le verdict avec chaque scénario
# (`ScenarioCoverage.sufficient`) ; le seuil — le nombre plus sa provenance —
# vit ici, comme `MIN_REGRESSION_SAMPLE`.
MIN_SCENARIO_COVERAGE = Threshold(
    key="MIN_SCENARIO_COVERAGE",
    name="couverture minimale d'un scénario",
    kind=ThresholdKind.CHOSEN,
    value=MIN_SCENARIO_COVERAGE_SHARE,
    decimals=0,
    rationale=(
        f"sous {typography.percent(MIN_SCENARIO_COVERAGE_SHARE, 0)} de la valeur, "
        "la partie rejouée ne représente plus assez l'ensemble pour en tirer un "
        "chiffre ; à "
        f"{typography.percent(MIN_SCENARIO_COVERAGE_SHARE, 0)}, même si la "
        "partie exclue avait perdu deux fois plus que la partie couverte, la perte "
        "de l'ensemble ne dépasserait le chiffre affiché que d'un cinquième, contre "
        f"moitié plus à {typography.percent(0.50, 0)}"
    ),
    percent=True,
)

MIN_REGRESSION_SAMPLE = Threshold(
    key="MIN_REGRESSION_SAMPLE",
    name="nombre minimal de séances d'une régression",
    kind=ThresholdKind.CHOSEN,
    value=float(MIN_REGRESSION_OBSERVATIONS),
    decimals=0,
    rationale=(
        "environ trois mois ; en deçà, quelques journées extrêmes dictent la pente "
        "à elles seules"
    ),
)

# Le quatrième seuil choisi, et le seul qui ne serve à aucune règle : c'est le
# MOTEUR qui l'applique, en refusant l'ajustement d'une Student
# (`engine.student_fit`), parce qu'il ne peut pas importer ce module sans
# cycle. Il est déclaré ici pour que la liste des seuils choisis à la main soit
# complète au même endroit. La constante vit dans le moteur, le seuil — le
# nombre plus sa provenance — ici, comme pour `MIN_REGRESSION_SAMPLE`.
#
# Les pourcentages de 1/√(2n) de cette justification et de la suivante sont
# calculés par la configuration du moteur (`sample_std_relative_error`), sur
# des fenêtres qu'elle nomme : écrit à la main, l'un d'eux s'en était écarté.
STUDENT_NU_CEILING = Threshold(
    key="STUDENT_NU_CEILING",
    name="ν maximal d'une loi de Student",
    kind=ThresholdKind.CHOSEN,
    value=MAX_STUDENT_NU,
    decimals=0,
    rationale=(
        "au-delà, la loi de Student ne se distingue pas de la normale : à "
        f"variance égale, sa VaR s'en écarte de {typography.percent(0.0205, 2)} "
        f"au plus à {typography.percent(0.99, 0)} et de "
        f"{typography.percent(0.0031, 2)} au plus à {typography.percent(0.95, 0)}, "
        "bien moins que l'erreur type d'un écart-type d'échantillon, environ "
        "1/√(2n) sous normalité ("
        f"{typography.percent(sample_std_relative_error(MIN_REGRESSION_OBSERVATIONS), 0)}"
        f" sur {typography.sessions(MIN_REGRESSION_OBSERVATIONS)}, "
        f"{typography.percent(sample_std_relative_error(DEFAULT_WINDOW), 1)}"
        f" sur {typography.sessions(DEFAULT_WINDOW)}) et davantage avec des queues "
        "épaisses"
    ),
)

# Le cinquième seuil choisi, appliqué lui aussi par le MOTEUR et par aucune
# règle : sous ce nombre de séances, la loi de Student n'est pas ajustée, et la
# volatilité comme la VaR paramétrique normale sont marquées minces
# (`engine._estimation_mince`). Une estimation marquée mince n'entre dans
# aucune observation : les règles ne lisent ni l'une ni l'autre.
MIN_DISTRIBUTION_SAMPLE = Threshold(
    key="MIN_DISTRIBUTION_SAMPLE",
    name="nombre minimal de séances pour estimer une loi",
    kind=ThresholdKind.CHOSEN,
    value=float(MIN_DISTRIBUTION_OBSERVATIONS),
    decimals=0,
    rationale=(
        "convention usuelle du « grand échantillon », qu'aucun calcul sur le "
        "portefeuille ne produit ; sous normalité, l'écart-type d'échantillon "
        "qui porte la volatilité et la VaR paramétrique varie d'environ "
        "1/√(2n) d'une fenêtre à l'autre ("
        f"{typography.percent(sample_std_relative_error(MIN_DISTRIBUTION_OBSERVATIONS), 0)}"
        f" sur {typography.sessions(MIN_DISTRIBUTION_OBSERVATIONS)}, "
        # Sept séances : un exemple de fenêtre très courte, cité comme tel ;
        # aucune constante du moteur ne le fixe.
        f"{typography.percent(sample_std_relative_error(7), 0)}"
        f" sur {typography.sessions(7)}), et l'ajustement d'une loi de Student "
        "repose sur une ou deux séances de queue"
    ),
)


# --------------------------------------------- Seuils calculés ou relatifs --

# Un seuil qui n'est pas une convention : il se démontre, comme celui d'une VaR
# historique (`historical_var_sample`, plus bas).
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
    key="MIN_ESTIMABLE_SAMPLE",
    name="nombre minimal de séances estimables",
    kind=ThresholdKind.DERIVED,
    value=float(MIN_ESTIMABLE_OBSERVATIONS),
    decimals=0,
    rationale=(
        "à deux observations, le centrage ne laisse qu'une seule direction : "
        "corrélation, beta et contributions à la variance s'y calculent tous à "
        "partir d'un unique écart journalier et ne portent aucune information "
        "qu'il ne porte déjà. Ce ne sont plus des statistiques bruyantes mais "
        "des identités arithmétiques"
    ),
)



def historical_var_sample(confidence: float) -> Threshold:
    """Séances minimales d'une VaR et d'une CVaR historiques au niveau
    `confidence` : 1/(1 − α), 20 à 95 %, 100 à 99 %.

    Un seuil DÉMONTRÉ, comme `MIN_ESTIMABLE_SAMPLE` : il se lit dans la
    définition du quantile. Appliqué par le moteur, déclaré ici.
    """
    return Threshold(
        key="historical_var_sample",
        params=(confidence,),
        name=(
            "nombre minimal de séances d'une VaR historique à "
            f"{typography.percent(confidence, 0)}"
        ),
        kind=ThresholdKind.DERIVED,
        value=float(historical_var_min_observations(confidence)),
        decimals=0,
        rationale=(
            "la queue au-delà du quantile compte n·(1 − α) séances ; en deçà "
            "d'une, aucune n'y tombe, et le chiffre ne serait que le pire "
            "rendement de la fenêtre, pas un quantile. La CVaR, qui moyenne "
            "cette queue, se réduirait au même minimum"
        ),
    )


def capital_share(ticker: str, weight: float) -> Threshold:
    """La part de capital d'une ligne, référence de sa part de risque."""
    return Threshold(
        key="capital_share",
        params=(ticker,),
        name=f"part de {ticker} dans la valeur",
        kind=ThresholdKind.DERIVED,
        value=weight,
        decimals=1,
        rationale=(
            "au-dessus, la ligne pèse davantage dans le risque que dans le capital ; "
            "en dessous, moins"
        ),
        percent=True,
        role=ThresholdRole.REFERENCE,
        feminine=True,  # « part … calculée sur ce portefeuille »
    )


def most_correlated_pair(first: str, second: str, correlation: float) -> Threshold:
    """La corrélation de la paire la plus corrélée, propre à ce portefeuille."""
    return Threshold(
        key="most_correlated_pair",
        params=(first, second),
        name=f"corrélation {first}–{second}",
        kind=ThresholdKind.PORTFOLIO_RELATIVE,
        value=correlation,
        decimals=2,
        rationale="corrélation de la paire la plus corrélée du portefeuille",
        role=ThresholdRole.REFERENCE,
        feminine=True,  # « corrélation … calculée sur ce portefeuille »
    )
