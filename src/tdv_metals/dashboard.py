"""Original research dashboard with an optional, user-activated TradingView widget."""
from __future__ import annotations


def dashboard_html() -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Shadow Price System</title>
<style>
:root{color-scheme:dark;--bg:#080d14;--panel:#111b27;--panel2:#172432;--line:#2d3c4d;--text:#f4f7f8;--muted:#abc0cc;--gold:#e8bc6a;--aqua:#70d4d4}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{font:16px/1.5 system-ui,Segoe UI,sans-serif;background:radial-gradient(circle at 82% 0,#1b3044 0,transparent 38%),var(--bg);color:var(--text);margin:0}
header,main,footer{max-width:1280px;margin:auto;padding:1rem 1.5rem}header{padding-top:1.2rem}h1{font-size:clamp(2.2rem,5vw,4rem);line-height:1.08;letter-spacing:-.045em;margin:.35rem 0 1rem;max-width:15ch}
h2{font-size:1.2rem;margin:.1rem 0 .7rem}.muted,small{color:var(--muted)}.lead{max-width:68ch}
.nav{display:flex;align-items:center;justify-content:space-between;gap:1rem;border-bottom:1px solid var(--line);padding-bottom:1rem}.brand{font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:var(--text);text-decoration:none}.brand-mark{display:inline-grid;place-items:center;background:var(--gold);color:#111b27;width:2rem;height:2rem;border-radius:8px;margin-right:.55rem}.nav-links{display:flex;flex-wrap:wrap;gap:1rem;font-size:.9rem}.eyebrow{color:var(--gold);font-size:.8rem;letter-spacing:.16em;text-transform:uppercase;font-weight:750}.hero{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(250px,.7fr);gap:1.5rem;padding:3rem 0 1rem}.hero-note{align-self:center;background:linear-gradient(145deg,#1d3140,#111b27);border:1px solid var(--line);border-radius:18px;padding:1.5rem}.hero-note strong{font-size:1.4rem;display:block;margin:.5rem 0}.section-kicker{font-size:.75rem;text-transform:uppercase;letter-spacing:.13em;color:var(--gold);font-weight:750}.section-heading{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;align-items:baseline}
.banner{border-left:4px solid var(--gold);background:#29251a;padding:.7rem 1rem;margin:1rem 0}
.controls{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}.badge{border:1px solid var(--line);border-radius:99px;padding:.25rem .7rem}
button{font:inherit;font-weight:650;border:1px solid var(--gold);border-radius:9px;color:#1d1a12;background:var(--gold);padding:.65rem .95rem;cursor:pointer}
button.secondary{color:var(--text);background:transparent;border-color:var(--line)}button:focus-visible,a:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
a{color:var(--aqua)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(265px,1fr));gap:1rem;margin:1rem 0}
.card,.section{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:1.3rem}.card{min-height:230px}.card:hover{border-color:#627482}
.score{font-size:2.4rem;font-weight:750;line-height:1}.metric{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:.4rem 0;gap:1rem}
.metric span:last-child{text-align:right;font-variant-numeric:tabular-nums}.action{font-weight:700;color:var(--gold)}.section{margin:1rem 0}
.chart{width:100%;height:240px;background:#0e1822;border-radius:9px}.legend{display:flex;gap:1rem;font-size:.85rem}.tv-host{min-height:460px;background:#0b1420;border:1px solid var(--line);border-radius:10px;overflow:hidden;display:grid;place-items:center}.tv-host .tradingview-widget-container{width:100%;height:460px}.tv-host .tradingview-widget-container__widget{width:100%;height:calc(100% - 32px)}.tradingview-widget-copyright{height:32px;display:flex;align-items:center;justify-content:center;gap:.3rem;font-size:.8rem}.tradingview-widget-copyright a{color:var(--aqua)}.tv-placeholder{max-width:48ch;text-align:center;padding:2rem;color:var(--muted)}.tv-notice{font-size:.88rem;max-width:80ch}.subnav{display:flex;gap:.75rem;flex-wrap:wrap;margin:.8rem 0}button[aria-pressed="true"]{border-color:var(--gold);color:var(--gold)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.82rem;background:#0d1721;border-radius:6px;padding:.7rem;color:var(--muted)}
footer{color:var(--muted);font-size:.9rem;padding-bottom:3rem}@media(max-width:760px){.hero{grid-template-columns:1fr;padding-top:2rem}.nav{align-items:flex-start;flex-direction:column}.chart{height:180px}.tv-host,.tv-host .tradingview-widget-container{min-height:340px;height:340px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body>
<header><nav class="nav" aria-label="Main navigation"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true">S</span>Shadow Price System</a><div class="nav-links"><a href="#overview">Overview</a><a href="#model">Shadow model</a><a href="#tradingview">TradingView</a><a href="#sessions-section">Sessions</a><a href="/docs">API</a></div></nav>
<div class="hero"><div><div class="eyebrow">Metals intelligence · research workspace</div><h1>See price beside its shadow.</h1><p class="lead muted">Explainable gold, silver and copper research. Compare modeled shadow values, trend, participation and exchange-session context.</p></div><aside class="hero-note"><span class="section-kicker">Decision boundary</span><strong>Research first. No orders.</strong><span class="muted">TradingView is an optional outside chart. Shadow scores and backtests use only configured system data.</span></aside></div>
<div class="banner">Research and paper-trading only. A score is not a trade probability. Exchange schedules must be verified separately; this app cannot place orders.</div>
<div class="controls"><button id="latest">Latest research</button><button id="demo" class="secondary">Explore synthetic demo</button><button id="refresh" class="secondary">Refresh providers</button><span class="badge" id="mode">Loading</span></div>
<p id="status" role="status" aria-live="polite" class="muted">Loading available research…</p></header>
<main><section id="overview"><div class="section-heading"><div><span class="section-kicker">01 / Opportunity map</span><h2>Gold · Silver · Copper</h2></div><span class="muted">Normalized score / 100</span></div><div class="grid" id="cards"></div></section>
<section class="section" id="model"><span class="section-kicker">02 / Proprietary model view</span><h2>Price and shadow benchmark</h2><p class="muted">Select a metal to see the last 90 completed observations. Synthetic mode is illustrative only.</p><div class="controls" id="chart-buttons"></div><svg class="chart" id="chart" role="img" aria-label="Price and shadow benchmark chart" viewBox="0 0 600 180" preserveAspectRatio="none"></svg><div class="legend"><span style="color:var(--gold)">● Market price</span><span style="color:var(--aqua)">● Shadow benchmark</span></div></section>
<section class="section" id="tradingview"><span class="section-kicker">03 / External market lens</span><h2>TradingView chart</h2><p class="tv-notice muted">Optional external chart, displayed only after you choose to load it. The supplied Gold and Silver charts use TradingView-calculated TVC symbols; Copper uses IG:COPPER. These can differ from the model's futures data in instrument, quote delay, timezone or adjustment. TradingView receives your browser connection when loaded; its chart never feeds the Shadow Valuation Score or a backtest.</p><div class="subnav" role="group" aria-label="TradingView metal"><button class="secondary" data-tv="GOLD" aria-pressed="true">Gold</button><button class="secondary" data-tv="SILVER" aria-pressed="false">Silver</button><button class="secondary" data-tv="COPPER" aria-pressed="false">Copper</button></div><div class="subnav"><button id="tv-load" class="secondary">Load external chart for Gold</button><button id="tv-unload" class="secondary" hidden>Remove chart</button><span class="badge" id="tv-symbol">Chart mapping loading…</span></div><p id="tv-status" role="status" aria-live="polite" class="muted">Chart not loaded.</p><div class="tv-host" id="tv-host"><p class="tv-placeholder">Your research remains local to this application until you load the TradingView chart.</p></div><p class="tv-notice muted">Chart technology and data © <a href="https://www.tradingview.com/" target="_blank" rel="noopener noreferrer">TradingView</a>. Its native widget branding remains visible. The supplied five TradingView studies are display-only and distinct from this system's calculated indicators.</p></section>
<section class="section" id="sessions-section"><span class="section-kicker">04 / Market context</span><h2>Exchange and regional context</h2><p class="muted">Actual eligibility comes from a verified instrument calendar. <a href="https://market24hclock.com/" target="_blank" rel="noopener noreferrer">Open Market 24h Clock</a> for independent regional awareness; site content is not embedded or scraped.</p><div id="sessions" class="grid"></div></section>
<div class="section"><h2>Decision evidence</h2><p class="muted">Select “Evidence” on a metal card for score components, provenance and feature status.</p><pre id="evidence">No metal selected.</pre></div></main>
<footer>TDV-style monetary-base anchors are model inputs, not verified fair values. Volume Profile is a bar-level OHLCV approximation. QQE MOD is experimental and disabled by default. Interface is an original Trecker-aligned implementation; no Framer template assets are bundled. <a href="https://www.framer.com/marketplace/templates/trecker/" target="_blank" rel="noopener noreferrer">Trecker template</a> · <a href="/docs">API documentation</a>.</footer>
<script>
const esc=s=>String(s??'—').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
let current=null,selected='GOLD',tvSelected='GOLD',tvConfig=null,tvLoaded=false;const symbols=['GOLD','SILVER','COPPER'];
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
function updateTradingViewLabel(){const mapped=tvConfig?.symbols?.[tvSelected];
 document.querySelectorAll('[data-tv]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tv===tvSelected)));
 document.querySelector('#tv-symbol').textContent=mapped||'No chart mapping';
 document.querySelector('#tv-load').textContent='Load external chart for '+tvSelected.charAt(0)+tvSelected.slice(1).toLowerCase();
 document.querySelector('#tv-load').disabled=!tvConfig?.enabled||!mapped}
function unloadTradingView(){const host=document.querySelector('#tv-host');host.replaceChildren();
 const placeholder=document.createElement('p');placeholder.className='tv-placeholder';placeholder.textContent='TradingView chart not loaded. Your model data stays separate.';host.append(placeholder);
 document.querySelector('#tv-unload').hidden=true;document.querySelector('#tv-status').textContent='Chart not loaded.';tvLoaded=false}
function loadTradingView(){if(tvLoaded||!tvConfig?.enabled)return;const symbol=tvConfig.symbols?.[tvSelected];if(!symbol)return;
 const host=document.querySelector('#tv-host');host.replaceChildren();const container=document.createElement('div');container.className='tradingview-widget-container';
 const widget=document.createElement('div');widget.className='tradingview-widget-container__widget';container.append(widget);
 const script=document.createElement('script');script.type='text/javascript';script.async=true;
 script.src='https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
 script.textContent=JSON.stringify({allow_symbol_change:true,calendar:false,details:false,hide_side_toolbar:true,hide_top_toolbar:false,hide_legend:false,hide_volume:false,hotlist:false,interval:'D',locale:'en',save_image:true,style:'1',theme:'dark',timezone:'Etc/UTC',backgroundColor:'#0F0F0F',gridColor:'rgba(242, 242, 242, 0.2)',watchlist:[],withdateranges:false,compareSymbols:[],support_host:'https://www.tradingview.com',studies:tvConfig.studies||[],autosize:true,symbol});
 script.onerror=()=>{unloadTradingView();document.querySelector('#tv-status').textContent='TradingView could not load. Check your connection or content blocker.'};
 const credit=document.createElement('div');credit.className='tradingview-widget-copyright';
 const link=document.createElement('a');const [venue,ticker]=symbol.split(':');link.href='https://www.tradingview.com/symbols/'+encodeURIComponent(ticker)+'/?exchange='+encodeURIComponent(venue);link.target='_blank';link.rel='noopener nofollow noreferrer';link.textContent=ticker+' chart';
 const by=document.createElement('span');by.textContent=' by TradingView';credit.append(link,by);
 container.append(script,credit);host.append(container);tvLoaded=true;document.querySelector('#tv-unload').hidden=false;
 document.querySelector('#tv-status').textContent='External TradingView '+symbol+' chart requested. Quotes may differ from model data.'}
async function chartConfig(){try{const r=await fetch('/api/chart-config');if(!r.ok)throw new Error(r.statusText);tvConfig=await r.json();
 if(!tvConfig.enabled)document.querySelector('#tv-status').textContent='TradingView is disabled by configuration.';
 updateTradingViewLabel()}catch(e){document.querySelector('#tv-status').textContent='Chart configuration unavailable: '+e.message;updateTradingViewLabel()}}
async function load(url){const r=await fetch(url);if(!r.ok)throw new Error((await r.json()).detail||r.statusText);render(await r.json())}
async function context(){try{const r=await fetch('/api/market-context'),x=await r.json();document.querySelector('#sessions').innerHTML=symbols.map(s=>{const q=x[s]||{};return '<div class="card"><h2>'+s+'</h2>'+row('Exchange',q.exchange||'Not configured')+row('Status',q.status||'UNKNOWN')+row('Next transition',q.next_transition_utc||'—')+row('Regional overlap',q.context?.label||'—')+'<small>'+esc(q.reason||q.note||'')+'</small></div>'}).join('')}catch(e){document.querySelector('#sessions').textContent='Session context unavailable: '+e.message}}
document.querySelector('#latest').onclick=async()=>{try{await load('/api/signals/latest')}catch(e){document.querySelector('#status').textContent='No research snapshot: '+e.message}};
document.querySelector('#demo').onclick=async()=>{try{await load('/api/demo')}catch(e){document.querySelector('#status').textContent=e.message}};
document.querySelector('#refresh').onclick=async()=>{document.querySelector('#status').textContent='Refreshing…';try{const r=await fetch('/api/refresh',{method:'POST'});if(!r.ok)throw new Error((await r.json()).detail||r.statusText);render(await r.json());context()}catch(e){document.querySelector('#status').textContent='Refresh unavailable: '+e.message}};
document.querySelector('#tv-load').onclick=loadTradingView;document.querySelector('#tv-unload').onclick=unloadTradingView;
document.querySelectorAll('[data-tv]').forEach(b=>b.onclick=()=>{if(tvSelected===b.dataset.tv)return;tvSelected=b.dataset.tv;unloadTradingView();updateTradingViewLabel()});
document.querySelector('#latest').click();context();chartConfig();
</script></body></html>"""
