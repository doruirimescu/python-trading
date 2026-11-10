See README.md. Tooling via mise (`mise.toml`): `mise run install`, `mise run test`, `mise run lint`,
`mise run scan configs/<x>.yaml` (`search.mode: ratio` = basket ratios, ratio.py); ad hoc: `mise exec -- python -m perfectshape ...`.
Dashboard: `mise run dashboard` (src/perfectshape/dashboard/server.py, stdlib HTTP). Front end in src/perfectshape/web/
(dashboard.html/js, trade.html/js = Trade Lab backtester, report.html, report.js = PS.renderReport + info bubbles,
shared with saved reports, shapes.css), Nexus design
system (live nexus.css / nexus.js, see the nexus-style skill): layout-only CSS, colours from tokens only. The server
reads web/ files on every request, so front-end edits need only a browser refresh; Python edits need a restart, which
ends a running scan. Scan hooks: pipeline.ScanControl.
Standalone package: no imports from Trading.*, mrscore or tradelab. Do not commit runs/, data_cache/ or analyses/.
