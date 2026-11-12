"""perfectshape CLI.

  perfectshape scan configs/sp500.yaml [--top 10] [--shape uptrend] [--end 2026-10-30] [--limit 50]
  perfectshape universe list | show <name> | refresh sp500
  perfectshape fetch configs/sp500.yaml          # warm the price cache only
  perfectshape dashboard [--port 8765] [--open]  # web UI: configure, run, pause, live results
  perfectshape dca now                           # DCA timing: what to do with this month's payment
  perfectshape dca report                        # ... and the full study against plain DCA (a few minutes)

Exit codes: 0 ok, 2 config error, 3 data error.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="perfectshape", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scan", help="search the universe for perfect uptrends / downtrends / ranges")
    sc.add_argument("config")
    sc.add_argument("--shape", action="append", choices=["uptrend", "downtrend", "range"])
    sc.add_argument("--end", type=date.fromisoformat, help="override data.end")
    sc.add_argument("--limit", type=int, help="override universe.limit")
    sc.add_argument("--top", type=int, default=10, help="rows per shape printed to the console")

    fe = sub.add_parser("fetch", help="download/refresh the price cache for a config's universe")
    fe.add_argument("config")

    db = sub.add_parser("dashboard", help="web dashboard: build a config, run it, follow / pause it live")
    db.add_argument("--host", default="127.0.0.1")
    db.add_argument("--port", type=int, default=8765)
    db.add_argument("--open", action="store_true", help="open a browser tab")

    dc = sub.add_parser("dca", help="beat monthly DCA into the S&P 500: this month's instruction, or the full report")
    dc.add_argument("action", choices=["now", "report"])
    dc.add_argument("--payment", type=float, default=2000.0, help="monthly payment in dollars")
    dc.add_argument("--quick", action="store_true", help="report: skip the sensitivity table and the other markets")
    dc.add_argument("--out", default="runs")

    un = sub.add_parser("universe", help="manage instrument lists")
    un.add_argument("action", choices=["list", "show", "refresh"])
    un.add_argument("name", nargs="?")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose or args.cmd != "universe" else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    if args.cmd == "dashboard":
        from perfectshape.dashboard.server import serve
        serve(args.host, args.port, open_browser=args.open)
        return 0

    if args.cmd == "universe":
        return _universe(args)

    if args.cmd == "dca":
        return _dca(args)

    from pydantic import ValidationError

    from perfectshape.config import load_config
    try:
        cfg = load_config(args.config)
        if args.cmd == "scan":
            upd = {}
            if args.shape:
                upd["search"] = cfg.search.model_copy(update={"shapes": args.shape})
            if args.end:
                upd["data"] = cfg.data.model_copy(update={"end": args.end})
            if args.limit:
                upd["universe"] = cfg.universe.model_copy(update={"limit": args.limit})
            cfg = cfg.model_validate(cfg.model_copy(update=upd).model_dump())
    except (ValidationError, FileNotFoundError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    if args.cmd == "fetch":
        from perfectshape.data.sources import load_panel
        from perfectshape.universe import build_universe
        u = build_universe(cfg.universe.lists, cfg.universe.tickers, cfg.universe.exclude, cfg.universe.limit)
        p = load_panel(u.tickers, cfg.data)
        print(f"{len(p.symbols)}/{len(u.tickers)} instruments, {p.n_bars} bars ({p.dates[0]} .. {p.dates[-1]})")
        return 0

    from perfectshape.pipeline import scan
    from perfectshape.report.writer import _fmt_members, write_run
    try:
        out = scan(cfg)
    except ValueError as e:
        print(f"data error: {e}", file=sys.stderr)
        return 3
    run_dir = write_run(out)
    ppy = cfg.scoring.periods_per_year
    for shape, results in out.ranked.items():
        print(f"\n== {shape}: {len(results)} ranked of {out.n_candidates[shape]} candidates")
        for i, r in enumerate(results[: args.top], 1):
            m = r.metrics
            band = (f"harvest {m['harvest']:+6.1%}/yr  {m['trades_per_year']:4.1f} tr/yr  band {m['swing_up']:+6.1%}  "
                    f"now {m['band_pos']:4.0%}  ") if "harvest" in m else ""
            on = f" (on {r.ref_window / ppy:.1f}y)" if r.ref_window and r.ref_window != r.duration else ""
            print(f"{i:>3}. held {r.duration / ppy:4.1f}y{on}  score {r.score:.3f}  {band}"
                  f"{'alive ' if r.alive else 'BROKEN'}  {_fmt_members(r)}")
    print(f"\nrun: {run_dir}\nreport: {run_dir / 'report.html'}")
    return 0


def _dca(args) -> int:
    from perfectshape.dca.data import load_market
    from perfectshape.dca.signals import features
    from perfectshape.dca.strategy import EXPOSURE_RECOMMENDED, RECOMMENDED, decision, exposure_decision

    try:
        market = load_market()
    except Exception as e:
        print(f"data error: {e}", file=sys.stderr)
        return 3
    if args.action == "now":
        n = decision(market, features(market), RECOMMENDED)
        print(f"{n['date']}: {n['text']}")
        print(f"  S&P 500 {n['px']:,.0f}, {n['vs_avg']:+.1%} against its {RECOMMENDED.ma}-day average ({n['avg']:,.0f}), "
              f"{n['days_in_state']} trading days {'above' if n['above'] else 'below'}")
        print(f"  10-year yield {n['y10']:.2f}% ({n['y10_rise']:+.2f} points over {RECOMMENDED.guard_days} trading days; "
              f"the guard trips above +{RECOMMENDED.guard_rise})")
        x = exposure_decision(market, features(market), EXPOSURE_RECOMMENDED)
        print(f"  account-sized variant (trend {EXPOSURE_RECOMMENDED.up:g} / {EXPOSURE_RECOMMENDED.down:g}, it sells): {x['text']}")
        return 0
    from perfectshape.dca.report import build_payload, summary_md, write_report

    print("running every policy over every start month (a few minutes) ...")
    payload = build_payload(RECOMMENDED, payment=args.payment, quick=args.quick)
    pages = None
    if not args.quick:
        from perfectshape.dca.pages import build_pages

        print("one page per rule (about 45 simulations on every core) ...")
        pages = build_pages()
    run_dir = write_report(payload, args.out, pages=pages)
    print(summary_md(payload))
    print(f"run: {run_dir}\nreport: {run_dir / 'report.html'}")
    return 0


def _universe(args) -> int:
    from perfectshape import universe as U
    if args.action == "list":
        for p in sorted(U.UNIVERSE_DIR.glob("*")):
            if p.suffix in (".csv", ".txt", ".json", ".yaml", ".yml"):
                print(f"{p.stem:<22} {len(U.read_list(p).tickers):>5}  {p.name}")
        print(f"\nfetchable (universe refresh <name>): {', '.join(sorted(U.FETCHERS))}")
        return 0
    if not args.name:
        print("name required", file=sys.stderr)
        return 2
    if args.action == "refresh":
        p = U.refresh(args.name)
        print(f"wrote {p} ({len(U.read_list(p).tickers)} tickers)")
        return 0
    u = U.read_list(U.resolve_list_path(args.name))
    for t in u.tickers:
        print(f"{t:<10} {u.sector(t):<24} {u.name(t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
