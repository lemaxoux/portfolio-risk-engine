"""La page méthodologie : son texte, vérifié comme les textes publiés, et
chaque nombre qu'il cite, comparé au moteur.

`frontend/src/contenu/methodologie.fr.md` est le plus gros texte du site. Il
ne passe pas par l'API, mais il ne doit pas être le seul texte que rien ne
contrôle.

═══ 1. LES GARDES EXISTANTES, PAR LEURS PROPRES EXPRESSIONS ═══

Chaque garde des textes publiés s'applique au fichier, par l'expression même
qui la porte, importée de `gardes_texte.py`, le module commun des gardes
(chantier 7D) : espace ordinaire avant « : », « ; », « ? », « ! » et dans les
guillemets, tiret cadratin, lettre grecque (hors formules : Spectral n'en a
pas), paire sécable, durée ou mois sécable, date ISO sécable ; espace sécable
avant « % » et entre un nombre et ce qu'il compte ; formulation prescriptive
et score global ; généralités sur une couverture partielle.

═══ 2. DEUX GARDES PROPRES À CE FICHIER ═══

« Séance » n'apparaît que dans une citation de l'écran ou une formule ;
ailleurs, le texte dit « jour de bourse » (DESIGN.md §15). Et chaque
citation « … » est un libellé que la page affiche, lu dans le code qui
l'affiche ou dans la réponse de l'API. La troisième, les glyphes des polices,
vit côté client (`src/contenu/methodologie.test.ts`).

═══ 3. LA LISTE FERMÉE DES NOMBRES ═══

Aucune valeur citée ne peut s'écarter du moteur sans qu'un test échoue :

1. chaque citation du moteur figure dans le fichier, écrite comme le moteur
   l'écrirait (`backend/typography.py`) : si une constante change, le texte
   attendu change, et le fichier ne le contient plus ;
2. chaque nombre du fichier, hors indices et exposants des formules (des
   rangs et des puissances), tombe dans une citation, un fragment
   mathématique déclaré ou un numéro de section : un nombre ajouté ou
   retouché à la main échoue, même s'il vaut une autre constante ;
3. un nombre tiré de la justification d'un seuil figure dans son `rationale`
   publié ;
4. un nombre écrit en lettres et suivi de ce qu'il compte (« deux ans »,
   « trois mois », « ces deux dernières années ») se vérifie comme un
   chiffre : « environ trois ans » à la place de « environ deux ans » passait.
   « Un » et « une » n'entrent pas dans cette garde : ce sont aussi des
   articles (« le rendement d'un jour », « un jour de bourse sur vingt »).

═══ 4. L'ANGLAIS (chantier 7D, session 2) ═══

`methodologie.en.md` passe les mêmes contrôles, avec les gardes anglaises de
`gardes_texte.py` : aucune espace avant « : ; ? ! », “ ” pour citer, rien
avant « % », virgule des milliers, aucune virgule décimale, aucun mot
français, aucune contraction, rien de prescriptif (`PRESCRIPTIF_EN`).
« Session » n'y apparaît que dans une citation de l'écran, comme « séance »
en français ; chaque citation “…” est un libellé de l'écran ANGLAIS, lu dans
`libelles.en.ts`, `phrases.en.ts` ou la réponse anglaise de l'API ; chaque
nombre est une constante du moteur écrite par `typography` en anglais, un
fragment déclaré ou un numéro de section. Les deux textes citent les mêmes
nombres, autant de fois : une traduction ne dit ni plus ni moins. Les tests
français ci-dessus sont ceux d'avant la traduction, inchangés ; les fonctions
qu'ils appellent prennent la langue, le français par défaut.

CE TEST LIT UN FICHIER DU CLIENT, comme `test_typographie_partagee.py` : les
constantes qu'il cite vivent dans le moteur, et c'est le moteur qui bouge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from scipy.stats import norm

from backend import typography
from backend.api.routes.analysis import CONFIDENCE_LEVELS
from backend.ingestion.universe import BACKFILL_START, BENCHMARK_NAMES, BENCHMARK_TICKER
from backend.risk_engine import config, engine
from backend.risk_engine.scenarios import SCENARIOS
from backend.rules import thresholds
from backend.rules.rules import RuleId
from backend.textes import textes

from .gardes_texte import (
    CADRATIN,
    ESPACES_AVANT_MOT,
    ESPACES_AVANT_POURCENT,
    FRANCAIS,
    GENERALITES_PAR_LANGUE,
    GREC,
    LIENS_SECABLES,
    NOMBRES_EN_LETTRES,
    NOTES_SUR_100,
    PAIRE_SECABLE,
    PONCTUATION,
    PRESCRIPTIONS,
    VIRGULE_DECIMALE,
    dates_secables,
    nombres,
)

RACINE = Path(__file__).resolve().parents[1]
CLIENT = RACINE / "frontend" / "src"
FICHIERS = {langue: CLIENT / "contenu" / f"methodologie.{langue}.md" for langue in ("fr", "en")}
FICHIER = FICHIERS["fr"]

NBSP = typography.NBSP
NNBSP = typography.NARROW_NBSP

# Les trois entités que le lecteur du client admet (`src/lib/contenu.ts`).
ENTITES = {"&nbsp;": NBSP, "&#x202F;": NNBSP, "&#x2060;": typography.WORD_JOINER}

FORMULE = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$")
INDICE = re.compile(r"[_^]\{([^}]*)\}")
# Une citation : « … » en français, “…” en anglais.
CITATIONS = {"fr": re.compile(f"«{NBSP}(.+?){NBSP}»"), "en": re.compile("“(.+?)”")}
CITATION = CITATIONS["fr"]


@dataclass(frozen=True)
class Lecture:
    """Le texte tel qu'il s'affiche, sous trois formes."""

    # Syntaxe retirée, formules en ligne, indices et exposants à leur place.
    lisible: str
    # Le même, sans les formules : ce que compose Spectral.
    prose: str
    # Le même que `lisible`, sans indices ni exposants : pour compter les nombres.
    sans_indices: str
    citations: tuple[str, ...]


def lire(source: str, langue: str = "fr") -> Lecture:
    for entite, caractere in ENTITES.items():
        source = source.replace(entite, caractere)
    inconnues = re.findall(r"&[#\w]+;", source)
    assert not inconnues, f"entités hors de la liste fermée : {inconnues}"
    texte = re.sub(r" \{#[a-z0-9-]+\}", "", source)
    texte = re.sub(r"\[([^\]]+)\]\(#[a-z0-9-]+\)", r"\1", texte)
    texte = texte.replace("**", "")
    texte = re.sub(r"^#{1,3} ", "", texte, flags=re.M)
    texte = re.sub(r"^- ", "", texte, flags=re.M)

    def formule(m: re.Match, indices: bool) -> str:
        corps = m.group(1) or m.group(2)
        return INDICE.sub(r"\1", corps) if indices else INDICE.sub("", corps)

    lisible = FORMULE.sub(lambda m: formule(m, True), texte)
    return Lecture(
        lisible=lisible,
        prose=FORMULE.sub(" ", texte),
        sans_indices=FORMULE.sub(lambda m: formule(m, False), texte),
        citations=tuple(CITATIONS[langue].findall(lisible)),
    )


@pytest.fixture(scope="module")
def source() -> str:
    return FICHIER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def source_en() -> str:
    return FICHIERS["en"].read_text(encoding="utf-8")


# ══════════════════════════════════════════ 1. Les gardes existantes ══


def fautes_de_typographie(lecture: Lecture, langue: str = "fr") -> list[str]:
    t = lecture.lisible
    # En français, l'espace ORDINAIRE avant « : ; ? ! » ; en anglais, toute
    # espace, les guillemets « » et une espace collée dans “ ”.
    nom = "espace ordinaire" if langue == "fr" else "ponctuation"
    fautes = [f"{nom} : {e!r}" for e in PONCTUATION[langue].findall(t)]
    if CADRATIN in t:
        fautes.append("tiret cadratin")
    fautes += [
        f"lettre grecque hors formule : {lecture.prose[max(0, m.start() - 20):m.end()]!r}"
        for m in GREC.finditer(lecture.prose)
    ]
    fautes += [f"paire sécable : {m.group()!r}" for m in PAIRE_SECABLE.finditer(t)]
    fautes += [f"lien sécable : {e!r}" for e in LIENS_SECABLES[langue].findall(t)]
    fautes += [f"date sécable : {d}" for d in dates_secables(t)]
    fautes += [f"espace avant % : {e!r}" for e in ESPACES_AVANT_POURCENT[langue].findall(t)]
    fautes += [f"espace avant le mot compté : {e!r}" for e in ESPACES_AVANT_MOT[langue].findall(t)]
    if langue == "en":
        fautes += [f"virgule décimale : {e!r}" for e in VIRGULE_DECIMALE.findall(t)]
        fautes += [
            f"français : {lecture.prose[max(0, m.start() - 25):m.end() + 10]!r}"
            for m in FRANCAIS.finditer(lecture.prose)
        ]
    return fautes


# Une contraction anglaise (« does not », jamais « doesn't ») : la même
# expression que les tests du client (`libelles.test.ts`). Le « 's » d'un
# possessif (« today's ») n'en est pas une.
CONTRACTION = re.compile(r"\b\w+n't\b|\b(it|that|there|what|here)'s\b|'(re|ll|ve|d)\b", re.IGNORECASE)


def fautes_de_registre(lecture: Lecture, langue: str = "fr") -> list[str]:
    t = lecture.lisible
    fautes = [
        f"prescriptif : {t[max(0, m.start() - 25):m.end() + 10]!r}"
        for m in PRESCRIPTIONS[langue].finditer(t)
    ]
    if "score" in t.lower() or NOTES_SUR_100[langue].search(t):
        fautes.append("score global")
    fautes += [f"généralité sur la couverture : {g}" for g in GENERALITES_PAR_LANGUE[langue] if g in t]
    if langue == "en":
        fautes += [f"contraction : {m.group()!r}" for m in CONTRACTION.finditer(t)]
    return fautes


def test_le_fichier_n_emploie_que_les_trois_entites(source):
    assert set(re.findall(r"&[#\w]+;", source)) <= set(ENTITES)


def test_la_typographie_suit_les_gardes_des_textes_publies(source):
    assert fautes_de_typographie(lire(source)) == []


def test_rien_de_prescriptif_aucune_note_globale_aucune_generalite(source):
    assert fautes_de_registre(lire(source)) == []


def test_la_garde_mord_sur_le_vrai_texte(source):
    """Contrôle en sens inverse : le texte CONTIENT des signes à espace
    insécable. Sans eux, les gardes vérifieraient une absence vide."""
    t = lire(source).lisible
    assert NBSP + ":" in t and NBSP + ";" in t and NBSP + "?" in t
    assert "«" + NBSP in t and NBSP + "»" in t
    assert NNBSP + "%" in t
    assert re.search(f"[0-9]{NBSP}jours de bourse", t)


# ═════════════════════════════════════ 2. Deux gardes propres au fichier ══


def fautes_de_seance(lecture: Lecture, langue: str = "fr") -> list[str]:
    """« Séance » n'apparaît que dans une citation de l'écran ou une formule ;
    « session » de même en anglais."""
    hors_citations = CITATIONS[langue].sub(" ", lecture.prose)
    mot, expression = ("séance", r"[Ss]éances?") if langue == "fr" else ("session", r"[Ss]essions?")
    return [
        f"{mot} hors citation : {hors_citations[max(0, m.start() - 30):m.end() + 10]!r}"
        for m in re.finditer(expression, hors_citations)
    ]


def test_seance_seulement_dans_une_citation_de_l_ecran(source):
    assert fautes_de_seance(lire(source)) == []


# Ce que le client affiche, lu dans le fichier qui l'écrit : depuis la 7D, les
# libellés français dans `contenu/libelles.fr.ts`.
LIBELLES_DU_CLIENT = {
    "Détails du calcul": "contenu/libelles.fr.ts",
    "Contrôle": "contenu/libelles.fr.ts",
    "Séances dans la queue": "contenu/libelles.fr.ts",
    "Valorisé au": "contenu/libelles.fr.ts",
    "non disponible": "contenu/libelles.fr.ts",
    "±": "views/SectionCrise.tsx",
    "aurait perdu": "lib/phrases.fr.ts",
}

# Pas des libellés : des exemples, cités comme tels.
EXEMPLES = {"les cinq dernières années"}


def libelles_de_l_ecran(analyse) -> set[str]:
    """Chaque libellé que la page affiche et que le texte peut citer, vérifié
    dans le code qui l'écrit ou dans la réponse de l'API."""
    for libelle, fichier in LIBELLES_DU_CLIENT.items():
        assert libelle in (CLIENT / fichier).read_text(encoding="utf-8"), (libelle, fichier)
    niveau = analyse["risk"]["tail_risk"]["levels"][0]
    detail_historique = niveau["historical_var"]["detail"]
    detail_normale = niveau["parametric_var"]["detail"]
    choisis = [t for t in vars(thresholds).values() if isinstance(t, thresholds.Threshold) and t.chosen]
    lignes = choisis + [
        thresholds.MIN_ESTIMABLE_SAMPLE,
        thresholds.historical_var_sample(0.95),
        thresholds.historical_var_sample(0.99),
    ]
    publies = {
        "interpolation 'lower'": "interpolation 'lower'" in detail_historique,
        "μ = 0": "μ = 0" in detail_normale,
        "Monte Carlo": niveau["monte_carlo_var"]["method"] == "Monte Carlo",
        "Estimation mince": engine._estimation_mince(
            engine.Window(7, 7, BACKFILL_START, BACKFILL_START)
        ).startswith("Estimation mince"),
        "grand échantillon": "« grand échantillon »" in thresholds.MIN_DISTRIBUTION_SAMPLE.rationale,
    }
    assert all(publies.values()), publies
    return (
        set(LIBELLES_DU_CLIENT)
        | set(publies)
        | {engine.period_label(config.DEFAULT_WINDOW)}
        | {regle.value for regle in RuleId}
        | {t.origin for t in lignes + [thresholds.capital_share("X", 0.1)]}
        | {f"{t.name} = {t.displayed}" for t in lignes}
    )


def fautes_de_libelles(lecture: Lecture, connus: set[str]) -> list[str]:
    return [f"citation inconnue de l'écran : {c!r}" for c in lecture.citations if c not in connus | EXEMPLES]


def test_les_libelles_cites_sont_ceux_de_l_ecran(source, analyse_reelle):
    lecture = lire(source)
    assert len(lecture.citations) > 20
    assert fautes_de_libelles(lecture, libelles_de_l_ecran(analyse_reelle.json())) == []


# ══════════════════════════════════════════ 3. La liste fermée des nombres ══

# L'exemple des lignes effectives (§ « Les lignes effectives ») : deux lignes de
# 90 % et 10 %. Ce sont des nombres d'exemple, pas d'un portefeuille ; le
# résultat est CALCULÉ ici, et écrit par `typography`.
EXEMPLE_POIDS = (0.9, 0.1)


def citations_du_moteur() -> dict[str, str]:
    """Chaque valeur que le texte cite, écrite comme le moteur l'écrirait."""

    def jours(n: float) -> str:
        return typography.counted(int(n), "jour de bourse", "jours de bourse")

    choisis = [t for t in vars(thresholds).values() if isinstance(t, thresholds.Threshold) and t.chosen]
    label, description = BENCHMARK_NAMES[BENCHMARK_TICKER]
    indice = label.removeprefix("le ")
    assert abs(sum(EXEMPLE_POIDS) - 1.0) < 1e-12
    effectives = 1.0 / sum(w * w for w in EXEMPLE_POIDS)
    citations = {
        "profondeur": typography.long_date(BACKFILL_START),
        "indice": f"{indice}, {description}",
        "nom de l'indice": indice,
        "fenêtre": jours(config.DEFAULT_WINDOW),
        "période": engine.period_label(config.DEFAULT_WINDOW),
        "durée": f"{typography.cardinal(round(config.DEFAULT_WINDOW / config.TRADING_DAYS_PER_YEAR))} ans",
        "année": jours(config.TRADING_DAYS_PER_YEAR),
        "racine de l'année": f"√{config.TRADING_DAYS_PER_YEAR}",
        "tranches": typography.number(config.HISTOGRAM_BIN_WIDTH * 100, 2) + NBSP + "point",
        "tranches en %": typography.percent(config.HISTOGRAM_BIN_WIDTH, 2),
        "tirages": typography.grouped(config.MONTE_CARLO_SIMULATIONS, "tirage"),
        "loi : jours": jours(config.MIN_DISTRIBUTION_OBSERVATIONS),
        "Student : degrés": typography.number(config.MAX_STUDENT_NU, 0) + NBSP + "degrés de liberté",
        "régression": jours(config.MIN_REGRESSION_OBSERVATIONS),
        "estimables": jours(config.MIN_ESTIMABLE_OBSERVATIONS),
        "corrélation forte": thresholds.STRONG_CORRELATION.displayed,
        "couverture": thresholds.MIN_SCENARIO_COVERAGE.displayed,
        "seuils choisis": f"{typography.cardinal(len(choisis))} seuils choisis à la main",
        "nombre de seuils choisis": f"Ils sont {typography.cardinal(len(choisis))} dans tout l'outil",
        "crises": f"les {typography.cardinal(len(SCENARIOS))} crises que l'outil rejoue",
        "crises rejouées": f"rejoue {typography.cardinal(len(SCENARIOS))} grandes crises",
        "exemple": (
            f"deux lignes de {typography.percent(EXEMPLE_POIDS[0], 0)} et "
            f"{typography.percent(EXEMPLE_POIDS[1], 0)} de la valeur pèsent comme "
            + typography.counted(effectives, "ligne", affiche=typography.number(effectives, 1))
        ),
    }
    for niveau in CONFIDENCE_LEVELS:
        citations[f"niveau {niveau}"] = typography.percent(niveau, 0)
        citations[f"queue {niveau}"] = typography.percent(round(1.0 - niveau, 9), 0)
        citations[f"VaR historique {niveau} : jours"] = jours(config.historical_var_min_observations(niveau))
        citations[f"quantile normal {niveau}"] = typography.number(-norm.ppf(1.0 - niveau), 3)
    for scenario in SCENARIOS:
        citations[f"crise {scenario.key}"] = scenario.name
    for seuil in choisis + [
        thresholds.MIN_ESTIMABLE_SAMPLE,
        thresholds.historical_var_sample(0.95),
        thresholds.historical_var_sample(0.99),
    ]:
        citations[f"ligne {seuil.name}"] = f"{seuil.name} = {seuil.displayed}"
    # Tirés de la justification publiée d'un seuil : ils doivent y figurer.
    for extrait, seuil in (
        (typography.percent(0.50, 0), thresholds.MIN_SCENARIO_COVERAGE),
        ("deux fois plus", thresholds.MIN_SCENARIO_COVERAGE),
        ("d'un cinquième", thresholds.MIN_SCENARIO_COVERAGE),
        ("moitié plus", thresholds.MIN_SCENARIO_COVERAGE),
        ("environ trois mois", thresholds.MIN_REGRESSION_SAMPLE),
        (typography.percent(0.0205, 2), thresholds.STUDENT_NU_CEILING),
        (typography.percent(0.13, 0), thresholds.MIN_DISTRIBUTION_SAMPLE),
    ):
        assert extrait in seuil.rationale, (extrait, seuil.name)
        citations[f"justification {extrait}"] = extrait
    return citations


# Ni constantes du moteur ni données : des mathématiques, écrites telles
# qu'elles s'affichent une fois indices et exposants retirés.
FRAGMENTS_MATHEMATIQUES = (
    "1 − α",  # la part des jours au-delà du quantile
    "1 / (1 − α)",  # le minimum démontré d'une VaR historique
    "n × (1 − α)",
    "(1 + r)",  # composer un rendement
    "ln(1 + r)",
    "ln(1 + R)",
    "− 1",  # un rendement, rapport de deux valeurs moins un
    "1 / (",  # l'inverse d'une somme de carrés
    "(ν − 2)",  # la variance d'une loi de Student
    "n − 1",  # l'écart-type d'échantillon
    "de −1 à +1",  # les bornes d'une corrélation
    "+1 si",
    "0 sans",
    "−1 toujours",
    "+1 ou −1",
    "100" + NNBSP + "%",  # les parts somment à l'ensemble
    "de 1" + NNBSP + "%",  # l'unité d'une sensibilité
    "part de 1 ",  # la base de la courbe de valeur
    "2" + NBSP + "degrés de liberté",  # une variance finie demande plus de deux
    "μ = 0",
    "entre deux jours",  # le quantile tombe entre deux jours observés
    "avec deux jours",  # une corrélation y vaut +1 ou −1, quelles que soient les lignes
)

# Des nombres écrits en lettres qui ne sont ni des constantes ni des données :
# des exemples, cités comme tels (chantier 7D, garde des nombres en lettres).
EXEMPLES_EN_LETTRES = (
    "sept jours",  # une volatilité « estimée sur deux ans ou sur sept jours »
    "un ou deux jours",  # une loi de Student « reposerait sur un ou deux jours extrêmes »
)

STRUCTURE = tuple(f"section {n}" for n in range(1, 7))


def fautes_de_nombres(lecture: Lecture, citations: dict[str, str], langue: str = "fr") -> list[str]:
    t = lecture.sans_indices
    couvert = [False] * len(t)
    fautes = []
    for nom, attendu in citations.items():
        trouvees = list(re.finditer(re.escape(attendu), t))
        if not trouvees:
            fautes.append(f"citation absente, le moteur a-t-il changé ? {nom} : {attendu!r}")
        for m in trouvees:
            couvert[m.start():m.end()] = [True] * (m.end() - m.start())
    for fragment in DECLARES[langue]:
        for m in re.finditer(re.escape(fragment), t):
            couvert[m.start():m.end()] = [True] * (m.end() - m.start())
    for m in re.finditer(r"[0-9]+", t):
        if not all(couvert[m.start():m.end()]):
            fautes.append(f"nombre non déclaré : {t[max(0, m.start() - 25):m.end() + 15]!r}")
    # Le nombre lui-même, groupe 1 de l'expression : « trois » dans « environ
    # trois ans ». « Un » et « une » n'y entrent pas (voir `gardes_texte.py`).
    for m in NOMBRES_EN_LETTRES[langue].finditer(t):
        if not all(couvert[m.start(1):m.end(1)]):
            fautes.append(f"nombre en lettres non déclaré : {t[max(0, m.start() - 25):m.end() + 15]!r}")
    return fautes


def test_chaque_nombre_est_une_constante_du_moteur_ou_un_fragment_declare(source):
    assert fautes_de_nombres(lire(source), citations_du_moteur()) == []


def test_un_changement_du_moteur_fait_echouer_la_liste(source, monkeypatch):
    """Témoin : la liste lit le moteur à chaque appel."""
    monkeypatch.setattr(config, "MIN_REGRESSION_OBSERVATIONS", 90)
    fautes = fautes_de_nombres(lire(source), citations_du_moteur())
    assert any("citation absente" in f and "90" in f for f in fautes), fautes


# ═══════════════════════════════════════════════════ Les gardes mordent ══

TEMOINS = (
    ("corrélation forte = 0,70", "corrélation forte = 0,75", "nombre non déclaré"),
    ("1,2&nbsp;ligne", "1,3&nbsp;ligne", "nombre non déclaré"),
    ("environ trois mois", "environ 63 jours", "nombre non déclaré"),
    ("500 grandes entreprises", "400 grandes entreprises", "citation absente"),
    ("perd-on en moyenne&nbsp;?", "perd-on en moyenne ?", "espace ordinaire"),
    ("Il ne dit jamais quoi en faire", "Il faut alléger la ligne", "prescriptif"),
    ("aucune note globale", "aucun score global", "score global"),
    ("$ν$ (la lettre grecque nu)", "ν (la lettre grecque nu)", "lettre grecque hors formule"),
    ("«&nbsp;Séances dans la queue&nbsp;»", "les séances dans la queue", "séance hors citation"),
    ("252&nbsp;jours de bourse", "252 jours de bourse", "lien sécable"),
    ("environ deux ans", "environ trois ans", "nombre en lettres non déclaré"),
)


@pytest.mark.parametrize("avant, apres, attendue", TEMOINS, ids=[t[2] + " " + t[1][:24] for t in TEMOINS])
def test_chaque_garde_mord_sur_un_texte_fautif(source, avant, apres, attendue):
    assert source.count(avant) >= 1, avant
    lecture = lire(source.replace(avant, apres, 1))
    fautes = (
        fautes_de_typographie(lecture)
        + fautes_de_registre(lecture)
        + fautes_de_seance(lecture)
        + fautes_de_nombres(lecture, citations_du_moteur())
    )
    assert any(attendue in f for f in fautes), fautes


def test_la_garde_des_libelles_mord(source, analyse_reelle):
    lecture = lire(source.replace("Détails du calcul", "Détail du calcul", 1))
    fautes = fautes_de_libelles(lecture, libelles_de_l_ecran(analyse_reelle.json()))
    assert fautes == ["citation inconnue de l'écran : 'Détail du calcul'"]


# ════════════════════════════════════════════════════ 4. L'anglais ══
#
# Les mêmes contrôles sur `methodologie.en.md`, avec ce que l'anglais cite et
# déclare : les libellés de l'écran anglais, les constantes écrites par
# `typography` en anglais.

LIBELLES_DU_CLIENT_EN = {
    "Calculation details": "contenu/libelles.en.ts",
    "Cross-check": "contenu/libelles.en.ts",
    "Sessions in the tail": "contenu/libelles.en.ts",
    "Valued as of": "contenu/libelles.en.ts",
    "not available": "contenu/libelles.en.ts",
    "±": "views/SectionCrise.tsx",
    "would have lost": "lib/phrases.en.ts",
}

EXEMPLES_EN = {"the past five years"}


def libelles_de_l_ecran_en(analyse) -> set[str]:
    """Chaque libellé de l'écran anglais que le texte peut citer, vérifié dans
    le code qui l'écrit ou dans la réponse anglaise de l'API."""
    for libelle, fichier in LIBELLES_DU_CLIENT_EN.items():
        assert libelle in (CLIENT / fichier).read_text(encoding="utf-8"), (libelle, fichier)
    niveau = analyse["risk"]["tail_risk"]["levels"][0]
    detail_historique = niveau["historical_var"]["detail"]
    detail_normale = niveau["parametric_var"]["detail"]
    choisis = [t for t in vars(thresholds).values() if isinstance(t, thresholds.Threshold) and t.chosen]
    lignes = choisis + [
        thresholds.MIN_ESTIMABLE_SAMPLE,
        thresholds.historical_var_sample(0.95),
        thresholds.historical_var_sample(0.99),
    ]
    publies = {
        "'lower' interpolation": "'lower' interpolation" in detail_historique,
        "μ = 0": "μ = 0" in detail_normale,
        "Monte Carlo": niveau["monte_carlo_var"]["method"] == "Monte Carlo",
        "Small-sample estimate": engine._estimation_mince(
            engine.Window(7, 7, BACKFILL_START, BACKFILL_START), "en"
        ).startswith("Small-sample estimate"),
        "large sample": "“large sample”" in thresholds.MIN_DISTRIBUTION_SAMPLE.justification("en"),
    }
    assert all(publies.values()), publies
    return (
        set(LIBELLES_DU_CLIENT_EN)
        | set(publies)
        | {engine.period_label(config.DEFAULT_WINDOW, "en")}
        | {textes("en").regles.libelle(regle) for regle in RuleId}
        | {t.origine("en") for t in lignes + [thresholds.capital_share("X", 0.1)]}
        | {f"{t.nom('en')} = {t.affiche('en')}" for t in lignes}
    )


def citations_du_moteur_en() -> dict[str, str]:
    """Chaque valeur que le texte anglais cite, écrite comme le moteur
    l'écrirait en anglais. Les mêmes clés qu'en français, sauf les extraits
    des justifications, qui sont les mots anglais."""

    def jours(n: float) -> str:
        return typography.counted(int(n), "trading day", "trading days", langue="en")

    def en_lettres(n: int) -> str:
        return typography.cardinal(n, langue="en")

    choisis = [t for t in vars(thresholds).values() if isinstance(t, thresholds.Threshold) and t.chosen]
    label, description = textes("en").moteur.NOMS_D_INDICE[BENCHMARK_TICKER]
    indice = label.removeprefix("the ")
    effectives = 1.0 / sum(w * w for w in EXEMPLE_POIDS)
    largeur = config.HISTOGRAM_BIN_WIDTH * 100
    citations = {
        "profondeur": typography.long_date(BACKFILL_START, langue="en"),
        "indice": f"{indice}, {description}",
        "nom de l'indice": indice,
        "fenêtre": jours(config.DEFAULT_WINDOW),
        "période": engine.period_label(config.DEFAULT_WINDOW, "en"),
        "durée": f"{en_lettres(round(config.DEFAULT_WINDOW / config.TRADING_DAYS_PER_YEAR))} years",
        "année": jours(config.TRADING_DAYS_PER_YEAR),
        "racine de l'année": f"√{config.TRADING_DAYS_PER_YEAR}",
        "tranches": typography.counted(
            largeur, "point", affiche=typography.number(largeur, 2, langue="en"), langue="en"
        ),
        "tranches en %": typography.percent(config.HISTOGRAM_BIN_WIDTH, 2, langue="en"),
        "tirages": typography.grouped(config.MONTE_CARLO_SIMULATIONS, "draw", langue="en"),
        "loi : jours": jours(config.MIN_DISTRIBUTION_OBSERVATIONS),
        "Student : degrés": typography.number(config.MAX_STUDENT_NU, 0, langue="en")
        + NBSP
        + "degrees of freedom",
        "régression": jours(config.MIN_REGRESSION_OBSERVATIONS),
        "estimables": jours(config.MIN_ESTIMABLE_OBSERVATIONS),
        "corrélation forte": thresholds.STRONG_CORRELATION.affiche("en"),
        "couverture": thresholds.MIN_SCENARIO_COVERAGE.affiche("en"),
        "seuils choisis": f"{en_lettres(len(choisis))} thresholds chosen by hand",
        "nombre de seuils choisis": f"There are {en_lettres(len(choisis))} in the whole tool",
        "crises": f"the {en_lettres(len(SCENARIOS))} crises that the tool replays",
        "crises rejouées": f"replays {en_lettres(len(SCENARIOS))} major crises",
        "exemple": (
            f"two holdings of {typography.percent(EXEMPLE_POIDS[0], 0, langue='en')} and "
            f"{typography.percent(EXEMPLE_POIDS[1], 0, langue='en')} of the value weigh like "
            + typography.counted(
                effectives,
                "equal-sized holding",
                affiche=typography.number(effectives, 1, langue="en"),
                langue="en",
            )
        ),
    }
    for niveau in CONFIDENCE_LEVELS:
        citations[f"niveau {niveau}"] = typography.percent(niveau, 0, langue="en")
        citations[f"queue {niveau}"] = typography.percent(round(1.0 - niveau, 9), 0, langue="en")
        citations[f"VaR historique {niveau} : jours"] = jours(config.historical_var_min_observations(niveau))
        citations[f"quantile normal {niveau}"] = typography.number(-norm.ppf(1.0 - niveau), 3, langue="en")
    for scenario in SCENARIOS:
        citations[f"crise {scenario.key}"] = scenario.nom("en")
    for seuil in choisis + [
        thresholds.MIN_ESTIMABLE_SAMPLE,
        thresholds.historical_var_sample(0.95),
        thresholds.historical_var_sample(0.99),
    ]:
        citations[f"ligne {seuil.name}"] = f"{seuil.nom('en')} = {seuil.affiche('en')}"
    # Tirés de la justification publiée d'un seuil, en anglais : ils doivent y
    # figurer.
    for extrait, seuil in (
        (typography.percent(0.50, 0, langue="en"), thresholds.MIN_SCENARIO_COVERAGE),
        ("twice as much", thresholds.MIN_SCENARIO_COVERAGE),
        ("by only a fifth", thresholds.MIN_SCENARIO_COVERAGE),
        ("a half", thresholds.MIN_SCENARIO_COVERAGE),
        ("about three months", thresholds.MIN_REGRESSION_SAMPLE),
        (typography.percent(0.0205, 2, langue="en"), thresholds.STUDENT_NU_CEILING),
        (typography.percent(0.13, 0, langue="en"), thresholds.MIN_DISTRIBUTION_SAMPLE),
    ):
        assert extrait in seuil.justification("en"), (extrait, seuil.name)
        citations[f"justification {extrait}"] = extrait
    return citations


# Les mêmes fragments qu'en français, dans les mots anglais.
FRAGMENTS_MATHEMATIQUES_EN = (
    "1 − α",
    "1 / (1 − α)",
    "n × (1 − α)",
    "(1 + r)",
    "ln(1 + r)",
    "ln(1 + R)",
    "− 1",
    "1 / (",
    "(ν − 2)",
    "n − 1",
    "from −1 to +1",
    "+1 if",
    "0 with no",
    "−1 always",
    "+1 or −1",
    "100%",
    "by 1%",
    "starts at 1 ",
    "2" + NBSP + "degrees of freedom",
    "μ = 0",
    "between two days",
    "with two days",
)

EXEMPLES_EN_LETTRES_EN = ("seven days",)  # « estimated over two years or over seven days »

# En tête de phrase, la section prend sa capitale : « Section 5 replays… ».
STRUCTURE_EN = tuple(f"{s}ection {n}" for s in ("s", "S") for n in range(1, 7))

# Ce que chaque langue déclare, hors des citations du moteur.
DECLARES = {
    "fr": FRAGMENTS_MATHEMATIQUES + STRUCTURE + EXEMPLES_EN_LETTRES + tuple(EXEMPLES),
    "en": FRAGMENTS_MATHEMATIQUES_EN + STRUCTURE_EN + EXEMPLES_EN_LETTRES_EN + tuple(EXEMPLES_EN),
}


def test_en_anglais_le_fichier_n_emploie_que_les_trois_entites(source_en):
    assert set(re.findall(r"&[#\w]+;", source_en)) <= set(ENTITES)


def test_en_anglais_la_typographie_suit_les_gardes_anglaises(source_en):
    assert fautes_de_typographie(lire(source_en, "en"), "en") == []


def test_en_anglais_rien_de_prescriptif_aucune_note_globale_aucune_contraction(source_en):
    assert fautes_de_registre(lire(source_en, "en"), "en") == []


def test_en_anglais_la_garde_mord_sur_le_vrai_texte(source_en):
    """Contrôle en sens inverse, comme en français : le texte anglais contient
    de la ponctuation haute collée au mot, des guillemets “ ”, un « % » collé
    au nombre, une espace insécable avant « trading days »."""
    t = lire(source_en, "en").lisible
    assert re.search(r"[a-z]: ", t) and re.search(r"[a-z]; ", t) and re.search(r"[a-z]\? ", t)
    assert "“" in t and "”" in t
    assert re.search(r"[0-9]%", t)
    assert re.search(f"[0-9]{NBSP}trading days", t)


def test_en_anglais_session_seulement_dans_une_citation_de_l_ecran(source_en):
    assert fautes_de_seance(lire(source_en, "en"), "en") == []


def test_en_anglais_les_libelles_cites_sont_ceux_de_l_ecran_anglais(source_en, analyse_reelle_en):
    lecture = lire(source_en, "en")
    assert len(lecture.citations) > 20
    connus = libelles_de_l_ecran_en(analyse_reelle_en.json()) | EXEMPLES_EN
    assert fautes_de_libelles(lecture, connus) == []


def test_en_anglais_chaque_nombre_est_une_constante_du_moteur_ou_un_fragment_declare(source_en):
    assert fautes_de_nombres(lire(source_en, "en"), citations_du_moteur_en(), "en") == []


def test_en_anglais_un_changement_du_moteur_fait_echouer_la_liste(source_en, monkeypatch):
    monkeypatch.setattr(config, "MIN_REGRESSION_OBSERVATIONS", 90)
    fautes = fautes_de_nombres(lire(source_en, "en"), citations_du_moteur_en(), "en")
    assert any("citation absente" in f and "90" in f for f in fautes), fautes


def test_les_deux_langues_citent_les_memes_nombres_autant_de_fois(source, source_en):
    """Une traduction ne dit ni plus ni moins : les deux textes, formules
    comprises et indices retirés, écrivent les mêmes nombres, chacun autant de
    fois (`gardes_texte.nombres` ramène « 1 645,5 » et « 1,645.5 » à une
    même écriture). Les nombres en lettres se relisent dans le tableau du
    rapport."""
    francais = nombres(lire(source).sans_indices, "fr")
    anglais = nombres(lire(source_en, "en").sans_indices, "en")
    assert anglais == francais


def test_les_citations_du_moteur_ont_les_memes_nombres_dans_les_deux_langues():
    francaises = citations_du_moteur()
    anglaises = citations_du_moteur_en()
    communes = [nom for nom in francaises if nom in anglaises]
    assert len(communes) == len(francaises) - 7  # les sept extraits de justification
    for nom in communes:
        assert nombres(anglaises[nom], "en") == nombres(francaises[nom], "fr"), nom


TEMOINS_EN = (
    ("strong correlation = 0.70", "strong correlation = 0.75", "nombre non déclaré"),
    ("1.2&nbsp;equal-sized", "1.3&nbsp;equal-sized", "nombre non déclaré"),
    ("about three months", "about 63 days", "nombre non déclaré"),
    ("500 large US companies", "400 large US companies", "citation absente"),
    ("how much is lost on average?", "how much is lost on average ?", "ponctuation"),
    ("It never says what to do with it", "You should trim the holding", "prescriptif"),
    ("no overall rating", "no overall score", "score global"),
    ("$ν$ (the Greek letter nu)", "ν (the Greek letter nu)", "lettre grecque hors formule"),
    ("“Sessions in the tail”", "the sessions in the tail", "session hors citation"),
    ("252&nbsp;trading days", "252 trading days", "lien sécable"),
    ("about two years", "about three years", "nombre en lettres non déclaré"),
    # Propres à l'anglais.
    ("“Calculation details”", "«&nbsp;Calculation details&nbsp;»", "ponctuation"),
    ("January&nbsp;1,&nbsp;2005", "January&nbsp;1, 2005", "lien sécable"),
    ("does not say the same thing", "doesn't say the same thing", "contraction"),
    ("0.25&nbsp;points", "0,25&nbsp;points", "virgule décimale"),
    ("Why there is no overall rating", "Pourquoi aucune note globale", "français"),
)


@pytest.mark.parametrize(
    "avant, apres, attendue", TEMOINS_EN, ids=[t[2] + " " + t[1][:24] for t in TEMOINS_EN]
)
def test_en_anglais_chaque_garde_mord_sur_un_texte_fautif(source_en, avant, apres, attendue):
    assert source_en.count(avant) >= 1, avant
    lecture = lire(source_en.replace(avant, apres, 1), "en")
    fautes = (
        fautes_de_typographie(lecture, "en")
        + fautes_de_registre(lecture, "en")
        + fautes_de_seance(lecture, "en")
        + fautes_de_nombres(lecture, citations_du_moteur_en(), "en")
    )
    assert any(attendue in f for f in fautes), fautes


def test_en_anglais_la_garde_des_libelles_mord(source_en, analyse_reelle_en):
    lecture = lire(source_en.replace("Calculation details", "Calculation detail", 1), "en")
    connus = libelles_de_l_ecran_en(analyse_reelle_en.json()) | EXEMPLES_EN
    assert fautes_de_libelles(lecture, connus) == ["citation inconnue de l'écran : 'Calculation detail'"]
