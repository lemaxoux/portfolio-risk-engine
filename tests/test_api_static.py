"""Le service du bundle frontend, et les deux choses qu'il ne doit pas casser.

En production, une seule application sert l'API et la page. Ce montage a deux
façons de mal tourner, opposées l'une à l'autre :

* servir `index.html` pour tout, `/api/nexiste-pas` compris — le client reçoit
  200 et du HTML là où il attend du JSON, et une faute de frappe dans une URL
  devient indébogable ;
* rendre 404 pour les routes du CLIENT — un rechargement sur `/methodologie`
  tombe sur une page d'erreur alors que l'application sait l'afficher.

Les deux sont vérifiées ici, plus une troisième propriété qui n'a rien à voir
avec le navigateur : la suite Python doit tourner sur une machine où Node n'a
jamais été installé.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.api.static import VARIABLE


@pytest.fixture
def bundle(tmp_path) -> Path:
    """Un `dist` minimal mais réaliste : un index et une ressource empreintée."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html lang=fr><body>Mx Risk MGT</body></html>",
        encoding="utf-8",
    )
    (dist / "assets" / "index-abc123.js").write_text(
        "export const rien = 0\n", encoding="utf-8"
    )
    return dist


@pytest.fixture
def client_avec_bundle(bundle, base_synthetique, client_factory, monkeypatch):
    monkeypatch.setenv(VARIABLE, str(bundle))
    with client_factory(base_synthetique) as client:
        yield client


@pytest.fixture
def client_sans_bundle(tmp_path, base_synthetique, client_factory, monkeypatch):
    monkeypatch.setenv(VARIABLE, str(tmp_path / "jamais-construit"))
    with client_factory(base_synthetique) as client:
        yield client


# ═══════════════════════ 1. Sans bundle, l'application démarre ══


def test_l_application_demarre_sans_bundle_construit(client_sans_bundle):
    """La suite Python n'exige pas Node.

    Le contrôle de schéma du `lifespan` s'exécute — le client est utilisé comme
    gestionnaire de contexte —, donc ce test dit bien que l'application est
    montée, pas seulement importée.
    """
    reponse = client_sans_bundle.get("/api/meta")
    assert reponse.status_code == 200
    assert "as_of" in reponse.json()


def test_sans_bundle_la_racine_ne_pretend_pas_servir_une_page(client_sans_bundle):
    """Aucune route attrape-tout n'est déclarée : la racine est un 404 franc.

    Un `index.html` fabriqué à la volée pour faire joli cacherait que le bundle
    n'a jamais été construit, et la panne se produirait plus loin.
    """
    assert client_sans_bundle.get("/").status_code == 404


# ═══════════════════ 2. Le repli ne masque jamais l'API ══


def test_une_route_d_api_inconnue_rend_du_json_et_non_index_html(client_avec_bundle):
    """LE test de ce module.

    `GET /api/nexiste-pas` doit rendre 404 et du JSON. S'il rendait
    `index.html`, le client recevrait 200 et `JSON.parse` échouerait sur
    « <!doctype » — un message d'erreur qui ne parle plus de la requête.
    """
    reponse = client_avec_bundle.get("/api/nexiste-pas")

    assert reponse.status_code == 404
    assert reponse.headers["content-type"].startswith("application/json")
    corps = json.loads(reponse.content)
    assert "nexiste-pas" in corps["detail"]
    # Même forme de corps que le reste de l'API : un client n'a qu'un format.
    assert corps["problems"] == []
    assert "doctype" not in reponse.text.lower()


def test_un_sous_chemin_d_api_inconnu_est_refuse_lui_aussi(client_avec_bundle):
    reponse = client_avec_bundle.get("/api/portfolios/1/analyse-detaillee")
    assert reponse.status_code == 404
    assert reponse.headers["content-type"].startswith("application/json")


def test_les_vraies_routes_d_api_passent_avant_le_repli(client_avec_bundle):
    """La route attrape-tout est déclarée APRÈS les routeurs.

    Starlette retient la PREMIÈRE correspondance complète : déclarée en tête,
    elle avalerait l'API entière, et ce test est ce qui l'interdit.
    """
    assert client_avec_bundle.get("/api/meta").status_code == 200
    assert client_avec_bundle.get("/api/portfolios").status_code == 200


def test_une_mauvaise_methode_reste_un_405_et_ne_devient_pas_un_404(
    client_avec_bundle,
):
    """Le diagnostic juste n'est pas écrasé par le repli.

    Un `Mount("/")` répondrait correspondance complète pour n'importe quelle
    méthode, et Starlette ne rend 405 que s'il n'a trouvé AUCUNE correspondance
    complète : tout `POST` sur un chemin d'API existant serait devenu 404. La
    route attrape-tout est limitée à GET et HEAD précisément pour cela.
    """
    reponse = client_avec_bundle.post("/api/meta", json={})
    assert reponse.status_code == 405


# ═══════════════════ 3. Le repli sert bien les routes du client ══


def test_une_route_du_client_rend_index_html(client_avec_bundle):
    reponse = client_avec_bundle.get("/methodologie")
    assert reponse.status_code == 200
    assert "Mx Risk MGT" in reponse.text
    # `index.html` n'est jamais gardé en cache : il pointe sur des ressources
    # empreintées qui n'existent plus après une reconstruction.
    assert reponse.headers["cache-control"] == "no-store"


def test_la_racine_rend_index_html(client_avec_bundle):
    reponse = client_avec_bundle.get("/")
    assert reponse.status_code == 200
    assert "Mx Risk MGT" in reponse.text


def test_une_ressource_construite_est_servie_telle_quelle(client_avec_bundle):
    reponse = client_avec_bundle.get("/assets/index-abc123.js")
    assert reponse.status_code == 200
    assert "export const rien" in reponse.text
    assert "javascript" in reponse.headers["content-type"]


def test_le_repli_ne_sort_pas_du_dossier_servi(client_avec_bundle):
    """Un chemin qui remonte ne doit rien lire ailleurs sur le disque.

    Le contrôle porte sur le chemin RÉSOLU : filtrer la chaîne d'entrée
    laisserait passer les formes encodées. Ici la remontée ne produit pas une
    fuite mais le repli, ce qui est le comportement voulu — l'application, pas
    un fichier du dépôt.
    """
    reponse = client_avec_bundle.get("/../requirements.txt")
    assert reponse.status_code in (200, 404)
    assert "fastapi==" not in reponse.text
