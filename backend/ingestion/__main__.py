"""Ligne de commande de l'ingestion.

    python -m backend.ingestion backfill          # chargement initial (5 ans)
    python -m backend.ingestion refresh           # rattrapage quotidien
    python -m backend.ingestion add TSLA          # titre hors univers de dev
    python -m backend.ingestion status            # ce qui est en base

Le code de sortie vaut 1 dès qu'un titre échoue, pour qu'un ordonnanceur ou un
cron voie passer l'échec au lieu de le croire silencieusement réussi.
"""

from __future__ import annotations

import argparse
import logging
import sys

from backend.db.init_db import connect
from backend.ingestion.prices import backfill, ensure_ticker, refresh
from backend.ingestion.universe import BACKFILL_YEARS, DEV_UNIVERSE


def configure_logging(verbose: bool = False) -> None:
    # La console Windows est en cp1252 par défaut : sans cela, les accents et
    # les flèches des messages de log ressortent en mojibake illisible.
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # urllib3 journalise chaque connexion en DEBUG, ce qui noie le bilan.
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def show_status() -> None:
    """Inventaire de la base : couverture par titre, sans appel réseau."""
    with connect() as conn:
        lignes = conn.execute(
            """
            SELECT s.ticker,
                   s.name,
                   s.sector,
                   COUNT(p.date)  AS seances,
                   MIN(p.date)    AS debut,
                   MAX(p.date)    AS fin
            FROM securities s
            LEFT JOIN prices p ON p.ticker = s.ticker
            GROUP BY s.ticker
            ORDER BY s.ticker
            """
        ).fetchall()

    if not lignes:
        print("Base vide. Lancer : python -m backend.ingestion backfill")
        return

    print(f"{'TICKER':<8} {'SÉANCES':>8}  {'DÉBUT':<12} {'FIN':<12} SECTEUR")
    for r in lignes:
        secteur = r["sector"] or "—"
        print(
            f"{r['ticker']:<8} {r['seances']:>8}  "
            f"{r['debut'] or '—':<12} {r['fin'] or '—':<12} {secteur}"
        )
    total = sum(r["seances"] for r in lignes)
    print(f"\n{len(lignes)} titres, {total} séances.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.ingestion",
        description="Ingestion des prix quotidiens ajustés.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="logs DEBUG")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backfill = sub.add_parser("backfill", help="chargement initial de l'historique")
    p_backfill.add_argument("--years", type=int, default=BACKFILL_YEARS)
    p_backfill.add_argument(
        "--tickers", nargs="+", metavar="TICKER", default=list(DEV_UNIVERSE)
    )

    p_refresh = sub.add_parser("refresh", help="rattrapage depuis la dernière séance")
    p_refresh.add_argument(
        "--tickers", nargs="+", metavar="TICKER", default=list(DEV_UNIVERSE)
    )

    p_add = sub.add_parser("add", help="charger un titre absent de la base")
    p_add.add_argument("ticker")
    p_add.add_argument("--years", type=int, default=BACKFILL_YEARS)

    sub.add_parser("status", help="inventaire de la base")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)

    if args.command == "status":
        show_status()
        return 0

    if args.command == "backfill":
        report = backfill([t.upper() for t in args.tickers], years=args.years)
    elif args.command == "refresh":
        report = refresh([t.upper() for t in args.tickers])
    else:
        report = ensure_ticker(args.ticker, years=args.years)

    print(report.summary())
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
