# tradelab

A generic, leakage-safe backtesting framework: intraday-first, daily-capable, built so that another person or AI agent can add a
strategy in a few lines and get a full, honest report from a single command.

**Agents: read [AGENTS.md](AGENTS.md).** Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), execution rules:
[docs/EXECUTION_MODEL.md](docs/EXECUTION_MODEL.md), metrics: [docs/METRICS.md](docs/METRICS.md), robustness: [docs/ROBUSTNESS.md](docs/ROBUSTNESS.md).

## Install and try

```bash
cd Trading/backtest
make env                                              # uv venv (python 3.13) + editable install with dev extras
.venv/bin/python -m tradelab run experiments/example_daily.yaml       # synthetic data, no network
open runs/LATEST/tearsheet.html   # or read runs/LATEST/summary.md
```

## What you get

- **One contract.** Strategies emit target positions (vector) or orders (event); the engines own all shifting and fills
  (decision at bar close t, fill at open t+1), costs, gaps, intrabar stop/target policy and risk rules.
- **Data layer.** yfinance, csv/parquet with timestamp presets (Databento, FirstRate, IBKR), Databento (cost-checked), seeded synthetic.
  Sessions and DST via `zoneinfo`, continuous futures with roll gaps stripped, data-quality checks.
- **Mandatory leakage test.** Prefix invariance, future poison and an engine delay oracle run on every `run`; a leak exits with code 4.
- **Reports on every run.** Metrics (daily-aggregated, frequency-aware), R-multiples, a self-contained plotly tearsheet with a trade viewer,
  `summary.md` for agents, robustness (PSR/DSR, PBO, block bootstrap, trade Monte Carlo, cost sensitivity, regimes, walk-forward) with an
  advisory traffic-light verdict, and an append-only trial ledger so the deflated Sharpe uses honest trial counts.

## Commands

`run | optimize | walkforward | report | compare | check-causality | validate-data | fetch-data | init-strategy | list-strategies |
list-sources | describe` via `python -m tradelab <command> -h`. Exit codes: 0 ok, 2 config, 3 data, 4 leak.

## Layout

`src/tradelab/` (config, data, features, strategy, engine, analytics, robustness, report, cli) - `strategies/` (your strategies,
auto-discovered) - `experiments/` (YAML configs) - `tests/` (unit, golden, leakage, smoke) - `docs/` - `runs/`, `data_cache/`,
`data_store/` (git-ignored). `make test` runs the suite (leakage tests are parametrised over every registered strategy).

## Caveats

Results on synthetic data demonstrate the machinery, not an edge. A green verdict is advisory, not proof. Never delete
`runs/_trials.jsonl`. Survivorship bias in equity universes is flagged but not corrected.
