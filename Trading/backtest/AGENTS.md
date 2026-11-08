# AGENTS.md - tradelab (read this first)

`tradelab` is a leakage-safe backtesting framework (intraday-first, daily-capable). You write a strategy, run one
command, and read `runs/LATEST/summary.md`. Everything runs from this directory with the project venv:

```bash
cd Trading/backtest            # all paths below are relative to here
PY=.venv/bin/python            # NEVER use bare python3 (wrong env). No venv? `make env`
```

## 1. Quickstart

| Goal | Command |
|---|---|
| List strategies / describe params | `$PY -m tradelab list-strategies` / `$PY -m tradelab describe sma_cross` |
| New strategy skeleton | `$PY -m tradelab init-strategy my_strat --mode vector\|event` (writes `strategies/my_strat.py`) |
| **Leak check (mandatory)** | `$PY -m tradelab check-causality experiments/x.yaml` (exit 4 = leak) |
| Backtest + full report | `$PY -m tradelab run experiments/x.yaml` |
| Parameter search (grid -> DSR/PBO/heatmaps) | `$PY -m tradelab optimize experiments/x.yaml [--n-jobs 4]` |
| Walk-forward (stitched OOS, per-fold params) | `$PY -m tradelab walkforward experiments/x.yaml` |
| Rebuild a report from a run dir | `$PY -m tradelab report runs/<dir>` |
| Compare runs | `$PY -m tradelab compare runs/<a> runs/<b>` -> `runs/compare_*/compare.html` |
| Data checks / fetch | `$PY -m tradelab validate-data x.yaml` / `fetch-data x.yaml --dry-run` |
| Tests | `make test` (`.venv/bin/pytest -q`), lint `make lint` |

Exit codes: `0` ok, `2` config error (bad YAML/params/strategy, optimize without grid), `3` data error, `4` look-ahead leak detected.
Try it now: `$PY -m tradelab run experiments/example_daily.yaml` (synthetic data, no network).

## 2. Config (YAML, `extra=forbid`: a typo is an error)

```yaml
config_version: 1
name: my_run
data: {source: synthetic, symbols: [SPY], start: "2010-01-04", end: "2023-12-29", freq: 1d}   # yfinance|csv|parquet|databento|synthetic
strategy:
  name: donchian                 # registered name, or "module:Class", or path: strategies/file.py
  params: {n: 20}
  warmup_sessions: 300           # optional; history before a window start (default 300 daily / 20 intraday)
  grid: {n: [10, 20, 40, 60]}    # optional; dict of param -> values, or "auto" (uses grid(...) hints in Params)
execution: {fill: next_open, commission_bps: 1, slippage_bps: 1}     # intraday futures: slippage_ticks, flatten_at, limit_fill: through|touch, risk: {...}
robustness:                      # all optional
  walkforward: {is_len: 750, oos_len: 250, scheme: rolling, purge: 5}   # sessions; needs strategy.grid
  bootstrap_n: 2000, mc_n: 2000, cost_mults: [0, 1, 2, 3], objective: sharpe, n_jobs: 1, pbo_slices: 16
analytics: {periods_per_year: 252}   # 365 for crypto
initial_capital: 100000
seed: 1
```
Full field list: `src/tradelab/config/schema.py`. Examples: `experiments/example_daily.yaml`, `experiments/example_mnq_intraday.yaml`.
Intraday: `freq: 5m`, `base_freq: 1m` (load 1m, session-resample to 5m), `session: rth|all`.

## 3. Add a strategy in < 50 lines

Strategies live in `strategies/*.py` (auto-discovered) and decide at the **close of bar t**; the engine owns all shifting
(fill at the open of t+1). Never shift for execution yourself. Features may only use data stamped <= t.

**Vector** (target position per bar: weight, or units with `execution.vector_sizing: units`):
```python
# strategies/donchian.py
from tradelab.features import donchian
from tradelab.strategy import Params, Strategy, grid, register
import pandas as pd

class DonchianParams(Params):                     # extra=forbid; grid() gives optimiser hints
    n: int = grid(20, low=10, high=60, step=10)

@register
class Donchian(Strategy):
    name, mode = "donchian", "vector"
    Params = DonchianParams
    description = "Long above the prior-n-bar high, flat below the prior-n-bar low."
    def signals(self, data):                      # data: Panel. returns DataFrame bar index x symbol
        out = {}
        for s in data.symbols:
            b = data[s]; ch = donchian(b["high"], b["low"], self.params.n)   # channel of PREVIOUS n bars
            state = pd.Series(float("nan"), index=b.index)
            state[b["close"] > ch["upper"]] = 1.0
            state[b["close"] < ch["lower"]] = 0.0
            out[s] = state.ffill().fillna(0.0)
        return pd.DataFrame(out, index=data.index)
```
**Event** (orders, intraday, stops/targets, risk-% sizing):
```python
# strategies/prior_high_break.py
from tradelab.strategy import Order, Params, Strategy, register

class PhbParams(Params):
    risk_pct: float = 0.005

@register
class PriorHighBreak(Strategy):
    name, mode = "prior_high_break", "event"
    Params = PhbParams
    description = "Long when close breaks the prior session's high; stop = prior session low."
    def prepare(self, data):                      # causal vectorised features, one array per name, len == n_bars
        b = data[data.primary]; g = b.groupby("session_date")
        hi = g["high"].max().shift(1).reindex(b["session_date"]).to_numpy()   # PRIOR session only (shift(1))
        lo = g["low"].min().shift(1).reindex(b["session_date"]).to_numpy()
        return {"prev_hi": hi, "prev_lo": lo}
    def on_bar(self, ctx):                        # called at the close of every bar; returns Order | [Order] | None
        hi, lo = ctx.f("prev_hi"), ctx.f("prev_lo")
        if ctx.position == 0 and ctx.trades_today == 0 and hi == hi and ctx.close > hi:
            return Order("buy", risk_pct=self.params.risk_pct, stop=lo, target=ctx.close + 2 * (ctx.close - lo))
```
Useful APIs: `data.field("close")` (bar x symbol), `data[sym]` (bars: open/high/low/close/volume, optional bid_vol/ask_vol,
`session_date`, `session_type`, `bar_in_session`, `is_session_last`), `data.specs[sym]` (tick_size, point_value), `data.primary`.
`Order(side, qty|risk_pct, entry=market|limit|stop, price, stop, target, trailing, time_stop_bars, valid_bars, tag)`,
`Order.flatten()`, `Order.modify(stop=...)`. `ctx`: `close position entry_price stop target bars_held equity trades_today
consecutive_losses session_pnl ts_local minute_of_day spec f(name) hist(name, n)`. Optional feature `_active` (bool array) lets the
engine skip `on_bar` while flat (speed). Features library: `tradelab.features` (sma, ema, rsi, atr, donchian, session_vwap,
confirmed_swings, session_profiles/prior_session_levels, delta_features, fib_zone, ...), all causal.
Risk rules (`execution.risk`: trade_window, max_trades_per_day, stop_after_consecutive_losses, daily_loss_limit_usd/_r) are
engine-enforced. A strategy may declare `warmup_sessions = N` as a class attribute.

Then: `check-causality` -> `run` -> read the summary. Worked example (the vector strategy above, `grid: auto`, walk-forward): `strategies/donchian.py` + `experiments/example_donchian.yaml`;
`$PY -m tradelab optimize experiments/example_donchian.yaml && $PY -m tradelab walkforward experiments/example_donchian.yaml`. New strategies are picked up by the parametrised leakage tests (`make test`).

## 4. Where outputs land and how to read them

`runs/<YYYYMMDD-HHMMSS>_<strategy>_<hash8>/`, with `runs/LATEST` -> newest. **Read `runs/LATEST/summary.md` first** (fixed headings,
`- key: value`, < ~110 lines): Meta -> Headline metrics -> Trades -> R-multiples -> Benchmark -> **Integrity** (causality, data quality)
-> **Robustness** (verdict) -> Cost sensitivity -> **Warnings** -> Files.

Other artifacts: `metrics.json` (all metrics), `robustness.json` (PSR/DSR/PBO/bootstrap/MC/cost/regimes/walk-forward/verdict, plus an
`errors` key if an analysis crashed - investigate it), `tearsheet.html` (self-contained, open in a browser: overview, equity/DD,
returns, trades+R, robustness, grid heatmaps, walk-forward, trade viewer), `trades.csv`, `equity.parquet`, `returns_daily.csv`,
`costs_daily.csv`, `tables/*.csv`, `grid_results.parquet`, `walkforward.json`, `best_params.json` (optimize), `causality.json`,
`data_quality.json`, `config.resolved.yaml`, `env.json` (versions, git sha, seed, data fingerprint). `runs/_trials.jsonl` = trial ledger.

**Verdict** (`Robustness` section; advisory traffic lights green/amber/red): DSR > 0.95 (deflated for N trials), PBO < 0.5,
walk-forward efficiency (OOS/IS Sharpe) > 0.5, still positive at 2x costs, >= 100 trades, grid plateau score >= 0.7, PSR(0) > 0.95.
Overall `red` if anything is red. A green verdict is not proof of an edge; a red one is a strong reason to stop. Always read
**Warnings**, check `Integrity -> causality: PASS`, and compare the cost table (edge must survive 2x costs). For `optimize`, the
reported run is the in-sample best config: judge it by DSR/PBO/plateau, never by its Sharpe.

## 5. Pitfalls (each of these has burned real backtests)

1. **Look-ahead.** Decision uses bar t's close, fill is at t+1 open (engine). `same_close_unsafe` needs `execution.allow_unsafe: true` and is a leak. Run `check-causality` on every new/changed strategy; do not trust results while `Integrity` shows FAIL (exit 4).
2. **Bar-end stamps.** Every bar is stamped at its CLOSE (known at that time). Sources that stamp bar OPEN (Databento, FirstRate, IBKR, yfinance intraday) are converted by presets; a custom CSV needs `options: {tz: ..., stamp: start|end}`. Off-by-one-bar stamping silently leaks or delays.
3. **Prior-session features** (yesterday's high/low, value area, VWAP) must be joined on the PREVIOUS session (`shift(1)` on the per-session aggregate, as in the event example) - never the current session's final aggregate.
4. **Fractal / swing pivots** need k bars to confirm: use `features.confirmed_swings` (exposed at pivot + k) rather than centred windows.
5. **Overfitting and trial honesty.** Every parameter you try is a trial. `optimize`/`run` append to `runs/_trials.jsonl`; DSR deflates by the per-strategy count. **Never delete or edit `runs/_trials.jsonl`** and never "start fresh" to look better. Prefer coarse grids on meaningful parameters; require a plateau (not a spike), walk-forward efficiency, and PBO < 0.5.
6. **Survivorship** in equity universes (today's index members): results are optimistic; the framework warns but cannot fix it. Futures: use continuous contracts.
7. **Roll gaps.** Back-adjusted continuous futures: use `data.continuous: volume|calendar` (+ `data.adjust: difference|ratio|none`) on per-contract data; roll gaps are stripped from P&L. Back-adjusted price LEVELS are not stable as data is appended (see `docs/EXECUTION_MODEL.md` section 7). Do not stitch unadjusted contracts.
8. **yfinance intraday caps** (1m ~7 days, 5m/15m ~60 days). Fine for smoke tests, not for research. Use Databento/parquet.
9. **Approximated delta.** Without `bid_vol/ask_vol`, order-flow features use a tick-rule/CLV approximation (labelled `approx_delta`). Do not claim true order-flow results from it.
10. **Few trades.** < 30 trades: statistics are noise (the summary warns); < 100: amber. Do not tune on it.
11. **DST / sessions.** All exchange-time logic uses `zoneinfo`; `session_date` for Globex futures rolls at 18:00 ET. Do not hand-compute UTC offsets. Use `trade_window`/`flatten_at` in exchange time.
12. **Warm-up in window runs.** Walk-forward/`run_fn(start=, end=)` computes features with `warmup_sessions` of history before `start` but trades only inside `[start, end]`. Intraday starts flat; a daily vector strategy may enter at the first bar of the window. Too-short warm-up silently degrades early folds - set `strategy.warmup_sessions` >= your longest lookback (in sessions).
13. **Daily vector trades are approximate** (derived from position segments); trust the equity curve, not trade-level stats, for vector strategies (the trade Monte Carlo is skipped for them).

## 6. Data

- Synthetic (default for tests, no network): `data: {source: synthetic, symbols: [MNQ], freq: 5m, base_freq: 1m, options: {seed: 7, bid_ask: true}}`.
- Files: `source: parquet|csv`, `options: {path: data_store/databento/MNQ_1m.parquet, preset: databento_ohlcv_1m}` (presets: `databento_ohlcv_1m|1s`, `firstrate`, `ibkr_export`, `generic_end`).
- **Databento (paid; always cost-check first).** `export DATABENTO_API_KEY=...`, write a config with `data: {source: databento, symbols: [MNQ.c.0], start: ..., end: ..., freq: 1m, options: {dataset: GLBX.MDP3, stype_in: continuous}}`, then
  `$PY -m tradelab fetch-data x.yaml --dry-run` (prints `metadata.get_cost`, downloads nothing), then `fetch-data x.yaml --max-cost-usd 5` (refuses above the limit; raw data cached in `data_store/databento/`, git-ignored). Then point a run config at the parquet with the preset.
- Quality: `validate-data x.yaml` (dupes, gaps, OHLC consistency, stale/zero-volume bars, missing sessions); `data.strict_quality: true` fails the run (exit 3). Reports land in `data_quality.json` and `summary.md`.
- Add instruments in `src/tradelab/data/instruments.yaml` (tick, point value, per-side commission, tz, session) or per run via `data.instruments: {SYM: {...}}`.

## 7. Extension points

- **Data source**: class with `load(symbol, start, end, freq, *, adjusted=True, **options) -> DataFrame` (bar-END UTC index, open/high/low/close/volume) in `src/tradelab/data/sources/`, add to `SOURCES`. Timestamp-convention presets: `files.py::PRESETS`.
- **Strategy from elsewhere**: entry point group `tradelab.strategies`, `TRADELAB_STRATEGIES=dir1:dir2`, `strategy.path`, or `name: module:Class`.
- **Metrics**: `src/tradelab/analytics/` (everything consumes `RunResult` only; frozen contract in `docs/ARCHITECTURE.md` section 5, definitions in `docs/METRICS.md`). Annualisation always from daily returns.
- **Tearsheet section**: subclass `tradelab.report.Section` (`id, title, order`, `render(ctx) -> html`) and decorate with `@register_section`; a failing section prints its error instead of breaking the page.
- **Robustness tool**: functions taking an injected `run_fn` (never import engines); see `docs/ROBUSTNESS.md`. Wire into `report/builder.py::run_default_analyses` and `summary_md.py`.
- **Engine behaviour**: `docs/EXECUTION_MODEL.md` is authoritative (gaps, intrabar policy, costs, sizing). Changing `engine/event.py` or `engine/vector.py` needs hand-computed tests (`tests/unit/engine/`).

## 8. Conventions

Standalone package (no imports from `mrscore` or `Trading.utils`). Wall clock only in `util/clock.py`; randomness via seeds in config
(identical config + data => identical hash and results). Docs: `docs/ARCHITECTURE.md` (design), `docs/EXECUTION_MODEL.md`,
`docs/METRICS.md`, `docs/ROBUSTNESS.md`. Do not commit `runs/`, `data_cache/`, `data_store/` (git-ignored).
