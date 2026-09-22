"""La règle d'or de la phase 7A, vérifiée mécaniquement.

« La couche API ne calcule RIEN. » Une règle écrite dans un README se contourne
sans bruit : une soustraction glissée dans un schéma pour « juste afficher
l'écart » produit un chiffre que personne n'a testé, à côté de chiffres qui
l'ont été, et rien ne les distingue à la lecture de la réponse.

Ces tests inspectent l'arbre syntaxique de `backend/api/` plutôt que son
comportement. Ils sont volontairement rigides : leur intérêt est d'échouer le
jour où quelqu'un — y compris plus tard, de bonne foi — ajoutera l'opération
« évidente » qui n'a pas sa place ici.

LES DOCSTRINGS SONT EXCLUES DE TOUTE RECHERCHE. Un module qui documente ce
qu'il s'interdit cite forcément le motif interdit ; une garde qui lirait le
texte brut se déclencherait sur sa propre explication, et la façon la plus
simple de la faire taire serait d'effacer l'explication. Les gardes portent donc
sur le CODE.

Même démarche que `test_rules.py`, qui vérifie déjà que le moteur de règles
n'importe aucun module de calcul.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_API = RACINE / "backend" / "api"

MODULES_API = sorted(DOSSIER_API.rglob("*.py"))


def arbre(chemin: Path) -> ast.Module:
    return ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))


def _docstrings(module: ast.Module) -> set[int]:
    """Identités des nœuds qui sont des docstrings, à ignorer."""
    repertoire = set()
    for noeud in ast.walk(module):
        if isinstance(
            noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            corps = getattr(noeud, "body", [])
            if (
                corps
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)
            ):
                repertoire.add(id(corps[0].value))
    return repertoire


def chaines_de_code(chemin: Path) -> list[ast.Constant]:
    """Chaînes littérales du module, docstrings exclues."""
    module = arbre(chemin)
    docstrings = _docstrings(module)
    return [
        noeud
        for noeud in ast.walk(module)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in docstrings
    ]


def test_le_dossier_api_est_bien_celui_qu_on_croit():
    noms = {chemin.name for chemin in MODULES_API}
    assert {"app.py", "schemas.py", "csv_import.py", "validation.py"} <= noms
    assert (DOSSIER_API / "routes").is_dir()


# ═══════════════════════════════════════════════ Zéro arithmétique ══


# `|` est exclu : dans une annotation, `int | None` est un `ast.BinOp` qui n'a
# rien d'un calcul. Ce sont les quatre opérations, la puissance et le modulo qui
# n'ont pas leur place ici.
CALCULS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.MatMult,
)

# Deux fonctions natives qui CHANGENT une valeur numérique.
#
# `round` est du formatage, et cette couche n'en fait pas : l'arrondi est décidé
# à un seul endroit, côté frontend. `abs` efface un signe, or le signe porte du
# sens partout dans ce moteur — une VaR est une perte positive, un rendement de
# scénario est négatif, un `prediction_gap` négatif dit que la crise a coûté
# plus que ce que la gestion courante laissait attendre.
NATIVES_INTERDITES = ("round", "abs")


def calculs_dans(source: str, nom: str = "<extrait>") -> list[str]:
    """Emplacements où ce source ferait un calcul. Liste vide s'il n'en fait pas.

    Extraite de la garde pour être elle-même testable : une garde qu'on n'a
    jamais vue échouer ne prouve rien, elle rassure. Deux jeux de témoins
    l'exercent plus bas, dans les deux sens.
    """
    fautes: list[str] = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, CALCULS):
            fautes.append(f"{nom}:{noeud.lineno} opération binaire")
        elif isinstance(noeud, ast.AugAssign) and isinstance(noeud.op, CALCULS):
            fautes.append(f"{nom}:{noeud.lineno} affectation augmentée")
        elif isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, ast.USub):
            # `-1` est un littéral négatif — un indice, une constante —, pas un
            # calcul. `-resultat.value` en est un, et c'est exactement
            # l'inversion de signe que `risk_engine.var` redoute : une VaR
            # rendue en perte positive et republiée en rendement négatif se
            # lirait comme un gain, sans qu'aucun test de valeur ne bronche.
            litteral = isinstance(noeud.operand, ast.Constant) and isinstance(
                noeud.operand.value, (int, float)
            )
            if not litteral:
                fautes.append(f"{nom}:{noeud.lineno} négation d'une valeur")
        elif isinstance(noeud, ast.Call):
            appele = getattr(noeud.func, "id", None) or getattr(
                noeud.func, "attr", None
            )
            if appele in NATIVES_INTERDITES:
                fautes.append(f"{nom}:{noeud.lineno} appel à {appele}()")
    return fautes


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_aucun_module_de_l_api_ne_fait_d_arithmetique(chemin):
    """Chaque nombre publié sort d'une fonction du moteur, déjà testée.

    Si une valeur manque, elle s'ajoute au moteur avec son test — jamais ici.
    Les concaténations de chaînes tombent sous la même règle : un `+` de texte
    est indiscernable d'un `+` de nombres à la lecture de l'arbre, et les
    f-strings font le travail sans ambiguïté.
    """
    fautes = calculs_dans(chemin.read_text(encoding="utf-8"), chemin.name)
    assert not fautes, f"calcul dans la couche API : {fautes}"


# ------------------------------------------------ Témoins de la garde --

TEMOINS_CALCUL = (
    ("addition", "resultat = a + b"),
    ("soustraction", "ecart = contribution - poids"),
    ("multiplication", "valeur = quantite * prix"),
    ("division", "part = valeur / total"),
    ("puissance", "annualisee = quotidienne ** 0.5"),
    ("modulo", "reste = index % taille"),
    ("affectation augmentée", "total += valeur"),
    ("négation d'un attribut", "perte = -resultat.value"),
    ("négation d'un appel", "perte = -calculer(serie)"),
    ("négation d'un nom", "inverse = -seuil"),
    ("arrondi", "affiche = round(valeur, 2)"),
    ("valeur absolue", "ecart = abs(reel)"),
    ("arrondi en méthode", "affiche = numpy.round(valeur)"),
)

TEMOINS_LEGITIMES = (
    ("annotation union", "def f(x: int | None) -> str | None: ..."),
    ("littéral négatif", "SEUIL = -1"),
    ("indice négatif", "dernier = noms[-1]"),
    ("tranche", "court = texte[:117]"),
    ("comparaison", "trop = len(payload) > MAX_BYTES"),
    ("f-string", "texte = f'{ticker} sur {seances} séances'"),
    ("sélection", "meilleur = max(options, key=len)"),
    ("somme d'un attribut", "total = sum(p.weight for p in positions)"),
    ("appel du moteur", "part = resultat.excess_over_weight(ticker)"),
)


@pytest.mark.parametrize(
    "libelle, extrait", TEMOINS_CALCUL, ids=[t[0] for t in TEMOINS_CALCUL]
)
def test_la_garde_voit_un_calcul_quand_il_y_en_a_un(libelle, extrait):
    """Témoins POSITIFS.

    Sans eux, une garde qui ne détecterait plus rien — un `CALCULS` vidé, un
    `ast.walk` remplacé par un parcours qui n'entre pas dans les corps de
    fonction — passerait au vert sur toute la couche et la déclarerait propre.
    """
    assert calculs_dans(extrait), extrait


@pytest.mark.parametrize(
    "libelle, extrait", TEMOINS_LEGITIMES, ids=[t[0] for t in TEMOINS_LEGITIMES]
)
def test_la_garde_laisse_passer_le_code_legitime(libelle, extrait):
    """Témoins NÉGATIFS.

    Une garde qui se déclenche sur `int | None` ou sur `noms[-1]` serait
    désactivée dans la semaine, et c'est ainsi qu'une règle meurt.
    """
    assert calculs_dans(extrait) == [], extrait


# ══════════════════════════════════════════════ Imports autorisés ══


# Modules de calcul dont RIEN ne doit être importé.
CALCUL_INTERDIT = {
    "numpy",
    "pandas",
    "scipy",
    "statistics",
    "backend.risk_engine.covariance",
    "backend.risk_engine.returns",
    "backend.risk_engine.regime",
}

# Modules qui contiennent des estimateurs ET les types qui les transportent.
# Seuls les TYPES sont autorisés : importer `expected_shortfall` ou
# `buy_and_hold_value` signalerait qu'un calcul est refait à la main ici.
TYPES_AUTORISES = {
    "backend.risk_engine.measures": {"Drawdown"},
    "backend.risk_engine.stress": {"PositionContribution"},
    "backend.risk_engine.var": {"StudentFit"},
}


def imports_de(chemin: Path):
    for noeud in ast.walk(arbre(chemin)):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                yield alias.name, None
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            yield noeud.module, {alias.name for alias in noeud.names}


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_l_api_n_importe_aucun_module_de_calcul(chemin):
    """Ni numpy, ni pandas, ni scipy, ni les modules purs du moteur.

    `engine`, `portfolio`, `scenarios`, `rules` restent autorisés : ce sont les
    façades qui rendent des résultats DÉJÀ composés, et les appeler est
    précisément le travail de cette couche.
    """
    fautes = [
        module for module, _ in imports_de(chemin) if module in CALCUL_INTERDIT
    ]
    assert not fautes, f"{chemin.name} importe un module de calcul : {fautes}"


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_des_modules_de_calcul_seuls_les_types_sont_importes(chemin):
    """`measures`, `stress` et `var` ne cèdent que leurs dataclasses.

    Un schéma a besoin du TYPE `Drawdown` pour annoter ce qu'il reçoit ; il n'a
    aucune raison d'appeler `max_drawdown`.
    """
    for module, noms in imports_de(chemin):
        if module in TYPES_AUTORISES and noms is not None:
            interdits = noms - TYPES_AUTORISES[module]
            assert not interdits, f"{chemin.name} importe {interdits} de {module}"
        elif module in TYPES_AUTORISES:
            pytest.fail(f"{chemin.name} importe {module} en entier")


# ═══════════════════════════════════════════════════════ Zéro SQL ══


MOTS_SQL = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE ", "PRAGMA ")


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_aucun_module_de_l_api_n_ecrit_de_sql(chemin):
    """Les lectures vivent dans `risk_engine.portfolio`, les écritures dans
    `db.portfolios`. La couche API valide, appelle, sérialise.

    Une requête ici créerait une troisième frontière avec la base, qui
    dériverait des deux autres — et une future commande en ligne devrait
    importer la couche HTTP pour écrire une position.
    """
    fautes = [
        f"{chemin.name}:{noeud.lineno}"
        for noeud in chaines_de_code(chemin)
        if any(mot in noeud.value.upper() for mot in MOTS_SQL)
    ]
    assert not fautes, f"SQL dans la couche API : {fautes}"


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_l_api_n_ouvre_jamais_sa_propre_connexion_hors_dependance(chemin):
    """Une connexion ouverte ailleurs que dans la dépendance ne serait pas fermée.

    `app.py` fait exception : son contrôle de schéma au démarrage ouvre et ferme
    explicitement, avant que la moindre requête n'existe.
    """
    if chemin.name in ("dependencies.py", "app.py"):
        return
    appels = {
        noeud.func.attr
        for noeud in ast.walk(arbre(chemin))
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
    }
    noms = {
        noeud.func.id
        for noeud in ast.walk(arbre(chemin))
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
    }
    assert "connect" not in appels | noms, f"{chemin.name} ouvre une connexion"


# ══════════════════════════════════════ Zéro suppression des nulls ══


EXCLUSIONS_INTERDITES = {
    "response_model_exclude_none",
    "response_model_exclude_unset",
    "response_model_exclude_defaults",
    "exclude_none",
    "exclude_unset",
    "exclude_defaults",
}


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_aucune_reponse_n_exclut_les_champs_nuls(chemin):
    """Exclure les nuls supprimerait exactement les champs qui expliquent un blanc.

    Un Sortino indéfini sort `annualised: null` ET `undefined_reason`. Retirer
    les nuls ferait disparaître le premier, et le client afficherait un vide au
    lieu d'une explication — la panne la plus coûteuse de cette couche, et la
    plus silencieuse.
    """
    fautes = [
        f"{chemin.name}:{noeud.lineno} ({noeud.arg})"
        for noeud in ast.walk(arbre(chemin))
        if isinstance(noeud, ast.keyword) and noeud.arg in EXCLUSIONS_INTERDITES
    ]
    assert not fautes, f"suppression de champs nuls : {fautes}"


@pytest.mark.parametrize("chemin", MODULES_API, ids=lambda p: p.name)
def test_aucun_schema_n_est_construit_par_asdict(chemin):
    """`asdict()` perd les `@property` et les méthodes, sans lever.

    C'est le piège central de cette phase : `prediction_gap`, `caveat`,
    `chosen`, `value_share`, `summary()`, `render()` disparaîtraient d'une API
    qui n'aurait pourtant produit aucune erreur. Chaque schéma énumère donc ses
    champs à la main.
    """
    fautes = []
    for noeud in ast.walk(arbre(chemin)):
        if isinstance(noeud, ast.Call):
            nom = getattr(noeud.func, "id", None) or getattr(noeud.func, "attr", None)
            if nom in ("asdict", "astuple"):
                fautes.append(f"{chemin.name}:{noeud.lineno}")
    assert not fautes, f"conversion générique de dataclass : {fautes}"


def test_les_schemas_refusent_nan_et_infini():
    """Première des deux gardes contre un JSON invalide.

    Pydantic nomme le champ fautif ; le rendu de Starlette, lui, refuse d'écrire
    la valeur mais ne dit pas d'où elle vient. Les deux servent.
    """
    from backend.api.schemas import Schema

    assert Schema.model_config["allow_inf_nan"] is False


# ════════════════════════════════════════ L'API est liée en local ══


def test_l_adresse_d_ecoute_est_ecrite_en_dur_sur_la_boucle_locale():
    """L'API n'a ni authentification ni notion d'utilisateur.

    Une adresse d'écoute laissée en option de ligne de commande est une adresse
    qu'on finit par changer ; elle est donc écrite dans le point d'entrée.
    """
    chemin = DOSSIER_API / "__main__.py"
    hotes = [
        noeud.value.value
        for noeud in ast.walk(arbre(chemin))
        if isinstance(noeud, ast.Assign)
        and any(getattr(c, "id", None) == "HOST" for c in noeud.targets)
        and isinstance(noeud.value, ast.Constant)
    ]
    assert hotes == ["127.0.0.1"]
    assert "0.0.0.0" not in {c.value for c in chaines_de_code(chemin)}


def test_l_application_ne_declare_aucun_cors_permissif():
    """Le frontend de la phase 7B sera servi par cette même application.

    Un `allow_origins=["*"]` sur une API sans authentification ouvrirait les
    portefeuilles à n'importe quelle page ouverte dans le navigateur.
    """
    chemin = DOSSIER_API / "app.py"
    mots_cles = {
        noeud.arg
        for noeud in ast.walk(arbre(chemin))
        if isinstance(noeud, ast.keyword)
    }
    assert "allow_origins" not in mots_cles
    assert "CORSMiddleware" not in {m for m, _ in imports_de(chemin)}
