"""Aucune phrase française dans une réponse anglaise (chantier 7D).

Chaque route, sur chaque jeu qu'on lit en français : la démonstration (copie
figée) à 504 et 60 séances, le portefeuille synthétique à trois fenêtres et
sans indice, les fenêtres de 2, 3, 8 et 40 cotations, un portefeuille vide,
les corps d'erreur (404, 409, 422 de saisie, de fichier, d'encodage, de
validation), le chemin d'API inconnu, l'écran d'acceptation, la liste des
portefeuilles, le format CSV, une saisie et un import réussis.

TOUTE CHAÎNE EST LUE, pas seulement les champs de prose : un mot français
glissé dans un champ inattendu serait vu. Trois exceptions, déclarées :

- les DONNÉES, écrites comme on les a saisies ou reçues : le nom d'un
  portefeuille, d'un titre, d'un fichier, la valeur refusée d'une saisie ;
- les IDENTIFIANTS, les mêmes dans les deux langues (question 15) : les
  valeurs de `decimal_separator` (« mixte », « aucune ») ;
- les garde-fous internes du moteur et du lecteur CSV (question 10), dont
  les messages restent français dans les deux langues. Ils ne sortent que sur
  une base corrompue ; la garde les reconnaît par leur début, lu dans le code
  des modules qu'ARCHITECTURE.md déclare (« What stays in French »,
  `MODULES_RESTES_EN_FRANCAIS`).

Les champs de prose passent en plus les gardes de forme et de registre de
l'anglais ; l'écran d'acceptation dit à bon droit « not advice » et « buy,
sell, or hold », la garde prescriptive ne le lit pas.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from backend.api.static import VARIABLE as DOSSIER_DU_BUNDLE
from backend.typography import NARROW_NBSP, NBSP, WORD_JOINER, prose

from .conftest import PORTEFEUILLE_DEMO
from .gardes_texte import (
    FRANCAIS,
    PROVENANCE,
    fautes_de_forme,
    fautes_de_francais,
    fautes_de_registre,
    toutes_les_chaines,
)
from .test_langue_api import CHAMPS_DE_PROSE, deposer, refus

RACINE = Path(__file__).resolve().parents[1]

# Des données : un nom de portefeuille (dans la liste, seul, ou rappelé par
# l'analyse), un nom de titre (univers, valorisation), un nom de fichier, une
# valeur refusée telle qu'elle a été saisie.
DONNEES = re.compile(
    r"^\[\d+\]\.name$|^\.name$|^\.portfolio\.name$|\.valuation\.lines\[\d+\]\.name$"
    r"|\.problems\[\d+\]\.value$|^\.source\.filename$"
)

# Des identifiants, les mêmes dans les deux langues.
IDENTIFIANTS = re.compile(r"^\.source\.decimal_separator$")

# Les refus de validation de FastAPI : le message de pydantic, publié tel quel
# dans les deux langues (question 14). Son « should » qualifie une saisie, pas
# un placement ; la garde prescriptive ne le lit pas.
MESSAGE_DE_PYDANTIC = re.compile(r"^Input should ")

# Les modules dont les garde-fous internes restent en français, déclarés dans
# ARCHITECTURE.md (« What stays in French »).
MODULES_RESTES_EN_FRANCAIS = (
    "backend/risk_engine/measures.py",
    "backend/risk_engine/covariance.py",
    "backend/risk_engine/stress.py",
    "backend/risk_engine/returns.py",
    "backend/risk_engine/regime.py",
    "backend/risk_engine/config.py",
    "backend/risk_engine/var.py",
    "backend/risk_engine/engine.py",
    "backend/risk_engine/scenarios.py",
    "backend/api/csv_import.py",
)


def _uni(texte: str) -> str:
    """Les espaces de liaison ramenées à l'espace ordinaire."""
    return texte.replace(WORD_JOINER, "").replace(NBSP, " ").replace(NARROW_NBSP, " ")


def debuts_declares() -> set[str]:
    """Le début de chaque message levé par un module déclaré : le texte
    littéral d'un `raise`, jusqu'à la première valeur insérée."""
    debuts: set[str] = set()
    for relatif in MODULES_RESTES_EN_FRANCAIS:
        arbre = ast.parse((RACINE / relatif).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Raise) or not isinstance(noeud.exc, ast.Call):
                continue
            for argument in noeud.exc.args[:1]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    debut = argument.value
                elif isinstance(argument, ast.JoinedStr) and isinstance(
                    getattr(argument.values[0], "value", None), str
                ):
                    debut = argument.values[0].value
                else:
                    continue
                if FRANCAIS.search(debut) and len(debut.strip()) >= 8:
                    debuts.add(_uni(debut))
    return debuts


DEBUTS_DECLARES = debuts_declares()


def declare(texte: str) -> bool:
    return any(_uni(texte).startswith(debut) for debut in DEBUTS_DECLARES)


def francais_dans(corps) -> list[tuple[str, str]]:
    """Les chaînes d'une réponse anglaise qui contiennent du français, hors
    données, identifiants et garde-fous déclarés."""
    return [
        (chemin, faute)
        for chemin, texte in toutes_les_chaines(corps)
        if not DONNEES.search(chemin) and not IDENTIFIANTS.search(chemin) and not declare(texte)
        for faute in fautes_de_francais(texte)
    ]


def fautes_de_prose(corps) -> list[tuple[str, str]]:
    fautes = []
    for chemin, texte in toutes_les_chaines(corps):
        if not chemin.endswith(tuple(f".{champ}" for champ in CHAMPS_DE_PROSE)):
            continue
        if DONNEES.search(chemin):
            continue
        fautes += [
            (chemin, f)
            for f in fautes_de_forme(texte, "en", grec_admis=bool(PROVENANCE.search(chemin)))
        ]
        fautes += [
            (chemin, f)
            for f in fautes_de_registre(texte, "en")
            if not (
                f.startswith("prescriptif")
                and (
                    chemin.startswith((".disclaimer.", ".title", ".sections", ".confirmation", ".text"))
                    or MESSAGE_DE_PYDANTIC.match(texte)
                )
            )
        ]
    return fautes


def verifier(reponse, ou: str) -> None:
    corps = reponse.json()
    assert francais_dans(corps) == [], (ou, francais_dans(corps)[:5])
    assert fautes_de_prose(corps) == [], (ou, fautes_de_prose(corps)[:5])


# ═══════════════════════════════════════════════════════ La garde elle-même ══


def test_les_garde_fous_declares_sont_lus_dans_le_code():
    """Un module déclaré sans message français, ou un module disparu, ferait
    une liste qui ne déclare plus rien."""
    for relatif in MODULES_RESTES_EN_FRANCAIS:
        assert (RACINE / relatif).is_file(), relatif
    assert len(DEBUTS_DECLARES) >= 20, sorted(DEBUTS_DECLARES)


def test_la_garde_voit_le_francais_et_laisse_passer_le_declare():
    exemple_declare = next(iter(sorted(DEBUTS_DECLARES)))
    corps = {
        "detail": f"{exemple_declare} (valeur reçue : 3)",
        "name": "Démo",
        "problems": [{"value": "dix", "problem": "Sur 7 jours de bourse, aucun ne tombe."}],
        "source": {"decimal_separator": "aucune", "filename": "positions-été.csv"},
    }
    vues = francais_dans(corps)
    assert [chemin for chemin, _ in vues] == [".problems[0].problem"] * len(vues) and vues


def test_la_garde_prescriptive_ne_laisse_passer_que_pydantic():
    pydantic = {"detail": "Input should be greater than or equal to 60"}
    conseil = {"detail": "You should trim JPM."}
    assert fautes_de_prose(pydantic) == []
    assert fautes_de_prose(conseil)


# ═════════════════════════════════════════════════════ Le portefeuille synthétique ══


def test_le_portefeuille_synthetique_en_anglais(client_synthetique, portefeuille_synthetique):
    identifiant = portefeuille_synthetique
    chemins = [
        "/api/disclaimer",
        "/api/meta",
        "/api/securities",
        "/api/csv-format",
        "/api/portfolios",
        f"/api/portfolios/{identifiant}",
        f"/api/portfolios/{identifiant}/analysis",
        f"/api/portfolios/{identifiant}/analysis?window=250",
        f"/api/portfolios/{identifiant}/analysis?window=60",
        f"/api/portfolios/{identifiant}/analysis?benchmark=",
    ]
    for chemin in chemins:
        reponse = client_synthetique.get(f"{chemin}{'&' if '?' in chemin else '?'}lang=en")
        assert reponse.status_code == 200, (chemin, reponse.text)
        verifier(reponse, chemin)


def test_un_portefeuille_vide_et_un_indice_absent_en_anglais(client_synthetique, portefeuille_synthetique):
    vide = client_synthetique.post("/api/portfolios", json={"name": "Vide"}).json()["id"]
    for chemin, code in (
        (f"/api/portfolios/{vide}?lang=en", 409),
        (f"/api/portfolios/{vide}/analysis?lang=en", 409),
        ("/api/portfolios?lang=en", 200),
        (f"/api/portfolios/{portefeuille_synthetique}/analysis?benchmark=absent&lang=en", 409),
    ):
        reponse = client_synthetique.get(chemin)
        assert reponse.status_code == code, (chemin, reponse.text)
        verifier(reponse, chemin)


def test_chaque_refus_en_anglais(client_synthetique, portefeuille_synthetique):
    for methode, chemin, arguments in refus(portefeuille_synthetique):
        separateur = "&" if "?" in chemin else "?"
        reponse = getattr(client_synthetique, methode)(f"{chemin}{separateur}lang=en", **arguments)
        assert reponse.status_code in (404, 422), (chemin, reponse.status_code)
        verifier(reponse, f"{methode} {chemin}")
    validation = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=10&lang=en"
    )
    assert validation.status_code == 422
    verifier(validation, "fenêtre hors domaine")


def test_une_saisie_et_un_import_reussis_en_anglais(client_synthetique, portefeuille_synthetique):
    saisie = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions?lang=en",
        json={"positions": [{"ticker": "ALFA", "quantity": 10}, {"ticker": "MIKE", "quantity": 5}]},
    )
    assert saisie.status_code == 200, saisie.text
    verifier(saisie, "saisie")
    for contenu in (b"ticker;quantity\nALFA;10\nMIKE;5\n", b"ticker;quantity\nALFA;1,5\nMIKE;2.5\n"):
        reponse = deposer(client_synthetique, portefeuille_synthetique, contenu, "?lang=en")
        assert reponse.status_code == 200, reponse.text
        assert reponse.json()["source"]["decimal_separator"] in ("aucune", "mixte")
        verifier(reponse, "import")


@pytest.fixture
def client_avec_bundle(tmp_path, base_synthetique, client_factory, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Mx Risk MGT</title>", encoding="utf-8")
    monkeypatch.setenv(DOSSIER_DU_BUNDLE, str(dist))
    with client_factory(base_synthetique) as client:
        yield client


def test_le_chemin_d_api_inconnu_en_anglais(client_avec_bundle):
    reponse = client_avec_bundle.get("/api/portfolios/1/analyse-detaillee?lang=en")
    assert reponse.status_code == 404
    verifier(reponse, "chemin inconnu")


# ═══════════════════════════════════════════════════════════ Les fenêtres courtes ══


@pytest.mark.parametrize("seances_courtes", [2, 3, 8, 40])
def test_une_fenetre_courte_en_anglais(base_historique_court, client_factory, seances_courtes):
    """De la fenêtre refusée (deux cotations, une seule séance commune) aux
    estimations minces : chaque refus et chaque réserve en anglais."""
    with client_factory(base_historique_court(seances_courtes)) as client:
        identifiant = client.post("/api/portfolios", json={}).json()["id"]
        client.put(
            f"/api/portfolios/{identifiant}/positions",
            json={"positions": [{"ticker": "LONG", "quantity": 10}, {"ticker": "COURT", "quantity": 20}]},
        )
        for chemin in (
            f"/api/portfolios/{identifiant}/analysis?lang=en",
            f"/api/portfolios/{identifiant}?lang=en",
            "/api/portfolios?lang=en",
        ):
            reponse = client.get(chemin)
            assert reponse.status_code in (200, 409, 422), (chemin, reponse.text)
            verifier(reponse, f"{seances_courtes} cotations : {chemin}")


# ═══════════════════════════════════════════════════════════ La démonstration ══


def test_la_demonstration_en_anglais(base_figee, client_factory):
    """La copie figée, le portefeuille de démonstration, à 504 et à 60
    séances : la page qu'un visiteur anglophone lira."""
    with client_factory(base_figee) as client:
        identifiant = client.post("/api/portfolios", json={"name": "Démo"}).json()["id"]
        ecriture = client.put(
            f"/api/portfolios/{identifiant}/positions?lang=en",
            json={
                "positions": [
                    {"ticker": ticker, "quantity": quantite}
                    for ticker, quantite in PORTEFEUILLE_DEMO.items()
                ]
            },
        )
        assert ecriture.status_code == 200, ecriture.text
        for chemin in (
            f"/api/portfolios/{identifiant}/analysis?window=504&lang=en",
            f"/api/portfolios/{identifiant}/analysis?window=60&lang=en",
            f"/api/portfolios/{identifiant}?lang=en",
            "/api/portfolios?lang=en",
            "/api/securities?lang=en",
        ):
            reponse = client.get(chemin)
            assert reponse.status_code == 200, (chemin, reponse.text)
            verifier(reponse, chemin)
