/* Perfect Shapes results view, shared by the dashboard (live) and report.html (a saved run).
 *
 *   PS.renderReport(DATA, root, {onOpen})   DATA = a run payload (report/writer.py _payload); onOpen(item,
 *                                           shape, DATA) makes rows and chart cards clickable (Trade Lab)
 *   PS.TIPS                                 key -> html for info bubbles: <button class="info" data-tip="key">
 *                                           (or data-tip-html="..."); one tooltip, handled for the whole page
 *
 * Nexus components (segmented control, table.data, chips, verdicts, Plotly via Nexus.plotlyLayout), so it
 * follows the viewer's theme. The dashboard server reads this file on every request: edit it and refresh. */
(function () {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = (v, d = 1) => (v == null || isNaN(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(d) + "%");
  const signed = (v, d = 1) => `<span class="${v >= 0 ? "pos" : "neg"}">${pct(v, d)}</span>`;
  const CHARTS_SHOWN = 12;
  const CHIPS_MAX = 4;          // tables show ticker chips up to this many tickers per ratio, else a compact label

  // ---------------------------------------------------------------- info bubbles (whole page, delegated)
  const TIPS = {};
  (function installTooltips() {
    let tip = null, owner = null;
    const ensure = () => {
      if (!tip) { tip = document.createElement("div"); tip.className = "tip"; tip.setAttribute("role", "tooltip"); tip.hidden = true; document.body.appendChild(tip); }
      return tip;
    };
    const place = (b) => {
      const r = b.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
      if (r.bottom < 0 || r.top > vh || !b.isConnected) return hide();     // bubble scrolled away or redrawn
      let x = r.right + 10, y = r.top - 6;                                  // right of the bubble
      if (x + w > vw - 8) x = r.left - w - 10;                              // else left of it
      if (x < 8) { x = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), vw - w - 8); y = r.bottom + 8; }  // else below
      tip.style.left = x + "px"; tip.style.top = Math.min(Math.max(8, y), vh - h - 8) + "px";
    };
    const show = (b) => {
      const html = b.dataset.tipHtml || TIPS[b.dataset.tip];
      if (!html) return;
      ensure();
      if (owner && owner !== b) owner.setAttribute("aria-expanded", "false");
      owner = b; b.setAttribute("aria-expanded", "true");
      tip.innerHTML = html; tip.hidden = false; place(b);
    };
    const hide = () => { if (tip) tip.hidden = true; if (owner) owner.setAttribute("aria-expanded", "false"); owner = null; };
    const infoOf = (e) => e.target.closest && e.target.closest(".info");
    document.addEventListener("mouseover", (e) => { const b = infoOf(e); if (b) show(b); });
    document.addEventListener("mouseout", (e) => { const b = infoOf(e); if (b && b === owner && !b.contains(e.relatedTarget)) hide(); });
    document.addEventListener("focusin", (e) => { const b = infoOf(e); if (b) show(b); });
    document.addEventListener("focusout", (e) => { if (infoOf(e) === owner) hide(); });
    // a click / tap only shows (and never opens the row or card it sits in); elsewhere or Esc hides
    document.addEventListener("click", (e) => { const b = infoOf(e); if (b) { e.preventDefault(); show(b); } else hide(); }, true);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
    const follow = () => owner && place(owner);
    window.addEventListener("scroll", follow, { passive: true, capture: true });
    window.addEventListener("resize", follow);
  })();

  const NOTES = {
    weighted: {
      uptrend: "Baskets whose combined value rises along a straight line (log scale). <b>Held</b> = longest lookback whose score clears the threshold. Dashed line: fitted trend; shaded tail: holdout (the last bars, never seen by the search).",
      downtrend: "Baskets whose combined value falls along a straight line (log scale). Held = longest lookback whose score clears the threshold. Dashed line: fitted trend; shaded tail: holdout.",
      range: "Baskets whose combined value oscillates inside a flat band.",
    },
    ratio: {
      uptrend: "Basket ratios rising along a straight line (log scale): the <b>numerator steadily outperforms</b> the denominator. A falling ratio is listed flipped. Held = longest lookback whose score clears the threshold. Dashed line: fitted trend; shaded tail: holdout (the last bars, never seen by the search).",
      range: "Basket ratios oscillating inside a flat band: <b>mean-reversion candidates</b>. Below the band, buy the numerator; above it, buy the denominator.",
    },
  };
  const rangeRule = (sc) =>
    `Band: median ± the smaller half of the p${sc.range_band_pct}–p${100 - sc.range_band_pct} band over the scored span, so a one-sided spike cannot widen it. ` +
    `A trade opens when the curve leaves the band and closes at the ${sc.range_exit === "mid" ? "median" : "opposite edge"}; <b>harvest/yr</b> = trades/yr × capture per trade (in-sample, before costs). ` +
    `<b>Repeat</b> = share of the span's ${sc.range_segments} parts with a closed trade. <b>Worst against</b> = largest move against an open trade past its entry edge. ` +
    `<b>Now</b>: 0% = bottom edge, 100% = top edge; outside = an entry signal today.`;

  const METRICS = {
    annual_return: ["Annual", (v) => signed(v)],
    r2: ["R²", (v) => v.toFixed(2)],
    adverse_ratio: ["Adverse/move", (v) => v.toFixed(2)],
    harvest: ["Harvest/yr", (v) => pct(v)],
    trades_per_year: ["Trades/yr", (v) => v.toFixed(1)],
    coverage: ["Repeat", (v) => (v * 100).toFixed(0) + "%"],
    per_trade: ["Per trade", (v) => pct(v)],
    worst_against: ["Worst against", (v) => `<span class="neg">${pct(-v)}</span>`],
    swing_up: ["Bottom→top", (v) => pct(v)],
    swing_down: ["Top→bottom", (v) => pct(-v)],
    band_pos: ["Now", (v) => bandPos(v)],
    drift_ratio: ["Drift/band", (v) => v.toFixed(2)],
    height: ["Height", (v) => (v * 100).toFixed(1) + "%"],
    swings: ["Swings", (v) => v.toFixed(0)],
  };
  function bandPos(v) {
    const t = (v * 100).toFixed(0) + "%";
    if (v <= 0) return `<mark>${t} ▼ below</mark>`;
    if (v >= 1) return `<mark>${t} ▲ above</mark>`;
    return t;
  }

  const legChips = (ms, cls, withWeight) =>
    `<span class="chips">${ms.map((m) => `<span class="chip ${cls}" title="${esc(m.name)}">${esc(m.ticker)}${withWeight ? ` ${(m.weight * 100).toFixed(0)}%` : ""}</span>`).join("")}</span>`;
  const isRatio = (it) => !!(it.den_members && it.den_members.length);
  const tickerCount = (it) => it.members.length + (it.den_members ? it.den_members.length : 0);
  function basketHTML(it) {
    if (isRatio(it))
      return `<span class="ratio">${legChips(it.members, "num")}<span class="over-sign">/</span>${legChips(it.den_members, "den")}</span>`;
    return `<span class="ratio">${legChips([...it.members].sort((a, b) => b.weight - a.weight), "long", true)}</span>`;
  }
  // the members, with names, for an info bubble
  function membersTip(it) {
    const rows = (ms, cls, w) => ms.map((m) => `<div class="tip-row"><span class="chip ${cls}">${esc(m.ticker)}</span>` +
      `<span>${esc(m.name || "")}${w ? ` · ${(m.weight * 100).toFixed(0)}%` : ""}</span></div>`).join("");
    if (!isRatio(it)) return `<div class="tip-h">Basket (weights at fit start)</div>${rows(it.members, "long", true)}`;
    return `<div class="tip-h">Numerator · buy when the ratio is low</div>${rows(it.members, "num")}` +
      `<div class="tip-h">Denominator · buy when the ratio is high</div>${rows(it.den_members, "den")}`;
  }
  // compact label: (i) with every member + name on hover, then the tickers, cut with … when too long
  function basketCompact(it) {
    const list = isRatio(it) ? `${it.members.map((m) => m.ticker).join(" ")} / ${it.den_members.map((m) => m.ticker).join(" ")}`
      : it.members.map((m) => m.ticker).join(" ");
    return `<span class="ratio-compact"><button type="button" class="info" aria-label="Show the members" ` +
      `data-tip-html="${esc(membersTip(it))}">i</button><span class="tk">${esc(list)}</span></span>`;
  }
  const basketCell = (it) => (tickerCount(it) <= CHIPS_MAX ? basketHTML(it) : basketCompact(it));
  const basketText = (it) => it.den_members && it.den_members.length
    ? `(${it.members.map((m) => m.ticker).join(" + ")}) / (${it.den_members.map((m) => m.ticker).join(" + ")})`
    : it.members.map((m) => m.ticker).join(" + ");
  const namesText = (it) => {
    const f = (ms) => ms.map((m) => m.name || m.ticker).join(", ");
    return it.den_members && it.den_members.length ? `${f(it.members)} ÷ ${f(it.den_members)}` : f(it.members);
  };

  function heldText(it, ppy) {
    let t = `${(it.duration / ppy).toFixed(1)}y`;
    if (it.ref_window && it.ref_window !== it.duration) t += ` <span class="faint small">(on ${(it.ref_window / ppy).toFixed(1)}y)</span>`;
    return t;
  }

  // ---------------------------------------------------------------- chart (Plotly, theme-aware)
  // about 5 evenly spaced ticks on a log axis (Plotly labels every 1..9 step when a series spans a decade)
  function logTicks(values) {
    const lo = Math.min(...values), hi = Math.max(...values);
    if (!(lo > 0) || !(hi > lo)) return {};
    const a = Math.log(lo), b = Math.log(hi), vals = [];
    for (let i = 0; i <= 4; i++) vals.push(Math.exp(a + (b - a) * i / 4));
    return { tickvals: vals, ticktext: vals.map((v) => (v >= 10 ? v.toFixed(1) : v.toFixed(2))) };
  }
  function drawChart(el, ch, ratio) {
    if (!window.Plotly || !window.Nexus) { el.innerHTML = '<div class="empty-state small">charts need Plotly + nexus.js (offline?)</div>'; return; }
    const C = window.Nexus.colors, d = ch.dates, v = ch.values, n = v.length, ov = ch.overlay;
    const data = [];
    if (ov.kind === "band") {
      const xs = [d[ov.from], d[n - 1]];
      data.push({ x: xs, y: [ov.lo, ov.lo], mode: "lines", line: { width: 0, color: C.neutral }, hoverinfo: "skip", showlegend: false });
      data.push({ x: xs, y: [ov.hi, ov.hi], mode: "lines", fill: "tonexty", fillcolor: window.Nexus.rgba(C.neutral, 0.22),
        line: { width: 0, color: C.neutral }, name: "band", hoverinfo: "skip" });
      data.push({ x: xs, y: [ov.mid, ov.mid], mode: "lines", line: { color: C.neutral, width: 1, dash: "dot" }, name: "median", hoverinfo: "skip" });
    } else {
      data.push({ x: [d[ov.from], d[ov.to - 1]], y: [ov.y0, ov.y1], mode: "lines", line: { color: C.neutral, width: 1.5, dash: "dash" },
        name: "fitted trend", hoverinfo: "skip" });
    }
    data.push({ x: d, y: v, mode: "lines", line: { color: C.accent, width: 1.6 }, name: ratio ? "ratio" : "basket",
      hovertemplate: "%{x}<br>%{y:.3f}<extra></extra>" });
    const hold = ch.holdout_from < n ? window.Nexus.bands([{ x0: d[ch.holdout_from], x1: d[n - 1], label: "", tone: "neutral" }]) : { shapes: [], annotations: [] };
    const layout = window.Nexus.plotlyLayout({
      margin: { l: 46, r: 10, t: 6, b: 30 }, showlegend: false, hovermode: "x unified",
      yaxis: Object.assign({ type: ch.log ? "log" : "linear", tickformat: ".2f", nticks: 5 }, ch.log ? logTicks(v) : {}), xaxis: { nticks: 5 },
      shapes: hold.shapes, annotations: hold.annotations,
    });
    window.Plotly.react(el, data, layout, Object.assign({}, window.Nexus.plotlyConfig, { displayModeBar: false }));
  }

  // ---------------------------------------------------------------- one shape: note, table, charts
  function renderShape(DATA, shape, host, state) {
    const S = DATA.shapes[shape], ratio = DATA.search.mode === "ratio", ppy = DATA.scoring.periods_per_year;
    const mk = S.metric_order.filter((k) => METRICS[k]);
    const note = (NOTES[ratio ? "ratio" : "weighted"][shape] || "") + (shape === "range" ? " " + rangeRule(DATA.scoring) : "");
    let html = `<p class="muted small shape-note">${note}</p>`;
    if (!S.items.length) {
      html += `<div class="panel empty-state">No ${ratio ? "ratio" : "basket"} holds this shape yet` +
        `${DATA.partial ? " — more lookback windows are still to come." : "."}</div>`;
      host.innerHTML = html;
      return;
    }
    html += `<div class="table-wrap"><table class="data ps" data-list><thead><tr><th>#</th>` +
      `<th data-list="title">${ratio ? "Ratio (numerator / denominator)" : "Basket (weights at fit start)"}</th>` +
      `<th class="num" data-list="subtitle" data-list-prefix="Held">Held</th><th class="num" data-list="value">Score</th>` +
      mk.map((k) => `<th class="num">${METRICS[k][0]}</th>`).join("") +
      `<th class="num">Holdout</th><th data-list="note">Status</th></tr></thead><tbody>`;
    for (const it of S.items) {
      html += `<tr data-i="${S.items.indexOf(it)}" title="${esc(namesText(it))}"><td class="rank">${it.rank}</td><td>${basketCell(it)}</td><td class="num">${heldText(it, ppy)}</td>` +
        `<td class="num"><b>${it.score.toFixed(3)}</b></td>` +
        mk.map((k) => `<td class="num">${it.metrics[k] == null ? "–" : METRICS[k][1](it.metrics[k])}</td>`).join("") +
        `<td class="num">${signed(it.holdout_return)}</td>` +
        `<td>${it.alive ? '<span class="verdict under">Alive</span>' : '<span class="verdict over">Broken</span>'}</td></tr>`;
    }
    html += `</tbody></table></div>`;
    const shown = state.all ? S.items.length : Math.min(CHARTS_SHOWN, S.items.length);
    html += `<div class="chart-grid">` + S.items.slice(0, shown).map((it, i) => {
      const sub = shape === "range"
        ? `harvest ${pct(it.metrics.harvest)}/yr · ${it.metrics.trades_per_year.toFixed(1)} trades/yr · repeat ${(it.metrics.coverage * 100).toFixed(0)}% · band ${pct(it.metrics.swing_up)} · now ${bandPos(it.metrics.band_pos)}`
        : `${pct(it.metrics.annual_return)}/yr · R² ${it.metrics.r2.toFixed(2)}`;
      return `<div class="panel chart-panel" data-i="${i}"><div class="chart-head"><h3><span class="rank">#${it.rank}</span>${basketCompact(it)}</h3>` +
        `${it.alive ? '<span class="verdict under">Alive</span>' : '<span class="verdict over">Broken</span>'}</div>` +
        `<div class="chart-sub">held ${heldText(it, ppy)} · score ${it.score.toFixed(3)} · ${sub} · holdout ${signed(it.holdout_return)}</div>` +
        `<div class="chart" data-i="${i}"></div></div>`;
    }).join("") + `</div>`;
    if (S.items.length > CHARTS_SHOWN)
      html += `<div class="more-row"><button class="btn sm" data-more>${state.all ? "Show the top " + CHARTS_SHOWN + " charts" : "Show all " + S.items.length + " charts"}</button></div>`;
    host.innerHTML = html;
    host.querySelectorAll(".chart[data-i]").forEach((el) => drawChart(el, S.items[+el.dataset.i].chart, ratio));
    const more = host.querySelector("[data-more]");
    if (more) more.onclick = () => { state.all = !state.all; renderShape(DATA, shape, host, state); };
    if (state.onOpen) {
      host.querySelectorAll("tr[data-i], .chart-panel[data-i]").forEach((el) => {
        el.classList.add("openable");
        el.title = "Open in the Trade Lab";
        el.addEventListener("click", (e) => {
          if (e.target.closest(".info, a, button, .modebar")) return;
          state.onOpen(S.items[+el.dataset.i], shape, DATA);
        });
      });
    }
  }

  // ---------------------------------------------------------------- whole report
  function renderReport(DATA, root, opts = {}) {
    const shapes = Object.keys(DATA.shapes);
    let current = root.dataset.shape;
    if (!current) { try { current = localStorage.getItem("ps-shape") || ""; } catch (e) { current = ""; } }
    if (!DATA.shapes[current]) current = shapes[0];
    const P = DATA.panel, ratio = DATA.search.mode === "ratio";
    const desc = ratio ? `${DATA.ratio.k} vs ${DATA.ratio.k} equal-weight ratios` :
      `max ${DATA.search.max_assets} assets, ${DATA.search.long_only ? "long-only" : "long/short"}`;
    root.innerHTML =
      `<div class="results-head"><div class="segmented" role="group" aria-label="Shape">` +
      shapes.map((s) => `<button class="btn" data-shape="${s}" aria-pressed="${s === current}">${s} · ${DATA.shapes[s].items.length}</button>`).join("") +
      `</div><span class="muted small">${P.symbols} of ${P.requested} instruments · ${P.start} → ${P.end} · fit end ${P.fit_end} · ${desc} · threshold ${DATA.scoring.threshold}` +
      `${DATA.partial ? ' · <span class="badge past">partial</span>' : ""}</span></div><div data-host></div>`;
    const host = root.querySelector("[data-host]");
    const state = { all: false, onOpen: opts.onOpen || null };
    const show = (s) => {
      root.dataset.shape = s;
      try { localStorage.setItem("ps-shape", s); } catch (e) { /* private mode */ }
      root.querySelectorAll("[data-shape]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.shape === s));
      state.all = false;
      renderShape(DATA, s, host, state);
    };
    root.querySelectorAll("[data-shape]").forEach((b) => (b.onclick = () => show(b.dataset.shape)));
    if (current) show(current);
  }

  // ---------------------------------------------------------------- Trade Lab: backtest one result in a new window
  function openTradeLab(it, shape, P) {
    const ch = it.chart, ov = ch.overlay;
    const q = new URLSearchParams({
      num: it.members.map((m) => m.ticker).join(","),
      den: (it.den_members || []).map((m) => m.ticker).join(","),
      shape,
      fit_from: ch.dates[ov.from],                  // start of the window the scan scored (and fitted the band on)
      fit_end: P.panel.fit_end,                     // last bar the scan saw; after it: holdout
      band_pct: P.scoring.range_band_pct, exit: P.scoring.range_exit,
      lists: (P.universe_lists || []).join(","), run: P.name, rank: it.rank,
    });
    window.open("/trade.html?" + q.toString(), "_blank");
  }
  // a saved report.html opens the Trade Lab only when the dashboard server serves it (not from file://)
  const canOpenLab = () => /^https?:$/.test(location.protocol);

  window.PS = { renderReport, basketText, membersTip, pct, esc, TIPS, openTradeLab, canOpenLab };
})();
