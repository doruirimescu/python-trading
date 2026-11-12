"""Write the mega strategy's page into a DCA run and link it from the report and every rule page.

    python research/dca/mega_page.py runs/<stamp>_dca
"""
import sys
from pathlib import Path

from combined_page import read_data

from perfectshape.dca.mega_page import NAME, SLUG, mega_page
from perfectshape.dca.pages import render_page
from perfectshape.dca.report import render_html

if __name__ == "__main__":
    run = Path(sys.argv[1])
    links = run / "rules"
    nav = []
    for p in sorted(links.glob("*.html")):
        d = read_data(p)
        if d.get("family") not in ("combined", "mega"):
            nav = d.get("nav", [])
            break
    nav = [{"name": NAME, "href": f"{SLUG}.html", "kind": "mega", "family": "mega"}] + [n for n in nav if n.get("kind") != "mega"]
    page = mega_page(nav=nav)
    (links / f"{SLUG}.html").write_text(render_page(page), encoding="utf-8")
    print(page["verdict"])
    for t in page["extra"]:
        print("\n" + t["title"])
        for row in t["rows"]:
            print("  ", " | ".join(row))
    for p in sorted(links.glob("*.html")):
        if p.stem == SLUG:
            continue
        d = read_data(p)
        d["nav"] = nav
        p.write_text(render_page(d), encoding="utf-8")
    rep = run / "report.html"
    d = read_data(rep)
    d["pages"] = {NAME: f"rules/{SLUG}.html", **{k: v for k, v in (d.get("pages") or {}).items() if not k.startswith("Mega")}}
    rep.write_text(render_html(d), encoding="utf-8")
    print("\nwrote", links / f"{SLUG}.html")
