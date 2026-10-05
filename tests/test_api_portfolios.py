"""Cycle de vie d'un portefeuille : création, positions, valorisation, suppression.

Deux propriétés sont verrouillées ici avant le reste : une écriture de positions
est un REMPLACEMENT complet, et elle est TOUT OU RIEN. Un import à moitié
appliqué produirait une valorisation plausible et fausse — le pire des deux
mondes, puisque rien n'aurait l'air cassé.
"""

from __future__ import annotations

from datetime import date

from backend.db import portfolios as store
from backend.db.init_db import connect


# ════════════════════════════════════════════════════════════ Création ══


def test_creation_renvoie_un_identifiant_et_un_portefeuille_vide(
    client_synthetique,
):
    reponse = client_synthetique.post(
        "/api/portfolios", json={"name": "Mon portefeuille"}
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert isinstance(corps["id"], int)
    assert corps["name"] == "Mon portefeuille"
    assert corps["owner"] == "local"


def test_la_creation_ne_date_pas_les_positions(client_synthetique):
    """`updated_at` est la fraîcheur des POSITIONS, pas l'âge de la ligne.

    Le dater à la création annoncerait des positions à jour alors qu'il n'y en a
    aucune. `null` se lit « jamais modifié depuis l'application », ce qui est
    exactement vrai d'un portefeuille qu'on vient de créer.
    """
    corps = client_synthetique.post("/api/portfolios", json={}).json()
    assert corps["updated_at"] is None


def test_le_nom_par_defaut_n_est_pas_le_proprietaire(client_synthetique):
    corps = client_synthetique.post("/api/portfolios", json={}).json()
    assert corps["name"] == "Portefeuille"
    assert corps["owner"] == "local"


# ═══════════════════════════════════════════════ Positions et valorisation ══


def test_les_positions_sont_valorisees_a_la_derniere_cloture(
    client_synthetique, portefeuille_synthetique
):
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()
    valorisation = corps["valuation"]
    assert valorisation["as_of"].startswith("2024")
    lignes = {p["ticker"]: p for p in valorisation["positions"]}
    assert sorted(lignes) == ["ALFA", "MIKE", "ZULU"]
    assert lignes["ALFA"]["quantity"] == 10.0
    assert lignes["MIKE"]["weight"] > lignes["ZULU"]["weight"]


def test_les_poids_somment_a_un(client_synthetique, portefeuille_synthetique):
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()
    total = sum(p["weight"] for p in corps["valuation"]["positions"])
    assert abs(total - 1.0) < 1e-12


def test_la_quantite_est_relue_en_base_et_non_deduite_du_prix(
    client_synthetique, portefeuille_synthetique
):
    """Une quantité retrouvée en divisant la valeur par le prix serait un calcul
    de la couche API — et presque juste, ce qui est le pire cas."""
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()
    quantites = {
        p["ticker"]: p["quantity"] for p in corps["valuation"]["positions"]
    }
    assert quantites == {"ALFA": 10.0, "MIKE": 30.0, "ZULU": 40.0}


def test_le_remplacement_remplace_au_lieu_d_ajouter(
    client_synthetique, portefeuille_synthetique
):
    """Déposer deux fois le même portefeuille ne doit pas doubler les quantités."""
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": [{"ticker": "ALFA", "quantity": 5}]},
    )
    assert reponse.status_code == 200
    assert reponse.json()["positions_count"] == 1
    assert reponse.json()["replaced"] is True

    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()
    lignes = corps["valuation"]["positions"]
    assert len(lignes) == 1
    assert lignes[0]["quantity"] == 5.0


def test_le_remplacement_date_les_positions(
    client_synthetique, portefeuille_synthetique
):
    corps = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()
    assert corps["updated_at"] == date.today().isoformat()


def test_le_prix_de_revient_est_conserve_et_reste_optionnel(
    client_synthetique, portefeuille_synthetique
):
    client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "ALFA", "quantity": 5, "cost_basis": 42.5},
                {"ticker": "MIKE", "quantity": 5},
            ]
        },
    )
    lignes = {
        p["ticker"]: p
        for p in client_synthetique.get(
            f"/api/portfolios/{portefeuille_synthetique}"
        ).json()["valuation"]["positions"]
    }
    assert lignes["ALFA"]["cost_basis"] == 42.5
    assert lignes["MIKE"]["cost_basis"] is None


# ═══════════════════════════════════════════════════ Positions stockées ══
#
# `positions` rend les lignes TELLES QU'ELLES SONT STOCKÉES — ticker, quantité,
# prix de revient —, que le portefeuille soit valorisable ou non. C'est ce que
# l'écran de saisie préremplit, et c'est ce qui dit qu'un portefeuille est vide
# sans aller chercher « sans position » dans le texte de `valuation_error`.


def test_les_positions_stockees_voyagent_avec_le_portefeuille(
    client_synthetique, portefeuille_synthetique
):
    client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "MIKE", "quantity": 5},
                {"ticker": "alfa", "quantity": 2.5, "cost_basis": 42.5},
            ]
        },
    )
    attendues = [
        {"ticker": "ALFA", "quantity": 2.5, "cost_basis": 42.5},
        {"ticker": "MIKE", "quantity": 5.0, "cost_basis": None},
    ]
    seul = client_synthetique.get(f"/api/portfolios/{portefeuille_synthetique}").json()
    assert seul["positions"] == attendues, "stockées : ticker normalisé, ordre des tickers"

    (dans_la_liste,) = client_synthetique.get("/api/portfolios").json()
    assert dans_la_liste["positions"] == attendues


def test_un_portefeuille_vide_se_reconnait_a_ses_positions(client_synthetique):
    client_synthetique.post("/api/portfolios", json={"name": "Vide"})
    (vide,) = client_synthetique.get("/api/portfolios").json()
    assert vide["positions"] == []
    assert vide["valuation"] is None


def test_un_portefeuille_non_valorisable_garde_ses_positions(tmp_path, client_factory):
    """Une ligne dont les prix ont disparu : pas de valorisation, mais les
    positions restent lisibles — sans elles, l'écran de saisie ne pourrait pas
    préremplir le portefeuille à réparer."""
    from .conftest import construire_base

    chemin = construire_base(
        tmp_path / "cassee.sqlite",
        {"ALFA": ("Alfa Inc", "Financials", [100.0, 101.0, 102.0])},
        3,
    )
    with client_factory(chemin) as client:
        identifiant = client.post("/api/portfolios", json={"name": "Cassé"}).json()["id"]
        client.put(
            f"/api/portfolios/{identifiant}/positions",
            json={"positions": [{"ticker": "ALFA", "quantity": 3, "cost_basis": 90.0}]},
        )
        conn = connect(chemin)
        with conn:
            conn.execute("DELETE FROM prices WHERE ticker = 'ALFA'")
        conn.close()
        (casse,) = client.get("/api/portfolios").json()

    assert casse["valuation"] is None
    assert casse["valuation_error"]
    assert casse["positions"] == [{"ticker": "ALFA", "quantity": 3.0, "cost_basis": 90.0}]


# ═══════════════════════════════════════════════════════════════ Refus ══


def test_un_ticker_inconnu_est_refuse_en_4xx_avec_un_message_exploitable(
    client_synthetique, portefeuille_synthetique
):
    """Pas un 500 : l'utilisateur doit savoir quoi faire, pas qu'il a planté."""
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": [{"ticker": "XYZ", "quantity": 10}]},
    )
    assert reponse.status_code == 422
    corps = reponse.json()
    probleme = corps["problems"][0]
    assert probleme["value"] == "XYZ"
    assert probleme["problem"].startswith("XYZ n'est pas un titre connu. ")
    # Les titres disponibles et la commande d'ajout sont dans le message.
    assert "ALFA" in probleme["problem"]
    assert "python -m backend.ingestion add XYZ" in probleme["problem"]


def test_un_ticker_sans_historique_de_prix_est_refuse(tmp_path, client_factory):
    from .conftest import construire_base

    chemin = construire_base(
        tmp_path / "creuse.sqlite",
        {"ALFA": ("Alfa Inc", "Financials", [100.0, 101.0, 102.0])},
        3,
    )
    conn = connect(chemin)
    with conn:
        conn.execute(
            "INSERT INTO securities (ticker, name, sector) VALUES ('VIDE', 'Sans prix', NULL)"
        )
    conn.close()

    with client_factory(chemin) as client:
        identifiant = client.post("/api/portfolios", json={}).json()["id"]
        reponse = client.put(
            f"/api/portfolios/{identifiant}/positions",
            json={"positions": [{"ticker": "VIDE", "quantity": 1}]},
        )

    assert reponse.status_code == 422
    probleme = reponse.json()["problems"][0]
    assert "aucun historique de prix" in probleme["problem"]
    assert "python -m backend.ingestion add VIDE" in probleme["problem"]


def test_une_quantite_nulle_ou_negative_est_refusee(
    client_synthetique, portefeuille_synthetique
):
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "ALFA", "quantity": 0},
                {"ticker": "MIKE", "quantity": -3},
            ]
        },
    )
    assert reponse.status_code == 422
    problemes = reponse.json()["problems"]
    assert len(problemes) == 2
    assert all("nulle ou négative" in p["problem"] for p in problemes)


def test_le_refus_cite_la_quantite_a_la_francaise(
    client_synthetique, portefeuille_synthetique
):
    """« (\u22123) », et non « (-3.0) » : la phrase est de la prose, le
    nombre passe par `typography`."""
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": [{"ticker": "MIKE", "quantity": -3}, {"ticker": "ALFA", "quantity": -2.5}]},
    )
    assert reponse.status_code == 422
    problemes = [p["problem"] for p in reponse.json()["problems"]]
    assert "pour MIKE (\u22123)." in problemes[0]
    assert "pour ALFA (\u22122,5)." in problemes[1]


def test_un_doublon_est_refuse_en_nommant_les_deux_lignes(
    client_synthetique, portefeuille_synthetique
):
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "ALFA", "quantity": 10},
                {"ticker": "alfa", "quantity": 5},
            ]
        },
    )
    assert reponse.status_code == 422
    assert "apparaît deux fois" in reponse.json()["problems"][0]["problem"]


def test_le_numero_de_ligne_d_une_saisie_revient_dans_ses_refus(
    client_synthetique, portefeuille_synthetique
):
    """`line` est le numéro de la ligne telle que l'utilisateur la voit, fourni
    par qui le connaît : le lecteur CSV pour un fichier, le client pour un
    tableau de saisie. L'API le renvoie tel quel, sans l'interpréter — chaque
    refus se rattache à sa ligne sans que le client lise la phrase."""
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "ALFA", "quantity": 10, "line": 1},
                {"ticker": "XYZ", "quantity": 10, "line": 2},
                {"ticker": "MIKE", "quantity": -1, "line": 3},
                {"ticker": "ALFA", "quantity": 5, "line": 4},
                {"ticker": "ZULU", "quantity": 2, "cost_basis": -3.0, "line": 5},
            ]
        },
    )
    assert reponse.status_code == 422
    par_ligne = {p["line"]: p for p in reponse.json()["problems"]}
    assert set(par_ligne) == {2, 3, 4, 5}
    assert par_ligne[2]["field"] == "ticker"
    assert par_ligne[3]["field"] == "quantity"
    assert par_ligne[4]["field"] == "ticker"
    assert "déjà ligne 1" in par_ligne[4]["problem"]
    assert par_ligne[5]["field"] == "cost_basis"


def test_sans_numero_de_ligne_un_refus_n_en_invente_pas(
    client_synthetique, portefeuille_synthetique
):
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": [{"ticker": "XYZ", "quantity": 10}]},
    )
    assert reponse.json()["problems"][0]["line"] is None


def test_un_numero_de_ligne_commence_a_un(client_synthetique, portefeuille_synthetique):
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": [{"ticker": "ALFA", "quantity": 10, "line": 0}]},
    )
    assert reponse.status_code == 422
    assert reponse.json()["problems"][0]["field"] == "line"


def test_tous_les_refus_sont_rendus_d_un_coup(
    client_synthetique, portefeuille_synthetique
):
    """Trois lignes fautives, une seule réponse : pas trois allers-retours."""
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "XYZ", "quantity": 10},
                {"ticker": "ALFA", "quantity": -1},
                {"ticker": "NOPE", "quantity": 3},
            ]
        },
    )
    assert reponse.status_code == 422
    assert len(reponse.json()["problems"]) == 3
    # Les messages d'erreur de l'API ne sont pas du texte de rapport : la
    # convention typographique du backend (`backend/typography.py`) porte sur
    # ce que les mesures RÉDIGENT, pas sur les diagnostics de validation.
    assert "3 lignes refusées" in reponse.json()["detail"]


def test_un_refus_n_ecrit_rien_du_tout(
    client_synthetique, portefeuille_synthetique
):
    """Aucun import partiel : la ligne valide du lot refusé n'est pas écrite."""
    avant = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()["valuation"]["positions"]

    client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={
            "positions": [
                {"ticker": "ALFA", "quantity": 999},
                {"ticker": "XYZ", "quantity": 10},
            ]
        },
    )

    apres = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()["valuation"]["positions"]
    assert apres == avant


def test_une_liste_vide_est_refusee(client_synthetique, portefeuille_synthetique):
    reponse = client_synthetique.put(
        f"/api/portfolios/{portefeuille_synthetique}/positions",
        json={"positions": []},
    )
    assert reponse.status_code == 422
    # Un problème unique est repris tel quel dans `detail` : le résumer par un
    # décompte remplacerait l'explication par un chiffre.
    assert "Aucune position soumise" in reponse.json()["detail"]


def test_un_portefeuille_inexistant_repond_404(client_synthetique):
    for methode, chemin in (
        ("get", "/api/portfolios/999"),
        ("get", "/api/portfolios/999/analysis"),
        ("delete", "/api/portfolios/999"),
    ):
        reponse = getattr(client_synthetique, methode)(chemin)
        assert reponse.status_code == 404, chemin
        assert "999" in reponse.json()["detail"]


def test_un_portefeuille_sans_position_repond_409_avec_la_raison(
    client_synthetique,
):
    """Il existe, mais il n'est pas valorisable : ce n'est ni un 404 ni un 500."""
    identifiant = client_synthetique.post("/api/portfolios", json={}).json()["id"]
    reponse = client_synthetique.get(f"/api/portfolios/{identifiant}")
    assert reponse.status_code == 409
    assert "sans position" in reponse.json()["detail"]


def test_la_liste_tolere_un_portefeuille_cassé_sans_perdre_les_autres(
    client_synthetique, portefeuille_synthetique
):
    """Un portefeuille non valorisable ne doit pas priver l'utilisateur du reste.

    Il ressort avec `valuation: null` ET la raison — jamais un blanc seul.
    """
    client_synthetique.post("/api/portfolios", json={"name": "Vide"})
    liste = client_synthetique.get("/api/portfolios").json()
    assert len(liste) == 2

    par_nom = {p["name"]: p for p in liste}
    assert par_nom["Synthétique"]["valuation"] is not None
    assert par_nom["Synthétique"]["valuation_error"] is None
    assert par_nom["Vide"]["valuation"] is None
    assert "sans position" in par_nom["Vide"]["valuation_error"]


# ════════════════════════════════════════════════════════ Suppression ══


def test_la_suppression_emporte_les_positions(
    client_synthetique, portefeuille_synthetique, base_synthetique
):
    reponse = client_synthetique.delete(
        f"/api/portfolios/{portefeuille_synthetique}"
    )
    assert reponse.status_code == 204
    assert client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).status_code == 404

    conn = connect(base_synthetique)
    restantes = store.load_positions(conn, portefeuille_synthetique)
    conn.close()
    assert restantes == []
