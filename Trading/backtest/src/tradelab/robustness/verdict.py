"""Advisory traffic-light verdict (ARCHITECTURE section 7). Not a gate: informs, never proves."""
from __future__ import annotations

from typing import Any


def _tl(value: Any, green: bool | None, amber: bool | None = None) -> str:
    if value is None or green is None:
        return "na"
    return "green" if green else ("amber" if amber else "red")


def verdict(*, dsr: float | None = None, pbo: float | None = None, wf_efficiency: float | None = None,
            positive_at_2x: bool | None = None, n_trades: int | None = None, plateau: float | None = None,
            psr0: float | None = None) -> dict:
    """Checks: DSR>0.95, PBO<0.5, WF efficiency>0.5, positive at 2x costs, trades>=100, plateau score, PSR(0)>0.95."""
    def ok(v):  # nan -> None
        return None if v is None or v != v else v
    dsr, pbo, wf_efficiency, plateau, psr0 = map(ok, (dsr, pbo, wf_efficiency, plateau, psr0))
    checks = [
        ("dsr", dsr, ">0.95", _tl(dsr, None if dsr is None else dsr > 0.95, None if dsr is None else dsr > 0.80)),
        ("pbo", pbo, "<0.5", _tl(pbo, None if pbo is None else pbo < 0.3, None if pbo is None else pbo < 0.5)),
        ("wf_efficiency", wf_efficiency, ">0.5",
         _tl(wf_efficiency, None if wf_efficiency is None else wf_efficiency > 0.5, None if wf_efficiency is None else wf_efficiency > 0.3)),
        ("positive_at_2x_costs", positive_at_2x, "true", _tl(positive_at_2x, positive_at_2x if positive_at_2x is not None else None)),
        ("n_trades", n_trades, ">=100", _tl(n_trades, None if n_trades is None else n_trades >= 100, None if n_trades is None else n_trades >= 30)),
        ("plateau_score", plateau, ">=0.7", _tl(plateau, None if plateau is None else plateau >= 0.7, None if plateau is None else plateau >= 0.5)),
        ("psr0", psr0, ">0.95", _tl(psr0, None if psr0 is None else psr0 > 0.95, None if psr0 is None else psr0 > 0.8)),
    ]
    rows = [{"check": n, "value": v, "threshold": th, "status": s} for n, v, th, s in checks]
    st = [r["status"] for r in rows if r["status"] != "na"]
    overall = "n/a" if not st else ("red" if "red" in st else ("amber" if "amber" in st else "green"))
    return {"overall": overall, "checks": rows, "advisory": True}
