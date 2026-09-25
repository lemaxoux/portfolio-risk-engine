"""Ingestion des prix en base : backfill, rattrapage, chargement à la demande.

Ce module ne connaît pas Tiingo. Il passe par `backend.data_provider`, qui lui
rend des `DailyBar`, et ne manipule par ailleurs que le schéma SQLite.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from backend.data_provider import (
    DailyBar,
    MarketDataProvider,
    ProviderError,
    RateLimitError,
    UnknownTickerError,
    get_provider,
)
from backend.db.init_db import connect
from backend.ingestion.universe import BACKFILL_START, DEV_UNIVERSE

logger = logging.getLogger(__name__)

OK = "ok"
A_JOUR = "à jour"
ECHEC = "échec"
IGNORE = "ignoré"


@dataclass
class TickerResult:
    ticker: str
    status: str
    rows: int = 0
    detail: str = ""


@dataclass
class IngestionReport:
    """Bilan d'un passage d'ingestion, ticker par ticker."""

    results: list[TickerResult] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return sum(r.rows for r in self.results)

    @property
    def failures(self) -> list[TickerResult]:
        return [r for r in self.results if r.status in (ECHEC, IGNORE)]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.status in (OK, A_JOUR))
        lignes = [f"{ok}/{len(self.results)} titres traités, {self.rows} séances écrites"]
        for r in self.failures:
            lignes.append(f"  {r.ticker} : {r.status} — {r.detail}")
        return "\n".join(lignes)


# ----------------------------------------------------------------- Écritures --

_INSERT_PRICES = """
INSERT OR REPLACE INTO prices
    (ticker, date, open, high, low, close, adj_close, volume)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

# Volontairement un UPSERT et non un INSERT OR REPLACE : REPLACE supprimerait
# la ligne existante avant de la réinsérer, et le ON DELETE CASCADE de prices
# emporterait tout l'historique du titre au passage. COALESCE protège en outre
# un secteur déjà saisi contre un réenregistrement qui le laisserait à NULL.
_UPSERT_SECURITY = """
INSERT INTO securities (ticker, name, sector)
VALUES (?, ?, ?)
ON CONFLICT(ticker) DO UPDATE SET
    name   = excluded.name,
    sector = COALESCE(excluded.sector, securities.sector)
"""


def store_bars(conn: sqlite3.Connection, ticker: str, bars: list[DailyBar]) -> int:
    """Écrit les séances et renvoie le nombre de lignes touchées.

    La clé primaire (ticker, date) rend l'opération idempotente : rejouer une
    fenêtre déjà chargée réécrit les mêmes lignes au lieu d'en créer. C'est ce
    qui permet de relancer un backfill interrompu sans réfléchir.
    """
    if not bars:
        return 0
    conn.executemany(
        _INSERT_PRICES,
        [
            (
                ticker,
                bar.date.isoformat(),
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.adj_close,
                bar.volume,
            )
            for bar in bars
        ],
    )
    return len(bars)


def upsert_security(
    conn: sqlite3.Connection, ticker: str, name: str, sector: str | None
) -> None:
    conn.execute(_UPSERT_SECURITY, (ticker, name, sector))


def last_stored_date(conn: sqlite3.Connection, ticker: str) -> date | None:
    """Dernière séance en base pour ce titre, ou None si aucune."""
    row = conn.execute(
        "SELECT MAX(date) AS derniere FROM prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    valeur = row["derniere"] if row else None
    return date.fromisoformat(valeur) if valeur else None


def first_stored_date(conn: sqlite3.Connection, ticker: str) -> date | None:
    """Première séance en base pour ce titre, ou None si aucune."""
    row = conn.execute(
        "SELECT MIN(date) AS premiere FROM prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    valeur = row["premiere"] if row else None
    return date.fromisoformat(valeur) if valeur else None


# ------------------------------------------------------------- Un seul titre --


def est_enregistre(conn: sqlite3.Connection, ticker: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM securities WHERE ticker = ?", (ticker,)
        ).fetchone()
        is not None
    )


def _register(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    ticker: str,
    sector: str | None,
    *,
    refresh_metadata: bool = False,
) -> None:
    """Crée ou met à jour la ligne `securities`.

    Prérequis de toute écriture de prix : la clé étrangère de `prices` la
    réclame.

    Les métadonnées ne sont redemandées que pour un titre inconnu. Elles ne
    changent quasiment jamais, alors qu'elles coûtent un appel par titre — la
    moitié du budget d'un backfill sur les 50 appels/heure du plan gratuit. Le
    secteur, lui, vient de la table locale et est réappliqué à chaque passage.
    """
    if not refresh_metadata and est_enregistre(conn, ticker):
        conn.execute(
            "UPDATE securities SET sector = COALESCE(?, sector) WHERE ticker = ?",
            (sector, ticker),
        )
        logger.debug("%s : déjà connu, métadonnées non redemandées", ticker)
        return

    info = provider.get_security_info(ticker)
    upsert_security(conn, ticker, info.name, sector)
    logger.debug("%s : %s (%s)", ticker, info.name, info.exchange or "place inconnue")


def operations_sur_titre(bars: list[DailyBar]) -> list[str]:
    """Décrit les séances qui ont fait retraiter l'historique ajusté du titre.

    Un split comme un détachement de dividende font recalculer au fournisseur
    TOUS les `adj_close` antérieurs à la séance. Une liste vide veut dire
    qu'aucune séance récupérée ne donne de raison de croire que l'historique
    en base a changé de base d'ajustement.
    """
    raisons: list[str] = []
    for bar in bars:
        if bar.split_factor != 1.0:
            raisons.append(f"split de facteur {bar.split_factor:g} le {bar.date}")
        if bar.div_cash != 0.0:
            raisons.append(f"dividende de {bar.div_cash:g} le {bar.date}")
    return raisons


def _fetch_and_store(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    ticker: str,
    start: date,
    end: date,
) -> tuple[int, list[str]]:
    """Récupère une fenêtre et l'écrit.

    Renvoie (lignes écrites, opérations sur titre trouvées dans la fenêtre).
    """
    bars = provider.get_daily_adjusted(ticker, start, end)
    rows = store_bars(conn, ticker, bars)
    return rows, operations_sur_titre(bars)


def replace_history(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    ticker: str,
    start: date,
    end: date,
) -> int:
    """Remplace d'un bloc tout l'historique du titre par celui du fournisseur.

    Le fournisseur recalcule les `adj_close` à chaque split et à chaque
    dividende. Un historique rechargé par morceaux mélangerait deux bases
    d'ajustement, et le rendement de la séance de jonction mesurerait l'écart
    entre elles au lieu du rendement réel. Tout est donc relu en un appel, et
    les lignes existantes sont supprimées avant réécriture : une séance que le
    fournisseur ne renvoie plus ne doit pas survivre sur l'ancienne base.

    La reprise part de `start`, ou de la première séance en base si elle est
    plus ancienne (backfill lancé avec un `--start` antérieur) : ce qui
    resterait en deçà de la reprise resterait sur l'ancienne base.

    Une réponse vide ne supprime rien. Elle signale un fournisseur en défaut,
    pas un titre qui aurait perdu son historique.
    """
    premiere = first_stored_date(conn, ticker)
    debut = min(start, premiere) if premiere else start
    bars = provider.get_daily_adjusted(ticker, debut, end)
    if not bars:
        raise ProviderError(
            f"{ticker} : reprise complète vide depuis {debut}, historique en base conservé"
        )
    conn.execute("DELETE FROM prices WHERE ticker = ?", (ticker,))
    return store_bars(conn, ticker, bars)


# ---------------------------------------------------------------- Opérations --


def backfill(
    tickers: list[str] | None = None,
    *,
    start: date = BACKFILL_START,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
    refresh_metadata: bool = False,
) -> IngestionReport:
    """Charge l'historique de chaque titre depuis `start`.

    Un titre dont la cotation commence après `start` entre avec l'historique
    qui existe : le fournisseur renvoie ce qu'il a, sans erreur, et la commande
    `status` montre la couverture réelle obtenue titre par titre.

    Chaque titre est committé séparément : une interruption au neuvième titre
    laisse les huit premiers en base, et relancer reprend sans redemander ce
    qui est déjà là.
    """
    cibles = tickers or list(DEV_UNIVERSE)
    end = today or date.today()
    logger.info("Backfill de %d titres (%s → %s)", len(cibles), start, end)
    return _run(
        cibles,
        lambda c, p, t: _fetch_and_store(c, p, t, start, end)[0],
        provider=provider,
        conn=conn,
        refresh_metadata=refresh_metadata,
    )


def refresh(
    tickers: list[str] | None = None,
    *,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
    fallback_start: date = BACKFILL_START,
) -> IngestionReport:
    """Rattrape chaque titre depuis sa dernière séance connue jusqu'à `today`.

    Rattrapage et non « récupérer hier » : la machine ne tourne pas tous les
    jours, et une fenêtre calée sur la veille laisserait un trou à chaque
    journée manquée. La fenêtre part de la dernière date en base, pas du
    lendemain : réécrire cette séance ne coûte rien (clé primaire) et corrige
    une clôture récupérée en séance puis révisée depuis.

    Un split ou un dividende dans la fenêtre déclenche une reprise complète
    (`replace_history`), soit un appel de plus pour le titre concerné. Sans
    elle, la séance `derniere` revenait sur la nouvelle base d'ajustement et la
    veille restait sur l'ancienne : le rendement de jonction comptait le
    détachement comme une perte. Constaté sur KO au 2026-09-09 : −1,51 %
    stocké contre −0,92 % réel, pour un dividende de 0,53 détaché le
    2026-09-15.

    La séance `derniere` fait elle-même partie de la fenêtre examinée. Si elle
    porte l'opération, une reprise déjà faite au passage précédent est refaite :
    un appel de trop, jamais une donnée fausse. L'exclure manquerait le cas où
    le fournisseur publie l'opération après avoir servi la clôture.
    """
    end = today or date.today()

    def rattrapage(c: sqlite3.Connection, p: MarketDataProvider, ticker: str) -> int:
        derniere = last_stored_date(c, ticker)
        if derniere is None:
            logger.info("%s : aucune donnée en base, backfill complet", ticker)
            return _fetch_and_store(c, p, ticker, fallback_start, end)[0]

        rows, raisons = _fetch_and_store(c, p, ticker, derniere, end)
        if raisons:
            logger.warning(
                "%s : %s — historique ajusté périmé, reprise complète",
                ticker,
                " ; ".join(raisons),
            )
            rows = replace_history(c, p, ticker, fallback_start, end)
        return rows

    logger.info("Rattrapage jusqu'au %s", end)
    return _run(tickers or list(DEV_UNIVERSE), rattrapage, provider=provider, conn=conn)


def ensure_ticker(
    ticker: str,
    *,
    start: date = BACKFILL_START,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
) -> IngestionReport:
    """Charge à la demande un titre absent de la base.

    Sert quand un utilisateur saisit un ticker hors de l'univers de dev. La
    date d'ancrage est la même que celle du backfill, délibérément : deux titres
    chargés sur des fenêtres différentes donneraient des covariances estimées
    sur des périodes différentes selon la paire. Un titre introduit en bourse
    après `start` entre simplement avec l'historique qui existe.

    Le secteur reste NULL — Tiingo ne le fournit pas et personne ne l'a saisi.
    """
    cible = ticker.upper()
    end = today or date.today()

    def charger(c: sqlite3.Connection, p: MarketDataProvider, t: str) -> int:
        if last_stored_date(c, t) is not None:
            logger.info("%s : déjà en base, rien à charger", t)
            return 0
        return _fetch_and_store(c, p, t, start, end)[0]

    return _run([cible], charger, provider=provider, conn=conn, sectors={cible: None})


# ------------------------------------------------------------- Orchestration --


def _run(
    tickers: list[str],
    operation,
    *,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    sectors: dict[str, str | None] | None = None,
    refresh_metadata: bool = False,
) -> IngestionReport:
    """Applique `operation` à chaque titre en isolant les échecs.

    Un titre en échec n'interrompt pas les autres : sur quatorze titres, une
    réponse illisible sur un seul ne doit pas coûter le passage entier. Le
    dépassement de quota fait exception — le quota est global au compte, et
    insister ne ferait qu'échouer plus vite sur les titres restants.
    """
    fournisseur = provider or get_provider()
    secteurs = sectors if sectors is not None else DEV_UNIVERSE
    report = IngestionReport()

    proprietaire = conn is None
    connexion = conn or connect()
    try:
        quota_epuise = False
        for ticker in tickers:
            if quota_epuise:
                report.results.append(
                    TickerResult(ticker, IGNORE, detail="quota épuisé avant traitement")
                )
                continue
            try:
                _register(
                    connexion,
                    fournisseur,
                    ticker,
                    secteurs.get(ticker),
                    refresh_metadata=refresh_metadata,
                )
                rows = operation(connexion, fournisseur, ticker)
                connexion.commit()
                report.results.append(
                    TickerResult(ticker, OK if rows else A_JOUR, rows=rows)
                )
                logger.info(
                    "%s : %s", ticker, f"{rows} séances écrites" if rows else "à jour"
                )
            except RateLimitError as exc:
                connexion.rollback()
                quota_epuise = True
                report.results.append(TickerResult(ticker, ECHEC, detail=str(exc)))
                logger.error("%s : quota Tiingo épuisé, arrêt du passage", ticker)
            except (UnknownTickerError, ProviderError) as exc:
                connexion.rollback()
                report.results.append(TickerResult(ticker, ECHEC, detail=str(exc)))
                logger.error("%s : %s", ticker, exc)
    finally:
        if proprietaire:
            connexion.close()

    logger.info("Bilan — %s", report.summary())
    return report
