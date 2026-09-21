"""Import CSV — survivre à ce qu'exporte vraiment un tableur français.

Le cas nominal de la documentation (`,` et UTF-8) est le cas MINORITAIRE sur un
Windows français : « Enregistrer sous → CSV » y produit du point-virgule, du
CP1252 et des décimales à la virgule. Un lecteur qui ne gère que le cas nominal
rejette les fichiers de la moitié de ses utilisateurs, ou pire, n'y voit qu'une
seule colonne et importe n'importe quoi.
"""

from __future__ import annotations

import pytest

from backend.api.csv_import import PROBE_BYTES, CsvError, read


def depose(client, portefeuille, contenu: bytes, nom: str = "positions.csv"):
    return client.post(
        f"/api/portfolios/{portefeuille}/positions/csv",
        files={"file": (nom, contenu, "text/csv")},
    )


# ══════════════════════════════════════════════════ Le cas Excel français ══


def test_un_csv_point_virgule_cp1252_s_importe(
    client_synthetique, portefeuille_synthetique
):
    """Le cas qui casse tous les lecteurs naïfs, bout à bout.

    Point-virgule, CP1252, accent dans une colonne libre, décimale à la virgule,
    fins de ligne Windows. Le fichier est construit en OCTETS : le décoder ici
    pour le recoder ne testerait rien.
    """
    contenu = (
        "ticker;quantity;cost_basis\r\n"
        "ALFA;12,5;48,30\r\n"
        "MIKE;30;201,75\r\n"
        "ZULU;40;79,90\r\n"
    ).encode("cp1252")

    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text

    corps = reponse.json()
    assert corps["positions_count"] == 3
    assert corps["source"]["delimiter"] == ";"
    assert corps["source"]["decimal_separator"] == ","

    lignes = {
        p["ticker"]: p
        for p in client_synthetique.get(
            f"/api/portfolios/{portefeuille_synthetique}"
        ).json()["valuation"]["positions"]
    }
    # La décimale à la virgule a bien été lue comme une décimale, pas tronquée.
    assert lignes["ALFA"]["quantity"] == 12.5
    assert lignes["ALFA"]["cost_basis"] == 48.30


def test_l_encodage_cp1252_est_detecte_et_annonce(
    client_synthetique, portefeuille_synthetique
):
    """Avec un accent, les octets CP1252 ne sont pas de l'UTF-8 valide.

    Sans accent, les mêmes octets seraient indiscernables d'UTF-8 — c'est
    pourquoi ce test en met un.
    """
    contenu = (
        "ticker;quantity;libellé\r\nALFA;10;Société Générale\r\n"
    ).encode("cp1252")
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["source"]["encoding"] == "cp1252"


def test_un_csv_virgule_utf8_s_importe_aussi(
    client_synthetique, portefeuille_synthetique
):
    contenu = b"ticker,quantity\nALFA,10\nMIKE,20\n"
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["source"]["delimiter"] == ","
    assert reponse.json()["source"]["decimal_separator"] == "."
    assert reponse.json()["source"]["encoding"] == "utf-8"


def test_le_bom_est_signale_comme_tel_et_non_comme_utf8_nu(
    client_synthetique, portefeuille_synthetique
):
    """Annoncer « utf-8-sig » pour un fichier sans BOM serait une provenance fausse.

    D'où la recherche explicite de la marque d'octets plutôt qu'un
    `decode("utf-8-sig")` tenté en premier, qui réussit sur tout UTF-8 valide.
    """
    contenu = "ticker,quantity\nALFA,10\n".encode("utf-8-sig")
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["source"]["encoding"] == "utf-8-sig"


def test_le_bom_ne_corrompt_pas_le_nom_de_la_premiere_colonne(
    client_synthetique, portefeuille_synthetique
):
    """Sans retrait du BOM, l'en-tête vaudrait « ﻿ticker » et la colonne
    serait introuvable."""
    contenu = "ticker;quantity\nALFA;10\n".encode("utf-8-sig")
    assert depose(client_synthetique, portefeuille_synthetique, contenu).status_code == 200


def test_les_espaces_de_milliers_d_un_tableur_sont_admis(
    client_synthetique, portefeuille_synthetique
):
    """Espace fine insécable, insécable, ordinaire : trois façons d'écrire 1 500."""
    contenu = (
        "ticker;quantity\r\n"
        "ALFA;1 500\r\n"
        "MIKE;1 200\r\n"
        "ZULU;1 000\r\n"
    ).encode("utf-8")
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text

    lignes = {
        p["ticker"]: p["quantity"]
        for p in client_synthetique.get(
            f"/api/portfolios/{portefeuille_synthetique}"
        ).json()["valuation"]["positions"]
    }
    assert lignes == {"ALFA": 1500.0, "MIKE": 1200.0, "ZULU": 1000.0}


def test_le_nom_du_fichier_voyage_dans_la_reponse(
    client_synthetique, portefeuille_synthetique
):
    contenu = b"ticker;quantity\nALFA;10\n"
    reponse = depose(
        client_synthetique, portefeuille_synthetique, contenu, "portefeuille.csv"
    )
    assert reponse.json()["source"]["filename"] == "portefeuille.csv"


# ═══════════════════════════════════════════════════════════════ Refus ══


def test_un_ticker_inconnu_renvoie_4xx_avec_le_numero_de_ligne(
    client_synthetique, portefeuille_synthetique
):
    """Pas un 500, et pas « une erreur est survenue » : la ligne et la suite.

    Le numéro annoncé est celui du TABLEUR — en-tête compris. XYZ est sur la
    troisième ligne du fichier.
    """
    contenu = b"ticker;quantity\nALFA;10\nXYZ;5\n"
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)

    assert reponse.status_code == 422
    probleme = reponse.json()["problems"][0]
    assert probleme["line"] == 3
    assert probleme["value"] == "XYZ"
    assert "Ticker inconnu" in probleme["problem"]
    assert "python -m backend.ingestion add XYZ" in probleme["problem"]


def test_un_csv_fautif_n_ecrit_rien(
    client_synthetique, portefeuille_synthetique
):
    avant = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()["valuation"]["positions"]

    depose(
        client_synthetique,
        portefeuille_synthetique,
        b"ticker;quantity\nALFA;999\nXYZ;5\n",
    )

    apres = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}"
    ).json()["valuation"]["positions"]
    assert apres == avant


def test_une_quantite_negative_est_refusee_en_csv(
    client_synthetique, portefeuille_synthetique
):
    reponse = depose(
        client_synthetique, portefeuille_synthetique, b"ticker;quantity\nALFA;-5\n"
    )
    assert reponse.status_code == 422
    assert "nulle ou négative" in reponse.json()["problems"][0]["problem"]


def test_un_doublon_est_refuse_en_csv(
    client_synthetique, portefeuille_synthetique
):
    reponse = depose(
        client_synthetique,
        portefeuille_synthetique,
        b"ticker;quantity\nALFA;10\nALFA;5\n",
    )
    assert reponse.status_code == 422
    probleme = reponse.json()["problems"][0]
    assert "apparaît deux fois" in probleme["problem"]
    assert "ligne 2" in probleme["problem"]


def test_une_quantite_illisible_dit_quelle_decimale_etait_attendue(
    client_synthetique, portefeuille_synthetique
):
    reponse = depose(
        client_synthetique, portefeuille_synthetique, b"ticker;quantity\nALFA;dix\n"
    )
    assert reponse.status_code == 422
    probleme = reponse.json()["problems"][0]
    assert probleme["field"] == "quantity"
    assert "Décimale attendue" in probleme["problem"]


def test_un_en_tete_manquant_dit_ce_qui_etait_attendu(
    client_synthetique, portefeuille_synthetique
):
    reponse = depose(
        client_synthetique, portefeuille_synthetique, b"titre;nombre\nALFA;10\n"
    )
    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert "ticker" in detail
    assert "ticker;quantity[;cost_basis]" in detail


def test_un_fichier_sans_separateur_est_refuse(
    client_synthetique, portefeuille_synthetique
):
    reponse = depose(client_synthetique, portefeuille_synthetique, b"ticker\nALFA\n")
    assert reponse.status_code == 422
    assert "Aucun séparateur" in reponse.json()["detail"]


def test_un_fichier_vide_est_refuse(client_synthetique, portefeuille_synthetique):
    reponse = depose(client_synthetique, portefeuille_synthetique, b"")
    assert reponse.status_code == 422
    assert "vide" in reponse.json()["detail"].lower()


def test_un_fichier_trop_gros_est_refuse_sans_etre_charge(
    client_synthetique, portefeuille_synthetique
):
    """Un portefeuille fait quelques kilo-octets ; rien ne justifie d'accepter
    un fichier arbitraire en mémoire."""
    contenu = b"ticker;quantity\n" + (b"ALFA;1\n" * 200_000)
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 422
    assert "trop volumineux" in reponse.json()["detail"]


def test_les_lignes_vides_sont_ignorees_sans_bruit(
    client_synthetique, portefeuille_synthetique
):
    """Un tableur laisse volontiers une ligne vide en fin de fichier."""
    contenu = b"ticker;quantity\nALFA;10\n\nMIKE;20\n\n"
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["positions_count"] == 2


# ══════════════════════════════════════════════════ Le lecteur, isolément ══


def test_la_virgule_decimale_n_est_admise_qu_en_separateur_point_virgule():
    """`1,5` est un nombre avec `;`, et deux colonnes avec `,`.

    Accepter les deux sens du même caractère dans le même fichier rendrait la
    valeur indécidable ; le lecteur tranche par le séparateur de champs.
    """
    lecture = read(b"ticker;quantity\nALFA;1,5\n")
    assert lecture.positions[0].quantity == 1.5

    lecture = read(b"ticker,quantity\nALFA,1.5\n")
    assert lecture.positions[0].quantity == 1.5


def test_un_encodage_illisible_leve_une_erreur_explicite():
    with pytest.raises(CsvError, match="ni UTF-8 ni CP1252"):
        read(b"ticker;quantity\n\x81\x8d;10\n")
