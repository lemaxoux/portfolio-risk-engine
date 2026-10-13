"""Le texte d'acceptation du site : celui de l'application, plus une section.

Le site envoie le portefeuille qu'un visiteur saisit à un serveur public
(chantier 9.6) ; l'application installée ne l'envoie nulle part. Le texte
d'acceptation EN LIGNE gagne donc une section, qui le dit. Deux choses se
tiennent ici :

* le texte de l'application ne change pas d'un octet. Son empreinte est la
  clé sous laquelle un navigateur mémorise l'acceptation : un caractère de
  plus ferait réaccepter tout le monde ;
* le texte en ligne est ce texte-là, avec la section nouvelle placée avant
  la dernière, et rien d'autre.
"""

from __future__ import annotations

import pytest

from backend.api.schemas import DisclaimerOut
from backend.risk_engine.config import DEFAULT_WINDOW
from backend.rules.disclaimer import (
    ACCEPTANCE_TEXT,
    acceptance_confirmation,
    acceptance_sections,
    acceptance_text,
    acceptance_title,
)
from backend.textes import textes
from backend.typography import prose

LANGUES = ("fr", "en")

# Le titre et la phrase validés le 2026-10-13, mot pour mot.
SECTION = {
    "fr": (
        "Votre portefeuille est envoyé, il n'est pas enregistré",
        "Le portefeuille que vous saisissez ou importez sur ce site est envoyé à un "
        "serveur pour le calcul, et n'y est pas enregistré.",
    ),
    "en": (
        "Your portfolio is sent, not stored",
        "The portfolio that you enter or import on this site is sent to a server "
        "for the calculation, and is not stored there.",
    ),
}

DERNIERE = {"fr": "Utilisation à vos risques", "en": "Use at your own risk"}


@pytest.mark.parametrize("langue", LANGUES)
def test_la_section_est_celle_qui_a_ete_validee(langue):
    assert textes(langue).bandeau.SECTION_EN_LIGNE == SECTION[langue]


@pytest.mark.parametrize("langue", LANGUES)
def test_la_section_est_une_seule_phrase(langue):
    """« Le portefeuille est envoyé au serveur pour le calcul et n'y est pas
    enregistré » : une phrase, comme décidé."""
    _, corps = SECTION[langue]
    assert corps.count(".") == 1 and corps.endswith(".")


# ═════════════════════════════════════ Le texte de l'application ne bouge pas ══


@pytest.mark.parametrize("langue", LANGUES)
def test_sans_le_demander_le_texte_est_celui_de_l_application(langue):
    locales = acceptance_sections(langue=langue)
    assert locales == acceptance_sections(langue=langue, en_ligne=False)
    assert len(locales) == 5
    assert all(section.title != SECTION[langue][0] for section in locales)
    assert SECTION[langue][1] not in acceptance_text(langue=langue)
    assert acceptance_text(langue=langue) == acceptance_text(langue=langue, en_ligne=False)


def test_le_texte_francais_par_defaut_est_la_constante_d_avant():
    assert acceptance_text() == ACCEPTANCE_TEXT
    assert SECTION["fr"][1] not in ACCEPTANCE_TEXT


@pytest.mark.parametrize("langue", LANGUES)
def test_l_api_locale_ne_sert_que_le_texte_de_l_application(client_synthetique, langue):
    """Aucune route ne rend le texte en ligne, et un paramètre de ce nom n'y
    change rien : l'export de la démonstration l'écrit, pas l'API."""
    simple = client_synthetique.get(f"/api/disclaimer?lang={langue}")
    force = client_synthetique.get(f"/api/disclaimer?lang={langue}&en_ligne=true")
    assert simple.status_code == force.status_code == 200
    assert simple.content == force.content
    corps = simple.json()
    assert len(corps["sections"]) == 5
    assert SECTION[langue][1] not in corps["text"]


# ═══════════════════════════════════════════════════════ Le texte en ligne ══


@pytest.mark.parametrize("langue", LANGUES)
def test_le_texte_en_ligne_est_celui_de_l_application_plus_une_section(langue):
    locales = acceptance_sections(langue=langue)
    en_ligne = acceptance_sections(langue=langue, en_ligne=True)
    assert len(en_ligne) == 6
    # Les quatre premières et la dernière sont celles de l'application.
    assert en_ligne[:4] == locales[:4]
    assert en_ligne[5] == locales[4]
    assert (en_ligne[4].title, en_ligne[4].body) == SECTION[langue]


@pytest.mark.parametrize("langue", LANGUES)
def test_la_section_precede_la_derniere(langue):
    titres = [section.title for section in acceptance_sections(langue=langue, en_ligne=True)]
    assert titres[-1] == DERNIERE[langue]
    assert titres[-2] == SECTION[langue][0]


@pytest.mark.parametrize("langue", LANGUES)
def test_le_texte_a_plat_porte_la_section_une_fois_a_sa_place(langue):
    titre, corps = SECTION[langue]
    local = acceptance_text(langue=langue)
    en_ligne = acceptance_text(langue=langue, en_ligne=True)
    assert en_ligne != local
    assert en_ligne.count(corps) == 1
    # Retirer la section redonne le texte de l'application, octet pour octet.
    assert en_ligne.replace(f"{titre}\n{corps}\n\n", "") == local
    assert en_ligne.index(corps) < en_ligne.index(DERNIERE[langue])
    assert en_ligne.startswith(acceptance_title(langue))
    assert en_ligne.endswith(acceptance_confirmation(langue))


@pytest.mark.parametrize("fenetre", (DEFAULT_WINDOW, 126))
@pytest.mark.parametrize("langue", LANGUES)
def test_le_schema_publie_les_six_sections_et_leur_texte_a_plat(langue, fenetre):
    local = DisclaimerOut.seul(fenetre, langue)
    en_ligne = DisclaimerOut.seul(fenetre, langue, en_ligne=True)
    assert len(local.sections) == 5 and len(en_ligne.sections) == 6
    assert en_ligne.title == local.title
    assert en_ligne.confirmation == local.confirmation
    assert [s.title for s in en_ligne.sections[:4]] == [s.title for s in local.sections[:4]]
    assert en_ligne.sections[5] == local.sections[4]
    assert en_ligne.sections[4].title == prose(SECTION[langue][0])
    assert en_ligne.sections[4].body == prose(SECTION[langue][1])
    assert en_ligne.text == prose(acceptance_text(fenetre, langue=langue, en_ligne=True))
    assert en_ligne.text != local.text


def test_les_deux_langues_ont_chacune_leur_texte_en_ligne():
    assert acceptance_text(langue="fr", en_ligne=True) != acceptance_text(langue="en", en_ligne=True)
