#!/usr/bin/env python3
"""Summarize index over/undervaluation under equal-weight assumptions."""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.config import SP500_WEIGHTS_GENERATED_PATH, SP500_TODAY_PATH, SP500_VALUATION_PATH, SP500_VALUATION_HTML_PATH


def _extract_json_array(html: str, key: str) -> list:
    """Extract the first JSON array following `"key":[` in html."""
    marker = f'"{key}":['
    start = html.find(marker)
    if start == -1:
        raise ValueError(f"Key {key!r} not found in HTML")
    start += len(marker) - 1  # point at '['
    depth, i, n = 0, start, len(html)
    in_str, escape = False, False
    while i < n:
        c = html[i]
        if escape:
            escape = False
        elif c == '\\' and in_str:
            escape = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return json.loads(html[start:i + 1])
        i += 1
    raise ValueError(f"Unterminated array for key {key!r}")


def load_entries_from_html(html_path: Path) -> list:
    html = html_path.read_text()

    # Find the bar trace region: "marker":{"color":[...]} comes just before "x":[...] "y":[...]
    # Locate the marker color array (first occurrence with red/green)
    color_marker = '"color":["green"'
    if color_marker not in html:
        color_marker = '"color":["red"'
    ci = html.find(color_marker)
    if ci == -1:
        raise ValueError("Cannot find marker color array in HTML")

    colors = _extract_json_array(html[ci - 10:], "color")

    x_idx = html.find('"x":[', ci)
    tickers = _extract_json_array(html[x_idx - 5:], "x")

    y_idx = html.find('"y":[', x_idx)
    scores = _extract_json_array(html[y_idx - 5:], "y")

    text_idx = html.find('"text":[', ci)
    texts = _extract_json_array(html[text_idx - 5:], "text")

    if not (len(colors) == len(tickers) == len(scores)):
        raise ValueError(
            f"Array length mismatch: colors={len(colors)}, tickers={len(tickers)}, scores={len(scores)}"
        )

    entries = []
    for symbol, score, color, text in zip(tickers, scores, colors, texts):
        solvency = None
        m = re.search(r"Solvency:\s*(\d+)", text)
        if m:
            solvency = int(m.group(1))
        entries.append({
            "symbol": symbol,
            "valuation_score": score,
            "valuation_type": "Overvalued" if color == "red" else "Undervalued",
            "solvency_score": solvency,
        })
    return entries


def load_entries_from_json(json_path: Path) -> list:
    with open(json_path) as f:
        data = json.load(f)
    entries = data if isinstance(data, list) else list(data.values())
    return [e for e in entries if e.get("valuation_score") is not None and e.get("valuation_type")]


def resolve_and_load(path: Path) -> list:
    if path.suffix == ".json":
        return load_entries_from_json(path)

    # Try to find the corresponding JSON first
    json_name = path.stem + ".json"
    for parent in path.parents:
        candidate = parent / "stock" / "data" / json_name
        if candidate.exists():
            return load_entries_from_json(candidate)

    # Fall back to parsing the HTML directly
    return load_entries_from_html(path)


def signed_score(entry) -> float:
    s = entry["valuation_score"]
    return s if entry["valuation_type"] == "Overvalued" else -s


def portfolio_valuation(entries: list) -> float:
    """Equal-weight portfolio valuation using intrinsic value aggregation."""
    total_intrinsic = 0.0
    for e in entries:
        dev = signed_score(e) / 100.0
        total_intrinsic += 1.0 / (1.0 + dev)
    return len(entries) / total_intrinsic - 1.0


def load_market_caps() -> dict:
    p = Path(SP500_WEIGHTS_GENERATED_PATH)
    if not p.exists():
        sys.exit(f"Market caps not found at {p}\nRun: python3 stock/fetch_sp500_weights.py <sp500.html>")
    with open(p) as f:
        return json.load(f)


def portfolio_valuation_weighted(entries: list, market_caps: dict) -> tuple:
    """Market-cap-weighted portfolio valuation. Returns (deviation, n_covered)."""
    market_values, deviations = [], []
    for e in entries:
        cap = market_caps.get(e["symbol"])
        if not cap:
            continue
        market_values.append(float(cap))
        deviations.append(signed_score(e) / 100.0)

    if not market_values:
        return 0.0, 0

    total_market = sum(market_values)
    total_intrinsic = sum(mv / (1.0 + dev) for mv, dev in zip(market_values, deviations))
    return total_market / total_intrinsic - 1.0, len(market_values)


def bucket(score: float) -> str:
    if score <= -30:
        return "Strongly undervalued (>30%)"
    if score <= -10:
        return "Moderately undervalued (10-30%)"
    if score < 0:
        return "Slightly undervalued (<10%)"
    if score == 0:
        return "Fairly valued"
    if score < 10:
        return "Slightly overvalued (<10%)"
    if score < 30:
        return "Moderately overvalued (10-30%)"
    return "Strongly overvalued (>30%)"


def render_html(result: dict) -> str:
    from datetime import date

    ew = result["equal_weight"]
    stocks = result["stocks"]
    dist = result["distribution"]
    mcw = result.get("market_cap_weighted")

    ew_pct = ew["portfolio_pct"]
    med_pct = ew["median_pct"]
    ew_cls = "green" if ew_pct < 0 else "red"
    med_cls = "green" if med_pct < 0 else "red"

    stat_cards = f'''\
    <div class="stat">
      <div class="label">Equal-weight</div>
      <div class="value {ew_cls}">{ew_pct:+.1f}%</div>
      <div class="sub">portfolio deviation</div>
    </div>
    <div class="stat">
      <div class="label">Median stock</div>
      <div class="value {med_cls}">{med_pct:+.1f}%</div>
      <div class="sub">deviation</div>
    </div>'''

    grid_cols = 2
    if mcw:
        mcw_pct = mcw["portfolio_pct"]
        mcw_cls = "green" if mcw_pct < 0 else "red"
        stat_cards += f'''
    <div class="stat">
      <div class="label">Market-cap weighted</div>
      <div class="value {mcw_cls}">{mcw_pct:+.1f}%</div>
      <div class="sub">{mcw["stocks_covered"]} / {stocks["total"]} stocks</div>
    </div>'''
        grid_cols = 3

    dist_order = [
        ("Strongly undervalued (>30%)",     "#16a34a"),
        ("Moderately undervalued (10-30%)", "#4ade80"),
        ("Slightly undervalued (<10%)",     "#86efac"),
        ("Fairly valued",                   "#94a3b8"),
        ("Slightly overvalued (<10%)",      "#fca5a5"),
        ("Moderately overvalued (10-30%)",  "#f87171"),
        ("Strongly overvalued (>30%)",      "#dc2626"),
    ]
    max_count = max((dist.get(lbl, 0) for lbl, _ in dist_order), default=1) or 1
    dist_rows = ""
    for label, color in dist_order:
        count = dist.get(label, 0)
        if not count:
            continue
        width = round(count / max_count * 100)
        dist_rows += f'''
  <div class="dist-row">
    <div class="dist-label">{label}</div>
    <div class="dist-bar-wrap"><div class="dist-bar" style="width:{width}%;background:{color}"></div></div>
    <div class="dist-count">{count}</div>
  </div>'''

    def entry_rows(entries):
        rows = ""
        for e in entries:
            sc = e["score_pct"]
            cls = "green" if sc < 0 else "red"
            sol = e.get("solvency")
            sol_str = str(sol) if sol is not None else "&mdash;"
            rows += f'\n      <tr><td class="sym">{e["symbol"]}</td><td class="{cls}">{sc:+.0f}%</td><td>{sol_str}</td></tr>'
        return rows

    under_rows = entry_rows(result["most_undervalued"])
    over_rows = entry_rows(result["most_overvalued"])
    today = date.today().isoformat()

    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>S&amp;P 500 Valuation Summary</title>
  <style>
    body {{ font-family: sans-serif; max-width: 820px; margin: 40px auto; padding: 0 20px; line-height: 1.6; }}
    a.back {{ margin-bottom: 20px; display: inline-block; color: #2563eb; text-decoration: none; }}
    a.back:hover {{ text-decoration: underline; }}
    h1 {{ margin-bottom: 6px; }}
    p.desc {{ color: #555; margin-bottom: 24px; }}
    h2 {{ font-size: 1em; text-transform: uppercase; letter-spacing: 0.06em; color: #888; margin: 32px 0 12px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
    .stat-grid {{ display: grid; grid-template-columns: repeat({grid_cols}, 1fr); gap: 14px; margin-bottom: 8px; }}
    .stat {{ padding: 16px 20px; border: 1px solid #e2e8f0; border-radius: 6px; background: #f8fafc; }}
    .stat .label {{ font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.06em; color: #888; margin-bottom: 4px; }}
    .stat .value {{ font-size: 1.8em; font-weight: 700; line-height: 1.2; }}
    .stat .sub {{ font-size: 0.82em; color: #64748b; }}
    .green {{ color: #16a34a; }}
    .red {{ color: #dc2626; }}
    .dist-row {{ display: flex; align-items: center; margin: 4px 0; font-size: 0.88em; }}
    .dist-label {{ width: 250px; flex-shrink: 0; color: #1e293b; }}
    .dist-bar-wrap {{ flex: 1; background: #f1f5f9; border-radius: 3px; height: 16px; margin: 0 10px; }}
    .dist-bar {{ height: 100%; border-radius: 3px; }}
    .dist-count {{ width: 32px; text-align: right; color: #64748b; font-variant-numeric: tabular-nums; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 7px 10px; font-size: 0.9em; border-bottom: 1px solid #e2e8f0; text-align: left; }}
    th {{ font-weight: 600; color: #1e293b; background: #f8fafc; }}
    .sym {{ font-weight: 600; font-family: monospace; font-size: 0.95em; }}
  </style>
</head>
<body>
  <a class="back" href="index.html">&#8592; Back</a>
  <h1>S&amp;P 500 Valuation Summary</h1>
  <p class="desc">{today} &mdash; {stocks["total"]} stocks &nbsp;&middot;&nbsp; {stocks["undervalued"]} undervalued &nbsp;&middot;&nbsp; {stocks["overvalued"]} overvalued</p>

  <div class="stat-grid">
{stat_cards}
  </div>

  <h2>Distribution</h2>
{dist_rows}

  <h2>Extremes</h2>
  <div class="two-col">
    <table>
      <thead><tr><th>Most Undervalued</th><th>Score</th><th>Solvency</th></tr></thead>
      <tbody>{under_rows}
      </tbody>
    </table>
    <table>
      <thead><tr><th>Most Overvalued</th><th>Score</th><th>Solvency</th></tr></thead>
      <tbody>{over_rows}
      </tbody>
    </table>
  </div>
</body>
</html>'''


def summarize(path: Path, market_cap: bool = False):
    entries = resolve_and_load(path)

    if not entries:
        sys.exit("No valid entries found.")

    n = len(entries)
    scores = [signed_score(e) for e in entries]
    med = median(scores)
    port_dev = portfolio_valuation(entries)

    overvalued = [e for e in entries if e["valuation_type"] == "Overvalued"]
    undervalued = [e for e in entries if e["valuation_type"] == "Undervalued"]

    direction = "OVERVALUED" if port_dev > 0 else "UNDERVALUED"
    print(f"File:    {path.name}")
    print(f"Stocks:  {n}  ({len(overvalued)} overvalued, {len(undervalued)} undervalued)")
    print()
    print(f"Equal-weight index valuation")
    print(f"  Portfolio: {port_dev*100:+.1f}%  [{direction} by {abs(port_dev)*100:.1f}%]")
    print(f"  Median:    {med:+.1f}%")
    print()

    order = [
        "Strongly undervalued (>30%)",
        "Moderately undervalued (10-30%)",
        "Slightly undervalued (<10%)",
        "Fairly valued",
        "Slightly overvalued (<10%)",
        "Moderately overvalued (10-30%)",
        "Strongly overvalued (>30%)",
    ]
    buckets = Counter(bucket(s) for s in scores)
    print("Distribution:")
    for b in order:
        count = buckets.get(b, 0)
        if count:
            bar = "#" * (count * 40 // n)
            print(f"  {b:<38} {count:>4}  {bar}")
    print()

    sorted_entries = sorted(entries, key=signed_score)
    print("Most undervalued (top 5):")
    for e in sorted_entries[:5]:
        print(f"  {e['symbol']:<8} {signed_score(e):+.0f}%  solvency={e.get('solvency_score', 'N/A')}")
    print()
    print("Most overvalued (top 5):")
    for e in reversed(sorted_entries[-5:]):
        print(f"  {e['symbol']:<8} {signed_score(e):+.0f}%  solvency={e.get('solvency_score', 'N/A')}")

    result = {
        "file": path.name,
        "stocks": {"total": n, "overvalued": len(overvalued), "undervalued": len(undervalued)},
        "equal_weight": {"portfolio_pct": round(port_dev * 100, 2), "median_pct": round(med, 2)},
        "distribution": {b: buckets.get(b, 0) for b in order},
        "most_undervalued": [
            {"symbol": e["symbol"], "score_pct": round(signed_score(e), 1), "solvency": e.get("solvency_score")}
            for e in sorted_entries[:5]
        ],
        "most_overvalued": [
            {"symbol": e["symbol"], "score_pct": round(signed_score(e), 1), "solvency": e.get("solvency_score")}
            for e in reversed(sorted_entries[-5:])
        ],
    }

    if market_cap:
        print()
        caps = load_market_caps()
        mcw_dev, n_covered = portfolio_valuation_weighted(entries, caps)
        mcw_dir = "OVERVALUED" if mcw_dev > 0 else "UNDERVALUED"
        print(f"Market-cap-weighted valuation  ({n_covered}/{n} stocks with data)")
        print(f"  Portfolio: {mcw_dev*100:+.1f}%  [{mcw_dir} by {abs(mcw_dev)*100:.1f}%]")
        result["market_cap_weighted"] = {"portfolio_pct": round(mcw_dev * 100, 2), "stocks_covered": n_covered}

    out = Path(SP500_VALUATION_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(result, f, indent=2)

    html_out = Path(SP500_VALUATION_HTML_PATH)
    html_out.parent.mkdir(parents=True, exist_ok=True)
    html_out.write_text(render_html(result))
    print(f"\nSaved to {out} and {html_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize index valuation")
    parser.add_argument("--file", action="store_true", help="Path to analysis .html or .json file")
    parser.add_argument("--market-cap", action="store_true", help="Also compute market-cap-weighted valuation (fetches via yfinance, cached)")
    args = parser.parse_args()
    if not args.file:
        print("No file provided, using default S&P 500 analysis")
        args.file = SP500_TODAY_PATH
    summarize(Path(args.file), market_cap=True)
