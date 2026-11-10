import numpy as np
import pytest

from perfectshape.config import RunConfig, ScoringConfig
from perfectshape.data.panel import align
from perfectshape.pipeline import scan
from perfectshape.shapes import get_shape, linear_fit, zone_swings
from perfectshape.solver import Bounds, Solver, project_weights

T = 300
tau = np.linspace(0, 1, T)
SC = ScoringConfig()


def test_linear_fit_exact_line():
    Y = np.column_stack([1 + 0.5 * tau, 2 - 0.3 * tau])
    a, b, resid, r2 = linear_fit(Y)
    np.testing.assert_allclose(b, [0.5, -0.3], atol=1e-12)
    np.testing.assert_allclose(r2, 1.0)
    assert np.abs(resid).max() < 1e-12


def test_trend_scores_rank_shapes():
    rng = np.random.default_rng(0)
    straight = np.exp(0.4 * tau)
    noisy = np.exp(0.4 * tau + np.cumsum(rng.normal(0, 0.02, T)))
    falling = np.exp(-0.4 * tau)
    flat = 1 + 0.001 * np.sin(tau * 20)
    up = get_shape("uptrend").score(np.column_stack([straight, noisy, falling, flat]), SC)
    assert up.score[0] > 0.99
    assert up.score[0] > up.score[1]
    assert up.score[2] == 0 and up.score[3] == 0          # wrong direction / too flat are gated
    down = get_shape("downtrend").score(np.column_stack([falling, straight]), SC)
    assert down.score[0] > 0.99 and down.score[1] == 0


def test_range_score_prefers_oscillation_over_drift():
    sine = 1 + 0.1 * np.sin(2 * np.pi * tau * 4)
    drift = 1 + 0.3 * tau + 0.02 * np.sin(2 * np.pi * tau * 4)
    r = get_shape("range").score(np.column_stack([sine, drift]), SC)
    assert r.score[0] > 0.8 and r.score[1] == 0
    assert zone_swings(np.log(sine)[:, None])[0] >= 7


def test_band_trades_counts_sine_cycles():
    from perfectshape.shapes import band_trades
    Y = np.log(1 + 0.1 * np.sin(2 * np.pi * tau * 4))[:, None]
    lo, mid, hi = np.percentile(Y, [10, 50, 90], axis=0)
    n_mid, cap, cov, _ = band_trades(Y, lo, mid, hi, "mid", segments=4)
    assert cov[0] == 1.0                                 # a trade closes in every quarter
    # 4 cycles = 4 shorts (peaks) + 4 longs (troughs); the last long is still open: the curve ends at the median
    assert n_mid[0] == 7
    np.testing.assert_allclose(cap, 3 * (mid - lo) + 4 * (hi - mid))
    n_opp, _, _, _ = band_trades(Y, lo, mid, hi, "opposite")
    assert n_opp[0] == 7                                 # trough->peak / peak->trough legs after the first edge


def test_range_score_rewards_frequent_and_large_swings():
    sc = get_shape("range").score
    slow, fast = (1 + 0.1 * np.sin(2 * np.pi * tau * c) for c in (2, 8))
    small, big = (1 + a * np.sin(2 * np.pi * tau * 4) for a in (0.06, 0.2))
    r = sc(np.column_stack([slow, fast, small, big]), SC)
    assert r.score[1] > r.score[0]                       # more swings
    assert r.score[3] > r.score[2]                       # bigger swings
    assert r.metrics["trades_per_year"][1] > r.metrics["trades_per_year"][0]


def test_project_weights_bounds():
    W = project_weights(np.array([[1.4, -0.2, -0.2], [0.2, 0.3, 0.5]]), Bounds(True, 0.7))
    np.testing.assert_allclose(W.sum(axis=1), 1)
    assert (W >= 0).all() and (W <= 0.7 + 1e-9).all()


def test_trend_solver_recovers_hedged_pair():
    rng = np.random.default_rng(1)
    wander = np.cumsum(rng.normal(0, 0.01, T))
    target = 1 + 0.5 * tau
    X = np.column_stack([target + wander, target - wander, 1 + np.cumsum(rng.normal(0, 0.01, T))])
    X /= X[0]
    s = Solver(X, "trend_tstat", direction=1)
    W = s.solve([0], np.array([1, 2]), Bounds(True, 0.7))
    np.testing.assert_allclose(W[0], [0.5, 0.5], atol=0.02)


def test_range_solver_cancels_drift():
    rng = np.random.default_rng(2)
    osc = 0.1 * np.sin(2 * np.pi * tau * 5)
    drift = 0.6 * tau
    X = np.column_stack([1 + osc + drift, 1 + osc - drift + rng.normal(0, 1e-3, T)])
    s = Solver(X, "range_ratio")
    W = s.solve([0], np.array([1]), Bounds(True, 0.7))
    np.testing.assert_allclose(W[0], [0.5, 0.5], atol=0.05)


def test_align_ffill_limited():
    d = np.arange("2024-01-01", "2024-01-11", dtype="datetime64[D]")
    a = (d, np.arange(10.0) + 1)
    b = (np.delete(d, [3, 6, 7, 8]), np.arange(6.0) + 1)
    p = align({"A": a, "B": b}, max_gap_bars=1)
    col = p.close[:, 1]
    assert np.isfinite(col[3])                       # 1-bar hole filled
    assert np.isnan(col[7]) and np.isnan(col[8])     # 3-bar hole not


@pytest.fixture(scope="module")
def planted():
    tickers = [f"S{i:02d}" for i in range(30)]
    plant = {"uptrend": ["S03", "S17"], "downtrend": ["S08", "S22"], "range": ["S11", "S26"]}
    cfg = RunConfig.model_validate({
        "universe": {"tickers": tickers},
        "data": {"source": "synthetic", "years": 6,
                 "synthetic": {"n_bars": 1600, "seed": 3, "plant": plant}},
        "search": {"windows": [126, 252, 504, 1008], "seeds": 30, "max_assets": 3},
    })
    return scan(cfg), plant


@pytest.mark.parametrize("shape", ["uptrend", "downtrend", "range"])
def test_scan_finds_planted_pair(planted, shape):
    out, plant = planted
    tops = out.ranked[shape][:3] if shape == "range" else out.ranked[shape][:1]   # random walks also form ranges
    hit = [r for r in tops if set(r.basket.members) == set(plant[shape])]
    assert hit, [r.basket.members for r in out.ranked[shape][:5]]
    assert hit[0].duration == 1008 and hit[0].alive


# ---------------------------------------------------------------- ratio mode (basket A / basket B)

def test_count_ratios_matches_enumeration():
    from perfectshape.config import RatioConfig
    from perfectshape.ratio import _library, _overlap_fn, _pair_chunks, count_ratios
    for k, overlap in [(1, False), (2, False), (3, False), (2, True)]:
        cfg = RatioConfig(k=k, allow_overlap=overlap)
        lib = _library(9, k)
        ov = _overlap_fn(lib, 9)
        n = 0
        for I, J in _pair_chunks(len(lib), chunk=17):
            if not overlap:
                sh = ov(I, J)
                assert (sh == [bool(set(lib[i]) & set(lib[j])) for i, j in zip(I, J)]).all()
                I = I[~sh]
            n += len(I)
        assert n == count_ratios(9, cfg), (k, overlap)


def test_ratio_config_is_symmetric_and_reads_legacy_keys():
    from perfectshape.config import RatioConfig
    assert RatioConfig.model_validate({"k_num": 3, "k_den": 3}).k == 3
    with pytest.raises(ValueError, match="symmetric"):
        RatioConfig.model_validate({"k_num": 2, "k_den": 3})


def test_fast_fits_match_the_reference():
    from perfectshape.shapes import linear_fit, poly_fit, quad_drift
    rng = np.random.default_rng(4)
    Y = np.cumsum(rng.normal(0, 0.01, (500, 40)), axis=0) + np.linspace(0, 0.3, 500)[:, None]
    a1, b1, _, r1 = linear_fit(Y, with_resid=True)
    a2, b2, res, r2 = linear_fit(Y, with_resid=False)
    assert res is None
    np.testing.assert_allclose([a1, b1, r1], [a2, b2, r2], atol=1e-10)
    F = poly_fit(Y, 2)
    np.testing.assert_allclose(quad_drift(Y), F.max(axis=0) - F.min(axis=0), rtol=0.01, atol=1e-6)


def test_log_difference_search_matches_ratio_scoring():
    """The fast path (log A - log B, slope orientation) ranks exactly like scoring A/B and B/A directly."""
    from perfectshape.ratio import search_ratio_window
    cfg = _small_ratio_cfg()
    out = scan(cfg)
    for shape in ("uptrend", "range"):
        fast = search_ratio_window(out.panel, get_shape(shape), 504, out.fit_end, cfg.ratio, cfg.scoring)
        # reference: score every surviving basket pair both ways with the plain curve scorer
        for b in fast[:20]:
            idx = [out.panel.symbols.index(m) for m in b.members]
            didx = [out.panel.symbols.index(m) for m in b.den_members]
            X = out.panel.close[out.fit_end - 504:out.fit_end]
            X = X / X[0]
            R = X[:, idx].mean(axis=1) / X[:, didx].mean(axis=1)
            ref = get_shape(shape).score(R[:, None], cfg.scoring).score[0] * (1 - 0.02 * (b.size - 1))
            assert ref == pytest.approx(b.fit_score, rel=1e-9), (shape, b.members, b.den_members)


def test_ratio_mode_rejects_downtrend_and_defaults_shapes():
    base = {"universe": {"tickers": ["A"]}, "search": {"mode": "ratio"}}
    assert RunConfig.model_validate(base).search.shapes == ["uptrend", "range"]
    with pytest.raises(ValueError, match="rising B/A"):
        RunConfig.model_validate({**base, "search": {"mode": "ratio", "shapes": ["downtrend"]}})


RATIO_PLANTS = {
    "up": {"shape": "uptrend", "num": ["S01", "S07"], "den": ["S03", "S10"]},
    # planted falling: must come back flipped, as (S04+S09) / (S02+S05) rising
    "down": {"shape": "downtrend", "num": ["S02", "S05"], "den": ["S04", "S09"]},
    "range": {"shape": "range", "num": ["S00", "S06"], "den": ["S08", "S11"]},
}


def _ratio_scan(plant: dict):
    # one plant per universe: two exact planted ratios can be mixed into other, equally exact ones
    cfg = RunConfig.model_validate({
        "universe": {"tickers": [f"S{i:02d}" for i in range(12)]},
        "data": {"source": "synthetic", "years": 6,
                 "synthetic": {"n_bars": 1600, "seed": 5, "plant": {"p": plant}}},
        "search": {"mode": "ratio", "windows": [126, 252, 504, 1008]},
        "ratio": {"k_num": 2, "k_den": 2},
    })
    return scan(cfg)


@pytest.fixture(scope="module")
def planted_ratio():
    return {k: _ratio_scan(v) for k, v in RATIO_PLANTS.items()}


def _top(out, shape):
    r = out.ranked[shape][0]
    return set(r.basket.members), set(r.basket.den_members), r


def test_ratio_scan_finds_planted_trends_oriented_up(planted_ratio):
    num, den, r = _top(planted_ratio["up"], "uptrend")
    assert (num, den) == ({"S01", "S07"}, {"S03", "S10"})
    assert r.duration == 1008 and r.alive and r.metrics["annual_return"] > 0.1
    num, den, r = _top(planted_ratio["down"], "uptrend")
    assert (num, den) == ({"S04", "S09"}, {"S02", "S05"})          # flipped
    assert r.duration == 1008 and r.alive and r.metrics["annual_return"] > 0.1


def test_ratio_scan_finds_planted_range(planted_ratio):
    want = {frozenset({"S00", "S06"}), frozenset({"S08", "S11"})}
    hit = [r for r in planted_ratio["range"].ranked["range"][:3]        # random ratios also form ranges
           if {frozenset(r.basket.members), frozenset(r.basket.den_members)} == want]
    assert hit and hit[0].duration == 1008 and hit[0].alive


def test_ratio_report_writes(planted_ratio, tmp_path):
    from perfectshape.report.writer import write_run
    run = write_run(planted_ratio["up"], root=tmp_path)
    assert "(S" in (run / "summary.md").read_text()
    assert "den_members" in (run / "results.csv").read_text().splitlines()[0]
    assert (run / "report.html").stat().st_size > 1000


# ---------------------------------------------------------------- range scoring: frequent, large swings win

AMPS = [0.05, 0.10, 0.20]            # sine amplitude (relative)
CYCLES = [4, 8, 16, 32]              # full oscillations over the window (2 in 10y reads as an arc: drift-gated)
T_RANGE = 2520                       # 10 years of daily bars


def _sine(amp, cycles, T=T_RANGE, trend=0.0):
    t = np.linspace(0, 1, T)
    return (1 + amp * np.sin(2 * np.pi * cycles * t)) * np.exp(trend * t)


def test_range_score_increases_with_amplitude_and_frequency():
    rng = get_shape("range")
    grid = np.array([[rng.score(_sine(a, c)[:, None], SC).score[0] for c in CYCLES] for a in AMPS])
    assert (grid > 0).all(), grid
    assert (np.diff(grid, axis=0) > 0).all(), f"larger amplitude must score higher\n{grid}"
    assert (np.diff(grid, axis=1) > 0).all(), f"higher frequency must score higher\n{grid}"
    assert grid.argmax() == grid.size - 1                    # largest amplitude x highest frequency wins


def test_range_harvest_and_trades_follow_the_sine():
    rng = get_shape("range")
    m = rng.score(np.column_stack([_sine(0.1, c) for c in CYCLES]), SC).metrics
    years = (T_RANGE - 1) / SC.periods_per_year
    # one long + one short per cycle (the last one may still be open at the window end)
    np.testing.assert_allclose(m["trades_per_year"] * years, [2 * c for c in CYCLES], atol=1)
    assert (np.diff(m["harvest"]) > 0).all() and (np.diff(m["per_trade"]) == pytest.approx(0, abs=0.01))


@pytest.mark.parametrize("name,curve", [
    ("straight uptrend", np.exp(0.8 * np.linspace(0, 1, T_RANGE))),
    ("straight downtrend", np.exp(-0.8 * np.linspace(0, 1, T_RANGE))),
    ("linear uptrend", 1 + 1.5 * np.linspace(0, 1, T_RANGE)),
    ("sine riding an uptrend", _sine(0.1, 8, trend=0.8)),
    ("sine riding a downtrend", _sine(0.2, 16, trend=-1.0)),
    ("arc", 1 + 0.5 * np.sin(np.pi * np.linspace(0, 1, T_RANGE))),
    ("too small to trade", _sine(0.02, 16)),
])
def test_range_discards_trends_and_untradable_curves(name, curve):
    assert get_shape("range").score(curve[:, None], SC).score[0] == 0, name


def test_scan_ranks_ranges_by_amplitude_and_frequency_and_drops_trends():
    """End to end: a panel of pure sines and trends; ranges must come out ordered by amplitude x frequency."""
    from perfectshape.data.panel import Panel
    n = 1300
    t = np.arange(n)
    cols = {
        "BIGFAST": 1 + 0.20 * np.sin(2 * np.pi * t / 63),
        "BIGSLOW": 1 + 0.20 * np.sin(2 * np.pi * t / 252),
        "SMALLFAST": 1 + 0.08 * np.sin(2 * np.pi * t / 63),
        "SMALLSLOW": 1 + 0.08 * np.sin(2 * np.pi * t / 252),
        "UP": np.exp(0.0008 * t),
        "DOWN": np.exp(-0.0008 * t),
        "UPWAVE": np.exp(0.0008 * t) * (1 + 0.1 * np.sin(2 * np.pi * t / 63)),
    }
    dates = np.busday_offset(np.datetime64("2026-10-30"), np.arange(-n + 1, 1), roll="backward")
    panel = Panel(dates=dates, symbols=list(cols), close=np.column_stack(list(cols.values())))
    cfg = RunConfig.model_validate({
        "universe": {"tickers": list(cols)}, "data": {"source": "synthetic", "years": 6},
        "search": {"shapes": ["range"], "windows": [252, 504, 1008], "max_assets": 1},
        "ranking": {"max_per_member": 1},
    })
    ranked = [r.basket.members[0] for r in scan(cfg, panel=panel).ranked["range"]]
    assert ranked == ["BIGFAST", "SMALLFAST", "BIGSLOW", "SMALLSLOW"] or \
        ranked == ["BIGFAST", "BIGSLOW", "SMALLFAST", "SMALLSLOW"], ranked
    assert ranked[0] == "BIGFAST" and ranked[-1] == "SMALLSLOW"
    assert not {"UP", "DOWN", "UPWAVE"} & set(ranked)


def _wiggle(T=T_RANGE):
    t = np.linspace(0, 1, T)
    return t, 1 + 0.06 * np.sin(2 * np.pi * 24 * t)


def test_range_band_is_symmetric_and_ignores_one_sided_spikes():
    from perfectshape.shapes import range_band
    t, base = _wiggle()
    spiky = base * np.exp(0.6 * np.exp(-((t - 0.75) / 0.03) ** 2))     # one large rally, like a squeeze
    lo, mid, hi = range_band(np.log(np.column_stack([base, spiky])), 10)
    np.testing.assert_allclose(hi - mid, mid - lo)
    assert (hi - lo)[1] <= (hi - lo)[0] * 1.15                          # the spike does not widen the band


def test_one_large_deviation_does_not_raise_the_range_score():
    rng = get_shape("range")
    t, base = _wiggle()
    spiky = base * np.exp(0.6 * np.exp(-((t - 0.75) / 0.03) ** 2))
    regular = _sine(0.2, 24)                                            # big, repeated swings
    r = rng.score(np.column_stack([base, spiky, regular]), SC)
    assert r.score[1] <= r.score[0] + 1e-9, r.score                     # spike adds nothing
    assert r.score[2] > r.score[1], r.score
    assert r.metrics["per_trade"][1] <= r.metrics["per_trade"][0] * 1.15


def test_swings_confined_to_one_stretch_score_below_repeated_swings():
    rng = get_shape("range")
    t = np.linspace(0, 1, T_RANGE)
    everywhere = 1 + 0.15 * np.sin(2 * np.pi * 24 * t)
    burst = np.where(t > 0.75, 0.15 * np.sin(2 * np.pi * 24 * t), 0.0)  # same swings, last quarter only
    once = 1 + burst + 0.01 * np.sin(2 * np.pi * 200 * t)
    r = rng.score(np.column_stack([everywhere, once]), SC)
    assert r.metrics["coverage"][0] == 1.0 and r.metrics["coverage"][1] <= 0.5, r.metrics["coverage"]
    assert r.score[0] > r.score[1], r.score


def test_a_squeeze_through_the_band_is_penalised():
    """Like (XLE + SLV) / (XLI + SMH): small regular swings, then one rally far past the top edge. A short
    opened at the edge would have had to sit through it, so the range must not pass."""
    rng = get_shape("range")
    t, base = _wiggle()
    squeeze = base * np.exp(0.6 * np.exp(-((t - 0.75) / 0.03) ** 2))
    r = rng.score(np.column_stack([base, squeeze]), SC)
    assert r.metrics["pain"][1] > 3 * max(r.metrics["pain"][0], 0.3), r.metrics["pain"]
    assert r.score[0] > SC.threshold and r.score[1] < SC.threshold, r.score
    assert r.metrics["worst_against"][1] > 0.4                     # >40% against the short before reverting


# ---------------------------------------------------------------- sector ETF holdings + dashboard run control

def test_parse_ssga_holdings_drops_futures_cash_and_second_share_classes():
    import io as _io

    import openpyxl
    from perfectshape.holdings import parse_ssga_xlsx
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in [["Fund Name:", "Some Select Sector SPDR"], ["Ticker Symbol:", "XLC"], [], [],
                ["Name", "Ticker", "Identifier", "SEDOL", "Weight", "Sector", "Shares Held", "Local Currency"],
                ["ALPHABET INC CL A", "GOOGL", "x", "x", 10.5, "-", 1, "USD"],
                ["META PLATFORMS INC CLASS A", "META", "x", "x", 21.0, "-", 1, "USD"],
                ["ALPHABET INC CL C", "GOOG", "x", "x", 8.4, "-", 1, "USD"],
                ["BROWN FORMAN CORP CLASS B", "BF.B", "x", "x", 0.3, "-", 1, "USD"],
                ["XAC COMM SERVICES DEC26", "IXCZ6", "x", "x", 0.01, "-", 1, "USD"],
                ["SSI US GOV MONEY MARKET CLASS", "-", "x", "x", 0.2, "-", 1, "USD"],
                [], ["Before investing in a fund, consider ..."]]:
        ws.append(row)
    buf = _io.BytesIO()
    wb.save(buf)
    hs = parse_ssga_xlsx(buf.getvalue())
    assert [h.ticker for h in hs] == ["META", "GOOGL", "BF-B"]          # by weight; GOOG, futures, cash dropped


def _small_ratio_cfg(**kw):
    tickers = [f"S{i:02d}" for i in range(10)]
    return RunConfig.model_validate({
        "universe": {"tickers": tickers},
        "data": {"source": "synthetic", "years": 6, "synthetic": {"n_bars": 1300, "seed": 2}},
        "search": {"mode": "ratio", "windows": [252, 504, 1008]},
        "ratio": {"k_num": 2, "k_den": 2}, **kw})


def test_scan_control_partial_results_and_progress():
    from perfectshape.pipeline import ScanControl

    class Rec(ScanControl):
        def __init__(self):
            self.prog, self.partials = [], []

        def checkpoint(self, progress, detail=""):
            self.prog.append(progress)

        def partial(self, out):
            self.partials.append({k: len(v) for k, v in out.ranked.items()})

    rec = Rec()
    out = scan(_small_ratio_cfg(), control=rec)
    assert rec.prog == sorted(rec.prog) and rec.prog[-1] == 1.0          # monotone, ends at 100%
    assert len(rec.partials) == 3                                         # one per window, both shapes in each
    assert all(set(p) == {"uptrend", "range"} for p in rec.partials)
    assert out.done and {k: len(v) for k, v in out.ranked.items()} == rec.partials[-1]


def test_ratio_search_snapshots_both_shapes_mid_window():
    from perfectshape.ratio import search_ratio_window
    cfg = _small_ratio_cfg()
    out = scan(cfg)
    snaps = []
    shapes = [get_shape("uptrend"), get_shape("range")]
    import perfectshape.ratio as R
    old = R.CHUNK_ELEMENTS
    R.CHUNK_ELEMENTS = 20_000                                             # many small chunks
    try:
        final = search_ratio_window(out.panel, shapes, 1008, out.fit_end, cfg.ratio, cfg.scoring,
                                    on_snapshot=snaps.append, snapshot_every=0.0)
    finally:
        R.CHUNK_ELEMENTS = old
    assert len(snaps) > 3 and set(snaps[-1]) == {"uptrend", "range"}
    assert snaps[-1]["uptrend"] and snaps[-1]["range"]
    # the snapshot is the best so far: by the end it agrees with the final best
    best_final = final["uptrend"][0].fit_score
    assert max(b.fit_score for b in snaps[-1]["uptrend"]) <= best_final + 1e-12


def test_run_manager_pause_resume_stop(tmp_path, monkeypatch):
    import time as _time

    from perfectshape.dashboard import server
    monkeypatch.chdir(tmp_path)
    m = server.RunManager()
    m.start(_small_ratio_cfg(output={"dir": str(tmp_path / "runs")}))
    deadline = _time.time() + 30
    while m.progress < 0.2 and _time.time() < deadline:
        _time.sleep(0.01)
    m.pause()
    _time.sleep(0.3)
    p = m.progress
    _time.sleep(0.5)
    assert m.state == "paused" and m.progress == p                       # nothing moves while paused
    m.resume()
    m.thread.join(30)
    s = m.status(-1)
    assert s["state"] == "done" and s["payload"] and not s["payload"]["partial"] and s["run_dir"]
    m.start(_small_ratio_cfg(output={"dir": str(tmp_path / "runs")}))
    m.stop()
    m.thread.join(30)
    assert m.state == "stopped"


def test_dashboard_check_config_estimates_and_rejects():
    from perfectshape.dashboard.server import check_config
    ok = check_config(_small_ratio_cfg().model_dump(mode="json"))
    assert ok["ok"] and ok["instruments"] == 10 and ok["ratios"] == 630 and ok["est_seconds"] > 0
    raw = _small_ratio_cfg().model_dump(mode="json")
    raw["ratio"]["max_ratios"] = 100
    assert not check_config(raw)["ok"]
    raw["search"]["shapes"] = ["downtrend"]
    assert "rising B/A" in check_config(raw)["error"]


def test_trade_lab_series_payload_aligns_members_and_benchmark():
    from perfectshape.dashboard.server import series_payload
    data = _small_ratio_cfg().data
    out = series_payload(["S01", "S02"], ["S03", "S04"], "SPY", data)
    n = len(out["dates"])
    assert n == 1300 and out["bench"] == "SPY"
    assert set(out["close"]) == {"S01", "S02", "S03", "S04", "SPY"}
    assert all(len(v) == n for v in out["close"].values())
    with pytest.raises(ValueError, match="required"):
        series_payload(["S01"], [], "SPY", data)
