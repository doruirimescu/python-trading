See README.md. Tooling via mise (`mise.toml`): `mise run install`, `mise run test`, `mise run lint`,
`mise run scan configs/<x>.yaml` (`search.mode: ratio` = basket ratios, ratio.py); ad hoc: `mise exec -- python -m perfectshape ...`.
Dashboard: `mise run dashboard` (src/perfectshape/dashboard/server.py, stdlib HTTP). Front end in src/perfectshape/web/
(dashboard.html/js, trade.html/js = Trade Lab backtester, report.html, report.js = PS.renderReport + info bubbles,
shared with saved reports, shapes.css), Nexus design
system (live nexus.css / nexus.js, see the nexus-style skill): layout-only CSS, colours from tokens only. The server
reads web/ files on every request, so front-end edits need only a browser refresh; Python edits need a restart, which
ends a running scan. Scan hooks: pipeline.ScanControl.
Standalone package: no imports from Trading.*, mrscore or tradelab. Do not commit runs/, data_cache/ or analyses/.
DCA (`src/perfectshape/dca/`, `mise run dca` / `dca-report`, README "DCA"): timing a monthly saver's payments into the
S&P 500 against plain DCA (account.py simulator, policy.py, strategy.py = the rules, exposure.py / rules.py / frontier.py = borrowing sized against the account, scored on
edge and drawdown, report.py + web/dca.html); policies
must keep `tests/test_dca.py::test_policies_use_yesterday_and_nothing_later` passing. Scripts: research/dca/.
Research (not part of the package, needs scikit-learn): research/robust_ranges/ = the forward test of lagged
scans behind scoring.range_robust (study, end-to-end replay, trend replay; README there).
