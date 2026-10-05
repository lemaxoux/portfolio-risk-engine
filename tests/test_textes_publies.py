"""La ponctuation et les glyphes des textes que l'API publie.

Trois règles, vérifiées sur ce que le client REÇOIT, chaîne par chaîne, comme
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

═══ 3. AUCUN TIRET CADRATIN ═══

L'interface n'emploie aucun tiret cadratin (U+2014), ni dans ce que le client
compose, ni dans ce que l'API publie (DESIGN.md §6.3, décision du 2026-10-05).
Dans une phrase, la ponctuation dit le lien : deux-points, virgule,
parenthèses ou point. La règle n'a pas d'exception. Le tiret court (U+2013)
des paires comme « JNJ–KO », le signe moins (U+2212) et la flèche d'une
période (→) ne sont pas concernés.

Les réponses ne déclenchent pas toutes les phrases que le code sait écrire :
la règle est donc vérifiée une seconde fois sur le CODE qui publie, chaîne par
chaîne (`test_aucune_chaine_publiee_n_ecrit_de_tiret_cadratin`).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from backend.typography import NBSP

RACINE = Path(__file__).resolve().parents[1]

# Une espace ORDINAIRE (U+0020) avant « : », « ; », « ? » ou « ! » suivi d'un
# blanc ou de la fin, après « « », avant « » ». Le motif est celui de
# `typography.prose`.
ESPACE_ORDINAIRE = re.compile(r".{0,30}(?: [:;?!](?=\s|$)|« | »).{0,10}")

GREC = re.compile(f"[{chr(0x370)}-{chr(0x3FF)}]")

# Écrit par son point de code : ce fichier ne doit pas contenir, dans une
# chaîne, le caractère qu'il interdit.
CADRATIN = chr(0x2014)

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
        if CADRATIN in texte:
            fautes.append((chemin, f"tiret cadratin : {texte[:60]}"))
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


def test_la_garde_voit_un_tiret_cadratin_et_lui_seul():
    """Partout, provenance comprise : la règle n'a pas d'exception."""
    phrase = {"regimes": [{"summary": f"Krach COVID {CADRATIN} échantillon trop mince"}]}
    provenance = {"risk": {"volatility": {"detail": f"écart-type {CADRATIN} 504 séances"}}}
    assert fautes_dans(phrase)
    assert fautes_dans(provenance)
    # Le tiret court d'une paire, le signe moins et la flèche d'une période.
    legitimes = {"a": "corrélation JNJ–KO = 0,42", "b": "−3", "c": "2024-09-05 → 2026-09-09"}
    assert fautes_dans(legitimes) == []


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


# ------------------------------- Le code qui publie, chaîne par chaîne --
#
# Les réponses ci-dessus ne déclenchent pas toutes les phrases : une matrice
# singulière, une loi de Student sans variance finie, un seuil que le
# portefeuille de test n'atteint pas. La règle du tiret cadratin se lit donc
# aussi dans le code, sur chaque chaîne que le backend sait écrire.
#
# Trois choses ne sont pas des textes de l'interface, et ne sont pas lues :
# les docstrings ; la documentation OpenAPI (`DESCRIPTION` de l'application,
# `description=` d'un champ), que la page n'affiche jamais — la garde du
# client écarte de même `schema.ts`, qui la recopie ; et la commande
# d'ingestion, qui écrit son journal et son bilan dans un terminal.

HORS_INTERFACE = ("backend/ingestion/__main__.py", "backend/ingestion/prices.py")


def chaines_publiables(source: str) -> list[tuple[int, str]]:
    """Chaque chaîne d'un module, avec sa ligne, hors docstrings et hors
    documentation OpenAPI."""
    arbre = ast.parse(source)
    ecartees: set[int] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = noeud.body
            if corps and isinstance(corps[0], ast.Expr) and isinstance(corps[0].value, ast.Constant):
                ecartees.add(id(corps[0].value))
        elif isinstance(noeud, ast.keyword) and noeud.arg == "description":
            ecartees.update(id(n) for n in ast.walk(noeud.value))
        elif isinstance(noeud, ast.Assign) and any(
            isinstance(cible, ast.Name) and cible.id == "DESCRIPTION" for cible in noeud.targets
        ):
            ecartees.update(id(n) for n in ast.walk(noeud.value))
    return [
        (noeud.lineno, noeud.value)
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in ecartees
    ]


def test_le_balayage_du_code_voit_une_chaine_et_ecarte_ce_qui_n_est_pas_publie():
    temoin = (
        f'"""Docstring {CADRATIN} jamais publiée."""\n'
        f'DESCRIPTION = "API {CADRATIN} documentation"\n'
        f'champ = Field(description="un rang {CADRATIN} par exemple")\n'
        f'raison = f"Causes habituelles {CADRATIN} {{cause}}"\n'
    )
    fautives = [texte for _, texte in chaines_publiables(temoin) if CADRATIN in texte]
    assert fautives == [f"Causes habituelles {CADRATIN} "]


def test_aucune_chaine_publiee_n_ecrit_de_tiret_cadratin():
    fautes = []
    for chemin in sorted((RACINE / "backend").rglob("*.py")):
        relatif = chemin.relative_to(RACINE).as_posix()
        if relatif in HORS_INTERFACE:
            continue
        for ligne, texte in chaines_publiables(chemin.read_text(encoding="utf-8")):
            if CADRATIN in texte:
                fautes.append(f"{relatif}:{ligne} : {texte[:60]}")
    assert fautes == []
