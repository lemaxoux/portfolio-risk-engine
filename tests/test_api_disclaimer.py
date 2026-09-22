"""`GET /api/disclaimer` — le bandeau d'acceptation, avant tout portefeuille.

L'écran d'acceptation est une page entière que l'utilisateur traverse avant le
premier accès (DESIGN.md §15). Il précède donc l'existence du moindre
portefeuille, et le texte doit être disponible sans analyse.

CE QUE CETTE ROUTE ÉVITE — si le texte n'était servi que par `/analysis`, le
client en embarquerait une copie pour pouvoir afficher l'écran d'accueil. Cette
copie deviendrait le texte réellement affiché, et le jour où le bandeau
changerait côté serveur, l'utilisateur continuerait de lire l'ancien : un texte
à portée quasi juridique figé dans un bundle, sans que rien ne le signale.
"""

from __future__ import annotations

import pytest

from backend.risk_engine.config import DEFAULT_WINDOW
from backend.rules.disclaimer import (
    ACCEPTANCE_CONFIRMATION,
    ACCEPTANCE_TITLE,
    acceptance_sections,
)


@pytest.fixture
def client(base_synthetique, client_factory):
    with client_factory(base_synthetique) as client:
        yield client


def test_le_bandeau_est_servi_sans_portefeuille(client):
    """Aucun portefeuille n'est créé par ce test — c'est tout l'intérêt."""
    reponse = client.get("/api/disclaimer")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["title"] == ACCEPTANCE_TITLE
    assert corps["confirmation"] == ACCEPTANCE_CONFIRMATION
    assert len(corps["sections"]) == len(acceptance_sections(DEFAULT_WINDOW))


def test_le_bandeau_est_structure_et_a_plat(client):
    """Les deux formes voyagent ensemble.

    Les sections servent à la mise en page — une page entière, pas une modale.
    `text` est le même contenu en un bloc : c'est lui dont le client prend
    l'empreinte pour savoir si le texte a changé depuis l'acceptation.
    """
    corps = client.get("/api/disclaimer").json()

    for section in corps["sections"]:
        assert section["title"]
        assert section["body"]
        assert section["title"] in corps["text"]
        assert section["body"] in corps["text"]
    assert corps["title"] in corps["text"]
    assert corps["confirmation"] in corps["text"]


def test_le_texte_est_identique_a_celui_que_sert_l_analyse(client):
    """Les deux routes servent le MÊME texte pour la même fenêtre.

    Sans cette égalité, l'utilisateur accepterait un texte et en lirait un autre
    en pied de section 6. Elle est vérifiée, pas supposée : `DisclaimerOut.seul`
    et `DisclaimerOut.of` remplissent `text` par deux chemins différents —
    `acceptance_text(window)` d'un côté, `rules_report.disclaimer` de l'autre.
    """
    identifiant = client.post("/api/portfolios", json={}).json()["id"]
    ecriture = client.put(
        f"/api/portfolios/{identifiant}/positions",
        json={
            "positions": [
                {"ticker": "ALFA", "quantity": 10},
                {"ticker": "MIKE", "quantity": 30},
            ]
        },
    )
    assert ecriture.status_code == 200, ecriture.text

    # La MÊME fenêtre que celle du bandeau autonome, sinon la comparaison ne
    # dirait rien : le texte cite la fenêtre demandée, et il doit en changer.
    analyse = client.get(
        f"/api/portfolios/{identifiant}/analysis?window={DEFAULT_WINDOW}"
    )
    assert analyse.status_code == 200, analyse.text

    seul = client.get("/api/disclaimer").json()
    assert seul == analyse.json()["disclaimer"]


def test_le_texte_cite_la_fenetre_de_la_configuration_du_moteur(client):
    """Le nombre de séances n'est pas écrit en dur dans le bandeau.

    Le jour où `DEFAULT_WINDOW` changerait, un texte codé en dur annoncerait une
    profondeur d'historique que le calcul n'utilise plus.
    """
    texte = client.get("/api/disclaimer").json()["text"]
    assert str(DEFAULT_WINDOW) in texte


def test_la_route_est_en_lecture_seule(client):
    """Ni écriture, ni paramètre. Une méthode d'écriture est refusée."""
    assert client.post("/api/disclaimer", json={}).status_code == 405
    assert client.put("/api/disclaimer", json={}).status_code == 405
    assert client.delete("/api/disclaimer").status_code == 405
