"""Self-contained research dashboard; no third-party browser scripts."""
from __future__ import annotations


def dashboard_html() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Shadow Price System</title>
<style>
:root{color-scheme:dark;--bg:#0b1118;--panel:#14202c;--line:#304355;--text:#f3f7fb;--muted:#b9c8d6;--gold:#f7cc68;--aqua:#70d4d4}
*{box-sizing:border-box}body{font:16px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--text);margin:0}
header,main,footer{max-width:1200px;margin:auto;padding:1rem 1.25rem}header{padding-top:2rem}h1{font-size:clamp(2rem,5vw,3.4rem);margin:0}
h2{font-size:1.2rem;margin:.1rem 0 .7rem}.muted,small{color:var(--muted)}.lead{max-width:68ch}
.banner{border-left:4px solid var(--gold);background:#29251a;padding:.7rem 1rem;margin:1rem 0}
.controls{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}.badge{border:1px solid var(--line);border-radius:99px;padding:.25rem .7rem}
button{font:inherit;font-weight:650;border:1px solid var(--aqua);border-radius:7px;color:#09202a;background:var(--aqua);padding:.55rem .85rem;cursor:pointer}
button.secondary{color:var(--text);background:transparent;border-color:var(--line)}button:focus-visible,a:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
a{color:var(--aqua)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(265px,1fr));gap:1rem;margin:1rem 0}
.card,.section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:1rem}.card{min-height:230px}
.score{font-size:2.4rem;font-weight:750;line-height:1}.metric{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:.4rem 0;gap:1rem}
.metric span:last-child{text-align:right;font-variant-numeric:tabular-nums}.action{font-weight:700;color:var(--gold)}.section{margin:1rem 0}
.chart{width:100%;height:180px;background:#0e1822;border-radius:6px}.legend{display:flex;gap:1rem;font-size:.85rem}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.82rem;background:#0d1721;border-radius:6px;padding:.7rem;color:var(--muted)}
footer{color:var(--muted);font-size:.9rem;padding-bottom:3rem}
</style></head><body>
<header><h1>Shadow Price System</h1><p class="lead muted">Explainable gold, silver and copper research. Compare modeled shadow values, trend, participation and exchange-session context.</p>
<div class="banner">Research and paper-trading only. A score is not a trade probability. Exchange schedules must be verified separately; this app cannot place orders.</div>
<div class="controls"><button id="latest">Latest research</button><button id="demo" class="secondary">Explore synthetic demo</button><button id="refresh" class="secondary">Refresh providers</button><span class="badge" id="mode">Loading</span></div>
<p id="status" role="status" aria-live="polite" class="muted">Loading available research…</p></header>
<main><div class="grid" id="cards"></div>
<div class="section"><h2>Price and shadow benchmark</h2><p class="muted">Select a metal to see the last 90 completed observations. Synthetic mode is illustrative only.</p><div class="controls" id="chart-buttons"></div><svg class="chart" id="chart" role="img" aria-label="Price and shadow benchmark chart" viewBox="0 0 600 180" preserveAspectRatio="none"></svg><div class="legend"><span style="color:var(--gold)">● Market price</span><span style="color:var(--aqua)">● Shadow benchmark</span></div></div>
<div class="section"><h2>Exchange and regional context</h2><p class="muted">Actual eligibility comes from a verified instrument calendar. <a href="https://market24hclock.com/" target="_blank" rel="noopener noreferrer">Open Market 24h Clock</a> for independent regional awareness; site content is not embedded or scraped.</p><div id="sessions" class="grid"></div></div>
<div class="section"><h2>Decision evidence</h2><p class="muted">Select “Evidence” on a metal card for score components, provenance and feature status.</p><pre id="evidence">No metal selected.</pre></div></main>
<footer>TDV-style monetary-base anchors are model inputs, not verified fair values. Volume Profile is a bar-level OHLCV approximation. QQE MOD is experimental and disabled by default. <a href="/docs">API documentation</a>.</footer>
<script>
const esc=s=>String(s??'—').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
let current=null,selected='GOLD';const symbols=['GOLD','SILVER','COPPER'];
const pct=x=>x==null?'—':(Number(x)*100).toFixed(1)+'%';
function row(label,value){return '<div class="metric"><span>'+esc(label)+'</span><span>'+esc(value)+'</span></div>'}
function render(x){current=x;document.querySelector('#mode').textContent=x.synthetic_data?'SYNTHETIC DEMO':'RESEARCH DATA';
 document.querySelector('#status').textContent=x.synthetic_data?x.warning:'Snapshot '+(x.created_at||'unavailable')+' · No execution';
 let cards='';for(const symbol of symbols){const s=(x.signals||{})[symbol];if(!s)continue;const ev=(x.evidence||{})[symbol]||{};const f=ev.features||{};
 const multiple=f.shadow_multiple_percentile??s.shadow_multiple_percentile;
 cards+='<article class="card"><h2>'+symbol+'</h2><div class="score">'+(s.score==null?'—':Number(s.score).toFixed(1))+'<small>/100</small></div><p class="action">'+esc(s.action)+'</p>';
 cards+=row('Shadow gap',pct(s.shadow_gap))+row('Shadow-multiple percentile',multiple==null?'—':Number(multiple).toFixed(1)+'th');
 cards+=row('Contracts',s.position_plan?.contracts??'—')+'<p class="muted">'+esc((s.blockers||[])[0]||(s.confirmations||[])[0]||'No decision evidence yet')+'</p><button class="secondary" data-evidence="'+symbol+'">Evidence</button></article>'}
 document.querySelector('#cards').innerHTML=cards||'<p>No completed snapshot. Explore the labeled synthetic demo or configure verified anchors.</p>';
 document.querySelectorAll('[data-evidence]').forEach(b=>b.onclick=()=>showEvidence(b.dataset.evidence));
 document.querySelector('#chart-buttons').innerHTML=symbols.map(s=>'<button class="secondary" data-chart="'+s+'" aria-pressed="'+(s===selected)+'">'+s+'</button>').join('');
 document.querySelectorAll('[data-chart]').forEach(b=>b.onclick=()=>{selected=b.dataset.chart;renderChart()});renderChart()}
function renderChart(){document.querySelectorAll('[data-chart]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.chart===selected)));
 const points=(current?.charts||{})[selected]||[];const valid=points.filter(p=>Number.isFinite(p.price)&&Number.isFinite(p.shadow));const svg=document.querySelector('#chart');
 if(valid.length<2){svg.innerHTML='<text x="20" y="90" fill="#b9c8d6">No chart observations</text>';return}
 const values=valid.flatMap(p=>[p.price,p.shadow]);let min=Math.min(...values),max=Math.max(...values);if(min===max)max=min+1;
 const xy=(v,i)=>(20+i*560/(valid.length-1)).toFixed(1)+','+(160-(v-min)*140/(max-min)).toFixed(1);
 svg.innerHTML='<polyline points="'+valid.map((p,i)=>xy(p.price,i)).join(' ')+'" fill="none" stroke="#f7cc68" stroke-width="2"/><polyline points="'+valid.map((p,i)=>xy(p.shadow,i)).join(' ')+'" fill="none" stroke="#70d4d4" stroke-width="2"/>'}
function showEvidence(symbol){const ev=(current?.evidence||{})[symbol],s=(current?.signals||{})[symbol];
 document.querySelector('#evidence').textContent=JSON.stringify(ev||{symbol,synthetic_demo:true,signal:s},null,2)}
async function load(url){const r=await fetch(url);if(!r.ok)throw new Error((await r.json()).detail||r.statusText);render(await r.json())}
async function context(){try{const r=await fetch('/api/market-context'),x=await r.json();document.querySelector('#sessions').innerHTML=symbols.map(s=>{const q=x[s]||{};return '<div class="card"><h2>'+s+'</h2>'+row('Exchange',q.exchange||'Not configured')+row('Status',q.status||'UNKNOWN')+row('Next transition',q.next_transition_utc||'—')+row('Regional overlap',q.context?.label||'—')+'<small>'+esc(q.reason||q.note||'')+'</small></div>'}).join('')}catch(e){document.querySelector('#sessions').textContent='Session context unavailable: '+e.message}}
document.querySelector('#latest').onclick=async()=>{try{await load('/api/signals/latest')}catch(e){document.querySelector('#status').textContent='No research snapshot: '+e.message}};
document.querySelector('#demo').onclick=async()=>{try{await load('/api/demo')}catch(e){document.querySelector('#status').textContent=e.message}};
document.querySelector('#refresh').onclick=async()=>{document.querySelector('#status').textContent='Refreshing…';try{const r=await fetch('/api/refresh',{method:'POST'});if(!r.ok)throw new Error((await r.json()).detail||r.statusText);render(await r.json());context()}catch(e){document.querySelector('#status').textContent='Refresh unavailable: '+e.message}};
document.querySelector('#latest').click();context();
</script></body></html>"""
