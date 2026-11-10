# perfectshape

Scan a universe of instruments for **weighted baskets whose combined price traces an ideal shape** (a straight
uptrend, a straight downtrend, or a flat oscillating range) and rank them by **how long the shape has held**.
In **ratio mode** the same search runs over **basket ratios** in the style of `Trading/basket`:
`(A + B) / (C + D)` of equal-weight baskets, so it finds one group steadily outperforming another, or
oscillating against it.

Successor of `Trading/utils/range/range.py::PerfectRange` and `Trading/algo/ranker` (single-instrument range
ranking): same idea, generalised to multi-instrument baskets and to trends, vectorised so the S&P 500 scans in
about 1.5 minutes.

Tooling is managed by [mise](https://mise.jdx.dev) (`mise.toml`): it installs Python 3.13 and uv, and creates
and activates `.venv` automatically when you enter the directory.

```bash
cd Trading/perfectshape
mise trust && mise install                    # once: Python 3.13 + uv, creates .venv
mise run install                              # editable install + dev deps into .venv
mise run smoke                                # offline, synthetic, ~2 s
mise run sp500                                # downloads/caches 11y of S&P 500 closes
mise run country-ratios                       # basket ratios of country ETFs, ~30 s
mise run etf-pairs                            # A / B over 39 ETFs (sectors, factors, regions, bonds, gold), ~15 s
mise run etf-ratios                           # (A + B) / (C + D) over the same 39 ETFs, ~7 min
mise run dashboard                            # web UI: sector ETF -> 3 vs 3 stock ratios, play / pause, live
mise run scan configs/my.yaml                 # any config
xdg-open runs/LATEST/report.html              # or read runs/LATEST/summary.md
```

`mise tasks` lists all tasks (`install`, `scan`, `smoke`, `sp500`, `country-ratios`, `etf-pairs`,
`etf-ratios`, `dashboard`, `universe`, `test`, `lint`).

## Dashboard: sector stock ratios (`mise run dashboard`)

http://127.0.0.1:8765 (opens a browser tab; `python -m perfectshape dashboard --port N` for another port).
Pages use the Investing Nexus design system (live `nexus.css` / `nexus.js`, theme panel bottom right) and Plotly.

* **Configure** on the left: a Select Sector SPDR (XLK, XLE, XLU, ...), how many of its top holdings by
  weight to use (uncheck a stock to exclude it; the next one takes its place), basket sizes (3 vs 3 by default),
  shapes, lookback windows, the scoring / ranking knobs and the max ratios per window (the size cap) and the holdout length. Every
  setting has an ⓘ bubble explaining it (hover, focus or tap); the texts live in `TIPS` in `web/dashboard.js`. The box under the form shows the number of
  ratios and an estimated runtime; the YAML preview can be saved to `configs/` and run from the CLI later.
* **▶ Play** starts the scan; the progress bar, current step, elapsed time and ETA update every second, and the
  ranking (same tables and charts as `report.html`) is redrawn after every finished lookback window.
* **❚❚ Pause** holds the scan between chunks of work (within a second) without losing anything; **▶ Resume**
  continues it. **■ Stop** abandons it (partial results stay on the page, nothing is written).
* When it finishes the run is written to `runs/` like a CLI run, with links to its report, CSV and summary.
  Reopening the page while a scan runs or after it finished restores its config and results.
* **Refreshing never stops a scan**: it runs in the server's background thread, and the page only follows it.
  The front end (`src/perfectshape/web/`: `dashboard.html`, `dashboard.js`, `report.js`, `shapes.css`) is read
  from disk on every request, so a style or layout edit shows up on the next refresh while the scan keeps
  running. Only edits to Python code need a server restart (Ctrl+C, `mise run dashboard`), and that does end a
  running scan.

Size: all ratios are enumerated, so 3 vs 3 grows fast with the holdings used: top 12 = 9,240 ratios (seconds),
top 16 = 80,080 (~2.5 min), top 20 = 387,600 (~12 min), top 25 = 1.77 M (~55 min); `ratio.max_ratios` (3 M)
caps a run.
Pick the holdings that matter rather than the whole fund.

**Holdings** (`holdings.py`): `universe.lists: ["etf:XLK"]` with `universe.limit: 20` works in any config.
They come from State Street's daily holdings file of the fund (every constituent with its weight), cached per
day in `data_cache/holdings/`. Cash, money-market and the index futures the funds hold are dropped, and so is a
second share class of the same company (GOOG next to GOOGL). Inside the
directory (with mise activated in your shell) `python -m perfectshape ...` and `perfectshape ...` use the venv
directly; elsewhere, prefix with `mise exec --`.

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
   * In ratio mode, step 3 is replaced by the exhaustive ratio search below.
4. **Duration.** Each basket is held as fixed shares and re-scored on every window of the ladder; *held* = the
   longest window whose score >= `threshold`.
5. **Alive.** Over the holdout, a trend must stay on the right side of its channel and its worst counter-move
   must not exceed the 95th percentile of same-length counter-moves inside the held window; a range must stay
   inside its padded band.
6. **Rank**: trends by held duration, then score. Ranges (`ranking.range_sort: score`, the default) by score,
   i.e. by how much trading the band would have harvested: a range must have held at least `range_min_held`
   bars (504, 2 years) and is described by its best-scoring held window of at least `range_min_score_window`
   bars (252), whose band is the one you would trade now (`range_sort: duration` restores duration-first).
   Overlapping baskets and over-used members are then thinned (`max_overlap`, `max_per_member`).

## Ratio mode (`search.mode: ratio`, `ratio.py`)

The object of `Trading/basket` (mrscore `RatioUniverse`), searched for shapes instead of mean-reversion events:

* in each window, prices are normalised to 1.0 at the window start; a basket is the equal-weight mean of its
  members and a ratio is `basket(num) / basket(den)`, with `ratio.k_num` and `ratio.k_den` members;
* **every** ratio is enumerated (disjoint legs unless `allow_overlap`) and scored in vectorised chunks, without
  materialising all ratios at once; the best `keep_per_window` per window go on to the duration ladder and the
  holdout check, held as fixed shares in both legs;
* a falling A/B is a rising B/A, so trends are **oriented**: both orientations are scored and every trend is
  reported as "numerator outperforms denominator". Ratio mode therefore offers `uptrend` and `range` (the
  default); `downtrend` is rejected. A ratio range is a basket-rotation (mean-reversion) candidate.
* Size: `C(n, k_num) * C(n - k_num, k_den)` ratios (halved when `k_num == k_den`). 19 country ETFs: 11,628 at
  2 vs 2, 271,320 at 3 vs 3. The 39-ETF mix (`universes/etf_mix.txt`): 741 at 1 vs 1 (`etf_pairs.yaml`),
  246,753 at 2 vs 2 (`etf_ratios.yaml`, ~6 min on 8 cores). A run larger than `ratio.max_ratios` stops with an error before scanning, so use
  ETF/sector-sized universes, not the S&P 500.
* `complexity_penalty` counts all members of both legs. Every ratio in a run has the same size, so it only
  shifts the threshold; `configs/country_ratios.yaml` sets it to 0 and lowers `min_annual_return` to 5%
  because relative moves are smaller than outright ones.

```yaml
search: {mode: ratio, shapes: [uptrend, range]}
ratio: {k_num: 2, k_den: 2, allow_overlap: false, keep_per_window: 300, max_ratios: 3000000}
```

## Scores (all in [0, 1], `shapes.py`)

| shape | score | gates |
|---|---|---|
| uptrend / downtrend | `sqrt(R2 * (1 - adverse/move))`: R2 of a straight line in log space; adverse = max drawdown (up) or rally (down) relative to the whole move | right direction, \|annualised move\| >= `min_annual_return` |
| range | `sqrt(flat * repeat * harvest_term * pain_term)`: flat = 1 - drift/band (drift = range of a quadratic trend fit); band = median ± h, h = the smaller half of the p`q`-p`100-q` band (`range_band_pct`, 10), so a one-sided spike cannot widen it; harvest_term = `1 - exp(-harvest/range_harvest_scale)`; repeat and pain below | band height >= `min_range_height`, drift/band <= `max_range_drift` (trends, sines riding a trend and arcs score 0) |

Every basket member beyond the first costs `complexity_penalty` (2%) of the score.

**Range harvest** (`shapes.band_trades`): a trade opens when the curve leaves the band (below: long, above:
short; for a ratio, buy the numerator or the denominator) and closes at the median (`range_exit: mid`) or the
opposite edge (`range_exit: opposite`). Each trade is credited the edge-to-exit distance (overshoot not
counted). `harvest/yr = trades/yr x per trade`; `range_harvest_scale` (0.15) is the harvest at which that
term reaches 63%. The band is fitted on the same window it trades, so this is an in-sample, before-costs
measure of how tradable the range was, not a backtest.

Two guards keep one-off excursions from passing as ranges:

* **repeat** (`range_segments`, 4): the share of the window's parts in which a trade closed. Swings confined
  to one stretch score low.
* **pain**: the worst move against an open trade beyond its entry edge, in half-bands. A clean oscillation
  overshoots by ~0.2, typical real ranges ~1-2. Beyond 1 the score is multiplied by
  `exp(-(pain - 1) / range_pain_scale)` (2.0): a squeeze that runs far through the band before reverting
  (e.g. 6 half-bands: x0.27) drops out, because nobody could have held the trade through it.

Range report columns: harvest/yr, trades/yr, repeat, per trade, worst against (largest move against an open
trade, from its entry edge), bottom->top and top->bottom (band size as a move
from one edge to the other), **now in band** (last bar: 0% = bottom edge, 100% = top edge; outside 0-100% is
an entry signal today) and drift/band. The chart shades the band, dots the median and extends both through
the holdout.

**Holdout**: the last `holdout_bars` (21, about a month) are never seen by the search, the band or the score.
They are an out-of-sample check only: a trend must stay on the right side of its channel, a range inside its
band padded by 25% ("alive"); "holdout" in the report is the move over those bars.

## Outputs (`runs/<stamp>_<name>_<hash>/`, `runs/LATEST`)

`summary.md`, `results.csv` (one row per ranked basket: members, weights at fit start, drifted weights now,
held duration, metrics, per-window scores; in ratio mode also `den_members`, `den_weights`, `den_weights_now`),
`results.json`, `report.html` (the dashboard's results view in one file: tables + charts with the fitted
line/band and the holdout; Nexus styles and Plotly load from the web), `config.resolved.json`.

## Extending

* **Universe**: drop a file in `universes/` and add its name to `universe.lists` (`mise run universe list`).
  Fetchable lists: `mise run universe refresh sp500` (add a fetcher to `universe.FETCHERS`).
* **Shape**: subclass `shapes.Shape` (`score`, `channel`, `objective`, `direction`) and `@register_shape`.
* **Weight objective**: add a branch in `solver.Solver` (batched over candidate sets).
* **Data source**: return `{ticker: (dates, close)}` and plug it into `data/sources.load_panel`.

## Caveats

This is a **descriptive, in-sample search**: with hundreds of instruments some shapes are coincidence. The
holdout check, the duration ladder and the complexity penalty push against it, but treat results as
candidates for research, not signals. The universe is today's index members (survivorship bias).
Ratio mode searches every combination, so the more ratios a run scans, the more of them are luck: at 3 vs 3
on 19 countries, a few hundred thousand ratios compete. Not supported yet: solved (non-equal) weights in
ratio legs, market-neutral (sum of weights 0) weighted baskets, rebalanced baskets, intraday bars.

`mise run test` / `mise run lint`.
