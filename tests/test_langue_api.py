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

import re

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


# ═════════════════════════════════════════════════════ Les textes du moteur ══
#
# Lot 4 : méthodes, détails, réserves, refus, périodes, crises, régimes,
# indice de référence, erreurs du portefeuille. Les observations du moteur de
# règles suivent au lot 5 : elles sont lues ici à part.


CHAMPS_DE_PROSE = (
    "statement", "provenance", "rendered", "rule_label", "name", "rationale",
    "title", "body", "confirmation", "text", "summary", "description", "method",
    "detail", "caveat", "undefined_reason", "unavailable_reason",
    "student_unavailable_reason", "monte_carlo_unavailable_reason", "period_label",
    "estimation_period_label", "calm_period_label", "benchmark_label",
    "benchmark_description", "basis", "reason", "valuation_error",
    "correlation_undefined_reason", "problem",
)

# Des données, écrites comme on les a saisies ou reçues : le nom d'un
# portefeuille, celui d'un titre.
DONNEES = re.compile(r"\.portfolio\.|\.valuation\.|^\[\d+\]\.name$|^\.name$")

# La provenance d'une mesure, écrite en IBM Plex Sans : le grec y est admis.
PROVENANCE = re.compile(r"\.risk\..*\.(method|detail)$")


def prose_publiee(corps, sauf: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    return [
        (chemin, texte)
        for chemin, texte in toutes_les_chaines(corps)
        if chemin.endswith(tuple(f".{champ}" for champ in CHAMPS_DE_PROSE))
        and not DONNEES.search(chemin)
        and not any(chemin.startswith(prefixe) for prefixe in sauf)
    ]


def fautes_anglaises(corps, sauf: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    fautes = []
    for chemin, texte in prose_publiee(corps, sauf):
        fautes += [(chemin, f) for f in fautes_de_forme(texte, "en", grec_admis=bool(PROVENANCE.search(chemin)))]
        fautes += [(chemin, f) for f in fautes_de_francais(texte)]
    return fautes


@pytest.fixture
def analyser_en(base_historique_court, client_factory):
    """Analyse d'un portefeuille dont une ligne a `seances_courtes` cotations,
    dans la langue demandée."""

    bases: dict[int, tuple[object, int]] = {}

    def _analyser(seances_courtes: int, parametres: str = "") -> object:
        if seances_courtes not in bases:
            chemin = base_historique_court(seances_courtes)
            with client_factory(chemin) as client:
                identifiant = client.post("/api/portfolios", json={}).json()["id"]
                client.put(
                    f"/api/portfolios/{identifiant}/positions",
                    json={"positions": [{"ticker": "LONG", "quantity": 10}, {"ticker": "COURT", "quantity": 20}]},
                )
            bases[seances_courtes] = (chemin, identifiant)
        chemin, identifiant = bases[seances_courtes]
        with client_factory(chemin) as client:
            return client.get(f"/api/portfolios/{identifiant}/analysis?window=504{parametres}")

    return _analyser


@pytest.mark.parametrize("fenetre", [250, 60])
def test_l_analyse_anglaise_du_moteur_n_a_plus_de_francais(
    client_synthetique, portefeuille_synthetique, fenetre
):
    """Hors des observations (lot 5) : chaque texte rédigé par le moteur est
    en anglais et passe les gardes anglaises."""
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window={fenetre}&lang=en"
    ).json()
    assert prose_publiee(corps, sauf=(".observations",)), "rien à lire"
    assert fautes_anglaises(corps, sauf=(".observations",)) == []
    assert corps["estimation_period_label"].startswith("the past ")
    assert corps["parameters"]["benchmark_label"] == "the S&P 500"
    assert corps["scenarios"][0]["scenario"]["name"] == "2008 Financial Crisis"


@pytest.mark.parametrize("seances_courtes", [3, 8, 40])
def test_les_refus_et_les_reserves_du_moteur_en_anglais(analyser_en, seances_courtes):
    """Refus sous trois séances, réserves sous trente, refus de la Student :
    les phrases que la démonstration ne déclenche jamais."""
    francais = analyser_en(seances_courtes)
    assert analyser_en(seances_courtes, "&lang=fr").content == francais.content
    anglais = analyser_en(seances_courtes, "&lang=en")
    assert anglais.status_code == 200, anglais.text
    assert fautes_anglaises(anglais.json(), sauf=(".observations",)) == []
    risque = anglais.json()["risk"]
    if seances_courtes == 3:
        assert risque["matrices"]["correlation_undefined_reason"].startswith("Over 2")
        assert "is meaningless" in risque["beta"]["undefined_reason"]
    if seances_courtes == 8:
        assert risque["volatility"]["caveat"].startswith("Small-sample estimate:")
    raison_student = risque["tail_risk"]["student_unavailable_reason"]
    if seances_courtes < 30:
        assert raison_student.startswith("Not enough days to fit Student's t-distribution")
    else:
        # 39 séances : la Student s'ajuste, mais ne se distingue pas de la normale.
        assert raison_student.startswith("Over these 39")


def test_les_erreurs_du_portefeuille_en_anglais(client_synthetique):
    """Un portefeuille vide : la liste dit pourquoi il n'est pas valorisé, sa
    page et son analyse répondent 409, dans la langue demandée."""
    identifiant = client_synthetique.post("/api/portfolios", json={"name": "Vide"}).json()["id"]
    for chemin in (f"/api/portfolios/{identifiant}", f"/api/portfolios/{identifiant}/analysis"):
        francais = client_synthetique.get(chemin)
        assert francais.status_code == 409
        assert client_synthetique.get(_avec(chemin, "lang=fr")).content == francais.content
        anglais = client_synthetique.get(_avec(chemin, "lang=en"))
        assert anglais.status_code == 409
        assert anglais.json()["detail"] == f"Portfolio {identifiant} has no positions."
    liste = client_synthetique.get("/api/portfolios?lang=en").json()
    vide = next(p for p in liste if p["id"] == identifiant)
    assert vide["valuation_error"] == f"Portfolio {identifiant} has no positions."


def test_l_indice_absent_en_anglais(client_synthetique, portefeuille_synthetique):
    chemin = f"/api/portfolios/{portefeuille_synthetique}/analysis?benchmark=absent"
    anglais = client_synthetique.get(_avec(chemin, "lang=en"))
    assert anglais.status_code == 409
    assert anglais.json()["detail"].startswith("No price in the database for ['ABSENT']. Load it with")
    assert client_synthetique.get(_avec(chemin, "lang=fr")).content == client_synthetique.get(chemin).content
