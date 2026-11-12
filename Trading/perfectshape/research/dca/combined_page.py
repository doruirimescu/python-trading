"""Write the four combined strategies' pages from the leave-one-era-out run (research/dca/kelly4_cv.py) into a DCA
run, and update the report's and the other rule pages' links.

    python research/dca/combined_page.py runs/<stamp>_dca
"""
import json
import sys
from pathlib import Path

import pandas as pd

from perfectshape.dca.pages import combined_page, family_rows, render_page
from perfectshape.dca.report import render_html

# the two fits of the first combined strategy that failed on years they had not seen (research/dca/fit_continuous.py)
ATTEMPTS = [
    {"name": "Every parameter optimised for wealth (7 parameters, differential evolution, 3 seeds)",
     "train": "100% · +6.3%", "test": "62% · +4.0%", "early": "32% · -1.0%",
     "why": "It learned 1962-1999's path of interest rates (rising to 1981, falling after) and drove the trend effect to "
            "almost zero; the rate penalty ended at the edge of its range."},
    {"name": "Forecast by least squares on 1962-1999 (4 slopes), sizing fitted",
     "train": "81% · +2.6%", "test": "7% · -1.9%", "early": "73% · +6.8%",
     "why": "The fine slopes change sign between eras: with rates in the regression, months above the average looked "
            "worse than months below it in 1962-1999 (t = -1.2), the opposite of every other era."},
]
LABELS = {"combined-strategy": "Optimism", "combined-pessimism": "Pessimism",
          "combined-optimism-sells": "Optimism, sells", "combined-pessimism-sells": "Pessimism, sells"}


def read_data(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8")
    i = txt.find("const D = ")
    return json.loads(txt[i + 10:txt.index("\n", i)].rstrip(";").replace("<\\/", "</"))


if __name__ == "__main__":
    run = Path(sys.argv[1])
    cvs = pd.read_pickle("data_cache/dca/kelly4_cv.pkl")
    finals = {s: cv["final"] for s, cv in cvs.items()}
    names = {s: k.rule().name for s, k in finals.items()}
    links = run / "rules"
    links.mkdir(parents=True, exist_ok=True)
    nav = []
    for p in sorted(links.glob("*.html")):
        d = read_data(p)
        if d.get("family") != "combined":
            nav = d.get("nav", [])
            break
    nav = [n for n in nav if n.get("kind") != "combined"]
    nav = [{"name": names[s], "href": f"{s}.html", "kind": "combined", "family": "combined"} for s in cvs] + nav
    for old in links.glob("combined*.html"):
        if old.stem not in cvs:
            old.unlink()
    for s, cv in cvs.items():
        fam = family_rows(cvs, finals, names, s)
        page = combined_page(finals[s], cv, ATTEMPTS if s == "combined-strategy" else [], nav=nav, family=fam)
        page["variant"], page["nav_label"] = s, LABELS[s]
        (links / f"{s}.html").write_text(render_page(page), encoding="utf-8")
        print("wrote", links / f"{s}.html", "|", page["verdict"][:160])
    # the other pages get the four in their navigation too
    for p in sorted(links.glob("*.html")):
        if p.stem in cvs:
            continue
        d = read_data(p)
        d["nav"] = nav
        p.write_text(render_page(d), encoding="utf-8")
    # the report: its page list (and the latest template)
    rep = run / "report.html"
    d = read_data(rep)
    pages = {k: v for k, v in (d.get("pages") or {}).items() if not k.startswith("Combined")}
    d["pages"] = {**{names[s]: f"rules/{s}.html" for s in cvs}, **pages}
    rep.write_text(render_html(d), encoding="utf-8")
    print("updated", rep)
