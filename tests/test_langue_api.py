"""La langue des réponses : `?lang=fr` ou `?lang=en`, le français par défaut.

L'INVARIANT DU CHANTIER 7D. Sans langue demandée, chaque réponse de l'API est
celle d'avant le chantier, octet pour octet ; avec `lang=fr`, aussi. Ces tests
le vérifient route par route, sur une base synthétique et sur des fenêtres
courtes qui déclenchent les refus et les réserves. La réponse de référence de
la démonstration (copie figée, 504 et 60 séances) est comparée hors de la
suite, à chaque lot, à sa capture du commit de départ.

L'anglais s'ajoute à côté : chaque domaine traduit le vérifie ici, aux gardes
anglaises de `gardes_texte.py`.
"""

from __future__ import annotations

import pytest

from backend.risk_engine.config import DEFAULT_WINDOW
from backend.rules.disclaimer import acceptance_text
from backend.typography import NBSP, prose

from .gardes_texte import fautes_de_forme, fautes_de_francais, fautes_de_registre, toutes_les_chaines


def _avec(chemin: str, parametre: str) -> str:
    return f"{chemin}{'&' if '?' in chemin else '?'}{parametre}"


def _routes(identifiant: int) -> list[str]:
    return [
        "/api/disclaimer",
        "/api/meta",
        "/api/securities",
        "/api/csv-format",
        "/api/portfolios",
        f"/api/portfolios/{identifiant}",
        f"/api/portfolios/{identifiant}/analysis",
        f"/api/portfolios/{identifiant}/analysis?window=250",
        f"/api/portfolios/{identifiant}/analysis?window=60",
    ]


def test_sans_langue_et_en_francais_chaque_reponse_est_la_meme(
    client_synthetique, portefeuille_synthetique
):
    """Octet pour octet : sans `lang`, avec `lang=fr`. Le français est le
    défaut, et le demander ne change rien."""
    for chemin in _routes(portefeuille_synthetique):
        sans = client_synthetique.get(chemin)
        francais = client_synthetique.get(_avec(chemin, "lang=fr"))
        assert sans.status_code == 200, (chemin, sans.text)
        assert francais.content == sans.content, chemin


def test_une_langue_inconnue_est_refusee(client_synthetique, portefeuille_synthetique):
    for chemin in ("/api/disclaimer", f"/api/portfolios/{portefeuille_synthetique}/analysis"):
        reponse = client_synthetique.get(_avec(chemin, "lang=de"))
        assert reponse.status_code == 422, (chemin, reponse.text)
        assert reponse.json()["problems"][0]["field"] == "lang"


# ═══════════════════════════════════════════════ L'écran d'acceptation ══


def test_l_ecran_d_acceptation_anglais(client_synthetique):
    corps = client_synthetique.get("/api/disclaimer?lang=en").json()
    assert corps["title"] == "Before using Mx Risk MGT"
    assert len(corps["sections"]) == 5
    assert corps["confirmation"].startswith("I have read these limitations")
    # La fenêtre de la configuration, groupée et liée à son unité, et sa durée.
    assert f"{DEFAULT_WINDOW}{NBSP}trading sessions, about 2{NBSP}years." in corps["text"]
    for section in corps["sections"]:
        assert section["title"] in corps["text"]
        assert section["body"] in corps["text"]


def test_l_anglais_a_sa_propre_empreinte_et_le_francais_garde_la_sienne(client_synthetique):
    """Le texte français n'a pas bougé : l'empreinte que garde le client ne
    change pas, personne n'a à réaccepter. L'anglais est un autre texte."""
    francais = client_synthetique.get("/api/disclaimer").json()["text"]
    anglais = client_synthetique.get("/api/disclaimer?lang=en").json()["text"]
    # Publiés tels que l'API les publie : `prose` sur chaque texte rédigé.
    assert francais == prose(acceptance_text(DEFAULT_WINDOW))
    assert anglais == prose(acceptance_text(DEFAULT_WINDOW, langue="en"))
    assert anglais != francais


def test_l_analyse_anglaise_sert_le_meme_ecran_que_la_route_seule(
    client_synthetique, portefeuille_synthetique
):
    analyse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window={DEFAULT_WINDOW}&lang=en"
    )
    assert analyse.status_code == 200, analyse.text
    assert analyse.json()["disclaimer"] == client_synthetique.get("/api/disclaimer?lang=en").json()


@pytest.mark.parametrize(
    "fenetre, duree",
    [(252, f"about 1{NBSP}year"), (504, f"about 2{NBSP}years"), (126, f"about 6{NBSP}months")],
)
def test_la_duree_de_la_fenetre_en_anglais(fenetre, duree):
    """La décision — années ou mois — est celle du français ; l'accord est
    anglais : « 1 year », « 2 years »."""
    assert f", {duree}." in acceptance_text(fenetre, langue="en")


def test_l_ecran_anglais_passe_les_gardes_anglaises(client_synthetique):
    """Forme, français oublié, note globale et généralités. La garde
    prescriptive ne le lit pas : il dit à bon droit « not advice » et « buy,
    sell, or hold »."""
    corps = client_synthetique.get("/api/disclaimer?lang=en").json()
    fautes = []
    for chemin, texte in toutes_les_chaines(corps):
        fautes += [(chemin, f) for f in fautes_de_forme(texte, "en")]
        fautes += [(chemin, f) for f in fautes_de_francais(texte)]
        fautes += [
            (chemin, f) for f in fautes_de_registre(texte, "en") if not f.startswith("prescriptif")
        ]
    assert fautes == []
