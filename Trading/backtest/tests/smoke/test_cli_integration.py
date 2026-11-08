"""CLI end-to-end on synthetic data: artifacts, exit codes, ledger, report/compare."""
import json
from pathlib import Path

import yaml

from tradelab.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _cfg(tmp, **over):
    cfg = {"data": {"source": "synthetic", "symbols": ["SPY"], "start": "2015-01-02", "end": "2019-12-31", "freq": "1d"},
           "strategy": {"name": "sma_cross", "params": {"fast": 10, "slow": 60}, "warmup_sessions": 100,
                        "grid": {"fast": [5, 10, 20], "slow": [40, 60, 100]}},
           "execution": {"commission_bps": 1}, "robustness": {"bootstrap_n": 100, "mc_n": 100,
                                                              "walkforward": {"is_len": 500, "oos_len": 250}}}
    cfg.update(over)
    p = Path(tmp) / "c.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


ARTIFACTS = ["metrics.json", "summary.md", "tearsheet.html", "robustness.json", "trades.csv", "data_quality.json", "env.json",
             "equity.parquet", "returns_daily.csv", "config.resolved.yaml", "causality.json", "grid_results.parquet"]


def test_run_optimize_walkforward_report_compare(tmp_path):
    out = tmp_path / "runs"
    cfg = _cfg(tmp_path)
    assert main(["run", cfg, "--out-dir", str(out)]) == 0
    d = (out / "LATEST").resolve()
    for f in ARTIFACTS + ["walkforward.json"]:
        assert (d / f).exists(), f
    html = (d / "tearsheet.html").read_text()
    assert "section failed" not in html
    rob = json.loads((d / "robustness.json").read_text())
    assert "dsr" in rob["psr"] and "pbo" in rob and rob["causality"]["ok"] and "errors" not in rob
    assert "- causality: PASS" in (d / "summary.md").read_text()
    n1 = len((out / "_trials.jsonl").read_text().splitlines())
    assert main(["optimize", cfg, "--out-dir", str(out)]) == 0
    assert main(["walkforward", cfg, "--out-dir", str(out)]) == 0
    assert len((out / "_trials.jsonl").read_text().splitlines()) == n1 + 2     # append-only, honest N
    d2 = (out / "LATEST").resolve()
    assert (d2 / "walkforward.json").exists()
    before = len((out / "_trials.jsonl").read_text().splitlines())
    assert main(["report", str(d2)]) == 0
    assert len((out / "_trials.jsonl").read_text().splitlines()) == before     # regenerating is not a trial
    assert main(["compare", str(d), str(d2), "--out-dir", str(tmp_path / "cmp")]) == 0
    assert (tmp_path / "cmp" / "compare.html").exists()


def test_exit_codes(tmp_path):
    out = str(tmp_path / "runs")
    bad = tmp_path / "bad.yaml"
    bad.write_text("nonsense: 1\n")
    assert main(["run", str(bad), "--out-dir", out]) == 2
    nogrid = _cfg(tmp_path, strategy={"name": "sma_cross"})
    assert main(["optimize", nogrid, "--out-dir", out]) == 2
    nodata = _cfg(tmp_path, data={"source": "parquet", "symbols": ["X"], "options": {"path": str(tmp_path / "missing.parquet")}})
    assert main(["run", nodata, "--out-dir", out]) == 3
    leak = _cfg(tmp_path, strategy={"name": "leaky_strats:LeakyVecFuture"})
    assert main(["run", leak, "--out-dir", out]) == 4
