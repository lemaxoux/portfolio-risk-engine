"""Un nombre saisi se lit de la même façon dans le tableau et dans un CSV.

Le tableau de saisie envoie des nombres en JSON : c'est le CLIENT qui lit
« 12,5 » (`frontend/src/lib/saisie.ts`). L'import CSV les lit côté serveur
(`backend/api/csv_import._nombre`). Deux lecteurs, donc, et une exigence : ils
acceptent et refusent exactement les mêmes entrées. Sans elle, un fichier
importé puis réenregistré depuis le tableau pourrait ne plus se relire, ou
l'inverse.

Même démarche que `test_typographie_partagee.py` : les deux moitiés du produit
sont tenues ensemble depuis la suite Python. Ici par une LISTE DE CAS
partagée, `frontend/src/lib/nombres-saisis.json`, que `saisie.test.ts` lit
aussi.

Le cas comparé est celui du séparateur « ; », où la virgule est admise comme
décimale : c'est la règle du tableau, qui n'a pas de séparateur de champs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.api.csv_import import _nombre

CAS = json.loads(
    Path(__file__)
    .resolve()
    .parents[1]
    .joinpath("frontend", "src", "lib", "nombres-saisis.json")
    .read_text(encoding="utf-8")
)


def test_la_liste_partagee_n_est_pas_vide():
    """Témoin : un chemin faux rendrait les tests suivants verts sur rien."""
    assert len(CAS["acceptes"]) >= 10
    assert len(CAS["refuses"]) >= 10


@pytest.mark.parametrize("texte, attendu", CAS["acceptes"], ids=repr)
def test_le_lecteur_csv_accepte_ce_que_le_tableau_accepte(texte, attendu):
    valeur, _ = _nombre(texte, virgule_admise=True)
    assert valeur == attendu


@pytest.mark.parametrize("texte", CAS["refuses"], ids=repr)
def test_le_lecteur_csv_refuse_ce_que_le_tableau_refuse(texte):
    with pytest.raises(ValueError):
        _nombre(texte, virgule_admise=True)


def test_la_liste_couvre_ce_que_float_accepterait_a_tort():
    """La grammaire est plus stricte que `float()`, et la liste le prouve :
    chacun de ces cas passerait par `float()` après retrait des espaces."""
    for texte in ("1e3", "inf", "nan", "1_000", ".5", "5.", "\u0661\u0662"):
        assert texte in CAS["refuses"], texte
        float(texte)  # ne lève pas : c'est bien la grammaire qui refuse
