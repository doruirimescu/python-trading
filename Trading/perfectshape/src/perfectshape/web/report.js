/* Perfect Shapes results view, shared by the dashboard (live) and report.html (a saved run).
 *
 *   PS.renderReport(DATA, root)   DATA = a run payload (report/writer.py _payload)
 *
 * Nexus components (segmented control, table.data, chips, verdicts, Plotly via Nexus.plotlyLayout), so it
 * follows the viewer's theme. The dashboard server reads this file on every request: edit it and refresh. */
(function () {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = (v, d = 1) => (v == null || isNaN(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(d) + "%");
  const signed = (v, d = 1) => `<span class="${v >= 0 ? "pos" : "neg"}">${pct(v, d)}</span>`;
  const CHARTS_SHOWN = 12;

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
  function basketHTML(it) {
    if (it.den_members && it.den_members.length)
      return `<span class="ratio">${legChips(it.members, "num")}<span class="over-sign">/</span>${legChips(it.den_members, "den")}</span>`;
    return `<span class="ratio">${legChips([...it.members].sort((a, b) => b.weight - a.weight), "long", true)}</span>`;
  }
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
      yaxis: { type: ch.log ? "log" : "linear", tickformat: ".2f", nticks: 5 }, xaxis: { nticks: 5 },
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
      html += `<tr title="${esc(namesText(it))}"><td class="rank">${it.rank}</td><td>${basketHTML(it)}</td><td class="num">${heldText(it, ppy)}</td>` +
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
      return `<div class="panel chart-panel"><div class="chart-head"><h3><span class="rank">#${it.rank}</span>${basketHTML(it)}</h3>` +
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
  }

  // ---------------------------------------------------------------- whole report
  function renderReport(DATA, root) {
    const shapes = Object.keys(DATA.shapes);
    let current = root.dataset.shape;
    if (!current) { try { current = localStorage.getItem("ps-shape") || ""; } catch (e) { current = ""; } }
    if (!DATA.shapes[current]) current = shapes[0];
    const P = DATA.panel, ratio = DATA.search.mode === "ratio";
    const desc = ratio ? `${DATA.ratio.k_num} vs ${DATA.ratio.k_den} equal-weight ratios` :
      `max ${DATA.search.max_assets} assets, ${DATA.search.long_only ? "long-only" : "long/short"}`;
    root.innerHTML =
      `<div class="results-head"><div class="segmented" role="group" aria-label="Shape">` +
      shapes.map((s) => `<button class="btn" data-shape="${s}" aria-pressed="${s === current}">${s} · ${DATA.shapes[s].items.length}</button>`).join("") +
      `</div><span class="muted small">${P.symbols} of ${P.requested} instruments · ${P.start} → ${P.end} · fit end ${P.fit_end} · ${desc} · threshold ${DATA.scoring.threshold}` +
      `${DATA.partial ? ' · <span class="badge past">partial</span>' : ""}</span></div><div data-host></div>`;
    const host = root.querySelector("[data-host]");
    const state = { all: false };
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

  window.PS = { renderReport, basketText, pct };
})();
