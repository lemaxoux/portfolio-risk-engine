"""La ponctuation et les glyphes des textes que l'API publie.

Six règles, vérifiées sur ce que le client REÇOIT, chaîne par chaîne, comme
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

═══ 4. UNE PAIRE NE SE COUPE PAS AU TIRET ═══

Une coupure de ligne est permise juste après un tiret court : « La paire la
plus liée est JNJ– » finissait une ligne que « KO, à 0,42. » commençait
(captures du 2026-10-05). `typography.prose` pose donc, à la publication, un
caractère de liaison invisible (U+2060) après le tiret court d'une paire. Ne
sont pas de la prose, et gardent la paire nue : les faits d'une observation
(`facts`, des données) et son sujet (`subject`, que la page affiche sur une
seule ligne).

═══ 5. UNE DURÉE NE SE SÉPARE PAS DE SON UNITÉ, NI UN JOUR DE SON MOIS ═══

« soit environ 2 » finissait une ligne que « ans. » commençait, sur l'écran
d'acceptation, et « (3 » une ligne que « janvier 2022) » commençait, dans la
description d'une crise (captures du 2026-10-05, à 390 px). L'espace y est
insécable, U+00A0 : `typography.counted` lie un nombre au mot qu'il compte,
`typography.long_date` le jour, le mois et l'année. Les séances, les lignes et
les points sont surveillés de la même façon par `test_api_analysis.py`.

═══ 6. UNE DATE NE SE COUPE PAS AU TRAIT D'UNION ═══

Une coupure de ligne est permise après le trait d'union d'une date ISO :
« valorisation au 2026-09- » finissait une ligne que « 25 » commençait, sous
« Détails du calcul » d'une observation (captures du 2026-10-05, à 390 px).
`typography.prose` pose donc le caractère de liaison (U+2060) après chaque
trait d'union d'une date citée dans un texte rédigé. Un champ qui n'est
qu'une date (`as_of`, `start`, `end`, la date d'une séance) est une donnée :
il reste nu, comme les faits et le sujet d'une observation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.typography import NBSP, WORD_JOINER, prose

from .gardes_texte import (
    CADRATIN,
    DATE_NUE,
    ESPACE_ORDINAIRE,
    GENERALITES,
    GREC,
    HORS_PROSE,
    LIEN_SECABLE,
    PAIRE_SECABLE,
    PROVENANCE,
    TIRET_COURT,
    chaines_publiables,
    dates_secables,
    toutes_les_chaines,
)

RACINE = Path(__file__).resolve().parents[1]

# Une période telle que `prose` la publie.
PERIODE_LIEE = f"2024-{WORD_JOINER}09-{WORD_JOINER}05 → 2026-{WORD_JOINER}09-{WORD_JOINER}09"


def fautes_dans(corps) -> list[tuple[str, str]]:
    fautes = []
    for chemin, texte in toutes_les_chaines(corps):
        fautes += [(chemin, extrait) for extrait in ESPACE_ORDINAIRE.findall(texte)]
        if GREC.search(texte) and not PROVENANCE.search(chemin):
            fautes.append((chemin, f"lettre grecque : {texte[:60]}"))
        if CADRATIN in texte:
            fautes.append((chemin, f"tiret cadratin : {texte[:60]}"))
        if PAIRE_SECABLE.search(texte) and not HORS_PROSE.search(chemin):
            fautes.append((chemin, f"paire sécable : {texte[:60]}"))
        fautes += [(chemin, f"lien sécable : {extrait}") for extrait in LIEN_SECABLE.findall(texte)]
        if not DATE_NUE.match(texte) and not HORS_PROSE.search(chemin):
            fautes += [(chemin, f"date sécable : {date}") for date in dates_secables(texte)]
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
    legitimes = {
        "a": f"corrélation JNJ{TIRET_COURT}{WORD_JOINER}KO = 0,42",
        "b": "−3",
        "c": PERIODE_LIEE,
    }
    assert fautes_dans(legitimes) == []


def test_la_garde_voit_une_paire_secable_dans_la_prose_seulement():
    paire = f"JNJ{TIRET_COURT}KO"
    phrase = {"observations": [{"statement": f"La paire la plus liée est {paire}, à 0,42."}]}
    assert fautes_dans(phrase)
    # Publiée par `prose`, la même phrase passe : le caractère de liaison y est.
    publiee = {"observations": [{"statement": prose(f"La paire la plus liée est {paire}, à 0,42.")}]}
    assert fautes_dans(publiee) == []
    assert f"JNJ{TIRET_COURT}{WORD_JOINER}KO" in publiee["observations"][0]["statement"]
    # Un fait et un sujet ne sont pas de la prose : la paire y reste nue.
    donnees = {"observations": [{"subject": paire, "facts": {"paire": paire}}]}
    assert fautes_dans(donnees) == []
    # Un tiret entouré d'espaces n'est pas une paire.
    assert fautes_dans({"a": f"calme {TIRET_COURT} crise"}) == []


def test_la_garde_voit_une_date_secable_dans_la_prose_seulement():
    phrase = f"capital{NBSP}: valorisation au 2026-09-25{NBSP}; risque"
    assert fautes_dans({"observations": [{"provenance": phrase}]})
    # Publiée par `prose`, la même phrase passe : les deux traits sont liés.
    publiee = prose(phrase)
    assert fautes_dans({"observations": [{"provenance": publiee}]}) == []
    assert f"au 2026-{WORD_JOINER}09-{WORD_JOINER}25{NBSP};" in publiee
    # Un seul trait lié sur les deux : encore sécable.
    assert fautes_dans({"a": f"au 2026-{WORD_JOINER}09-25"})
    # Une date nue est une donnée : elle reste sans liaison.
    donnees = {"as_of": "2026-09-25", "window": {"start": "2024-09-05", "end": "2026-09-09"}}
    assert fautes_dans(donnees) == []


def test_prose_lie_la_paire_une_seule_fois_et_ne_touche_a_rien_d_autre():
    paire = f"JNJ{TIRET_COURT}KO"
    une_fois = prose(f"corrélation {paire} = 0,42")
    assert une_fois == f"corrélation JNJ{TIRET_COURT}{WORD_JOINER}KO = 0,42"
    assert prose(une_fois) == une_fois, "appliquée deux fois, elle n'ajoute rien"
    # Seul un caractère invisible est ajouté : les caractères visibles sont les mêmes.
    assert une_fois.replace(WORD_JOINER, "") == f"corrélation {paire} = 0,42"
    for intact in ("−3", f"calme {TIRET_COURT} crise", "10:30"):
        assert prose(intact) == intact


def test_prose_lie_la_date_une_seule_fois_et_ne_touche_a_rien_d_autre():
    periode = "2024-09-05 → 2026-09-09"
    une_fois = prose(periode)
    assert une_fois == PERIODE_LIEE
    assert prose(une_fois) == une_fois, "appliquée deux fois, elle n'ajoute rien"
    assert une_fois.replace(WORD_JOINER, "") == periode
    # Ni un nombre, ni un mois, ni un intervalle d'années, ni un identifiant.
    for intact in ("2026", "100 000", "2024-09", "de 2007-2009", "01-02-03", "FR0000120271"):
        assert prose(intact) == intact


def test_la_garde_voit_une_duree_separee_de_son_unite_et_un_jour_de_son_mois():
    fautifs = (
        "soit environ 2 ans.",
        "depuis 6 mois",
        "sur 7 jours de bourse",
        "(3 janvier 2022)",
        f"(3{NBSP}janvier 2022)",
        f"(3 janvier{NBSP}2022)",
    )
    for fautif in fautifs:
        assert fautes_dans({"a": fautif}), fautif
    legitimes = (
        f"soit environ 2{NBSP}ans.",
        f"(3{NBSP}janvier{NBSP}2022)",
        "il en faut au moins 20 pour ce calcul",
        "pendant la Crise financière 2008 et le Krach COVID",
        "0,50 en régime calme, mais 0,86 en crise",
        PERIODE_LIEE,
    )
    for legitime in legitimes:
        assert fautes_dans({"a": legitime}) == [], legitime


def test_les_durees_et_les_dates_en_lettres_publiees_sont_liees(analyse_reelle):
    """Contrôle en sens inverse : la réponse CONTIENT une durée et des dates en
    toutes lettres, liées par des espaces insécables."""
    textes = [t for _, t in toutes_les_chaines(analyse_reelle.json())]
    assert any(f"soit environ 2{NBSP}ans" in t for t in textes)
    assert any(f"(3{NBSP}janvier{NBSP}2022)" in t for t in textes)
    assert any(f"(9{NBSP}mars{NBSP}2009)" in t for t in textes)


def test_les_dates_iso_citees_dans_la_prose_sont_liees(analyse_reelle):
    """Contrôle en sens inverse : la provenance d'une observation CITE la date
    de valorisation et la période d'estimation, traits d'union liés."""
    textes = [t for _, t in toutes_les_chaines(analyse_reelle.json())]
    assert any(f"valorisation au 2026-{WORD_JOINER}09-{WORD_JOINER}09" in t for t in textes)
    assert any(PERIODE_LIEE in t for t in textes)


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
    # La paire la plus liée du portefeuille de démonstration, liée par U+2060.
    assert any(f"JNJ{TIRET_COURT}{WORD_JOINER}KO" in t for t in textes)

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


def test_aucune_chaine_publiee_n_affirme_le_sens_d_une_couverture_partielle():
    """« En moyenne plus spéculative », « probablement sous-estimée » : le
    moteur ne mesure ni l'un ni l'autre. Une couverture partielle dit
    seulement que la perte de l'ensemble a pu être différente (textes de
    lecture, 2026-10-05)."""
    interdits = GENERALITES
    fautes = []
    for chemin in sorted((RACINE / "backend").rglob("*.py")):
        relatif = chemin.relative_to(RACINE).as_posix()
        if relatif in HORS_INTERFACE:
            continue
        for ligne, texte in chaines_publiables(chemin.read_text(encoding="utf-8")):
            if any(interdit in texte for interdit in interdits):
                fautes.append(f"{relatif}:{ligne} : {texte[:60]}")
    assert fautes == []
