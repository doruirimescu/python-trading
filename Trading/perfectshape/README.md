# perfectshape

Scan a universe of instruments for **weighted baskets whose combined price traces an ideal shape** (a straight
uptrend, a straight downtrend, or a flat oscillating range) and rank them by **how long the shape has held**.
In **ratio mode** the same search runs over **basket ratios** in the style of `Trading/basket`:
`(A + B) / (C + D)` of equal-weight baskets, so it finds one group steadily outperforming another, or
oscillating against it.

Successor of `Trading/utils/range/range.py::PerfectRange` and `Trading/algo/ranker` (single-instrument range
ranking): same idea, generalised to multi-instrument baskets and to trends, vectorised and spread over every
CPU core (Windows and Linux) so the S&P 500 scans in about 20 s on 16 logical cores (about 50 s on one).

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
mise run etf-ratios                           # (A + B) / (C + D) over the same 39 ETFs, ~30 s on 16 cores
mise run dashboard                            # web UI: sector ETF -> 3 vs 3 stock ratios, play / pause, live
mise run dca                                  # DCA timing: what to do with this month's payment (see "DCA")
mise run scan configs/my.yaml                 # any config
xdg-open runs/LATEST/report.html              # or read runs/LATEST/summary.md
```

`mise tasks` lists all tasks (`install`, `scan`, `smoke`, `sp500`, `country-ratios`, `etf-pairs`,
`etf-ratios`, `dashboard`, `dca`, `dca-report`, `universe`, `test`, `lint`).

## Dashboard: sector stock ratios (`mise run dashboard`)

http://127.0.0.1:8765 (opens a browser tab; `python -m perfectshape dashboard --port N` for another port).
Pages use the Investing Nexus design system (live `nexus.css` / `nexus.js`, theme panel bottom right) and Plotly.

* **Configure** on the left: a Select Sector SPDR (XLK, XLE, XLU, ...), how many of its top holdings by
  weight to use (uncheck a stock to exclude it; the next one takes its place), stocks per leg (3 vs 3 by default),
  shapes, lookback windows, the scoring / ranking knobs and the max ratios per window (the size cap) and the holdout length. Every
  setting has an ⓘ bubble explaining it (hover, focus or tap); the texts live in `TIPS` in `web/dashboard.js`. The box under the form shows the number of
  ratios and an estimated runtime; the YAML preview can be saved to `configs/` and run from the CLI later.
* **Robust ranges only** (Scoring, ticked by default): ranges must revert often, with a band narrow against the
  ratio's own volatility and swings that are not fading, the traits that predicted reversions after the scan in
  a forward test of lagged scans (see "Robust ranges" below). Expect fewer ranges, sometimes none; untick it for
  the classic ranking. Its three thresholds show under it.
* **Lookback window (years)** defaults to **10**; type any length (0.5 to 30 years, one window per scan). The
  prices loaded grow with it, and a stock listed for less than the window is left out of the search (the
  robust-range gates were tested on 5- and 10-year windows only). **Lag (years before today)** (`data.lag_years`, default 0) ends
  the scan that many years ago: the search uses the windows ending then and never sees the years after. In the
  Trade Lab those years are the **final test** (below).
* **▶ Play** starts the scan (and clears the previous run's results); the progress bar, current step, elapsed
  time and ETA update every second. The ranking (same tables and charts as `report.html`) shows up after about
  3 seconds and is refreshed every 10 seconds and after every lookback window: windows run longest first and
  both shapes are scored together, so the long-lived shapes that rank highest appear first, in both tabs.
* **❚❚ Pause** holds the scan between chunks of work (within a second) without losing anything; **▶ Resume**
  continues it. **■ Stop** abandons it (partial results stay on the page, nothing is written).
* When it finishes the run is written to `runs/` like a CLI run, with links to its report, CSV and summary.
  Reopening the page while a scan runs or after it finished restores its config and results.
* **Results with many tickers** show as `#rank ⓘ` plus the tickers, cut with "…" when long; hover or tap the
  ⓘ for every member with its company name (tables keep ticker chips up to 4 tickers per ratio).
* **Click a result** (table row or chart card) to open it in the **Trade Lab** (below), in a new window.
* **Refreshing never stops a scan**: it runs in the server's background thread, and the page only follows it.
  The front end (`src/perfectshape/web/`: `dashboard.html`, `dashboard.js`, `report.js`, `shapes.css`) is read
  from disk on every request, so a style or layout edit shows up on the next refresh while the scan keeps
  running. Only edits to Python code need a server restart (Ctrl+C, `mise run dashboard`), and that does end a
  running scan.

Size: all ratios are enumerated, so the count grows fast with the holdings used and the basket size (table in
"Ratio mode" below: 20 stocks = 388 k ratios at 3 vs 3, 4.4 M at 4 vs 4, 23 M at 5 vs 5); `ratio.max_ratios`
(25 M) caps a run. Pick the holdings that matter rather than the whole fund.

### Trade Lab (`/trade.html`, `web/trade.js`)

Backtests buying and selling one ratio, in the browser: prices of its members and SPY come from the dashboard
server (`/api/series`, the scan's price cache), and every change of a rule recomputes at once.

* **Backtest** (first control): **Whole history** runs the rules over From -> To, the way the range was found
  (in-sample with the scan-window band). **After the scan: the next swings** (a scan run with a lag) runs only
  what you would have traded after it: one episode that starts flat on the scan's last day, trades the ratio the
  scan scored (equal weight at its window start, fixed shares since) with the same rules, takes at most **Max
  trades** (default 1) within the **Horizon** (default 1 year; an open trade is closed there), then stops. **Enter**
  "only if outside the band at the scan end" (default) trades only a ratio that is ready to swing that day, else
  the episode has no trade; "at any band edge" waits for the edge. A stop loss, or the optional **range-break
  stop** (the ratio passes the scored window's high / low on its losing side, drawn as dashed lines), ends the
  episode. The ratio chart still shows the window the range came from; statistics, equity and drawdown cover
  the episode only. In the replay of lagged sector scans (`research/robust_ranges/`), robust ranges outside the
  band at the scan end completed 1 swing within a year 72% of the time (mean +5.8% in pair mode) against 59%
  (+0.8%) for those inside it; one episode is still one or two trades, an example rather than a probability.

* **Strategies**: band mean reversion (the scan's in-sample band; a rolling band of the last N days; or an
  expanding band of every day since From, available after N days of warm-up; the last two use past data only;
  band percentile, entry beyond the edge in %, exit at a share of the band: 50% = median, 100% = opposite
  edge), z-score mean reversion (lookback, entry / exit / stop z), trend (moving-average crossover with a
  buffer), buy & hold the ratio. Directions: both, numerator up only, denominator up only.
* **Execution**: rotation (default: all money in the basket expected to outperform, long only, cash when
  flat), long/short pair (with exposure per leg), numerator only; starting capital (default $10,000), costs in bps per side per leg,
  fill at the next close (default, no look-ahead) or the same close. **Risk exits**: stop loss, take profit,
  maximum holding days (a stopped-out side is not re-entered until its signal resets). No position is opened on
  the last bar of the period; whatever is open is closed at the last in-period close ("end of period").
* **Report**: the ratio with its band / averages and every entry and exit; portfolio value against SPY and
  all members equal weight; drawdown; statistics (final value, total return, CAGR, volatility, Sharpe,
  Sortino, max drawdown, Calmar, trades, win rate, average / best / worst trade, profit factor, holding days,
  time in the market, beta and correlation to SPY); the trade list (copy as CSV); calendar-year returns.
* **Final test** (results of a lagged scan): the years after the scan's last bar are kept out of the backtest
  (To stops at the scan end) and out of the optimizer (train and test both stay before it), so nothing is tuned
  on them. Tick **Include the final test** to bring them back: the charts extend to today with the final period
  shaded, and the statistics get **Final test** and **SPY · final test** columns (the same rules as their own
  run from the scan end, fresh capital) plus a KPI tile. Saved analyses keep the scan end and the tick.
* **Swing meter** on the ratio chart: click a point, then a second one, for the % move of the ratio between
  them, the trading days, each basket's own move and what a long-numerator / short-denominator pair made over
  that stretch (a dotted line on the chart; hover previews after the first click; a third click starts again).
  It works on a zoomed chart: the zoom stays through meter clicks and rule changes (it resets when the period
  changes; double-click the chart to zoom out). **⛶ Full screen** gives the ratio chart, with its swing meter,
  the whole screen (or the whole window if the browser refuses); Esc or the button leaves it.
* Baskets are equal weight at the start date, held as fixed shares (as the scan values them). Shorts assume
  free borrow; no interest on cash. With the scan's band the backtest is in-sample inside the band's window.
* Every setting can also be put in the URL (`&strategy=zscore&z_in=2.5&mode=rotation`), so a backtest can
  be bookmarked or shared. The "all members, equal weight" line (holding every stock of the ratio) is off by
  default; tick it in the portfolio chart's legend.
* **Find best rules** (the optimizer, in the page and as a button above the strategy):
  * realistic conditions only: rolling and expanding bands (past data only; band rules are searched with both,
    listed as "band" and "band (expanding)"), fills at the next close; your position mode,
    exposure, capital, costs and directions are kept;
  * the period is split into **train** (first 70% by default) and **test** (the rest, never used to choose);
    by default a rule's train score is its **weakest of 3 consecutive train segments**, so it has to work
    throughout, not in one lucky stretch; rules with fewer than the minimum trades are ignored;
  * objective: Sharpe (default), CAGR, Calmar or total return; one strategy or every strategy;
  * **Change only within the current band** (tick, off by default): keeps the band picked in "Band from"
    (scan window, rolling or expanding) and tunes only its settings; unticked, band rules are searched with both
    past-only bands. With the scan-window band the search is in-sample (that band was drawn with the prices it
    is judged on, test included), so treat its results as an upper bound;
  * search: Latin-hypercube sampling of the settings (40% of the budget), then a (mu + 1) evolution around the
    best rules with shrinking steps (lookbacks on a log scale). A backtest takes well under a millisecond, so
    the default 2,000 run in about a second. The search is randomised: a second run can surface different
    rules of similar quality;
  * the leaderboard's first train column is the **score** the ranking uses (with "weakest of 3 segments", the
    objective on the weakest third of train); the return, CAGR, drawdown and trades after it are for the whole
    train period. After **Apply**, the charts mark the train | test boundary and the statistics table adds
    **Train** and **Test** columns, separate backtests that match the leaderboard; the whole-period column is
    one continuous run (money compounds through both parts, trades carry across), so it is not train + test;
  * the leaderboard shows train and test side by side (rules that trade identically are shown once, and each
    strategy's best is always listed) plus your current rules under the same conditions; **Apply** loads a
    rule set and backtests it over the whole period. A rule that is good in train and poor in test is
    overfitted, and a ratio whose best rules all fail in test has probably changed regime.

**Saved analyses**: in the Trade Lab, **💾 Save analysis** stores the ratio, every setting (including the
optimizer's train | test boundary) and a snapshot of the results, with a name and notes, as
`analyses/<date>_<name>.json` (git-ignored). The dashboard lists them under **Saved analyses** (Open reloads the
Trade Lab with every setting, Delete asks for a confirming click). A reopened analysis shows its name, notes and
the results when saved next to today's (prices are refreshed); Save then updates it, Save as new copies it, and
the page address reopens it.

**Holdings** (`holdings.py`): `universe.lists: ["etf:XLK"]` with `universe.limit: 20` works in any config.
They come from State Street's daily holdings file of the fund (every constituent with its weight), cached per
day in `data_cache/holdings/`. Cash, money-market and the index futures the funds hold are dropped, and so is a
second share class of the same company (GOOG next to GOOGL). Inside the
directory (with mise activated in your shell) `python -m perfectshape ...` and `perfectshape ...` use the venv
directly; elsewhere, prefix with `mise exec --`.

## How it works

1. **Universe -> panel.** Lists in `universes/` (csv/txt/json/yaml) are merged; closes come from yfinance
   (auto-adjusted), cached per ticker in `data_cache/yfinance/*.npz` (re-downloaded after `max_age_days`;
   a fixed past `data.end` is never re-downloaded). Union calendar, short holes forward-filled. A ticker the
   bulk download returns nothing for (yfinance drops some when it throttles) is retried once on its own and
   never cached empty, so the next scan asks again. The report and dashboard name the stocks a scan could not
   use: no prices at all, or listed for less than the window (in no basket of it).
2. **Fit end.** The last `holdout_bars` (default 21) are never used by the search.
3. **Search, per shape and per lookback window** (`windows`, e.g. 3 months ... 10 years):
   * every instrument is scored on its own (one vectorised pass);
   * from each of the best `seeds` singles, a basket grows greedily: every other instrument is tried as the
     next member, weights are re-solved for all candidates in one batched solve, the best-scoring addition
     is kept, until `max_assets` or the gain < `min_improvement`. The seeds grow on a thread pool
     (`search.workers`, 0 = every logical core), recorded in seed order: the same baskets on any number of
     threads.
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
  members and a ratio is `basket(num) / basket(den)`, with `ratio.k` members on each side (symmetric: 3 vs 3,
  4 vs 4, ...; older configs with equal `k_num` / `k_den` still load);
* **every** ratio is enumerated (disjoint legs unless `allow_overlap`) and scored in vectorised chunks, without
  materialising all ratios at once; the best `keep_per_window` per window go on to the duration ladder and the
  holdout check, held as fixed shares in both legs;
* a falling A/B is a rising B/A, so trends are **oriented** (flipped when their fitted slope is negative) and
  every trend is reported as "numerator outperforms denominator". Ratio mode therefore offers `uptrend` and `range` (the
  default); `downtrend` is rejected. A ratio range is a basket-rotation (mean-reversion) candidate.
* Size: `C(n, k) * C(n - k, k) / 2` ratios per window. 19 country ETFs: 11,628 at 2 vs 2, 271,320 at 3 vs 3.
  The 39-ETF mix (`universes/etf_mix.txt`): 741 at 1 vs 1 (`etf_pairs.yaml`), 246,753 at 2 vs 2
  (`etf_ratios.yaml`). Sector stocks, with rough run times for 2 shapes on all 11 windows:

  | stocks | 3 vs 3 | 4 vs 4 | 5 vs 5 |
  |---|---|---|---|
  | 16 | 80,080 (~30 s) | 450,450 (~2.5 min) | 1.0 M (~5 min) |
  | 20 | 387,600 (~2 min) | 4.4 M (~25 min) | 23 M (~2 h) |
  | 25 | 1.8 M (~10 min) | 38 M (~3.5 h) | 412 M |
  | 30 | 5.9 M (~30 min) | 205 M | 3.8 B |

  A run larger than `ratio.max_ratios` (25 M) stops with an error before scanning.
* **Speed** (`ratio.py`, `Shape.score_y(full=False)`): in log space each basket's log curve is computed once
  per window, so a ratio is one subtraction (log A − log B); trends are scored in one orientation; the trend
  fit uses sums of squares instead of a residual matrix and the range drift is a closed-form quadratic; and
  scoring is **pruned exactly**: the cheap parts give an upper bound on the score (sqrt(R²) for trends,
  sqrt(flatness) for ranges), and the drawdown / trade simulation only runs for ratios that pass the gates
  and can still beat the weakest of the best `keep_per_window` so far. All shapes are scored from the same
  chunk of ratios, and windows run longest first (strong candidates early raise the bar for the rest). Same
  rankings, about 6× faster than scoring every ratio in full (XLU top 16, 3 vs 3: 143 s → 24 s).
* **Cores** (`parallel.py`, `search.workers`, default 0 = every logical core): chunks of ratios are scored
  on a thread pool and merged in order, so the rankings are the same on any number of threads. Threads, not
  processes: the scoring is numpy on large arrays, which releases the GIL, and threads share the panel
  without spawning (slow on Windows) or copying. BLAS is pinned to one thread per worker
  (`OPENBLAS_NUM_THREADS` etc., set on import unless already set) so the pools do not multiply. Scoring is
  memory bound: `configs/etf_ratios.yaml` takes 79 s on one thread and 30 s on 16 logical cores, about the
  same speedup as 16 separate processes get on that machine.
* `complexity_penalty` counts all members of both legs. Every ratio in a run has the same size, so it only
  shifts the threshold; `configs/country_ratios.yaml` sets it to 0 and lowers `min_annual_return` to 5%
  because relative moves are smaller than outright ones.

```yaml
search: {mode: ratio, shapes: [uptrend, range]}
ratio: {k: 3, allow_overlap: false, keep_per_window: 300, max_ratios: 25000000}
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

**Speed to the mean** (optional, `range_speed_days`, dashboard "Target days to mean", 0 = off): every range gets
**to mean**, the average trading days a band trade takes from leaving the band to its exit. With a target of D
days, ranges within it keep their score and slower ones get `min(1, D / days)` inside the square root (twice as
slow keeps 71%), so faster-reverting ranges rank higher without the others being wiped out.

### Robust ranges (`scoring.range_robust`, on by default in ratio mode)

A range that scores well over 10 years often stops working right after the scan: in the Trade Lab's final test
the band breaks. To find out what tells the ranges that keep working apart, lagged scans were replayed for every
sector SPDR (top 20 holdings, 3 vs 3, scan ends every 6 months from 2015 to mid-2024) and every range was traded
with its fixed scan-window band over the next 2 years, like the final test (study, scripts and full numbers:
`research/robust_ranges/`). Findings:

* The classic score does not predict the final test (AUC ~0.5): only ~15% of the ranges it passes made at least
  2 profitable reversions in the 2 years after the scan.
* What does, in every scan year: how often and how fast the range reverts **relative to its own noise**, and
  whether its swings are still alive at the scan end. These traits do not predict the size of the P&L; they
  predict that reversions keep coming.

So with `range_robust` a range scores 0 (it is neither kept by the search nor listed) unless its window has:

| gate | setting (dashboard) | default | why |
|---|---|---|---|
| completed band trades per year | `range_min_trades_per_year` (Min trades / yr) | 2.0 | ~4 expected in a 2-year final test; the strongest single predictor |
| half-band / annual volatility of the ratio's daily changes (**band/vol**) | `range_max_band_vol` (Max band / vol) | 0.40 | ordinary noise keeps carrying the ratio to the edges; ~ a mean-reversion half-life under 35 days. A band crossed only by a few big, slow swings rarely repeats |
| volatility of the window's last fifth / its median fifth (**recent vol**) | `range_min_recent_vol` (Min recent vol) | 1.0 | below 1 the swings are fading and the band stops being reached |

The thresholds were first chosen at 1.5 trades/yr and band/vol 0.45 on 2015-2019 scan ends; the stricter
2.0 / 0.40 became the default after a range that passed the looser gates only just broke in its final test
(`research/robust_ranges/README.md`, "Follow-up"). The cheap gates run before the band-trade simulation, so the
search also gets a little faster. Results of the real scan pipeline with the dashboard settings (10y window,
21-bar holdout, top 30, overlap thinning), robust off vs on, 211 lagged scans, every listed range traded over
the 2 years after its scan end:

| per listed range | plain | robust 1.5 / 0.45 | robust 2.0 / 0.40 (default) |
|---|---|---|---|
| at least 2 profitable reversions in 2 years | 18.5% | 33.5% | **40%** |
| at least 2 reversions (any P&L) | 19.8% | 39.1% | **48%** |
| completed reversions (mean) | 0.82 | 1.47 | **1.67** |
| at least 1 profitable reversion in the first year | 32% | 47% | 43% |
| mean / median 2-year band P&L | -1.4% / +0.7% | +0.1% / +2.1% | +0.4% / +2.0% |
| loss over 50% | 6.4% | 3.1% | 7% (3 of 42) |
| ranges listed | 5.9 per scan | 2.8 per listing scan, 115 of 211 scans list one | 1.1 per listing scan, **39 of 211 scans list one** |

The last column is an estimate: the 1.5 / 0.45 listings that also pass 2.0 / 0.40 (a real rerun could list a
few more, where a removed range had crowded out an overlapping one), and with 42 ranges its percentages are
rough. The looser gates hold in both halves (scan ends 2015-2019: 36% vs 16%; 2020-2024: 32% vs 21%; study,
scan-weighted: 40.7% vs 13.9% and 40.6% vs 18.1%). The stricter ones add little on 2015-2019 and more on
2020-2024 (study, all gated 10-year ranges: 46% vs 46% and 49% vs 39%; listed: 35% and 45%), with the same mean
P&L (+5.3% in the study) and far fewer listings (study: 64 of 206 scans instead of 112). Ranges that pass the
gates only just (e.g. 1.50 trades/yr, band/vol 0.44, recent vol 1.00 under the looser gates) did somewhat worse
than the quarter with the most room to spare (10-year windows: 42% vs 46%; 5-year windows: 32% vs 40%). To go
back, set Min trades / yr 1.5 and Max band / vol 0.45.

What it does not do: it does not keep the ratio **inside** the band. The scanner picks the flattest of hundreds
of thousands of ratios, so the scan-window band understates how far the ratio will swing: 89% of the robust
ranges it listed went past their own 10-year high or low within 2 years (a ratio that kept behaving as in the
window would do so about 30% of the time), with a median excursion of 2.8 half-bands beyond the band edge
against 1.2 inside the window. The gates predict that it keeps **coming back**, not that it stays put. It does
not stop a single stock from blowing a range up (a ratio whose swings come mostly from one stock is a bet on
that stock: watch **top stock**, red above 45%; on 5-year windows its top fifth had about three times the
losses beyond 60%; on 10-year windows it showed no link), and it does not make the P&L large: the band rule has
no stop. A **10% stop loss** in the Trade Lab (replayed in pair mode) cut the listed robust ranges with a 2-year loss beyond 20% from 23%
to 4% at the same mean P&L and almost the same success rate (32% vs 34%), but over all gated 10-year ranges in
the study it also cut the mean from +5.3% to +1.0% (trades that ran 10% against often came back): a choice of
risk, not a free improvement. A stop at the window's own high / low did no better than 10%, and entering further
outside the band kept the mean P&L while halving the ranges with 2 reversions. How concentrated a leg has become
under its fixed shares (the members' **now** weights; e.g. one stock at 80% of a leg) did not predict breaks
among the gated ranges either. It usually lists **no range at all** for a sector (about 4 scans in 5 at the defaults), which is the
point: untick it to see the classic ranking. On 5-year windows it raises the success rate as well (24% to 35%) but not the mean P&L (TSLA's 2020 run sat in a
third of the big losers). The study's universe is today's holdings (survivorship). The gates were validated on
basket ratios only, so weighted baskets keep the classic score unless `range_robust: true` is set.
The same replay for **uptrends** found no robust filter: 58% of listed 10-year trends were still up 2 years
later, at a median pace of only 18% of their fitted slope, and no in-sample trait predicted which ones
(`research/robust_ranges/README.md`).

Range report columns: harvest/yr, trades/yr, **band/vol** and **recent vol** (the robust-range measures, above),
to mean, repeat, per trade, worst against (largest move against an open trade, from its entry edge), bottom->top
and top->bottom (band size as a move from one edge to the other), **top stock** (ratio mode: the share of the
ratio's daily swings coming from its most influential stock with the legs at equal weight, and which one; red
above 45%), **now in band**
(last bar: 0% = bottom edge, 100% = top edge; outside 0-100% is an entry signal today) and drift/band. The
chart shades the band, dots the median and extends both through the holdout. Trends in ratio mode also show
top stock.

**Holdout**: the last `holdout_bars` (21, about a month) are never seen by the search, the band or the score.
They are an out-of-sample check only: a trend must stay on the right side of its channel, a range inside its
band padded by 25% ("alive"); "holdout" in the report is the move over those bars.

## Outputs (`runs/<stamp>_<name>_<hash>/`, `runs/LATEST`)

`runs/LATEST` is a symlink to the newest run, or a copy of it where symlinks need extra rights (Windows
without Developer Mode).

`summary.md`, `results.csv` (one row per ranked basket: members, weights at fit start, drifted weights now,
held duration, metrics, per-window scores; in ratio mode also `den_members`, `den_weights`, `den_weights_now`),
`results.json`, `report.html` (the dashboard's results view in one file: tables + charts with the fitted
line/band and the holdout; Nexus styles and Plotly load from the web), `config.resolved.json`.

## DCA: beating monthly dollar-cost averaging into the S&P 500 (`perfectshape.dca`)

A saver gets $2,000 a month for the S&P 500. Plain DCA invests it the day it arrives. May the saver do better by
choosing **when** each payment goes in: holding up to six payments back, or borrowing up to six on margin (at the
10-year Treasury yield, within margin rules) and repaying them with the payments to come?

```bash
mise run dca            # what to do with this month's payment
mise run dca-report     # the study: runs/<stamp>_dca/report.html, summary.md, dca.json (about 3 minutes)
```

**The rule the research arrived at** (`dca/strategy.py`):

1. On payment day, look at yesterday's close. If the **S&P 500 is above its 200-day average** and the **10-year
   yield has not risen more than 0.6 points in the last 126 trading days**: borrow until you are **6 payments
   ahead**, and invest it. Debt never above 25% of the account.
2. Otherwise borrow nothing new: payments repay the debt first, then buy as usual.
3. Never sell; never hold a payment back in cash.

**Against plain DCA**, an account opened on every payment day and run for H years (edge = final wealth over plain
DCA's - 1; trades use the previous close; `tests/test_dca.py` checks that no policy sees the future):

| | start months | beats DCA | median edge | worst | best |
|---|---|---|---|---|---|
| 5-year accounts, 1962-2026 | 719 | 94% | +2.24% | -1.31% | +7.09% |
| 10-year | 659 | 99% | +2.63% ($12,000) | -0.11% | +5.10% |
| 20-year | 539 | 100% | +2.63% ($43,000) | +0.79% | +4.24% |
| 30-year | 419 | 100% | +2.59% ($142,000) | +1.07% | +4.10% |
| 10-year, **1928-1961 (held out)** | 289 | 100% | +2.56% | -0.02% | +6.76% |
| 5-year, 1928-1961 | 349 | 80% | +3.30% | -6.66% | +7.40% |

No margin call in any account. What else was tried (10-year accounts): holding every payment a month 20%, waiting
for a 5% dip 41%, always 6 payments ahead 76% (worst -4.9%), investing 4 days before the month ends 92% (+0.4%),
borrowing on fear or after a 10% drawdown 62 to 75%.

**Why it works**: over 1928-2026, in months that began above the average the S&P 500 beat the 10-year yield by
9.5% a year (t 5.5, positive in every era) at 14% volatility; in months that began below it, by 1.1% (t 0.2) at
25%. Borrowing pays where that premium is established and is switched off where it is not.

**How much to believe**:

* The prize is small by construction: six payments are a sliver of a grown account. Perfect foresight would add
  about 14% over ten years; the rule adds 2 to 3%.
* It is leverage, timed. A crash that starts above the average (1929, 1987) hits before the rule steps back, and
  a young account feels it most: hence 5-year accounts at 94% (80% in 1928-1961).
* Brokers usually charge more than the 10-year yield: at 1 / 2 / 3 points more, 98% / 97% / 96% of 10-year
  accounts still win (median +2.3% / +2.0% / +1.7%).
* Not a law of nature: Nasdaq-100 98% and DAX 85%, but FTSE 100 67%, Nikkei 64%, Russell 2000 56%.
* The 200-day average is the textbook setting and passed the holdout; the rate guard and the debt limit were
  chosen after seeing 1962-2026 (yields barely moved in 1928-1961, so the holdout does not test the guard).

### Borrowing sized against the account (`dca/exposure.py`, `dca/rules.py`, `dca/frontier.py`)

A second question: what if the saver may borrow more than six payments ("the market is down 10%: borrow 10% of the
account"), react to the VIX, volatility or news, and sell to repay? A rule sets the account's **exposure** (position
/ equity: 1 = plain DCA, 1.5 = borrowed half the equity, 0.5 = half in cash; Reg T caps it at 2). Each rule is
scored twice over every start month: its edge over plain DCA, and its deepest fall against plain DCA's over the
same years (time-weighted, so a payment does not hide a loss). 10-year accounts, 1962-2026, 5 bps per trade:

| rule | beats DCA | median edge | worst | fall vs DCA (median, points) | shallower in |
|---|---|---|---|---|---|
| Crash 10% -> borrow 10% of the account | 69% | +1.2% | -5.5% | 2.6 deeper | 0% |
| Crash 10 / 20 / 30% -> borrow 20 / 40 / 60% | 77% | +5.9% | -22.1% | 9.6 deeper | 0% |
| VIX above 30 -> borrow 25% | 59% | +1.0% | -10.5% | 2.8 deeper | 0% |
| Policy news 2x usual -> borrow 50% | 48% | 0.0% | -23.6% | 0.5 deeper | 0% |
| Always borrowed 50% | 64% | +6.4% | -29.3% | 17.1 deeper | 0% |
| Trend 1.25 / 0.75 (borrow 25% above the 200-day average, 25% cash below) | 92% | +5.0% | -3.1% | 4.8 shallower | 95% |
| **Trend 1.5 / 0.5 + rate guard** (`EXPOSURE_RECOMMENDED`) | 87% | +12.3% | -9.1% | **11.6 shallower** | 92% |
| Trend 2.0 / 0.5 + rate guard | 88% | +24.5% | -9.9% | 7.3 shallower | 85% |

* **Buying the crash on margin never reduced the drawdown**: every crash, VIX, volatility-spike and news rule fell
  deeper than plain DCA in every account, and the big ladders lost 20% and more against DCA when the fall went on.
* **The only family that beats DCA and falls less** borrows while the index is above its 200-day average and holds
  part of the account in cash below it. Cash alone (1.0 / 0.5) falls far less but loses to DCA; borrowing alone
  beats DCA but falls further; together the borrowing pays for the cash.
* The recommended 1.5 / 0.5: 20-year accounts 98%, median +35%, shallower in all of them; 1928-1961 (held out) 100%,
  +19%, but the fall is only about level with DCA's there (shallower in 73%, up to 9 points deeper). 2.0 / 0.5 earns
  about twice as much and fell *deeper* than DCA in the holdout, so it is not the pick.
* **Fragile where the first strategy is not**: it sells and trades often (the index crosses its average many times),
  so at 0.2% a trade it wins 68% with +5%; 5-year accounts win 76% (worst -12%); Nasdaq-100 67%, Nikkei 64%, DAX
  53%, FTSE 100 31% (median -8%), Russell 2000 15% (median -16%). Taxes on the sales are not modelled.

### Combined strategy: a continuous borrowing function, never sells (`dca/continuous.py`)

Instead of on/off rules, one function sets the exposure every day from the VIX, the margin rate (10-year yield), the
Fed's rate (3-month bill) and the trend: Merton's rule with separate borrowing and lending rates,
`exposure = k x (expected return - rate) / (VIX/100)^2`, borrowing when it exceeds 1 against the margin rate and
holding payments when it falls below 1 against the bill rate. The account never sells: debt (capped in payments) is
repaid by the payments. Page: `rules/combined-strategy.html` of a DCA run (`python research/dca/combined_page.py <run>`
after `python research/dca/kelly_cv.py`).

* **Fitting the whole function overfits.** Seven parameters optimised on 1962-1999 won 100% of its accounts there,
  62% on 2000-2026 and 32% on 1928-1961; estimating the forecast's slopes by regression did worse (7% on 2000-2026):
  the fine slopes change sign between eras (`research/dca/fit_continuous.py`).
* **What survives** feeds the function only the coarse facts that held in every era (the premium above vs below the
  200-day average, a penalty for a rising 10-year yield) and chooses k and the caps on the accounts. Tested leave one
  era out (fit on two eras, score the third): 82% / 60% / 100% of 10-year accounts (1928-61 / 1962-99 / 2000-26),
  median +6.8% / +2.0% / +0.6%, about 1 point deeper falls than plain DCA. The simple trend rules under the same caps
  won more (94% / 72% / 96%) but fell 3 to 6 points deeper (`research/dca/kelly_cv.py`).
* Fitted on all eras: premium +9.2% above / +1.1% below, rate penalty 0.087 per point, k = 0.15, debt at most 12
  payments, no cash. It borrows only above the average with the VIX under about 12: the gentlest borrower here.

Modules: `dca/data.py` (market history), `account.py` (the account: interest, margin, many start dates at once,
and the perfect-foresight bound), `signals.py`, `policy.py`, `evaluate.py`, `strategy.py`, `report.py` +
`web/dca.html`. Every number above and the signals that did not make it (VIX, policy news, credit, turn of the
month): `research/dca/README.md`.

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
