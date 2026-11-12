# DCA research: can a monthly saver beat plain DCA into the S&P 500 by timing the payments?

Scripts behind the package README's "DCA" section. They import the installed package; data is downloaded once into
`data_cache/dca/` (Yahoo: S&P 500 price and total return, VIX, 10-year and 3-month yields, a high-yield and a
Treasury fund; policyuncertainty.com: the daily newspaper-based policy-uncertainty index; Shiller: dividends and
the long yield before 1988 / 1962; reading Shiller's `.xls` needs `xlrd`).

```bash
python research/dca/forecast.py --h 63   # which signals predict the return over the margin rate, by era
python research/dca/round1.py            # simple policies over every start month
python research/dca/round2.py            # the trend rule: averages, bands, monthly decisions, combinations
python research/dca/robust.py            # horizons, margin spreads, 1928-1961, other markets
python research/dca/why.py               # return above / below the average; the perfect-foresight ceiling
python research/dca/round3.py            # the rate guard and the debt limit, with the 1928-1961 holdout
```

## Setup

$2,000 arrives on the first trading day of each month. Plain DCA invests it at that close. A policy sets a
target each day: +k = k payments held in cash, -k = k payments of margin debt, at most 6 either way; the account
buys down to the target at the close and never sells (so debt is repaid by the next payments). Debt costs the
10-year Treasury yield, cash earns the 3-month bill yield, a new loan must respect the initial margin, a margin
call sells down to 30% equity. Trades at a close use signals from the previous close. A policy is judged over an
account opened on **every** payment day and run for H years: edge = final wealth / plain DCA's - 1.

## What the data says

1. **Stocks beat the loan rate on average, in every era**: the 3-month total return over the 10-year yield was
   +2.9% a year in 1962-89, +5.1% in 1990-2007, +9.9% in 2008-26. So holding a payment back starts with the odds
   against it, and it lost: always a month late beats DCA in 20% of 10-year accounts; waiting for a 5% dip in 41%
   (4% of those running in 1990-2007, none in 2008-26).
2. **Always borrowing is a bet on the decade.** Six payments ahead all the time: 75% of 10-year accounts, median
   +1.8%, worst -4.8%; it lost in more than half of the accounts of 1962-89.
3. **Signals** (`forecast.py`, fifths of each signal, three eras). The same sign in every era: a volatility
   spike, a high VIX, heavy policy news and a rising high-yield market before better returns; a 10-year yield
   that rose over six months before worse ones (top fifth minus bottom fifth: -28, -7 and -13 points a year);
   a bad week before a better fortnight. Drawdown, trend, 12-month momentum, the yield curve and the level of
   yields change sign between eras when read this way.
4. **The turn of the month** is real in all three eras (the last 4 trading days of a month and the first of the next
   returned 34 to 58 basis points together, against about 22 for five average days). Investing 4 days before the month ends: 91% of 10-year
   accounts, but only +0.37%.
5. **The trend rule** (borrow 6 payments while the S&P 500 is above its 200-day average, nothing otherwise):
   97% of 10-year accounts, median +2.6%, worst -0.7%; 90% even in 1962-89. Averages of 150 to 300 days all work
   (86 to 97%); 50 and 100 days do not in 1962-89. Deciding **once a month on payment day** is as good or better
   (100% of 659 accounts, worst -0.07%): the account cannot sell, so leaving a trend late costs nothing but new
   purchases. Borrowing on fear, on drawdowns or below the average: 62 to 75%, worst -4 to -5%.
6. **Why** (`why.py`, 1928-2026, months by the trend state on payment day): above the average the S&P 500 beat
   the 10-year yield by 9.5% a year (t 5.5; positive in each of four eras, t 1.8 to 3.7) at 14% volatility;
   below it by 1.1% (t 0.2) at 25%. The difference between the two states is itself not significant (t 1.7): the
   rule wins because it borrows only where the premium is established, not because below-average months are
   proven bad.
7. **Guards** (`round3.py`). Not borrowing while the 10-year yield is up more than 0.6 points in 126 days lifts
   5-year accounts from 88% to 95% and 10-year median from 2.3% to 2.8% (Reg T accounts); neighbours (0.4 to 0.8
   points, 126 or 252 days) agree; 63 days does nothing. In 1928-1961 yields never moved that fast, so the
   holdout neither confirms nor refutes it. A debt limit of 25% of the position removes every margin call in
   every data set (1929 and the Nasdaq in 2000 included) for about 0.2 points of edge.
8. **Ceiling**: a saver who knew every future price would gain a median 14% over 10 years (8% to 20%). The
   strategy gets about a sixth of that.

## The strategy (`perfectshape.dca.strategy.RECOMMENDED`) against plain DCA

| S&P 500 1962-2026 | start months | beats DCA | median | worst | best |
|---|---|---|---|---|---|
| 5-year accounts | 719 | 94% | +2.24% | -1.31% | +7.09% |
| 10-year | 659 | 99% | +2.63% | -0.11% | +5.10% |
| 20-year | 539 | 100% | +2.63% | +0.79% | +4.24% |
| 30-year | 419 | 100% | +2.59% | +1.07% | +4.10% |
| **1928-1961, held out:** 5-year | 349 | 80% | +3.30% | -6.66% | +7.40% |
| 10-year | 289 | 100% | +2.56% | -0.02% | +6.76% |
| 20-year | 169 | 100% | +2.07% | +1.30% | +5.52% |

No margin calls in any of them. Margin rate above the 10-year yield by 1 / 2 / 3 points: 98% / 97% / 96% of
10-year accounts (median +2.3% / +2.0% / +1.7%), 92% / 89% / 84% of 5-year ones.

Other markets, 10-year accounts, US rates (beats DCA, median): Nasdaq-100 98%, +4.4%; DAX 85%, +2.0%; FTSE 100
67%, +0.7%; Nikkei 64%, +1.0%; Russell 2000 56%, +0.3% (there, always borrowing did better: 90%).

## Borrowing sized against the account (`round4.py`, `round5.py`, `round6.py`)

Exposure = position / equity, at most 2 (Reg T), 5 bps per trade, traded when 2% of equity off target; "pay" rules
never sell (payments repay), "sell" rules sell. Scores per start month: edge over plain DCA, and the account's
deepest time-weighted fall minus plain DCA's (10-year accounts 1962-2026 unless said; every third start month).

* `round4.py`, about 100 rules. Crash ladders: more edge the bigger the ladder (+1% to +10% median) and always a
  deeper fall (3 to 17 points), worst accounts -5% to -28% (to -62% with margin calls for "crash 30% -> borrow
  100%" without selling). Waiting until the index is back above its 200-day average before stepping in fixes
  1962-2026 (96%, fall level with DCA) but not 1928-1961 or the Nasdaq. VIX, volatility-spike, credit and news
  switches: 45 to 75%, deeper falls; from 1990 only, "VIX above 30/40" wins 86 to 89% when it sells, still 5 to 11
  points deeper. Never-selling versions of anything above 1.25 are worse than selling ones: the debt is carried
  into the fall. Always borrowed 2.0: wiped out to -53% against DCA.
* `round5.py`, 120 trend rules (exposure above / below the average x daily, 1% band, monthly x guard x a volatility
  cap). No rule wins 85% and is shallower in 90% of accounts in both 1962-2026 and 1928-1961; the closest are
  1.25 / 0.75 daily (92% / 100% wins, shallower in 95% / 90%) and 1.5 / 0.5 daily + guard (87% / 100%, 92% / 73%).
  Deciding monthly, which helped the six-payment strategy, hurts here (a sold account must also get back in).
* `round6.py`, finalists under stress: see the package README. The rate guard helps 1962-1989 and 20-year
  accounts and costs a little from 1990; a 1% band lowers turnover and the win rate together.

## Caveats

* Start months overlap: 659 ten-year accounts are far fewer independent decades. The eras and the holdout are
  the honest check, and 5-year accounts show the risk: a crash that begins above the average (1929, 1987) hits
  before the rule steps back.
* About 60 policies and variants were run on 1962-2026. The 200-day average is the textbook setting and passed
  the holdout; the rate guard (0.6 points / 126 days was fixed before its grid was run) and the 25% limit were
  chosen after seeing 1962-2026.
* The loan rate is the 10-year Treasury yield, as the study specifies; brokers usually charge more.
* The other markets use price indices (no dividends, except the DAX) and US rates.
* No taxes; interest is not deductible here; payments are not indexed to inflation.
