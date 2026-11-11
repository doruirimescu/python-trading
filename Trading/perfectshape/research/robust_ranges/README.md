# Robust ranges: what predicts that a scan-window band keeps working after the scan

The question: a lagged scan finds a ratio that ranged beautifully for 10 years, but in the years after the scan
(the Trade Lab's final test) the band breaks. Which in-sample traits tell, before the final test, that the
scan-window band will keep producing mean reversions (at least 2 in the next 1-2 years)?

The answer was turned into `scoring.range_robust` (on by default in ratio mode; see the package README,
"Robust ranges"). These scripts reproduce the study. They are research code: they import the package from
`../../src`, and the analysis scripts need scikit-learn and pandas (not package dependencies).

## Method

* **Universe**: the top 20 holdings (today's weights) of each of the 11 Select Sector SPDRs that have prices
  over the whole span needed (window + 2 forward years), 3 vs 3 ratios (388k ratios per scan at 20 stocks).
  Prices: 22 years of yfinance closes (`harness.load_all`, cached in `cache/`).
* **Scan ends**: every 6 months from January 2015 to July 2024 (20 per sector), so the 2 forward years are
  always available; windows of 10 years (2520 bars) and 5 years (1260 bars).
* **Study** (`harness.py`): per sector and scan end, the package's own ratio search keeps the best 300 ranges
  by the classic score; for each, ~70 in-sample features (only data up to the scan end) and the forward outcome.
* **Forward outcome**: the fixed band of the scored window (p10, the Trade Lab's "scan window" band) traded
  like the Trade Lab final test: start flat at the scan end, enter when the ratio leaves the band, exit at the
  median, next-close fills, 5 bps per side per leg, long/short pair, open trade closed at the end.
  **Success = at least 2 completed reversions in the next 2 years and a positive P&L.**
* **End to end** (`harness_e2e.py`): the real `pipeline.scan` on prices up to the scan end with the dashboard
  defaults (one 10y window, 21-bar holdout, alive check, overlap thinning, top 30), robust ranges off and on,
  and every listed range traded through the next 2 years as above. This is what the dashboard would have
  listed.
* `analyze.py` (univariate AUCs, consistency by year), `analyze2.py` (quintiles, train 2015-2019 vs test
  2020-2024), `analyze3.py` (breakouts, gradient boosting leave-one-year-out), `analyze4.py` (logistic vs
  boosting), `analyze5.py` (threshold rules, chosen on train years, read on test years).

```bash
cd research/robust_ranges
for s in XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY; do
  python harness.py --W 2520 --sectors $s --out parts/w2520_$s.pkl &      # ~25 min on 12 cores
done; wait
python analyze.py 'parts/w2520_*.pkl'; python analyze5.py 'parts/w2520_*.pkl'
for s in ...; do python harness_e2e.py --sectors $s --out parts/e2e2520_$s.pkl & done
```

## Findings (10-year windows, 39,597 ranges passing the 0.6 threshold, 206 scans)

* The classic range score does **not** predict the final test: AUC 0.47-0.50. Only 14.6% of passing ranges made
  at least 2 profitable reversions in the 2 years after the scan; the mean 2-year band P&L was -1.6%.
* What predicts it, consistently in every scan year 2015-2024: how fast and how often the range reverts
  relative to its own noise.

  | feature (passing ranges) | best quintile | worst quintile |
  |---|---|---|
  | half-band / annual volatility (low) | 27% | 5% |
  | completed band trades / yr in the window (high) | 28% | 5% |
  | walk-forward: band fitted on the earlier part, reversions in the next 2y inside the window (high) | 28% | 5% |
  | AR(1) half-life (short) | 26% | 6% |
  | band height (small) | 29% | 5% |
  | recent volatility vs usual (high) | 21% | 8% |

* None of them predicts the **size** of the forward P&L (Spearman ~0): they predict that reversions keep
  happening, and breakouts still happen. A gradient-boosted model on all features reaches AUC 0.745
  leave-one-year-out; a logistic model on a handful 0.69-0.72; per-scan top-10 picks by any of them reach ~28-30%
  success but a slightly negative mean P&L, because some scans have no good range and forcing picks hurts.
  So the filter is an **absolute gate** (list nothing rather than a bad range), not a re-ranking.
* Gates chosen on 2015-2019 scan ends (a grid of thresholds), read on 2020-2024. The package ships the three
  gates trades/yr >= 1.5, band/vol <= 0.45, recent vol >= 1.0 (passing ranges, 10-year windows):

  | | all passing | gated | gated, train (2015-19) | gated, test (2020-24) |
  |---|---|---|---|---|
  | >= 2 profitable reversions in 2y | 14.6% | **41.8%** | 45.8% | 38.9% |
  | mean 2y band P&L | -1.6% | **+5.3%** | +7.8% | +3.4% |
  | median 2y band P&L | +0.7% | +6.2% | | |
  | loss > 20% | 23.7% | 16.4% | | |
  | loss > 60% | 4.9% | **0.6%** | | |
  | scans with at least one | 206 / 206 | 112 / 206 | | |

  Adding leg correlation <= 0.7 (the two baskets' daily returns) gives 43.6% and +6.6% but on 72 scans instead
  of 112, so the package leaves it out. Within the gate nothing ranks further (every feature AUC ~0.5); the 0.6
  score threshold still helps a little (gated ranges scoring 0.5-0.6: 39% vs 43%).
* **5-year windows** (57,848 passing ranges): the gates raise success from 24.4% to 35.4% (train 36.5%, test
  34.5%), but the mean P&L is unchanged (-7.7% vs -7.9%; medians ~0), because of a fat tail: one stock (TSLA,
  2018-2019 scan ends, into 2020) sat in 243 of the 740 gated ratios that lost more than 60%. Without it: -1.7% vs
  -4.2%. The share of the ratio's swings coming from its most influential stock flags this tail (top quintile:
  15% big losses vs 4-5%), which is why the reports show **Top stock**.

## End to end (`harness_e2e.py`, what the dashboard lists)

211 lagged scans (10-year window, dashboard defaults), robust ranges off vs on (the shipped gates inside the
search), every listed range traded with its scan-window band over the 2 years after the scan end:

| per listed range | plain | robust |
|---|---|---|
| at least 2 profitable reversions in 2 years | 18.5% | **33.5%** |
| at least 2 reversions (any P&L) | 19.8% | 39.1% |
| completed reversions (mean) | 0.82 | 1.47 |
| at least 1 profitable reversion in the first year | 32.0% | 46.6% |
| mean / median 2-year band P&L | -1.4% / +0.7% | +0.1% / +2.1% |
| loss over 20% / over 50% | 22.9% / 6.4% | 22.7% / 3.1% |
| listed / scans listing at least one | 1,192 / 201 | 322 / 115 |

By scan end: 2015-2019 36% vs 16%, 2020-2024 32% vs 21%; the only year without a gain is 2023 (19% vs 20%).
By sector the gain is largest in XLK (54% vs 12%, 24 ranges), XLY (45% vs 15%), XLRE (40% vs 12%) and XLB (37% vs
14%); in XLF, XLP and XLV it gains little (32% vs 30%, 36% vs 33%, 19% vs 16%), and XLE, XLI and XLC list almost nothing robust (17 ranges in 60 scans), mostly failures. The ranges the gated search finds
beyond the classic top 300 do as well as those inside it (36.5% vs 31.4%), and the first-ranked robust range is
no better than the others (score does not rank inside the gate). The study's 42% counts every gated candidate,
so a few scans with many similar gated ranges weigh heavily; the dashboard lists ~3 diverse ranges per scan.

## Trends: no robust filter found (`harness_trend.py`, `analyze_trend.py`)

The same replay for uptrends (10-year window, best 200 per scan, 43,623 passing the 0.6 threshold, 220 scans),
outcome: did the ratio keep rising over the next 2 years?

* 58% were still up 2 years later (mean log move +6.1%, median +4.4%), but at a median pace of **18% of the
  fitted slope**: a 10-year straight line mostly flattens out. Only 27% stayed above the fitted lower channel.
* The scan year dominates: 35% to 79% still up depending on the scan end.
* No in-sample feature predicts continuation consistently: the best single one, the correlation of the two
  baskets' daily returns (AUC 0.57), loses its pattern on 2020-2024 scan ends; the trend score is slightly
  negative (0.45); slope, R2, drawdown / move, block slopes, curvature, recent momentum, walk-forward, betas
  are all within 0.45-0.56 with signs that change from year to year. Gradient boosting on everything reaches
  AUC 0.60 leave-one-year-out. Nothing here is solid enough for a default filter, so trends are unchanged;
  read a long, straight relative trend as history, not as a forecast of its pace.

## Follow-up: a listed range that broke (GE DE ETN / PWR UPS DAL)

`example_ge_pwr.py`. XLI, 10-year window to 2025-04, scan end 2025-05 (lag 1.5 years): score 0.615, harvest
+13.9%/yr, a tidy band. It passed every robust gate **only just**: 1.50 trades/yr (>= 1.5), band/vol 0.443
(<= 0.45), recent vol 1.00 (>= 1.0; the last fifth was the median fifth). In the final test the ratio fell 24%
(43% at its low, 5.2 half-bands below the band edge, where 10 years had never gone past 1.1); the band rule
lost 21%.

Why: the legs are fixed shares from 2015. PWR grew 9.4x over the window while UPS and DAL barely moved, so at
the scan end PWR was 80% of the denominator leg and the ratio held was in effect GE/DE/ETN against PWR. PWR then
rose another 79% (the denominator leg +76% against +34%).

What was checked across the study (`concentration.py` adds the features, then `analyze_concentration.py`,
`analyze_margin.py`, `excursions.py`, `stops.py`, `wide_entry.py`):

* **Leg concentration does not predict breaks among gated ranges.** Drifted end weight of the largest member,
  effective member count, growth dispersion inside a leg, top-stock share over the window or its last year:
  AUC 0.43-0.57 for success and for losses beyond 20%, with signs that change from year to year. Before the
  gates there is a mild link (all passing 10-year ranges: largest end weight vs a loss beyond 20%, AUC 0.57,
  same sign in 10 of 11 years), but the gates already take it out: inside them it reverses, and on 5-year
  windows the most concentrated gated legs did *better* (largest end weight in its top fifth: 44% success vs
  30%, both halves). A concentration gate would have dropped this range and nothing else useful.
* **Top stock, definition matters.** The 5-year link to losses beyond 60% (top fifth about 3x the rest: 14.8%
  vs ~5%) holds for the share with the legs at equal weight (`member_share_max`), not for the same share under
  drifted weights (7.7% vs 6.1%); on 10-year windows neither shows it. The report's top stock uses equal weight.
* **Gate margins matter a little.** The quarter of gated ranges with the least room to spare did somewhat worse
  than the quarter with the most (10-year: 42% vs 46%; 5-year: 32% vs 40%). Trades/yr >= 2 and band/vol <= 0.40
  give 48% on 10-year windows (2015-2019 46%, unchanged; 2020-2024 49%) on 64 instead of 112 scans: not
  consistent enough for a new default.
* **The fitted band understates the forward swing: selection.** 89% of the robust ranges the dashboard listed
  went past their own 10-year high or low within 2 years; a ratio that kept behaving as in its window would do
  that about 30% of the time (new extremes in 504 bars after 2520). Median forward excursion beyond the band
  edge: 2.8 half-bands, against 1.2 inside the window. Picking the flattest of ~390,000 ratios selects the ones
  that happened to stay tight. The gates predict that the ratio keeps coming back, not that it stays inside.
* **Stops trade tail for mean.** Trade Lab rules replayed (`stops.py`: scan-window band, exit at the median,
  next-close fills, 5 bps, pair mode, a stopped side blocked until its signal resets):

| set, 2 years after the scan end | rule | >= 2 profitable reversions | mean / median P&L | loss > 20% |
|---|---|---|---|---|
| dashboard-listed robust ranges (322) | no stop | 33.5% | +0.1% / +2.1% | 22.7% |
| | stop 10% | 32.0% | +0.7% / -3.4% | 4.3% |
| | stop past the window's high / low | 30.4% | +0.1% / -3.1% | 5.3% |
| all gated 10-year ranges (880) | no stop | 41.6% | +5.3% / +6.2% | 16.4% |
| | stop 10% | 37.0% | +1.0% / -2.6% | 9.5% |

  A 10% stop removes most large losses. On the listed ranges it costs almost nothing; over all gated ranges it
  costs most of the mean, because many trades that ran 10% against came back. Max days (120 / 250) changed
  little. Entering further outside the band (0.5 to 1.5 half-bands) kept the mean P&L and cut the ranges with
  2 reversions from 48% to 27% / 9% / 3% (all gated 10-year ranges): against the goal of repeated reversions.

The top-stock column was switched to the equal-weight definition that the forward test supports. The gate
defaults then moved to 2.0 trades/yr and band/vol 0.40 on request, to test in the dashboard: in the study 48% vs
42% success at the same mean P&L, gained on 2020-2024 scan ends only, with about half as many scans listing a
range (the main README's end-to-end table has an estimate for what the dashboard lists).

## Episodes: one or two swings after the scan (`episodes.py`, needs `concentration.py` output)

The Trade Lab's "After the scan" backtest, replayed on every range the dashboard listed in the end-to-end run
(1.5 / 0.45 gates): start flat at the scan end with the scan-window band, enter beyond an edge, exit at the
median, at most N trades within H, then stop; pair mode (the range's own edge), 5 bps, next-close fills.

| listed ranges, by where the ratio was at the scan end | N, H | got N swings | mean / median P&L | loss > 20% |
|---|---|---|---|---|
| robust, outside the band (50) | 1, 1 year | 72% | +5.8% / +8.4% | 2% |
| | 2, 1.5 years | 40% | +4.3% / +9.5% | 12% |
| robust, inside the band (199) | 1, 1 year | 59% | +0.8% / +6.3% | 10% |
| not robust, outside the band (223) | 1, 1 year | 39% | -2.0% / +5.0% | 20% |

Outside the band at the scan end is what helps (positive on 2015-2019 and 2020-2024 scan ends alike; only 50
episodes); being just inside an edge (outer 15%) did no better than mid-band. A second swing adds little on
average and doubles the losing tail. In rotation mode (long only) most of the P&L is the market: robust ranges
inside the band earned nearly as much as those outside (+6.7% vs +7.4% over a year).

## Caveats

* Today's sector holdings, so survivorship: stocks that left the index are missing, and a stock that later
  became huge is in every past universe.
* Scan ends 6 months apart share most of their window: the 220 scans are far from 220 independent samples.
  The year-by-year and train/test splits are the honest check.
* The forward test is the band rule without stops unless stated; `stops.py` shows what stops change.
* Regimes matter more than any feature: success of all ranges ranged from 4% (2022 scan ends) to 27% (2020).
