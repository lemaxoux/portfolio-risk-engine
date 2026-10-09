"""Les documents publics du dépôt, en anglais : leurs nombres, leurs résultats
datés et leurs gardes (phase 8).

`README.md`, `METHODOLOGY.md` et `ARCHITECTURE.md` font foi pour un lecteur du
dépôt ; le code, ses commentaires, ses tests, CLAUDE.md et DESIGN.md restent en
français. Ce fichier tient trois choses.

═══ 1. AUCUN CHIFFRE VIVANT ═══

Un nombre de tests, une taille de bundle, la VaR du portefeuille de
démonstration se périment au commit ou au rafraîchissement suivant. Comme dans
la méthodologie du site (`test_methodologie.py`), chaque nombre d'un document
tombe dans une liste fermée :

* une constante du code, lue là où elle vit et écrite par `typography` en
  anglais : si elle change, le document ne la contient plus et le test échoue ;
* un fait de marché du catalogue des crises (la baisse du S&P 500, le nombre de
  séances), recalculé sur la copie figée ;
* un fragment déclaré : une formule, une durée, un exemple, chacun avec sa
  raison et, quand il en a une, la source où ce test le relit ;
* une citation d'un résultat daté, dans le bloc de ce résultat seulement.

Les nombres d'un bloc de code, d'un code en ligne ou d'une adresse ne sont pas
de la prose : ils ne sont pas lus.

═══ 2. LES QUATRE RÉSULTATS DATÉS ═══

Encadrés dans le Markdown par `<!-- dated: clé -->` et `<!-- /dated -->`,
commentaires que GitHub n'affiche pas. Chaque bloc porte son cadre
(portefeuille, date de valorisation, fenêtre) et ses chiffres, recalculés ici
sur une copie de la base figée au `DATE_GEL` (`copier_base_reelle_figee`, le
seul accès qu'admet `test_gel_des_tests.py`). METHODOLOGY.md donne chaque
résultat en entier ; un chiffre daté n'apparaît que dans les blocs de sa clé.
Une seule valeur ne vient pas de la copie figée : le rendement que la base
stockait pour KO avant le correctif, lu dans la sauvegarde d'avant la
réparation et recopié ici (`KO_ADJ_CLOSE_AVANT_CORRECTIF`).

Les affirmations qui accompagnent les chiffres (le beta calme a sous-estimé la
perte en 2008, JPM a coûté dans chaque crise…) se vérifient sur les mêmes
résultats.

═══ 3. LES GARDES ANGLAISES ═══

Celles des textes publiés (`gardes_texte.py`) : aucun tiret cadratin, aucune
contraction, aucune note globale, aucune virgule décimale, rien avant « % »,
aucune ponctuation à la française, aucune généralité que le moteur ne mesure
pas, jamais « expected loss ». La garde prescriptive s'applique aussi, avec une
liste fermée de PHRASES entières (`EXCEPTIONS_PRESCRIPTIVES`) limitée à deux
cas : la description de la convention des poids constants (le rééquilibrage
quotidien) et les phrases qui disent ce que l'outil refuse de dire. Un mot
gardé hors de ces phrases échoue toujours, et chaque exception doit être une
phrase entière, présente une fois, et nécessaire.

Les règles propres à l'écran ne s'appliquent pas : l'espace insécable entre un
nombre et ce qu'il compte, la date insécable, la lettre grecque hors d'une
formule. Un fichier Markdown lu sur GitHub n'est pas composé en Spectral, et
ses lignes ne sont pas coupées par la page.

SANS BASE LOCALE, la partie qui lit la copie figée est ignorée, comme tout test
sur cours réels ; les gardes tournent quand même.
"""

from __future__ import annotations

import math
import re
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
import scipy
from scipy.stats import norm
from scipy.stats import t as student_t

from backend import typography
from backend.api.routes.analysis import CONFIDENCE_LEVELS
from backend.db.init_db import connect
from backend.ingestion.universe import BACKFILL_START, BENCHMARK_TICKER
from backend.risk_engine import config, covariance, engine, var
from backend.risk_engine.scenarios import SCENARIOS, SCENARIOS_BY_KEY
from backend.rules import thresholds
from backend.rules.rules import RuleId
from backend.textes import textes

from .conftest import DATE_GEL, PORTEFEUILLE_DEMO, copier_base_reelle_figee
from .gardes_texte import (
    CADRATIN,
    ESPACE_AVANT_POURCENT_EN,
    GENERALITES_EN,
    NOMBRE_EN_LETTRES_EN,
    PONCTUATION_EN,
    PRESCRIPTIF_EN,
    SCORE_SUR_100_EN,
    VIRGULE_DECIMALE,
)
from .test_methodologie import CONTRACTION, FORMULE, INDICE

RACINE = Path(__file__).resolve().parents[1]

# Les documents publics, dans l'ordre où les lots de la phase 8 les créent.
DOCUMENTS = ("METHODOLOGY.md",)

EN = "en"

# ═══════════════════════════════════════════════ Le rendement stocké de KO ══
#
# Lus le 2026-10-09, en lecture seule, dans une COPIE de la sauvegarde que
# `python -m backend.ingestion rebuild` a posée avant de réparer la base :
# fichier data/backup-2026-09-28.sqlite, table `prices`, ticker KO, colonne
# `adj_close`, séances du 2026-09-08 et du 2026-09-09. Aucun test n'ouvre cette
# sauvegarde (`test_gel_des_tests.py`) : les deux valeurs sont recopiées ici, et
# le rendement stocké se recalcule depuis elles.
#
# Le 2026-09-08 n'avait pas été réajusté (88,36, égal au cours brut) ; le
# 2026-09-09 l'avait été, par le rattrapage, d'après un dividende détaché plus
# tard. La séance de jonction comptait ce réajustement comme une perte.
DATE_SAUVEGARDE = date(2026, 9, 28)
KO_ADJ_CLOSE_AVANT_CORRECTIF = {
    date(2026, 9, 8): 88.36,
    date(2026, 9, 9): 87.0300369789,
}


# ════════════════════════════════════════════════════════════ L'écriture ══


def ecrit(texte: str) -> str:
    """Une chaîne de `typography` telle qu'elle se lit dans un fichier
    Markdown : les espaces insécables y sont des espaces, et le caractère de
    liaison disparaît (voir l'en-tête : la page n'y coupe aucune ligne)."""
    return (
        texte.replace(typography.NBSP, " ")
        .replace(typography.NARROW_NBSP, " ")
        .replace(typography.WORD_JOINER, "")
    )


def jour(d: date) -> str:
    """« September 9, 2026 »."""
    return ecrit(typography.long_date(d, langue=EN))


def seances(n: int) -> str:
    """« 504 sessions »."""
    return ecrit(typography.counted(n, "session", langue=EN))


def jours_de_bourse(n: int) -> str:
    """« 504 trading days », le registre du README."""
    return ecrit(typography.counted(n, "trading day", "trading days", langue=EN))


def nombre(x: float, decimales: int, *, signe: bool = False) -> str:
    return ecrit(typography.number(x, decimales, signed=signe, langue=EN))


def pourcent(x: float, decimales: int = 1, *, signe: bool = False) -> str:
    return ecrit(typography.percent(x, decimales, signed=signe, langue=EN))


def points(ecart: float, *, signe: bool = True) -> str:
    """Un écart en points de pourcentage : « −7.4 points », « +9.4 points »."""
    return f"{nombre(ecart * 100.0, 1, signe=signe)} points"


# ═══════════════════════════════════════════════════════════════ La lecture ══

CODE_CLOTURE = re.compile(r"^```.*?^```[^\n]*$", re.S | re.M)
COMMENTAIRE = re.compile(r"<!--.*?-->", re.S)
BLOC_DATE = re.compile(r"<!-- dated: ([a-z0-9-]+) -->\n(.*?)<!-- /dated -->", re.S)
CODE_EN_LIGNE = re.compile(r"`[^`\n]+`")
LIEN = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)\)")
ADRESSE = re.compile(r"<https?://[^>\s]+>|https?://[^\s)]+")


def visible(source: str) -> str:
    """Le texte tel que GitHub l'affiche, sans code, sans commentaires ni
    adresses, un paragraphe par ligne ; les indices et les exposants des
    formules retirés, comme dans `test_methodologie.lire` (des rangs et des
    puissances, pas des nombres cités)."""
    texte = CODE_CLOTURE.sub("\n", source)
    texte = COMMENTAIRE.sub("", texte)
    texte = CODE_EN_LIGNE.sub("", texte)
    texte = LIEN.sub(r"\1", texte)
    texte = ADRESSE.sub("", texte)
    texte = texte.replace("**", "")
    texte = re.sub(r"^#{1,6} ", "", texte, flags=re.M)
    texte = ecrit(texte)
    paragraphes = (re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", texte))
    texte = "\n".join(p for p in paragraphes if p)
    return FORMULE.sub(lambda m: INDICE.sub("", m.group(1) or m.group(2)), texte)


def hors_des_blocs(source: str, cles: set[str] | None = None) -> str:
    """La source sans les blocs datés (tous, ou ceux de `cles`)."""
    return BLOC_DATE.sub(
        lambda m: "\n\n" if cles is None or m.group(1) in cles else m.group(0), source
    )


# ═══════════════════════════════════════════════ 1. La liste fermée ══


def constantes() -> dict[str, str]:
    """Chaque constante du code qu'un document peut citer, écrite comme il
    l'écrit. Relue à chaque appel : une constante changée se voit."""
    choisis = [
        t for t in vars(thresholds).values() if isinstance(t, thresholds.Threshold) and t.chosen
    ]
    demontres = [thresholds.MIN_ESTIMABLE_SAMPLE] + [
        thresholds.historical_var_sample(niveau) for niveau in CONFIDENCE_LEVELS
    ]
    label, description = textes(EN).moteur.NOMS_D_INDICE[BENCHMARK_TICKER]
    indice = label.removeprefix("the ")
    ans = round(config.DEFAULT_WINDOW / config.TRADING_DAYS_PER_YEAR)
    largeur = config.HISTOGRAM_BIN_WIDTH * 100
    c = {
        "fenêtre": seances(config.DEFAULT_WINDOW),
        "fenêtre en jours de bourse": jours_de_bourse(config.DEFAULT_WINDOW),
        "durée": f"about {typography.cardinal(ans, langue=EN)} years",
        "période": ecrit(engine.period_label(config.DEFAULT_WINDOW, EN)),
        "racine de l'année": f"√{config.TRADING_DAYS_PER_YEAR}",
        "régression": seances(config.MIN_REGRESSION_OBSERVATIONS),
        "loi": seances(config.MIN_DISTRIBUTION_OBSERVATIONS),
        "estimables": seances(config.MIN_ESTIMABLE_OBSERVATIONS),
        "λ": f"λ = {typography.compact(config.EWMA_LAMBDA, langue=EN)}",
        "tirages": ecrit(typography.grouped(config.MONTE_CARLO_SIMULATIONS, "draw", langue=EN)),
        "profondeur": jour(BACKFILL_START),
        "taux sans risque": pourcent(config.DEFAULT_RISK_FREE_RATE, 2),
        "date du taux": jour(config.RISK_FREE_RATE_OBSERVED_ON),
        "gel": jour(date.fromisoformat(DATE_GEL)),
        "ν maximal": f"ν > {nombre(config.MAX_STUDENT_NU, 0)}",
        "ν maximal cité": f"ν = {nombre(config.MAX_STUDENT_NU, 0)}",
        "tranches": ecrit(
            typography.counted(largeur, "point", affiche=typography.number(largeur, 2, langue=EN), langue=EN)
        ),
        "indice": f"{indice}, {description}",
        "nom de l'indice": indice,
        "corrélation forte": thresholds.STRONG_CORRELATION.affiche(EN),
        "couverture": thresholds.MIN_SCENARIO_COVERAGE.affiche(EN),
        "seuils choisis": f"The {typography.cardinal(len(choisis), langue=EN)} thresholds chosen by hand",
        "nombre de seuils choisis": f"There are {typography.cardinal(len(choisis), langue=EN)} in the whole tool",
        "seuils démontrés": f"The {typography.cardinal(len(demontres), langue=EN)} proven thresholds",
        "crises": f"replays {typography.cardinal(len(SCENARIOS), langue=EN)} crises",
        "règles": f"The {typography.cardinal(len(RuleId), langue=EN)} rules",
        # Le piège d'échelle de `var.student_scale_matrix` : √(ν/(ν−2)) − 1 à ν = 5.
        "piège d'échelle": pourcent(math.sqrt(5 / 3) - 1, 0),
    }
    for niveau in CONFIDENCE_LEVELS:
        c[f"niveau {niveau}"] = pourcent(niveau, 0)
        c[f"queue {niveau}"] = pourcent(round(1.0 - niveau, 9), 0)
        c[f"VaR historique {niveau}"] = seances(config.historical_var_min_observations(niveau))
        c[f"quantile normal {niveau}"] = nombre(-norm.ppf(1.0 - niveau), 3)
    for scenario in SCENARIOS:
        c[f"crise {scenario.key}"] = scenario.nom(EN)
        c[f"début {scenario.key}"] = jour(scenario.start)
        c[f"fin {scenario.key}"] = jour(scenario.end)
    for seuil in choisis + demontres:
        c[f"ligne {seuil.key} {seuil.params}"] = ecrit(f"{seuil.nom(EN)} = {seuil.affiche(EN)}")
    # Tirés de la justification publiée d'un seuil : ils doivent y figurer.
    for extrait, seuil in (
        (pourcent(0.0205, 2), thresholds.STUDENT_NU_CEILING),
        (pourcent(0.0031, 2), thresholds.STUDENT_NU_CEILING),
        (pourcent(0.09, 0), thresholds.STUDENT_NU_CEILING),
        (pourcent(0.13, 0), thresholds.MIN_DISTRIBUTION_SAMPLE),
        (pourcent(0.50, 0), thresholds.MIN_SCENARIO_COVERAGE),
        ("about three months", thresholds.MIN_REGRESSION_SAMPLE),
    ):
        assert extrait in ecrit(seuil.justification(EN)), (extrait, seuil.key)
        c[f"justification {extrait}"] = extrait
    return c


# Ce que chaque document doit citer, en plus de ses nombres : si l'outil gagne
# une règle, une crise ou un seuil, le texte qui les compte doit changer.
REQUISES = {
    "METHODOLOGY.md": ("seuils choisis", "nombre de seuils choisis", "seuils démontrés", "crises", "règles"),
}

# Ni constantes ni données : des mathématiques, écrites telles qu'elles se
# lisent une fois les indices et les exposants retirés des formules.
FRAGMENTS_MATHEMATIQUES = (
    "− 1",  # un rendement : le rapport de deux valeurs, moins un
    "(1 + r)",
    "ln(1 + r)",
    "ln(1 + R)",
    "n − 1",  # l'écart-type d'échantillon ; le rang d'une covariance
    "n − 2",  # les degrés de liberté résiduels d'une régression
    "n = 2",  # la frontière démontrée, en symboles
    "two sessions",  # la même, en mots
    "1 − α",
    "n × (1 − α)",
    "1 / (1 − α)",
    "(1 − λ)",
    "(1 − R)",  # l'erreur type de la pente, exposant retiré
    "(ν − 2)",
    "ν ≤ 2",
    "ν = 2",
    "ν > 4",  # le domaine de la méthode des moments
    "6/κ + 4",
    "ν = 5",  # l'exemple du piège d'échelle
    "1/√(2n)",
    "1/N",
    "1 / (",  # l'inverse d'une somme de carrés
    "±δ/2",
    "rank 1",
    "+1 or −1",
    "from −1 to +1",
    "> 0",
    "μ = 0",  # la moyenne de la VaR normale
    "100%",  # des poids renormalisés à l'ensemble
    "starts at 1 ",  # la base de la courbe de valeur
)

# Des exemples, cités comme tels.
EXEMPLES = ("the past five years",)  # la profondeur glissante qu'on n'a pas retenue

# Des faits qui ne sont pas des constantes du code, chacun relu dans le
# fichier qui le porte : (fragment, fichier, ce que le fichier en dit).
FRAGMENTS_SOURCES = (
    ("13-week", "backend/risk_engine/config.py", "13 semaines"),
    ("360-day", "backend/risk_engine/config.py", "360 jours"),
    ("three months on both sides", "tests/test_stress.py", "months=3"),
)


def fragments() -> list[str]:
    return [*FRAGMENTS_MATHEMATIQUES, *EXEMPLES, *(f for f, _, _ in FRAGMENTS_SOURCES)]


NOMBRE = re.compile(r"[0-9]+")


def motif(citation: str) -> re.Pattern:
    """Une citation, sans qu'un chiffre voisin la prolonge : « 3 sessions » ne
    couvre pas le 3 de « 23 sessions »."""
    debut = r"(?<![0-9.,])" if citation[:1].isdigit() else ""
    fin = r"(?![0-9])" if citation[-1:].isdigit() else ""
    return re.compile(debut + re.escape(citation) + fin)


def fautes_de_nombres(texte: str, couvrants: list[str]) -> list[str]:
    """Chaque nombre de `texte`, en chiffres ou en lettres suivi de la durée
    qu'il compte, doit tomber dans une des chaînes `couvrants`."""
    couvert = [False] * len(texte)
    for citation in couvrants:
        for m in motif(citation).finditer(texte):
            couvert[m.start():m.end()] = [True] * (m.end() - m.start())
    fautes = [
        f"nombre non déclaré : {texte[max(0, m.start() - 30):m.end() + 15]!r}"
        for m in NOMBRE.finditer(texte)
        if not all(couvert[m.start():m.end()])
    ]
    fautes += [
        f"nombre en lettres non déclaré : {texte[max(0, m.start() - 30):m.end() + 15]!r}"
        for m in NOMBRE_EN_LETTRES_EN.finditer(texte)
        if not all(couvert[m.start(1):m.end(1)])
    ]
    return fautes


# ═══════════════════════════════════════════════ 2. Les résultats datés ══


@dataclass(frozen=True)
class Mesures:
    """Le portefeuille de démonstration analysé sur la copie figée."""

    rapport: engine.RiskReport
    scenarios: dict
    regimes: dict
    sigma_quotidien: float
    ko: tuple


@pytest.fixture(scope="module")
def mesures(tmp_path_factory) -> Mesures:
    copie = copier_base_reelle_figee(tmp_path_factory.mktemp("documents_publics") / "copie.sqlite")
    with closing(connect(copie)) as conn:
        with conn:
            conn.execute("INSERT INTO portfolios (owner) VALUES ('documents')")
            pid = conn.execute("SELECT MAX(id) FROM portfolios").fetchone()[0]
            conn.executemany(
                "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (?, ?, ?)",
                [(pid, ticker, quantite) for ticker, quantite in PORTEFEUILLE_DEMO.items()],
            )
        rapport = engine.analyse_portfolio(conn, pid, monte_carlo=True)
        serie = engine.build_portfolio_series(conn, pid)
        scenarios = {r.scenario.key: r for r in engine.run_all_scenarios(conn, pid)}
        regimes = {c.scenario.key: c for c in engine.compare_all_regimes(conn, pid)}
        ko = tuple(
            tuple(ligne)
            for ligne in conn.execute(
                "SELECT date, close, adj_close FROM prices "
                "WHERE ticker = 'KO' AND date <= ? ORDER BY date DESC LIMIT 2",
                (DATE_GEL,),
            )
        )
    sigma = covariance.parametric_volatility(
        serie.weights.weights,
        covariance.covariance_matrix(serie.asset_returns),
        periods_per_year=1,
    )
    return Mesures(rapport, scenarios, regimes, sigma, ko)


def version_de_scipy() -> str:
    """La version figée dans `requirements.txt`, celle du résultat de scipy."""
    (version,) = re.findall(r"^scipy==(\S+)$", (RACINE / "requirements.txt").read_text(), re.M)
    return version


def faits_de_marche(m: Mesures) -> list[str]:
    """La baisse du S&P 500 sur chaque crise et le nombre de séances de chacune :
    des faits du catalogue, pas du portefeuille, recalculés sur la copie figée."""
    faits = []
    for comparaison in m.regimes.values():
        faits.append(pourcent(comparaison.benchmark_return))
        faits.append(seances(comparaison.crisis_beta.observations))
    return faits


@pytest.fixture(scope="module")
def resultats(mesures) -> dict[str, dict[str, dict[str, str]]]:
    """Les quatre résultats : pour chaque clé, son cadre et ses chiffres, écrits
    comme les documents les écrivent."""
    r = mesures.rapport
    fenetre = r.window
    assert r.as_of == date.fromisoformat(DATE_GEL)
    periode = f"from {jour(fenetre.start)}, to {jour(fenetre.end)}"
    cadre_demo = {
        "portefeuille": ", ".join(f"{ticker} {quantite}" for ticker, quantite in PORTEFEUILLE_DEMO.items()),
        "valorisation": jour(r.as_of),
        "fenêtre session": f"{seances(fenetre.observations)}, {periode}",
        "fenêtre trading day": f"{jours_de_bourse(fenetre.observations)}, {periode}",
    }

    calme = mesures.regimes["gfc_2008"].calm_beta
    beta_calme = {
        "beta calme": f"{nombre(calme.beta, 2)} ± {nombre(calme.standard_error, 2)}",
        "R² calme": nombre(calme.r_squared, 2),
    }
    for cle, c in mesures.regimes.items():
        beta_calme[f"séances {cle}"] = nombre(c.crisis_beta.observations, 0)
        beta_calme[f"beta {cle}"] = (
            f"{nombre(c.crisis_beta.beta, 2)} ± {nombre(c.crisis_beta.standard_error, 2)}"
        )
        beta_calme[f"R² {cle}"] = nombre(c.crisis_beta.r_squared, 2)
        beta_calme[f"rejoué {cle}"] = pourcent(c.portfolio_return)
        beta_calme[f"impliqué {cle}"] = pourcent(c.predicted_return)
        beta_calme[f"écart {cle}"] = points(c.prediction_gap)
        beta_calme[f"S&P 500 {cle}"] = pourcent(c.benchmark_return)

    poids = r.weights
    parts = r.variance_contributions.contributions
    resserrement = mesures.scenarios["tightening_2022"]
    xom = next(c for c in resserrement.contributions if c.ticker == "XOM")
    jpm = {
        cle: next(c for c in s.contributions if c.ticker == "JPM").contribution
        for cle, s in mesures.scenarios.items()
    }
    pire, moindre = min(jpm, key=jpm.get), max(jpm, key=jpm.get)
    concentration = {
        "XOM valeur": pourcent(poids["XOM"]),
        "XOM variance": pourcent(parts["XOM"]),
        "XOM rendement": pourcent(xom.own_return, signe=True),
        "XOM contribution": points(xom.contribution),
        "portefeuille rejoué": pourcent(resserrement.end_to_end_return),
        "S&P 500 tightening_2022": pourcent(mesures.regimes["tightening_2022"].benchmark_return),
        "JPM valeur": pourcent(poids["JPM"]),
        "JPM variance": pourcent(parts["JPM"]),
        "JPM dans les crises": (
            f"from {points(-jpm[pire], signe=False)} in the {SCENARIOS_BY_KEY[pire].nom(EN)} "
            f"to {points(-jpm[moindre], signe=False)} in the {SCENARIOS_BY_KEY[moindre].nom(EN)}"
        ),
    }

    x = r.returns.to_numpy()
    naif = student_t.fit(x)
    ecart_de_vraisemblance = r.student_fit.log_likelihood - float(student_t.logpdf(x, *naif).sum())
    student = {
        "SciPy": f"SciPy {version_de_scipy()}",
        "ν estimé": f"ν = {nombre(r.student_fit.nu, 2)}",
        "ν de scipy": f"ν = {nombre(naif[0], 2)}",
        "vraisemblance": f"{round(ecart_de_vraisemblance)} units",
        "VaR Student 99 au ν de scipy": pourcent(var.student_t_var(mesures.sigma_quotidien, naif[0], 0.99), 2),
        "VaR normale 99": pourcent(r.parametric_var[0.99].value, 2),
        "VaR Student 99": pourcent(r.student_parametric_var[0.99].value, 2),
        "VaR normale 95": pourcent(r.parametric_var[0.95].value, 2),
        "VaR Student 95": pourcent(r.student_parametric_var[0.95].value, 2),
    }

    (seance, _, _), (veille, _, _) = mesures.ko

    return {
        "calm-beta": {"cadre": cadre_demo, "chiffres": beta_calme},
        "concentration-2022": {"cadre": cadre_demo, "chiffres": concentration},
        "student-nu": {"cadre": cadre_demo, "chiffres": student},
        "ko-dividend": {
            "cadre": {
                "titre": "Security: KO alone",
                "séance": jour(date.fromisoformat(seance)),
                "veille": jour(date.fromisoformat(veille)),
            },
            "chiffres": chiffres_ko(mesures),
        },
    }


def chiffres_ko(m: Mesures) -> dict[str, str]:
    """Le rendement réel de la copie figée, et le rendement stocké avant le
    correctif, recalculé depuis les deux cours recopiés de la sauvegarde."""
    (_, _, ajuste), (_, _, ajuste_veille) = m.ko
    avant = KO_ADJ_CLOSE_AVANT_CORRECTIF
    return {
        "réel": pourcent(ajuste / ajuste_veille - 1.0, 2),
        "stocké": pourcent(avant[date(2026, 9, 9)] / avant[date(2026, 9, 8)] - 1.0, 2),
        "sauvegarde": jour(DATE_SAUVEGARDE),
    }


# Ce que chaque document doit citer de chaque résultat, cadre compris (dans le
# registre du document : « sessions » ou « trading days »). `TOUS` : chaque
# chiffre du résultat.
TOUS = None
EXIGENCES = {
    "METHODOLOGY.md": {
        "calm-beta": TOUS,
        "concentration-2022": TOUS,
        "student-nu": TOUS,
        "ko-dividend": TOUS,
    },
}
REGISTRES = {"README.md": "fenêtre trading day"}


def citations_exigees(document: str, cle: str, res) -> dict[str, str]:
    registre = REGISTRES.get(document, "fenêtre session")
    cadre = {
        nom: valeur
        for nom, valeur in res[cle]["cadre"].items()
        if not nom.startswith("fenêtre") or nom == registre
    }
    noms = EXIGENCES[document][cle]
    chiffres = res[cle]["chiffres"]
    return cadre | (chiffres if noms is TOUS else {nom: chiffres[nom] for nom in noms})


def est_un_fait_de_marche(nom: str) -> bool:
    return nom.startswith(("S&P 500", "séances"))


def fautes_des_blocs(document: str, source: str, res) -> list[str]:
    fautes = []
    trouves = sorted(cle for cle, _ in BLOC_DATE.findall(source))
    attendus = sorted(EXIGENCES.get(document, {}))
    if trouves != attendus:
        fautes.append(f"blocs datés : {trouves} au lieu de {attendus}")
    for cle, corps in BLOC_DATE.findall(source):
        if cle not in res or cle not in EXIGENCES.get(document, {}):
            continue
        texte = visible(corps)
        for nom, citation in citations_exigees(document, cle, res).items():
            if not motif(citation).search(texte):
                fautes.append(f"[{cle}] citation absente, le moteur a-t-il changé ? {nom} : {citation!r}")
    # Un chiffre daté ne vit que dans les blocs de sa clé : une copie oubliée
    # ailleurs se périmerait sans que personne la voie.
    for cle, resultat in res.items():
        for nom, valeur in resultat["chiffres"].items():
            if est_un_fait_de_marche(nom):
                continue
            permises = {k for k, r in res.items() if valeur in r["chiffres"].values()}
            if motif(valeur).search(visible(hors_des_blocs(source, permises))):
                fautes.append(f"citation datée hors de son bloc : {valeur!r} ({cle}, {nom})")
    return fautes


def fautes_des_nombres(document: str, source: str, mesures_: Mesures, res) -> list[str]:
    communs = list(constantes().values()) + faits_de_marche(mesures_) + fragments()
    fautes = fautes_de_nombres(visible(hors_des_blocs(source)), communs)
    for cle, corps in BLOC_DATE.findall(source):
        if cle not in res:
            continue
        citations = list(res[cle]["cadre"].values()) + list(res[cle]["chiffres"].values())
        fautes += [f"[{cle}] {f}" for f in fautes_de_nombres(visible(corps), communs + citations)]
    texte = visible(source)
    c = constantes()
    fautes += [
        f"citation absente, le moteur a-t-il changé ? {nom} : {c[nom]!r}"
        for nom in REQUISES.get(document, ())
        if not motif(c[nom]).search(texte)
    ]
    return fautes


# ═════════════════════════════════════════════ 3. Les gardes anglaises ══

# Des phrases ENTIÈRES, document par document, que la garde prescriptive admet.
# Deux cas seulement : la description de la convention des poids constants (le
# rééquilibrage quotidien qu'elle suppose), et les phrases qui disent ce que
# l'outil refuse de dire. Le même mot, ailleurs, échoue.
EXCEPTIONS_PRESCRIPTIVES = {
    "METHODOLOGY.md": (
        # Les poids constants.
        "Applying today's weights to every past session amounts to rebalancing "
        "the portfolio to its current composition at the end of each session.",
        "Over several months, constant weights would mean rebalancing every day, "
        "selling what held up best to buy what had just fallen, which a holder who "
        "trades nothing does not do.",
        # Ce que l'outil refuse de dire.
        "“This holding carries a large share of the fluctuations” is a verifiable "
        "fact; “you should reduce it” is investment advice, which nothing in this "
        "project allows the tool to give.",
    ),
}

FIN_DE_PHRASE = re.compile(r"[.!?] [A-Z“]")


def phrases_admises(texte: str, exceptions: tuple[str, ...]) -> tuple[str, list[str]]:
    """Efface de `texte` chaque phrase admise, entière, et rend ce qui reste avec
    les fautes des exceptions elles-mêmes : une exception doit être UNE phrase,
    présente une fois, à sa place de phrase, et contenir un mot gardé."""
    fautes = []
    for phrase in exceptions:
        if phrase[-1] not in ".!?" or FIN_DE_PHRASE.search(phrase):
            fautes.append(f"exception qui n'est pas une phrase : {phrase[:50]!r}")
        if not PRESCRIPTIF_EN.search(phrase):
            fautes.append(f"exception inutile : {phrase[:50]!r}")
        entieres = [
            m.start()
            for m in re.finditer(re.escape(phrase), texte)
            if (m.start() == 0 or texte[m.start() - 1] == "\n" or texte[m.start() - 2:m.start()] in (". ", "? ", "! ", "- "))
            and (m.end() == len(texte) or texte[m.end()] in " \n")
        ]
        if len(entieres) != 1:
            fautes.append(f"exception absente ou répétée ({len(entieres)}) : {phrase[:50]!r}")
        for debut in entieres:
            texte = texte[:debut] + " " * len(phrase) + texte[debut + len(phrase):]
    return texte, fautes


def fautes_de_garde(document: str, texte: str) -> list[str]:
    fautes = [f"ponctuation : {e!r}" for e in PONCTUATION_EN.findall(texte)]
    if CADRATIN in texte:
        fautes.append("tiret cadratin")
    fautes += [f"contraction : {m.group()!r}" for m in CONTRACTION.finditer(texte)]
    if re.search(r"expected loss", texte, re.IGNORECASE):
        fautes.append("expected loss : une VaR se lit « a loss of at least »")
    if "score" in texte.lower() or SCORE_SUR_100_EN.search(texte):
        fautes.append("note globale")
    fautes += [f"virgule décimale : {e!r}" for e in VIRGULE_DECIMALE.findall(texte)]
    fautes += [f"espace avant % : {e!r}" for e in ESPACE_AVANT_POURCENT_EN.findall(texte)]
    fautes += [f"généralité : {g}" for g in GENERALITES_EN if g in texte.lower()]
    reste, fautes_d_exceptions = phrases_admises(texte, EXCEPTIONS_PRESCRIPTIVES.get(document, ()))
    fautes += fautes_d_exceptions
    fautes += [
        f"prescriptif : {reste[max(0, m.start() - 30):m.end() + 15]!r}"
        for m in PRESCRIPTIF_EN.finditer(reste)
    ]
    return fautes


# ═══════════════════════════════════════════════════════════════ Les tests ══


@pytest.fixture(scope="module")
def sources() -> dict[str, str]:
    return {document: (RACINE / document).read_text(encoding="utf-8") for document in DOCUMENTS}


@pytest.mark.parametrize("document", DOCUMENTS)
def test_les_gardes_anglaises(document, sources):
    assert fautes_de_garde(document, visible(sources[document])) == []


@pytest.mark.parametrize("document", DOCUMENTS)
def test_chaque_nombre_est_une_constante_un_fait_ou_un_fragment_declare(document, sources, mesures, resultats):
    assert fautes_des_nombres(document, sources[document], mesures, resultats) == []


@pytest.mark.parametrize("document", DOCUMENTS)
def test_chaque_resultat_date_porte_son_cadre_et_reste_dans_son_bloc(document, sources, resultats):
    assert fautes_des_blocs(document, sources[document], resultats) == []


@pytest.mark.parametrize("document", DOCUMENTS)
def test_les_liens_internes_menent_a_un_fichier_du_depot(document, sources):
    cibles = [
        cible.partition("#")[0]
        for _, cible in LIEN.findall(sources[document])
        if not cible.startswith(("http://", "https://", "#", "mailto:"))
    ]
    assert [c for c in cibles if not (RACINE / c).exists()] == []


def test_les_regles_citees_portent_les_libelles_de_l_application(sources):
    """Chaque règle, par l'identifiant que publie l'API (`rule`, le nom du
    membre en minuscules) et par son libellé anglais (`rule_label`)."""
    source = sources["METHODOLOGY.md"]
    texte = visible(source)
    for regle in RuleId:
        assert f"`{regle.name.lower()}`" in source, regle
        assert textes(EN).regles.libelle(regle) in texte, regle


def test_les_lignes_de_seuil_citees_sont_celles_du_moteur(sources):
    """Une citation “… = …” est la ligne d'un seuil publié, mot pour mot."""
    lignes = {
        ecrit(f"{t.nom(EN)} = {t.affiche(EN)}")
        for t in vars(thresholds).values()
        if isinstance(t, thresholds.Threshold)
    } | {ecrit(f"{t.nom(EN)} = {t.affiche(EN)}") for t in map(thresholds.historical_var_sample, CONFIDENCE_LEVELS)}
    lignes.add(constantes()["ν maximal cité"])
    citees = [c for c in re.findall(r"“([^”]+)”", visible(sources["METHODOLOGY.md"])) if " = " in c]
    assert citees and [c for c in citees if c not in lignes] == []


def test_les_fragments_sources_disent_ce_que_le_document_dit():
    for fragment, fichier, marque in FRAGMENTS_SOURCES:
        assert marque in (RACINE / fichier).read_text(encoding="utf-8"), (fragment, fichier)


def test_scipy_est_la_version_figee():
    """Le résultat de `scipy.stats.t.fit` est daté par sa version : celle qui
    tourne est celle de `requirements.txt`."""
    assert scipy.__version__ == version_de_scipy()


# ═══════════════════════════════════════ Ce que disent les résultats datés ══


def test_le_beta_calme_contre_les_crises(mesures):
    regimes = mesures.regimes
    assert len({c.calm_beta.beta for c in regimes.values()}) == 1  # couverture complète
    calme = regimes["gfc_2008"].calm_beta.r_squared
    for cle in ("gfc_2008", "tightening_2022"):
        assert not regimes[cle].crisis_beta.sample_too_thin
        assert regimes[cle].crisis_beta.r_squared > calme
    covid = regimes["covid_2020"].crisis_beta
    assert covid.sample_too_thin and covid.r_squared > calme
    # Sous-estimée en 2008 et en 2020, surestimée en 2022.
    assert regimes["gfc_2008"].prediction_gap < 0
    assert regimes["covid_2020"].prediction_gap < 0
    assert regimes["tightening_2022"].prediction_gap > 0


def test_la_concentration_joue_dans_les_deux_sens(mesures):
    resserrement = mesures.scenarios["tightening_2022"]
    xom = next(c for c in resserrement.contributions if c.ticker == "XOM")
    assert xom.contribution > 0 > resserrement.end_to_end_return
    for scenario in mesures.scenarios.values():
        assert next(c for c in scenario.contributions if c.ticker == "JPM").contribution < 0


def test_un_nu_mal_estime_rassure(mesures):
    r = mesures.rapport
    x = r.returns.to_numpy()
    naif = student_t.fit(x)
    au_nu_de_scipy = var.student_t_var(mesures.sigma_quotidien, naif[0], 0.99)
    assert au_nu_de_scipy < r.parametric_var[0.99].value < r.student_parametric_var[0.99].value
    assert r.student_parametric_var[0.95].value < r.parametric_var[0.95].value
    assert r.student_fit.log_likelihood > float(student_t.logpdf(x, *naif).sum())


def test_les_cours_de_ko_recopies_se_recoupent_avec_la_copie_figee(mesures):
    """Le cours du 2026-09-08 recopié de la sauvegarde est le cours brut, que
    rien n'ajuste ; celui du 2026-09-09 était déjà réajusté, et le rebuild l'a
    réécrit à l'identique. Le rendement réel est le même par les cours bruts et
    par les cours ajustés."""
    (seance, brut, ajuste), (veille, brut_veille, ajuste_veille) = mesures.ko
    assert (seance, veille) == ("2026-09-09", "2026-09-08")
    assert KO_ADJ_CLOSE_AVANT_CORRECTIF[date(2026, 9, 8)] == brut_veille
    assert KO_ADJ_CLOSE_AVANT_CORRECTIF[date(2026, 9, 9)] == pytest.approx(ajuste, abs=1e-9)
    assert pourcent(ajuste / ajuste_veille - 1.0, 2) == pourcent(brut / brut_veille - 1.0, 2)


# ════════════════════════════════════════════════════════ Les gardes mordent ══

TEMOINS = (
    # (document, avant, après, faute attendue)
    ("METHODOLOGY.md", "| −44.0% |", "| −45.0% |", "nombre non déclaré"),
    ("METHODOLOGY.md", "about two years", "about three years", "nombre en lettres non déclaré"),
    ("METHODOLOGY.md", "The five thresholds", "The six thresholds", "citation absente"),
    ("METHODOLOGY.md", "Session: September 9, 2026", "Session: September 10, 2026", "citation absente"),
    ("METHODOLOGY.md", "set out below.", "set out below, at −44.0%.", "citation datée hors de son bloc"),
    ("METHODOLOGY.md", "set out below.", "set out below (1,346 tests).", "nombre non déclaré"),
    ("METHODOLOGY.md", "set out below.", "set out below, with no rebalancing.", "prescriptif"),
    (
        "METHODOLOGY.md",
        "amounts to rebalancing the portfolio",
        "amounts to rebalancing the whole portfolio",
        "exception absente",
    ),
    ("METHODOLOGY.md", "not an average", "not an expected loss", "expected loss"),
    ("METHODOLOGY.md", "There is no overall rating.", "There is no overall score.", "note globale"),
    ("METHODOLOGY.md", "does not measure what", "doesn't measure what", "contraction"),
    ("METHODOLOGY.md", "set out below.", f"set out below{CADRATIN}here.", "tiret cadratin"),
    ("METHODOLOGY.md", "about 13% from one window", "about 13,5% from one window", "virgule décimale"),
)


def toutes_les_fautes(document: str, source: str, mesures_: Mesures, res) -> list[str]:
    return (
        fautes_de_garde(document, visible(source))
        + fautes_des_nombres(document, source, mesures_, res)
        + fautes_des_blocs(document, source, res)
    )


@pytest.mark.parametrize(
    "document, avant, apres, attendue", TEMOINS, ids=[f"{t[3]} {t[2][:24]}" for t in TEMOINS]
)
def test_chaque_garde_mord_sur_un_texte_fautif(document, avant, apres, attendue, sources, mesures, resultats):
    source = sources[document]
    assert source.count(avant) >= 1, avant
    assert toutes_les_fautes(document, source, mesures, resultats) == []
    fautes = toutes_les_fautes(document, source.replace(avant, apres, 1), mesures, resultats)
    assert any(attendue in f for f in fautes), fautes


def test_un_changement_du_moteur_fait_echouer_la_liste(sources, mesures, resultats, monkeypatch):
    """Témoin : la liste lit le moteur à chaque appel."""
    monkeypatch.setattr(config, "MIN_REGRESSION_OBSERVATIONS", 90)
    fautes = fautes_des_nombres("METHODOLOGY.md", sources["METHODOLOGY.md"], mesures, resultats)
    assert any("nombre non déclaré" in f and "60 sessions" in f for f in fautes), fautes


def test_un_cours_de_ko_recopie_autrement_fait_echouer_le_bloc(sources, mesures, resultats, monkeypatch):
    """Témoin : le rendement stocké du bloc se recalcule depuis les deux cours
    recopiés ; un cours mal recopié ne passe pas."""
    monkeypatch.setitem(KO_ADJ_CLOSE_AVANT_CORRECTIF, date(2026, 9, 9), 87.10)
    autres = resultats | {
        "ko-dividend": {"cadre": resultats["ko-dividend"]["cadre"], "chiffres": chiffres_ko(mesures)}
    }
    fautes = fautes_des_blocs("METHODOLOGY.md", sources["METHODOLOGY.md"], autres)
    assert any("citation absente" in f and "stocké" in f for f in fautes), fautes
