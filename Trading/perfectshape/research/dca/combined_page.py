"""Write the combined strategy's page from the leave-one-era-out run (research/dca/kelly_cv.py) into a DCA run.

    python research/dca/combined_page.py runs/<stamp>_dca
"""
import json
import sys
from pathlib import Path

import pandas as pd

from perfectshape.dca.pages import combined_page, render_page

# the two fits that failed on years they had not seen (research/dca/fit_continuous.py; README "Combined strategy")
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

if __name__ == "__main__":
    run = Path(sys.argv[1])
    cv = pd.read_pickle("data_cache/dca/kelly_cv.pkl")
    final = cv["final"]
    nav = []
    links = run / "rules"
    if links.exists():
        # keep the other pages' navigation: read it back from any existing rule page
        for p in sorted(links.glob("*.html")):
            txt = p.read_text(encoding="utf-8")
            i = txt.find("const D = ")
            if i > 0:
                d = json.loads(txt[i + 10:txt.index("\n", i)].rstrip(";").replace("<\\/", "</"))
                nav = d.get("nav", [])
                break
    name = final.rule().name
    nav = [n for n in nav if n.get("kind") != "combined"]
    nav = [{"name": name, "href": "combined-strategy.html", "kind": "combined", "family": "combined"}] + nav
    page = combined_page(final, cv, ATTEMPTS, nav=nav)
    links.mkdir(parents=True, exist_ok=True)
    (links / "combined-strategy.html").write_text(render_page(page), encoding="utf-8")
    # the other pages get the combined page in their navigation too
    for p in sorted(links.glob("*.html")):
        if p.name == "combined-strategy.html":
            continue
        txt = p.read_text(encoding="utf-8")
        i = txt.find("const D = ")
        j = txt.index("\n", i)
        d = json.loads(txt[i + 10:j].rstrip(";").replace("<\\/", "</"))
        d["nav"] = nav
        p.write_text(render_page(d), encoding="utf-8")
    print("wrote", links / "combined-strategy.html")
    print(page["verdict"])
    print(page["combined"]["now"])
