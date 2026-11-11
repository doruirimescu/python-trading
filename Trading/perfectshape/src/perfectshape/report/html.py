"""report.html: a saved run in the Nexus design system (live nexus.css / nexus.js, Plotly from its CDN).

The page template, its layout CSS and the renderer live in ``perfectshape/web/`` and are shared with the
dashboard; they are inlined here so a report is one file (it still needs the network for the Nexus styles and
Plotly, like the Investing Nexus pages).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


def render_html(payload: dict) -> str:
    data = json.dumps(payload, default=float).replace("</", "<\\/")
    ratio = payload.get("search", {}).get("mode") == "ratio"
    p = payload.get("panel", {})
    if ratio:
        r = payload.get("ratio", {})
        lead = (f"Every <mark>{r.get('k')} vs {r.get('k')} ratio</mark> of {p.get('symbols')} instruments, "
                "ranked by <span class=\"hl-accent\">straight-line trend</span> and by "
                "<span class=\"hl-accent\">tradable range</span>.")
    else:
        lead = (f"Weighted baskets of {p.get('symbols')} instruments whose combined value traces a "
                "<mark>straight trend or a flat range</mark>, ranked by how long the shape has held.")
    lead += f" Data {p.get('start')} → {p.get('end')}; the last bars after {p.get('fit_end')} are the holdout."
    page = (WEB / "report.html").read_text(encoding="utf-8")
    page = (page.replace("/*__SHAPES_CSS__*/", (WEB / "shapes.css").read_text(encoding="utf-8"))
                .replace("/*__REPORT_JS__*/", (WEB / "report.js").read_text(encoding="utf-8"))
                .replace("__NAME__", html.escape(str(payload.get("name", ""))))
                .replace("__TITLE__", html.escape(str(payload.get("name", "Perfect"))))
                .replace("__GENERATED__", html.escape(str(payload.get("generated", ""))))
                .replace("__LEAD__", lead))
    return page.replace("__DATA__", data)
