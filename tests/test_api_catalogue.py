"""`GET /api/meta` et `GET /api/securities` — l'état de la base, tel qu'il est.

Le point de ces deux endpoints est de ne rien inventer : `as_of` sort de la
table des prix et jamais de l'horloge, et un titre sans historique apparaît en
disant qu'il n'en a pas plutôt que de disparaître.
"""

from __future__ import annotations

from datetime import date

from .conftest import construire_base


def test_as_of_est_la_derniere_seance_en_base_pas_la_date_du_jour(
    client_synthetique,
):
    """La base synthétique s'arrête en 2024 ; la réponse doit le dire.

    C'est la garantie centrale de cet endpoint. Une base qui n'a pas été
    rafraîchie depuis des mois doit l'annoncer ; `date.today()` afficherait une
    fraîcheur que personne n'a vérifiée.
    """
    meta = client_synthetique.get("/api/meta").json()
    assert meta["as_of"] < date.today().isoformat()
    assert meta["as_of"].startswith("2024")


def test_meta_compte_les_titres_de_l_univers(client_synthetique):
    assert client_synthetique.get("/api/meta").json()["securities_count"] == 4


def test_securities_donne_les_bornes_de_couverture(client_synthetique):
    titres = {t["ticker"]: t for t in client_synthetique.get("/api/securities").json()}
    assert sorted(titres) == ["ALFA", "MIKE", "SPY", "ZULU"]
    alfa = titres["ALFA"]
    assert alfa["name"] == "Alfa Inc"
    assert alfa["sector"] == "Financials"
    assert alfa["first_price_date"] < alfa["last_price_date"]
    assert alfa["has_prices"] is True


def test_un_titre_sans_secteur_ressort_a_null_et_non_a_la_chaine_vide(
    client_synthetique,
):
    """SPY n'a pas de secteur propre : il les contient tous.

    `null` dit « pas de secteur » ; `""` se confondrait avec un secteur dont le
    nom serait vide, et une interface le rendrait par une case blanche sans
    savoir laquelle des deux situations elle affiche.
    """
    titres = {t["ticker"]: t for t in client_synthetique.get("/api/securities").json()}
    assert titres["SPY"]["sector"] is None


def test_un_titre_sans_historique_reste_liste_avec_des_dates_nulles(
    tmp_path, client_factory
):
    """« Présent mais jamais ingéré » et « absent de l'univers » ne sont pas la
    même chose, et n'appellent pas la même action."""
    chemin = construire_base(
        tmp_path / "creuse.sqlite",
        {"ALFA": ("Alfa Inc", "Financials", [100.0, 101.0, 102.0])},
        3,
    )
    from backend.db.init_db import connect

    conn = connect(chemin)
    with conn:
        conn.execute(
            "INSERT INTO securities (ticker, name, sector) VALUES ('VIDE', 'Sans prix', NULL)"
        )
    conn.close()

    with client_factory(chemin) as client:
        titres = {t["ticker"]: t for t in client.get("/api/securities").json()}

    assert titres["VIDE"]["first_price_date"] is None
    assert titres["VIDE"]["last_price_date"] is None
    assert titres["VIDE"]["has_prices"] is False


def test_une_base_sans_aucun_prix_rend_as_of_null(tmp_path, client_factory):
    """Pas de date plutôt qu'une date fausse.

    Champ par champ, et non par égalité sur toute la réponse : ce test porte
    sur `as_of`, pas sur la liste des champs de `/api/meta`. Cette liste est
    déjà surveillée par `test_openapi_schema.py`, qui compare le schéma publié
    au schéma commité — y revenir ici par une égalité complète ne comblerait
    aucun trou, et ferait échouer ce test à chaque champ ajouté sans que
    `as_of` soit en cause.
    """
    from backend.db.init_db import init_db

    chemin = tmp_path / "vide.sqlite"
    init_db(chemin)
    with client_factory(chemin) as client:
        meta = client.get("/api/meta").json()
    assert meta["as_of"] is None
    assert meta["securities_count"] == 0
    # La devise est une hypothèse du périmètre, publiée même sur une base vide.
    assert meta["price_currency"] == "USD"
