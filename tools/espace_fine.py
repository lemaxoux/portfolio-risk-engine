"""Écrit la police d'une seule espace qui complète Spectral : U+202F.

    pip install fonttools          # seulement pour régénérer, pas pour l'application
    python -m tools.espace_fine    # écrit frontend/src/styles/fonts/espace-fine.ttf

═══ LE DÉFAUT, MESURÉ ═══

Le sous-ensemble latin de Spectral publié par @fontsource revendique U+202F
dans sa `unicode-range` (U+2000-206F), mais son cmap ne contient pas ce
caractère. Le navigateur ne cherche donc aucune autre police : Chrome
synthétise une demi-espace de la police principale, 0,125 em. Mesuré dans la
page : 1,75 px sur un texte Spectral de 14 px, 2,00 px à 16 px. Georgia seule
donne aussi une demi-espace ; Times New Roman, qui a le glyphe, 0,200 em.

La largeur n'est pas nulle, mais Spectral serre ses chiffres. L'approche droite
du « 0 » fait 33 unités, l'approche gauche du « % » 12, et le blanc entre les
deux tombe à 0,170 em : « 50 % » se lit « 50% ». IBM Plex Sans n'a pas davantage
le glyphe, mais ses approches font 60 et 65 unités, soit un blanc de 0,243 em,
qui reste visible.

═══ LE CORRECTIF ═══

Une police de deux glyphes : `.notdef` et une espace vide de 200 unités sur
1000, soit 0,200 em. C'est la largeur que Times New Roman, Arial et Cambria
donnent à U+202F, et le « cinquième de cadratin » que Unicode indique pour
l'espace fine. Le blanc entre « 0 » et « % » passe alors à 0,245 em en Spectral,
celui de Plex.

`typography.css` la déclare dans la famille 'Spectral', pour U+202F seulement
et APRÈS les faces de @fontsource : entre deux faces qui couvrent le même
caractère, c'est la dernière déclarée qui est essayée d'abord.

Les métriques verticales sont celles de Spectral (ascendante 1059, descendante
463) : une police de repli plus haute que la police principale pourrait
agrandir la ligne qui la contient.

Un fichier TTF plutôt que WOFF2 : il pèse quelques centaines d'octets, et le
test qui le vérifie (`typography.test.ts`) le lit sans décompresseur.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

RACINE = Path(__file__).resolve().parents[1]
DESTINATION = RACINE / "frontend" / "src" / "styles" / "fonts" / "espace-fine.ttf"

UNITES_PAR_EM = 1000
AVANCE_ESPACE_FINE = 200  # 0,200 em
ASCENDANTE_SPECTRAL = 1059
DESCENDANTE_SPECTRAL = 463
NOM = "Espace fine Mx Risk"
# Dates de la table `head`, FIXÉES : sans elles, chaque régénération écrirait
# un fichier différent pour une police identique. L'époque des polices
# TrueType est le 1904-01-01.
DATE_FIGEE = int((datetime(2026, 9, 25) - datetime(1904, 1, 1)).total_seconds())


def construire() -> FontBuilder:
    fb = FontBuilder(UNITES_PAR_EM, isTTF=True)
    glyphes = [".notdef", "uni202F"]
    fb.setupGlyphOrder(glyphes)
    fb.setupCharacterMap({0x202F: "uni202F"})
    vide = TTGlyphPen(None).glyph()
    fb.setupGlyf({nom: vide for nom in glyphes})
    fb.setupHorizontalMetrics(
        {".notdef": (AVANCE_ESPACE_FINE, 0), "uni202F": (AVANCE_ESPACE_FINE, 0)}
    )
    fb.setupHorizontalHeader(ascent=ASCENDANTE_SPECTRAL, descent=-DESCENDANTE_SPECTRAL)
    fb.setupNameTable({"familyName": NOM, "styleName": "Regular"})
    fb.setupOS2(
        version=4,  # le bit USE_TYPO_METRICS n'existe qu'à partir de la version 4
        sTypoAscender=ASCENDANTE_SPECTRAL,
        sTypoDescender=-DESCENDANTE_SPECTRAL,
        sTypoLineGap=0,
        usWinAscent=ASCENDANTE_SPECTRAL,
        usWinDescent=DESCENDANTE_SPECTRAL,
        fsSelection=0b11000000,  # USE_TYPO_METRICS, comme Spectral
    )
    fb.setupPost()
    fb.updateHead(created=DATE_FIGEE, modified=DATE_FIGEE)
    return fb


if __name__ == "__main__":
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    construire().save(DESTINATION)
    print(f"Police écrite : {DESTINATION.relative_to(RACINE)} ({DESTINATION.stat().st_size} octets)")
