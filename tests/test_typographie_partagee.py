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

import re
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
