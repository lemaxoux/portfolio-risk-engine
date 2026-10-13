"""Les réglages du serveur public chez son hébergeur (`deploiement/render.yaml`).

Aucun test ne couvre un déploiement. Celui-ci tient ce qui se tient sans
hébergeur : que le fichier dit ce que le serveur attend, et rien qu'il ne
faudrait pas.

* la version de Python est celle des tests, écrite en entier ;
* la base se désigne par la variable que le serveur lit, et par elle seule ;
* un fil pour l'algèbre linéaire ;
* aucun déploiement automatique, aucun secret, aucun dossier racine qui
  cacherait la base au service ;
* les commandes lancent le serveur public, avec ses dépendances à lui.

Le fichier est lu comme du texte : le dépôt n'a pas de lecteur YAML, et n'en
prend pas un pour vingt lignes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from backend.public_api.app import VARIABLE_ORIGINE_DE_DEVELOPPEMENT, create_public_app
from backend.public_api.base import VARIABLE_BASE

RACINE = Path(__file__).resolve().parents[1]
FICHIER = RACINE / "deploiement" / "render.yaml"

FILS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def lignes() -> list[str]:
    """Les lignes du fichier, sans commentaires ni lignes vides."""
    return [
        ligne.rstrip()
        for ligne in FICHIER.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    ]


def reglages() -> dict[str, str]:
    """Les réglages du service : `cle: valeur`, hors variables."""
    trouves = {}
    for ligne in lignes():
        cle, separateur, valeur = ligne.strip().removeprefix("- ").partition(":")
        if separateur and valeur.strip() and cle not in ("key", "value"):
            trouves[cle.strip()] = valeur.strip()
    return trouves


def variables() -> dict[str, str]:
    """Les variables d'environnement : chaque `key` avec le `value` qui la suit."""
    propres = [ligne.strip().removeprefix("- ") for ligne in lignes()]
    trouvees = {}
    for rang, ligne in enumerate(propres):
        if ligne.startswith("key:"):
            suivante = propres[rang + 1]
            assert suivante.startswith("value:"), ligne
            trouvees[ligne.partition(":")[2].strip()] = suivante.partition(":")[2].strip()
    return trouvees


def test_la_lecture_voit_le_service_et_ses_variables():
    assert reglages()["type"] == "web"
    assert len(variables()) >= 5


def test_la_version_de_python_est_celle_des_tests_ecrite_en_entier():
    version = variables()["PYTHON_VERSION"]
    parties = version.split(".")
    assert len(parties) == 3 and all(partie.isdigit() for partie in parties), version
    assert (int(parties[0]), int(parties[1])) == sys.version_info[:2]


def test_la_base_se_designe_par_la_variable_que_le_serveur_lit():
    assert variables()[VARIABLE_BASE] == "../base/serveur.sqlite"
    # La commande part de `app/` : la base est à côté de lui, hors de l'arbre
    # du dépôt public.
    assert reglages()["startCommand"] == "cd app && python -m backend.public_api"


def test_les_variables_sont_celles_la_et_aucune_autre():
    """Ni clé, ni secret, ni origine de développement, ni base de
    l'application."""
    assert set(variables()) == {"PYTHON_VERSION", VARIABLE_BASE, *FILS}
    assert VARIABLE_ORIGINE_DE_DEVELOPPEMENT not in variables()
    texte = FICHIER.read_text(encoding="utf-8")
    for interdit in ("sync:", "MX_RISK_DB_PATH", "TIINGO", "fromDatabase", "generateValue"):
        assert interdit not in texte, interdit


def test_un_fil_pour_l_algebre_lineaire():
    assert {variables()[nom] for nom in FILS} == {'"1"'}


def test_aucun_deploiement_automatique():
    # Entre guillemets : nu, `off` se lit « faux » en YAML, pas le mot.
    assert reglages()["autoDeployTrigger"] == '"off"'
    assert "autoDeploy" not in reglages()


def test_l_offre_gratuite_sans_dossier_racine():
    assert reglages()["plan"] == "free"
    assert reglages()["runtime"] == "python"
    assert "rootDir" not in reglages()


def test_les_dependances_installees_sont_celles_du_serveur():
    assert reglages()["buildCommand"] == "pip install -r app/requirements-serveur.txt"
    assert (RACINE / "requirements-serveur.txt").is_file()


def test_le_chemin_de_sante_est_une_route_du_serveur():
    chemin = reglages()["healthCheckPath"]
    assert chemin in create_public_app().openapi()["paths"]
    assert chemin == "/health"
