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
from backend.ingestion.universe import BACKFILL_YEARS, DEV_UNIVERSE

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


# ------------------------------------------------------------------ Fenêtres --


def years_ago(years: int, reference: date | None = None) -> date:
    """Même jour, `years` années plus tôt.

    Le 29 février est ramené au 28 : `date.replace` lèverait sinon ValueError
    une année sur quatre, faisant échouer un backfill au hasard du calendrier.
    """
    ref = reference or date.today()
    try:
        return ref.replace(year=ref.year - years)
    except ValueError:
        return ref.replace(year=ref.year - years, day=28)


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


# ------------------------------------------------------------- Un seul titre --


def _register(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    ticker: str,
    sector: str | None,
) -> None:
    """Crée ou met à jour la ligne `securities`.

    Prérequis de toute écriture de prix : la clé étrangère de `prices` la
    réclame.
    """
    info = provider.get_security_info(ticker)
    upsert_security(conn, ticker, info.name, sector)
    logger.debug("%s : %s (%s)", ticker, info.name, info.exchange or "place inconnue")


def _fetch_and_store(
    conn: sqlite3.Connection,
    provider: MarketDataProvider,
    ticker: str,
    start: date,
    end: date,
) -> tuple[int, bool]:
    """Récupère une fenêtre et l'écrit. Renvoie (lignes écrites, split détecté)."""
    bars = provider.get_daily_adjusted(ticker, start, end)
    rows = store_bars(conn, ticker, bars)
    split = any(bar.split_factor != 1.0 for bar in bars)
    return rows, split


# ---------------------------------------------------------------- Opérations --


def backfill(
    tickers: list[str] | None = None,
    *,
    years: int = BACKFILL_YEARS,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
) -> IngestionReport:
    """Charge `years` années d'historique pour chaque titre.

    Chaque titre est committé séparément : une interruption au neuvième titre
    laisse les huit premiers en base, et relancer reprend sans redemander ce
    qui est déjà là.
    """
    cibles = tickers or list(DEV_UNIVERSE)
    end = today or date.today()
    start = years_ago(years, end)
    logger.info(
        "Backfill de %d titres sur %d ans (%s → %s)", len(cibles), years, start, end
    )
    return _run(
        cibles,
        lambda c, p, t: _fetch_and_store(c, p, t, start, end),
        provider=provider,
        conn=conn,
    )


def refresh(
    tickers: list[str] | None = None,
    *,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
    fallback_years: int = BACKFILL_YEARS,
) -> IngestionReport:
    """Rattrape chaque titre depuis sa dernière séance connue jusqu'à `today`.

    Rattrapage et non « récupérer hier » : la machine ne tourne pas tous les
    jours, et une fenêtre calée sur la veille laisserait un trou à chaque
    journée manquée. La fenêtre part de la dernière date en base, pas du
    lendemain : réécrire cette séance ne coûte rien (clé primaire) et corrige
    une clôture récupérée en séance puis révisée depuis.
    """
    end = today or date.today()

    def rattrapage(
        c: sqlite3.Connection, p: MarketDataProvider, ticker: str
    ) -> tuple[int, bool]:
        derniere = last_stored_date(c, ticker)
        if derniere is None:
            logger.info("%s : aucune donnée en base, backfill complet", ticker)
            return _fetch_and_store(c, p, ticker, years_ago(fallback_years, end), end)

        rows, split = _fetch_and_store(c, p, ticker, derniere, end)
        if split:
            # Tiingo retraite tout l'historique après un split : les adj_close
            # déjà en base sont périmés et fausseraient tous les rendements du
            # titre. Seule une reprise complète de la fenêtre les remet d'aplomb.
            logger.warning(
                "%s : split détecté, historique ajusté périmé — reprise complète",
                ticker,
            )
            rows, _ = _fetch_and_store(c, p, ticker, years_ago(fallback_years, end), end)
        return rows, split

    logger.info("Rattrapage jusqu'au %s", end)
    return _run(tickers or list(DEV_UNIVERSE), rattrapage, provider=provider, conn=conn)


def ensure_ticker(
    ticker: str,
    *,
    years: int = BACKFILL_YEARS,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    today: date | None = None,
) -> IngestionReport:
    """Charge à la demande un titre absent de la base.

    Sert quand un utilisateur saisit un ticker hors de l'univers de dev. La
    profondeur est la même que celle du backfill, délibérément : un titre chargé
    sur trente ans à côté de titres chargés sur cinq donnerait des matrices de
    covariance estimées sur des fenêtres différentes selon la paire.

    Le secteur reste NULL — Tiingo ne le fournit pas et personne ne l'a saisi.
    """
    cible = ticker.upper()
    end = today or date.today()
    start = years_ago(years, end)

    def charger(
        c: sqlite3.Connection, p: MarketDataProvider, t: str
    ) -> tuple[int, bool]:
        if last_stored_date(c, t) is not None:
            logger.info("%s : déjà en base, rien à charger", t)
            return 0, False
        return _fetch_and_store(c, p, t, start, end)

    return _run([cible], charger, provider=provider, conn=conn, sectors={cible: None})


# ------------------------------------------------------------- Orchestration --


def _run(
    tickers: list[str],
    operation,
    *,
    provider: MarketDataProvider | None = None,
    conn: sqlite3.Connection | None = None,
    sectors: dict[str, str | None] | None = None,
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
                _register(connexion, fournisseur, ticker, secteurs.get(ticker))
                rows, _ = operation(connexion, fournisseur, ticker)
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
