#!/usr/bin/env bash
# Basket Rotation pages of Investing Nexus: export runs, preview locally, publish.
#
# The pages live in the stock-market-data repo (docs/basket/, served by GitHub
# Pages); this repo produces the run data for them.
#
#   ./web.sh export    run config.yaml and write a new run into the site
#   ./web.sh trend     run config_trend.yaml and refresh the Sector Trend research page
#   ./web.sh start     serve the site locally (background) and open the basket pages
#   ./web.sh stop      stop the local server
#   ./web.sh status    show whether it is running
#   ./web.sh restart   stop + start
#   ./web.sh publish   commit docs/basket/ in the site repo and push it to GitHub Pages
#
# Env: BASKET_SITE_REPO (default ~/personal/stock-market-data), PORT (default 8765),
#      NO_BROWSER=1 to skip opening a browser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_REPO="${BASKET_SITE_REPO:-$HOME/personal/stock-market-data}"
BASKET_DIR="$SITE_REPO/docs/basket"
PORT="${PORT:-8765}"
PIDFILE="$ROOT/.web-server.pid"
LOGFILE="$ROOT/.web-server.log"
URL="http://127.0.0.1:$PORT/basket/index.html"

running() { [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

need_site() {
  [[ -d "$BASKET_DIR" ]] || { echo "Site folder not found: $BASKET_DIR (set BASKET_SITE_REPO)"; exit 1; }
}

export_run() {
  need_site
  (cd "$ROOT" && PYTHONPATH=src python3 -m mrscore.cli.export_web --out "$BASKET_DIR/data")
}

export_trend() {
  need_site
  (cd "$ROOT" && PYTHONPATH=src python3 -m mrscore.cli.export_trend --out "$BASKET_DIR/data")
}

start() {
  need_site
  if running; then echo "Already running (pid $(cat "$PIDFILE")): $URL"; return; fi
  [[ -f "$BASKET_DIR/data/manifest.js" ]] || { echo "No runs published yet; exporting one first…"; export_run; }
  DOCS="$SITE_REPO/docs" PORT="$PORT" nohup python3 - >"$LOGFILE" 2>&1 <<'PY' &
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # new runs show up on reload
        super().end_headers()

ThreadingHTTPServer(("127.0.0.1", int(os.environ["PORT"])), partial(Handler, directory=os.environ["DOCS"])).serve_forever()
PY
  echo $! >"$PIDFILE"
  for _ in $(seq 50); do
    if curl -sf -o /dev/null "$URL"; then break; fi
    if ! running; then echo "Server failed to start:"; cat "$LOGFILE"; rm -f "$PIDFILE"; exit 1; fi
    sleep 0.1
  done
  echo "Basket Rotation running (pid $(cat "$PIDFILE")): $URL"
  if [[ -z "${NO_BROWSER:-}" ]] && command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1 || true; fi
}

stop() {
  if running; then kill "$(cat "$PIDFILE")" && echo "Stopped (pid $(cat "$PIDFILE"))."; else echo "Not running."; fi
  rm -f "$PIDFILE"
}

status() {
  if running; then echo "Running (pid $(cat "$PIDFILE")): $URL"; else echo "Not running."; fi
}

publish() {
  need_site
  cd "$SITE_REPO"
  git add -- docs/basket
  if git diff --cached --quiet -- docs/basket; then echo "Nothing new to publish in docs/basket."; return; fi
  local latest
  latest="$(ls docs/basket/data/runs | sort | tail -1)"
  # Commit only docs/basket, even if other files are staged.
  git commit -m "Basket rotation: publish latest results (run ${latest%.js})" -- docs/basket
  git push
  echo "Pushed. GitHub Pages updates in a minute or two:"
  echo "  https://doruirimescu.github.io/stock-market-data/basket/"
}

case "${1:-}" in
  export) export_run ;;
  trend) export_trend ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  restart) stop; start ;;
  publish) publish ;;
  *) echo "Usage: $0 {export|trend|start|stop|status|restart|publish}"; exit 2 ;;
esac
