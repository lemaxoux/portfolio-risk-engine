"""Les témoins des gardes de `gardes_texte.py` que leurs fichiers n'éprouvent
pas encore : toutes les gardes anglaises, la garde des nombres en lettres
dans les deux langues, et les deux assemblages par langue.

Une garde qu'on n'a jamais vue échouer ne prouve rien : chacune reçoit des
textes fautifs, qu'elle doit voir, et des textes légitimes, qu'elle doit
laisser passer. Les textes anglais suivent le glossaire et les règles de
`anglais-proposition.md` (§c), validés par Maxence le 2026-10-08.
"""

from __future__ import annotations

import pytest

from backend.typography import NARROW_NBSP, NBSP, WORD_JOINER

from .gardes_texte import (
    FRANCAIS,
    GARDES_PAR_LANGUE,
    LANGUES,
    LIEN_SECABLE_EN,
    NOMBRE_EN_LETTRES,
    NOMBRE_EN_LETTRES_EN,
    PONCTUATION_EN,
    PRESCRIPTIF_EN,
    SCORE_SUR_100_EN,
    VIRGULE_DECIMALE,
    ESPACE_AVANT_MOT_EN,
    ESPACE_AVANT_POURCENT_EN,
    fautes_de_forme,
    fautes_de_francais,
    fautes_de_registre,
)

TIRET_COURT = chr(0x2013)
MOINS = chr(0x2212)


def temoins(garde, fautifs, legitimes):
    """Les deux sens d'un témoin : chaque fautif est vu, aucun légitime ne l'est."""
    manques = [texte for texte in fautifs if not garde.search(texte)]
    fausses_alertes = [texte for texte in legitimes if garde.search(texte)]
    assert manques == [], f"non vus : {manques}"
    assert fausses_alertes == [], f"vus à tort : {fausses_alertes}"


# ═══════════════════════════════════════════════════ La forme, en anglais ══


def test_ponctuation_anglaise():
    temoins(
        PONCTUATION_EN,
        fautifs=(
            "Unknown ticker : XYZ.",
            f"Unknown ticker{NBSP}: XYZ.",
            "Start it :",
            "capital ; risk",
            f"capital{NBSP}; risk",
            "Delete this portfolio ?",
            "Watch out !",
            "the separator « ; »",
            "“ Demo”",
            "“Demo ”",
        ),
        legitimes=(
            "Unknown ticker: XYZ.",
            "capital; risk",
            "Delete this portfolio?",
            "at 10:30",
            "http://127.0.0.1:8001",
            "“Demo”",
            "(see “The worst days”).",
            "scale S = Σ·(ν−2)/ν",
            "if x != y",
        ),
    )


def test_une_duree_ou_une_date_anglaise_ne_se_coupe_pas():
    temoins(
        LIEN_SECABLE_EN,
        fautifs=(
            "about 2 years.",
            "over 6 months",
            "over 7 trading days",
            "on April 4, 2025",
            f"on April{NBSP}4, 2025",
            f"on April 4,{NBSP}2025",
        ),
        legitimes=(
            f"about 2{NBSP}years.",
            f"over 7{NBSP}trading days",
            f"on April{NBSP}4,{NBSP}2025",
            "this calculation needs at least 20",
            "during the 2008 Financial Crisis and the COVID Crash",
            f"2024-{WORD_JOINER}09-{WORD_JOINER}05 → 2026-{WORD_JOINER}09-{WORD_JOINER}09",
            "it may fall",
        ),
    )


def test_rien_avant_un_pourcent_anglais():
    temoins(
        ESPACE_AVANT_POURCENT_EN,
        fautifs=("1.06 %", f"1.06{NARROW_NBSP}%", f"1.06{NBSP}%"),
        legitimes=("1.06%", f"{MOINS}44.0%", "100% of the value"),
    )


def test_un_nombre_anglais_reste_lie_au_mot_qu_il_compte():
    temoins(
        ESPACE_AVANT_MOT_EN,
        fautifs=("504 sessions", "9.8 points", "6 holdings", "+9.8 pts", "1 session"),
        legitimes=(f"504{NBSP}sessions", f"9.8{NBSP}points", f"6{NBSP}holdings", "Line 4: XYZ"),
    )


def test_une_virgule_decimale_dans_un_texte_anglais():
    temoins(
        VIRGULE_DECIMALE,
        fautifs=("1,06%", "ν = 4,07", "0,5 points", "1,0000", "lost 44,0%"),
        legitimes=(
            "1,420 USD",
            "100,000 draws",
            "84,076.05 USD",
            "1.06%",
            "2024-09-05",
            "BRK.B",
            f"{MOINS}3",
            "AAPL, MSFT and KO",
        ),
    )


# ═══════════════════════════════════════════════════ Le registre, en anglais ══


def test_rien_de_prescriptif_en_anglais():
    temoins(
        PRESCRIPTIF_EN,
        fautifs=(
            "You should trim JPM.",
            "Consider selling XOM.",
            "We recommend rebalancing.",
            "Diversify your holdings.",
            "Together, they diversify less than their number implies.",
            "You need to reduce risk.",
            "Avoid energy stocks.",
            "Buy more KO.",
            "You have to act.",
        ),
        legitimes=(
            "JPM accounts for 25.6% of the portfolio's value and 35.4% of its fluctuations, 9.8 points more.",
            "Together, they provide less diversification than their number implies.",
            "This calculation needs at least 20.",
            "The more a holding weighs in the fluctuations, the more it weighs on the result.",
            "Diversification works on them alone.",
            "In the replayed crises, JPM cost the portfolio every time.",
        ),
    )


def test_aucune_note_globale_en_anglais():
    temoins(
        SCORE_SUR_100_EN,
        fautifs=("Risk: 72/100", "7.5 / 100"),
        legitimes=("100,000 draws", "1 / (1 − α)", "1.06%"),
    )
    assert fautes_de_registre("Overall risk score: high", "en")
    assert fautes_de_registre("Why there is no overall rating", "en") == []


def test_aucune_generalite_en_anglais():
    for fautif in (
        "the excluded part is younger and more speculative",
        "the loss is probably underestimated",
        "a recently listed security is riskier on average",
    ):
        assert fautes_de_registre(fautif, "en"), fautif
    assert fautes_de_registre("the loss of the whole may have been different", "en") == []


# ═══════════════════════════════════════════ Les nombres en lettres, deux langues ══


def test_nombres_en_lettres_en_francais():
    temoins(
        NOMBRE_EN_LETTRES,
        fautifs=(
            "environ trois ans",
            "sur sept jours",
            f"ces deux{NBSP}dernières années",
            "Deux mois plus tard",
            "dix séances",
        ),
        legitimes=(
            "un jour de bourse sur vingt",
            "Le rendement d'un jour",
            "une seule séance",
            "deux lignes de même poids",
            "les trois crises que l'outil rejoue",
            "504 jours de bourse",
        ),
    )


def test_nombres_en_lettres_en_anglais():
    temoins(
        NOMBRE_EN_LETTRES_EN,
        fautifs=(
            "about three years",
            "over seven days",
            "the past two years",
            "two trading days",
            "Ten sessions",
        ),
        legitimes=(
            "one trading day in twenty",
            "one day",
            "two holdings of equal weight",
            "the three crises the tool replays",
            "504 trading days",
        ),
    )


def test_le_nombre_est_le_premier_groupe():
    """Ce qui se vérifie est le nombre lui-même : c'est lui qu'une citation
    ou un fragment déclaré doit couvrir."""
    assert NOMBRE_EN_LETTRES.search("environ trois ans").group(1) == "trois"
    assert NOMBRE_EN_LETTRES_EN.search("the past two years").group(1) == "two"


# ═══════════════════════════════════════════ Du français dans de l'anglais ══


def test_du_francais_dans_un_texte_anglais():
    temoins(
        FRANCAIS,
        fautifs=(
            "Sur 7 jours de bourse",
            "the S&P 500, le S&P 500",
            "Crise financière 2008",
            "« Démo »",
            "504 séances",
            "votre portefeuille",
        ),
        legitimes=(
            "Over 7 trading days",
            "the S&P 500",
            "2008 Financial Crisis",
            "“Demo”",
            "504 sessions",
            "your portfolio",
            "Student's t-distribution",
            "a regime, not the future",
        ),
    )
    assert fautes_de_francais("Over 7 trading days") == []


# ═════════════════════════════════════════════════ Les assemblages par langue ══


def test_les_deux_langues_ont_les_memes_gardes():
    """Une garde doublée pour l'anglais l'est pour de bon : chaque table a ses
    deux langues."""
    assert LANGUES == ("fr", "en")
    for nom, table in GARDES_PAR_LANGUE.items():
        assert set(table) == set(LANGUES), nom


@pytest.mark.parametrize(
    "langue, fautif, attendue",
    [
        ("fr", "Ticker inconnu : XYZ.", "ponctuation"),
        ("fr", "le 4 avril 2025", "lien sécable"),
        ("fr", "ν = 4.07", "nombre mal écrit"),
        ("fr", f"JNJ{TIRET_COURT}KO", "paire sécable"),
        ("fr", "504 séances", "espace avant le mot compté"),
        ("fr", "1,06 %", "espace avant %"),
        ("en", "Unknown ticker : XYZ.", "ponctuation"),
        ("en", "on April 4, 2025", "lien sécable"),
        ("en", "ν = 4,07", "nombre mal écrit"),
        ("en", f"JNJ{TIRET_COURT}KO", "paire sécable"),
        ("en", "504 sessions", "espace avant le mot compté"),
        ("en", f"1.06{NARROW_NBSP}%", "espace avant %"),
        ("en", "a gap of -7 pts", "trait d'union"),
        ("en", "the estimate " + chr(0x2014) + " thin", "tiret cadratin"),
    ],
)
def test_les_gardes_de_forme_mordent_dans_chaque_langue(langue, fautif, attendue):
    assert any(attendue in faute for faute in fautes_de_forme(fautif, langue)), fautif


@pytest.mark.parametrize(
    "langue, legitime",
    [
        ("fr", f"Ticker inconnu{NBSP}: XYZ."),
        ("fr", f"le 4{NBSP}avril{NBSP}2025, il aurait perdu 5,87{NARROW_NBSP}%."),
        ("fr", f"JNJ{TIRET_COURT}{WORD_JOINER}KO, à 0,42"),
        ("en", "Unknown ticker: XYZ."),
        ("en", f"on April{NBSP}4,{NBSP}2025, it would have lost 5.87%."),
        ("en", f"JNJ{TIRET_COURT}{WORD_JOINER}KO, at 0.42"),
        ("en", f"Over 7{NBSP}trading days, none falls among the worst 5%: this calculation needs at least 20."),
    ],
)
def test_les_gardes_de_forme_laissent_passer_le_texte_juste(langue, legitime):
    assert fautes_de_forme(legitime, langue) == [], legitime


def test_les_gardes_de_registre_mordent_dans_chaque_langue():
    assert fautes_de_registre("Vous devriez alléger JPM.", "fr")
    assert fautes_de_registre("Score de risque : 72/100", "fr")
    assert fautes_de_registre("You should trim JPM.", "en")
    assert fautes_de_registre("Risk: 72/100", "en")
    assert fautes_de_registre("Dans les crises rejouées, JPM a coûté au portefeuille.", "fr") == []
    assert fautes_de_registre("In the replayed crises, JPM cost the portfolio.", "en") == []
