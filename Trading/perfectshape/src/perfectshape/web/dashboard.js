/* Perfect Shapes Lab: config form, run control (play / pause / stop) and live results.
 * The scan runs in the dashboard server's background thread; this page only polls /api/status, so reloading
 * it (or closing it) never touches a running scan. The server reads this file on every request. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const PPY = 252;                     // trading days per year: window years -> bars
  const SHAPES = ["uptrend", "range"];

  // ---------------------------------------------------------------- info bubbles (key: input id or data-tip-for)
  const TIPS = {
    sector: "The universe is one <b>Select Sector SPDR</b>'s holdings, from State Street's daily holdings file (every stock with its weight; cash, futures and second share classes removed).",
    etf: "Which sector ETF supplies the stocks. Ratios are built only from stocks inside this one sector.",
    top: "How many of the ETF's <b>largest holdings by weight</b> to use. The number of 3 vs 3 ratios explodes with it: 12 stocks ≈ 9k, 16 ≈ 80k, 20 ≈ 388k, 25 ≈ 1.8M per window. Excluded stocks are replaced by the next one by weight.",
    baskets: "A ratio is <b>mean(numerator prices) / mean(denominator prices)</b>, every price normalised to 1 at the window start (equal weight per leg). Every combination is scored.",
    k: "Stocks in <b>each</b> basket: 3 means (A + B + C) / (D + E + F). Bigger baskets give smoother, more diversified ratios, but the count grows fast: at 20 stocks, 3 vs 3 ≈ 388k ratios, 4 vs 4 ≈ 4.4M, 5 vs 5 ≈ 23M per window. They also leave room for fewer distinct results, see Output.",
    overlap: "Let the same stock sit in both legs. Off by default: a shared stock partly cancels out and adds little.",
    maxratios: "Safety cap. A scan with <b>more ratios per window</b> than this is refused before it starts. Raise it to allow bigger scans; the estimate below shows the expected run time.",
    shapes: "<b>Uptrend</b>: the ratio rises along a straight line on a log scale, i.e. the numerator steadily outperforms (a falling ratio is listed flipped). <b>Range</b>: the ratio oscillates in a flat band, a mean-reversion trade candidate.",
    lag: "End the scan this many years <b>before today</b>: the search uses the lookback windows that end then (10 years by default) and never sees the years after. In the Trade Lab those years come back only as the <b>final test</b>: the optimizer never trains on them, and you switch them on to judge the final rules. 0 = scan up to today.",
    window: "Years of history, ending at the scan end, over which every ratio is fitted and scored (a trading year = 252 bars). " +
      "Longer = the shape must have held for longer. The prices loaded grow with it; a stock listed for less than this is left out of the search. " +
      "Run time grows with the length. The robust-range gates were tested on 5- and 10-year windows only.",
    scoring: "How a window's score (0 to 1) is computed and gated. Hover each field for details.",
    threshold: "Minimum score (0 to 1) for a window to count as holding the shape. Higher = fewer, cleaner results.",
    minret: "Trends only: the fitted line must move at least this much <b>per year</b>, so a nearly flat line does not count as a trend.",
    bandpct: "Range band = median ± the smaller half of the <b>p to (100 − p) percentile</b> band. 10 ≈ the 10th to 90th percentile. A lower number gives a wider band and rarer, larger trades.",
    exit: "A range trade opens when the ratio leaves the band. <b>Median</b>: close at the middle (more, smaller trades). <b>Opposite edge</b>: hold to the other side (fewer, larger trades).",
    harvest: "Annual return from trading the band (log units) at which the harvest part of the score reaches 63%. <b>Raise it</b> to demand more profitable ranges.",
    pain: "Penalty for the <b>worst move against an open trade</b> past its entry edge, measured in half-band widths. Beyond 1, the score is multiplied by exp(−(pain − 1) / scale). Lower = stricter about squeezes and spikes.",
    holdout: "The last trading days of data, <b>kept out of the search</b>: no ratio is picked, fitted or scored on them. Afterwards each result is checked on them: a trend must stay on the right side of its channel, a range inside its band (padded 25%). Pass = <b>Alive</b>; the move over these days is the Holdout column and the shaded strip on the charts. 21 ≈ one month; 0 turns the check off.",
    speed: "Optional: favour ranges whose swings <b>return to the mean quickly</b>. Each range gets its <b>average days to the mean</b> (how long a band trade takes from leaving the band to its exit), shown as <b>To mean</b> in the results. With a target of D days, ranges that return within D keep their full score and slower ones are scored down in proportion: D / days, inside the square root like the other factors, so twice as slow keeps 71% and four times as slow 50%. <b>0</b> = off: speed does not change the score.",
    robust: "<b>On by default.</b> Lists only ranges whose window shows what predicted, <b>out of sample</b>, that the scan-window band keeps reverting after the scan: " +
      "enough completed reversions per year, a band that is narrow against the ratio's own volatility, and swings that are not fading. " +
      "Found by replaying lagged scans of every sector (scan ends 2015–2024, 10-year windows) and trading each listed band over the next 2 years: " +
      "ranges passing these gates made <b>≥ 2 profitable reversions 48% of the time vs 15%</b> for all ranges (mean 2-year band P&L +5.3% vs −1.6%; losses over 60%: 0.6% vs 4.9%). " +
      "Few ranges pass: about 4 sector scans in 5 list none at these settings (1.5 trades/yr and band/vol 0.45 list about twice as often, 42% success), which is the point. Untick for the classic harvest score alone.",
    r_tpy: "Completed band trades (leave the band, return to the median) per year inside the scored window. 2 = about 4 in a 2-year final test. The strongest single predictor of reversions after the scan.",
    r_bvol: "Half the band height divided by the ratio's annual volatility. Low = ordinary daily noise keeps carrying the ratio to the edges, so the band keeps getting traded; high = the band was crossed only by a few big slow swings, which rarely repeat. 0.40 ≈ a mean-reversion half-life of about 35 trading days.",
    r_rvol: "Volatility of the window's last fifth divided by that of its median fifth. Below 1 the swings have been fading lately: the band, fitted on the whole window, stops being reached. 1.0 keeps ratios whose recent swings are at least as large as usual.",
    minheld: "A range must have held for at least this long to be listed. Its band, harvest and 'now' come from its best-scoring window of at least 1 year.",
    output: "How many results are kept and what the run is called.",
    topn: "Results kept per shape (uptrend, range).",
    maxper: "A stock may appear in at most this many results per shape, so a few names cannot fill the whole list. Follows the basket size (at least 3) until you change it: big baskets of a small universe share stocks, and a low cap would leave few results. A result is also dropped when more than half of its stocks are in a better one.",
    name: "Name of the run folder in <code>runs/</code> and of the config file saved to <code>configs/</code>.",
  };
  function addInfo(el, key) {
    if (!TIPS[key] || el.querySelector(":scope > .info")) return;
    const b = document.createElement("button");
    b.type = "button"; b.className = "info"; b.textContent = "i"; b.dataset.tip = key;
    b.setAttribute("aria-label", "About this setting"); b.setAttribute("aria-expanded", "false");
    el.appendChild(b);
  }
  function installTips() {
    // the bubbles themselves (hover, focus, tap, positioning) are handled page-wide by report.js
    Object.assign(PS.TIPS, TIPS);
    document.querySelectorAll(".lab-side .field, .lab-side .check").forEach((f) => {
      const input = f.querySelector("input, select");
      if (input) addInfo(f.querySelector("span"), input.id);
    });
    document.querySelectorAll("[data-tip-for]").forEach((el) => addInfo(el, el.dataset.tipFor));
  }
  let DEF = null, HOLD = [], excluded = new Set(), nameTouched = false;
  let state = "idle", lastV = -1, checkOk = false, est = {}, lastStatus = null, runId = null;
  const EMPTY_RESULTS = '<div class="panel empty-state">The best ratios found so far appear here within seconds of ' +
    'pressing Play and keep improving as the scan proceeds (longest lookbacks first).</div>';

  function clearResults(message) {
    lastV = -1;
    if (lastStatus) lastStatus.payload_meta = null;
    $("report").dataset.shape = "";
    $("report").innerHTML = message || EMPTY_RESULTS;
    $("links").innerHTML = "";
  }

  // ---------------------------------------------------------------- form
  function toggles(el, items, selected) {
    el.innerHTML = items.map(([v, label]) =>
      `<span class="chip${selected.includes(v) ? "" : " off"}" role="button" tabindex="0" data-v="${v}">${label}</span>`).join("");
    el.querySelectorAll(".chip").forEach((c) => {
      const flip = () => { c.classList.toggle("off"); changed(); };
      c.onclick = flip;
      c.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); } };
    });
  }
  const picked = (el) => [...el.querySelectorAll(".chip:not(.off)")].map((c) => c.dataset.v);
  const autoName = () => `${$("etf").value.toLowerCase()}_${$("k").value}v${$("k").value}`;
  let maxperTouched = false;

  function buildConfig() {
    const c = structuredClone(DEF), etf = $("etf").value;
    c.name = $("name").value || autoName();
    c.universe = { lists: [`etf:${etf}`], limit: +$("top").value, exclude: [...excluded] };
    c.search.shapes = picked($("shapes"));
    const years = Math.max(0.5, +$("window").value || 10);
    c.search.windows = [Math.round(years * PPY)];
    Object.assign(c.ratio, { k: +$("k").value, allow_overlap: $("overlap").checked,
      max_ratios: Math.max(1, Math.round(+$("maxratios").value || DEF.ratio.max_ratios)) });
    Object.assign(c.scoring, {
      threshold: +$("threshold").value, min_annual_return: +$("minret").value / 100, range_band_pct: +$("bandpct").value,
      range_exit: $("exit").value, range_harvest_scale: +$("harvest").value, range_pain_scale: +$("pain").value,
      range_speed_days: Math.max(0, +$("speed").value || 0),
      range_robust: $("robust").checked, range_min_trades_per_year: Math.max(0, +$("r_tpy").value || 0),
      range_max_band_vol: Math.max(0.05, +$("r_bvol").value || DEF.scoring.range_max_band_vol),
      range_min_recent_vol: Math.max(0, +$("r_rvol").value || 0),
    });
    c.search.holdout_bars = Math.max(0, Math.round(+$("holdout").value || 0));
    // prices to load: the window and the holdout plus a margin for holidays (never less than the default)
    c.data.years = Math.max(DEF.data.years, Math.ceil(years + c.search.holdout_bars / PPY + 0.5));
    c.data.lag_years = Math.max(0, +$("lag").value || 0);
    c.data.end = null;
    Object.assign(c.ranking, { top_n: +$("topn").value, max_per_member: +$("maxper").value,
      range_min_held: Math.round(+$("minheld").value * 252) });
    return c;
  }

  function applyConfig(c) {
    const lst = (c.universe.lists || []).find((x) => x.toLowerCase().startsWith("etf:"));
    if (lst) $("etf").value = lst.slice(4).toUpperCase();
    excluded = new Set(c.universe.exclude || []);
    $("top").value = c.universe.limit || 20;
    $("k").value = c.ratio.k; $("overlap").checked = c.ratio.allow_overlap;
    $("maxratios").value = c.ratio.max_ratios;
    toggles($("shapes"), SHAPES.map((s) => [s, s]), c.search.shapes);
    $("window").value = +(Math.max(...c.search.windows) / PPY).toFixed(2);
    $("threshold").value = c.scoring.threshold; $("minret").value = +(c.scoring.min_annual_return * 100).toFixed(2);
    $("bandpct").value = c.scoring.range_band_pct; $("exit").value = c.scoring.range_exit;
    $("harvest").value = c.scoring.range_harvest_scale; $("pain").value = c.scoring.range_pain_scale;
    $("speed").value = c.scoring.range_speed_days || 0;
    const sc = Object.assign({}, DEF.scoring, c.scoring);
    $("robust").checked = sc.range_robust !== false;
    $("r_tpy").value = sc.range_min_trades_per_year; $("r_bvol").value = sc.range_max_band_vol; $("r_rvol").value = sc.range_min_recent_vol;
    $("robust-fields").hidden = !$("robust").checked;
    $("minheld").value = +(c.ranking.range_min_held / 252).toFixed(2);
    $("holdout").value = c.search.holdout_bars;
    $("lag").value = (c.data && c.data.lag_years) || 0;
    $("topn").value = c.ranking.top_n; $("maxper").value = c.ranking.max_per_member;
    $("name").value = c.name;
  }

  function renderHoldings() {
    const top = +$("top").value;
    let rank = 0;
    $("hold").innerHTML = HOLD.map((h) => {
      const out = excluded.has(h.ticker), used = !out && ++rank <= top;
      return `<div class="hold-row${used ? "" : " out"}${out ? " excluded" : ""}" data-t="${esc(h.ticker)}" title="${out ? "excluded: click to include" : "click to exclude"}">` +
        `<input type="checkbox" ${out ? "" : "checked"} tabindex="-1"><span class="sym">${esc(h.ticker)}</span>` +
        `<span class="nm">${esc(h.name)}</span><span class="w">${h.weight.toFixed(1)}%</span></div>`;
    }).join("");
    $("hold-count").textContent = HOLD.length ? `${Math.min(top, HOLD.length - excluded.size)} of ${HOLD.length} used` : "";
    $("hold").querySelectorAll(".hold-row").forEach((row) => (row.onclick = () => {
      const t = row.dataset.t;
      excluded.has(t) ? excluded.delete(t) : excluded.add(t);
      renderHoldings(); changed();
    }));
  }

  async function loadHoldings() {
    $("hold").innerHTML = '<div class="muted small" style="padding:10px">Loading holdings…</div>';
    try {
      const r = await fetch("/api/holdings?etf=" + $("etf").value);
      if (!r.ok) throw new Error((await r.json()).error || r.statusText);
      HOLD = await r.json();
      renderHoldings();
    } catch (e) {
      HOLD = [];
      $("hold").innerHTML = `<div class="notice" style="margin:8px">Could not load holdings: ${esc(e.message)}</div>`;
    }
    changed();
  }

  function lagNote() {
    const n = +$("lag").value || 0;
    if (!n) { $("lag-note").textContent = "Scans up to today."; return; }
    const d = new Date(); d.setDate(d.getDate() - Math.round(n * 365.25));
    $("lag-note").innerHTML = `Scan ends <b>${d.toISOString().slice(0, 10)}</b>; the ${n} year${n === 1 ? "" : "s"} after it stay out of the search and come back as the Trade Lab's final test.`;
  }
  let checkTimer = null;
  function changed() {
    lagNote();
    $("robust-fields").hidden = !$("robust").checked;
    if (!nameTouched) $("name").value = autoName();
    clearTimeout(checkTimer);
    checkTimer = setTimeout(check, 250);
  }

  const fmtDur = (s) => {
    if (s == null) return "–";
    s = Math.round(s);
    if (s < 60) return s + "s";
    const m = Math.floor(s / 60);
    return m < 60 ? `${m}m ${String(s % 60).padStart(2, "0")}s` : `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
  };

  async function check() {
    const r = await fetch("/api/check", { method: "POST", body: JSON.stringify({ config: buildConfig() }) });
    const j = await r.json();
    checkOk = !!j.ok; est = j;
    if (j.yaml && !(state === "running" || state === "paused")) $("yaml").textContent = j.yaml;
    const e = $("est");
    if (j.ok) {
      e.className = "estimate callout";
      e.innerHTML = `<b>${j.instruments}</b> stocks · <b>${(j.ratios ?? 0).toLocaleString()}</b> ratios per window` +
        (j.est_seconds != null ? ` · about <mark>${fmtDur(j.est_seconds)}</mark>` : "");
    } else {
      e.className = "estimate notice";
      e.textContent = j.error || "invalid config";
    }
    syncButtons();
    if (lastStatus) renderKpis(lastStatus);
  }

  // ---------------------------------------------------------------- run control
  function syncButtons() {
    const p = $("play"), s = $("stop");
    if (state === "running") { p.textContent = "❚❚ Pause"; p.disabled = false; }
    else if (state === "paused") { p.textContent = "▶ Resume"; p.disabled = false; }
    else { p.textContent = "▶ Play"; p.disabled = !checkOk; }
    s.disabled = !(state === "running" || state === "paused");
  }

  $("play").onclick = async () => {
    const url = state === "running" ? "/api/pause" : state === "paused" ? "/api/resume" : "/api/run";
    const r = await fetch(url, { method: "POST", body: JSON.stringify({ config: buildConfig() }) });
    if (!r.ok) { const j = await r.json(); showError(j.error || "could not start"); }
    else {
      showError(null);
      if (url === "/api/run") clearResults('<div class="panel empty-state">Scan started: the best ratios found so far ' +
        "appear here within seconds and keep improving.</div>");
    }
    poll(true);
  };
  $("stop").onclick = async () => { await fetch("/api/stop", { method: "POST" }); poll(true); };
  $("save").onclick = async () => {
    const r = await fetch("/api/save", { method: "POST", body: JSON.stringify({ config: buildConfig() }) });
    const j = await r.json();
    $("saved").textContent = j.ok ? "saved " + j.path : j.error || "failed";
  };
  $("copy").onclick = async () => {
    try { await navigator.clipboard.writeText($("yaml").textContent); $("saved").textContent = "copied"; }
    catch (e) { $("saved").textContent = "copy failed"; }
  };
  function showError(msg) { $("error").hidden = !msg; $("error").textContent = msg || ""; }

  const BADGE = { idle: ["", "Idle"], running: ["live", "Running"], paused: ["past", "Paused"], done: ["", "Finished"],
    stopped: ["past", "Stopped"], error: ["", "Failed"] };

  function renderKpis(s) {
    const P = s.payload_meta || {};
    const kpi = (label, value, sub) => `<div class="panel kpi"><div class="label">${label}</div><div class="value sm">${value}</div><div class="sub">${sub || ""}</div></div>`;
    const running = s.state === "running" || s.state === "paused";
    $("kpis").innerHTML =
      kpi("Stocks", P.symbols ?? est.instruments ?? "–", P.requested ? `of ${P.requested} requested` : "in the universe") +
      kpi("Ratios per window", (P.ratios ?? est.ratios ?? 0).toLocaleString(),
        `${$("k").value} vs ${$("k").value}` + (P.ratios != null && est.ratios != null && P.ratios !== est.ratios ? ` · ${est.ratios.toLocaleString()} if all stocks had the history` : "")) +
      kpi("Progress", `${(s.progress * 100).toFixed(1)}%`, `<div class="progress"><div style="width:${(s.progress * 100).toFixed(1)}%"></div></div>`) +
      kpi(running ? "Time left" : "Run time", running ? fmtDur(s.eta) : fmtDur(s.elapsed), running ? `elapsed ${fmtDur(s.elapsed)}` : s.state) +
      Object.entries(P.found || {}).map(([k, v]) => kpi(k === "range" ? "Ranges" : k[0].toUpperCase() + k.slice(1) + "s", v.n,
        v.n ? `best score ${v.best.toFixed(3)}` : "none yet")).join("");
  }

  let pollTimer = null;
  async function poll(once) {
    try {
      let s = await (await fetch("/api/status?v=" + lastV)).json();
      if (runId !== null && s.run_id !== runId) {        // a new scan started (here or in another tab)
        clearResults();
        s = await (await fetch("/api/status?v=-1")).json();
      }
      runId = s.run_id;
      state = s.state;
      const [cls, label] = BADGE[s.state] || ["", s.state];
      $("badge").className = "badge " + cls;
      $("badge").textContent = label;
      $("bar").firstElementChild.style.width = (s.progress * 100).toFixed(1) + "%";
      $("bar").classList.toggle("paused", s.state === "paused");
      $("stage").textContent = s.state === "idle" ? "Configure a scan and press Play." : [s.stage, s.detail].filter(Boolean).join(" · ");
      $("timing").textContent = s.state === "idle" ? "" : `${(s.progress * 100).toFixed(1)}% · ${fmtDur(s.elapsed)}` +
        (s.state === "running" ? ` · ${fmtDur(s.eta)} left` : "");
      showError(s.state === "error" ? s.error : null);
      $("links").innerHTML = s.run_dir ? `Saved to <code>runs/${esc(s.run_dir)}</code>: ` +
        ["report.html", "results.csv", "summary.md"].map((f) => `<a href="/runs/${encodeURIComponent(s.run_dir)}/${f}" target="_blank">${f}</a>`).join(" · ") : "";
      $("log").textContent = (s.log || []).join("\n");
      if (s.payload) {
        lastV = s.version;
        const P = s.payload;
        s.payload_meta = { symbols: P.panel.symbols - (P.panel.short || []).length, requested: P.panel.requested, ratios: P.panel.ratios,
          found: Object.fromEntries(Object.entries(P.shapes).map(([k, v]) => [k, { n: v.items.length, best: Math.max(0, ...v.items.map((i) => i.score)) }])) };
        const y = window.scrollY;
        PS.renderReport(P, $("report"), { onOpen: PS.openTradeLab });
        window.scrollTo(0, y);
      } else if (lastStatus) {
        s.payload_meta = lastStatus.payload_meta;
      }
      if (s.config_yaml && (s.state === "running" || s.state === "paused")) $("yaml").textContent = s.config_yaml;
      lastStatus = s;
      renderKpis(s);
      syncButtons();
    } catch (e) {
      $("stage").textContent = "Dashboard server unreachable: is `mise run dashboard` still running?";
    }
    if (!once) { clearTimeout(pollTimer); pollTimer = setTimeout(() => poll(false), state === "running" ? 1000 : 2500); }
  }

  // ---------------------------------------------------------------- saved analyses
  const pctS = (v) => (v == null || !isFinite(v) ? "–" : `<span class="${v >= 0 ? "pos" : "neg"}">${(v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(1)}%</span>`);
  const armed = new Set();
  async function loadAnalyses() {
    let list = [];
    try { list = await (await fetch("/api/analyses")).json(); } catch (e) { list = []; }
    if (!Array.isArray(list) || !list.length) {
      $("analyses").innerHTML = '<tbody><tr><td class="muted">No saved analyses yet: open a result in the Trade Lab and press 💾 Save analysis.</td></tr></tbody>';
      return;
    }
    $("analyses").innerHTML = `<thead><tr><th data-list="title">Name</th><th data-list="subtitle">Ratio</th><th>Rules</th><th>Period</th>` +
      `<th class="num" data-list="value">CAGR</th><th class="num">SPY CAGR</th><th class="num">Sharpe</th><th class="num">Max DD</th><th class="num">Trades</th>` +
      `<th data-list="note">Saved</th><th></th></tr></thead><tbody>` +
      list.map((a) => {
        const q = a.query || {}, m = a.summary || {};
        return `<tr><td><b>${esc(a.name)}</b>${a.notes ? `<div class="muted small">${esc(a.notes.slice(0, 140))}${a.notes.length > 140 ? "…" : ""}</div>` : ""}</td>` +
          `<td class="cfg">${esc((q.num || "").replaceAll(",", " "))} / ${esc((q.den || "").replaceAll(",", " "))}</td>` +
          `<td class="cfg">${esc(m.rules || q.strategy || "")}</td><td class="muted small">${esc(m.from || "")} → ${esc(m.to || "")}</td>` +
          `<td class="num">${pctS(m.cagr)}</td><td class="num">${pctS(m.spy_cagr)}</td><td class="num">${m.sharpe == null ? "–" : (+m.sharpe).toFixed(2)}</td>` +
          `<td class="num">${m.mdd == null ? "–" : `<span class="neg">−${Math.abs(m.mdd * 100).toFixed(1)}%</span>`}</td><td class="num">${m.trades ?? "–"}</td>` +
          `<td class="muted small">${esc((a.saved || "").replace("T", " "))}</td>` +
          `<td class="actions"><button class="btn sm primary" data-open="${esc(a.id)}">Open</button>` +
          `<button class="btn sm" data-del="${esc(a.id)}">${armed.has(a.id) ? "Confirm delete" : "Delete"}</button></td></tr>`;
      }).join("") + `</tbody>`;
    const byId = Object.fromEntries(list.map((a) => [a.id, a]));
    $("analyses").querySelectorAll("[data-open]").forEach((b) => (b.onclick = () => {
      const a = byId[b.dataset.open];
      window.open("/trade.html?" + new URLSearchParams(Object.assign({}, a.query, { analysis: a.id })), "_blank");
    }));
    $("analyses").querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      const id = b.dataset.del;
      if (!armed.has(id)) { armed.add(id); b.textContent = "Confirm delete"; setTimeout(() => { armed.delete(id); loadAnalyses(); }, 4000); return; }
      armed.delete(id);
      await fetch("/api/analyses/delete", { method: "POST", body: JSON.stringify({ id }) });
      loadAnalyses();
    }));
  }
  $("an_refresh").onclick = loadAnalyses;
  window.addEventListener("focus", loadAnalyses);        // coming back from a Trade Lab window that saved one

  // ---------------------------------------------------------------- start
  (async function init() {
    const meta = await (await fetch("/api/meta")).json();
    DEF = meta.defaults;
    $("etf").innerHTML = Object.entries(meta.sectors).map(([k, v]) => `<option value="${k}">${k} · ${esc(v)}</option>`).join("");
    const current = await (await fetch("/api/status?v=-1")).json();   // a running / finished scan restores its form
    applyConfig(current.config || DEF);
    nameTouched = !!current.config && current.config.name !== autoName();
    document.querySelectorAll(".lab-side input:not([type=checkbox]), .lab-side select").forEach((el) =>
      el.addEventListener("input", () => {
        if (el.id === "name") nameTouched = !!el.value;
        if (el.id === "maxper") maxperTouched = true;
        if (el.id === "k" && !maxperTouched) $("maxper").value = Math.max(3, +$("k").value);
        if (el.id === "etf") { excluded.clear(); loadHoldings(); return; }
        if (el.id === "top") renderHoldings();
        changed();
      }));
    $("overlap").onchange = changed;
    $("robust").onchange = changed;
    installTips();
    await loadHoldings();
    loadAnalyses();
    poll(false);
  })();
})();
