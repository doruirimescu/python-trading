# Loan Tools

## 1. Loan Analysis (web)

Upload your `loan.json` to the **[Loan Analysis](https://doruirimescu.github.io/loan_analysis.html)** page on Investing Nexus to get a full dashboard: principal paid/remaining, interest and cost breakdown, monthly bar charts, and a cumulative repayment line chart.

The JSON format is described [here](./json_format.md).

### Running locally

**Terminal 1 — backend** (from the repo root `Trading/`):
```bash
pip install -r render/requirements.txt   # first time only
uvicorn render.main:app --reload --port 8000
```

**Terminal 2 — frontend** (from the `docs/` directory):
```bash
cd ../docs
python -m http.server 8080
```

Then open **http://localhost:8080** in your browser.

The frontend auto-detects the environment: when served from `localhost` it talks to `http://localhost:8000`; on GitHub Pages it talks to the Render-hosted backend.

## 2. Loan vs Investment Simulator (web)

Should you repay your loan faster or invest your spare cash?

Use the **[Loan vs Investment Simulator](https://doruirimescu.github.io/loan_simulation.html)** page to find the optimal percentage of your salary to allocate toward loan repayment vs investing, given your interest rate, investment return, and time horizon.
