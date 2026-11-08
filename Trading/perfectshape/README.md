# perfectshape

Scan a universe of instruments for **weighted baskets whose combined price traces an ideal shape** (a straight
uptrend, a straight downtrend, or a flat oscillating range) and rank them by **how long the shape has held**.

Successor of `Trading/utils/range/range.py::PerfectRange` and `Trading/algo/ranker` (single-instrument range
ranking): same idea, generalised to multi-instrument baskets and to trends, vectorised so the S&P 500 scans in
about 1.5 minutes.

```bash
cd Trading/perfectshape
make env                                              # uv venv + editable install
.venv/bin/python -m perfectshape scan configs/smoke.yaml   # offline, synthetic, ~2 s
.venv/bin/python -m perfectshape scan configs/sp500.yaml   # downloads/caches 11y of S&P 500 closes
xdg-open runs/LATEST/report.html                      # or read runs/LATEST/summary.md
```

## How it works

1. **Universe -> panel.** Lists in `universes/` (csv/txt/json/yaml) are merged; closes come from yfinance
   (auto-adjusted), cached per ticker in `data_cache/yfinance/*.npz` (re-downloaded after `max_age_days`;
   a fixed past `data.end` is never re-downloaded). Union calendar, short holes forward-filled.
2. **Fit end.** The last `holdout_bars` (default 21) are never used by the search.
3. **Search, per shape and per lookback window** (`windows`, e.g. 3 months ... 10 years):
   * every instrument is scored on its own (one vectorised pass);
   * from each of the best `seeds` singles, a basket grows greedily: every other instrument is tried as the
     next member, weights are re-solved for all candidates in one batched solve, the best-scoring addition
     is kept, until `max_assets` or the gain < `min_improvement`.
   * Weight objectives (closed form, see `solver.py`):
     * trends: maximise the slope t-stat (move along the line / noise around it): `w ~ R^-1 c`;
     * range: minimise quadratic drift relative to oscillation (smallest generalised eigenvector).
     * Long-only + `max_weight` enforced by projection; weights sum to 1.
4. **Duration.** Each basket is held as fixed shares and re-scored on every window of the ladder; *held* = the
   longest window whose score >= `threshold`.
5. **Alive.** Over the holdout, a trend must stay on the right side of its channel and its worst counter-move
   must not exceed the 95th percentile of same-length counter-moves inside the held window; a range must stay
   inside its padded band.
6. **Rank**: alive baskets by held duration, then score; overlapping baskets and over-used members are
   thinned (`max_overlap`, `max_per_member`).

## Scores (all in [0, 1], `shapes.py`)

| shape | score | gates |
|---|---|---|
| uptrend / downtrend | `sqrt(R2 * (1 - adverse/move))`: R2 of a straight line in log space; adverse = max drawdown (up) or rally (down) relative to the whole move | right direction, \|annualised move\| >= `min_annual_return` |
| range | `sqrt((1 - drift/band) * (1 - exp(-swings/3)))`: drift = range of a quadratic trend fit; band = p95-p5; swings = trips between the lower and upper quintile zones | band height >= `min_range_height`, drift/band <= `max_range_drift` |

Every basket member beyond the first costs `complexity_penalty` (2%) of the score.

## Outputs (`runs/<stamp>_<name>_<hash>/`, `runs/LATEST`)

`summary.md`, `results.csv` (one row per ranked basket: members, weights at fit start, drifted weights now,
held duration, metrics, per-window scores), `results.json`, `report.html` (self-contained: tables + charts with
the fitted line/band and the holdout), `config.resolved.json`.

## Extending

* **Universe**: drop a file in `universes/` and add its name to `universe.lists` (`perfectshape universe list`).
  Fetchable lists: `perfectshape universe refresh sp500` (add a fetcher to `universe.FETCHERS`).
* **Shape**: subclass `shapes.Shape` (`score`, `channel`, `objective`, `direction`) and `@register_shape`.
* **Weight objective**: add a branch in `solver.Solver` (batched over candidate sets).
* **Data source**: return `{ticker: (dates, close)}` and plug it into `data/sources.load_panel`.

## Caveats

This is a **descriptive, in-sample search**: with hundreds of instruments some shapes are coincidence. The
holdout check, the duration ladder and the complexity penalty push against it, but treat results as
candidates for research, not signals. The universe is today's index members (survivorship bias).
Not supported yet: market-neutral (sum of weights 0) baskets, rebalanced baskets, intraday bars.

`make test` / `make lint`.
