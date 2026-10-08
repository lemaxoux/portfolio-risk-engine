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

from .gardes_texte import (
    CADRATIN,
    ESPACE_AVANT_MOT,
    ESPACE_AVANT_POURCENT,
    ESPACE_ORDINAIRE,
    GENERALITES,
    GREC,
    LIEN_SECABLE,
    NOMBRE_EN_LETTRES,
    PAIRE_SECABLE,
    PRESCRIPTIF,
    SCORE_SUR_100,
    dates_secables,
)

RACINE = Path(__file__).resolve().parents[1]
CLIENT = RACINE / "frontend" / "src"
FICHIER = CLIENT / "contenu" / "methodologie.fr.md"

NBSP = typography.NBSP
NNBSP = typography.NARROW_NBSP

# Les trois entités que le lecteur du client admet (`src/lib/contenu.ts`).
ENTITES = {"&nbsp;": NBSP, "&#x202F;": NNBSP, "&#x2060;": typography.WORD_JOINER}

FORMULE = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$")
INDICE = re.compile(r"[_^]\{([^}]*)\}")
CITATION = re.compile(f"«{NBSP}(.+?){NBSP}»")


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


def lire(source: str) -> Lecture:
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
        citations=tuple(CITATION.findall(lisible)),
    )


@pytest.fixture(scope="module")
def source() -> str:
    return FICHIER.read_text(encoding="utf-8")


# ══════════════════════════════════════════ 1. Les gardes existantes ══


def fautes_de_typographie(lecture: Lecture) -> list[str]:
    t = lecture.lisible
    fautes = [f"espace ordinaire : {e!r}" for e in ESPACE_ORDINAIRE.findall(t)]
    if CADRATIN in t:
        fautes.append("tiret cadratin")
    fautes += [
        f"lettre grecque hors formule : {lecture.prose[max(0, m.start() - 20):m.end()]!r}"
        for m in GREC.finditer(lecture.prose)
    ]
    fautes += [f"paire sécable : {m.group()!r}" for m in PAIRE_SECABLE.finditer(t)]
    fautes += [f"lien sécable : {e!r}" for e in LIEN_SECABLE.findall(t)]
    fautes += [f"date sécable : {d}" for d in dates_secables(t)]
    fautes += [f"espace avant % : {e!r}" for e in ESPACE_AVANT_POURCENT.findall(t)]
    fautes += [f"espace avant le mot compté : {e!r}" for e in ESPACE_AVANT_MOT.findall(t)]
    return fautes


def fautes_de_registre(lecture: Lecture) -> list[str]:
    t = lecture.lisible
    fautes = [
        f"prescriptif : {t[max(0, m.start() - 25):m.end() + 10]!r}"
        for m in PRESCRIPTIF.finditer(t)
    ]
    if "score" in t.lower() or SCORE_SUR_100.search(t):
        fautes.append("score global")
    fautes += [f"généralité sur la couverture : {g}" for g in GENERALITES if g in t]
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


def fautes_de_seance(lecture: Lecture) -> list[str]:
    """« Séance » n'apparaît que dans une citation de l'écran ou une formule."""
    hors_citations = CITATION.sub(" ", lecture.prose)
    return [
        f"séance hors citation : {hors_citations[max(0, m.start() - 30):m.end() + 10]!r}"
        for m in re.finditer(r"[Ss]éances?", hors_citations)
    ]


def test_seance_seulement_dans_une_citation_de_l_ecran(source):
    assert fautes_de_seance(lire(source)) == []


# Ce que le client affiche, lu dans le fichier qui l'écrit.
LIBELLES_DU_CLIENT = {
    "Détails du calcul": "components/Measure.tsx",
    "Contrôle": "lib/provenance.ts",
    "Séances dans la queue": "lib/provenance.ts",
    "Valorisé au": "lib/provenance.ts",
    "non disponible": "components/Absent.tsx",
    "±": "views/SectionCrise.tsx",
    "aurait perdu": "lib/phrases.ts",
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


def fautes_de_nombres(lecture: Lecture, citations: dict[str, str]) -> list[str]:
    t = lecture.sans_indices
    couvert = [False] * len(t)
    fautes = []
    for nom, attendu in citations.items():
        trouvees = list(re.finditer(re.escape(attendu), t))
        if not trouvees:
            fautes.append(f"citation absente, le moteur a-t-il changé ? {nom} : {attendu!r}")
        for m in trouvees:
            couvert[m.start():m.end()] = [True] * (m.end() - m.start())
    for fragment in FRAGMENTS_MATHEMATIQUES + STRUCTURE + EXEMPLES_EN_LETTRES + tuple(EXEMPLES):
        for m in re.finditer(re.escape(fragment), t):
            couvert[m.start():m.end()] = [True] * (m.end() - m.start())
    for m in re.finditer(r"[0-9]+", t):
        if not all(couvert[m.start():m.end()]):
            fautes.append(f"nombre non déclaré : {t[max(0, m.start() - 25):m.end() + 15]!r}")
    # Le nombre lui-même, groupe 1 de l'expression : « trois » dans « environ
    # trois ans ». « Un » et « une » n'y entrent pas (voir `gardes_texte.py`).
    for m in NOMBRE_EN_LETTRES.finditer(t):
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
