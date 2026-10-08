"""L'écriture anglaise des nombres et des dates, côté serveur (chantier 7D).

`test_typographie_partagee.py` compare les deux moitiés du produit sur une
table commune. Ceux-ci couvrent ce que le client n'a pas : les nombres en
lettres, l'écriture exacte d'un nombre saisi, la constante citée, l'accord
d'un nombre affiché autrement que par sa valeur. Et ils vérifient qu'un appel
sans langue écrit toujours le français.
"""

from __future__ import annotations

from datetime import date

import pytest

from backend import typography
from backend.typography import MINUS, NARROW_NBSP, NBSP


def test_sans_langue_l_ecriture_reste_francaise():
    assert typography.number(1234.5, 1) == f"1{NARROW_NBSP}234,5"
    assert typography.percent(0.0138, 2) == f"1,38{NARROW_NBSP}%"
    assert typography.long_date(date(2025, 4, 4)) == f"4{NBSP}avril{NBSP}2025"
    assert typography.cardinal(2) == "deux"
    assert typography.sessions(1) == f"1{NBSP}séance"


def test_le_premier_du_mois_s_ecrit_1er_en_francais_seulement():
    assert typography.long_date(date(2005, 1, 1)) == f"1er{NBSP}janvier{NBSP}2005"
    assert typography.long_date(date(2005, 1, 1), langue="en") == f"January{NBSP}1,{NBSP}2005"
    # Le 11 et le 21 ne sont pas des premiers du mois.
    assert typography.long_date(date(2005, 1, 11)) == f"11{NBSP}janvier{NBSP}2005"
    assert typography.long_date(date(2005, 1, 21)) == f"21{NBSP}janvier{NBSP}2005"


def test_une_date_anglaise_est_liee_apres_le_mois_et_apres_la_virgule():
    assert typography.long_date(date(2025, 4, 4), langue="en") == f"April{NBSP}4,{NBSP}2025"
    assert " " not in typography.long_date(date(2009, 3, 9), langue="en")


@pytest.mark.parametrize(
    "nombre, attendu",
    [(0, "zero"), (1, "one"), (2, "two"), (7, "seven"), (10, "ten"), (14, "14"), (1000, "1,000")],
)
def test_les_nombres_en_lettres_jusqu_a_dix(nombre, attendu):
    assert typography.cardinal(nombre, langue="en") == attendu


def test_le_groupement_anglais():
    assert typography.thousands(504, langue="en") == "504"
    assert typography.thousands(100000, langue="en") == "100,000"
    assert typography.grouped(100000, "draw", langue="en") == f"100,000{NBSP}draws"
    assert typography.number(-83185.85, 2, langue="en") == f"{MINUS}83,185.85"


def test_le_pourcentage_anglais_n_a_aucune_espace():
    assert typography.percent(0.8, 1, trim=True, langue="en") == "80%"
    assert typography.percent(0.256, 1, trim=True, langue="en") == "25.6%"
    assert typography.percent(-0.088, 1, signed=True, langue="en") == f"{MINUS}8.8%"
    assert typography.percent(0.088, 1, signed=True, langue="en") == "+8.8%"


def test_un_nombre_saisi_et_une_constante_citee_en_anglais():
    assert typography.exact(-3.0, langue="en") == f"{MINUS}3"
    assert typography.exact(2.5, langue="en") == "2.5"
    assert typography.exact(123456.789, langue="en") == "123,456.789"
    assert typography.compact(0.94, langue="en") == "0.94"
    assert typography.compact(60.0, langue="en") == "60"
    assert typography.compact(-0.5, langue="en") == f"{MINUS}0.5"


def test_l_accord_anglais_suit_l_ecriture():
    """Le singulier est réservé à ce qui s'écrit exactement « 1 », signe à
    part : « 1.0 holdings », « 1.9 points », mais « 1 holding »."""
    assert typography.counted(1, "holding", langue="en") == f"1{NBSP}holding"
    assert typography.counted(0, "holding", langue="en") == f"0{NBSP}holdings"
    assert typography.counted(1.0, "holding", affiche="1.0", langue="en") == f"1.0{NBSP}holdings"
    assert typography.counted(1.9, "point", affiche="1.9", langue="en") == f"1.9{NBSP}points"
    assert typography.counted(3, "day", "days", langue="en") == f"3{NBSP}days"
    assert typography.lines(1, langue="en") == f"1{NBSP}holding"


def test_un_nombre_non_fini_n_est_ecrit_dans_aucune_langue():
    for langue in ("fr", "en"):
        with pytest.raises(ValueError):
            typography.number(float("nan"), 2, langue=langue)
        with pytest.raises(ValueError):
            typography.compact(float("inf"), langue=langue)
