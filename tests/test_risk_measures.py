"""Tests des mesures pures, sur données synthétiques à résultat connu.

Aucune base de données : ces fonctions prennent des tableaux et rendent des
nombres, et chaque attendu est calculable à la main.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.risk_engine.measures import (
    annualised_volatility,
    downside_deviation,
    equal_weight_reference,
    ewma_volatility,
    herfindahl_index,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from backend.risk_engine.returns import (
    align_panel,
    log_returns,
    portfolio_returns,
    simple_returns,
    wealth_curve,
)

RACINE_252 = math.sqrt(252)


def jours(n: int, depart: date = date(2026, 1, 5)) -> list[date]:
    return [depart + timedelta(days=i) for i in range(n)]


def serie(valeurs, depart: date = date(2026, 1, 5)) -> pd.Series:
    return pd.Series(list(valeurs), index=jours(len(valeurs), depart))


# ------------------------------------------------------------- Rendements --


def test_rendement_simple_et_log_different_sur_les_grandes_variations():
    prix = serie([100.0, 110.0])
    assert simple_returns(prix).iloc[0] == pytest.approx(0.10)
    assert log_returns(prix).iloc[0] == pytest.approx(math.log(1.10))


def test_l_agregation_entre_titres_exige_des_rendements_simples():
    """La correction de la spec, verrouillée par un test.

    Deux lignes de 50, l'une +10 %, l'autre −10 %. La valeur passe de 100 à
    55 + 45 = 100 : le rendement du portefeuille est exactement zéro. La moyenne
    pondérée des rendements SIMPLES le retrouve. Celle des rendements LOG rend
    −0,50 %, une perte qui n'a pas eu lieu.
    """
    rendements = pd.DataFrame(
        {"A": [0.10], "B": [-0.10]}, index=jours(1)
    )
    poids = {"A": 0.5, "B": 0.5}

    assert portfolio_returns(rendements, poids).iloc[0] == pytest.approx(0.0)

    faux = 0.5 * math.log(1.10) + 0.5 * math.log(0.90)
    assert faux == pytest.approx(-0.005025, abs=1e-6)
    assert faux != pytest.approx(0.0, abs=1e-4)


def test_les_poids_sont_apparies_par_etiquette_pas_par_position():
    # Colonnes dans un ordre, poids dans l'autre : un appariement positionnel
    # attribuerait le poids de A à B sans rien signaler.
    rendements = pd.DataFrame({"B": [0.20], "A": [0.00]}, index=jours(1))
    resultat = portfolio_returns(rendements, {"A": 0.25, "B": 0.75})
    assert resultat.iloc[0] == pytest.approx(0.15)


def test_un_titre_sans_serie_leve_une_erreur():
    rendements = pd.DataFrame({"A": [0.01]}, index=jours(1))
    with pytest.raises(KeyError, match="ZZZZ"):
        portfolio_returns(rendements, {"A": 0.5, "ZZZZ": 0.5})


def test_l_alignement_retire_les_dates_incompletes():
    dates = jours(3)
    panel = pd.DataFrame(
        {"A": [10.0, 11.0, 12.0], "B": [20.0, None, 22.0]}, index=dates
    )
    aligne = align_panel(panel)

    assert list(aligne.index) == [dates[0], dates[2]]
    assert not aligne.isna().any().any()


# ------------------------------------------------------------ Volatilité --


def test_une_serie_a_rendement_constant_a_une_volatilite_nulle():
    assert annualised_volatility([0.01] * 50) == 0.0


def test_la_volatilite_estimee_sur_une_normale_est_dans_la_tolerance():
    rng = np.random.default_rng(42)
    rendements = rng.normal(0.0, 0.01, 4000)

    attendu = 0.01 * RACINE_252
    assert annualised_volatility(rendements) == pytest.approx(attendu, rel=0.05)


def test_la_volatilite_annualise_par_racine_de_252():
    rendements = [0.02, 0.0, 0.02, 0.0]
    quotidienne = float(np.std(rendements, ddof=1))
    assert annualised_volatility(rendements) == pytest.approx(quotidienne * RACINE_252)


def test_ewma_sans_centrage_ne_rend_pas_zero_sur_une_serie_constante():
    """Conséquence assumée de la convention RiskMetrics.

    L'écart-type d'une série constante est nul — il mesure la dispersion autour
    de la moyenne. L'EWMA non centrée mesure l'ampleur des rendements eux-mêmes
    et rend |r|·√252. Les deux sont justes : ils ne répondent pas à la même
    question, et c'est pourquoi la convention est documentée.
    """
    constante = [0.01] * 200
    assert annualised_volatility(constante) == 0.0
    assert ewma_volatility(constante) == pytest.approx(0.01 * RACINE_252, rel=1e-6)


def test_ewma_reagit_plus_vite_qu_une_fenetre_fixe_apres_un_choc():
    calme = [0.001] * 250
    choc = calme + [0.08] * 5

    assert ewma_volatility(choc) > ewma_volatility(calme)
    assert ewma_volatility(choc) > annualised_volatility(choc), (
        "après un choc récent, la pondération exponentielle doit dominer "
        "l'écart-type qui dilue le choc sur toute la fenêtre"
    )


def test_lambda_hors_bornes_est_refuse():
    with pytest.raises(ValueError, match="λ"):
        ewma_volatility([0.01, 0.02], lam=1.0)


# --------------------------------------------------------------- Drawdown --


def test_une_serie_a_rendement_constant_positif_n_a_pas_de_drawdown():
    valeur = wealth_curve(serie([0.01] * 20))
    assert max_drawdown(valeur).value == pytest.approx(0.0)


def test_une_serie_strictement_decroissante_a_pour_drawdown_sa_baisse_totale():
    niveaux = serie([100.0, 90.0, 80.0, 70.0])
    resultat = max_drawdown(niveaux)

    assert resultat.value == pytest.approx(70.0 / 100.0 - 1.0)
    assert resultat.peak_date == niveaux.index[0]
    assert resultat.trough_date == niveaux.index[-1]


def test_le_pic_est_glissant_et_non_global():
    """Le point que le pic global ferait rater.

    [100, 90, 80, 200] : la perte réellement subie est −20 % (de 100 à 80). Un
    maximum global pris à 200 rendrait −60 %, une perte impossible puisqu'on ne
    peut pas décrocher d'un sommet atteint plus tard.
    """
    niveaux = serie([100.0, 90.0, 80.0, 200.0])
    resultat = max_drawdown(niveaux)

    assert resultat.value == pytest.approx(-0.20)
    assert resultat.peak_level == 100.0
    assert resultat.trough_level == 80.0
    assert resultat.trough_date == niveaux.index[2]


def test_la_courbe_de_valeur_part_de_un_a_la_date_fournie():
    depart = date(2026, 1, 1)
    courbe = wealth_curve(serie([-0.5], date(2026, 1, 2)), initial_date=depart)

    assert courbe.iloc[0] == 1.0
    assert courbe.index[0] == depart
    # Sans ce point de départ, le drawdown serait mesuré depuis 0,5 et vaudrait 0.
    assert max_drawdown(courbe).value == pytest.approx(-0.5)


# ----------------------------------------------------------------- Sharpe --


def test_le_sharpe_est_annualise_une_seule_fois():
    rendements = [0.02, 0.0, 0.02, 0.0]
    # moyenne 0,01 ; écart-type d'échantillon 0,0115470 ; ×√252
    assert sharpe_ratio(rendements) == pytest.approx(13.7477, rel=1e-4)


def test_le_taux_sans_risque_deplace_le_numerateur_sans_toucher_l_ecart_type():
    rendements = [0.02, 0.0, 0.02, 0.0]
    rf = 0.001

    ecart_type = float(np.std(np.array(rendements) - rf, ddof=1))
    attendu = RACINE_252 * (0.01 - rf) / ecart_type

    assert sharpe_ratio(rendements, risk_free_daily=rf) == pytest.approx(attendu)
    # Retrancher une constante ne change pas la dispersion.
    assert ecart_type == pytest.approx(float(np.std(rendements, ddof=1)))


def test_une_serie_constante_n_a_pas_de_sharpe_defini():
    with pytest.raises(ValueError, match="Sharpe"):
        sharpe_ratio([0.01] * 10)


# ---------------------------------------------------------------- Sortino --


def test_la_deviation_a_la_baisse_divise_par_le_nombre_total_de_periodes():
    """L'erreur classique, verrouillée.

    Une seule baisse de −10 % sur quatre séances. Diviser par N=4 donne 0,05 ;
    diviser par le seul compte des séances négatives (1) donnerait 0,10, soit un
    Sortino deux fois trop favorable.
    """
    rendements = [-0.10, 0.0, 0.0, 0.0]

    assert downside_deviation(rendements) == pytest.approx(0.05)
    assert downside_deviation(rendements) != pytest.approx(0.10)


def test_les_rendements_au_dessus_de_la_cible_ne_penalisent_pas():
    assert downside_deviation([0.10, 0.20, 0.30]) == 0.0
    assert downside_deviation([-0.10, 0.99]) == pytest.approx(
        downside_deviation([-0.10, 0.01])
    ), "seules les baisses comptent, quelle que soit l'ampleur des hausses"


def test_sortino_sans_rendement_negatif_rend_none_et_pas_nan():
    resultat = sortino_ratio([0.01, 0.02, 0.03])

    assert resultat is None, "indéfini, pas infini : aucune baisse observée"
    assert not isinstance(resultat, float), "ni inf ni NaN ne doivent circuler"


def test_sortino_utilise_la_cible_fournie():
    rendements = [0.01, 0.02, 0.03]
    # Avec une cible à 2 %, deux observations passent sous la cible.
    assert sortino_ratio(rendements, target_daily=0.02) is not None
    assert downside_deviation(rendements, target_daily=0.02) > 0.0


def test_sortino_est_annualise_comme_le_sharpe():
    rendements = [-0.10, 0.0, 0.0, 0.0]
    attendu = RACINE_252 * (float(np.mean(rendements)) - 0.0) / 0.05
    assert sortino_ratio(rendements) == pytest.approx(attendu)


# ----------------------------------------------------------- Concentration --


@pytest.mark.parametrize("n", [1, 2, 4, 10, 14])
def test_un_portefeuille_equipondere_a_un_hhi_de_un_sur_n(n):
    poids = {f"T{i}": 1.0 / n for i in range(n)}
    assert herfindahl_index(poids) == pytest.approx(1.0 / n)
    assert equal_weight_reference(n) == pytest.approx(1.0 / n)


def test_un_portefeuille_concentre_tend_vers_un():
    assert herfindahl_index({"A": 1.0}) == pytest.approx(1.0)
    assert herfindahl_index({"A": 0.9, "B": 0.1}) == pytest.approx(0.82)


def test_l_inverse_du_hhi_donne_le_nombre_de_positions_effectives():
    # Dix lignes dont une pèse 80 % : la diversification affichée est un leurre.
    poids = {"GROSSE": 0.8, **{f"T{i}": 0.2 / 9 for i in range(9)}}
    assert 1.0 / herfindahl_index(poids) == pytest.approx(1.55, abs=0.02)


def test_un_poids_negatif_est_refuse_plutot_que_calcule():
    with pytest.raises(ValueError, match="longues"):
        herfindahl_index({"A": 1.3, "B": -0.3})


def test_des_poids_qui_ne_somment_pas_a_un_sont_refuses():
    with pytest.raises(ValueError, match="sommer à 1"):
        herfindahl_index({"A": 0.5, "B": 0.2})
