/* Perfect Shapes Trade Lab: backtest entry / exit rules on one basket ratio, in the browser.
 *
 * Opened from a dashboard result (/trade.html?num=A,B&den=C,D&shape=range&fit_from=...&fit_end=...).
 * Prices come from /api/series (the scan's price cache, plus SPY). Everything else runs here, so changing a
 * rule recomputes at once. The server reads this file on every request: edit it and refresh.
 *
 * Model
 *   baskets   N_t = mean_i P_i,t / P_i,s (numerator), D_t likewise; equal weight at the period start s, held as
 *             fixed shares (no rebalancing), exactly as the scan values them. Ratio R = N / D, Y = log R.
 *   signals   decided on the close of day t from data up to t; filled at the next close (default) or the same.
 *             "Numerator up" (+1) = the trade gains when R rises; "denominator up" (-1) = when R falls.
 *   positions pair: long one basket and short the other, each leg = equity at entry x leverage;
 *             rotation: hold the basket expected to outperform, all equity, long only; numerator only: +1 trades.
 *   costs     bps of each leg's notional, on entry and on exit.
 */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = PS.esc;
  const P = new URLSearchParams(location.search);
  const PPY = 252;

  // ---------------------------------------------------------------- info bubbles
  Object.assign(PS.TIPS, {
    period: "The backtest runs from <b>From</b> to <b>To</b>. Both baskets are equal weight at the start date and then held as fixed shares, like the scan values them. Defaults: the start of the window the scan scored, to the last bar.",
    strategy: "<b>Band</b>: trade the ratio back into its band. <b>Z-score</b>: the same idea with a rolling mean and standard deviation. <b>Moving-average crossover</b>: follow the trend of the ratio. <b>Buy &amp; hold</b>: own the ratio for the whole period.",
    band_src: "<b>Scan window</b>: the band the dashboard showed, fitted on the window the scan scored (in-sample: it knew the future of that window). <b>Rolling</b>: at each day, the band of the previous N days only, an honest out-of-sample test.",
    band_lb: "Days of history used for the rolling band.",
    band_pct: "Band = median ± the smaller half of the p to (100 − p) percentile range of the ratio. 10 ≈ the 10th to 90th percentile.",
    entry_buf: "Wait until the ratio is this much <b>beyond</b> the band edge before entering (0 = enter as soon as it leaves the band).",
    exit_frac: "Where a trade closes, as a share of the band from its entry edge: <b>50</b> = the median, <b>100</b> = the opposite edge, 25 = a quarter of the way back.",
    z_lb: "Days used for the rolling mean and standard deviation of the log ratio.",
    z_in: "Enter when the ratio is at least this many standard deviations from its rolling mean (below: numerator up; above: denominator up).",
    z_out: "Exit when the z-score has come back within this distance of 0 (0 = exit at the mean).",
    z_stop: "Give up when the ratio runs this many standard deviations away (0 = no z stop).",
    ma_fast: "Days in the fast moving average of the ratio (1 = the ratio itself).",
    ma_slow: "Days in the slow moving average. Numerator up while fast > slow; denominator up while fast < slow (if allowed).",
    ma_buf: "The fast average must clear the slow one by this much to enter, which avoids flip-flopping around the cross.",
    dirs: "Which side to trade: <b>numerator up</b> (the ratio rises) and/or <b>denominator up</b> (the ratio falls).",
    execution: "How a signal becomes a position, what it costs, and when it is filled.",
    mode: "<b>Long/short pair</b>: buy the basket expected to outperform and short the other, market neutral. <b>Rotation</b>: put all the money in the basket expected to outperform, no shorting (cash when flat). <b>Numerator only</b>: only buy the numerator basket, when the ratio is expected to rise.",
    leg: "Pair only: each leg's size as a multiple of equity. 1 = $10k long and $10k short on $10k (2× gross).",
    capital: "Starting portfolio value. The S&amp;P 500 comparison invests the same amount in SPY.",
    bps: "Trading costs (commission + spread + slippage) per side, in basis points of each leg traded. 5 bps = 0.05%.",
    lag: "<b>Next close</b>: the signal of day t is traded at the close of day t+1 (no look-ahead). <b>Same close</b>: traded at the close that triggered it (optimistic).",
    risk: "Exits that override the strategy, measured on the trade's own return.",
    stop: "Close a trade that has lost this much. After a stop the same side is not re-entered until its signal resets.",
    tp: "Close a trade that has made this much.",
    maxdays: "Close a trade after this many trading days.",
  });
  function addInfo(el, key) {
    if (!PS.TIPS[key] || el.querySelector(":scope > .info")) return;
    const b = document.createElement("button");
    b.type = "button"; b.className = "info"; b.textContent = "i"; b.dataset.tip = key;
    b.setAttribute("aria-label", "About this setting");
    el.appendChild(b);
  }

  // ---------------------------------------------------------------- numbers
  const pct = (v, d = 1) => (v == null || !isFinite(v) ? "–" : (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(d) + "%");
  const signed = (v, d = 1) => (v == null || !isFinite(v) ? "–" : `<span class="${v >= 0 ? "pos" : "neg"}">${pct(v, d)}</span>`);
  const money = (v) => (v == null || !isFinite(v) ? "–" : (v < 0 ? "−$" : "$") + Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 }));
  const num = (v, d = 2) => (v == null || !isFinite(v) ? "–" : v.toFixed(d));

  function percentile(sorted, q) {               // numpy's default (linear interpolation)
    const pos = (sorted.length - 1) * q / 100, lo = Math.floor(pos), hi = Math.ceil(pos);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
  }
  function symBand(values, q) {                    // median ± the smaller half of the [q, 100-q] band
    const s = values.filter(Number.isFinite).sort((a, b) => a - b);
    if (s.length < 5) return null;
    const lo = percentile(s, q), mid = percentile(s, 50), hi = percentile(s, 100 - q);
    const h = Math.min(mid - lo, hi - mid);
    return [mid - h, mid, mid + h];
  }

  // ---------------------------------------------------------------- data
  let S = null;            // series from the server + derived arrays

  async function load() {
    const q = new URLSearchParams({ num: P.get("num") || "", den: P.get("den") || "", lists: P.get("lists") || "" });
    const r = await fetch("/api/series?" + q);
    const j = await r.json();
    if (!r.ok || j.error) throw new Error(j.error || r.statusText);
    S = j;
    S.idx = Object.fromEntries(S.dates.map((d, i) => [d, i]));
  }

  const firstIndexOnOrAfter = (date) => { const i = S.dates.findIndex((d) => d >= date); return i < 0 ? S.dates.length - 1 : i; };
  const lastIndexOnOrBefore = (date) => { for (let i = S.dates.length - 1; i >= 0; i--) if (S.dates[i] <= date) return i; return 0; };

  /** basket values normalised at index s (fixed shares), defined wherever every member has a price */
  function basket(tickers, s) {
    const T = S.dates.length, out = new Float64Array(T).fill(NaN);
    const cols = tickers.map((t) => S.close[t]);
    for (let t = 0; t < T; t++) {
      let acc = 0, ok = true;
      for (const c of cols) { if (c[t] == null || c[s] == null) { ok = false; break; } acc += c[t] / c[s]; }
      if (ok) out[t] = acc / cols.length;
    }
    return out;
  }

  // ---------------------------------------------------------------- settings
  const SETTINGS = ["from", "to", "strategy", "band_src", "band_lb", "band_pct", "entry_buf", "exit_frac", "z_lb", "z_in",
    "z_out", "z_stop", "ma_fast", "ma_slow", "ma_buf", "dirs", "mode", "leg", "capital", "bps", "lag", "stop", "tp", "maxdays"];
  function defaults() {
    const range = (P.get("shape") || "range") === "range";
    return {
      from: P.get("fit_from") || S.dates[0], to: S.dates[S.dates.length - 1],
      strategy: range ? "band" : "hold", band_src: "fixed", band_lb: 252, band_pct: +(P.get("band_pct") || 10),
      entry_buf: 0, exit_frac: P.get("exit") === "opposite" ? 100 : 50,
      z_lb: 126, z_in: 2, z_out: 0, z_stop: 0, ma_fast: 20, ma_slow: 100, ma_buf: 0,
      dirs: "both", mode: "pair", leg: 1, capital: 10000, bps: 5, lag: "1", stop: 0, tp: 0, maxdays: 0,
    };
  }
  // any setting can also come from the URL (&strategy=zscore&z_in=2.5 ...): shareable, bookmarkable backtests
  function withUrl(o) {
    for (const k of SETTINGS) if (P.has(k)) o[k] = typeof o[k] === "number" ? +P.get(k) : P.get(k);
    return o;
  }
  function readSettings() {
    const o = {};
    for (const k of SETTINGS) { const el = $(k); o[k] = el.type === "number" ? +el.value : el.value; }
    return o;
  }
  function applySettings(o) { for (const k of SETTINGS) if (o[k] != null) $(k).value = o[k]; }
  function syncVisibility(o) {
    document.querySelectorAll("[data-for]").forEach((el) => (el.hidden = el.dataset.for !== o.strategy));
    document.querySelectorAll("[data-not-for]").forEach((el) => (el.hidden = el.dataset.notFor === o.strategy));
    document.querySelectorAll("[data-for-src]").forEach((el) => (el.hidden = el.dataset.forSrc !== o.band_src));
    document.querySelectorAll("[data-for-mode]").forEach((el) => (el.hidden = el.dataset.forMode !== o.mode));
  }

  // ---------------------------------------------------------------- indicators (arrays over all dates)
  function indicators(o, Y, s, e) {
    const T = Y.length, lo = new Float64Array(T).fill(NaN), mid = new Float64Array(T).fill(NaN), hi = new Float64Array(T).fill(NaN);
    const z = new Float64Array(T).fill(NaN), fast = new Float64Array(T).fill(NaN), slow = new Float64Array(T).fill(NaN);
    let calib = null;
    if (o.strategy === "band") {
      if (o.band_src === "fixed") {
        // the scan's band: fitted on the window it scored, [fit_from, fit_end] (clipped to the data)
        const c0 = firstIndexOnOrAfter(P.get("fit_from") || S.dates[s]);
        const c1 = lastIndexOnOrBefore(P.get("fit_end") || S.dates[e]);
        const b = symBand(Array.from(Y.slice(c0, c1 + 1)), o.band_pct);
        if (b) for (let t = 0; t < T; t++) [lo[t], mid[t], hi[t]] = b;
        calib = [c0, c1];
      } else {
        const L = Math.max(20, Math.round(o.band_lb));
        for (let t = L; t < T; t++) {
          if (t < s - 1) continue;
          const b = symBand(Array.from(Y.slice(t - L + 1, t + 1)), o.band_pct);
          if (b) [lo[t], mid[t], hi[t]] = b;
        }
      }
    } else if (o.strategy === "zscore") {
      const L = Math.max(10, Math.round(o.z_lb));
      for (let t = L - 1; t < T; t++) {
        if (t < s - 1) continue;
        let m = 0, v = 0, n = 0;
        for (let i = t - L + 1; i <= t; i++) if (Number.isFinite(Y[i])) { m += Y[i]; n++; }
        if (n < L * 0.8) continue;
        m /= n;
        for (let i = t - L + 1; i <= t; i++) if (Number.isFinite(Y[i])) v += (Y[i] - m) ** 2;
        const sd = Math.sqrt(v / n);
        if (sd > 0) { z[t] = (Y[t] - m) / sd; mid[t] = m; lo[t] = m - o.z_in * sd; hi[t] = m + o.z_in * sd; }
      }
    } else if (o.strategy === "ma") {
      const sma = (L, out) => {
        L = Math.max(1, Math.round(L));
        let acc = 0, n = 0;
        for (let t = 0; t < T; t++) {
          if (Number.isFinite(Y[t])) { acc += Y[t]; n++; }
          if (t >= L && Number.isFinite(Y[t - L])) { acc -= Y[t - L]; n--; }
          if (n === L) out[t] = acc / L;
        }
      };
      sma(o.ma_fast, fast); sma(o.ma_slow, slow);
    }
    return { lo, mid, hi, z, fast, slow, calib };
  }

  // ---------------------------------------------------------------- the backtest
  function backtest(o) {
    const s = firstIndexOnOrAfter(o.from), e = lastIndexOnOrBefore(o.to);
    if (e - s < 20) throw new Error("the period is too short (fewer than 20 trading days)");
    const late = [...S.num, ...S.den].filter((t) => S.close[t][s] == null);
    if (late.length) {
      const first = Math.max(...late.map((t) => S.close[t].findIndex((v) => v != null)));
      throw new Error(`${late.join(", ")} ${late.length > 1 ? "have" : "has"} no price on ${S.dates[s]}: ` +
        `start on ${S.dates[first]} or later (the first day every member trades).`);
    }
    const N = basket(S.num, s), D = basket(S.den, s);
    const T = S.dates.length, Y = new Float64Array(T);
    for (let t = 0; t < T; t++) Y[t] = Math.log(N[t] / D[t]);
    const ind = indicators(o, Y, s, e);
    const allowLong = o.dirs !== "short", allowShort = o.dirs !== "long" && o.mode !== "longnum";
    const lag = +o.lag, bps = o.bps / 1e4, leg = o.mode === "pair" ? o.leg : 1;
    const legs = o.mode === "pair" ? 2 : 1;
    const buf = o.entry_buf / 100, f = o.exit_frac / 100;

    let cash = o.capital;            // equity when flat
    let pos = null;                  // {side, t0, N0, D0, E, equityBefore}
    let pending = null;              // {action: "open"|"close"|"reverse", side, reason}
    let blocked = { 1: false, "-1": false };
    const eq = new Float64Array(T).fill(NaN);
    const trades = [];

    const value = (t) => {
      if (!pos) return cash;
      const n = N[t] / pos.N0, d = D[t] / pos.D0;
      if (o.mode === "pair") return pos.E * (1 + pos.side * leg * (n - d));
      return pos.E * (pos.side > 0 ? n : d);
    };
    const open = (t, side, reason) => {
      const E0 = cash, E = E0 * (1 - bps * legs * leg);
      pos = { side, t0: t, N0: N[t], D0: D[t], E, equityBefore: E0, reason };
    };
    const close = (t, reason) => {
      const v = value(t), gross = o.mode === "pair" ? pos.E * leg * (N[t] / pos.N0 + D[t] / pos.D0) : v;
      cash = v - bps * gross;              // exit costs on the notional of the legs closed
      trades.push({ side: pos.side, t0: pos.t0, t1: t, r0: Math.exp(Y[pos.t0]), r1: Math.exp(Y[t]),
        ret: cash / pos.equityBefore - 1, pnl: cash - pos.equityBefore, reason, entryReason: pos.reason, equity: cash });
      pos = null;
    };
    const execute = (t, act) => {
      if (act.action === "close" || act.action === "reverse") close(t, act.reason);
      if (act.action === "open" || act.action === "reverse") open(t, act.side, act.entry || act.reason);
    };

    // entry signal of day t: +1 numerator up, -1 denominator up, 0 none
    const entrySignal = (t) => {
      const y = Y[t];
      if (!Number.isFinite(y)) return 0;
      if (o.strategy === "hold") return t === s ? 1 : 0;
      if (o.strategy === "band") {
        if (!Number.isFinite(ind.lo[t])) return 0;
        if (y <= ind.lo[t] + Math.log(1 - Math.min(buf, 0.99))) return 1;
        if (y >= ind.hi[t] + Math.log(1 + buf)) return -1;
        return 0;
      }
      if (o.strategy === "zscore") {
        if (!Number.isFinite(ind.z[t])) return 0;
        if (ind.z[t] <= -o.z_in) return 1;
        if (ind.z[t] >= o.z_in) return -1;
        return 0;
      }
      if (!Number.isFinite(ind.fast[t]) || !Number.isFinite(ind.slow[t])) return 0;
      const gap = ind.fast[t] - ind.slow[t], b = Math.log(1 + o.ma_buf / 100);
      return gap > b ? 1 : gap < -b ? -1 : 0;
    };
    // exit signal of day t for the open position (reason string or null)
    const exitSignal = (t) => {
      const y = Y[t], side = pos.side, r = value(t) / pos.equityBefore - 1, held = t - pos.t0;
      if (o.stop > 0 && r <= -o.stop / 100) return "stop loss";
      if (o.tp > 0 && r >= o.tp / 100) return "take profit";
      if (o.maxdays > 0 && held >= o.maxdays) return "max days";
      if (o.strategy === "band" && Number.isFinite(ind.lo[t])) {
        const w = ind.hi[t] - ind.lo[t];
        if (side > 0 && y >= ind.lo[t] + f * w) return f >= 0.999 ? "opposite edge" : f === 0.5 ? "median" : "target";
        if (side < 0 && y <= ind.hi[t] - f * w) return f >= 0.999 ? "opposite edge" : f === 0.5 ? "median" : "target";
      } else if (o.strategy === "zscore" && Number.isFinite(ind.z[t])) {
        if (o.z_stop > 0 && Math.abs(ind.z[t]) >= o.z_stop && Math.sign(ind.z[t]) === -side) return "z stop";
        if (side > 0 && ind.z[t] >= -o.z_out) return "z exit";
        if (side < 0 && ind.z[t] <= o.z_out) return "z exit";
      } else if (o.strategy === "ma" && Number.isFinite(ind.fast[t])) {
        const gap = ind.fast[t] - ind.slow[t];
        if (side > 0 && gap < 0) return "cross down";
        if (side < 0 && gap > 0) return "cross up";
      }
      return null;
    };

    for (let t = s; t <= e; t++) {
      if (pending) { execute(t, pending); pending = null; }
      eq[t] = value(t);
      if (t === e) break;
      // decide on today's close
      const sig = entrySignal(t);
      for (const side of [1, -1]) if (sig !== side) blocked[side] = false;     // a signal that resets unblocks
      let act = null;
      if (pos) {
        const why = exitSignal(t);
        if (why) {
          if (why === "stop loss" || why === "z stop") blocked[pos.side] = true;
          const again = sig !== 0 && sig !== pos.side && ((sig > 0 && allowLong) || (sig < 0 && allowShort)) && !blocked[sig];
          act = again ? { action: "reverse", side: sig, reason: why, entry: "signal" } : { action: "close", reason: why };
        }
      } else if (sig !== 0 && ((sig > 0 && allowLong) || (sig < 0 && allowShort)) && !blocked[sig]) {
        act = { action: "open", side: sig, reason: "signal" };
      }
      if (act) {
        if (lag === 0) { execute(t, act); eq[t] = value(t); } else pending = act;
      }
    }
    if (pos) { close(e, "end of period"); eq[e] = cash; }
    let exposure = 0;
    for (const tr of trades) exposure += tr.t1 - tr.t0;
    return { s, e, N, D, Y, ind, eq, trades, exposure: exposure / Math.max(e - s, 1) };
  }

  // ---------------------------------------------------------------- statistics
  function stats(eq, s, e) {
    const v = Array.from(eq.slice(s, e + 1)), rets = [];
    for (let i = 1; i < v.length; i++) rets.push(v[i] / v[i - 1] - 1);
    const years = (v.length - 1) / PPY;
    const total = v[v.length - 1] / v[0] - 1;
    const mean = rets.reduce((a, b) => a + b, 0) / Math.max(rets.length, 1);
    const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(rets.length - 1, 1));
    const down = Math.sqrt(rets.reduce((a, b) => a + Math.min(b, 0) ** 2, 0) / Math.max(rets.length - 1, 1));
    let peak = v[0], mdd = 0;
    const dd = v.map((x) => { peak = Math.max(peak, x); const d = x / peak - 1; mdd = Math.min(mdd, d); return d; });
    const cagr = Math.pow(v[v.length - 1] / v[0], 1 / Math.max(years, 1e-9)) - 1;
    return { total, cagr, vol: sd * Math.sqrt(PPY), sharpe: sd > 0 ? (mean / sd) * Math.sqrt(PPY) : NaN,
      sortino: down > 0 ? (mean / down) * Math.sqrt(PPY) : NaN, mdd, calmar: mdd < 0 ? cagr / -mdd : NaN, dd, rets, final: v[v.length - 1] };
  }
  function betaCorr(a, b) {
    const n = Math.min(a.length, b.length), ma = a.reduce((x, y) => x + y, 0) / n, mb = b.reduce((x, y) => x + y, 0) / n;
    let cov = 0, va = 0, vb = 0;
    for (let i = 0; i < n; i++) { cov += (a[i] - ma) * (b[i] - mb); va += (a[i] - ma) ** 2; vb += (b[i] - mb) ** 2; }
    return { beta: vb > 0 ? cov / vb : NaN, corr: va > 0 && vb > 0 ? cov / Math.sqrt(va * vb) : NaN };
  }

  // ---------------------------------------------------------------- render
  const sideLabel = (s) => (s > 0 ? "Numerator up" : "Denominator up");
  const what = (o, side) => o.mode === "pair" ? (side > 0 ? "long numerator / short denominator" : "long denominator / short numerator")
    : side > 0 ? "hold numerator" : "hold denominator";

  function render(o) {
    syncVisibility(o);
    let bt;
    try { bt = backtest(o); $("error").hidden = true; } catch (err) { $("error").hidden = false; $("error").textContent = err.message; return; }
    const { s, e, eq, trades } = bt, C = window.Nexus ? Nexus.colors : {};
    const dates = S.dates.slice(s, e + 1);
    const st = stats(eq, s, e);
    // benchmarks: SPY and all members equal weight, same capital, same days
    const B = S.bench ? S.close[S.bench] : null;
    const spyEq = new Float64Array(S.dates.length).fill(NaN), ewEq = new Float64Array(S.dates.length).fill(NaN);
    for (let t = s; t <= e; t++) {
      if (B && B[t] != null && B[s] != null) spyEq[t] = o.capital * B[t] / B[s];
      ewEq[t] = o.capital * (bt.N[t] * S.num.length + bt.D[t] * S.den.length) / (S.num.length + S.den.length);
    }
    const spy = B ? stats(spyEq, s, e) : null, ew = stats(ewEq, s, e);
    const bc = spy ? betaCorr(st.rets, spy.rets) : { beta: NaN, corr: NaN };
    const wins = trades.filter((t) => t.ret > 0), losses = trades.filter((t) => t.ret <= 0);
    const grossWin = wins.reduce((a, t) => a + t.pnl, 0), grossLoss = -losses.reduce((a, t) => a + t.pnl, 0);
    const avgDays = trades.length ? trades.reduce((a, t) => a + t.t1 - t.t0, 0) / trades.length : NaN;

    // KPIs
    const kpi = (label, value, sub) => `<div class="panel kpi"><div class="label">${label}</div><div class="value sm">${value}</div><div class="sub">${sub}</div></div>`;
    $("kpis").innerHTML =
      kpi("Final value", money(st.final), `from ${money(o.capital)} · SPY ${spy ? money(spy.final) : "–"}`) +
      kpi("CAGR", signed(st.cagr), `SPY ${spy ? pct(spy.cagr) : "–"} · ${dates[0]} → ${dates[dates.length - 1]}`) +
      kpi("Max drawdown", `<span class="neg">${pct(st.mdd)}</span>`, `SPY ${spy ? pct(spy.mdd) : "–"}`) +
      kpi("Sharpe", num(st.sharpe), `SPY ${spy ? num(spy.sharpe) : "–"} · Sortino ${num(st.sortino)}`) +
      kpi("Trades", trades.length, trades.length ? `${(wins.length / trades.length * 100).toFixed(0)}% winners · ${num(avgDays, 0)} days avg` : "no trade triggered") +
      kpi("In the market", (bt.exposure * 100).toFixed(0) + "%", `beta to SPY ${num(bc.beta)} · corr ${num(bc.corr)}`);

    if (!window.Plotly || !window.Nexus) return;
    const cfg = Object.assign({}, Nexus.plotlyConfig, { displaylogo: false });
    // ratio + rules + trades
    const R = dates.map((_, i) => Math.exp(bt.Y[s + i]));
    const line = (arr, name, extra) => ({ x: dates, y: Array.from(arr.slice(s, e + 1)).map((v) => (Number.isFinite(v) ? Math.exp(v) : null)),
      mode: "lines", name, hoverinfo: "skip", ...extra });
    const data = [];
    if (o.strategy === "band" || o.strategy === "zscore") {
      data.push(line(bt.ind.lo, "band low", { line: { width: 0, color: C.neutral }, showlegend: false }));
      data.push(line(bt.ind.hi, "band high", { fill: "tonexty", fillcolor: Nexus.rgba(C.neutral, 0.2), line: { width: 0, color: C.neutral } }));
      data.push(line(bt.ind.mid, o.strategy === "band" ? "median" : "rolling mean", { line: { width: 1, color: C.neutral, dash: "dot" } }));
    } else if (o.strategy === "ma") {
      data.push(line(bt.ind.fast, `fast ${o.ma_fast}d`, { line: { width: 1.2, color: C.series2 } }));
      data.push(line(bt.ind.slow, `slow ${o.ma_slow}d`, { line: { width: 1.2, color: C.neutral, dash: "dash" } }));
    }
    data.push({ x: dates, y: R, mode: "lines", name: "ratio", line: { color: C.accent, width: 1.6 }, hovertemplate: "%{x}<br>ratio %{y:.4f}<extra></extra>" });
    const mark = (list, name, symbol, color) => ({ x: list.map((p) => S.dates[p.t]), y: list.map((p) => Math.exp(bt.Y[p.t])), mode: "markers", name,
      marker: { symbol, size: 12, color, line: { width: 1, color: C.surface } }, text: list.map((p) => p.text), hovertemplate: "%{x}<br>%{text}<extra></extra>" });
    data.push(mark(trades.filter((t) => t.side > 0).map((t) => ({ t: t.t0, text: `enter: ${what(o, 1)}` })), "enter: numerator up", "triangle-up", C.positive));
    data.push(mark(trades.filter((t) => t.side < 0).map((t) => ({ t: t.t0, text: `enter: ${what(o, -1)}` })), "enter: denominator up", "triangle-down", C.series2));
    data.push(mark(trades.map((t) => ({ t: t.t1, text: `exit (${t.reason}): ${pct(t.ret)}` })), "exit", "x", C.text));
    const eras = [];
    if (bt.ind.calib) eras.push({ x0: S.dates[Math.max(bt.ind.calib[0], s)], x1: S.dates[Math.min(bt.ind.calib[1], e)], label: "band fitted", tone: "accent" });
    const fe = P.get("fit_end");
    if (fe && fe < S.dates[e]) eras.push({ x0: fe, x1: S.dates[e], label: "after the scan (holdout)", tone: "neutral" });
    const bands = Nexus.bands(eras);
    Plotly.react("c-ratio", data, Nexus.plotlyLayout({ hovermode: "closest", showlegend: false, margin: { l: 56, r: 14, t: 10, b: 36 },
      yaxis: { type: "log", tickformat: ".3f" }, shapes: bands.shapes, annotations: bands.annotations }), cfg);
    // equity
    const eqLine = (arr, name, color, w) => ({ x: dates, y: Array.from(arr.slice(s, e + 1)), mode: "lines", name, line: { color, width: w },
      hovertemplate: `%{x}<br>${name} %{y:$,.0f}<extra></extra>` });
    const eqData = [eqLine(eq, "strategy", C.accent, 2), eqLine(ewEq, "all members", C.series2, 1.2)];
    if (spy) eqData.splice(1, 0, eqLine(spyEq, "SPY", C.neutral, 1.4));
    Plotly.react("c-equity", eqData, Nexus.plotlyLayout({ hovermode: "x unified", showlegend: false, margin: { l: 64, r: 14, t: 10, b: 36 },
      yaxis: { tickprefix: "$", tickformat: ",.0f" } }), cfg);
    // drawdown
    const ddData = [{ x: dates, y: st.dd, mode: "lines", name: "strategy", fill: "tozeroy", line: { color: C.negative, width: 1 },
      hovertemplate: "%{x}<br>strategy %{y:.1%}<extra></extra>" }];
    if (spy) ddData.push({ x: dates, y: spy.dd, mode: "lines", name: "SPY", line: { color: C.neutral, width: 1.2 }, hovertemplate: "%{x}<br>SPY %{y:.1%}<extra></extra>" });
    Plotly.react("c-dd", ddData, Nexus.plotlyLayout({ hovermode: "x unified", showlegend: false, margin: { l: 56, r: 14, t: 10, b: 36 },
      yaxis: { tickformat: ".0%" } }), cfg);

    // statistics table
    const row = (label, a, b, c) => `<tr><td>${label}</td><td class="num">${a}</td><td class="num">${b}</td><td class="num">${c}</td></tr>`;
    $("stats").innerHTML = `<thead><tr><th>Measure</th><th class="num">Strategy</th><th class="num">SPY</th><th class="num">All members, equal weight</th></tr></thead><tbody>` +
      row("Final value", money(st.final), spy ? money(spy.final) : "–", money(ew.final)) +
      row("Total return", signed(st.total), spy ? signed(spy.total) : "–", signed(ew.total)) +
      row("CAGR", signed(st.cagr), spy ? signed(spy.cagr) : "–", signed(ew.cagr)) +
      row("Volatility (annual)", pct(st.vol).replace("+", ""), spy ? pct(spy.vol).replace("+", "") : "–", pct(ew.vol).replace("+", "")) +
      row("Sharpe (rf 0)", num(st.sharpe), spy ? num(spy.sharpe) : "–", num(ew.sharpe)) +
      row("Sortino", num(st.sortino), spy ? num(spy.sortino) : "–", num(ew.sortino)) +
      row("Max drawdown", `<span class="neg">${pct(st.mdd)}</span>`, spy ? `<span class="neg">${pct(spy.mdd)}</span>` : "–", `<span class="neg">${pct(ew.mdd)}</span>`) +
      row("Calmar (CAGR / max DD)", num(st.calmar), spy ? num(spy.calmar) : "–", num(ew.calmar)) +
      row("Trades", trades.length, "–", "–") +
      row("Win rate", trades.length ? (wins.length / trades.length * 100).toFixed(0) + "%" : "–", "–", "–") +
      row("Average trade", trades.length ? signed(trades.reduce((a, t) => a + t.ret, 0) / trades.length) : "–", "–", "–") +
      row("Average win / loss", `${wins.length ? pct(wins.reduce((a, t) => a + t.ret, 0) / wins.length) : "–"} / ${losses.length ? pct(losses.reduce((a, t) => a + t.ret, 0) / losses.length) : "–"}`, "–", "–") +
      row("Best / worst trade", trades.length ? `${pct(Math.max(...trades.map((t) => t.ret)))} / ${pct(Math.min(...trades.map((t) => t.ret)))}` : "–", "–", "–") +
      row("Profit factor", grossLoss > 0 ? num(grossWin / grossLoss) : wins.length ? "∞" : "–", "–", "–") +
      row("Average holding (days)", num(avgDays, 0), "–", "–") +
      row("Time in the market", (bt.exposure * 100).toFixed(0) + "%", "100%", "100%") +
      row("Beta / correlation to SPY", `${num(bc.beta)} / ${num(bc.corr)}`, "1.00 / 1.00", spy ? (() => { const x = betaCorr(ew.rets, spy.rets); return `${num(x.beta)} / ${num(x.corr)}`; })() : "–") +
      `</tbody>`;

    // trades table
    $("trades-note").textContent = trades.length
      ? `${trades.length} trades · ${what(o, 1)} when the ratio is expected to rise` + (allowShortNote(o) ? `, ${what(o, -1)} when it is expected to fall` : "")
      : "No trade was triggered with these rules.";
    $("trades").innerHTML = `<thead><tr><th>#</th><th data-list="title">Side</th><th data-list="subtitle">Entry</th><th class="num">Entry ratio</th>` +
      `<th>Exit</th><th class="num">Exit ratio</th><th>Why</th><th class="num">Days</th><th class="num" data-list="value">Return</th>` +
      `<th class="num" data-list="note">P&amp;L</th><th class="num">Equity after</th></tr></thead><tbody>` +
      trades.map((t, i) => `<tr><td class="faint">${i + 1}</td><td>${t.side > 0 ? '<span class="verdict under">Numerator up</span>' : '<span class="verdict over">Denominator up</span>'}</td>` +
        `<td>${S.dates[t.t0]}</td><td class="num">${t.r0.toFixed(4)}</td><td>${S.dates[t.t1]}</td><td class="num">${t.r1.toFixed(4)}</td>` +
        `<td class="muted">${esc(t.reason)}</td><td class="num">${t.t1 - t.t0}</td><td class="num">${signed(t.ret)}</td>` +
        `<td class="num"><span class="${t.pnl >= 0 ? "pos" : "neg"}">${money(t.pnl)}</span></td><td class="num">${money(t.equity)}</td></tr>`).join("") + `</tbody>`;
    lastTrades = trades;

    // calendar years
    const years = [];
    let y0 = S.dates[s].slice(0, 4), start = s;
    for (let t = s; t <= e; t++) {
      const y = S.dates[t].slice(0, 4);
      if (y !== y0 || t === e) {
        const end = y !== y0 ? t - 1 : t;
        years.push({ y: y0, st: eq[end] / eq[start] - 1, spy: spy ? spyEq[end] / spyEq[start] - 1 : NaN, n: trades.filter((tr) => S.dates[tr.t1].startsWith(y0)).length });
        y0 = y; start = end;
      }
    }
    $("years").innerHTML = `<thead><tr><th data-list="title">Year</th><th class="num" data-list="value">Strategy</th><th class="num" data-list="note" data-list-prefix="SPY">SPY</th>` +
      `<th class="num">Difference</th><th class="num" data-list="subtitle" data-list-suffix="trades closed">Trades closed</th></tr></thead><tbody>` +
      years.map((r) => `<tr><td>${r.y}</td><td class="num">${signed(r.st)}</td><td class="num">${signed(r.spy)}</td><td class="num">${signed(r.st - r.spy)}</td><td class="num">${r.n}</td></tr>`).join("") + `</tbody>`;

    $("caveat").innerHTML = (o.strategy === "band" && o.band_src === "fixed"
      ? "<b>In-sample:</b> the band was fitted on the window the scan scored, so trades inside the shaded “band fitted” span knew where the band would be. Trades after the scan's fit end (holdout) did not. Switch “Band from” to rolling for an out-of-sample test. "
      : "") + "Baskets are equal weight at the start date, held as fixed shares. Short positions assume borrow is available at no cost; no interest on cash or margin.";
  }
  const allowShortNote = (o) => o.dirs !== "long" && o.mode !== "longnum";
  let lastTrades = [];

  // ---------------------------------------------------------------- page
  function header() {
    const names = S.names || {};
    const chips = (ts, cls) => `<span class="chips">${ts.map((t) => `<span class="chip ${cls}" title="${esc(names[t] || "")}">${esc(t)}</span>`).join("")}</span>`;
    const label = (ts) => ts.map((t) => names[t] || t).join(", ");
    $("anatomy").innerHTML =
      `<div class="side num"><span class="leg-label num">Numerator · ${S.num.length} stocks</span>${chips(S.num, "num")}<span class="hint">${esc(label(S.num))}</span></div>` +
      `<div class="div">÷</div>` +
      `<div class="side den"><span class="leg-label den">Denominator · ${S.den.length} stocks</span>${chips(S.den, "den")}<span class="hint">${esc(label(S.den))}</span></div>`;
    const run = P.get("run"), rank = P.get("rank"), shape = P.get("shape");
    $("eyebrow").textContent = `Trade Lab${run ? ` · ${run}` : ""}${shape ? ` · ${shape}` : ""}${rank ? ` #${rank}` : ""}`;
    document.title = `${S.num.join("+")} / ${S.den.join("+")} · Trade Lab`;
  }

  let timer = null;
  const changed = () => { clearTimeout(timer); timer = setTimeout(() => render(readSettings()), 120); };

  $("copy-trades").onclick = async () => {
    const head = "n,side,entry_date,entry_ratio,exit_date,exit_ratio,reason,days,return,pnl,equity_after";
    const rows = lastTrades.map((t, i) => [i + 1, t.side > 0 ? "numerator_up" : "denominator_up", S.dates[t.t0], t.r0.toFixed(6), S.dates[t.t1],
      t.r1.toFixed(6), t.reason, t.t1 - t.t0, t.ret.toFixed(6), t.pnl.toFixed(2), t.equity.toFixed(2)].join(","));
    try { await navigator.clipboard.writeText([head, ...rows].join("\n")); $("copy-trades").textContent = "Copied"; }
    catch (e) { $("copy-trades").textContent = "Copy failed"; }
    setTimeout(() => ($("copy-trades").textContent = "Copy as CSV"), 1500);
  };

  (async function init() {
    try { await load(); } catch (e) {
      $("error").hidden = false; $("error").textContent = "Could not load prices: " + e.message;
      $("anatomy").innerHTML = ""; return;
    }
    header();
    applySettings(withUrl(defaults()));
    $("from").min = $("to").min = S.dates[0]; $("from").max = $("to").max = S.dates[S.dates.length - 1];
    document.querySelectorAll(".lab-side .field").forEach((fl) => { const i = fl.querySelector("input, select"); if (i && fl.querySelector("span")) addInfo(fl.querySelector("span"), i.id); });
    document.querySelectorAll("[data-tip-for]").forEach((el) => addInfo(el, el.dataset.tipFor));
    document.querySelectorAll(".lab-side input, .lab-side select").forEach((el) => el.addEventListener("input", changed));
    if (window.Nexus && Nexus.onThemeChange) Nexus.onThemeChange(() => render(readSettings()));
    render(readSettings());
  })();
})();
