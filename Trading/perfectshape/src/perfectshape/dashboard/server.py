"""Local dashboard: build a scan config in the browser, run it, follow it live, pause / resume / stop it.

``perfectshape dashboard`` (``mise run dashboard``) serves http://127.0.0.1:8765. One scan runs at a time in a
background thread; the page polls ``/api/status`` and re-renders the ranking after every finished window.

API (JSON):
  GET  /api/meta                     sector ETFs, defaults, speed constant for estimates
  GET  /api/holdings?etf=XLK         holdings of a sector ETF (largest weight first)
  POST /api/check    {config}        validate -> {ok, yaml, instruments, ratios, est_seconds | error}
  POST /api/run      {config}        start a new scan
  POST /api/pause | /api/resume | /api/stop
  GET  /api/status?v=N               state + progress; includes the ranking payload when version > N
  POST /api/save     {config}        write configs/<name>.yaml
  GET  /api/analyses                 saved Trade Lab analyses (newest first); GET /api/analyses/<id> one of them
  POST /api/analyses {id?, name, notes, query, summary}   save (update when id is given) -> {id}
  POST /api/analyses/delete {id}
  GET  /runs/<dir>/<file>            finished run outputs (report.html, results.csv, ...)
  GET  /assets/<file>                page assets from perfectshape/web/, read fresh on every request
"""

from __future__ import annotations

import json
import logging
import threading
import time
import traceback
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

import yaml
from pydantic import ValidationError

from perfectshape.config import RunConfig
from perfectshape.holdings import SECTOR_ETFS, holdings
from perfectshape.pipeline import ScanCancelled, ScanControl, ScanOutput, scan
from perfectshape.ratio import count_ratios
from perfectshape.report.writer import _payload, write_run
from perfectshape.universe import PROJECT_ROOT

log = logging.getLogger(__name__)

# the page and its assets are read from disk on every request: edit them and refresh the browser, no restart
# (the scan runs in this process's background thread, so a page reload never touches it)
WEB = Path(__file__).resolve().parents[1] / "web"
ASSETS = {"shapes.css": "text/css; charset=utf-8", "report.js": "text/javascript; charset=utf-8",
          "dashboard.js": "text/javascript; charset=utf-8", "trade.js": "text/javascript; charset=utf-8"}
PAGES = {"/": "dashboard.html", "/index.html": "dashboard.html", "/trade.html": "trade.html"}
BENCHMARK = "SPY"
ANALYSES = PROJECT_ROOT / "analyses"          # saved Trade Lab analyses, one JSON file each (git-ignored)
# seconds per (ratio x bar x shape), measured on XLU top 16 at 3 vs 3 (80,080 ratios, 11 windows, 2 shapes:
# 24 s); machine and data dependent (pruning skips more on noisier universes), for estimates only
SECONDS_PER_RATIO_BAR = 1.5e-8

DEFAULT_CONFIG = {
    "config_version": 1,
    "name": "xlk_3v3",
    "universe": {"lists": ["etf:XLK"], "limit": 20, "exclude": []},
    "data": {"source": "yfinance", "years": 11, "cache_dir": "data_cache", "max_age_days": 1},
    "search": {"mode": "ratio", "shapes": ["uptrend", "range"],
               "windows": [63, 126, 252, 378, 504, 756, 1008, 1260, 1512, 2016, 2520], "holdout_bars": 21},
    "ratio": {"k": 3, "allow_overlap": False, "keep_per_window": 300, "max_ratios": 25_000_000},
    "scoring": {"space": "log", "threshold": 0.6, "min_annual_return": 0.05, "min_range_height": 0.10,
                "max_range_drift": 0.5, "complexity_penalty": 0.0, "range_band_pct": 10, "range_exit": "mid",
                "range_harvest_scale": 0.15, "range_pain_scale": 2.0, "range_segments": 4},
    "ranking": {"top_n": 30, "require_alive": True, "max_overlap": 0.5, "max_per_member": 3,
                "range_sort": "score", "range_min_held": 504, "range_min_score_window": 252},
}


class _LogBuffer(logging.Handler):
    def __init__(self, n: int = 200):
        super().__init__(logging.INFO)
        self.lines: deque[str] = deque(maxlen=n)
        self.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.lines.append(self.format(record))


class RunManager(ScanControl):
    """The one scan the dashboard runs: a thread, its pause gate, its progress and its latest ranking."""

    def __init__(self):
        self.lock = threading.Lock()
        self.go = threading.Event()          # set = running, clear = paused
        self.go.set()
        self.stop_requested = False
        self.thread: Optional[threading.Thread] = None
        self.logs = _LogBuffer()
        self.run_id = 0                      # changes with every new scan, so pages can drop old results
        logging.getLogger("perfectshape").addHandler(self.logs)
        self._reset("idle")

    def _reset(self, state: str, cfg: Optional[RunConfig] = None):
        self.state = state                   # idle | running | paused | done | stopped | error
        self.cfg = cfg
        self.stage_text = ""
        self.detail = ""
        self.progress = 0.0
        self.active_seconds = 0.0            # time spent running (pauses excluded)
        self._resumed_at = time.monotonic()
        self.version = 0
        self.payload: Optional[dict] = None
        self.run_dir: Optional[str] = None
        self.error: Optional[str] = None

    # ---------------------------------------------------------------- commands (HTTP threads)

    def start(self, cfg: RunConfig) -> None:
        with self.lock:
            if self.state in ("running", "paused"):
                raise RuntimeError("a scan is already running; stop it first")
            self._reset("running", cfg)
            self.run_id += 1
            self.stop_requested = False
            self.go.set()
            self.thread = threading.Thread(target=self._run, name="perfectshape-scan", daemon=True)
            self.thread.start()

    def pause(self) -> None:
        with self.lock:
            if self.state == "running":
                self.active_seconds += time.monotonic() - self._resumed_at
                self.state = "paused"
                self.go.clear()

    def resume(self) -> None:
        with self.lock:
            if self.state == "paused":
                self._resumed_at = time.monotonic()
                self.state = "running"
                self.go.set()

    def stop(self) -> None:
        with self.lock:
            if self.state in ("running", "paused"):
                self.stop_requested = True
                self.go.set()

    def status(self, since: int) -> dict:
        with self.lock:
            active = self.active_seconds + (time.monotonic() - self._resumed_at if self.state == "running" else 0)
            eta = active / self.progress * (1 - self.progress) if 0.02 < self.progress < 1 else None
            out = {"run_id": self.run_id, "state": self.state, "stage": self.stage_text, "detail": self.detail,
                   "progress": self.progress, "elapsed": active, "eta": eta, "version": self.version,
                   "run_dir": self.run_dir, "error": self.error, "log": list(self.logs.lines)[-12:],
                   "name": self.cfg.name if self.cfg else None,
                   "config_yaml": yaml.safe_dump(self.cfg.model_dump(mode="json"), sort_keys=False,
                                                 default_flow_style=None, width=110) if self.cfg else None}
            if self.payload is not None and self.version > since:
                out["payload"] = self.payload
            if since < 0 and self.cfg is not None:
                out["config"] = self.cfg.model_dump(mode="json")      # lets a reopened page restore its form
            return out

    # ---------------------------------------------------------------- ScanControl (scan thread)

    def stage(self, text: str) -> None:
        with self.lock:
            self.stage_text = text
        log.info("%s", text)

    def checkpoint(self, progress: float, detail: str = "") -> None:
        with self.lock:
            self.progress = max(self.progress, min(progress, 1.0))
            self.detail = detail
        self.go.wait()                       # blocks while paused
        if self.stop_requested:
            raise ScanCancelled()

    def partial(self, out: ScanOutput) -> None:
        payload = _payload(out, [])
        payload["partial"] = not out.done
        with self.lock:
            self.payload = payload
            self.version += 1

    def _run(self) -> None:
        try:
            out = scan(self.cfg, control=self)
            run_dir = write_run(out)
            self.partial(out)
            with self.lock:
                self.active_seconds += time.monotonic() - self._resumed_at
                self.run_dir = run_dir.name
                self.progress = 1.0
                self.state = "done"
                self.stage_text = "finished"
        except ScanCancelled:
            with self.lock:
                self.active_seconds += time.monotonic() - self._resumed_at
                self.state = "stopped"
                self.stage_text = "stopped (partial results kept on the page, nothing written)"
        except Exception as e:  # noqa: BLE001 - surfaced on the page
            log.error("scan failed: %s", e)
            with self.lock:
                self.state = "error"
                self.error = f"{type(e).__name__}: {e}"
                self.stage_text = "failed"
            log.debug(traceback.format_exc())


def check_config(raw: dict) -> dict:
    """Validate a config from the page; estimate its size and runtime."""
    try:
        cfg = RunConfig.model_validate(raw)
    except ValidationError as e:
        return {"ok": False, "error": "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())}
    dumped = cfg.model_dump(mode="json")
    out = {"ok": True, "yaml": yaml.safe_dump(dumped, sort_keys=False, default_flow_style=None, width=110)}
    try:
        n = _instrument_count(cfg)
    except Exception as e:  # noqa: BLE001
        return {**out, "ok": False, "error": f"universe: {e}"}
    out["instruments"] = n
    if cfg.search.mode == "ratio":
        r = count_ratios(n, cfg.ratio)
        out["ratios"] = r
        out["est_seconds"] = r * sum(cfg.search.windows) * len(cfg.search.shapes) * SECONDS_PER_RATIO_BAR
        if r > cfg.ratio.max_ratios:
            out.update(ok=False, error=f"{r:,} ratios > ratio.max_ratios ({cfg.ratio.max_ratios:,}): "
                                       "use fewer holdings or smaller baskets")
    return out


def _instrument_count(cfg: RunConfig) -> int:
    from perfectshape.universe import build_universe
    u = cfg.universe
    return len(build_universe(u.lists, u.tickers, u.exclude, u.limit).tickers)


class _Handler(BaseHTTPRequestHandler):
    manager: RunManager

    def log_message(self, fmt, *args):      # keep the terminal quiet (status is polled every second)
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, default=float).encode(), "application/json")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path in PAGES:
                return self._send(200, (WEB / PAGES[url.path]).read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/analyses":
                return self._json(list_analyses())
            if url.path.startswith("/api/analyses/"):
                return self._json(load_analysis(url.path.rsplit("/", 1)[1]))
            if url.path == "/api/series":
                return self._json(self._series(q))
            if url.path.startswith("/assets/"):
                name = url.path[len("/assets/"):]
                if name in ASSETS:
                    return self._send(200, (WEB / name).read_bytes(), ASSETS[name])
            if url.path == "/api/meta":
                return self._json({"sectors": SECTOR_ETFS, "defaults": DEFAULT_CONFIG,
                                   "speed": SECONDS_PER_RATIO_BAR})
            if url.path == "/api/holdings":
                etf = q.get("etf", ["XLK"])[0]
                return self._json([h.__dict__ for h in holdings(etf)])
            if url.path == "/api/status":
                return self._json(self.manager.status(int(q.get("v", ["-1"])[0])))
            if url.path.startswith("/runs/"):
                return self._run_file(unquote(url.path[len("/runs/"):]))
            self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        m = self.manager
        try:
            if path == "/api/check":
                return self._json(check_config(self._body().get("config", {})))
            if path == "/api/run":
                chk = check_config(self._body().get("config", {}))
                if not chk["ok"]:
                    return self._json(chk, 400)
                m.start(RunConfig.model_validate(yaml.safe_load(chk["yaml"])))
                return self._json({"ok": True})
            if path in ("/api/pause", "/api/resume", "/api/stop"):
                getattr(m, path.rsplit("/", 1)[1])()
                return self._json({"ok": True, "state": m.state})
            if path == "/api/analyses":
                return self._json(save_analysis(self._body()))
            if path == "/api/analyses/delete":
                delete_analysis(str(self._body().get("id", "")))
                return self._json({"ok": True})
            if path == "/api/save":
                chk = check_config(self._body().get("config", {}))
                if "yaml" not in chk:
                    return self._json(chk, 400)
                name = yaml.safe_load(chk["yaml"])["name"]
                safe = "".join(c for c in name if c.isalnum() or c in "-_") or "dashboard"
                dest = PROJECT_ROOT / "configs" / f"{safe}.yaml"
                dest.write_text("# written by the perfectshape dashboard\n" + chk["yaml"], encoding="utf-8")
                return self._json({"ok": True, "path": str(dest.relative_to(PROJECT_ROOT))})
            self._json({"error": "not found"}, 404)
        except RuntimeError as e:
            self._json({"ok": False, "error": str(e)}, HTTPStatus.CONFLICT)
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)

    def _series(self, q: dict) -> dict:
        split = lambda key: [t for t in (q.get(key, [""])[0]).split(",") if t]
        cfg = self.manager.cfg
        data_cfg = cfg.data if cfg is not None else RunConfig.model_validate(DEFAULT_CONFIG).data
        return series_payload(split("num"), split("den"), q.get("bench", [BENCHMARK])[0], data_cfg, split("lists"))

    def _run_file(self, rel: str) -> None:
        root = (PROJECT_ROOT / "runs").resolve()
        target = (root / rel).resolve()
        if root not in target.parents or not target.is_file():
            return self._json({"error": "not found"}, 404)
        ctype = {".html": "text/html; charset=utf-8", ".csv": "text/csv", ".json": "application/json",
                 ".md": "text/markdown; charset=utf-8"}.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)


# ---------------------------------------------------------------- saved Trade Lab analyses
_ID_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


def _analysis_path(aid: str) -> Path:
    if not aid or not set(aid) <= _ID_OK or len(aid) > 120:
        raise ValueError(f"bad analysis id {aid!r}")
    return ANALYSES / f"{aid}.json"


def save_analysis(body: dict) -> dict:
    """Create (no id) or update (id) a saved analysis: {name, notes, query, summary}."""
    import re
    from datetime import datetime

    name = str(body.get("name") or "").strip()[:200] or "Untitled analysis"
    query = body.get("query")
    if not isinstance(query, dict) or not query.get("num") or not query.get("den"):
        raise ValueError("query with num and den is required")
    now = datetime.now().isoformat(timespec="seconds")
    aid = str(body.get("id") or "")
    if aid:
        path = _analysis_path(aid)
        created = json.loads(path.read_text(encoding="utf-8")).get("created", now) if path.exists() else now
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "analysis"
        base_id = aid = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{slug}"
        n = 2
        while _analysis_path(aid).exists():                     # two saves in the same second
            aid, n = f"{base_id}-{n}", n + 1
        path, created = _analysis_path(aid), now
    doc = {"id": aid, "name": name, "notes": str(body.get("notes") or "")[:5000], "created": created, "saved": now,
           "query": {str(k): str(v) for k, v in query.items()}, "summary": body.get("summary") or {}}
    ANALYSES.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return {"ok": True, "id": aid, "saved": now}


def load_analysis(aid: str) -> dict:
    path = _analysis_path(aid)
    if not path.exists():
        raise FileNotFoundError(f"no saved analysis {aid}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_analyses() -> list[dict]:
    if not ANALYSES.exists():
        return []
    docs = []
    for p in ANALYSES.glob("*.json"):
        try:
            docs.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(docs, key=lambda d: d.get("saved", ""), reverse=True)


def delete_analysis(aid: str) -> None:
    path = _analysis_path(aid)
    if path.exists():
        path.unlink()


def series_payload(num: list[str], den: list[str], bench: str, data_cfg, lists: list[str] = ()) -> dict:
    """Aligned daily closes of a ratio's members plus the benchmark, for the Trade Lab (from the price cache).

    -> {dates, num, den, names, bench, close: {ticker: [price or None, ...]}}
    """
    from perfectshape.data.sources import load_panel
    from perfectshape.universe import build_universe

    if not num or not den:
        raise ValueError("num= and den= are required")
    panel = load_panel(list(dict.fromkeys(num + den + [bench])), data_cfg)
    missing = [t for t in num + den if t not in panel.symbols]
    if missing:
        raise ValueError(f"no price data for {', '.join(missing)}")
    names: dict[str, str] = {}
    if lists:
        try:
            u = build_universe(lists)
            names = {t: u.name(t) for t in num + den if u.name(t)}
        except Exception:  # noqa: BLE001 - names are cosmetic
            pass
    has_bench = bench in panel.symbols
    col = lambda t: [None if v != v else round(float(v), 6) for v in panel.close[:, panel.symbols.index(t)]]
    return {"dates": [str(d) for d in panel.dates], "num": num, "den": den, "names": names,
            "bench": bench if has_bench else None,
            "close": {t: col(t) for t in dict.fromkeys(num + den + ([bench] if has_bench else []))}}


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    import os
    import webbrowser

    os.chdir(PROJECT_ROOT)                   # relative cache / runs / configs paths resolve in the project
    handler = type("Handler", (_Handler,), {"manager": RunManager()})
    httpd = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}/"
    print(f"perfectshape dashboard on {url}  (Ctrl+C to quit)", flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


__all__ = ["serve", "RunManager", "check_config", "DEFAULT_CONFIG"]
