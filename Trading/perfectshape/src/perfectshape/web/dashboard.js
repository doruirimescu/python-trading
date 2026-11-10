/* Perfect Shapes Lab: config form, run control (play / pause / stop) and live results.
 * The scan runs in the dashboard server's background thread; this page only polls /api/status, so reloading
 * it (or closing it) never touches a running scan. The server reads this file on every request. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const WINDOWS = [[63, "3m"], [126, "6m"], [252, "1y"], [378, "1.5y"], [504, "2y"], [756, "3y"], [1008, "4y"],
    [1260, "5y"], [1512, "6y"], [2016, "8y"], [2520, "10y"]];
  const SHAPES = ["uptrend", "range"];

  // ---------------------------------------------------------------- info bubbles (key: input id or data-tip-for)
  const TIPS = {
    sector: "The universe is one <b>Select Sector SPDR</b>'s holdings, from State Street's daily holdings file (every stock with its weight; cash, futures and second share classes removed).",
    etf: "Which sector ETF supplies the stocks. Ratios are built only from stocks inside this one sector.",
    top: "How many of the ETF's <b>largest holdings by weight</b> to use. The number of 3 vs 3 ratios explodes with it: 12 stocks ≈ 9k, 16 ≈ 80k, 20 ≈ 388k, 25 ≈ 1.8M per window. Excluded stocks are replaced by the next one by weight.",
    baskets: "A ratio is <b>mean(numerator prices) / mean(denominator prices)</b>, every price normalised to 1 at the window start (equal weight per leg). Every combination is scored.",
    kn: "Stocks in the <b>numerator</b> basket (top of the ratio). The ratio rises when these outperform.",
    kd: "Stocks in the <b>denominator</b> basket (bottom of the ratio).",
    overlap: "Let the same stock sit in both legs. Off by default: a shared stock partly cancels out and adds little.",
    maxratios: "Safety cap. A scan with <b>more ratios per window</b> than this is refused before it starts. Raise it to allow bigger scans; the estimate below shows the expected run time.",
    shapes: "<b>Uptrend</b>: the ratio rises along a straight line on a log scale, i.e. the numerator steadily outperforms (a falling ratio is listed flipped). <b>Range</b>: the ratio oscillates in a flat band, a mean-reversion trade candidate.",
    windows: "Lookbacks over which every ratio is fitted and scored. <b>Held</b> = the longest window whose score clears the threshold. Run time grows with the total length of the windows picked.",
    scoring: "How a window's score (0 to 1) is computed and gated. Hover each field for details.",
    threshold: "Minimum score (0 to 1) for a window to count as holding the shape. Higher = fewer, cleaner results.",
    minret: "Trends only: the fitted line must move at least this much <b>per year</b>, so a nearly flat line does not count as a trend.",
    bandpct: "Range band = median ± the smaller half of the <b>p to (100 − p) percentile</b> band. 10 ≈ the 10th to 90th percentile. A lower number gives a wider band and rarer, larger trades.",
    exit: "A range trade opens when the ratio leaves the band. <b>Median</b>: close at the middle (more, smaller trades). <b>Opposite edge</b>: hold to the other side (fewer, larger trades).",
    harvest: "Annual return from trading the band (log units) at which the harvest part of the score reaches 63%. <b>Raise it</b> to demand more profitable ranges.",
    pain: "Penalty for the <b>worst move against an open trade</b> past its entry edge, measured in half-band widths. Beyond 1, the score is multiplied by exp(−(pain − 1) / scale). Lower = stricter about squeezes and spikes.",
    holdout: "The last trading days of data, <b>kept out of the search</b>: no ratio is picked, fitted or scored on them. Afterwards each result is checked on them: a trend must stay on the right side of its channel, a range inside its band (padded 25%). Pass = <b>Alive</b>; the move over these days is the Holdout column and the shaded strip on the charts. 21 ≈ one month; 0 turns the check off.",
    minheld: "A range must have held for at least this long to be listed. Its band, harvest and 'now' come from its best-scoring window of at least 1 year.",
    output: "How many results are kept and what the run is called.",
    topn: "Results kept per shape (uptrend, range).",
    maxper: "A stock may appear in at most this many results per shape, so a few names cannot fill the whole list.",
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
    document.querySelectorAll(".lab-side .field, .lab-side .check").forEach((f) => {
      const input = f.querySelector("input, select");
      if (input) addInfo(f.querySelector("span"), input.id);
    });
    document.querySelectorAll("[data-tip-for]").forEach((el) => addInfo(el, el.dataset.tipFor));
    const tip = $("tip");
    let owner = null;
    const place = (b) => {
      const r = b.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
      if (r.bottom < 0 || r.top > window.innerHeight) return hide();            // bubble scrolled away
      const vw = window.innerWidth, vh = window.innerHeight;
      let x = r.right + 10, y = r.top - 6;                                       // right of the bubble
      if (x + w > vw - 8) x = r.left - w - 10;                                   // else left of it
      if (x < 8) { x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), vw - w - 8); y = r.bottom + 8; }  // else below
      y = Math.min(Math.max(8, y), vh - h - 8);
      tip.style.left = x + "px"; tip.style.top = y + "px";
    };
    const show = (b) => {
      owner && owner.setAttribute("aria-expanded", "false");
      owner = b; b.setAttribute("aria-expanded", "true");
      tip.innerHTML = TIPS[b.dataset.tip]; tip.hidden = false;
      place(b);
    };
    const hide = () => { tip.hidden = true; owner && owner.setAttribute("aria-expanded", "false"); owner = null; };
    document.querySelectorAll(".info").forEach((b) => {
      b.addEventListener("mouseenter", () => show(b));
      b.addEventListener("mouseleave", hide);
      b.addEventListener("focus", () => show(b));
      b.addEventListener("blur", hide);
      // a click (or a tap on touch screens) only shows; clicking elsewhere or Esc hides
      b.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); show(b); });
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
    document.addEventListener("click", hide);
    // scrolling (also the scroll-into-view of a keyboard focus) moves the tooltip with its bubble
    const follow = () => owner && place(owner);
    document.querySelector(".lab-side").addEventListener("scroll", follow, { passive: true });
    window.addEventListener("scroll", follow, { passive: true });
    window.addEventListener("resize", follow);
  }
  let DEF = null, HOLD = [], excluded = new Set(), nameTouched = false;
  let state = "idle", lastV = -1, checkOk = false, est = {}, lastStatus = null;

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
  const autoName = () => `${$("etf").value.toLowerCase()}_${$("kn").value}v${$("kd").value}`;

  function buildConfig() {
    const c = structuredClone(DEF), etf = $("etf").value;
    c.name = $("name").value || autoName();
    c.universe = { lists: [`etf:${etf}`], limit: +$("top").value, exclude: [...excluded] };
    c.search.shapes = picked($("shapes"));
    c.search.windows = picked($("windows")).map(Number);
    Object.assign(c.ratio, { k_num: +$("kn").value, k_den: +$("kd").value, allow_overlap: $("overlap").checked,
      max_ratios: Math.max(1, Math.round(+$("maxratios").value || DEF.ratio.max_ratios)) });
    Object.assign(c.scoring, {
      threshold: +$("threshold").value, min_annual_return: +$("minret").value / 100, range_band_pct: +$("bandpct").value,
      range_exit: $("exit").value, range_harvest_scale: +$("harvest").value, range_pain_scale: +$("pain").value,
    });
    c.search.holdout_bars = Math.max(0, Math.round(+$("holdout").value || 0));
    Object.assign(c.ranking, { top_n: +$("topn").value, max_per_member: +$("maxper").value,
      range_min_held: Math.round(+$("minheld").value * 252) });
    return c;
  }

  function applyConfig(c) {
    const lst = (c.universe.lists || []).find((x) => x.toLowerCase().startsWith("etf:"));
    if (lst) $("etf").value = lst.slice(4).toUpperCase();
    excluded = new Set(c.universe.exclude || []);
    $("top").value = c.universe.limit || 20;
    $("kn").value = c.ratio.k_num; $("kd").value = c.ratio.k_den; $("overlap").checked = c.ratio.allow_overlap;
    $("maxratios").value = c.ratio.max_ratios;
    toggles($("shapes"), SHAPES.map((s) => [s, s]), c.search.shapes);
    toggles($("windows"), WINDOWS.map(([v, l]) => [String(v), l]), c.search.windows.map(String));
    $("threshold").value = c.scoring.threshold; $("minret").value = +(c.scoring.min_annual_return * 100).toFixed(2);
    $("bandpct").value = c.scoring.range_band_pct; $("exit").value = c.scoring.range_exit;
    $("harvest").value = c.scoring.range_harvest_scale; $("pain").value = c.scoring.range_pain_scale;
    $("minheld").value = +(c.ranking.range_min_held / 252).toFixed(2);
    $("holdout").value = c.search.holdout_bars;
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

  let checkTimer = null;
  function changed() {
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
    else { showError(null); if (url === "/api/run") { lastV = -1; $("report").dataset.shape = ""; } }
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
      kpi("Ratios per window", (est.ratios ?? 0).toLocaleString(), `${$("kn").value} vs ${$("kd").value}`) +
      kpi("Progress", `${(s.progress * 100).toFixed(1)}%`, `<div class="progress"><div style="width:${(s.progress * 100).toFixed(1)}%"></div></div>`) +
      kpi(running ? "Time left" : "Run time", running ? fmtDur(s.eta) : fmtDur(s.elapsed), running ? `elapsed ${fmtDur(s.elapsed)}` : s.state) +
      Object.entries(P.found || {}).map(([k, v]) => kpi(k === "range" ? "Ranges" : k[0].toUpperCase() + k.slice(1) + "s", v.n,
        v.n ? `best score ${v.best.toFixed(3)}` : "none yet")).join("");
  }

  let pollTimer = null;
  async function poll(once) {
    try {
      const r = await fetch("/api/status?v=" + lastV);
      const s = await r.json();
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
        s.payload_meta = { symbols: P.panel.symbols, requested: P.panel.requested,
          found: Object.fromEntries(Object.entries(P.shapes).map(([k, v]) => [k, { n: v.items.length, best: Math.max(0, ...v.items.map((i) => i.score)) }])) };
        const y = window.scrollY;
        PS.renderReport(P, $("report"));
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
        if (el.id === "etf") { excluded.clear(); loadHoldings(); return; }
        if (el.id === "top") renderHoldings();
        changed();
      }));
    $("overlap").onchange = changed;
    installTips();
    await loadHoldings();
    poll(false);
  })();
})();
