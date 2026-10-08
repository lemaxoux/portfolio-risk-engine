"""Les deux moitiés du produit écrivent les nombres avec les mêmes caractères.

Le backend RÉDIGE des phrases contenant des nombres (`backend/typography.py`) ;
le frontend en FORMATE d'autres (`frontend/src/lib/format.ts`). Les deux sortes
se retrouvent côte à côte dans la même page : une observation du moteur de
règles, et le bloc mesure affiché juste à côté d'elle.

Si les deux emploient des espaces différentes, rien ne se voit — U+00A0 et
U+202F sont indiscernables à l'œil — jusqu'à ce qu'une ligne se coupe en fin de
ligne dans un cas et pas dans l'autre, et que le texte ait l'air composé à la
main. C'est exactement ce qu'un outil dont l'argument est la rigueur ne peut pas
se permettre d'avoir l'air d'être.

CE TEST LIT LE FICHIER TYPESCRIPT. C'est inhabituel, et c'est le point : la
garde doit vivre dans la suite qui tourne à chaque modification du backend,
puisque c'est le backend qui bouge. Un test Vitest équivalent ne serait joué
qu'en touchant au frontend, c'est-à-dire pas au moment où la divergence naît.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from backend import typography

RACINE = Path(__file__).resolve().parents[1]
FORMAT_TS = RACINE / "frontend" / "src" / "lib" / "format.ts"


@pytest.fixture(scope="module")
def source_frontend() -> str:
    if not FORMAT_TS.exists():
        pytest.skip("frontend/src/lib/format.ts absent")
    return FORMAT_TS.read_text(encoding="utf-8")


def _constante(source: str, nom: str) -> str:
    """La valeur d'une constante exportée, telle qu'elle est ÉCHAPPÉE."""
    trouve = re.search(rf"export const {nom} = '(\\u[0-9A-Fa-f]{{4}})'", source)
    assert trouve is not None, f"{nom} introuvable ou non échappée dans format.ts"
    return trouve.group(1)


def test_le_frontend_declare_les_memes_espaces_que_le_backend(source_frontend):
    """Les constantes sont ÉCRITES EN ÉCHAPPEMENTS des deux côtés.

    Une espace fine insécable collée telle quelle dans un fichier source se
    confond avec une espace ordinaire à la relecture, et un éditeur zélé la
    normalise sans que personne le voie passer.
    """
    attendus = {
        "ESPACE_FINE": typography.NARROW_NBSP,
        "ESPACE_INSECABLE": typography.NBSP,
    }
    for nom, caractere_python in attendus.items():
        echappement = _constante(source_frontend, nom)
        assert int(echappement[2:], 16) == ord(caractere_python), nom


def test_les_constantes_du_backend_sont_bien_celles_qu_on_croit(source_frontend):
    """Témoin : si `typography` changeait d'espace, le test ci-dessus suivrait
    sans rien dire. Les points de code sont donc écrits en clair, une fois."""
    assert ord(typography.NARROW_NBSP) == 0x202F
    assert ord(typography.NBSP) == 0x00A0
    assert _constante(source_frontend, "SIGNE_MOINS") == "\\u2212"


def test_le_seuil_de_groupement_des_milliers_est_le_meme(source_frontend):
    """« 504 » ne se groupe pas, « 1 000 » se groupe — des deux côtés.

    Le backend groupe à partir de quatre chiffres (`f"{n:,}"`). Un frontend qui
    grouperait dès trois écrirait « 504 séances » en deux morceaux là où le
    moteur en écrit un.
    """
    assert typography.thousands(504) == "504"
    assert typography.thousands(1000) == f"1{typography.NARROW_NBSP}000"
    # Côté frontend, le groupement est une expression régulière à bornes de mot.
    assert r"\B(?=(\d{3})+(?!\d))" in source_frontend


def test_l_accord_du_pluriel_est_le_meme(source_frontend):
    """Zéro et un prennent le singulier, des deux côtés."""
    assert typography.sessions(0) == f"0{typography.NBSP}séance"
    assert typography.sessions(1) == f"1{typography.NBSP}séance"
    assert typography.sessions(2) == f"2{typography.NBSP}séances"
    assert "Math.abs(nombre) < 2" in source_frontend


# ═════════════════════════════════════ Les nombres eux-mêmes, pas les espaces ══
#
# Les quatre tests ci-dessus comparent le VOCABULAIRE. Ceux-ci comparent
# l'ÉCRITURE d'un nombre : virgule, signe, arrondi. C'est leur absence qui a
# laissé passer « ν = 4.07 » à côté du « 4,07 » du frontend — le backend
# n'avait tout simplement pas de formateur décimal à comparer.


def test_le_signe_moins_est_le_meme(source_frontend):
    echappement = _constante(source_frontend, "SIGNE_MOINS")
    assert int(echappement[2:], 16) == ord(typography.MINUS) == 0x2212


def test_la_virgule_decimale_est_la_meme(source_frontend):
    assert typography.number(1.5, 1) == "1,5"
    assert typography.number(1234.5, 1) == f"1{typography.NARROW_NBSP}234,5"
    assert "`${grouper(entier)},${fraction}`" in source_frontend


def test_l_arrondi_est_le_meme(source_frontend):
    """La moitié s'éloigne de zéro, sur la valeur binaire réelle, comme `toFixed`.

    Le `format` de Python arrondit au pair : `f"{2.5:.0f}"` rend « 2 » là où
    `(2.5).toFixed(0)` rend « 3 ». Une part de 12,5 % s'écrirait 12 % dans une
    phrase du moteur et 13 % dans le chiffre affiché à côté.
    """
    assert typography.number(2.5, 0) == "3"
    assert typography.number(-2.5, 0) == f"{typography.MINUS}3"
    assert typography.number(0.125, 2) == "0,13"
    # 1,005 vaut 1,00499999999999989 en binaire : ce n'est PAS une moitié.
    assert typography.number(1.005, 2) == "1,00"
    assert "Math.abs(valeur).toFixed(decimales)" in source_frontend


def test_un_zero_arrondi_ne_porte_de_signe_d_aucun_cote(source_frontend):
    assert typography.number(-0.004, 2) == "0,00"
    assert "negatif && !nul" in source_frontend


# ═══════════════════════════════════ Les deux langues, cas par cas (chantier 7D) ══
#
# Les tests ci-dessus lisent le VOCABULAIRE déclaré dans format.ts. Ceux-ci
# fixent l'ÉCRITURE elle-même, dans les deux langues : une seule table de cas,
# `frontend/src/lib/typographie-partagee.json`, que `format.test.ts` lit aussi.
# Chaque moitié du produit doit écrire, pour chaque cas, exactement la chaîne
# attendue : la même des deux côtés, caractère pour caractère.

CAS_PARTAGES = RACINE / "frontend" / "src" / "lib" / "typographie-partagee.json"

ECRITURES = {
    "nombre": lambda langue, valeur, decimales: typography.number(valeur, decimales, langue=langue),
    "pourcentage": lambda langue, fraction, decimales: typography.percent(fraction, decimales, langue=langue),
    "pourcentage signé": lambda langue, fraction, decimales: typography.percent(
        fraction, decimales, signed=True, langue=langue
    ),
    "écart signé": lambda langue, ecart, decimales: typography.signed_points(ecart, decimales, langue=langue),
    "séances": lambda langue, nombre: typography.sessions(nombre, langue=langue),
    "lignes": lambda langue, nombre: typography.lines(nombre, langue=langue),
    "date longue": lambda langue, iso: typography.long_date(date.fromisoformat(iso), langue=langue),
}


def _cas_partages() -> list[dict]:
    return json.loads(CAS_PARTAGES.read_text(encoding="utf-8"))["cas"]


def test_la_table_des_cas_couvre_chaque_ecriture_dans_les_deux_langues():
    cas = _cas_partages()
    assert {c["fonction"] for c in cas} == set(ECRITURES)
    assert all(set(c) == {"fonction", "arguments", "fr", "en"} for c in cas)


@pytest.mark.parametrize("langue", ["fr", "en"])
def test_le_backend_ecrit_chaque_cas_partage(langue):
    fautes = [
        (c["fonction"], c["arguments"], ecrit, c[langue])
        for c in _cas_partages()
        if (ecrit := ECRITURES[c["fonction"]](langue, *c["arguments"])) != c[langue]
    ]
    assert fautes == []


def test_les_cas_partages_ecrivent_bien_les_espaces_et_le_signe_attendus():
    """Témoin : la table porte des espaces fines, insécables et des signes
    moins, et l'anglais n'en met aucune avant « % »."""
    cas = _cas_partages()
    francais = "".join(c["fr"] for c in cas)
    anglais = "".join(c["en"] for c in cas)
    assert typography.NARROW_NBSP in francais and typography.NBSP in francais
    assert typography.MINUS in francais and typography.MINUS in anglais
    assert typography.NARROW_NBSP not in anglais
    assert f"1er{typography.NBSP}janvier" in francais


def _liste_de_mots(source: str, nom: str) -> list[str]:
    """Les mots d'une constante `const NOM = [ ... ] as const` de format.ts."""
    trouve = re.search(rf"const {nom} = \[(.*?)\] as const", source, re.S)
    assert trouve is not None, f"{nom} introuvable dans format.ts"
    return re.findall(r"'([^']+)'", trouve.group(1))


def test_les_mois_sont_les_memes_dans_les_deux_langues(source_frontend):
    assert _liste_de_mots(source_frontend, "MOIS") == list(typography._MOIS)
    assert _liste_de_mots(source_frontend, "MONTHS") == list(typography._MONTHS)


def test_l_anglais_groupe_a_la_virgule_au_meme_seuil(source_frontend):
    """« 504 » ne se groupe pas, « 1,000 » se groupe, des deux côtés ; la
    même expression régulière, à la virgule."""
    assert typography.thousands(504, langue="en") == "504"
    assert typography.thousands(1000, langue="en") == "1,000"
    assert r"replace(/\B(?=(\d{3})+(?!\d))/g, ',')" in source_frontend
    assert "`${grouperEnAnglais(entier)}.${fraction}`" in source_frontend


def test_le_singulier_anglais_est_reserve_a_un_des_deux_cotes(source_frontend):
    """« 1 session », « 0 sessions », « 1.9 points » : en anglais, l'écriture
    décide, pas la valeur."""
    assert typography.sessions(1, langue="en") == f"1{typography.NBSP}session"
    assert typography.sessions(0, langue="en") == f"0{typography.NBSP}sessions"
    assert "ecrit.replace(SIGNE_MOINS, '') === '1'" in source_frontend
