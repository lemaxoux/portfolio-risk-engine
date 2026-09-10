"""Tests de l'ingestion, sur un fournisseur simulé.

Le double implémente le contrat de `MarketDataProvider` sans aucune couche
HTTP : ces tests ne touchent ni le réseau ni le quota Tiingo, et enregistrent
les fenêtres demandées pour qu'on puisse vérifier ce qui a été réclamé.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.data_provider.base import (
    DailyBar,
    ProviderError,
    RateLimitError,
    SecurityInfo,
    UnknownTickerError,
)
from backend.db.init_db import connect, init_db
from backend.ingestion.prices import (
    A_JOUR,
    ECHEC,
    IGNORE,
    OK,
    backfill,
    ensure_ticker,
    last_stored_date,
    refresh,
    upsert_security,
    years_ago,
)
from backend.ingestion.universe import BACKFILL_YEARS, DEV_UNIVERSE

AUJOURD_HUI = date(2026, 9, 9)


# ---------------------------------------------------------------- Doublures --


def barres(depart: date, nombre: int, prix: float = 100.0, split_le: date | None = None):
    """`nombre` séances ouvrées consécutives à partir de `depart`."""
    resultat, jour = [], depart
    while len(resultat) < nombre:
        if jour.weekday() < 5:
            resultat.append(
                DailyBar(
                    date=jour,
                    open=prix,
                    high=prix + 1,
                    low=prix - 1,
                    close=prix,
                    adj_close=prix / 2,  # volontairement différent de close
                    volume=1_000_000,
                    split_factor=4.0 if jour == split_le else 1.0,
                )
            )
        jour += timedelta(days=1)
    return resultat


class FakeProvider:
    def __init__(self, series=None, erreurs=None, erreurs_info=None):
        self.series = series or {}
        self.erreurs = erreurs or {}
        self.erreurs_info = erreurs_info or {}
        self.fenetres: list[tuple[str, date, date]] = []

    def get_security_info(self, ticker: str) -> SecurityInfo:
        if ticker in self.erreurs_info:
            raise self.erreurs_info[ticker]
        return SecurityInfo(ticker=ticker, name=f"{ticker} Corp", exchange="NASDAQ")

    def get_daily_adjusted(self, ticker: str, start: date, end: date):
        self.fenetres.append((ticker, start, end))
        if ticker in self.erreurs:
            raise self.erreurs[ticker]
        if start > end:
            return []
        return [b for b in self.series.get(ticker, []) if start <= b.date <= end]

    def fenetres_de(self, ticker: str):
        return [(s, e) for t, s, e in self.fenetres if t == ticker]


@pytest.fixture
def conn(tmp_path):
    chemin = tmp_path / "test.sqlite"
    init_db(chemin)
    connexion = connect(chemin)
    yield connexion
    connexion.close()


def compte_prix(conn, ticker: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) AS n FROM prices WHERE ticker = ?", (ticker,)
    ).fetchone()["n"]


# ------------------------------------------------------------------ Backfill --


def test_le_backfill_ecrit_les_seances(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 5)})
    report = backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    assert compte_prix(conn, "AAPL") == 5
    assert report.results[0].status == OK
    assert report.rows == 5


def test_le_backfill_stocke_adj_close_et_close_separement(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 1, prix=200.0)})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    ligne = conn.execute("SELECT close, adj_close FROM prices").fetchone()
    assert ligne["close"] == 200.0
    assert ligne["adj_close"] == 100.0


def test_le_backfill_demande_la_profondeur_voulue(conn):
    p = FakeProvider({"AAPL": []})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    (debut, fin), = p.fenetres_de("AAPL")
    assert debut == date(2021, 9, 9), "cinq ans avant aujourd'hui"
    assert fin == AUJOURD_HUI


def test_le_backfill_est_idempotent(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 5)})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    assert compte_prix(conn, "AAPL") == 5, "rejouer ne doit pas dupliquer"


def test_les_secteurs_du_seed_sont_ecrits(conn):
    p = FakeProvider({t: [] for t in ("AAPL", "JPM", "SPY")})
    backfill(["AAPL", "JPM", "SPY"], provider=p, conn=conn, today=AUJOURD_HUI)

    secteurs = {
        r["ticker"]: r["sector"]
        for r in conn.execute("SELECT ticker, sector FROM securities")
    }
    assert secteurs["AAPL"] == "Information Technology"
    assert secteurs["JPM"] == "Financials"
    assert secteurs["SPY"] is None, "un ETF indiciel n'a pas de secteur propre"


def test_l_univers_de_dev_couvre_les_quatorze_titres():
    assert len(DEV_UNIVERSE) == 14
    assert DEV_UNIVERSE["SPY"] is None
    assert all(v for t, v in DEV_UNIVERSE.items() if t != "SPY")


# ---------------------------------------------------------------- Rattrapage --


def test_le_rattrapage_repart_de_la_derniere_seance(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 5)})
    backfill(["AAPL"], provider=p, conn=conn, today=date(2026, 9, 5))
    derniere = last_stored_date(conn, "AAPL")

    refresh(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    debut, fin = p.fenetres_de("AAPL")[-1]
    assert debut == derniere, "on réécrit la dernière séance pour capter sa révision"
    assert fin == AUJOURD_HUI


def test_le_rattrapage_ne_laisse_pas_de_trou_apres_une_semaine_off(conn):
    # La machine n'a pas tourné depuis dix jours : la fenêtre doit couvrir tout
    # l'intervalle, pas seulement la veille.
    p = FakeProvider({"AAPL": barres(date(2026, 8, 24), 20)})
    backfill(["AAPL"], provider=p, conn=conn, today=date(2026, 8, 28))
    avant = compte_prix(conn, "AAPL")

    refresh(["AAPL"], provider=p, conn=conn, today=date(2026, 9, 9))

    debut, fin = p.fenetres_de("AAPL")[-1]
    assert (fin - debut).days >= 10
    assert compte_prix(conn, "AAPL") > avant
    dates = [
        r["date"] for r in conn.execute("SELECT date FROM prices ORDER BY date")
    ]
    assert dates == sorted(set(dates)), "aucun doublon ni désordre"


def test_le_rattrapage_sur_base_vide_fait_un_backfill_complet(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 3)})
    refresh(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    debut, _ = p.fenetres_de("AAPL")[0]
    assert debut == years_ago(BACKFILL_YEARS, AUJOURD_HUI)


def test_le_rattrapage_d_une_base_a_jour_n_ecrit_rien(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 5)})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    report = refresh(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    assert compte_prix(conn, "AAPL") == 5
    assert report.results[0].status in (OK, A_JOUR)


def test_un_split_declenche_une_reprise_complete(conn):
    # Tiingo retraite tout l'historique après un split : sans reprise complète,
    # les adj_close déjà en base resteraient sur l'ancienne échelle.
    series = barres(date(2026, 9, 1), 5) + barres(
        date(2026, 9, 8), 2, split_le=date(2026, 9, 8)
    )
    p = FakeProvider({"AAPL": series})
    backfill(["AAPL"], provider=p, conn=conn, today=date(2026, 9, 5))
    appels_avant = len(p.fenetres_de("AAPL"))

    refresh(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    fenetres = p.fenetres_de("AAPL")
    assert len(fenetres) == appels_avant + 2, "un rattrapage puis une reprise complète"
    debut_reprise, _ = fenetres[-1]
    assert debut_reprise == years_ago(BACKFILL_YEARS, AUJOURD_HUI)


def test_sans_split_il_n_y_a_pas_de_reprise(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 7)})
    backfill(["AAPL"], provider=p, conn=conn, today=date(2026, 9, 3))
    appels_avant = len(p.fenetres_de("AAPL"))

    refresh(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    assert len(p.fenetres_de("AAPL")) == appels_avant + 1


# ----------------------------------------------------- Intégrité du schéma --


def test_reenregistrer_un_titre_ne_detruit_pas_son_historique(conn):
    # Piège du schéma : prices a un ON DELETE CASCADE sur securities. Un
    # INSERT OR REPLACE sur securities supprimerait la ligne avant de la
    # réinsérer et emporterait tout l'historique. D'où l'UPSERT.
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 5)})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    assert compte_prix(conn, "AAPL") == 5

    upsert_security(conn, "AAPL", "Apple Inc (renommé)", "Information Technology")

    assert compte_prix(conn, "AAPL") == 5, "l'historique doit survivre au réenregistrement"
    assert (
        conn.execute("SELECT name FROM securities").fetchone()["name"]
        == "Apple Inc (renommé)"
    )


def test_un_secteur_deja_saisi_survit_a_un_reenregistrement_sans_secteur(conn):
    upsert_security(conn, "TSLA", "Tesla", "Consumer Discretionary")
    upsert_security(conn, "TSLA", "Tesla Inc", None)

    ligne = conn.execute("SELECT name, sector FROM securities").fetchone()
    assert ligne["sector"] == "Consumer Discretionary"
    assert ligne["name"] == "Tesla Inc"


# ------------------------------------------------------ Chargement à la demande --


def test_ensure_ticker_charge_un_titre_absent(conn):
    p = FakeProvider({"TSLA": barres(date(2026, 9, 1), 4)})
    report = ensure_ticker("tsla", provider=p, conn=conn, today=AUJOURD_HUI)

    assert compte_prix(conn, "TSLA") == 4
    assert report.results[0].status == OK
    ligne = conn.execute("SELECT ticker, sector FROM securities").fetchone()
    assert ligne["ticker"] == "TSLA"
    assert ligne["sector"] is None, "hors univers de dev, le secteur reste à saisir"


def test_ensure_ticker_ne_recharge_pas_un_titre_deja_present(conn):
    p = FakeProvider({"TSLA": barres(date(2026, 9, 1), 4)})
    ensure_ticker("TSLA", provider=p, conn=conn, today=AUJOURD_HUI)
    appels = len(p.fenetres_de("TSLA"))

    ensure_ticker("TSLA", provider=p, conn=conn, today=AUJOURD_HUI)

    assert len(p.fenetres_de("TSLA")) == appels, "pas d'appel inutile sur le quota"
    assert compte_prix(conn, "TSLA") == 4


def test_ensure_ticker_signale_un_ticker_inconnu(conn):
    p = FakeProvider(erreurs_info={"ZZZZ": UnknownTickerError("inconnu")})
    report = ensure_ticker("ZZZZ", provider=p, conn=conn, today=AUJOURD_HUI)

    assert report.results[0].status == ECHEC
    assert compte_prix(conn, "ZZZZ") == 0


# ------------------------------------------------------------ Robustesse --


def test_un_titre_en_echec_n_interrompt_pas_les_autres(conn):
    p = FakeProvider(
        series={"AAPL": barres(date(2026, 9, 1), 3), "MSFT": barres(date(2026, 9, 1), 3)},
        erreurs={"JPM": ProviderError("réponse illisible")},
    )
    report = backfill(["AAPL", "JPM", "MSFT"], provider=p, conn=conn, today=AUJOURD_HUI)

    statuts = {r.ticker: r.status for r in report.results}
    assert statuts == {"AAPL": OK, "JPM": ECHEC, "MSFT": OK}
    assert compte_prix(conn, "AAPL") == 3
    assert compte_prix(conn, "MSFT") == 3


def test_un_quota_epuise_arrete_le_passage(conn):
    # Le quota est global au compte : insister sur les titres suivants ne ferait
    # qu'échouer plus vite.
    p = FakeProvider(
        series={"AAPL": barres(date(2026, 9, 1), 3)},
        erreurs={"JPM": RateLimitError("quota épuisé")},
    )
    report = backfill(["AAPL", "JPM", "MSFT"], provider=p, conn=conn, today=AUJOURD_HUI)

    statuts = {r.ticker: r.status for r in report.results}
    assert statuts["AAPL"] == OK
    assert statuts["JPM"] == ECHEC
    assert statuts["MSFT"] == IGNORE
    assert p.fenetres_de("MSFT") == [], "aucun appel après l'épuisement du quota"


def test_le_bilan_liste_les_echecs(conn):
    p = FakeProvider(erreurs={"JPM": ProviderError("boom")})
    report = backfill(["JPM"], provider=p, conn=conn, today=AUJOURD_HUI)

    assert len(report.failures) == 1
    assert "JPM" in report.summary()


# --------------------------------------------------------------- Calendrier --


def test_years_ago_gere_le_29_fevrier():
    assert years_ago(1, date(2024, 2, 29)) == date(2023, 2, 28)


def test_years_ago_cas_courant():
    assert years_ago(5, date(2026, 9, 9)) == date(2021, 9, 9)
