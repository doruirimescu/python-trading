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
from config.config import SP500_WEIGHTS_GENERATED_PATH


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

    buckets = Counter(bucket(s) for s in scores)
    print("Distribution:")
    order = [
        "Strongly undervalued (>30%)",
        "Moderately undervalued (10-30%)",
        "Slightly undervalued (<10%)",
        "Fairly valued",
        "Slightly overvalued (<10%)",
        "Moderately overvalued (10-30%)",
        "Strongly overvalued (>30%)",
    ]
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

    if market_cap:
        print()
        caps = load_market_caps()
        mcw_dev, n_covered = portfolio_valuation_weighted(entries, caps)
        mcw_dir = "OVERVALUED" if mcw_dev > 0 else "UNDERVALUED"
        print(f"Market-cap-weighted valuation  ({n_covered}/{n} stocks with data)")
        print(f"  Portfolio: {mcw_dev*100:+.1f}%  [{mcw_dir} by {abs(mcw_dev)*100:.1f}%]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize index valuation")
    parser.add_argument("file", help="Path to analysis .html or .json file")
    parser.add_argument("--market-cap", action="store_true", help="Also compute market-cap-weighted valuation (fetches via yfinance, cached)")
    args = parser.parse_args()
    summarize(Path(args.file), market_cap=args.market_cap)
