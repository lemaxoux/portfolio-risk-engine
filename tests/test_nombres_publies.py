"""Aucun nombre à point décimal dans un texte que l'API publie.

Le backend RÉDIGE des phrases : `summary` des scénarios et des régimes,
`detail` d'une VaR, `method` d'une volatilité, raisons de refus, observations
du moteur de règles. Le frontend les affiche TELLES QUELLES, à côté de nombres
qu'il formate lui-même en « 4,07 ». Une phrase qui écrit « ν = 4.07 » crée
donc deux conventions dans la même page — c'est arrivé : la provenance de la
VaR Student affichait « ν = 4.07 (MLE sur 504 séances) » juste au-dessus de
« ν ajusté 4,07 ».

═══ POURQUOI UNE GARDE DÉDIÉE, ET POURQUOI SUR LA RÉPONSE ═══

Aucune des gardes existantes ne pouvait le voir, chacune pour une raison qui
tient à ce qu'elle inspecte :

* `test_api_discipline.py` lit l'arbre syntaxique de `backend/api/` et y
  interdit l'ARITHMÉTIQUE. Les phrases fautives sont rédigées dans
  `backend/risk_engine/engine.py` et relayées mot pour mot par l'API — qui ne
  doit justement pas y toucher. Étendue au moteur, une garde sur l'arbre ne
  verrait pas davantage `f"EWMA (λ={lam})"`, qui n'a aucun format explicite :
  c'est le `str()` d'un flottant qui écrit le point.
* `test_typographie_partagee.py` compare le VOCABULAIRE déclaré des deux
  moitiés — espaces, seuil de groupement, accord du pluriel. Il ne vérifie pas
  que ce vocabulaire est EMPLOYÉ, et `typography.py` n'avait pas de formateur
  décimal : il n'y avait rien à comparer.
* les sondes typographiques de `test_api_analysis.py` lisent bien la réponse
  réelle, mais n'y cherchent que des ESPACES sécables. « 4.07 » n'a pas
  d'espace.
* `tokens.test.ts` inspecte le code du frontend, pas les données qu'il reçoit.

La garde porte donc sur ce que le client reçoit : chaque chaîne de chaque
réponse, où qu'elle ait été rédigée. Elle ne dépend pas de la façon dont le
nombre a été écrit — format explicite, `str()`, concaténation.

Seule la PROSE est concernée. Un message d'erreur qui montre un littéral à
recopier (« MX_RISK_FREE_RATE=0.035 ») garde son point : c'est du code.
Aucun de ces messages ne sort dans une réponse 200.
"""

from __future__ import annotations

import re
import sys

import pytest

from backend import typography
from backend.risk_engine import var

# Un chiffre, un point, un chiffre : « 4.07 », « -43.9 ». Ni une date ISO
# (tirets), ni « BRK.B » (lettres), ni « backend.ingestion » (lettres).
POINT_DECIMAL = re.compile(r".{0,40}\d\.\d.{0,10}")

# Un trait d'union qui sert de signe moins : précédé d'un blanc, d'une
# parenthèse ou du début de chaîne, suivi d'un chiffre. Le tiret d'une date
# (« 2024-09-05 ») suit un chiffre et n'est pas pris.
TRAIT_D_UNION_SIGNE = re.compile(r".{0,40}(?<![\w−-])-\d.{0,10}")


def fautes_de(texte: str) -> list[str]:
    """Extraits fautifs d'un texte. Liste vide s'il suit la convention."""
    return POINT_DECIMAL.findall(texte) + TRAIT_D_UNION_SIGNE.findall(texte)


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
    return [
        (chemin, extrait)
        for chemin, texte in toutes_les_chaines(corps)
        for extrait in fautes_de(texte)
    ]


# ------------------------------------------------ Témoins de la garde --

TEMOINS_FAUTIFS = (
    ("ν au point", "ν = 4.07 (MLE sur 504 séances)"),
    ("paramètre sans format", "EWMA (λ=0.94)"),
    ("pourcentage au point", "Krach COVID : -35.6 % de bout en bout"),
    ("écart signé", "en crise (+0.36)"),
    ("signe en trait d'union", "écart -7 pts"),
    ("signe entre parenthèses", "variation (-2 pts)"),
)

TEMOINS_LEGITIMES = (
    ("date ISO", "fenêtre 2024-09-05 → 2026-09-09"),
    ("ticker à point", "BRK.B et BF.B"),
    ("commande", "Lancer : python -m backend.ingestion add SPY"),
    ("formule", "échelle S = Σ·(ν−2)/ν, n − 2 degrés de liberté"),
    ("écriture française", "ν = 4,07 ; −43,9 % ; +0,36 ; 83 185,85"),
    ("paire de tickers", "JPM–KO"),
)


@pytest.mark.parametrize(
    "libelle, texte", TEMOINS_FAUTIFS, ids=[t[0] for t in TEMOINS_FAUTIFS]
)
def test_la_garde_voit_un_nombre_mal_ecrit(libelle, texte):
    """Témoins POSITIFS : une garde qu'on n'a jamais vue échouer ne prouve rien."""
    assert fautes_de(texte), texte


@pytest.mark.parametrize(
    "libelle, texte", TEMOINS_LEGITIMES, ids=[t[0] for t in TEMOINS_LEGITIMES]
)
def test_la_garde_laisse_passer_le_texte_legitime(libelle, texte):
    """Témoins NÉGATIFS : une garde qui se déclenche sur une date ISO serait
    désactivée dans la semaine."""
    assert fautes_de(texte) == [], texte


# ------------------------------------------- Les réponses de l'API --


def test_la_reponse_reelle_n_ecrit_aucun_nombre_au_point(analyse_reelle):
    """Le portefeuille de démonstration, sur les vraies séries.

    C'est la réponse où « ν = 4.07 » a été vu : volet Student ajusté, trois
    scénarios rejoués, trois comparaisons de régimes.
    """
    fautes = fautes_dans(analyse_reelle.json())
    assert not fautes, f"{len(fautes)} nombre(s) mal écrit(s) : {fautes[:5]}"


def test_la_reponse_reelle_ecrit_bien_des_decimales_a_la_virgule(analyse_reelle):
    """Contrôle en sens inverse : la garde vérifie une ABSENCE. Elle passerait
    sur une réponse qui n'écrirait aucun nombre décimal — celle-ci en écrit, et
    aux endroits où le point était apparu."""
    corps = analyse_reelle.json()
    detail = corps["risk"]["tail_risk"]["levels"][0]["student_parametric_var"]["detail"]
    assert re.search(r"ν = \d+,\d\d ", detail), detail
    assert re.search(r"λ=0,\d+", corps["risk"]["ewma_volatility"]["method"])
    for scenario in corps["scenarios"]:
        assert re.search(r"−\d+,\d %", scenario["summary"]), scenario["summary"]


def test_un_portefeuille_synthetique_n_ecrit_aucun_nombre_au_point(
    client_synthetique, portefeuille_synthetique
):
    """Autres chemins de rédaction : scénarios sans aucune ligne couverte (les
    séries commencent en 2024), raisons d'indisponibilité, régimes refusés."""
    reponse = client_synthetique.get(
        f"/api/portfolios/{portefeuille_synthetique}/analysis?window=250"
    )
    assert reponse.status_code == 200, reponse.text
    fautes = fautes_dans(reponse.json())
    assert not fautes, f"{len(fautes)} nombre(s) mal écrit(s) : {fautes[:5]}"


@pytest.mark.parametrize("seances_courtes", [3, 40])
def test_une_fenetre_reduite_n_ecrit_aucun_nombre_au_point(
    analyse_historique_court, seances_courtes
):
    """Fenêtre réduite par une ligne récente : refus sous trois séances, seuils
    choisis et mentions d'échantillon mince au-dessus. Ce sont les phrases que
    le portefeuille de démonstration ne déclenche jamais."""
    reponse = analyse_historique_court(seances_courtes)
    assert reponse.status_code == 200, reponse.text
    fautes = fautes_dans(reponse.json())
    assert not fautes, f"{len(fautes)} nombre(s) mal écrit(s) : {fautes[:5]}"


def test_le_catalogue_et_le_bandeau_n_ecrivent_aucun_nombre_au_point(
    client_synthetique, portefeuille_synthetique
):
    for chemin in ("/api/meta", "/api/disclaimer", "/api/portfolios"):
        reponse = client_synthetique.get(chemin)
        assert reponse.status_code == 200, (chemin, reponse.text)
        fautes = fautes_dans(reponse.json())
        assert not fautes, (chemin, fautes[:5])


def test_le_refus_de_student_ecrit_nu_a_la_virgule():
    """ν ≤ 2 : la raison du refus est publiée telle quelle dans
    `student_unavailable_reason`, dans une réponse 200. Aucune base réelle ne la
    déclenche aujourd'hui ; elle est donc vérifiée à la source."""
    with pytest.raises(ValueError) as refus:
        var.student_t_var(0.01, 1.9, 0.95)
    message = str(refus.value)
    assert message.startswith("Degrés de liberté ν = 1,900 ≤ 2")
    assert fautes_de(message) == []


# ------------------------------------------------- Les formateurs --


def test_number_ecrit_la_virgule_et_le_vrai_signe_moins():
    assert typography.number(4.0731, 2) == "4,07"
    assert typography.number(-0.36, 2) == "−0,36"
    assert typography.number(0.36, 2, signed=True) == "+0,36"
    assert typography.number(83185.85, 2) == "83 185,85"


def test_une_valeur_qui_s_arrondit_a_zero_ne_porte_pas_de_signe():
    """« −0,00 » se lirait comme une perte alors que le chiffre dit qu'il n'y
    en a pas — même règle que `format.ts`."""
    assert typography.number(-0.004, 2) == "0,00"
    assert typography.number(0.004, 2, signed=True) == "0,00"


def test_percent_et_points():
    assert typography.percent(-0.439, 1) == "−43,9 %"
    assert typography.percent(-0.088, 1, signed=True) == "−8,8 %"
    assert typography.percent(0.8, 1, trim=True) == "80 %"
    assert typography.percent(0.256, 1, trim=True) == "25,6 %"
    assert typography.signed_points(-0.074) == "−7,4 pts"
    assert typography.signed_points(0.098) == "+9,8 pts"


def test_exact_cite_un_nombre_saisi_tel_que_l_utilisateur_l_a_tape():
    """« Quantité nulle ou négative pour MSFT (−3) » : ni « (-3.0) », qui
    est l'écriture de Python, ni une décimale perdue ou inventée."""
    assert typography.exact(-3.0) == "\u22123"
    assert typography.exact(2.5) == "2,5"
    assert typography.exact(0.1) == "0,1"
    assert typography.exact(-0.25) == "\u22120,25"
    assert typography.exact(1e-07) == "0,0000001"
    assert typography.exact(123456.789) == "123\u202f456,789"
    assert typography.exact(0.0) == "0"
    with pytest.raises(ValueError):
        typography.exact(float("nan"))


def test_compact_cite_un_parametre_sans_decimales_inventees():
    assert typography.compact(0.94) == "0,94"
    assert typography.compact(60.0) == "60"
    assert typography.compact(-0.5) == "−0,5"


def test_un_nombre_non_fini_n_est_jamais_ecrit():
    for valeur in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            typography.number(valeur, 2)
        with pytest.raises(ValueError):
            typography.compact(valeur)


@pytest.mark.parametrize(
    "valeur",
    [
        # ν de Student relevés sur historique court, qui faisaient tomber
        # l'analyse en 500 : au-delà de 28 chiffres, `quantize` levait.
        3.5730354042096355e27,
        2.0602619888175704e31,
        6.006274911096697e15,
        1e300,
        sys.float_info.max,
        -sys.float_info.max,
    ],
)
def test_tout_nombre_fini_s_ecrit_sans_exception(valeur):
    """Quel que soit le nombre, s'il est fini, il s'écrit — et juste.

    Ces flottants sont tous des entiers : leur écriture exacte, relue, rend le
    même flottant. C'est ce qui prouve que la précision a suivi le nombre au
    lieu de le tronquer.
    """
    for decimales in (0, 2, 4):
        texte = typography.number(valeur, decimales)
        entier, _, fraction = texte.partition(",")
        assert fraction == "0" * decimales
        relu = entier.replace(typography.NARROW_NBSP, "").replace(
            typography.MINUS, "-"
        )
        assert float(int(relu)) == valeur
