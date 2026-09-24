"""La valorisation ligne à ligne, dans la MÊME réponse que les mesures.

Le tableau « Le portefeuille » (DESIGN.md §8.2, section 1) affiche quantité,
prix, valeur et poids. Les lire sur `GET /api/portfolios/{id}` ferait décrire
deux états de la base à une même page si les prix étaient rafraîchis entre les
deux appels — exactement ce que l'endpoint unique d'analyse existe pour
empêcher.
"""

from __future__ import annotations

import pytest

from .conftest import PORTEFEUILLE_DEMO


def test_la_valorisation_est_datee_comme_l_analyse(analyse_reelle):
    corps = analyse_reelle.json()
    assert corps["valuation"]["as_of"] == corps["as_of"]
    assert corps["valuation"]["total_value"] == corps["total_value"]


def test_les_lignes_suivent_l_ordre_canonique_et_ses_poids(analyse_reelle):
    """Un tableau et une carte de chaleur ne s'étiquettent pas différemment."""
    corps = analyse_reelle.json()
    lignes = corps["valuation"]["positions"]
    assert [ligne["ticker"] for ligne in lignes] == corps["tickers"]
    assert [ligne["weight"] for ligne in lignes] == [p["weight"] for p in corps["weights"]]


def test_les_quantites_sont_celles_stockees(analyse_reelle):
    lignes = analyse_reelle.json()["valuation"]["positions"]
    assert {ligne["ticker"]: ligne["quantity"] for ligne in lignes} == {
        ticker: float(quantite) for ticker, quantite in PORTEFEUILLE_DEMO.items()
    }


def test_la_valeur_est_la_quantite_au_prix_publie(analyse_reelle):
    """Relation vérifiée ici, jamais calculée par l'API ni par le client."""
    for ligne in analyse_reelle.json()["valuation"]["positions"]:
        assert ligne["value"] == pytest.approx(ligne["quantity"] * ligne["price"], rel=1e-12)


def test_chaque_ligne_porte_le_nom_du_catalogue(client_synthetique, portefeuille_synthetique):
    catalogue = {
        titre["ticker"]: titre["name"]
        for titre in client_synthetique.get("/api/securities").json()
    }
    analyse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()
    detail = client_synthetique.get(f"/api/portfolios/{portefeuille_synthetique}").json()

    for lignes in (analyse["valuation"]["positions"], detail["valuation"]["positions"]):
        assert lignes
        for ligne in lignes:
            assert ligne["name"] == catalogue[ligne["ticker"]]


# ═════════════════════════════════════════════════════════════ Devise ══


def test_la_devise_est_publiee_sur_la_valorisation_et_dans_meta(
    client_synthetique, portefeuille_synthetique
):
    """Un code ISO, jamais un symbole : « $ » se lit dollar canadien à Montréal."""
    from backend.risk_engine.config import PRICE_CURRENCY

    analyse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    ).json()
    detail = client_synthetique.get(f"/api/portfolios/{portefeuille_synthetique}").json()
    meta = client_synthetique.get("/api/meta").json()

    assert PRICE_CURRENCY == "USD"
    assert analyse["valuation"]["currency"] == PRICE_CURRENCY
    assert detail["valuation"]["currency"] == PRICE_CURRENCY
    assert meta["price_currency"] == PRICE_CURRENCY
