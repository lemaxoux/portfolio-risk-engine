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

from backend.api.csv_import import read as lire_csv
from backend.api.static import VARIABLE as DOSSIER_DU_BUNDLE
from backend.risk_engine.config import DEFAULT_WINDOW
from backend.rules.disclaimer import acceptance_text
from backend.typography import NBSP, prose

from .gardes_texte import (
    fautes_de_forme,
    fautes_de_francais,
    fautes_de_registre,
    nombres,
    toutes_les_chaines,
)


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


# ═════════════════════════════════════════ Les textes du moteur et des règles ══
#
# Lot 4 : méthodes, détails, réserves, refus, périodes, crises, régimes,
# indice de référence, erreurs du portefeuille. Lot 5 : les observations du
# moteur de règles et leurs seuils. Toute la réponse d'analyse est lue.


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


def prose_publiee(corps) -> list[tuple[str, str]]:
    return [
        (chemin, texte)
        for chemin, texte in toutes_les_chaines(corps)
        if chemin.endswith(tuple(f".{champ}" for champ in CHAMPS_DE_PROSE))
        and not DONNEES.search(chemin)
    ]


# L'écran d'acceptation dit à bon droit ce que l'outil n'est pas (« not
# advice », « buy, sell, or hold ») : la garde prescriptive ne le lit pas.
ECRAN_D_ACCEPTATION = re.compile(r"^\.disclaimer\.")


def fautes_anglaises(corps) -> list[tuple[str, str]]:
    """Forme, français oublié et registre : rien de prescriptif, aucune note
    globale, aucune généralité que le moteur ne mesure pas."""
    fautes = []
    for chemin, texte in prose_publiee(corps):
        fautes += [(chemin, f) for f in fautes_de_forme(texte, "en", grec_admis=bool(PROVENANCE.search(chemin)))]
        fautes += [(chemin, f) for f in fautes_de_francais(texte)]
        fautes += [
            (chemin, f)
            for f in fautes_de_registre(texte, "en")
            if not (ECRAN_D_ACCEPTATION.search(chemin) and f.startswith("prescriptif"))
        ]
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
def test_l_analyse_anglaise_n_a_plus_de_francais(
    client_synthetique, portefeuille_synthetique, fenetre
):
    """Chaque texte rédigé par le moteur et par les règles est en anglais et
    passe les gardes anglaises, observations comprises."""
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window={fenetre}&lang=en"
    ).json()
    assert prose_publiee(corps), "rien à lire"
    assert any(chemin.startswith(".observations") for chemin, _ in prose_publiee(corps))
    assert fautes_anglaises(corps) == []
    assert corps["estimation_period_label"].startswith("the past ")
    assert corps["parameters"]["benchmark_label"] == "the S&P 500"
    assert corps["scenarios"][0]["scenario"]["name"] == "2008 Financial Crisis"


@pytest.mark.parametrize("seances_courtes", [3, 8, 40])
def test_les_refus_et_les_reserves_du_moteur_en_anglais(analyser_en, seances_courtes):
    """Refus sous trois séances, réserves sous trente, refus de la Student,
    observations refusées ou minces : les phrases que la démonstration ne
    déclenche jamais."""
    francais = analyser_en(seances_courtes)
    assert analyser_en(seances_courtes, "&lang=fr").content == francais.content
    anglais = analyser_en(seances_courtes, "&lang=en")
    assert anglais.status_code == 200, anglais.text
    assert fautes_anglaises(anglais.json()) == []
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
    enonces = " ".join(o["statement"] for o in anglais.json()["observations"])
    if seances_courtes == 3:
        # Deux séances communes : les règles refusent de chiffrer.
        assert "is meaningless: it takes at least 3." in enonces
    else:
        assert "Small-sample estimate: over " in enonces


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


# ═════════════════════════════════════════ Les observations, langue à langue ══

LIBELLES_ANGLAIS = {
    "effective_concentration": "How many holdings, really",
    "variance_contribution": "Weight in the fluctuations",
    "apparent_diversification": "Holdings that move together",
    "systematic_share": "Share that follows the market",
    "crisis_degradation": "The portfolio in a crisis",
    "scenario_coverage": "Crisis partly replayed",
}


def periodes(corps: dict) -> list[str]:
    """Les périodes que dit une réponse (« ces 11 derniers mois », « the past
    two years »), aussi en tête de phrase, les plus longues d'abord."""
    dites = {texte for chemin, texte in toutes_les_chaines(corps) if chemin.endswith("period_label")}
    return sorted(dites | {d[:1].upper() + d[1:] for d in dites}, key=len, reverse=True)


def nombres_hors_periodes(texte: str, langue: str, retirees: list[str]) -> list[str]:
    for periode in retirees:
        texte = texte.replace(periode, "")
    return nombres(texte, langue)


def comparer_les_observations(francais: dict, anglais: dict) -> None:
    """Une observation anglaise est la française, traduite : la même règle,
    les mêmes faits (des identifiants et des nombres, les mêmes dans les deux
    langues), les mêmes seuils, et les mêmes nombres dans chaque phrase.

    L'anglais nomme la période de la fenêtre là où le français ne la dit pas
    (question 9 : une phrase au présent ou au prétérit porte son cadre de
    rejeu). Les périodes sont donc retirées des deux textes avant d'en
    compter les nombres : « the past 11 months » ajouterait un 11.
    """
    retirees = {"fr": periodes(francais), "en": periodes(anglais)}
    assert retirees["fr"] and retirees["en"], "aucune période : le retrait ne vérifierait rien"
    assert len(anglais["observations"]) == len(francais["observations"])
    for fr, en in zip(francais["observations"], anglais["observations"]):
        assert en["rule"] == fr["rule"]
        assert en["rule_label"] == LIBELLES_ANGLAIS[en["rule"]]
        assert en["facts"] == fr["facts"]
        assert en["uses_chosen_threshold"] == fr["uses_chosen_threshold"]
        if fr["subject"] == "portefeuille":
            assert en["subject"] == "portfolio"
        for champ in ("statement", "provenance"):
            assert nombres_hors_periodes(en[champ], "en", retirees["en"]) == nombres_hors_periodes(
                fr[champ], "fr", retirees["fr"]
            ), (fr[champ], en[champ])
        assert len(en["thresholds"]) == len(fr["thresholds"])
        for seuil_fr, seuil_en in zip(fr["thresholds"], en["thresholds"]):
            for champ in ("kind", "role", "value", "percent", "chosen"):
                assert seuil_en[champ] == seuil_fr[champ], champ
            assert nombres(seuil_en["rendered"], "en") == nombres(seuil_fr["rendered"], "fr")


@pytest.mark.parametrize("fenetre", [250, 60])
def test_chaque_observation_anglaise_traduit_la_francaise(
    client_synthetique, portefeuille_synthetique, fenetre
):
    chemin = f"/api/portfolios/{portefeuille_synthetique}/analysis?window={fenetre}"
    francais = client_synthetique.get(chemin).json()
    anglais = client_synthetique.get(_avec(chemin, "lang=en")).json()
    assert anglais["observations"], "aucune observation à comparer"
    comparer_les_observations(francais, anglais)


@pytest.mark.parametrize("seances_courtes", [3, 8, 40])
def test_chaque_observation_anglaise_traduit_la_francaise_sur_une_fenetre_courte(
    analyser_en, seances_courtes
):
    comparer_les_observations(
        analyser_en(seances_courtes).json(), analyser_en(seances_courtes, "&lang=en").json()
    )


# ═════════════════════════════════════ Saisie, fichier et erreurs (lot 6) ══
#
# Les refus d'une saisie, d'un fichier, les 404 et le chemin d'API inconnu.
# Aucune de ces requêtes n'écrit : un refus est vérifié avant la première
# écriture, et l'invariant se lit donc sur la même base, requête après requête.


def deposer(client, identifiant: int, contenu: bytes, parametres: str = ""):
    return client.post(
        f"/api/portfolios/{identifiant}/positions/csv{parametres}",
        files={"file": ("positions.csv", contenu, "text/csv")},
    )


def refus(identifiant: int) -> list[tuple[str, str, dict]]:
    """Méthode, chemin et arguments de chaque refus. Les valeurs refusées
    citées sont des mots : un nombre saisi est une donnée, qui ne se lit pas
    pareil dans les deux langues."""
    positions = f"/api/portfolios/{identifiant}/positions"
    fichier = f"/api/portfolios/{identifiant}/positions/csv"

    def csv(contenu: bytes) -> dict:
        return {"files": {"file": ("positions.csv", contenu, "text/csv")}}

    return [
        ("get", "/api/portfolios/999", {}),
        ("get", "/api/portfolios/999/analysis", {}),
        ("delete", "/api/portfolios/999", {}),
        ("put", "/api/portfolios/999/positions", {"json": {"positions": [{"ticker": "ALFA", "quantity": 1}]}}),
        ("put", positions, {"json": {"positions": []}}),
        (
            "put",
            positions,
            {
                "json": {
                    "positions": [
                        {"ticker": "XYZ", "quantity": 5, "line": 2},
                        {"ticker": "ALFA", "quantity": 1, "line": 3},
                        {"ticker": "ALFA", "quantity": 2, "line": 4},
                        {"ticker": " ", "quantity": 1, "line": 5},
                        {"ticker": "MIKE", "quantity": -3, "line": 6},
                        {"ticker": "ZULU", "quantity": 1, "cost_basis": -2, "line": 7},
                    ]
                }
            },
        ),
        ("put", positions, {"json": {"positions": [{"ticker": "MIKE", "quantity": 0}]}}),
        ("post", fichier, csv(b"ticker;quantity\nALFA;1" + bytes([0x81]) + b"\n")),
        ("post", fichier, csv(b"symbol;count\nALFA;1\n")),
        ("post", fichier, csv(b"ticker quantity\nALFA 1\n")),
        ("post", fichier, csv(b"   \n")),
        ("post", fichier, csv(b"ticker,quantity,cost_basis\nALFA\nMIKE,dix\nALFA,10,cher\nMIKE,1,5,7,9\n")),
    ]


def test_un_refus_en_francais_est_celui_d_avant_le_chantier(client_synthetique, portefeuille_synthetique):
    """Sans `lang` et avec `lang=fr`, chaque refus est le même, octet pour
    octet."""
    for methode, chemin, arguments in refus(portefeuille_synthetique):
        sans = getattr(client_synthetique, methode)(chemin, **arguments)
        francais = getattr(client_synthetique, methode)(_avec(chemin, "lang=fr"), **arguments)
        assert sans.status_code in (404, 422), (chemin, sans.status_code)
        assert francais.content == sans.content, (methode, chemin)


def test_chaque_refus_anglais_traduit_le_francais(client_synthetique, portefeuille_synthetique):
    """Le même code, les mêmes champs, les mêmes lignes et les mêmes valeurs
    refusées ; le détail et chaque problème en anglais, aux gardes anglaises,
    avec les nombres du français."""
    for methode, chemin, arguments in refus(portefeuille_synthetique):
        francais = getattr(client_synthetique, methode)(chemin, **arguments)
        anglais = getattr(client_synthetique, methode)(_avec(chemin, "lang=en"), **arguments)
        assert anglais.status_code == francais.status_code, (methode, chemin)
        fr, en = francais.json(), anglais.json()
        assert len(en["problems"]) == len(fr["problems"])
        for p_fr, p_en in zip(fr["problems"], en["problems"]):
            assert {k: p_en[k] for k in ("line", "field", "value")} == {
                k: p_fr[k] for k in ("line", "field", "value")
            }
        textes = [(fr["detail"], en["detail"])] + [
            (p_fr["problem"], p_en["problem"]) for p_fr, p_en in zip(fr["problems"], en["problems"])
        ]
        for texte_fr, texte_en in textes:
            assert texte_en != texte_fr, texte_en
            assert fautes_de_forme(texte_en, "en") == [], texte_en
            assert fautes_de_francais(texte_en) == [], texte_en
            assert fautes_de_registre(texte_en, "en") == [], texte_en
            assert nombres(texte_en, "en") == nombres(texte_fr, "fr"), (texte_fr, texte_en)


def test_les_refus_anglais_disent_ce_que_le_glossaire_fixe(client_synthetique, portefeuille_synthetique):
    absent = client_synthetique.get("/api/portfolios/999?lang=en").json()
    assert absent["detail"] == "Portfolio 999 not found."
    saisie = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions?lang=en",
        json={"positions": [{"ticker": "XYZ", "quantity": 5}]},
    ).json()
    assert saisie["detail"].startswith("XYZ is not a known security. Available securities: ")
    fichier = deposer(
        client_synthetique,
        portefeuille_synthetique,
        b"ticker;quantity\nALFA;dix\nMIKE;onze\n",
        "?lang=en",
    ).json()
    assert fichier["detail"] == "2\u00a0lines rejected: no position was written."
    assert fichier["problems"][0]["problem"] == (
        "\u201cdix\u201d is not a readable quantity. Accepted decimal separator: `,`."
    )


def test_un_refus_de_validation_de_fastapi_ne_change_pas_de_langue(
    client_synthetique, portefeuille_synthetique
):
    """Le message de pydantic est publié tel quel, en anglais, dans les deux
    langues (question 14) : `lang` ne le touche pas."""
    chemin = f"/api/portfolios/{portefeuille_synthetique}/analysis?window=10"
    francais = client_synthetique.get(chemin)
    anglais = client_synthetique.get(_avec(chemin, "lang=en"))
    assert francais.status_code == anglais.status_code == 422
    assert anglais.content == francais.content


@pytest.fixture
def client_avec_bundle(tmp_path, base_synthetique, client_factory, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Mx Risk MGT</title>", encoding="utf-8")
    monkeypatch.setenv(DOSSIER_DU_BUNDLE, str(dist))
    with client_factory(base_synthetique) as client:
        yield client


def test_le_chemin_d_api_inconnu_dans_la_langue_de_l_adresse(client_avec_bundle):
    """Aucune route ne déclare `lang` ici : la langue se lit dans l'adresse,
    et une langue inconnue n'y est pas refusée, la réponse refuse déjà autre
    chose."""
    francais = client_avec_bundle.get("/api/nexiste-pas")
    assert francais.json()["detail"].startswith("Aucune route d'API à ce chemin")
    assert client_avec_bundle.get("/api/nexiste-pas?lang=fr").content == francais.content
    assert client_avec_bundle.get("/api/nexiste-pas?lang=de").content == francais.content
    anglais = client_avec_bundle.get("/api/nexiste-pas?lang=en")
    assert anglais.status_code == 404
    assert anglais.json() == {"detail": "No API route at this path: /api/nexiste-pas", "problems": []}
    # Une route du client reste une page, quelle que soit la langue demandée.
    assert client_avec_bundle.get("/methodologie?lang=de").status_code == 200


def test_l_exemple_csv_anglais_est_celui_d_un_excel_anglais(client_synthetique):
    """Seul l'exemple change : le format lu est le même. L'exemple anglais est
    lu par le vrai lecteur, comme le français : virgule, point décimal, prix
    de revient laissé vide."""
    francais = client_synthetique.get("/api/csv-format").json()
    anglais = client_synthetique.get("/api/csv-format?lang=en").json()
    assert {k: v for k, v in anglais.items() if k != "example"} == {
        k: v for k, v in francais.items() if k != "example"
    }
    assert anglais["example"] != francais["example"]
    lecture = lire_csv(anglais["example"].encode("utf-8"))
    assert lecture.problems == ()
    assert [(p.ticker, p.quantity, p.cost_basis) for p in lecture.positions] == [
        ("AAPL", 40.0, 185.2),
        ("MSFT", 25.0, None),
    ]
    assert lecture.source.delimiter == ","
    assert lecture.source.decimal_separator == "."


def test_l_exemple_csv_anglais_s_importe_sur_la_copie_figee(base_figee, client_factory):
    with client_factory(base_figee) as client:
        identifiant = client.post("/api/portfolios", json={"name": "Example"}).json()["id"]
        exemple = client.get("/api/csv-format?lang=en").json()["example"]
        reponse = deposer(client, identifiant, exemple.encode("utf-8"), "?lang=en")
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["positions_count"] == 2
