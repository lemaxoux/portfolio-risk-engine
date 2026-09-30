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
    contenu = b"ticker,quantity\nALFA,10.5\nMIKE,20\n"
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


def test_une_colonne_en_trop_non_vide_est_refusee_avec_son_numero_de_ligne():
    """Avec `,` en séparateur, « 1,5 » est deux colonnes : 1 et 5. Le lecteur
    lisait la quantité 1 et ignorait le 5, sans rien dire — une lecture fausse
    et silencieuse. Une colonne en trop non vide est désormais refusée."""
    lecture = read(b"ticker,quantity\nALFA,10\nMIKE,1,5\n")
    (probleme,) = lecture.problems
    assert probleme.line == 3
    assert probleme.problem.startswith("3 colonnes lues, l'en-tête en a 2")
    assert "une virgule décimale coupe le nombre en deux" in probleme.problem
    assert [p.ticker for p in lecture.positions] == ["ALFA"]


def test_un_prix_de_revient_a_virgule_decimale_est_refuse_en_separateur_virgule():
    lecture = read(b"ticker,quantity,cost_basis\nALFA,10,185,20\n")
    (probleme,) = lecture.problems
    assert probleme.line == 2
    assert probleme.problem.startswith("4 colonnes lues, l'en-tête en a 3")
    assert "une virgule décimale coupe le nombre en deux" in probleme.problem


def test_une_colonne_en_trop_vide_est_toleree():
    """Un séparateur final, fréquent dans un export Excel, n'est pas une
    donnée : la colonne vide qui le suit est ignorée."""
    lecture = read(b"ticker,quantity\nALFA,15,\n")
    assert lecture.problems == ()
    assert lecture.positions[0].quantity == 15.0


def test_l_indice_de_virgule_decimale_ne_s_ajoute_que_s_il_a_un_sens():
    """Une colonne en trop qui n'est pas faite de chiffres, ou un séparateur
    `;`, ne vient pas d'une virgule décimale : le message s'en tient au
    décompte."""
    texte = read(b"ticker,quantity\nALFA,10,achat\n").problems[0].problem
    assert texte.startswith("3 colonnes lues, l'en-tête en a 2")
    assert "virgule décimale" not in texte

    point_virgule = read(b"ticker;quantity\nALFA;10;99\n").problems[0].problem
    assert point_virgule.startswith("3 colonnes lues, l'en-tête en a 2")
    assert "virgule décimale" not in point_virgule


def test_une_colonne_en_trop_n_ecrit_rien(client_synthetique, portefeuille_synthetique):
    """Tout ou rien, aussi quand le refus vient de la LECTURE et non de la
    validation : une seule ligne refusée, aucune position écrite."""
    avant = client_synthetique.get(f"/api/portfolios/{portefeuille_synthetique}").json()

    reponse = depose(
        client_synthetique,
        portefeuille_synthetique,
        b"ticker,quantity\nALFA,999\nMIKE,1,5\nZULU,7\n",
    )
    assert reponse.status_code == 422
    assert [p["line"] for p in reponse.json()["problems"]] == [3]

    apres = client_synthetique.get(f"/api/portfolios/{portefeuille_synthetique}").json()
    assert apres["positions"] == avant["positions"]
    assert apres["updated_at"] == avant["updated_at"]


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


def test_une_quantite_illisible_dit_quelle_decimale_est_acceptee(
    client_synthetique, portefeuille_synthetique
):
    """« Acceptée » et non « observée » : le message décrit la règle de lecture,
    qui est ce dont l'utilisateur a besoin pour corriger son fichier."""
    reponse = depose(
        client_synthetique, portefeuille_synthetique, b"ticker;quantity\nALFA;dix\n"
    )
    assert reponse.status_code == 422
    probleme = reponse.json()["problems"][0]
    assert probleme["field"] == "quantity"
    assert "Décimale acceptée : `,`" in probleme["problem"]


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


# ════════════════════════ Le séparateur décimal est OBSERVÉ, pas supposé ══
#
# Annoncer la RÈGLE DE LECTURE à la place de ce que contient le fichier serait
# une provenance fausse — la même faute que d'annoncer « utf-8-sig » pour un
# fichier sans marque d'octets. Avec `;`, la virgule est admise ; ce n'est pas
# une raison pour dire qu'elle a été rencontrée.


def test_un_fichier_point_virgule_a_decimales_point_annonce_le_point(
    client_synthetique, portefeuille_synthetique
):
    """Le cas qui rendait la provenance fausse : `;` en champs, `.` en décimale."""
    reponse = depose(
        client_synthetique, portefeuille_synthetique, b"ticker;quantity\nALFA;40.5\n"
    )
    assert reponse.status_code == 200, reponse.text
    source = reponse.json()["source"]
    assert source["delimiter"] == ";"
    assert source["decimal_separator"] == "."


def test_un_fichier_sans_aucune_decimale_l_annonce(
    client_synthetique, portefeuille_synthetique
):
    """Des quantités entières ne disent rien du séparateur décimal.

    `aucune` est une information : elle évite d'affirmer une convention que le
    fichier n'exerce nulle part.
    """
    reponse = depose(
        client_synthetique, portefeuille_synthetique, b"ticker;quantity\nALFA;40\n"
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["source"]["decimal_separator"] == "aucune"


def test_un_fichier_qui_melange_les_deux_ecritures_le_dit(
    client_synthetique, portefeuille_synthetique
):
    """`mixte` n'est pas une erreur : c'est la signature d'un assemblage à la
    main, et c'est utile à savoir devant un résultat inattendu."""
    contenu = b"ticker;quantity;cost_basis\nALFA;40,5;12.75\n"
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["source"]["decimal_separator"] == "mixte"


def test_le_prix_de_revient_compte_aussi_dans_ce_qui_est_observe(
    client_synthetique, portefeuille_synthetique
):
    """Une décimale peut n'apparaître que dans `cost_basis`."""
    contenu = b"ticker;quantity;cost_basis\nALFA;40;12,75\n"
    reponse = depose(client_synthetique, portefeuille_synthetique, contenu)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["source"]["decimal_separator"] == ","


# ══════════════════════════════════════════════════ Le lecteur, isolément ══


def test_la_virgule_decimale_n_est_admise_qu_en_separateur_point_virgule():
    """`1,5` est un nombre avec `;`, et deux colonnes avec `,`.

    Accepter les deux sens du même caractère dans le même fichier rendrait la
    valeur indécidable ; le lecteur tranche par le séparateur de champs.
    """
    lecture = read(b"ticker;quantity\nALFA;1,5\n")
    assert lecture.positions[0].quantity == 1.5
    assert lecture.source.decimal_separator == ","

    lecture = read(b"ticker,quantity\nALFA,1.5\n")
    assert lecture.positions[0].quantity == 1.5
    assert lecture.source.decimal_separator == "."


def test_un_encodage_illisible_leve_une_erreur_explicite():
    with pytest.raises(CsvError, match="ni UTF-8 ni CP1252"):
        read(b"ticker;quantity\n\x81\x8d;10\n")


# ═══════════════════════════════════════════════════════ Le format publié ══
#
# `GET /api/csv-format` publie ce que le lecteur accepte, pour que l'écran
# d'import l'affiche sans en garder une copie : une copie embarquée dans le
# bundle deviendrait le format affiché le jour où le lecteur changerait. Ces
# tests ne comparent pas la réponse à des constantes recopiées : ils font lire
# au VRAI lecteur ce que la réponse annonce.


@pytest.fixture
def format_publie(client_synthetique):
    reponse = client_synthetique.get("/api/csv-format")
    assert reponse.status_code == 200, reponse.text
    return reponse.json()


def test_le_format_publie_nomme_les_colonnes_et_les_limites(format_publie):
    from backend.api.csv_import import MAX_BYTES
    from backend.api.validation import MAX_POSITIONS

    assert format_publie["required_columns"] == ["ticker", "quantity"]
    assert format_publie["optional_columns"] == ["cost_basis"]
    assert format_publie["max_bytes"] == MAX_BYTES
    assert format_publie["max_positions"] == MAX_POSITIONS


def test_l_exemple_publie_est_lu_par_le_vrai_lecteur(format_publie):
    lecture = read(format_publie["example"].encode("utf-8"))
    assert lecture.problems == ()
    assert [(p.ticker, p.quantity, p.cost_basis) for p in lecture.positions] == [
        ("AAPL", 40.0, 185.2),
        ("MSFT", 25.0, None),
    ]
    # L'exemple montre ce qu'exporte un Excel français : point-virgule,
    # virgule décimale, prix de revient laissé vide.
    assert lecture.source.delimiter == ";"
    assert lecture.source.decimal_separator == ","


def test_l_exemple_publie_s_importe_sur_la_copie_figee(base_figee, client_factory):
    """Bout à bout, sur de vrais titres : la copie figée propre au test."""
    with client_factory(base_figee) as client:
        identifiant = client.post("/api/portfolios", json={"name": "Exemple"}).json()["id"]
        exemple = client.get("/api/csv-format").json()["example"]
        reponse = depose(client, identifiant, exemple.encode("utf-8"), "exemple.csv")
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["positions_count"] == 2


def test_chaque_separateur_et_chaque_decimale_publies_sont_lus(format_publie):
    regles = format_publie["delimiters"]
    assert {r["delimiter"] for r in regles} == {";", ","}
    for regle in regles:
        separateur = regle["delimiter"]
        for decimale in regle["decimal_separators"]:
            lecture = read(
                f"ticker{separateur}quantity\nALFA{separateur}1{decimale}5\n".encode()
            )
            assert lecture.problems == (), (separateur, decimale)
            assert lecture.positions[0].quantity == 1.5, (separateur, decimale)


def test_chaque_espace_de_milliers_publiee_est_lue(format_publie):
    espaces = format_publie["thousands_separators"]
    assert espaces, "au moins l'espace ordinaire"
    for espace in espaces:
        lecture = read(f"ticker;quantity\nALFA;1{espace}000\n".encode("utf-8"))
        assert lecture.positions[0].quantity == 1000.0, repr(espace)


def test_chaque_encodage_publie_est_reconnu_et_annonce(format_publie):
    for encodage in format_publie["encodings"]:
        lecture = read("ticker;quantity\nÉLAN;10\n".encode(encodage))
        assert lecture.source.encoding == encodage, encodage


def test_l_en_tete_attendu_publie_est_celui_des_messages_de_refus(format_publie):
    with pytest.raises(CsvError) as refus:
        read(b"ticker;quantite\nALFA;10\n")
    assert format_publie["expected_header"] in str(refus.value)
