"""Ligne de commande de l'ingestion.

    python -m backend.ingestion backfill          # chargement initial (depuis 2005)
    python -m backend.ingestion refresh           # rattrapage quotidien
    python -m backend.ingestion add TSLA          # titre hors univers de dev
    python -m backend.ingestion status            # ce qui est en base
    python -m backend.ingestion rebuild           # réparation : tout recharger

Le code de sortie vaut 1 dès qu'un titre échoue, pour qu'un ordonnanceur ou un
cron voie passer l'échec au lieu de le croire silencieusement réussi.
"""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import closing
from datetime import date

from backend.data_provider import HOURLY_CALL_BUDGET
from backend.db.backup import sauvegarder
from backend.db.init_db import connect, get_db_path
from backend.ingestion.prices import (
    backfill,
    ensure_ticker,
    rebuild,
    refresh,
    tickers_en_base,
)
from backend.ingestion.universe import BACKFILL_START, DEV_UNIVERSE


def configure_logging(verbose: bool = False) -> None:
    """Prépare la sortie de la commande : console en UTF-8, journal au niveau
    INFO (DEBUG avec `verbose`), urllib3 limité aux avertissements."""
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


def reconstruire(tickers: list[str] | None, *, today: date | None = None) -> int:
    """Sauvegarde la base, puis recharge l'historique complet de chaque titre.

    Réservé à la réparation d'une base écrite par un rattrapage fautif : un
    appel par titre, donc un budget vérifié AVANT la sauvegarde et le premier
    appel. Au-delà, rien n'est lancé ; on relance par lots avec `--tickers`.
    """
    chemin = get_db_path()
    if not chemin.exists():
        print(f"Base introuvable : {chemin}. Rien à reconstruire.")
        return 1

    with closing(connect(chemin)) as conn:
        cibles = tickers or tickers_en_base(conn)
    if len(cibles) > HOURLY_CALL_BUDGET:
        print(
            f"{len(cibles)} appels nécessaires, au-delà de la limite de "
            f"{HOURLY_CALL_BUDGET} par heure du fournisseur. Rien n'a été lancé : "
            "relancer par lots avec --tickers, à une heure d'intervalle."
        )
        return 1

    sauvegarde = sauvegarder(chemin, today or date.today())
    # flush : les journaux partent sur stderr, et dans un tube la sauvegarde
    # s'afficherait après eux, comme si elle avait suivi la reconstruction.
    print(f"Sauvegarde : {sauvegarde}", flush=True)
    print(
        f"{len(cibles)} titres à recharger : {len(cibles)} appels prévus, sous la "
        f"limite de {HOURLY_CALL_BUDGET} par heure (un refresh lancé dans la même "
        "heure s'y ajoute).",
        flush=True,
    )
    report = rebuild(cibles, today=today)
    print(report.summary())
    return 1 if report.failures else 0


def build_parser() -> argparse.ArgumentParser:
    """L'analyseur des cinq commandes, `backfill`, `refresh`, `add`, `status`
    et `rebuild`, avec leurs options. Sans `--tickers`, `backfill` et
    `refresh` portent sur l'univers de développement, `rebuild` sur tous les
    titres en base ; la date d'ancrage par défaut est `BACKFILL_START`."""
    parser = argparse.ArgumentParser(
        prog="python -m backend.ingestion",
        description="Ingestion des prix quotidiens ajustés.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="logs DEBUG")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backfill = sub.add_parser("backfill", help="chargement initial de l'historique")
    p_backfill.add_argument(
        "--start", type=date.fromisoformat, default=BACKFILL_START,
        metavar="AAAA-MM-JJ", help="date d'ancrage (defaut : %(default)s)",
    )
    p_backfill.add_argument(
        "--refresh-metadata", action="store_true",
        help="redemander nom et place de cotation (1 appel de plus par titre)",
    )
    p_backfill.add_argument(
        "--tickers", nargs="+", metavar="TICKER", default=list(DEV_UNIVERSE)
    )

    p_refresh = sub.add_parser("refresh", help="rattrapage depuis la dernière séance")
    p_refresh.add_argument(
        "--tickers", nargs="+", metavar="TICKER", default=list(DEV_UNIVERSE)
    )

    p_add = sub.add_parser("add", help="charger un titre absent de la base")
    p_add.add_argument("ticker")
    p_add.add_argument(
        "--start", type=date.fromisoformat, default=BACKFILL_START,
        metavar="AAAA-MM-JJ", help="date d'ancrage (defaut : %(default)s)",
    )

    sub.add_parser("status", help="inventaire de la base")

    p_rebuild = sub.add_parser(
        "rebuild",
        help="sauvegarder la base puis recharger tout l'historique de chaque titre",
    )
    p_rebuild.add_argument(
        "--tickers", nargs="+", metavar="TICKER",
        help="défaut : tous les titres en base",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Exécute la commande et rend son code de sortie : 1 dès qu'un titre
    échoue ou est ignoré faute de quota, 0 sinon. `status` rend 0, `rebuild`
    le code de `reconstruire`. Les tickers saisis passent en capitales."""
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)

    if args.command == "status":
        show_status()
        return 0

    if args.command == "rebuild":
        return reconstruire([t.upper() for t in args.tickers] if args.tickers else None)

    if args.command == "backfill":
        report = backfill(
            [t.upper() for t in args.tickers],
            start=args.start,
            refresh_metadata=args.refresh_metadata,
        )
    elif args.command == "refresh":
        report = refresh([t.upper() for t in args.tickers])
    else:
        report = ensure_ticker(args.ticker, start=args.start)

    print(report.summary())
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
