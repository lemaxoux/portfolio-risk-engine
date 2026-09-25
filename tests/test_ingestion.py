"""Tests de l'ingestion, sur un fournisseur simulé.

Le double implémente le contrat de `MarketDataProvider` sans aucune couche
HTTP : ces tests ne touchent ni le réseau ni le quota Tiingo, et enregistrent
les fenêtres demandées pour qu'on puisse vérifier ce qui a été réclamé.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pytest

from backend import data_provider
from backend.data_provider import HOURLY_CALL_BUDGET
from backend.ingestion.__main__ import main as ingestion_main

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
    rebuild,
    refresh,
    upsert_security,
)
from backend.ingestion.universe import BACKFILL_START, DEV_UNIVERSE

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
        self.appels_info: list[str] = []

    def get_security_info(self, ticker: str) -> SecurityInfo:
        self.appels_info.append(ticker)
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


def test_le_backfill_part_de_la_date_d_ancrage(conn):
    p = FakeProvider({"AAPL": []})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    (debut, fin), = p.fenetres_de("AAPL")
    assert debut == BACKFILL_START
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
    assert debut == BACKFILL_START


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
    assert debut_reprise == BACKFILL_START


def test_sans_split_il_n_y_a_pas_de_reprise(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 7)})
    backfill(["AAPL"], provider=p, conn=conn, today=date(2026, 9, 3))
    appels_avant = len(p.fenetres_de("AAPL"))

    refresh(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    assert len(p.fenetres_de("AAPL")) == appels_avant + 1


# ---------------------------------------------------------------- Dividendes --
#
# Le défaut corrigé : à chaque dividende, le fournisseur recalcule TOUS les
# adj_close antérieurs au détachement. Le rattrapage réécrivait la dernière
# séance stockée sur la nouvelle base d'ajustement sans toucher à la veille,
# et le rendement de cette séance de jonction comptait le détachement comme
# une perte : KO au 2026-09-09, −1,51 % stocké contre −0,92 % réel.

# Cours bruts sur le modèle de KO : dividende de 0,53 détaché le 2026-09-15,
# rendement réel de −0,92 % le 2026-09-09 (le 2026-09-07 est férié).
COURS_KO = {
    date(2026, 9, 4): 70.20,
    date(2026, 9, 8): 70.00,
    date(2026, 9, 9): 70.00 * (1 - 0.0092),
    date(2026, 9, 10): 69.60,
    date(2026, 9, 11): 69.90,
    date(2026, 9, 14): 70.10,
    date(2026, 9, 15): 69.70,
    date(2026, 9, 16): 69.80,
}
DETACHEMENT = date(2026, 9, 15)
DIVIDENDE = 0.53
JONCTION = date(2026, 9, 9)


class FournisseurAjuste(FakeProvider):
    """Réajuste l'historique à chaque dividende, à la manière de Tiingo.

    L'`adj_close` d'une séance est son cours brut multiplié, pour chaque
    dividende détaché APRÈS elle et déjà connu, par (1 − dividende / clôture
    de la veille du détachement). Le fournisseur ne connaît un dividende qu'à
    partir de sa date de détachement : `aujourd_hui` fixe ce qu'il sait au
    moment de l'appel.

    `masquer_dividendes` retire `div_cash` des séances sans rien changer à
    l'ajustement : c'est ce que voyait l'ingestion avant de lire ce champ.
    """

    def __init__(self, cours, dividendes, *, masquer_dividendes=False, reprise_vide=False):
        super().__init__()
        self.cours = cours
        self.dividendes = dividendes
        self.masquer_dividendes = masquer_dividendes
        self.reprise_vide = reprise_vide
        self.aujourd_hui = max(cours)

    def get_daily_adjusted(self, ticker, start, end):
        self.fenetres.append((ticker, start, end))
        if self.reprise_vide and start <= BACKFILL_START and len(self.fenetres) > 1:
            return []
        jours = sorted(j for j in self.cours if j <= self.aujourd_hui)
        connus = {j: m for j, m in self.dividendes.items() if j <= self.aujourd_hui}
        resultat = []
        for jour in jours:
            if not start <= jour <= end:
                continue
            facteur = 1.0
            for detachement, montant in connus.items():
                if detachement > jour:
                    veille = max(j for j in jours if j < detachement)
                    facteur *= 1 - montant / self.cours[veille]
            resultat.append(
                DailyBar(
                    date=jour,
                    open=None,
                    high=None,
                    low=None,
                    close=self.cours[jour],
                    adj_close=self.cours[jour] * facteur,
                    volume=None,
                    div_cash=0.0 if self.masquer_dividendes else connus.get(jour, 0.0),
                )
            )
        return resultat


def rendement_stocke(conn, ticker: str, jour: date) -> float:
    """Rendement simple de `jour`, lu sur les deux derniers adj_close en base."""
    (dernier, apres), (_, avant) = conn.execute(
        "SELECT date, adj_close FROM prices WHERE ticker = ? AND date <= ? "
        "ORDER BY date DESC LIMIT 2",
        (ticker, jour.isoformat()),
    ).fetchall()
    assert dernier == jour.isoformat()
    return apres / avant - 1


def rattraper_ko(conn, *, jusqu_au: date = date(2026, 9, 16), **options):
    """Backfill au 2026-09-09, puis rattrapage à `jusqu_au`."""
    p = FournisseurAjuste(COURS_KO, {DETACHEMENT: DIVIDENDE}, **options)
    p.aujourd_hui = JONCTION
    backfill(["KO"], provider=p, conn=conn, today=JONCTION)
    p.aujourd_hui = jusqu_au
    rapport = refresh(["KO"], provider=p, conn=conn, today=jusqu_au)
    return p, rapport


def test_un_dividende_dans_la_fenetre_declenche_une_reprise_complete(conn):
    p, rapport = rattraper_ko(conn)

    assert p.fenetres_de("KO") == [
        (BACKFILL_START, JONCTION),         # backfill
        (JONCTION, date(2026, 9, 16)),      # rattrapage : voit le dividende
        (BACKFILL_START, date(2026, 9, 16)),  # reprise complète
    ]
    assert rapport.results[0].status == OK


def test_apres_reprise_la_seance_de_jonction_porte_son_rendement_reel(conn):
    rattraper_ko(conn)

    assert rendement_stocke(conn, "KO", JONCTION) == pytest.approx(-0.0092, abs=1e-12)


def test_temoin_sans_lire_le_dividende_la_jonction_porte_l_ecart_de_base(conn):
    # Le défaut reproduit, pour que le test précédent prouve quelque chose :
    # sans div_cash, aucune reprise, et le rendement de jonction absorbe le
    # facteur d'ajustement du dividende.
    p, _ = rattraper_ko(conn, masquer_dividendes=True)

    assert len(p.fenetres_de("KO")) == 2, "aucune reprise complète"
    facteur = 1 - DIVIDENDE / COURS_KO[date(2026, 9, 14)]
    ecart = (1 - 0.0092) * facteur - 1
    assert rendement_stocke(conn, "KO", JONCTION) == pytest.approx(ecart, abs=1e-12)
    assert ecart < -0.0092 - 0.005, "l'écart est de l'ordre du rendement du coupon"


def test_apres_reprise_le_detachement_rapporte_le_rendement_total(conn):
    rattraper_ko(conn)

    veille = COURS_KO[date(2026, 9, 14)]
    stocke = rendement_stocke(conn, "KO", DETACHEMENT)
    # L'ajustement multiplicatif rapporte le cours du jour à la veille diminuée
    # du dividende : exact par construction...
    assert stocke == pytest.approx(COURS_KO[DETACHEMENT] / (veille - DIVIDENDE) - 1, abs=1e-12)
    # ... et égal au rendement total (dividende réinvesti) au second ordre près.
    total = (COURS_KO[DETACHEMENT] + DIVIDENDE) / veille - 1
    assert stocke == pytest.approx(total, abs=5e-5)
    assert stocke > 0, "le détachement n'est pas compté comme une perte"


def test_sans_dividende_ni_split_le_rattrapage_est_inchange(conn):
    # Rattrapage au 2026-09-14, veille du détachement : rien à reprendre.
    p, _ = rattraper_ko(conn, jusqu_au=date(2026, 9, 14))
    avant_jonction = conn.execute(
        "SELECT date, adj_close FROM prices WHERE date < ? ORDER BY date",
        (JONCTION.isoformat(),),
    ).fetchall()

    assert p.fenetres_de("KO")[1:] == [(JONCTION, date(2026, 9, 14))]
    assert [tuple(r) for r in avant_jonction] == [
        ("2026-09-04", COURS_KO[date(2026, 9, 4)]),
        ("2026-09-08", COURS_KO[date(2026, 9, 8)]),
    ], "les séances antérieures à la fenêtre ne sont pas réécrites"
    assert compte_prix(conn, "KO") == 6


def test_la_reprise_efface_une_seance_que_le_fournisseur_ne_renvoie_plus(conn):
    # Une ligne laissée sur l'ancienne base d'ajustement fausserait deux
    # rendements : celui du jour et celui du lendemain.
    p = FournisseurAjuste(COURS_KO, {DETACHEMENT: DIVIDENDE})
    p.aujourd_hui = JONCTION
    backfill(["KO"], provider=p, conn=conn, today=JONCTION)
    conn.execute(
        "INSERT INTO prices (ticker, date, close, adj_close) "
        "VALUES ('KO', '2026-09-05', 70.1, 70.1)"
    )

    p.aujourd_hui = date(2026, 9, 16)
    refresh(["KO"], provider=p, conn=conn, today=p.aujourd_hui)

    dates = [r["date"] for r in conn.execute("SELECT date FROM prices ORDER BY date")]
    assert "2026-09-05" not in dates
    assert len(dates) == len(COURS_KO)


def test_une_reprise_vide_conserve_l_historique(conn):
    p, rapport = rattraper_ko(conn, reprise_vide=True)

    assert rapport.results[0].status == ECHEC
    assert "historique en base conservé" in rapport.results[0].detail
    assert compte_prix(conn, "KO") == 3, "le rattrapage fautif est annulé avec la reprise"


def test_la_reprise_remonte_a_la_premiere_seance_si_elle_precede_l_ancrage(conn):
    # Titre chargé avec un --start antérieur à l'ancrage : ce qui resterait en
    # deçà de la reprise resterait sur l'ancienne base.
    anciens = {date(2004, 6, 1): 40.0, date(2004, 6, 2): 40.5}
    p = FournisseurAjuste({**anciens, **COURS_KO}, {DETACHEMENT: DIVIDENDE})
    p.aujourd_hui = JONCTION
    backfill(["KO"], start=date(2004, 6, 1), provider=p, conn=conn, today=JONCTION)

    p.aujourd_hui = date(2026, 9, 16)
    refresh(["KO"], provider=p, conn=conn, today=p.aujourd_hui)

    debut_reprise, _ = p.fenetres_de("KO")[-1]
    assert debut_reprise == date(2004, 6, 1)


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


# ------------------------------------------------------------ Date d'ancrage --


def test_l_ancrage_ne_glisse_pas_avec_le_temps(conn):
    """Le defaut de la fenetre glissante, verrouille par un test.

    Une profondeur exprimee en annees rendait des debuts differents selon le
    jour d'execution, et un scenario historique sortait de la fenetre sans que
    rien ne change dans le code. L'ancrage rend la fenetre independante de la
    date du jour.
    """
    p = FakeProvider({"AAPL": []})
    backfill(["AAPL"], provider=p, conn=conn, today=date(2026, 9, 9))
    backfill(["AAPL"], provider=p, conn=conn, today=date(2031, 9, 9))

    debuts = {debut for debut, _ in p.fenetres_de("AAPL")}
    assert debuts == {BACKFILL_START}, "cinq ans plus tard, le debut est le meme"


def test_l_ancrage_couvre_les_trois_scenarios_de_stress():
    # Ce que 5 ans glissants ne garantissaient plus.
    for evenement in (date(2008, 9, 15), date(2020, 3, 16), date(2022, 6, 13)):
        assert BACKFILL_START < evenement, f"{evenement} hors de la fenetre"


def test_un_titre_introduit_apres_l_ancrage_entre_avec_ce_qui_existe(conn):
    # Le fournisseur renvoie ce qu'il a ; l'absence d'historique avant
    # l'introduction en bourse n'est pas une erreur.
    p = FakeProvider({"NEW": barres(date(2024, 3, 1), 10)})
    report = backfill(["NEW"], provider=p, conn=conn, today=AUJOURD_HUI)

    debut, _ = p.fenetres_de("NEW")[0]
    assert debut == BACKFILL_START, "on demande large"
    assert report.results[0].status == OK
    premiere = conn.execute("SELECT MIN(date) AS d FROM prices").fetchone()["d"]
    assert premiere == "2024-03-01", "et on stocke ce qui existe reellement"


# ------------------------------------------------------------------- Quota --


def test_les_metadonnees_ne_sont_pas_redemandees_pour_un_titre_connu(conn):
    # Un appel par titre economise, soit la moitie du budget d'un backfill.
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 3)})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    assert p.appels_info == ["AAPL"]

    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    assert p.appels_info == ["AAPL"], "le second passage ne redemande rien"


def test_refresh_metadata_force_le_rappel(conn):
    p = FakeProvider({"AAPL": barres(date(2026, 9, 1), 3)})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    backfill(
        ["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI, refresh_metadata=True
    )
    assert p.appels_info == ["AAPL", "AAPL"]


def test_le_secteur_reste_applique_meme_sans_appel_de_metadonnees(conn):
    p = FakeProvider({"AAPL": []})
    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)
    conn.execute("UPDATE securities SET sector = NULL")

    backfill(["AAPL"], provider=p, conn=conn, today=AUJOURD_HUI)

    secteur = conn.execute("SELECT sector FROM securities").fetchone()["sector"]
    assert secteur == "Information Technology"


# ----------------------------------------------------------- Reconstruction --
#
# `rebuild` répare une base écrite par l'ancien rattrapage. La base de départ
# est produite par ce rattrapage lui-même (dividende masqué), pas écrite à la
# main : c'est l'état exact qu'il laisse.


class ParTitre(FakeProvider):
    """Un fournisseur ajusté par titre, derrière une seule interface."""

    def __init__(self, fournisseurs):
        super().__init__()
        self.fournisseurs = fournisseurs

    def get_daily_adjusted(self, ticker, start, end):
        self.fenetres.append((ticker, start, end))
        return self.fournisseurs[ticker].get_daily_adjusted(ticker, start, end)


COURS_CALME = {jour: 50.0 + i for i, jour in enumerate(sorted(COURS_KO))}


def base_a_reparer(chemin):
    """Base où KO porte la jonction fausse, plus un portefeuille et ses positions."""
    init_db(chemin)
    with closing(connect(chemin)) as c:
        rattraper_ko(c, masquer_dividendes=True)
        p = FournisseurAjuste(COURS_CALME, {})
        backfill(["AAPL"], provider=p, conn=c, today=date(2026, 9, 16))
        with c:
            c.execute(
                "INSERT INTO portfolios (owner, name, updated_at) "
                "VALUES ('local', 'Principal', '2026-09-21')"
            )
            c.executemany(
                "INSERT INTO positions (portfolio_id, ticker, quantity, cost_basis) "
                "VALUES (1, ?, ?, ?)",
                [("KO", 120, 61.5), ("AAPL", 40, None)],
            )
    return chemin


def fournisseur_a_jour():
    return ParTitre(
        {
            "KO": FournisseurAjuste(COURS_KO, {DETACHEMENT: DIVIDENDE}),
            "AAPL": FournisseurAjuste(COURS_CALME, {}),
        }
    )


def contenu(chemin, table):
    with closing(sqlite3.connect(chemin)) as c:
        return c.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()


@pytest.fixture
def base_reelle_simulee(tmp_path, monkeypatch):
    """Une base à réparer, à la place de data/mx_risk.sqlite pour la commande."""
    chemin = base_a_reparer(tmp_path / "mx_risk.sqlite")
    monkeypatch.setenv("MX_RISK_DB_PATH", str(chemin))
    fournisseur = fournisseur_a_jour()
    data_provider.set_provider(fournisseur)
    yield chemin, fournisseur
    data_provider.set_provider(None)


def test_la_base_a_reparer_porte_bien_la_jonction_fausse(tmp_path):
    chemin = base_a_reparer(tmp_path / "b.sqlite")
    with closing(connect(chemin)) as c:
        assert rendement_stocke(c, "KO", JONCTION) < -0.0092 - 0.005


def test_rebuild_repare_la_seance_de_jonction(base_reelle_simulee):
    chemin, _ = base_reelle_simulee

    assert ingestion_main(["rebuild"]) == 0

    with closing(connect(chemin)) as c:
        assert rendement_stocke(c, "KO", JONCTION) == pytest.approx(-0.0092, abs=1e-12)


def test_rebuild_sauvegarde_la_base_avant_d_ecrire(base_reelle_simulee):
    chemin, _ = base_reelle_simulee
    prix_avant = contenu(chemin, "prices")

    ingestion_main(["rebuild"])

    (sauvegarde,) = chemin.parent.glob("backup-*.sqlite")
    assert sauvegarde.name == f"backup-{date.today().isoformat()}.sqlite"
    assert contenu(sauvegarde, "prices") == prix_avant, "l'état d'AVANT la réparation"
    assert contenu(chemin, "prices") != prix_avant


def test_une_sauvegarde_existante_n_est_jamais_ecrasee(base_reelle_simulee):
    chemin, _ = base_reelle_simulee
    premiere = chemin.parent / f"backup-{date.today().isoformat()}.sqlite"
    premiere.write_bytes(b"etat d'avant la premiere reparation")

    ingestion_main(["rebuild"])

    assert premiere.read_bytes() == b"etat d'avant la premiere reparation"
    assert (chemin.parent / f"backup-{date.today().isoformat()}-2.sqlite").exists()


def test_rebuild_ne_touche_ni_portfolios_ni_positions(base_reelle_simulee):
    chemin, _ = base_reelle_simulee
    avant = {t: contenu(chemin, t) for t in ("portfolios", "positions", "securities")}

    ingestion_main(["rebuild"])

    assert {t: contenu(chemin, t) for t in avant} == avant
    assert avant["positions"], "le test porte sur des positions réelles, pas sur du vide"


def test_rebuild_n_ecrit_que_dans_prices(tmp_path):
    # Plus fort qu'une comparaison avant/après : l'autoriseur de SQLite voit
    # chaque écriture tentée, même une qui réécrirait la même valeur.
    chemin = base_a_reparer(tmp_path / "b.sqlite")
    ecritures = set()

    def espion(action, table, *_):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            ecritures.add(table)
        return sqlite3.SQLITE_OK

    with closing(connect(chemin)) as c:
        c.set_authorizer(espion)
        rebuild(provider=fournisseur_a_jour(), conn=c, today=date(2026, 9, 16))

    assert ecritures == {"prices"}


def test_rebuild_fait_un_appel_par_titre_et_l_affiche(base_reelle_simulee, capsys):
    _, fournisseur = base_reelle_simulee

    ingestion_main(["rebuild"])

    sortie = capsys.readouterr().out
    assert len(fournisseur.fenetres) == 2, "un appel par titre, aucun de métadonnées"
    assert fournisseur.appels_info == []
    assert f"2 appels prévus, sous la limite de {HOURLY_CALL_BUDGET} par heure" in sortie
    assert "2 appels au fournisseur" in sortie


def test_rebuild_recharge_depuis_l_ancrage(base_reelle_simulee):
    _, fournisseur = base_reelle_simulee

    ingestion_main(["rebuild"])

    assert {debut for _, debut, _ in fournisseur.fenetres} == {BACKFILL_START}


def test_rebuild_refuse_au_dela_du_budget_horaire(base_reelle_simulee, capsys):
    chemin, fournisseur = base_reelle_simulee
    with closing(connect(chemin)) as c, c:
        c.executemany(
            "INSERT INTO securities (ticker, name) VALUES (?, ?)",
            [(f"T{i:03d}", "Titre") for i in range(HOURLY_CALL_BUDGET)],
        )

    assert ingestion_main(["rebuild"]) == 1

    assert fournisseur.fenetres == [], "aucun appel lancé"
    assert list(chemin.parent.glob("backup-*.sqlite")) == [], "ni sauvegarde"
    assert "--tickers" in capsys.readouterr().out


def test_rebuild_par_lot_ne_recharge_que_les_titres_demandes(base_reelle_simulee):
    _, fournisseur = base_reelle_simulee

    assert ingestion_main(["rebuild", "--tickers", "ko"]) == 0

    assert [t for t, _, _ in fournisseur.fenetres] == ["KO"]


def test_rebuild_signale_un_titre_absent_de_la_base(base_reelle_simulee, capsys):
    _, fournisseur = base_reelle_simulee

    assert ingestion_main(["rebuild", "--tickers", "KO", "TSLA"]) == 1

    assert [t for t, _, _ in fournisseur.fenetres] == ["KO"]
    assert "TSLA" in capsys.readouterr().out
