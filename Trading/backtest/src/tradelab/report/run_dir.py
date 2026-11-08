"""Run-directory helpers: naming, LATEST symlink, artifact writers, env info."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tradelab.analytics.metrics import jsonable


def make_run_dir(runs_root: str | Path, strategy: str, hash8: str, now: datetime | None = None) -> Path:
    """Create ``<runs_root>/<YYYYMMDD-HHMMSS>_<strategy>_<hash8>`` (``now`` injectable for determinism)."""
    now = now or datetime.now()  # wall clock only for run ids
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in strategy)
    d = Path(runs_root) / f"{now:%Y%m%d-%H%M%S}_{safe}_{hash8[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def update_latest(run_dir: str | Path) -> Path | None:
    """Point ``<runs_root>/LATEST`` at ``run_dir`` (relative symlink). Best effort; returns link path."""
    run_dir = Path(run_dir)
    link = run_dir.parent / "LATEST"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(run_dir.name)
        return link
    except OSError:
        return None


def write_json(path: str | Path, obj: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(jsonable(obj), indent=2, sort_keys=False, allow_nan=False), encoding="utf-8")
    return p


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(path: str | Path, df: pd.DataFrame, index: bool = True) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=index)
    return p


def env_info(seed: int | None = None) -> dict:
    """Versions, git sha, seed. Never raises."""
    info: dict[str, Any] = {"python": sys.version.split()[0], "platform": platform.platform(), "seed": seed}
    for mod in ("numpy", "pandas", "scipy", "plotly", "pyarrow", "pydantic"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:
            info[mod] = None
    try:
        info["git_sha"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                         timeout=5).stdout.strip() or None
    except Exception:
        info["git_sha"] = None
    return info


def write_core_artifacts(run_dir: Path, result: Any) -> list[str]:
    """equity.parquet, returns_daily.csv, trades.csv, costs_daily.csv. Returns written file names."""
    written = []
    eq = pd.Series(result.equity).rename("equity")
    try:
        eq.to_frame().to_parquet(run_dir / "equity.parquet")
        written.append("equity.parquet")
    except Exception:  # pyarrow missing -> csv fallback
        write_csv(run_dir / "equity.csv", eq.to_frame())
        written.append("equity.csv")
    write_csv(run_dir / "returns_daily.csv", pd.Series(result.returns_daily).rename("return").to_frame())
    written.append("returns_daily.csv")
    tr = getattr(result, "trades", None)
    if tr is not None:
        write_csv(run_dir / "trades.csv", tr, index=False)
        written.append("trades.csv")
    cd = getattr(result, "costs_daily", None)
    if cd is not None:
        write_csv(run_dir / "costs_daily.csv", pd.Series(cd).rename("costs").to_frame())
        written.append("costs_daily.csv")
    return written
