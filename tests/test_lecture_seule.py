"""La base du serveur public ne s'écrit pas, et une composition n'y reste pas.

`backend/db/lecture_seule.py` ouvre la base en lecture seule au niveau de
SQLite, pose la composition reçue dans des tables temporaires qui masquent
celles de la base, puis verrouille la connexion. Trois choses se tiennent
ici :

* une écriture échoue, avant le verrou (la base) comme après (la connexion
  entière, table temporaire comprise) ;
* le moteur, inchangé, lit la composition posée et rend ce qu'il rend d'un
  portefeuille en base ;
* deux compositions analysées en même temps, dans deux fils, ne se voient
  pas : chacune a sa connexion, donc ses tables.

Les cours sont ceux de la copie figée de `conftest.py`, jamais ceux de la
base réelle.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from backend.db import portfolios as store
from backend.db.init_db import connect
from backend.db.lecture_seule import (
    NUMERO,
    nombre_de_seances,
    ouvrir,
    portefeuilles_en_base,
    poser_la_composition,
    seances_par_titre,
)
from backend.db.portfolios import PositionRow
from backend.risk_engine.engine import analyse_portfolio, run_all_scenarios
from backend.risk_engine.portfolio import load_positions
from tests.conftest import DATE_GEL, PORTEFEUILLE_DEMO

RACINE = Path(__file__).resolve().parents[1]

TECH = {"NVDA": 75, "AAPL": 55, "MSFT": 35, "GOOGL": 50, "AMZN": 65}


def lignes(composition: dict[str, float]) -> list[PositionRow]:
    return [PositionRow(ticker, float(quantite), None) for ticker, quantite in composition.items()]


ECRITURES = (
    "INSERT INTO prices (ticker, date, close, adj_close) VALUES ('KO', '2030-01-01', 1, 1)",
    "UPDATE prices SET close = 0",
    "DELETE FROM prices",
    "INSERT INTO portfolios (owner, name) VALUES ('x', 'y')",
    "INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1, 'KO', 1)",
    "CREATE TABLE intrus (a)",
    "DROP TABLE prices",
)


# ═══════════════════════════════════════════════ La base ne s'écrit pas ══


@pytest.mark.parametrize("requete", ECRITURES)
def test_une_ecriture_dans_la_base_echoue(base_figee, requete):
    """Sur un fichier que le système laisserait écrire : c'est SQLite qui
    refuse, pas les droits du fichier."""
    with closing(ouvrir(base_figee)) as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute(requete)
            conn.commit()


def test_la_meme_ecriture_passe_par_une_connexion_ordinaire(base_figee):
    """Le témoin : ce qui est refusé ci-dessus l'est par le mode d'ouverture."""
    with closing(connect(base_figee)) as conn, conn:
        conn.execute(ECRITURES[0])
    with closing(ouvrir(base_figee)) as conn:
        assert conn.execute("SELECT MAX(date) FROM prices").fetchone()[0] == "2030-01-01"


def test_la_base_n_a_pas_bouge_apres_une_analyse(base_figee_partagee):
    avant = base_figee_partagee.read_bytes()
    with closing(ouvrir(base_figee_partagee)) as conn:
        numero = poser_la_composition(conn, lignes(PORTEFEUILLE_DEMO))
        analyse_portfolio(conn, numero, monte_carlo=True)
    assert base_figee_partagee.read_bytes() == avant
    assert sorted(f.name for f in base_figee_partagee.parent.iterdir()) == [base_figee_partagee.name]


# ═══════════════════════════════════════ La composition, posée et masquante ══


def test_le_moteur_lit_la_composition_posee(base_figee_partagee):
    with closing(ouvrir(base_figee_partagee)) as conn:
        numero = poser_la_composition(conn, lignes(PORTEFEUILLE_DEMO))
        assert numero == NUMERO
        lues = load_positions(conn, numero)
    assert {p.ticker: p.quantity for p in lues} == PORTEFEUILLE_DEMO
    # L'ordre du moteur est celui des tickers, quel que soit l'ordre posé.
    assert [p.ticker for p in lues] == sorted(PORTEFEUILLE_DEMO)


def test_les_tables_temporaires_masquent_celles_de_la_base(base_figee):
    """La base porte un portefeuille numéro 1 qui n'est pas la composition :
    le moteur lit la composition."""
    with closing(connect(base_figee)) as conn:
        conn.execute("DELETE FROM positions")
        conn.execute("DELETE FROM portfolios")
        conn.execute("INSERT INTO portfolios (id, owner, name) VALUES (1, 'local', 'En base')")
        conn.execute("INSERT INTO positions (portfolio_id, ticker, quantity) VALUES (1, 'PFE', 700)")
        conn.commit()
    with closing(ouvrir(base_figee)) as conn:
        assert portefeuilles_en_base(conn) == (1, 1)
        numero = poser_la_composition(conn, lignes(TECH))
        assert [p.ticker for p in load_positions(conn, numero)] == sorted(TECH)
        assert store.get(conn, numero).name != "En base"
        # La base, elle, n'a pas changé : lue par son nom, elle a toujours sa ligne.
        assert conn.execute("SELECT ticker FROM main.positions").fetchall()[0][0] == "PFE"
        assert portefeuilles_en_base(conn) == (1, 1)


def test_l_analyse_de_la_composition_est_celle_du_portefeuille_en_base(base_figee):
    """Le même moteur, les mêmes cours : poser une composition ou l'écrire en
    base rend les mêmes nombres."""
    with closing(connect(base_figee)) as conn:
        cree = store.create(conn, "En base")
        store.replace_positions(conn, cree.id, lignes(PORTEFEUILLE_DEMO))
        en_base = analyse_portfolio(conn, cree.id, monte_carlo=True)
    with closing(ouvrir(base_figee)) as conn:
        posee = analyse_portfolio(conn, poser_la_composition(conn, lignes(PORTEFEUILLE_DEMO)), monte_carlo=True)
    assert posee.weights == en_base.weights
    assert posee.total_value == en_base.total_value
    assert posee.as_of == en_base.as_of == date.fromisoformat(DATE_GEL)
    assert posee.volatility == en_base.volatility
    assert posee.historical_var == en_base.historical_var
    assert posee.monte_carlo_var == en_base.monte_carlo_var
    assert posee.returns.equals(en_base.returns)


def test_rien_ne_reste_de_la_composition_apres_la_requete(base_figee_partagee):
    with closing(ouvrir(base_figee_partagee)) as conn:
        poser_la_composition(conn, lignes(TECH))
    with closing(ouvrir(base_figee_partagee)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM temp.sqlite_master").fetchone()[0] == 0


# ═══════════════════════════════════════════ La connexion, verrouillée ══

APRES_LE_VERROU = (
    *ECRITURES,
    "INSERT INTO temp.positions (portfolio_id, ticker, quantity) VALUES (1, 'PG', 1)",
    "DELETE FROM temp.positions",
    "UPDATE temp.portfolios SET name = 'x'",
    "CREATE TEMP TABLE intrus (a)",
    "ATTACH DATABASE ':memory:' AS autre",
    "PRAGMA writable_schema = 1",
    "PRAGMA temp_store = FILE",
)


@pytest.mark.parametrize("requete", APRES_LE_VERROU)
def test_une_fois_la_composition_posee_tout_ce_qui_n_est_pas_une_lecture_echoue(
    base_figee_partagee, requete
):
    with closing(ouvrir(base_figee_partagee)) as conn:
        poser_la_composition(conn, lignes(PORTEFEUILLE_DEMO))
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            conn.execute(requete)
        # La composition est intacte.
        assert len(load_positions(conn, NUMERO)) == len(PORTEFEUILLE_DEMO)


def test_avant_le_verrou_une_table_temporaire_s_ecrit(base_figee_partagee):
    """Le témoin du verrou : sans lui, la connexion laisse écrire ses tables
    temporaires. C'est lui qui les ferme."""
    with closing(ouvrir(base_figee_partagee)) as conn:
        conn.execute("CREATE TEMP TABLE intrus (a)")
        conn.execute("INSERT INTO intrus VALUES (1)")
        assert conn.execute("SELECT a FROM intrus").fetchone()[0] == 1


def test_la_composition_vit_en_memoire(base_figee_partagee):
    with closing(ouvrir(base_figee_partagee)) as conn:
        conn.execute("PRAGMA temp_store = MEMORY")
        # 2 : la mémoire (documentation de SQLite, `PRAGMA temp_store`).
        assert conn.execute("PRAGMA temp_store").fetchone()[0] == 2


# ══════════════════════════════════════ Deux analyses en même temps ══


def _analyser(base: Path, composition: dict[str, float], depart: threading.Barrier | None = None):
    with closing(ouvrir(base)) as conn:
        numero = poser_la_composition(conn, lignes(composition))
        if depart is not None:
            depart.wait(timeout=30)
        rapport = analyse_portfolio(conn, numero, monte_carlo=True)
        scenarios = run_all_scenarios(conn, numero)
    return rapport, scenarios


def _resume(resultat) -> tuple:
    rapport, scenarios = resultat
    return (
        tuple(rapport.weights.items()),
        rapport.total_value,
        rapport.volatility,
        tuple(sorted((niveau, var.value) for niveau, var in rapport.historical_var.items())),
        tuple(sorted((niveau, var.value) for niveau, var in (rapport.monte_carlo_var or {}).items())),
        tuple(rapport.returns.round(15)),
        tuple(s.end_to_end_return for s in scenarios),
    )


def test_deux_compositions_analysees_en_meme_temps_ne_se_voient_pas(base_figee_partagee):
    """Deux fils, deux connexions, deux compositions, posées toutes les deux
    AVANT que l'une ou l'autre soit analysée (la barrière) : chacune rend le
    résultat qu'elle rend seule."""
    seules = {
        "demo": _resume(_analyser(base_figee_partagee, PORTEFEUILLE_DEMO)),
        "tech": _resume(_analyser(base_figee_partagee, TECH)),
    }
    assert seules["demo"] != seules["tech"]

    depart = threading.Barrier(2)
    ensemble: dict[str, tuple] = {}
    erreurs: list[BaseException] = []

    def lancer(nom: str, composition: dict[str, float]) -> None:
        try:
            ensemble[nom] = _resume(_analyser(base_figee_partagee, composition, depart))
        except BaseException as exc:  # noqa: BLE001 : rendue au fil du test
            erreurs.append(exc)

    fils = [
        threading.Thread(target=lancer, args=("demo", PORTEFEUILLE_DEMO)),
        threading.Thread(target=lancer, args=("tech", TECH)),
    ]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join(timeout=120)

    assert erreurs == []
    assert ensemble == seules


# ═══════════════════════════════════════════════ Ce que la base contient ══


def test_les_seances_par_titre_sont_celles_de_la_base(base_figee_partagee):
    with closing(ouvrir(base_figee_partagee)) as conn:
        par_titre = seances_par_titre(conn)
        distinctes = nombre_de_seances(conn)
        attendu = conn.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM prices WHERE ticker = 'KO'"
        ).fetchone()
    nombre, debut, fin = par_titre["KO"]
    assert (nombre, debut.isoformat(), fin.isoformat()) == tuple(attendu)
    assert fin.isoformat() == DATE_GEL
    assert nombre <= distinctes


def test_le_seul_sql_du_serveur_public_est_ici():
    """`backend/public_api/` n'écrit aucune requête : ce module est son seul
    accès à SQLite."""
    from .test_api_discipline import MOTS_SQL, chaines_de_code

    modules = sorted((RACINE / "backend" / "public_api").glob("*.py"))
    assert len(modules) >= 6
    fautes = [
        f"{chemin.name}:{noeud.lineno}"
        for chemin in modules
        for noeud in chaines_de_code(chemin)
        if any(mot in noeud.value.upper() for mot in MOTS_SQL)
    ]
    assert fautes == []
