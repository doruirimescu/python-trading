"""Golden test: fixed synthetic RunResult -> frozen metrics. Regenerate deliberately with
``TRADELAB_UPDATE_GOLDEN=1 pytest tests/golden`` after an intentional metric change."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from synth import make_result  # noqa: E402

from tradelab.analytics import compute_metrics  # noqa: E402
from tradelab.robustness import block_bootstrap, psr  # noqa: E402

GOLDEN = Path(__file__).with_name("metrics_expected.json")


def _flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[f"{prefix}{k}"] = float(v)
    return out


def _current():
    res = make_result(n_days=500, seed=7)
    flat = _flatten(compute_metrics(res))
    flat["psr0"] = psr(res.returns_daily)
    bs = block_bootstrap(res.returns_daily, n=300, seed=42).summary
    flat["bootstrap.sharpe_p05"] = bs["sharpe_p05"]
    flat["bootstrap.sharpe_p95"] = bs["sharpe_p95"]
    return flat


def test_golden_metrics():
    cur = _current()
    if os.environ.get("TRADELAB_UPDATE_GOLDEN") or not GOLDEN.exists():
        GOLDEN.write_text(json.dumps(cur, indent=1, sort_keys=True))
        if not os.environ.get("TRADELAB_UPDATE_GOLDEN"):
            pytest.skip("golden file created; rerun")
    exp = json.loads(GOLDEN.read_text())
    assert set(exp) == set(cur), set(exp) ^ set(cur)
    for k, v in exp.items():
        assert cur[k] == pytest.approx(v, rel=1e-9, abs=1e-12), k
