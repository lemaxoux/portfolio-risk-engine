"""Tests du moteur de règles (Phase 6).

Trois principes sont verrouillés avant les règles elles-mêmes : le moteur décrit
sans prescrire, il ne produit aucun score global, et il ne recalcule rien. Puis
chaque règle, ses seuils et leur provenance, et le texte du bandeau.
"""

from __future__ import annotations

import ast
import re
from contextlib import closing
from dataclasses import fields, replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.db.init_db import connect, init_db
from backend.risk_engine.covariance import effective_risk_positions, variance_contributions
from backend.risk_engine.engine import (
    ConcentrationResult,
    ExcludedPosition,
    ExpectedShortfallResult,
    RegimeComparison,
    RegressedBeta,
    ScenarioCoverage,
    VarianceContributionResult,
    Window,
    analyse_portfolio,
    compare_all_regimes,
    run_all_scenarios,
)
from backend.risk_engine.scenarios import SCENARIOS, Scenario
from backend.risk_engine.stress import PositionContribution
from backend.rules import (
    MIN_DISTRIBUTION_SAMPLE,
    MIN_ESTIMABLE_SAMPLE,
    MIN_REGRESSION_SAMPLE,
    MIN_SCENARIO_COVERAGE,
    STRONG_CORRELATION,
    STUDENT_NU_CEILING,
    Observation,
    RuleId,
    RulesReport,
    ThresholdKind,
    ThresholdRole,
    acceptance_text,
    apparent_diversification,
    crisis_degradation,
    effective_concentration,
    evaluate,
    evaluate_portfolio,
    scenario_coverage,
    systematic_share,
    variance_contribution,
)

RACINE = Path(__file__).resolve().parents[1]

# Garde lexicale : formes qui transformeraient une observation en consigne.
PRESCRIPTIF = re.compile(
    r"\b(devr\w*|doi(s|t|vent)|il faut|faudr\w*|recommand\w*|conseill\w*|"
    r"rédui\w*|allég\w*|allège\w*|vend(s|ez|re)|achèt\w*|achet(er|ez)|"
    r"renforc\w*|privilégi\w*|évit(e|ez|er)|envisag\w*|rééquilibr\w*|"
    r"diversifi(e|es|ez|er))\b",
    re.IGNORECASE,
)

# Motif d'un score ramené sur 100 (« 72/100 », « 7,5 / 100 »).
SCORE_SUR_100 = re.compile(r"\b\d+(,\d+)?\s*/\s*100\b")

FENETRE = Window(requested=504, observations=504, start=date(2024, 9, 5), end=date(2026, 9, 9))


# ============================================ Mesure : contribution à la variance ==


def matrice(valeurs, tickers):
    return pd.DataFrame(valeurs, index=tickers, columns=tickers)


def test_les_contributions_somment_exactement_a_un():
    rng = np.random.default_rng(3)
    brut = rng.normal(0, 0.01, (300, 5))
    tickers = list("ABCDE")
    cov = pd.DataFrame(np.cov(brut, rowvar=False), index=tickers, columns=tickers)
    poids = dict(zip(tickers, [0.3, 0.25, 0.2, 0.15, 0.1]))

    assert sum(variance_contributions(poids, cov).values()) == pytest.approx(1.0, abs=1e-12)


def test_une_ligne_correlee_contribue_plus_qu_une_ligne_decorrelee_de_meme_poids():
    """Ce que le poids seul ne dit pas.

    B et C pèsent chacune 10 % et ont la même volatilité. B est très corrélée à
    la grosse ligne A, C ne l'est pas : B porte bien plus que 10 % de la variance,
    C bien moins.
    """
    v = 0.01**2
    cov = matrice(
        [[v, 0.9 * v, 0.0], [0.9 * v, v, 0.0], [0.0, 0.0, v]], ["A", "B", "C"]
    )
    parts = variance_contributions({"A": 0.8, "B": 0.1, "C": 0.1}, cov)

    assert parts["B"] > 0.10 > parts["C"]


def test_une_ligne_qui_evolue_a_rebours_a_une_contribution_negative():
    v = 0.01**2
    cov = matrice([[v, -0.8 * v], [-0.8 * v, v]], ["A", "B"])
    parts = variance_contributions({"A": 0.8, "B": 0.2}, cov)

    assert parts["B"] < 0.0
    assert parts["A"] > 1.0
    assert sum(parts.values()) == pytest.approx(1.0, abs=1e-12)


def test_lignes_independantes_de_meme_volatilite_contribuent_selon_le_carre_du_poids():
    v = 0.01**2
    cov = matrice(np.eye(3) * v, ["A", "B", "C"])
    equi = variance_contributions({"A": 1 / 3, "B": 1 / 3, "C": 1 / 3}, cov)
    assert all(p == pytest.approx(1 / 3) for p in equi.values())

    parts = variance_contributions({"A": 0.5, "B": 0.3, "C": 0.2}, cov)
    total = 0.5**2 + 0.3**2 + 0.2**2
    assert parts["A"] == pytest.approx(0.25 / total)


def test_lignes_effectives_en_risque_aux_bornes():
    assert effective_risk_positions({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}) == pytest.approx(4.0)
    assert effective_risk_positions({"A": 1.0}) == pytest.approx(1.0)


def test_lignes_effectives_en_risque_jamais_au_dela_de_n_meme_avec_une_contribution_negative():
    # Les contributions sommant à 1, 1/Σc² ≤ N ; une forte contribution négative
    # peut en revanche faire descendre le nombre sous 1.
    for parts in ({"A": 0.7, "B": 0.4, "C": -0.1}, {"A": 1.2, "B": -0.2}):
        assert effective_risk_positions(parts) <= len(parts) + 1e-12
    assert effective_risk_positions({"A": 1.2, "B": -0.2}) < 1.0


def test_les_poids_sont_apparies_a_la_matrice_par_etiquette():
    v = 0.01**2
    cov = matrice([[v, 0.0], [0.0, 4 * v]], ["A", "B"])
    parts = variance_contributions({"B": 0.5, "A": 0.5}, cov)
    assert parts["B"] == pytest.approx(0.8)
    assert parts["A"] == pytest.approx(0.2)


# ============================================================ Portefeuille synthétique ==


def seances(n: int, depart: date) -> list[date]:
    resultat, jour = [], depart
    while len(resultat) < n:
        if jour.weekday() < 5:
            resultat.append(jour)
        jour += timedelta(days=1)
    return resultat


JOURS = seances(300, date(2019, 1, 2))
CRISE = Scenario(
    key="crise_test",
    name="Crise de test",
    start=JOURS[40],
    end=JOURS[139],
    benchmark="SPY",
    description="Fenêtre synthétique de cent séances.",
)


@pytest.fixture
def conn(tmp_path):
    chemin = tmp_path / "regles.sqlite"
    init_db(chemin)
    connexion = connect(chemin)
    yield connexion
    connexion.close()


def serie(rendements: np.ndarray, initial: float = 100.0) -> pd.Series:
    return pd.Series(initial * np.cumprod(1.0 + rendements), index=JOURS)


def peupler(conn, part_de_c: float) -> None:
    """A et B quasi identiques ; C, indépendante, n'existe qu'après le début de
    la crise et pèse `part_de_c` de la valeur actuelle."""
    rng = np.random.default_rng(12)
    marche = rng.normal(0.0004, 0.008, len(JOURS))
    marche[40:140] = rng.normal(-0.003, 0.016, 100)
    a = 0.9 * marche + rng.normal(0.0, 0.006, len(JOURS))
    b = a + rng.normal(0.0, 0.002, len(JOURS))
    c = rng.normal(0.0003, 0.012, len(JOURS))

    cours = {
        "SPY": serie(marche, 300.0),
        "A": serie(a),
        "B": serie(b, 50.0),
        "C": serie(c, 20.0).iloc[100:],
    }
    valeur_ab = 10 * cours["A"].iloc[-1] + 20 * cours["B"].iloc[-1]
    quantite_c = part_de_c * valeur_ab / (1.0 - part_de_c) / cours["C"].iloc[-1]

    conn.execute("INSERT INTO portfolios (owner) VALUES ('test')")
    for ticker, valeurs in cours.items():
        conn.execute("INSERT INTO securities (ticker, name) VALUES (?, ?)", (ticker, ticker))
        for jour, valeur in valeurs.items():
            conn.execute(
                "INSERT INTO prices (ticker, date, close, adj_close) VALUES (?,?,?,?)",
                (ticker, jour.isoformat(), float(valeur), float(valeur)),
            )
    for ticker, quantite in {"A": 10, "B": 20, "C": quantite_c}.items():
        conn.execute(
            "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1,?,?)",
            (ticker, float(quantite)),
        )
    conn.commit()


def evaluer(conn) -> RulesReport:
    return evaluate(
        analyse_portfolio(conn, 1, window=100),
        run_all_scenarios(conn, 1, (CRISE,)),
        compare_all_regimes(conn, 1, (CRISE,), window=100),
    )


@pytest.fixture
def entrees(conn):
    """Sorties des Phases 4 et 5 sur le portefeuille synthétique."""
    peupler(conn, part_de_c=0.30)
    return (
        analyse_portfolio(conn, 1, window=100),
        run_all_scenarios(conn, 1, (CRISE,)),
        compare_all_regimes(conn, 1, (CRISE,), window=100),
    )


@pytest.fixture
def risque(entrees):
    return entrees[0]


@pytest.fixture
def rapport(entrees) -> RulesReport:
    return evaluate(*entrees)


# ================================================================ Principes ==


def test_les_six_regles_s_expriment_sur_un_portefeuille_qui_les_declenche(rapport):
    assert {o.rule for o in rapport.observations} == set(RuleId)


def test_aucune_observation_ne_prescrit_d_action(rapport):
    """Le moteur décrit, il ne prescrit pas. Garde lexicale sur chaque phrase."""
    assert PRESCRIPTIF.search("Tu devrais alléger JPM.")  # la garde mord
    for observation in rapport.observations:
        trouve = PRESCRIPTIF.search(observation.render())
        assert trouve is None, f"formulation prescriptive « {trouve.group()} » : {observation.statement}"


def test_aucun_score_global_n_est_produit(rapport):
    """Une liste d'observations, et rien d'autre."""
    for classe in (RulesReport, Observation):
        assert not [f.name for f in fields(classe) if "score" in f.name.lower()]
    assert all(isinstance(o, Observation) for o in rapport.observations)
    texte = rapport.render()
    assert SCORE_SUR_100.search("Score de risque : 72/100")  # la garde mord
    assert "score" not in texte.lower()
    assert SCORE_SUR_100.search(texte) is None


def test_le_moteur_de_regles_n_importe_aucun_module_de_calcul():
    """Il lit les sorties des Phases 4 et 5 ; il ne recalcule rien."""
    interdits = {
        "numpy", "pandas", "scipy",
        "backend.risk_engine.covariance", "backend.risk_engine.var",
        "backend.risk_engine.measures", "backend.risk_engine.returns",
        "backend.risk_engine.stress", "backend.risk_engine.regime",
    }
    for module in ("rules.py", "thresholds.py", "disclaimer.py"):
        arbre = ast.parse((RACINE / "backend" / "rules" / module).read_text(encoding="utf-8"))
        importes = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes.update(alias.name for alias in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.add(noeud.module)
        assert not importes & interdits, f"{module} importe {importes & interdits}"


# ================================================== 1. Concentration effective ==


def concentration(n: int, effectives: float) -> ConcentrationResult:
    return ConcentrationResult(
        hhi=1.0 / effectives, effective_positions=effectives,
        equal_weight_reference=1.0 / n, n_positions=n, as_of=date(2026, 9, 9),
    )


DEMO_POIDS = {"JPM": 0.256, "JNJ": 0.161, "XOM": 0.158, "AAPL": 0.152, "MSFT": 0.148, "KO": 0.125}
DEMO_PARTS = {"JPM": 0.354, "AAPL": 0.221, "MSFT": 0.154, "XOM": 0.139, "JNJ": 0.079, "KO": 0.053}


def test_la_concentration_se_dit_en_capital_et_en_risque_sans_seuil(risque):
    """Le risque ne se répartit pas comme le capital, et la version en capital
    seule est la plus flatteuse des deux."""
    base = replace(
        risque,
        concentration=concentration(6, 5.65),
        variance_contributions=_contributions(DEMO_PARTS, DEMO_POIDS),
    )
    obs = effective_concentration(base)

    assert obs.statement.startswith(
        "Vos 6\u00a0lignes pèsent comme 5,7\u00a0lignes de même montant, mais font bouger "
        "le portefeuille comme 4,4 seulement : le risque est plus concentré que l'argent."
    )
    assert "Avec des montants égaux, elles compteraient pour 6." in obs.statement
    assert "À ne regarder que les montants, on surestime donc la diversification." in obs.statement
    assert obs.facts["lignes_effectives_risque"] == pytest.approx(1.0 / sum(v * v for v in DEMO_PARTS.values()))
    assert obs.thresholds == ()
    assert "Aucun seuil" in obs.render()
    assert obs.provenance.startswith("capital : valorisation au 2026-09-09 ; risque : fenêtre")


def test_un_risque_mieux_reparti_que_le_capital_est_dit_tel_quel(risque):
    base = replace(
        risque,
        concentration=concentration(3, 1.0 / (0.6**2 + 0.2**2 + 0.2**2)),
        variance_contributions=_contributions(
            {"A": 0.34, "B": 0.33, "C": 0.33}, {"A": 0.6, "B": 0.2, "C": 0.2}
        ),
    )
    obs = effective_concentration(base)

    assert (
        "et font bouger le portefeuille comme 3,0 : le risque est mieux réparti que l'argent."
    ) in obs.statement
    assert "surestime" not in obs.statement


def test_une_contribution_negative_rend_la_lecture_en_risque_approximative(risque):
    base = replace(
        risque,
        concentration=concentration(2, 1.0 / (0.8**2 + 0.2**2)),
        variance_contributions=_contributions({"A": 1.1, "B": -0.1}, {"A": 0.8, "B": 0.2}),
    )
    assert "n'est qu'une approximation" in effective_concentration(base).statement


def test_la_concentration_d_une_ligne_unique(risque):
    base = replace(
        risque,
        concentration=concentration(1, 1.0),
        variance_contributions=_contributions({"A": 1.0}, {"A": 1.0}),
    )
    assert (
        "une seule ligne : elle en porte tout le montant et toutes les variations"
    ) in effective_concentration(base).statement


def test_le_nombre_en_risque_du_rapport_est_celui_de_la_mesure(risque):
    vc = risque.variance_contributions
    assert vc.effective_positions == pytest.approx(effective_risk_positions(vc.contributions))


# ================================================ 2. Contribution à la variance ==


def test_une_observation_par_ligne_de_la_plus_forte_a_la_plus_faible(rapport):
    obs = rapport.of_rule(RuleId.VARIANCE_CONTRIBUTION)
    parts = [o.facts["part_de_variance"] for o in obs]

    assert sorted(o.subject for o in obs) == ["A", "B", "C"]
    assert parts == sorted(parts, reverse=True)
    assert sum(parts) == pytest.approx(1.0, abs=1e-12)
    for o in obs:
        (seuil,) = o.thresholds
        assert seuil.kind is ThresholdKind.DERIVED
        assert "de la valeur du portefeuille" in o.statement and "de ses variations" in o.statement


def _contributions(parts, poids):
    return VarianceContributionResult(contributions=parts, weights=poids, window=FENETRE)


def test_la_part_du_risque_est_comparee_a_la_part_du_capital(risque):
    base = replace(
        risque,
        variance_contributions=_contributions(
            {"A": 0.60, "B": 0.45, "C": -0.05}, {"A": 0.40, "B": 0.45, "C": 0.15}
        ),
    )
    obs = {o.subject: o for o in variance_contribution(base)}

    assert "de ses variations, soit 20,0\u00a0points de plus." in obs["A"].statement
    assert "de ses variations, soit la même part." in obs["B"].statement
    assert "ses mouvements ont en moyenne compensé ceux des autres lignes" in obs["C"].statement


def test_l_influence_dans_les_deux_sens_est_dite_une_fois_sur_la_plus_forte(rapport):
    obs = rapport.of_rule(RuleId.VARIANCE_CONTRIBUTION)
    avec = [o for o in obs if "plus elle pèse sur le résultat, à la baisse comme à la hausse" in o.statement]
    assert avec == [obs[0]]


def _scenario(rapport_scenario, key, nom, contributions, part_couverte=1.0):
    exclus = () if part_couverte == 1.0 else (
        ExcludedPosition("Z", "historique absent", value=1.0 - part_couverte, weight=1.0 - part_couverte),
    )
    return replace(
        rapport_scenario,
        scenario=replace(rapport_scenario.scenario, key=key, name=nom),
        coverage=ScenarioCoverage(
            covered=tuple(contributions), excluded=exclus,
            covered_value=part_couverte, total_value=1.0,
        ),
        end_to_end_return=sum(contributions.values()),
        contributions=tuple(
            PositionContribution(t, 0.0, 0.0, 0.0, v, 0.0, 0.0) for t, v in contributions.items()
        ),
    )


def test_le_parcours_en_crise_est_dit_dans_les_deux_sens(entrees):
    """La ligne qui coûte dans une crise peut sauver le portefeuille dans une autre."""
    risque, (modele,), _ = entrees

    perte = _scenario(modele, "krach", "Krach", {"A": -0.076, "B": -0.05})
    gain = _scenario(modele, "resserrement", "Resserrement", {"A": 0.094, "B": -0.02})
    obs = {o.subject: o for o in variance_contribution(risque, (perte, gain))}

    assert (
        "A a joué dans les deux sens : il a coûté 7,6\u00a0points (Krach), mais rapporté "
        "9,4\u00a0points (Resserrement)"
    ) in obs["A"].statement
    assert "B a coûté au portefeuille à chaque fois" in obs["B"].statement
    assert obs["A"].facts["scenario:resserrement"] == pytest.approx(0.094)


def test_un_scenario_sous_le_seuil_de_couverture_n_alimente_pas_le_parcours(entrees):
    risque, (modele,), _ = entrees

    mince = _scenario(modele, "mince", "Mince", {"A": -0.40}, part_couverte=0.70)
    obs = {o.subject: o for o in variance_contribution(risque, (mince,))}

    assert "scenario:mince" not in obs["A"].facts
    assert "Mince" not in obs["A"].statement


# ================================================== 3. Diversification apparente ==


def test_une_paire_fortement_correlee_est_signalee_avec_son_seuil_choisi(rapport):
    (obs,) = rapport.of_rule(RuleId.APPARENT_DIVERSIFICATION)

    assert obs.subject == "A–B"
    assert obs.facts["correlation"] >= STRONG_CORRELATION.value
    assert "à elles deux, elles diversifient moins que leur nombre ne le laisse penser" in obs.statement
    assert obs.uses_chosen_threshold
    assert "CHOISI à la main" in obs.render()


def test_sans_paire_forte_la_paire_la_plus_correlee_est_decrite(risque):
    base = replace(risque, matrices=replace(
        risque.matrices,
        correlation=matrice([[1.0, 0.42, 0.1], [0.42, 1.0, 0.3], [0.1, 0.3, 1.0]], ["JNJ", "KO", "X"]),
    ))
    (obs,) = apparent_diversification(base)

    assert obs.subject == "portefeuille"
    assert "La paire la plus liée est JNJ–KO, à 0,42" in obs.statement
    kinds = [s.kind for s in obs.thresholds]
    assert kinds == [ThresholdKind.CHOSEN, ThresholdKind.PORTFOLIO_RELATIVE]


def test_la_paire_la_plus_correlee_est_une_reference_pas_un_seuil(risque):
    # DESIGN.md §9.2 : « Référence : » pour une valeur calculée sur le
    # portefeuille. La corrélation JNJ–KO était titrée « Seuil : », comme le
    # vrai seuil choisi de la ligne précédente.
    base = replace(risque, matrices=replace(
        risque.matrices,
        correlation=matrice([[1.0, 0.42, 0.1], [0.42, 1.0, 0.3], [0.1, 0.3, 1.0]], ["JNJ", "KO", "X"]),
    ))
    (obs,) = apparent_diversification(base)

    roles = [s.role for s in obs.thresholds]
    assert roles == [ThresholdRole.THRESHOLD, ThresholdRole.REFERENCE]
    rendu = obs.render()
    assert "  Seuil : corrélation forte" in rendu
    assert "  Référence : corrélation JNJ–KO" in rendu
    assert "Seuil : corrélation JNJ–KO" not in rendu


def test_la_part_de_capital_est_une_reference(rapport):
    for obs in rapport.of_rule(RuleId.VARIANCE_CONTRIBUTION):
        part, *_ = obs.thresholds
        assert part.role is ThresholdRole.REFERENCE
        assert f"  Référence : part de {obs.subject} dans la valeur" in obs.render()


def test_les_seuils_fixes_restent_des_seuils():
    # Choisis à la main ou démontrés : des frontières posées d'avance, les
    # mêmes pour tout portefeuille.
    for seuil in (STRONG_CORRELATION, MIN_SCENARIO_COVERAGE, MIN_REGRESSION_SAMPLE, MIN_ESTIMABLE_SAMPLE):
        assert seuil.role is ThresholdRole.THRESHOLD, seuil.name
    assert MIN_ESTIMABLE_SAMPLE.kind is ThresholdKind.DERIVED, "kind ne suffit pas à trancher"


def test_le_plafond_de_nu_est_le_quatrieme_seuil_choisi():
    """Appliqué par le moteur, qui ne peut pas importer les règles, mais déclaré
    ici avec les trois autres : la liste des seuils choisis à la main est
    complète au même endroit, et la valeur est celle du moteur."""
    from backend.risk_engine.config import MAX_STUDENT_NU

    assert STUDENT_NU_CEILING.chosen
    assert STUDENT_NU_CEILING.role is ThresholdRole.THRESHOLD
    assert STUDENT_NU_CEILING.value == MAX_STUDENT_NU == 30.0
    assert STUDENT_NU_CEILING.displayed == "30"
    choisis = [
        seuil
        for seuil in (
            STRONG_CORRELATION,
            MIN_SCENARIO_COVERAGE,
            MIN_REGRESSION_SAMPLE,
            MIN_ESTIMABLE_SAMPLE,
            STUDENT_NU_CEILING,
        )
        if seuil.chosen
    ]
    assert len(choisis) == 4
    assert "seuil CHOISI à la main" in str(STUDENT_NU_CEILING)


def test_le_minimum_de_seances_d_une_loi_est_le_cinquieme_seuil_choisi():
    """Appliqué par le moteur — refus de la Student, réserve sur la volatilité
    et la VaR paramétrique —, déclaré ici avec les quatre autres."""
    from backend.risk_engine.config import MIN_DISTRIBUTION_OBSERVATIONS

    assert MIN_DISTRIBUTION_SAMPLE.chosen
    assert MIN_DISTRIBUTION_SAMPLE.role is ThresholdRole.THRESHOLD
    assert MIN_DISTRIBUTION_SAMPLE.value == MIN_DISTRIBUTION_OBSERVATIONS == 30
    assert MIN_DISTRIBUTION_SAMPLE.displayed == "30"
    assert "seuil CHOISI à la main" in str(MIN_DISTRIBUTION_SAMPLE)
    choisis = [
        seuil
        for seuil in (
            STRONG_CORRELATION,
            MIN_SCENARIO_COVERAGE,
            MIN_REGRESSION_SAMPLE,
            MIN_ESTIMABLE_SAMPLE,
            STUDENT_NU_CEILING,
            MIN_DISTRIBUTION_SAMPLE,
        )
        if seuil.chosen
    ]
    assert len(choisis) == 5


class _Piege:
    """Une mesure que le moteur de règles n'a pas le droit de lire."""

    def __init__(self, nom: str) -> None:
        self._nom = nom

    def __getattr__(self, attribut: str):
        raise AssertionError(
            f"le moteur de règles a lu {self._nom}.{attribut} : une volatilité "
            "ou une VaR peut être une estimation mince, et une estimation mince "
            "n'entre dans aucune conclusion"
        )


def test_le_moteur_de_regles_ne_lit_ni_volatilite_ni_var(entrees):
    """Garde de comportement, pas de lecture du code : chaque volatilité et
    chaque VaR du rapport est remplacée par un piège qui lève à la moindre
    lecture, et les six règles s'évaluent quand même.

    C'est ce qui permet de publier une volatilité sur 7 séances sans qu'elle
    devienne un jour la prémisse d'une observation : aucune règle ne la lit.
    """
    risque, scenarios, regimes = entrees
    pieges = replace(
        risque,
        volatility=_Piege("volatility"),
        ewma_volatility=_Piege("ewma_volatility"),
        parametric_volatility=_Piege("parametric_volatility"),
        historical_var={c: _Piege("historical_var") for c in risque.historical_var},
        parametric_var={c: _Piege("parametric_var") for c in risque.parametric_var},
        expected_shortfall={
            c: _Piege("expected_shortfall") for c in risque.expected_shortfall
        },
        monte_carlo_var={c: _Piege("monte_carlo_var") for c in risque.historical_var},
    )
    rapport = evaluate(pieges, scenarios, regimes)
    assert {o.rule for o in rapport.observations} == set(RuleId)


def test_le_minimum_d_une_var_historique_est_un_seuil_derive():
    """Démontré, pas choisi : la queue doit contenir au moins une séance."""
    from backend.rules.thresholds import historical_var_sample

    for confiance, minimum in ((0.95, 20), (0.99, 100)):
        seuil = historical_var_sample(confiance)
        assert seuil.kind is ThresholdKind.DERIVED
        assert not seuil.chosen
        assert seuil.role is ThresholdRole.THRESHOLD
        assert seuil.value == minimum
        assert seuil.displayed == str(minimum)
        assert "référence calculée" in str(seuil)


def test_un_role_incoherent_avec_la_provenance_est_refuse():
    with pytest.raises(ValueError, match="choisi"):
        replace(STRONG_CORRELATION, role=ThresholdRole.REFERENCE)
    with pytest.raises(ValueError, match="relative au portefeuille"):
        replace(STRONG_CORRELATION, kind=ThresholdKind.PORTFOLIO_RELATIVE)


# Un même nombre a la même forme dans un même bloc : la ligne de seuil écrit
# `displayed`, la phrase aussi. Le seuil choisi s'écrivait « 0,70 » dans la
# phrase et « 0,7 » dessous.


def _sans_paire_forte(risque, rho):
    return replace(risque, matrices=replace(
        risque.matrices,
        correlation=matrice([[1.0, rho, 0.1], [rho, 1.0, 0.05], [0.1, 0.05, 1.0]], ["JNJ", "KO", "X"]),
    ))


def test_le_seuil_choisi_s_ecrit_comme_dans_la_phrase(risque):
    (obs,) = apparent_diversification(_sans_paire_forte(risque, 0.42))

    assert "aucune corrélation n'atteint 0,70." in obs.statement
    assert "  Seuil : corrélation forte = 0,70 (seuil CHOISI" in obs.render()
    assert "= 0,7 " not in obs.render()


def test_la_reference_de_la_paire_garde_ses_deux_decimales(risque):
    (obs,) = apparent_diversification(_sans_paire_forte(risque, 0.40))

    assert "La paire la plus liée est JNJ–KO, à 0,40." in obs.statement
    assert "  Référence : corrélation JNJ–KO = 0,40 (relatif au portefeuille)" in obs.render()


def test_une_egalite_exacte_s_ecrit_pareil_dans_la_phrase_et_la_reference(risque):
    # 0,125 est exact en binaire : round() le tranche au pair (0,12), toFixed
    # vers le haut (0,13). Arrondir la valeur avant de l'écrire donnait les
    # deux formes dans le même bloc.
    (obs,) = apparent_diversification(_sans_paire_forte(risque, 0.125))
    reference = obs.thresholds[1]

    assert "à 0,13." in obs.statement
    assert reference.displayed == "0,13"
    assert reference.value == 0.125, "la valeur publiée n'est pas arrondie d'avance"


def test_une_part_de_capital_ronde_garde_sa_decimale_dans_la_reference(risque):
    base = replace(
        risque,
        variance_contributions=_contributions({"A": 0.40, "B": 0.35, "C": 0.25}, {"A": 0.50, "B": 0.25, "C": 0.25}),
    )
    observations = {o.subject: o for o in variance_contribution(base)}

    obs = observations["B"]
    assert "B représente 25,0\u202f% de la valeur du portefeuille" in obs.statement
    assert "  Référence : part de B dans la valeur = 25,0\u202f% (référence calculée)" in obs.render()


def test_les_seuils_fixes_s_ecrivent_sous_la_forme_de_leur_phrase():
    assert STRONG_CORRELATION.displayed == "0,70"
    assert MIN_SCENARIO_COVERAGE.displayed == "80\u202f%"
    assert MIN_REGRESSION_SAMPLE.displayed == "60"
    assert MIN_ESTIMABLE_SAMPLE.displayed == "3"


def test_une_ligne_unique_n_a_pas_de_paire(risque):
    base = replace(risque, matrices=replace(risque.matrices, correlation=matrice([[1.0]], ["A"])))
    assert apparent_diversification(base) == []


# ======================================================== 4. Part systématique ==


def test_la_part_systematique_se_dit_sans_seuil(rapport):
    (obs,) = rapport.of_rule(RuleId.SYSTEMATIC_SHARE)
    r2 = obs.facts["r2"]

    assert f"{round(r2 * 100)}\u202f% des variations de votre portefeuille ont suivi" in obs.statement
    assert "celles du marché, le S&P" in obs.statement and "ne se dilue pas" in obs.statement
    assert obs.facts["part_propre"] == pytest.approx(1.0 - r2)
    assert obs.thresholds == ()


def test_sans_benchmark_pas_de_part_systematique(risque):
    assert systematic_share(replace(risque, beta=None)) == []


# ======================================================== 5. Dégradation en crise ==


def regime(key, nom, r2_crise, observations, r2_calme=0.49):
    scenario = Scenario(key, nom, date(2020, 1, 2), date(2020, 6, 1), "SPY", "Test.")
    commun = dict(beta=0.9, standard_error=0.02, start=date(2020, 1, 3), end=date(2020, 6, 1))
    return RegimeComparison(
        scenario=scenario,
        coverage=ScenarioCoverage(covered=("A",), excluded=(), covered_value=1.0, total_value=1.0),
        benchmark="SPY",
        portfolio_return=-0.3, benchmark_return=-0.3, amplification_ratio=1.0,
        crisis_beta=RegressedBeta(r_squared=r2_crise, observations=observations, **commun),
        calm_beta=RegressedBeta(r_squared=r2_calme, observations=504, **commun),
        predicted_return=-0.2,
    )


def test_la_part_systematique_monte_dans_les_crises_suffisantes():
    (obs,) = crisis_degradation([
        regime("gfc", "Crise 2008", 0.86, 355),
        regime("covid", "COVID", 0.98, 23),
        regime("taux", "Resserrement 2022", 0.79, 195),
    ])

    assert (
        "passe de 49\u202f% ces deux\u00a0dernières années à 86\u202f% pendant l'épisode "
        "Crise 2008 et à 79\u202f% pendant l'épisode Resserrement 2022."
    ) in obs.statement
    assert "Dans ces deux crises, la diversification entre vos lignes s'est affaiblie" in obs.statement
    assert "trois crises" not in obs.statement
    assert "pendant l'épisode COVID" not in obs.statement, "la crise mince est citée à part"
    assert obs.thresholds == (MIN_REGRESSION_SAMPLE,)
    assert obs.facts["crises_en_hausse"] == 2
    assert obs.facts["crises_en_hausse_echantillon_mince"] == 1


def test_une_baisse_est_dite_telle_quelle_sans_seuil_superflu():
    (obs,) = crisis_degradation([
        regime("a", "A", 0.80, 200), regime("b", "B", 0.40, 200), regime("c", "C", 0.70, 200),
    ])
    assert "Elle augmente dans deux de ces trois crises." in obs.statement
    assert obs.thresholds == ()


# Une conclusion ne compte que les crises estimées sur au moins
# MIN_REGRESSION_SAMPLE séances. Celles sous le seuil sont citées à part, avec
# leur sens, hors du décompte : la même phrase ne peut pas qualifier un
# échantillon de trop mince puis le compter comme une preuve.


def test_toutes_les_crises_suffisantes_entrent_dans_la_conclusion():
    (obs,) = crisis_degradation([
        regime("gfc", "Crise 2008", 0.86, 355),
        regime("covid", "COVID", 0.98, 100),
        regime("taux", "Resserrement 2022", 0.79, 195),
    ])

    assert (
        "Dans ces trois crises, la diversification entre vos lignes s'est affaiblie au "
        "moment où elle aurait servi."
    ) in obs.statement
    assert "trop peu pour conclure" not in obs.statement
    assert obs.thresholds == ()
    assert obs.facts["crises_comparees"] == 3
    assert obs.facts["crises_en_hausse"] == 3
    assert obs.facts["crises_comparees_echantillon_mince"] == 0


def test_une_crise_mince_est_citee_a_part_hors_du_decompte():
    (obs,) = crisis_degradation([
        regime("gfc", "Crise 2008", 0.86, 355),
        regime("covid", "COVID", 0.98, 23),
        regime("taux", "Resserrement 2022", 0.79, 195),
    ])

    assert (
        "Dans ces deux crises, la diversification entre vos lignes s'est affaiblie au "
        "moment où elle aurait servi. L'épisode COVID va dans le même sens (98\u202f%), "
        "mais sur 23\u00a0jours de bourse seulement : trop peu pour conclure."
    ) in obs.statement
    assert obs.facts["crises_comparees"] == 2
    assert obs.facts["crises_en_hausse"] == 2
    assert obs.facts["crises_comparees_echantillon_mince"] == 1
    assert obs.facts["crises_en_hausse_echantillon_mince"] == 1


def test_une_crise_mince_en_sens_contraire_le_dit():
    (obs,) = crisis_degradation([
        regime("gfc", "Crise 2008", 0.86, 355),
        regime("covid", "COVID", 0.30, 23),
        regime("taux", "Resserrement 2022", 0.79, 195),
    ])

    assert "Dans ces deux crises, la diversification entre vos lignes s'est affaiblie" in obs.statement
    assert (
        "L'épisode COVID va en sens contraire (30\u202f%), mais sur 23\u00a0jours de "
        "bourse seulement : trop peu pour conclure."
    ) in obs.statement


def test_quand_les_crises_suffisantes_divergent_la_crise_mince_dit_son_sens():
    # « Même sens » n'aurait pas de référent : le sens est dit en clair.
    (obs,) = crisis_degradation([
        regime("a", "A", 0.80, 200),
        regime("b", "B", 0.40, 200),
        regime("covid", "COVID", 0.98, 23),
    ])

    assert "Elle augmente dans une de ces deux crises." in obs.statement
    assert (
        "Pendant l'épisode COVID, elle augmente (98\u202f%), mais sur 23\u00a0jours de "
        "bourse seulement : trop peu pour conclure."
    ) in obs.statement
    assert "même sens" not in obs.statement


def test_sans_crise_suffisante_aucune_conclusion_generale():
    (obs,) = crisis_degradation([
        regime("covid", "COVID", 0.98, 23),
        regime("x", "Flash", 0.70, 40),
    ])

    # Aucune phrase de conclusion : chaque crise dit elle-même qu'elle repose
    # sur trop peu de jours pour conclure.
    assert obs.statement.startswith(
        "La part des variations qui suit le marché est de 49\u202f% ces "
        "deux\u00a0dernières années."
    )
    for nom, part, jours in (("COVID", "98", 23), ("Flash", "70", 40)):
        assert (
            f"Pendant l'épisode {nom}, elle augmente ({part}\u202f%), mais sur "
            f"{jours}\u00a0jours de bourse seulement : trop peu pour conclure."
        ) in obs.statement
    assert "affaiblie" not in obs.statement
    assert "Elle augmente dans" not in obs.statement
    assert obs.facts["crises_comparees"] == 0
    assert obs.facts["crises_en_hausse"] == 0
    assert obs.facts["crises_comparees_echantillon_mince"] == 2


def test_une_seule_crise_mince_ne_conclut_rien():
    (obs,) = crisis_degradation([regime("covid", "COVID", 0.98, 23)])

    assert (
        "Pendant l'épisode COVID, elle augmente (98\u202f%), mais sur 23\u00a0jours de "
        "bourse seulement : trop peu pour conclure."
    ) in obs.statement
    assert "affaiblie" not in obs.statement


def test_sans_comparaison_disponible_aucune_observation():
    indisponible = replace(regime("a", "A", 0.8, 200), unavailable_reason="aucune ligne couverte")
    assert crisis_degradation([indisponible]) == []


# ================================================ 6. Couverture d'un scénario ==


def test_un_scenario_complet_ne_produit_pas_d_observation(entrees):
    (resultat,) = entrees[1]
    complet = replace(resultat, coverage=ScenarioCoverage(("A", "B", "C"), (), 1.0, 1.0))
    assert scenario_coverage([complet]) == []


def test_une_couverture_partielle_donne_le_chiffre_avec_sa_portee(conn):
    peupler(conn, part_de_c=0.10)
    (obs,) = evaluer(conn).of_rule(RuleId.SCENARIO_COVERAGE)

    assert obs.facts["part_couverte"] == pytest.approx(0.90, abs=0.01)
    assert "resultat_partie_couverte" in obs.facts
    assert (
        "L'épisode Crise de test ne se rejoue que sur 90\u202f% de votre portefeuille "
        "(2\u00a0lignes sur 3) : C n'était pas encore coté."
    ) in obs.statement
    assert "ne porte que sur cette partie" in obs.statement
    assert "Les lignes absentes n'ont pas été rejouées" in obs.statement
    # Correction 2 du 2026-10-05 : aucune généralité sur le sens de l'écart.
    assert "sous-estime" not in obs.statement
    assert obs.thresholds == (MIN_SCENARIO_COVERAGE,)


def test_le_sujet_d_une_crise_rejouee_en_partie_est_son_nom_jamais_sa_cle(rapport):
    """La page affiche le sujet tel quel, à côté du libellé : « gfc_2008 » y
    serait une clé technique sous les yeux du lecteur."""
    (obs,) = rapport.of_rule(RuleId.SCENARIO_COVERAGE)
    assert obs.subject == CRISE.name == "Crise de test"
    assert obs.subject != CRISE.key

    # Aucun sujet, d'aucune règle, n'a la forme d'une clé technique.
    cle = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")
    assert cle.match(CRISE.key), "le témoin a bien la forme d'une clé"
    for observation in rapport.observations:
        assert cle.match(observation.subject) is None, observation.subject


def test_sous_le_seuil_aucun_chiffre_principal(conn):
    """70 % de couverture : un chiffre aurait été produit sous l'ancien seuil de
    50 %, il ne l'est plus. Le chiffre décrirait la partie la plus établie du
    portefeuille, et la partie exclue pèse trop pour que le biais reste borné."""
    peupler(conn, part_de_c=0.30)
    (obs,) = evaluer(conn).of_rule(RuleId.SCENARIO_COVERAGE)

    assert obs.facts["part_couverte"] == pytest.approx(0.70, abs=0.01)
    assert obs.facts["part_couverte"] < MIN_SCENARIO_COVERAGE.value
    assert "resultat_partie_couverte" not in obs.facts
    assert "moins de 80\u202f%, trop peu pour donner un chiffre pour l'ensemble" in obs.statement
    assert "Son résultat" not in obs.statement


def test_sans_ligne_couverte_aucun_chiffre(entrees):
    (resultat,) = entrees[1]
    vide = replace(
        resultat,
        coverage=ScenarioCoverage((), (ExcludedPosition("A", "absent", 1.0, 1.0),), 0.0, 1.0),
        end_to_end_return=None, max_drawdown=None, contributions=(),
    )
    (obs,) = scenario_coverage([vide])
    assert obs.statement == (
        "Impossible de rejouer l'épisode Crise de test : aucune de vos lignes n'était "
        "cotée pendant toute cette crise."
    )


# ============================================ Avertissement attaché au CVaR 99 % ==


def queue(niveau, observations):
    return ExpectedShortfallResult(
        value=0.03, confidence=niveau, tail_observations=observations, threshold=-0.02, window=FENETRE,
    )


def test_le_cvar_a_99_porte_en_permanence_son_avertissement():
    """Attaché au chiffre, pas déclenché par lui : présent quelle que soit la
    taille de la queue, y compris quand elle serait « suffisante »."""
    assert queue(0.99, 6).caveat == (
        "Moyenne de 6\u00a0jours de bourse seulement, sur 504 : chacun pèse pour "
        "17\u202f% du chiffre."
    )
    assert "50\u00a0jours de bourse" in queue(0.99, 50).caveat
    assert queue(0.95, 26).caveat is None


def test_la_fragilite_de_la_queue_n_est_plus_une_regle_qui_se_declenche(rapport):
    assert "fragilité de la queue" not in {r.value for r in RuleId}
    assert all("CVaR" not in o.statement for o in rapport.observations)


# ================================================================== Seuils ==


def test_chaque_seuil_choisi_dit_qu_il_a_ete_choisi():
    for seuil in (STRONG_CORRELATION, MIN_SCENARIO_COVERAGE, MIN_REGRESSION_SAMPLE):
        assert seuil.kind is ThresholdKind.CHOSEN
        assert "CHOISI à la main, non dérivé des données" in str(seuil)


def test_la_couverture_minimale_est_plus_stricte_qu_un_pile_ou_face():
    assert MIN_SCENARIO_COVERAGE.value == 0.80
    assert "= 80 %" in str(MIN_SCENARIO_COVERAGE)
    assert "d'un cinquième" in MIN_SCENARIO_COVERAGE.rationale


def test_la_justification_du_seuil_de_couverture_dit_ce_qui_est_vrai():
    """Sous 80 % de la valeur, la partie rejouée ne représente plus assez
    l'ensemble. Le seuil ne dit pas que la partie exclue est « en moyenne plus
    spéculative » : le moteur ne le mesure pas."""
    assert MIN_SCENARIO_COVERAGE.rationale.startswith(
        "sous 80\u202f% de la valeur, la partie rejouée ne représente plus assez "
        "l'ensemble pour en tirer un chiffre ; "
    )
    for generalite in ("spéculati", "plus récente", "biais"):
        assert generalite not in str(MIN_SCENARIO_COVERAGE), generalite


def test_un_seuil_calcule_ne_se_presente_pas_comme_choisi(rapport):
    (seuil,) = rapport.of_rule(RuleId.VARIANCE_CONTRIBUTION)[0].thresholds
    assert "CHOISI" not in str(seuil)
    assert "référence calculée" in str(seuil)


# ================================================================== Bandeau ==


def test_le_bandeau_couvre_les_points_attendus():
    texte = acceptance_text()
    for attendu in (
        "pas un conseil en investissement réglementé",
        "Aucune garantie",
        "504 dernières séances de bourse, soit environ 2 ans",
        "Elles ne prédisent pas son comportement futur",
        "ne prédisent ni la survenue, ni l'ampleur, ni la forme",
        "à vos propres risques",
    ):
        assert attendu in texte, attendu


def test_la_duree_du_bandeau_ne_se_separe_pas_de_son_unite():
    """« soit environ 2 » finissait une ligne que « ans. » commençait, sur
    l'écran d'acceptation à 390 px (captures du 2026-10-05)."""
    assert "soit environ 2 ans." in acceptance_text(504)
    assert "soit environ 1 an." in acceptance_text(252)
    assert "soit environ 6 mois." in acceptance_text(126)


def test_le_bandeau_et_les_observations_vouvoient(rapport):
    """Un seul registre dans toute la page, comme les phrases de lecture
    (décision D1 du 2026-10-05). Les observations tutoyaient."""
    tutoiement = re.compile(r"\b(tu|ton|ta|tes|toi)\b", re.IGNORECASE)
    vouvoiement = re.compile(r"\b(vous|votre|vos)\b", re.IGNORECASE)

    assert tutoiement.search(rapport.disclaimer) is None
    assert vouvoiement.search(rapport.disclaimer)
    for observation in rapport.observations:
        assert tutoiement.search(observation.statement) is None, observation.statement
    concentration_obs = rapport.of_rule(RuleId.EFFECTIVE_CONCENTRATION)[0]
    assert vouvoiement.search(concentration_obs.statement)


def test_le_bandeau_suit_la_fenetre_reellement_utilisee(rapport):
    assert "252 dernières séances de bourse, soit environ 1 an" in acceptance_text(252)
    assert "100 dernières séances" in rapport.disclaimer


# ====================================================== Données réelles ==


def test_regles_sur_un_portefeuille_reel(base_figee):
    with closing(connect(base_figee)) as c:
        c.execute("INSERT INTO portfolios (owner) VALUES ('demo')")
        pid = c.execute("SELECT MAX(id) FROM portfolios").fetchone()[0]
        for ticker, quantite in {"AAPL": 40, "MSFT": 25, "JPM": 60, "JNJ": 50, "XOM": 80, "KO": 120}.items():
            c.execute(
                "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (?,?,?)",
                (pid, ticker, quantite),
            )
        c.commit()
        resultat = evaluate_portfolio(c, pid)

    contributions = {o.subject: o for o in resultat.of_rule(RuleId.VARIANCE_CONTRIBUTION)}
    assert len(contributions) == 6
    assert sum(o.facts["part_de_variance"] for o in contributions.values()) == pytest.approx(1.0, abs=1e-12)
    # La ligne énergie a coûté dans certaines crises et sauvé le portefeuille en 2022.
    assert "XOM a joué dans les deux sens" in contributions["XOM"].statement
    assert contributions["XOM"].facts["scenario:tightening_2022"] > 0
    # Les noms du catalogue prennent l'article qu'il déclare.
    (crise,) = resultat.of_rule(RuleId.CRISIS_DEGRADATION)
    assert "pendant la Crise financière 2008" in crise.statement
    assert "pendant le Resserrement monétaire 2022" in crise.statement
    assert "Le Krach COVID va dans le même sens" in crise.statement
    for observation in resultat.observations:
        assert PRESCRIPTIF.search(observation.render()) is None
    assert "504 dernières séances" in resultat.disclaimer


# ================================================ Taille de l'échantillon ==
#
# Deux régimes, et la frontière entre les deux n'est pas une convention.
#
# Sous trois observations, une corrélation vaut ±1 et un R² vaut 1 — par
# construction, quelles que soient les données : une régression avec constante
# n'a plus aucun degré de liberté résiduel. Une phrase qui affirme ces valeurs
# décrit une identité arithmétique en la faisant passer pour une propriété du
# portefeuille, et aucune mention d'« échantillon mince » ne répare ça.
#
# Entre trois séances et le seuil de régression, le chiffre est une estimation
# réelle mais fragile : il est rendu, et signalé.


def fenetre_de(observations: int) -> Window:
    return Window(
        requested=504,
        observations=observations,
        start=date(2026, 9, 8),
        end=date(2026, 9, 9),
    )


def avec_correlation(report, valeurs, tickers, observations: int):
    return replace(
        report,
        matrices=replace(
            report.matrices,
            correlation=matrice(valeurs, tickers),
            window=fenetre_de(observations),
        ),
    )


# ------------------------------------------------- Refus sous trois séances --


def test_sous_trois_seances_aucune_correlation_n_est_chiffree(risque):
    """Deux points sont toujours alignés : |ρ| = 1 n'est pas une mesure."""
    base = avec_correlation(risque, [[1.0, 1.0], [1.0, 1.0]], ["A", "B"], 2)
    (obs,) = apparent_diversification(base)

    assert obs.subject == "portefeuille"
    assert "corrélation de 1,00" not in obs.statement
    assert "une corrélation n'a pas de sens : il en faut au moins 3." in obs.statement
    assert obs.facts["correlation_max"] is None
    assert obs.facts["seances"] == 2


def test_sous_trois_seances_la_part_systematique_n_est_pas_chiffree(risque):
    base = replace(risque, beta=replace(risque.beta, r_squared=1.0, window=fenetre_de(2)))
    (obs,) = systematic_share(base)

    assert "R² 1,00" not in obs.statement
    assert "100\u202f%" not in obs.statement
    assert (
        "la part des variations qui suit le marché n'a pas de sens : il en faut au moins 3."
    ) in obs.statement
    assert obs.facts["r2"] is None
    assert obs.facts["part_propre"] is None


def test_le_refus_porte_un_seuil_derive_et_non_choisi(risque):
    """Le 3 se démontre, il ne se choisit pas.

    Une régression avec constante a n − 2 degrés de liberté résiduels. Le
    « pourquoi » doit être lisible par la machine — via `kind` — et pas
    seulement dans la phrase.
    """
    refus = [
        apparent_diversification(
            avec_correlation(risque, [[1.0, 1.0], [1.0, 1.0]], ["A", "B"], 2)
        )[0],
        systematic_share(replace(risque, beta=replace(risque.beta, window=fenetre_de(2))))[0],
    ]
    for obs in refus:
        (seuil,) = obs.thresholds
        assert seuil is MIN_ESTIMABLE_SAMPLE
        assert seuil.kind is ThresholdKind.DERIVED
        assert seuil.value == 3.0
        assert obs.uses_chosen_threshold is False
        # La rationale couvre les TROIS mesures : elle ne peut donc invoquer ni
        # une régression, ni un coefficient à ±1.
        assert "le centrage ne laisse qu'une seule direction" in seuil.rationale
        assert "régression" not in seuil.rationale


# ---------------------------------------- Signalement de trois à soixante --


def test_a_trois_seances_la_correlation_est_chiffree_et_signalee_mince(risque):
    """À trois observations le coefficient mesure enfin quelque chose, mal."""
    base = avec_correlation(risque, [[1.0, 0.95], [0.95, 1.0]], ["A", "B"], 3)
    (obs,) = apparent_diversification(base)

    assert obs.facts["correlation"] == pytest.approx(0.95)
    assert "Estimation mince : sur 3\u00a0jours de bourse" in obs.statement
    assert MIN_REGRESSION_SAMPLE in obs.thresholds
    assert obs.uses_chosen_threshold


def test_a_trois_seances_la_part_systematique_est_chiffree_et_signalee_mince(risque):
    base = replace(risque, beta=replace(risque.beta, window=fenetre_de(3)))
    (obs,) = systematic_share(base)

    assert obs.facts["r2"] is not None
    assert "Estimation mince : sur 3\u00a0jours de bourse" in obs.statement
    assert obs.thresholds == (MIN_REGRESSION_SAMPLE,)


def test_la_paire_la_plus_correlee_est_aussi_signalee_mince(risque):
    base = avec_correlation(risque, [[1.0, 0.42], [0.42, 1.0]], ["A", "B"], 40)
    (obs,) = apparent_diversification(base)

    assert "Estimation mince : sur 40\u00a0jours de bourse" in obs.statement
    kinds = [s.kind for s in obs.thresholds]
    assert kinds == [
        ThresholdKind.CHOSEN,
        ThresholdKind.PORTFOLIO_RELATIVE,
        ThresholdKind.CHOSEN,
    ]


@pytest.mark.parametrize("observations", [60, 100, 504])
def test_au_dela_du_seuil_aucune_mention_ni_seuil_supplementaire(risque, observations):
    """Le seuil est franchi À 60, pas au-dessus : la borne est inclusive."""
    base = replace(risque, beta=replace(risque.beta, window=fenetre_de(observations)))
    (obs,) = systematic_share(base)

    assert "Estimation mince" not in obs.statement
    assert obs.thresholds == ()


# ------------------------------------------------------ Garde lexicale --


@pytest.mark.parametrize("observations", [2, 3, 10, 40, 59])
def test_aucune_valeur_degeneree_n_est_affirmee_sans_signalement(risque, observations):
    """La garde qui résume les deux régimes.

    Sous soixante séances, une phrase ne peut porter « 1,00 » qu'à deux
    conditions : que la valeur ait été réellement estimée (trois observations
    au moins) et qu'elle soit accompagnée du seuil CHOISI. Sous trois
    observations, la valeur n'apparaît pas du tout.

    L'arrondi compte ici : `_decimal(rho, 2)` rend « 1,00 » pour 0,9987, ce qui
    est légitime sur quarante séances et ne l'est pas sur deux.
    """
    parfait = avec_correlation(
        risque, [[1.0, 1.0], [1.0, 1.0]], ["A", "B"], observations
    )
    parfait = replace(
        parfait, beta=replace(parfait.beta, r_squared=1.0, window=fenetre_de(observations))
    )
    observations_rendues = apparent_diversification(parfait) + systematic_share(parfait)
    assert observations_rendues

    for obs in observations_rendues:
        # Un R² de 1 se lit « 100 % des variations … ont suivi celles du marché ».
        degeneree = (
            "corrélation de 1,00" in obs.statement
            or "100\u202f% des variations" in obs.statement
        )
        if observations < 3:
            assert not degeneree, obs.statement
            assert obs.thresholds == (MIN_ESTIMABLE_SAMPLE,)
        elif degeneree:
            assert MIN_REGRESSION_SAMPLE in obs.thresholds, obs.statement
            assert "Estimation mince" in obs.statement


def test_les_refus_ne_prescrivent_rien_non_plus(risque):
    """La garde lexicale du module vaut aussi pour les phrases de refus."""
    base = avec_correlation(risque, [[1.0, 1.0], [1.0, 1.0]], ["A", "B"], 2)
    base = replace(base, beta=replace(base.beta, window=fenetre_de(2)))
    for obs in apparent_diversification(base) + systematic_share(base):
        assert PRESCRIPTIF.search(obs.render()) is None, obs.render()

# ------------------------- Règles 1 et 2 : la même matrice, les mêmes régimes --
#
# La covariance ne sert pas qu'aux corrélations et au beta : les contributions à
# la variance et les lignes effectives « en risque » en sortent aussi. À n = 2,
# Σ est de rang 1 et la contribution de i se réduit exactement à
# `wᵢδᵢ / (wᵀδ)` — la part de chaque ligne dans UNE différence journalière.


def avec_fenetre_de_variance(report, observations: int):
    return replace(
        report,
        variance_contributions=replace(
            report.variance_contributions, window=fenetre_de(observations)
        ),
    )


def test_sous_trois_seances_aucune_part_de_variance_n_est_chiffree(risque):
    (obs,) = variance_contribution(avec_fenetre_de_variance(risque, 2))

    assert obs.subject == "portefeuille"
    assert (
        "la part de chaque ligne dans les variations n'a pas de sens : il en faut au moins 3."
    ) in obs.statement
    assert obs.facts.get("part_de_variance") is None
    assert "%" not in obs.statement.replace("séances", "")
    (seuil,) = obs.thresholds
    assert seuil is MIN_ESTIMABLE_SAMPLE
    assert seuil.kind is ThresholdKind.DERIVED


def test_sous_trois_seances_les_lignes_effectives_en_risque_ne_sont_pas_dites(risque):
    """La moitié EN CAPITAL survit : c'est une mesure ponctuelle, sans fenêtre.

    Seule la lecture en risque disparaît, et elle dit pourquoi — plutôt que de
    laisser croire que le risque se concentre sur 1,4 ligne.
    """
    obs = effective_concentration(avec_fenetre_de_variance(risque, 2))

    assert "lignes de même montant" in obs.statement
    assert "Ce qu'elles font bouger n'est pas chiffré." in obs.statement
    assert "ce calcul n'a pas de sens : il en faut au moins 3." in obs.statement
    assert obs.facts["lignes_effectives_capital"] is not None
    assert obs.facts["lignes_effectives_risque"] is None
    (seuil,) = obs.thresholds
    assert seuil is MIN_ESTIMABLE_SAMPLE


def test_a_trois_seances_les_deux_regles_chiffrent_et_signalent(risque):
    base = avec_fenetre_de_variance(risque, 3)

    concentration_obs = effective_concentration(base)
    assert concentration_obs.facts["lignes_effectives_risque"] is not None
    assert "Estimation mince : sur 3\u00a0jours de bourse" in concentration_obs.statement
    assert concentration_obs.thresholds == (MIN_REGRESSION_SAMPLE,)

    contributions = variance_contribution(base)
    assert len(contributions) == len(risque.variance_contributions.contributions)
    for obs in contributions:
        assert obs.facts["part_de_variance"] is not None
        assert "Estimation mince : sur 3\u00a0jours de bourse" in obs.statement
        assert MIN_REGRESSION_SAMPLE in obs.thresholds
        assert obs.uses_chosen_threshold


@pytest.mark.parametrize("observations", [60, 100, 504])
def test_au_dela_du_seuil_les_deux_regles_ne_signalent_rien(risque, observations):
    base = avec_fenetre_de_variance(risque, observations)

    concentration_obs = effective_concentration(base)
    assert "Estimation mince" not in concentration_obs.statement
    assert concentration_obs.thresholds == ()

    for obs in variance_contribution(base):
        assert "Estimation mince" not in obs.statement
        # Seule la part de capital de la ligne, qui n'est pas un seuil de taille.
        assert [s.kind for s in obs.thresholds] == [ThresholdKind.DERIVED]


def test_les_quatre_regles_portent_le_seuil_choisi_sur_un_echantillon_mince(risque):
    """Les quatre règles qui lisent la covariance, d'un coup.

    C'était le trou : le minimum de 60 séances ne s'appliquait qu'aux
    régressions de crise, alors que quatre règles reposent sur la même matrice.
    """
    base = avec_fenetre_de_variance(risque, 40)
    base = replace(
        base,
        beta=replace(base.beta, window=fenetre_de(40)),
        matrices=replace(base.matrices, window=fenetre_de(40)),
    )

    rendues = [
        effective_concentration(base),
        *variance_contribution(base),
        *apparent_diversification(base),
        *systematic_share(base),
    ]
    regles = {o.rule for o in rendues}
    assert regles == {
        RuleId.EFFECTIVE_CONCENTRATION,
        RuleId.VARIANCE_CONTRIBUTION,
        RuleId.APPARENT_DIVERSIFICATION,
        RuleId.SYSTEMATIC_SHARE,
    }
    for obs in rendues:
        assert MIN_REGRESSION_SAMPLE in obs.thresholds, obs.rule


def test_les_refus_des_regles_1_et_2_ne_prescrivent_rien(risque):
    base = avec_fenetre_de_variance(risque, 2)
    for obs in (effective_concentration(base), *variance_contribution(base)):
        assert PRESCRIPTIF.search(obs.render()) is None, obs.render()


# ==================================================== Pour un lecteur qui part de zéro ==
#
# Les observations s'affichent telles quelles devant un lecteur qui ne connaît
# ni la variance ni le R² (textes de lecture validés le 2026-10-05, D7). Les
# tests ci-dessus suivent les textes du document ; ceux-ci fixent les variantes
# qu'il n'écrivait pas.


def test_les_phrases_disent_jours_de_bourse_et_les_provenances_seances(rapport, risque):
    """« Séance » reste le mot des provenances et des seuils, jamais celui
    d'une phrase : celles-ci se lisent à côté des phrases de lecture."""
    refus = avec_correlation(avec_fenetre_de_variance(risque, 2), [[1.0, 1.0], [1.0, 1.0]], ["A", "B"], 2)
    refus = replace(refus, beta=replace(refus.beta, window=fenetre_de(2)))
    minces = avec_fenetre_de_variance(risque, 40)
    observations = [
        *rapport.observations,
        effective_concentration(refus),
        *variance_contribution(refus),
        *apparent_diversification(refus),
        *systematic_share(refus),
        effective_concentration(minces),
        *variance_contribution(minces),
    ]
    for obs in observations:
        assert "séance" not in obs.statement, obs.statement
    assert any("séances" in obs.provenance for obs in observations)


def test_le_catalogue_declare_l_article_de_chaque_crise():
    """« pendant la Crise financière 2008 » : le genre d'un nom ne se devine pas."""
    assert [s.with_article for s in SCENARIOS] == [
        "la Crise financière 2008",
        "le Krach COVID",
        "le Resserrement monétaire 2022",
    ]
    bulle = replace(SCENARIOS[0], name="Éclatement de la bulle", article="l'")
    assert bulle.with_article == "l'Éclatement de la bulle"
    # Sans article déclaré : « l'épisode », correct quel que soit le nom.
    assert CRISE.with_article == "l'épisode Crise de test"


def test_une_seule_crise_rejouee_dit_ce_que_chaque_ligne_a_coute_ou_rapporte(entrees):
    risque, (modele,), _ = entrees
    seule = _scenario(modele, "krach", "Krach", {"A": -0.076, "B": 0.02})
    obs = {o.subject: o for o in variance_contribution(risque, (seule,))}

    assert (
        "Dans la crise rejouée (Krach), A a coûté 7,6\u00a0points au portefeuille."
    ) in obs["A"].statement
    assert (
        "Dans la crise rejouée (Krach), B a rapporté 2,0\u00a0points au portefeuille."
    ) in obs["B"].statement


def test_une_couverture_partielle_en_gain_ne_parle_pas_de_perte(entrees):
    """Une ligne sans cours n'était pas « pas encore cotée » : elle ne l'était
    pas pendant TOUTE la crise. Et un gain ne se dit pas « perte »."""
    _, (modele,), _ = entrees
    rebond = _scenario(modele, "rebond", "Rebond", {"A": 0.05, "B": 0.03}, part_couverte=0.90)
    (obs,) = scenario_coverage([rebond])

    assert (
        "L'épisode Rebond ne se rejoue que sur 90\u202f% de votre portefeuille "
        "(2\u00a0lignes sur 3) : Z n'était pas coté pendant toute la crise."
    ) in obs.statement
    assert "le résultat de l'ensemble a pu être différent." in obs.statement
    assert "perte" not in obs.statement


def test_une_crise_sans_deux_jours_communs_dit_pourquoi(entrees):
    """Des lignes couvertes, mais moins de deux jours de bourse en commun : la
    cause n'est pas « aucune ligne cotée »."""
    (resultat,) = entrees[1]
    sans_jours = replace(
        resultat,
        coverage=ScenarioCoverage(("A",), (ExcludedPosition("B", "absent", 0.5, 0.5),), 0.5, 1.0),
        end_to_end_return=None, max_drawdown=None, contributions=(),
    )
    (obs,) = scenario_coverage([sans_jours])
    assert obs.statement == (
        "Impossible de rejouer l'épisode Crise de test : les lignes cotées pendant toute "
        "cette crise ont moins de deux jours de bourse en commun."
    )


def test_un_temps_ordinaire_propre_a_chaque_crise_est_dit_crise_par_crise():
    """En couverture partielle, le temps ordinaire est mesuré sur les lignes
    rejouées de chaque crise : sa part change d'une crise à l'autre."""
    (obs,) = crisis_degradation([
        regime("gfc", "Crise 2008", 0.86, 355, r2_calme=0.45),
        regime("taux", "Resserrement 2022", 0.79, 195),
        replace(regime("x", "X", 0.8, 200), unavailable_reason="aucune ligne couverte"),
    ])

    assert obs.statement.startswith(
        "Mesurée sur les lignes rejouées de chaque crise, la part des variations qui "
        "suit le marché passe de 45\u202f% ces deux\u00a0dernières années à 86\u202f% "
        "pendant l'épisode Crise 2008 et de 49\u202f% à 79\u202f% pendant l'épisode "
        "Resserrement 2022."
    )
    assert obs.statement.endswith("Pas de comparaison possible pour l'épisode X.")
    assert obs.facts["r2_calme"] is None


def test_une_ligne_unique_sous_trois_seances_garde_sa_moitie_en_capital(risque):
    base = replace(avec_fenetre_de_variance(risque, 2), concentration=concentration(1, 1.0))
    obs = effective_concentration(base)

    assert obs.statement == (
        "Votre portefeuille compte une seule ligne : elle en porte tout le montant. "
        "Ce qu'elle fait bouger n'est pas chiffré. Sur 2\u00a0jours de bourse, ce "
        "calcul n'a pas de sens : il en faut au moins 3."
    )
