"""La ponctuation et les glyphes des textes que l'API publie.

Deux règles, vérifiées sur ce que le client REÇOIT, chaîne par chaîne, comme
`test_nombres_publies.py` le fait pour les nombres :

═══ 1. AUCUNE ESPACE ORDINAIRE AVANT « : », « ; », « ? », « ! » NI DANS LES
GUILLEMETS ═══

Avec une espace ordinaire, le signe ou le guillemet fermant part seul en début
de ligne : « Colonnes obligatoires » finissait une ligne que « : ticker »
commençait (captures 7B.3a). L'espace y est insécable, U+00A0, posée à la
publication par `typography.prose` sur chaque champ de texte rédigé
(`api.schemas.Texte`) et sur les corps d'erreur.

═══ 2. AUCUNE LETTRE GRECQUE HORS DE LA PROVENANCE ═══

Les phrases du moteur s'affichent en Spectral, qui n'a aucun glyphe grec : un
« ν » y passe dans une police de repli, où il se lit « v » (capture 15). La
provenance — `method` et `detail` d'une mesure : « ν = 4,07 », « μ = 0 »,
« λ=0,94 » — s'affiche en IBM Plex Sans, qui a le grec : elle seule en garde.
"""

from __future__ import annotations

import re

import pytest

from backend.typography import NBSP

# Une espace ORDINAIRE (U+0020) avant « : », « ; », « ? » ou « ! » suivi d'un
# blanc ou de la fin, après « « », avant « » ». Le motif est celui de
# `typography.prose`.
ESPACE_ORDINAIRE = re.compile(r".{0,30}(?: [:;?!](?=\s|$)|« | »).{0,10}")

GREC = re.compile(f"[{chr(0x370)}-{chr(0x3FF)}]")

# La provenance d'une mesure : écrite en Plex Sans, qui a le grec.
PROVENANCE = re.compile(r"\.risk\..*\.(method|detail)$")


def toutes_les_chaines(noeud, chemin=""):
    """Chaque chaîne d'une réponse, avec son chemin — pour nommer la fautive."""
    if isinstance(noeud, str):
        yield chemin, noeud
    elif isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield from toutes_les_chaines(valeur, f"{chemin}.{cle}")
    elif isinstance(noeud, list):
        for rang, valeur in enumerate(noeud):
            yield from toutes_les_chaines(valeur, f"{chemin}[{rang}]")


def fautes_dans(corps) -> list[tuple[str, str]]:
    fautes = []
    for chemin, texte in toutes_les_chaines(corps):
        fautes += [(chemin, extrait) for extrait in ESPACE_ORDINAIRE.findall(texte)]
        if GREC.search(texte) and not PROVENANCE.search(chemin):
            fautes.append((chemin, f"lettre grecque : {texte[:60]}"))
    return fautes


# ------------------------------------------------ Témoins de la garde --

TEMOINS_FAUTIFS = (
    ("deux-points", "Ticker inconnu : XYZ."),
    ("deux-points final", "L'API ne répond pas. La démarrer :"),
    ("entre parenthèses", "Au moins 30 (reçu : 7)."),
    ("guillemet ouvrant", "le séparateur « ;" + NBSP + "»"),
    ("guillemet fermant", "le séparateur «" + NBSP + "; »"),
    ("point-virgule", "valorisation au 2026-09-09 ; risque"),
    ("point d'interrogation", "Supprimer ce portefeuille ? Ses lignes"),
    ("point d'exclamation", "Attention !"),
)

TEMOINS_LEGITIMES = (
    ("deux-points insécable", "Ticker inconnu" + NBSP + ": XYZ."),
    ("heure", "à 10:30"),
    ("adresse", "http://127.0.0.1:8001"),
    ("guillemets insécables", "«" + NBSP + "Démo" + NBSP + "»"),
    ("formule sans deux-points", "échelle S = Σ·(ν−2)/ν"),
    ("point-virgule insécable", "valorisation" + NBSP + "; risque"),
    ("question insécable", "Supprimer ce portefeuille" + NBSP + "?"),
    ("opérateur", "si x != y"),
)


@pytest.mark.parametrize("libelle, texte", TEMOINS_FAUTIFS, ids=[t[0] for t in TEMOINS_FAUTIFS])
def test_la_garde_voit_une_espace_ordinaire(libelle, texte):
    """Témoins POSITIFS : une garde qu'on n'a jamais vue échouer ne prouve rien."""
    assert ESPACE_ORDINAIRE.findall(texte), texte


@pytest.mark.parametrize(
    "libelle, texte", TEMOINS_LEGITIMES, ids=[t[0] for t in TEMOINS_LEGITIMES]
)
def test_la_garde_laisse_passer_la_ponctuation_juste(libelle, texte):
    assert ESPACE_ORDINAIRE.findall(texte) == [], texte


def test_la_garde_voit_une_lettre_grecque_hors_de_la_provenance():
    phrase = {"risk": {"tail_risk": {"student_unavailable_reason": "estimer ν"}}}
    provenance = {"risk": {"tail_risk": {"levels": [{"student_parametric_var": {"detail": "ν = 4,07"}}]}}}
    assert fautes_dans(phrase)
    assert fautes_dans(provenance) == []


# ------------------------------------------- Les réponses de l'API --


def _verifier(corps, origine: str) -> None:
    fautes = fautes_dans(corps)
    assert not fautes, f"{origine} : {len(fautes)} faute(s) : {fautes[:5]}"


def test_la_reponse_reelle(analyse_reelle):
    _verifier(analyse_reelle.json(), "démonstration, 504 séances")


def test_un_portefeuille_synthetique(client_synthetique, portefeuille_synthetique):
    """Scénarios sans ligne couverte, régimes refusés, raisons d'indisponibilité."""
    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    )
    assert reponse.status_code == 200, reponse.text
    _verifier(reponse.json(), "synthétique, 250 séances")


@pytest.mark.parametrize("seances_courtes", [3, 8, 40])
def test_une_fenetre_reduite(analyse_historique_court, seances_courtes):
    """Refus sous trois séances, réserves d'estimation mince sous trente, refus
    de la Student, seuils choisis : les phrases que la démonstration ne
    déclenche jamais."""
    reponse = analyse_historique_court(seances_courtes)
    assert reponse.status_code == 200, reponse.text
    _verifier(reponse.json(), f"{seances_courtes} cotations")


@pytest.mark.parametrize(
    "chemin",
    ["/api/meta", "/api/disclaimer", "/api/portfolios", "/api/csv-format", "/api/securities"],
)
def test_le_catalogue_et_le_bandeau(client_synthetique, portefeuille_synthetique, chemin):
    reponse = client_synthetique.get(chemin)
    assert reponse.status_code == 200, (chemin, reponse.text)
    _verifier(reponse.json(), chemin)


def test_les_corps_d_erreur(client_synthetique, portefeuille_synthetique):
    """404, 409, 422 de validation et 422 d'import : un seul format de corps,
    une seule convention."""
    base = f"/api/portfolios/{portefeuille_synthetique}"
    reponses = {
        "404": client_synthetique.get("/api/portfolios/999999/analysis"),
        "409 indice absent": client_synthetique.get(
            f"{base}/analysis", params={"window": 250, "benchmark": "absent"}
        ),
        "422 positions": client_synthetique.put(
            f"{base}/positions",
            json={"positions": [{"ticker": "XYZ", "quantity": 1}, {"ticker": "MIKE", "quantity": -3}]},
        ),
        "422 CSV": client_synthetique.post(
            f"{base}/positions/csv",
            files={"file": ("f.csv", b"ticker,quantity\nMIKE,1,5\n", "text/csv")},
        ),
        "422 quantité illisible": client_synthetique.post(
            f"{base}/positions/csv",
            files={"file": ("f.csv", b"ticker;quantity\nMIKE;dix\n", "text/csv")},
        ),
        "422 encodage": client_synthetique.post(
            f"{base}/positions/csv", files={"file": ("f.csv", ENCODAGE_ILLISIBLE, "text/csv")}
        ),
    }
    for origine, reponse in reponses.items():
        assert reponse.status_code == int(origine[:3]), (origine, reponse.text)
        _verifier(reponse.json(), origine)


def test_sous_deux_rendements_le_409_aussi(analyse_historique_court):
    reponse = analyse_historique_court(2)
    assert reponse.status_code == 409, reponse.text
    _verifier(reponse.json(), "409, deux cotations")


# 0x81 n'est ni de l'UTF-8 seul ni un caractère de CP1252 : le lecteur refuse
# le fichier, et sa phrase est la seule publiée qui cite entre guillemets.
ENCODAGE_ILLISIBLE = b"ticker;quantity\nMIKE;1" + bytes([0x81]) + b"\n"


def test_la_garde_mord_sur_de_vraies_reponses(
    analyse_reelle, client_synthetique, portefeuille_synthetique
):
    """Contrôle en sens inverse : les réponses CONTIENNENT bien des
    deux-points et des guillemets, à espace insécable. Sans eux, la garde
    vérifierait une absence vide."""
    textes = [t for _, t in toutes_les_chaines(analyse_reelle.json())]
    assert any(NBSP + ":" in t for t in textes)
    assert any(NBSP + ";" in t for t in textes)

    refus = client_synthetique.post(
        f"/api/portfolios/{portefeuille_synthetique}/positions/csv",
        files={"file": ("f.csv", ENCODAGE_ILLISIBLE, "text/csv")},
    ).json()["detail"]
    assert "«" + NBSP + "CSV UTF-8" + NBSP + "»" in refus, refus
