"""Self-contained HTML report: per shape, a ranked table and small-multiple charts (inline SVG, hover crosshair)."""

from __future__ import annotations

import json

_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Perfect Shapes - __NAME__</title>
<style>
:root{--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--grid:#e6e5e0;
 --series:#2a78d6;--band:rgba(42,120,214,.12);--fit:#52514e;--hold:rgba(138,137,132,.13);--good:#0ca30c;--crit:#d03b3b;
 color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;
 --ink2:#c3c2b7;--muted:#8f8e86;--grid:#2c2c2a;--series:#3987e5;--band:rgba(57,135,229,.18);--fit:#c3c2b7;
 --hold:rgba(143,142,134,.16);color-scheme:dark}}
:root[data-theme="dark"]{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;--grid:#2c2c2a;
 --series:#3987e5;--band:rgba(57,135,229,.18);--fit:#c3c2b7;--hold:rgba(143,142,134,.16);color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 4px}
.meta{color:var(--ink2);font-size:13px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:20px 0 8px}
.tabs button{font:inherit;border:1px solid var(--grid);background:var(--surface);color:var(--ink);padding:6px 14px;
 border-radius:999px;cursor:pointer}
.tabs button[aria-selected="true"]{border-color:var(--series);box-shadow:inset 0 0 0 1px var(--series)}
.note{color:var(--ink2);font-size:13px;max-width:900px}
.tbl{overflow-x:auto;background:var(--surface);border:1px solid var(--grid);border-radius:8px;margin-top:12px}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:6px 10px;text-align:left;border-bottom:1px solid var(--grid);white-space:nowrap}
th{color:var(--ink2);font-weight:600}td.num,th.num{text-align:right}
tr:last-child td{border-bottom:0}
.dead{color:var(--crit)}.ok{color:var(--good)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:12px;margin-top:16px}
.card{background:var(--surface);border:1px solid var(--grid);border-radius:8px;padding:12px}
.card h3{font-size:14px;margin:0;font-weight:600}
.card .sub{color:var(--ink2);font-size:12px;margin:2px 0 6px}
.chart{position:relative}
svg{display:block;width:100%;height:auto;overflow:visible}
.tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--grid);border-radius:6px;
 padding:4px 8px;font-size:12px;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.12)}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--ink2);font-size:12px;margin-top:6px}
.legend i{display:inline-block;width:14px;height:10px;vertical-align:-1px;margin-right:4px;border-radius:2px}
@media (max-width:480px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<h1>Perfect Shapes</h1>
<div class="meta" id="meta"></div>
<div class="tabs" role="tablist" id="tabs"></div>
<div id="view"></div>
</div>
<script>
const DATA = __DATA__;
const pct = (v,d=1)=> (v>=0?'+':'')+(v*100).toFixed(d)+'%';
const NOTES = {
 uptrend:"Baskets whose combined value rises along a straight line (log scale). Held = longest lookback whose score clears the threshold. Dashed line = fitted trend over that span; shaded tail = holdout bars never seen by the search.",
 downtrend:"Baskets whose combined value falls along a straight line (log scale). Held = longest lookback whose score clears the threshold. Dashed line = fitted trend; shaded tail = holdout.",
 range:"Baskets whose combined value oscillates inside a flat band. Band = 5th-95th percentile over the held span; swings = trips between the lower and upper zones; shaded tail = holdout."
};
const METRIC_LABEL = {annual_return:"Annual", r2:"R²", adverse_ratio:"Adverse/move", height:"Height", drift_ratio:"Drift/band", swings:"Swings"};
const fmtMetric = (k,v)=> k==='annual_return'?pct(v): k==='height'?(v*100).toFixed(1)+'%': k==='swings'?v.toFixed(0): v.toFixed(2);
const ppy = DATA.scoring.periods_per_year;
const P = DATA.panel;
document.getElementById('meta').textContent =
 `${DATA.name} · ${P.symbols} of ${P.requested} instruments · ${P.start} → ${P.end} · fit end ${P.fit_end} · ` +
 `max ${DATA.search.max_assets} assets, ${DATA.search.long_only?'long-only':'long/short'} · threshold ${DATA.scoring.threshold} · generated ${DATA.generated}`;
const shapes = Object.keys(DATA.shapes);
const tabs = document.getElementById('tabs');
shapes.forEach((s,i)=>{const b=document.createElement('button');b.textContent=`${s} (${DATA.shapes[s].items.length})`;
 b.setAttribute('role','tab');b.onclick=()=>show(s);b.dataset.shape=s;tabs.appendChild(b);});
function basketLabel(it){return it.members.slice().sort((a,b)=>b.weight-a.weight).map(m=>`${(m.weight*100).toFixed(0)}% ${m.ticker}`).join(' + ');}
function show(shape){
 let saved; try{localStorage.setItem('ps-tab',shape)}catch(e){}
 tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-selected',b.dataset.shape===shape));
 const S = DATA.shapes[shape], mk = S.metric_order;
 const v = document.getElementById('view'); v.innerHTML='';
 const h = document.createElement('p'); h.className='note'; h.textContent = NOTES[shape]||''; v.appendChild(h);
 if(!S.items.length){v.insertAdjacentHTML('beforeend','<p class="note">No basket held this shape over any window.</p>');return;}
 let t = `<div class="tbl"><table><thead><tr><th>#</th><th>Basket (weights at fit start)</th><th class="num">Held</th><th class="num">Score</th>`+
   mk.map(k=>`<th class="num">${METRIC_LABEL[k]||k}</th>`).join('')+`<th class="num">Holdout</th><th>Alive</th><th>Names</th></tr></thead><tbody>`;
 S.items.forEach(it=>{
  t += `<tr><td>${it.rank}</td><td>${basketLabel(it)}</td><td class="num">${it.duration} bars · ${(it.duration/ppy).toFixed(1)}y</td>`+
   `<td class="num">${it.score.toFixed(3)}</td>`+mk.map(k=>`<td class="num">${fmtMetric(k,it.metrics[k])}</td>`).join('')+
   `<td class="num">${pct(it.holdout_return)}</td><td class="${it.alive?'ok':'dead'}">${it.alive?'✓ yes':'✗ broken'}</td>`+
   `<td>${it.members.map(m=>m.name||m.ticker).join(' / ')}</td></tr>`;});
 v.insertAdjacentHTML('beforeend', t+'</tbody></table></div>');
 const g = document.createElement('div'); g.className='grid'; v.appendChild(g);
 S.items.slice(0,24).forEach(it=>g.appendChild(card(it, shape)));
}
function card(it, shape){
 const c = document.createElement('div'); c.className='card';
 const sec = [...new Set(it.members.map(m=>m.sector).filter(Boolean))].join(', ');
 c.innerHTML = `<h3>#${it.rank} ${basketLabel(it)}</h3><div class="sub">held ${(it.duration/ppy).toFixed(1)}y · score ${it.score.toFixed(3)} · `+
  `holdout ${pct(it.holdout_return)}${sec?' · '+sec:''}</div>`;
 const wrap = document.createElement('div'); wrap.className='chart'; c.appendChild(wrap);
 drawChart(wrap, it.chart, shape);
 const ov = it.chart.overlay.kind==='band'?'range band (p5–p95)':'fitted trend';
 c.insertAdjacentHTML('beforeend',`<div class="legend"><span><i style="background:var(--series);height:2px;vertical-align:3px"></i>basket value</span>`+
  `<span><i style="${it.chart.overlay.kind==='band'?'background:var(--band)':'border-top:2px dashed var(--fit);height:0;vertical-align:3px'}"></i>${ov}</span>`+
  `<span><i style="background:var(--hold)"></i>holdout</span></div>`);
 return c;
}
function drawChart(el, ch, shape){
 const W=360,H=170,m={l:44,r:10,t:8,b:22}, n=ch.values.length;
 const tf = ch.log? Math.log : (x=>x), inv = ch.log? Math.exp : (x=>x);
 const ys = ch.values.map(tf); let lo=Math.min(...ys), hi=Math.max(...ys);
 const ov = ch.overlay;
 if(ov.kind==='band'){lo=Math.min(lo,tf(ov.lo));hi=Math.max(hi,tf(ov.hi));}
 const pad=(hi-lo)*0.06||0.01; lo-=pad; hi+=pad;
 const x=i=>m.l+(W-m.l-m.r)*i/(n-1), y=v=>m.t+(H-m.t-m.b)*(1-(v-lo)/(hi-lo));
 const NS='http://www.w3.org/2000/svg';
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="basket value">`;
 for(let k=0;k<=3;k++){const v=lo+(hi-lo)*k/3, yy=y(v);
  s+=`<line x1="${m.l}" x2="${W-m.r}" y1="${yy}" y2="${yy}" stroke="var(--grid)" stroke-width="1"/>`+
     `<text x="${m.l-6}" y="${yy+4}" text-anchor="end" font-size="10" fill="var(--muted)">${inv(v).toFixed(2)}</text>`;}
 [0, Math.floor((n-1)/2), n-1].forEach((i,k)=>{s+=`<text x="${x(i)}" y="${H-6}" font-size="10" fill="var(--muted)" text-anchor="${k===0?'start':k===2?'end':'middle'}">${ch.dates[i]}</text>`;});
 if(ch.holdout_from<n) s+=`<rect x="${x(ch.holdout_from)}" y="${m.t}" width="${x(n-1)-x(ch.holdout_from)}" height="${H-m.t-m.b}" fill="var(--hold)"/>`;
 if(ov.kind==='band') s+=`<rect x="${x(ov.from)}" y="${y(tf(ov.hi))}" width="${x(ov.to-1)-x(ov.from)}" height="${y(tf(ov.lo))-y(tf(ov.hi))}" fill="var(--band)"/>`;
 else { const base=ch.values[ov.from];
  s+=`<line x1="${x(ov.from)}" x2="${x(ov.to-1)}" y1="${y(tf(ov.y0*base))}" y2="${y(tf(ov.y1*base))}" stroke="var(--fit)" stroke-width="1.5" stroke-dasharray="5 4"/>`;}
 s+=`<polyline fill="none" stroke="var(--series)" stroke-width="2" stroke-linejoin="round" points="${ys.map((v,i)=>x(i).toFixed(1)+','+y(v).toFixed(1)).join(' ')}"/>`;
 s+=`<line class="xh" y1="${m.t}" y2="${H-m.b}" stroke="var(--muted)" stroke-width="1" visibility="hidden"/><circle class="dot" r="4" fill="var(--series)" stroke="var(--surface)" stroke-width="2" visibility="hidden"/>`;
 s+=`<rect x="${m.l}" y="0" width="${W-m.l-m.r}" height="${H}" fill="transparent" class="hit"/></svg>`;
 el.innerHTML=s;
 const svg=el.querySelector('svg'), xh=svg.querySelector('.xh'), dot=svg.querySelector('.dot');
 const tip=document.createElement('div'); tip.className='tip'; tip.hidden=true; el.appendChild(tip);
 const move=e=>{const r=svg.getBoundingClientRect(); const px=(e.clientX-r.left)*W/r.width;
  const i=Math.max(0,Math.min(n-1,Math.round((px-m.l)/(W-m.l-m.r)*(n-1))));
  xh.setAttribute('x1',x(i));xh.setAttribute('x2',x(i));xh.setAttribute('visibility','visible');
  dot.setAttribute('cx',x(i));dot.setAttribute('cy',y(ys[i]));dot.setAttribute('visibility','visible');
  tip.hidden=false; tip.innerHTML=`<b>${ch.dates[i]}</b> · ${ch.values[i].toFixed(3)} (${pct(ch.values[i]-1)})${i>=ch.holdout_from?' · holdout':''}`;
  const left=x(i)*r.width/W; tip.style.top='0px'; tip.style.left=(left>r.width/2? left-tip.offsetWidth-10 : left+10)+'px';};
 svg.addEventListener('pointermove',move); svg.addEventListener('pointerleave',()=>{tip.hidden=true;xh.setAttribute('visibility','hidden');dot.setAttribute('visibility','hidden');});
}
let first = shapes[0]; try{const s=localStorage.getItem('ps-tab'); if(s&&DATA.shapes[s]) first=s;}catch(e){}
show(first);
</script></body></html>
"""


def render_html(payload: dict) -> str:
    data = json.dumps(payload, default=float).replace("</", "<\\/")
    return _TEMPLATE.replace("__NAME__", str(payload.get("name", ""))).replace("__DATA__", data)
