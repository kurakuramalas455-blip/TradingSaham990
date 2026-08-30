"""FastAPI Web Interface — IDX Bot with auto-scan, hidden gems, sortable table, and realtime charts."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
import yfinance as yf
from main import IDXTradingBot
from data_fetcher import fetch_live_profile
from idx_tickers import get_dynamic_gems, cache_status, get_trending
import watchlist as wl_store

app = FastAPI(title="IDX Bot Engine")
bot = IDXTradingBot()

IDX_WATCHLIST = [
    "BBCA", "BBRI", "BMRI", "BBNI", "BRIS",
    "ASII", "TLKM", "UNVR", "ICBP", "INDF",
    "KLBF", "GOTO", "BREN", "PGAS", "ADRO",
    "ANTM", "PTBA", "INCO", "TOWR", "EXCL",
    "SMGR", "CPIN", "ACES", "MAPI", "SIDO",
    "HEAL", "JSMR", "WIKA", "MEDC", "AMMN",
]

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>IDX Bot Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  :root { --blue:#2563eb;--green:#16a34a;--red:#dc2626;--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#f1f5f9;--sub:#94a3b8; }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

  nav{display:flex;align-items:center;justify-content:space-between;padding:1rem 2rem;border-bottom:1px solid var(--border)}
  nav h1{font-size:1.2rem;font-weight:700;color:var(--blue)}
  .badge{background:#0f3460;color:#60a5fa;padding:.2rem .75rem;border-radius:999px;font-size:.7rem}

  .main{padding:1.5rem 2rem;max-width:1400px;margin:0 auto}
  .top-bar{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap;margin-bottom:1.25rem}

  button{padding:.45rem 1rem;border:none;border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:600;transition:opacity .15s}
  button:hover{opacity:.85}
  .btn-blue{background:var(--blue);color:#fff}
  .btn-purple{background:#7c3aed;color:#fff}
  .btn-teal{background:#0d9488;color:#fff}
  .btn-dark{background:var(--card);color:var(--text);border:1px solid var(--border)}
  .ticker-input{background:var(--card);border:1px solid var(--border);color:var(--text);padding:.45rem .75rem;border-radius:6px;font-size:.8rem;width:150px}

  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.75rem;margin-bottom:1.25rem}
  .stat-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1rem}
  .stat-card .lbl{font-size:.65rem;color:var(--sub);margin-bottom:.2rem;text-transform:uppercase;letter-spacing:.06em}
  .stat-card .val{font-size:1.5rem;font-weight:700}

  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.25rem}
  @media(max-width:900px){.two-col{grid-template-columns:1fr}}

  .card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1.25rem}
  .card h3{font-size:.8rem;color:var(--sub);margin-bottom:.9rem;text-transform:uppercase;letter-spacing:.07em}

  /* TABLE */
  .table-wrap{background:var(--card);border:1px solid var(--border);border-radius:10px;overflow-x:auto;margin-bottom:1.25rem}
  table{width:100%;border-collapse:collapse;font-size:.82rem}
  thead th{text-align:left;padding:.65rem 1rem;background:#0f172a;color:var(--sub);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;cursor:pointer;user-select:none;white-space:nowrap}
  thead th:hover{color:var(--text)}
  thead th.sorted-asc::after{content:" ▲"}
  thead th.sorted-desc::after{content:" ▼"}
  tbody tr{border-top:1px solid var(--border);cursor:pointer;transition:background .1s}
  tbody tr:hover{background:#263352}
  tbody tr.active-row{background:#1e3a5f}
  td{padding:.65rem 1rem}

  .action{display:inline-block;padding:.12rem .55rem;border-radius:999px;font-size:.68rem;font-weight:700}
  .action.BUY{background:#14532d;color:#4ade80}
  .action.SELL{background:#7f1d1d;color:#f87171}
  .action.HOLD{background:#1e3a5f;color:#60a5fa}
  .action.WATCHLIST{background:#451a03;color:#fb923c}
  .action.PASS{background:#1f2937;color:#6b7280}

  .risk.LOW_RISK{color:#4ade80}
  .risk.MEDIUM_RISK{color:#fb923c}
  .risk.HIGH_RISK{color:#f87171}

  .pb-wrap{background:#0f172a;border-radius:999px;height:5px;width:90px;display:inline-block;vertical-align:middle}
  .pb{height:5px;border-radius:999px;background:var(--blue)}

  /* DETAIL PANEL */
  #detail-panel{display:none;margin-bottom:1.25rem}
  .detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.65rem;margin-bottom:1rem}
  .di{background:#0f172a;border-radius:6px;padding:.7rem}
  .di .dk{font-size:.65rem;color:var(--sub);margin-bottom:.2rem;text-transform:uppercase;letter-spacing:.05em}
  .di .dv{font-size:.95rem;font-weight:600}
  .rationale-list{list-style:none}
  .rationale-list li{padding:.2rem 0;font-size:.82rem;color:var(--sub)}
  .rationale-list li::before{content:"→ ";color:var(--blue)}

  /* SPINNER */
  .spinner{display:none;align-items:center;gap:.5rem;color:var(--sub);font-size:.8rem}
  .spinner.active{display:flex}
  .spin{width:1rem;height:1rem;border:2px solid var(--border);border-top-color:var(--blue);border-radius:50%;animation:spin .7s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}

  .gem-badge{background:#134e4a;color:#5eead4;font-size:.65rem;font-weight:700;padding:.1rem .4rem;border-radius:999px;margin-left:.4rem}

  /* Prediction Cards */
  .pred-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.75rem;margin-bottom:1rem}
  @media(max-width:700px){.pred-grid{grid-template-columns:1fr}}
  .pred-card{background:#0f172a;border-radius:8px;padding:.85rem 1rem;border:1px solid var(--border)}
  .pred-card .horizon{font-size:.65rem;color:var(--sub);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35rem}
  .pred-card .consensus{font-size:1.15rem;font-weight:700;margin-bottom:.2rem}
  .pred-card .pred-price{font-size:.85rem;margin-bottom:.4rem}
  .pred-card .method-row{display:flex;flex-wrap:wrap;gap:.3rem}
  .pred-card .m-badge{font-size:.6rem;font-weight:600;padding:.1rem .4rem;border-radius:4px}
  .m-badge.NAIK{background:#14532d;color:#4ade80}
  .m-badge.TURUN{background:#7f1d1d;color:#f87171}
  .m-badge.NETRAL{background:#1f2937;color:#94a3b8}

  /* Watchlist Star */
  .star-btn{background:none;border:none;cursor:pointer;font-size:1.1rem;padding:.1rem .3rem;line-height:1;opacity:.5;transition:opacity .15s}
  .star-btn.saved{opacity:1;color:#fbbf24}
  .star-btn:hover{opacity:1}
  .btn-gold{background:#92400e;color:#fcd34d}

  /* Watchlist panel */
  .wl-panel{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:1.25rem;margin-bottom:1.25rem;display:none}
  .wl-chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.75rem}
  .wl-chip{background:#0f172a;border:1px solid var(--border);border-radius:6px;padding:.35rem .75rem;font-size:.8rem;display:flex;align-items:center;gap:.4rem}
  .wl-chip button{background:none;border:none;color:#f87171;cursor:pointer;font-size:.9rem;padding:0;line-height:1}

  /* Mobile Overrides */
  @media(max-width:600px){
    .main{padding:1rem}
    nav{padding:1rem}
    .top-bar button{flex:1 1 45%;font-size:.75rem}
    .ticker-input{width:100%;flex:1 1 100%}
    .stat-card{padding:.75rem}
    .detail-grid{grid-template-columns:1fr 1fr}
  }
</style>
</head>
<body>
<nav>
  <h1>IDX Bot Dashboard</h1>
  <span class="badge">Paper Trading ✓ DRY_RUN</span>
</nav>

<div class="main">
  <div class="top-bar">
    <button class="btn-blue" onclick="scanAll('lq45')">Auto-Scan LQ45</button>
    <button class="btn-teal" onclick="scanAll('gems')">Scan Hidden Gems <span style="font-size:.65rem;background:#0d9488;padding:.1rem .4rem;border-radius:999px;margin-left:.3rem">LIVE</span></button>
    <button class="btn-purple" style="background:#ef4444" onclick="scanAll('trending')">🔥 Scan Trending</button>
    <button class="btn-gold" onclick="toggleWatchlist()">★ Watchlist <span id="wl-count-badge"></span></button>
    <button class="btn-dark" onclick="loadPortfolio()">Portfolio Virtual</button>
    <button class="btn-purple" style="background:#8b5cf6" onclick="showAutoPlan()">Rekomendasi Pintar</button>
    <input class="ticker-input" id="ticker" placeholder="Kode saham (BBCA...)" />
    <button class="btn-purple" onclick="scanOne()">Analisa Manual</button>
    <div class="spinner" id="spinner"><div class="spin"></div><span id="spinner-text">Memindai...</span></div>
  </div>

  <!-- Watchlist Panel -->
  <div class="wl-panel" id="wl-panel">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">
      <h3 style="font-size:.85rem">Watchlist Tersimpan</h3>
      <button class="btn-blue" style="font-size:.72rem;padding:.3rem .7rem" onclick="scanWatchlist()">Scan Semua Watchlist</button>
    </div>
    <div class="wl-chips" id="wl-chips">Kosong — tambahkan saham dari panel detail.</div>
  </div>

  <div id="gems-info" style="display:none;font-size:.72rem;color:var(--sub);margin-bottom:.75rem;padding:.5rem .75rem;background:var(--card);border-radius:6px;border:1px solid var(--border)">
    Sumber data: <span id="gems-source" style="color:#5eead4"></span> &nbsp;|&nbsp;
    Total saham di cache: <span id="gems-total"></span> &nbsp;|&nbsp;
    25 saham dipilih acak setiap kali scan &nbsp;|&nbsp;
    Cache diperbarui tiap 1 jam
  </div>

  <div class="stats" id="stats-row">
    <div class="stat-card"><div class="lbl">Total Dipindai</div><div class="val" id="s-total">—</div></div>
    <div class="stat-card"><div class="lbl">Sinyal BUY</div><div class="val" style="color:#4ade80" id="s-buy">—</div></div>
    <div class="stat-card"><div class="lbl">Watchlist Tersimpan</div><div class="val" style="color:#fbbf24" id="s-wl">—</div></div>
    <div class="stat-card"><div class="lbl">Skor Tertinggi</div><div class="val" style="color:#60a5fa" id="s-top">—</div></div>
    <div class="stat-card"><div class="lbl">Kas Virtual</div><div class="val" style="color:#a78bfa" id="s-cash">—</div></div>
  </div>

  <div class="two-col">
    <div class="card" id="score-card" style="display:none">
      <h3>Skor Fundamental (klik bar untuk detail)</h3>
      <canvas id="scoreChart" height="160"></canvas>
    </div>
    <div class="card" id="action-card" style="display:none">
      <h3>Distribusi Sinyal</h3>
      <canvas id="actionChart" height="160"></canvas>
    </div>
  </div>

  <div id="detail-panel" class="card">
    <div id="detail-content"></div>
    <div id="pred-cards-section" style="display:none;margin-top:1rem">
      <h3 style="font-size:.8rem;color:var(--sub);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.75rem">Prediksi Multi-Metode & Multi-Timeframe</h3>
      <div class="pred-grid" id="pred-cards"></div>
    </div>
    <div id="news-section" style="display:none;margin-top:1rem;background:#0f172a;padding:1rem;border-radius:8px;border:1px solid var(--border)">
      <h3 style="font-size:.8rem;color:var(--sub);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.75rem">Sentimen Berita Terbaru (Yahoo Finance)</h3>
      <ul id="news-list" style="margin:0;padding-left:1.2rem;font-size:.85rem;color:#e2e8f0;line-height:1.6"></ul>
    </div>
    <div style="margin-top:1rem">
      <div id="price-chart-info" style="display:none">
        <h3 style="font-size:.8rem;color:var(--sub);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.75rem">Analisis Teknikal — 6 Bulan + Prediksi (Regresi Linear)</h3>
        <div id="ta-badges"></div>
        <canvas id="priceChart" height="110"></canvas>
      </div>
    </div>
  </div>

  <!-- Rekomendasi Pintar Panel -->
  <div class="card" id="rekomendasi-panel" style="display:none;margin-bottom:1.5rem;border:1px solid #8b5cf6">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
      <h2 style="font-size:1.1rem;color:#c4b5fd">🎯 Rekomendasi Pintar (Auto Trading Plan)</h2>
      <button onclick="document.getElementById('rekomendasi-panel').style.display='none'" style="background:none;border:none;color:var(--sub);cursor:pointer;font-size:1.2rem">✕</button>
    </div>
    <div id="rekomendasi-content" style="font-size:.9rem"></div>
  </div>

  <div class="table-wrap" id="table-wrap" style="display:none">
    <table id="result-table">
      <thead>
        <tr>
          <th style="width:30px">★</th>
          <th onclick="sortBy('ticker')">Ticker</th>
          <th onclick="sortBy('company_name')">Nama</th>
          <th onclick="sortBy('price')">Harga (Rp)</th>
          <th onclick="sortBy('fundamental_score')">Skor</th>
          <th onclick="sortBy('mos')">MoS%</th>
          <th onclick="sortBy('confidence_score')">Confidence</th>
          <th onclick="sortBy('action')">Sinyal</th>
          <th onclick="sortBy('lots')">Lots</th>
          <th onclick="sortBy('risk')">Risiko</th>
        </tr>
      </thead>
      <tbody id="table-body"></tbody>
    </table>
  </div>
</div>

<script>
let allResults = [];
let sortState = { col: 'fundamental_score', asc: false };
let scoreChart = null, actionChart = null, priceChart = null;
let savedWatchlist = [];  // [{ticker, company_name}] — synced from backend

const fmt = n => n != null ? Number(n).toLocaleString('id-ID') : '—';
const fmtB = n => n >= 1e12 ? (n/1e12).toFixed(1)+'T' : n >= 1e9 ? (n/1e9).toFixed(1)+'M' : fmt(n);
const mosColor = v => v > 20 ? '#4ade80' : v > 0 ? '#fb923c' : '#f87171';

// Load watchlist on startup
(async () => {
  try {
    const data = await fetch('/api/watchlist').then(r=>r.json());
    savedWatchlist = data;
    renderWatchlistChips();
    updateWatchlistBadge();
  } catch(_) {}
})();

function setSpinner(on, text = 'Memindai...') {
  document.getElementById('spinner').classList.toggle('active', on);
  document.getElementById('spinner-text').textContent = text;
}

async function scanAll(type) {
  setSpinner(true, type === 'gems' ? 'Mengambil daftar saham IDX terkini & memilih 25 acak...' : 'Auto-Scan LQ45...');
  document.getElementById('detail-panel').style.display = 'none';
  document.getElementById('gems-info').style.display = 'none';
  try {
    const res = await fetch(`/api/scan-all?type=${type}`);
    if (!res.ok) throw new Error('Gagal memuat data');
    allResults = await res.json();
    renderAll(allResults);
    if (type === 'gems') {
      // Show data source metadata
      const status = await fetch('/api/gems-status').then(r => r.json());
      document.getElementById('gems-source').textContent = status.source;
      document.getElementById('gems-total').textContent = status.total_tickers_cached;
      document.getElementById('gems-info').style.display = 'block';
    }
  } catch(e) { alert('Error: ' + e.message); }
  finally { setSpinner(false); }
}

async function scanOne() {
  const t = document.getElementById('ticker').value.trim();
  if (!t) return alert('Masukkan kode saham!');
  setSpinner(true, `Menganalisa ${t.toUpperCase()}...`);
  try {
    const res = await fetch(`/api/scan?ticker=${t}`);
    if (!res.ok) throw new Error((await res.json()).detail);
    const data = await res.json();
    allResults = [data];
    renderAll(allResults);
    showDetail(data);
  } catch(e) { alert('Error: ' + e.message); }
  finally { setSpinner(false); }
}

async function loadPortfolio() {
  const data = await fetch('/api/portfolio').then(r=>r.json());
  const panel = document.getElementById('detail-panel');
  panel.style.display = 'block';
  const holdings = Object.entries(data.holdings || {}).map(([k,v]) =>
    `<div class="di"><div class="dk">${k}</div><div class="dv">${v.lots} lots @ Rp ${fmt(v.avg_price)}</div></div>`
  ).join('') || '<p style="color:var(--sub);font-size:.85rem">Belum ada posisi aktif.</p>';
  document.getElementById('detail-content').innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem">
      <h3>Portfolio Virtual</h3>
    </div>
    <div class="detail-grid">
      <div class="di"><div class="dk">Kas Tersedia</div><div class="dv" style="color:#a78bfa">Rp ${fmtB(data.cash_balance_idr)}</div></div>
      <div class="di"><div class="dk">Total Order Eksekusi</div><div class="dv">${data.total_orders_executed}</div></div>
    </div>
    <div class="detail-grid">${holdings}</div>`;
  document.getElementById('price-chart-info').style.display = 'none';
}

function renderAll(results) {
  renderChart(results);
  renderActionChart(results);
  renderTable(results);
  updateStats(results);
}

// ─── SORT ───────────────────────────────────────────────────────────────────
function sortBy(col) {
  if (sortState.col === col) sortState.asc = !sortState.asc;
  else { sortState.col = col; sortState.asc = col === 'ticker' || col === 'company_name'; }
  document.querySelectorAll('thead th').forEach(th => th.classList.remove('sorted-asc','sorted-desc'));
  const idx = ['ticker','company_name','price','fundamental_score','mos','confidence_score','action','lots','risk'];
  const th = document.querySelectorAll('thead th')[idx.indexOf(col)];
  if (th) th.classList.add(sortState.asc ? 'sorted-asc' : 'sorted-desc');

  const keyOf = r => ({
    ticker: r.ticker, company_name: r.company_name||'',
    price: r.execution_details?.target_price||0,
    fundamental_score: r.fundamental_score,
    mos: r.valuation_summary?.margin_of_safety_percentage||0,
    confidence_score: r.confidence_score,
    action: r.action,
    lots: r.execution_details?.calculated_lots||0,
    risk: r.risk_assessment||''
  })[col] ?? '';

  const sorted = [...allResults].sort((a,b) => {
    const av = keyOf(a), bv = keyOf(b);
    if (typeof av === 'number') return sortState.asc ? av-bv : bv-av;
    return sortState.asc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });
  renderTable(sorted, false);
}

// ─── TABLE ───────────────────────────────────────────────────────────────────
function renderTable(results, updateSort = true) {
  document.getElementById('table-wrap').style.display = 'block';
  const wlSet = new Set(savedWatchlist.map(w => w.ticker));
  document.getElementById('table-body').innerHTML = results.map((r,i) => {
    const mos = r.valuation_summary?.margin_of_safety_percentage ?? 0;
    const isGem = r.is_gem ? '<span class="gem-badge">GEM</span>' : '';
    const t = r.ticker.replace('.JK','');
    const starred = wlSet.has(t) ? 'saved' : '';
    return `<tr onclick="showDetail(${i})" id="row-${i}">
      <td onclick="event.stopPropagation()"><button class="star-btn ${starred}" onclick="toggleStar('${t}','${(r.company_name||'').replace(/'/g,'')}')" title="Simpan ke Watchlist">★</button></td>
      <td><b>${t}</b>${isGem}</td>
      <td style="color:var(--sub);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${r.company_name||'—'}</td>
      <td>${fmt(r.execution_details?.target_price)}</td>
      <td><div class="pb-wrap"><div class="pb" style="width:${r.fundamental_score}%"></div></div> <span style="font-size:.8rem">${r.fundamental_score}</span></td>
      <td style="color:${mosColor(mos)}">${mos.toFixed(1)}%</td>
      <td>${r.confidence_score}%</td>
      <td><span class="action ${r.action}">${r.action}</span></td>
      <td>${r.execution_details?.calculated_lots??0}</td>
      <td><span class="risk ${r.risk_assessment}">${(r.risk_assessment||'').replace('_',' ')}</span></td>
    </tr>`;
  }).join('');
  window._results = results;
}

// ─── CHARTS ─────────────────────────────────────────────────────────────────
function renderChart(results) {
  const sorted = [...results].sort((a,b)=>b.fundamental_score-a.fundamental_score).slice(0,20);
  const labels = sorted.map(r=>r.ticker.replace('.JK',''));
  const scores = sorted.map(r=>r.fundamental_score);
  const colors = sorted.map(r=>r.action==='BUY'?'#4ade80':r.action==='WATCHLIST'?'#fb923c':r.action==='HOLD'?'#60a5fa':'#4b5563');
  document.getElementById('score-card').style.display='block';
  const ctx = document.getElementById('scoreChart').getContext('2d');
  if (scoreChart) scoreChart.destroy();
  scoreChart = new Chart(ctx,{
    type:'bar',
    data:{labels,datasets:[{data:scores,backgroundColor:colors,borderRadius:4}]},
    options:{
      onClick:(e,el)=>{ if(el.length){ const r=sorted[el[0].index]; showDetailDirect(r); } },
      plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`Skor: ${c.raw}`}}},
      scales:{
        x:{ticks:{color:'#94a3b8',font:{size:10}},grid:{color:'#1e293b'}},
        y:{min:0,max:100,ticks:{color:'#94a3b8'},grid:{color:'#1e293b'}}
      }
    }
  });
}

function renderActionChart(results) {
  const counts = results.reduce((acc,r)=>{acc[r.action]=(acc[r.action]||0)+1;return acc;},{});
  const labels = Object.keys(counts);
  const data = Object.values(counts);
  const colorMap = {BUY:'#4ade80',WATCHLIST:'#fb923c',HOLD:'#60a5fa',PASS:'#4b5563',SELL:'#f87171'};
  document.getElementById('action-card').style.display='block';
  const ctx = document.getElementById('actionChart').getContext('2d');
  if (actionChart) actionChart.destroy();
  actionChart = new Chart(ctx,{
    type:'doughnut',
    data:{labels,datasets:[{data,backgroundColor:labels.map(l=>colorMap[l]||'#666'),borderWidth:0}]},
    options:{
      plugins:{legend:{labels:{color:'#94a3b8',font:{size:11}}}},
      cutout:'65%'
    }
  });
}

// ─── DETAIL PANEL ────────────────────────────────────────────────────────────
function showDetail(idx) {
  const r = window._results?.[idx];
  if (!r) return;
  showDetailDirect(r);
}

async function showDetailDirect(r) {
  document.querySelectorAll('tbody tr').forEach(tr=>tr.classList.remove('active-row'));

  const ex = r.execution_details||{}, vs = r.valuation_summary||{};
  const mos = vs.margin_of_safety_percentage||0;
  const isGem = r.is_gem ? '<span class="gem-badge" style="font-size:.8rem">Hidden Gem</span>' : '';

  const inWl = savedWatchlist.some(w => w.ticker === r.ticker.replace('.JK',''));
  window._currentDetailTicker = r.ticker.replace('.JK','');

  document.getElementById('detail-content').innerHTML = `
    <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.9rem;flex-wrap:wrap">
      <h3 style="font-size:1rem">${r.ticker} — ${r.company_name||''}</h3>
      <span class="action ${r.action}" style="font-size:.8rem">${r.action}</span>
      ${isGem}
      <span class="risk ${r.risk_assessment}" style="font-size:.75rem">${(r.risk_assessment||'').replace('_',' ')}</span>
      <button id="detail-star-btn" class="star-btn ${inWl?'saved':''}" style="font-size:1rem;opacity:1"
        onclick="toggleStar('${r.ticker.replace('.JK','')}','${(r.company_name||'').replace(/'/g,'')}')"
        title="${inWl?'Hapus dari Watchlist':'Simpan ke Watchlist'}">★ ${inWl?'Tersimpan':'Simpan Watchlist'}</button>
      <a href="https://stockbit.com/symbol/${r.ticker.replace('.JK','')}" target="_blank" style="margin-left:auto;font-size:.75rem;padding:.3rem .6rem;background:#1e293b;border:1px solid var(--border);border-radius:4px;color:var(--sub);text-decoration:none">Cek Bandarmologi (Stockbit) ↗</a>
    </div>
    <div class="detail-grid">
      <div class="di"><div class="dk">Harga Saat Ini</div><div class="dv">Rp ${fmt(ex.target_price)}</div></div>
      <div class="di"><div class="dk">Fair Value</div><div class="dv">Rp ${fmt(vs.fair_value_estimate)}</div></div>
      <div class="di"><div class="dk">Margin of Safety</div><div class="dv" style="color:${mosColor(mos)}">${mos.toFixed(2)}%</div></div>
      <div class="di"><div class="dk">Skor Fundamental</div><div class="dv">${r.fundamental_score}/100</div></div>
      <div class="di"><div class="dk">Confidence</div><div class="dv">${r.confidence_score}%</div></div>
      <div class="di"><div class="dk">Stop Loss</div><div class="dv" style="color:#f87171">Rp ${fmt(ex.stop_loss_price)}</div></div>
      <div class="di"><div class="dk">Take Profit</div><div class="dv" style="color:#4ade80">Rp ${fmt(ex.take_profit_price)}</div></div>
      <div class="di"><div class="dk">Lot Direkomendasikan</div><div class="dv">${ex.calculated_lots} lots</div></div>
      <div class="di"><div class="dk">Est. Biaya Beli</div><div class="dv">Rp ${fmtB(ex.estimated_cost_idr)}</div></div>
    </div>
    <p style="font-size:.65rem;color:var(--sub);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.4rem">Analisis Rationale</p>
    <ul class="rationale-list">${(r.analysis_rationale||[]).map(x=>`<li>${x}</li>`).join('')}</ul>`;

  const panel = document.getElementById('detail-panel');
  panel.style.display = 'block';
  document.getElementById('price-chart-info').style.display = 'none';
  document.getElementById('pred-cards-section').style.display = 'none';
  document.getElementById('news-section').style.display = 'none';
  panel.scrollIntoView({behavior:'smooth',block:'start'});

  // Load technical chart + multi-timeframe predictions
  try {
    const hist = await fetch(`/api/history?ticker=${r.ticker.replace('.JK','')}`).then(r=>r.json());
    if (!hist.dates || hist.dates.length === 0) return;

    // ── Render prediction cards ───────────────────────────────────────────
    if (hist.predictions) renderPredictionCards(hist.predictions);
    
    // ── Render news ───────────────────────────────────────────────────────
    if (hist.news && hist.news.length > 0) {
      document.getElementById('news-section').style.display = 'block';
      document.getElementById('news-list').innerHTML = hist.news.map(n => 
        `<li style="margin-bottom:.5rem"><a href="${n.link}" target="_blank" style="color:#60a5fa;text-decoration:none">${n.title}</a> <span style="font-size:.7rem;color:var(--sub)">— ${n.publisher}</span></li>`
      ).join('');
    } else {
      document.getElementById('news-section').style.display = 'none';
    }

    // ── Technical Analysis Badges ─────────────────────────────────────────
    const rsi = hist.current_rsi || 50;
    const rsiColor = rsi < 30 ? '#4ade80' : rsi > 70 ? '#f87171' : '#fb923c';
    const rsiLabel = rsi < 30 ? 'Oversold (Potensi Naik)' : rsi > 70 ? 'Overbought (Hati-hati)' : 'Netral';
    const trendColor = hist.trend === 'BULLISH' ? '#4ade80' : hist.trend === 'BEARISH' ? '#f87171' : '#94a3b8';
    const macdColor = hist.macd_signal === 'BULLISH' ? '#4ade80' : '#f87171';
    const predPct = hist.pct_change_predicted || 0;
    const predColor = predPct >= 0 ? '#4ade80' : '#f87171';
    const predSign = predPct >= 0 ? '+' : '';

    document.getElementById('price-chart-info').style.display = 'block';
    // Insert technical badges before the canvas
    const volColor = hist.volume_trend && hist.volume_trend.includes('LONJAKAN') ? '#4ade80' : hist.volume_trend && hist.volume_trend.includes('SEPI') ? '#f87171' : '#94a3b8';

    document.getElementById('ta-badges').innerHTML = `
      <div style="display:flex;gap:.6rem;flex-wrap:wrap;margin-bottom:.9rem">
        <div class="di" style="padding:.5rem .75rem;flex:0 1 auto">
          <div class="dk">Trend Harga</div>
          <div class="dv" style="color:${trendColor}">${hist.trend}</div>
        </div>
        <div class="di" style="padding:.5rem .75rem;flex:0 1 auto">
          <div class="dk">Volume</div>
          <div class="dv" style="color:${volColor}">${hist.volume_trend || 'N/A'}</div>
        </div>
        <div class="di" style="padding:.5rem .75rem;flex:0 1 auto">
          <div class="dk">Support - Resist (60h)</div>
          <div class="dv" style="color:var(--sub)">Rp ${fmt(hist.support)} - Rp ${fmt(hist.resistance)}</div>
        </div>
        <div class="di" style="padding:.5rem .75rem;flex:0 1 auto">
          <div class="dk">RSI 14</div>
          <div class="dv" style="color:${rsiColor}">${rsi} — ${rsiLabel}</div>
        </div>
        <div class="di" style="padding:.5rem .75rem;flex:0 1 auto">
          <div class="dk">MACD</div>
          <div class="dv" style="color:${macdColor}">${hist.macd_signal}</div>
        </div>
      </div>`;

    // ── Price Chart with MA + Prediction ─────────────────────────────────
    const ctx = document.getElementById('priceChart').getContext('2d');
    if (priceChart) priceChart.destroy();
    const closes = hist.closes;
    const lastClose = closes.filter(v=>v!==null).slice(-1)[0];
    const firstClose = closes.find(v=>v!==null);
    const mainColor = lastClose >= firstClose ? '#4ade80' : '#f87171';

    priceChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: hist.dates,
        datasets: [
          {
            label: 'Harga',
            data: hist.closes,
            borderColor: mainColor,
            backgroundColor: mainColor + '10',
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.3,
            order: 1,
          },
          {
            label: 'MA20',
            data: hist.ma20,
            borderColor: '#f59e0b',
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            borderDash: [4, 3],
            order: 2,
          },
          {
            label: 'MA50',
            data: hist.ma50,
            borderColor: '#60a5fa',
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
            borderDash: [4, 3],
            order: 3,
          },
          {
            label: 'Prediksi (Regresi)',
            data: hist.prediction,
            borderColor: '#c084fc',
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: '#c084fc',
            fill: false,
            tension: 0.2,
            borderDash: [6, 4],
            order: 0,
          },
        ]
      },
      options: {
        plugins: {
          legend: {
            display: true,
            labels: { color: '#94a3b8', font: { size: 10 }, boxWidth: 20 }
          },
          tooltip: {
            mode: 'index', intersect: false,
            callbacks: {
              label: c => c.raw !== null ? `${c.dataset.label}: Rp ${Number(c.raw).toLocaleString('id-ID')}` : null
            }
          }
        },
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { ticks: { color: '#94a3b8', maxTicksLimit: 9, font: { size: 10 } }, grid: { color: '#1e293b' } },
          y: {
            ticks: { color: '#94a3b8', callback: v => 'Rp ' + Number(v).toLocaleString('id-ID') },
            grid: { color: '#1e293b' }
          }
        }
      }
    });
  } catch(_) { /* chart data unavailable */ }
}

async function loadPortfolio() {
  const data = await fetch('/api/portfolio').then(r=>r.json());
  const panel = document.getElementById('detail-panel');
  panel.style.display = 'block';
  document.getElementById('price-chart-info').style.display = 'none';
  const holdings = Object.entries(data.holdings || {}).map(([k,v]) =>
    `<div class="di"><div class="dk">${k}</div><div class="dv">${v.lots} lots @ Rp ${fmt(v.avg_price)}</div></div>`
  ).join('') || '<p style="color:var(--sub);font-size:.85rem">Belum ada posisi aktif.</p>';

  document.getElementById('detail-content').innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem;flex-wrap:wrap;gap:.5rem">
      <h3>Portfolio Virtual</h3>
    </div>
    <div class="detail-grid">
      <div class="di">
        <div class="dk">Kas Tersedia</div>
        <div class="dv" style="color:#a78bfa" id="cash-display">Rp ${fmtB(data.cash_balance_idr)}</div>
        <div style="display:flex;gap:.4rem;margin-top:.6rem;align-items:center">
          <input id="cash-input" type="number" placeholder="Nominal baru (Rp)"
            style="background:#0f172a;border:1px solid var(--border);color:var(--text);padding:.3rem .5rem;border-radius:4px;font-size:.78rem;width:160px"
            value="${Math.round(data.cash_balance_idr)}" />
          <button onclick="updateCash()" style="padding:.3rem .7rem;background:#7c3aed;color:#fff;border:none;border-radius:4px;font-size:.78rem;cursor:pointer">Simpan</button>
        </div>
      </div>
      <div class="di"><div class="dk">Total Order Eksekusi</div><div class="dv">${data.total_orders_executed}</div></div>
    </div>
    <div class="detail-grid">${holdings}</div>`;
}

async function updateCash() {
  const val = parseFloat(document.getElementById('cash-input').value);
  if (isNaN(val) || val < 0) return alert('Masukkan nominal yang valid');
  const res = await fetch(`/api/portfolio/cash?amount=${val}`, { method: 'POST' });
  const data = await res.json();
  document.getElementById('cash-display').textContent = 'Rp ' + fmtB(data.cash_balance_idr);
  document.getElementById('s-cash').textContent = 'Rp ' + fmtB(data.cash_balance_idr);
  const btn = document.querySelector('[onclick="updateCash()"]');
  const orig = btn.textContent;
  btn.textContent = '✓ Tersimpan';
  btn.style.background = '#16a34a';
  setTimeout(() => { btn.textContent = orig; btn.style.background = '#7c3aed'; }, 1500);
}

function updateStats(results) {
  document.getElementById('s-total').textContent = results.length;
  document.getElementById('s-buy').textContent = results.filter(r=>r.action==='BUY').length;
  document.getElementById('s-wl').textContent = savedWatchlist.length;
  const top = results.reduce((a,b)=>b.fundamental_score>a.fundamental_score?b:a,{fundamental_score:0});
  document.getElementById('s-top').textContent = (top.ticker||'—').replace('.JK','') + ' ' + (top.fundamental_score||0);
  fetch('/api/portfolio').then(r=>r.json()).then(d=>{
    document.getElementById('s-cash').textContent = 'Rp ' + fmtB(d.cash_balance_idr);
  });
}

// ─── WATCHLIST ────────────────────────────────────────────────────────────────
function updateWatchlistBadge() {
  const el = document.getElementById('wl-count-badge');
  if (el) el.textContent = savedWatchlist.length ? `(${savedWatchlist.length})` : '';
  const wlEl = document.getElementById('s-wl');
  if (wlEl) wlEl.textContent = savedWatchlist.length;
}

function renderWatchlistChips() {
  const el = document.getElementById('wl-chips');
  if (!el) return;
  if (!savedWatchlist.length) { el.textContent = 'Kosong — tambahkan saham dari panel detail atau bintang di tabel.'; return; }
  el.innerHTML = savedWatchlist.map(w => `
    <div class="wl-chip">
      <span style="cursor:pointer;font-weight:600" onclick="scanOneWl('${w.ticker}')">${w.ticker}</span>
      <span style="color:var(--sub);font-size:.72rem">${w.company_name||''}</span>
      <button onclick="removeStar('${w.ticker}')" title="Hapus">✕</button>
    </div>`).join('');
}

function toggleWatchlist() {
  const panel = document.getElementById('wl-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

async function toggleStar(ticker, company_name) {
  const inWl = savedWatchlist.some(w => w.ticker === ticker);
  if (inWl) {
    await fetch(`/api/watchlist/${ticker}`, { method: 'DELETE' });
    savedWatchlist = savedWatchlist.filter(w => w.ticker !== ticker);
  } else {
    const res = await fetch(`/api/watchlist/${ticker}?company_name=${encodeURIComponent(company_name)}`, { method: 'POST' });
    savedWatchlist = await res.json();
  }
  renderWatchlistChips();
  updateWatchlistBadge();
  // Refresh star state in current detail panel if open
  if (window._currentDetailTicker === ticker) {
    const btn = document.getElementById('detail-star-btn');
    if (btn) { btn.classList.toggle('saved', !inWl); btn.title = inWl ? 'Simpan ke Watchlist' : 'Hapus dari Watchlist'; }
  }
  // Re-render table stars without a full re-render
  if (allResults.length) renderTable(window._results || allResults, false);
}

async function removeStar(ticker) { await toggleStar(ticker, ''); }

async function scanOneWl(ticker) {
  document.getElementById('wl-panel').style.display = 'none';
  document.getElementById('ticker').value = ticker;
  await scanOne();
}

async function scanWatchlist() {
  if (!savedWatchlist.length) return alert('Watchlist kosong.');
  setSpinner(true, 'Scan Watchlist...');
  document.getElementById('wl-panel').style.display = 'none';
  try {
    const cash = (await fetch('/api/portfolio').then(r=>r.json())).cash_balance_idr || 1e8;
    const fetchOne = async t => {
      const r = await fetch(`/api/scan?ticker=${t}`);
      return r.ok ? r.json() : null;
    };
    const res = await Promise.all(savedWatchlist.map(w => fetchOne(w.ticker)));
    allResults = res.filter(Boolean);
    renderAll(allResults);
  } catch(e) { alert('Error: ' + e.message); }
  finally { setSpinner(false); }
}

// ─── PREDICTION CARDS ─────────────────────────────────────────────────────────
function renderPredictionCards(predictions) {
  if (!predictions) return;
  const section = document.getElementById('pred-cards-section');
  const container = document.getElementById('pred-cards');
  section.style.display = 'block';

  const labels = { '7d': '7 Hari', '30d': '4 Minggu', '90d': '3 Bulan' };
  const confColor = c => c === 'TINGGI' ? '#4ade80' : c === 'SEDANG' ? '#fb923c' : '#94a3b8';
  const consColor = c => c === 'NAIK' ? '#4ade80' : c === 'TURUN' ? '#f87171' : '#94a3b8';
  const methodLabels = { linear_regression: 'LinReg', ema_trend: 'EMA Trend', rsi_momentum: 'RSI Momentum', bollinger_band: 'Bollinger' };

  container.innerHTML = Object.entries(predictions).map(([key, p]) => {
    const sign = p.pct_change >= 0 ? '+' : '';
    const methods = Object.entries(p.signals).map(([m, s]) =>
      `<span class="m-badge ${s}">${methodLabels[m]||m}: ${s}</span>`
    ).join('');
    return `<div class="pred-card">
      <div class="horizon">${labels[key] || key}</div>
      <div class="consensus" style="color:${consColor(p.consensus)}">${p.consensus}</div>
      <div class="pred-price" style="color:${consColor(p.consensus)}">
        Rp ${fmt(Math.round(p.price))} <span style="font-size:.75rem">(${sign}${p.pct_change}%)</span>
      </div>
      <div style="font-size:.65rem;color:${confColor(p.confidence)};margin-bottom:.4rem">Keyakinan: ${p.confidence}</div>
      <div class="method-row">${methods}</div>
    </div>`;
  }).join('');
}

// ─── AUTO REKOMENDASI PINTAR ────────────────────────────────────────────────
async function showAutoPlan() {
  if (!allResults || allResults.length === 0) {
    alert('Lakukan Scan terlebih dahulu untuk mendapatkan rekomendasi.');
    return;
  }
  
  const pnl = document.getElementById('rekomendasi-panel');
  pnl.style.display = 'block';
  document.getElementById('rekomendasi-content').innerHTML = '<div class="spinner active" style="margin:1rem 0;justify-content:flex-start"><div class="spin"></div><span>Menyusun portofolio...</span></div>';
  pnl.scrollIntoView({behavior:'smooth',block:'start'});
  
  const d = await fetch('/api/portfolio').then(r=>r.json());
  let cash = d.cash_balance_idr;
  
  const buys = allResults.filter(r => r.action === 'BUY')
    .sort((a,b) => b.fundamental_score - a.fundamental_score || b.confidence_score - a.confidence_score)
    .slice(0, 5); // top 5
    
  if (buys.length === 0) {
    document.getElementById('rekomendasi-content').innerHTML = '<p style="color:var(--sub)">Tidak ada saham dengan sinyal BUY kuat di sesi scan saat ini. Tunggu koreksi pasar atau scan kategori lain.</p>';
    return;
  }
  
  let html = `<p style="margin-bottom:1rem;color:var(--sub)">Rekomendasi berdasarkan skor fundamental tertinggi dan Margin of Safety. Sisa Kas: Rp ${fmt(cash)}</p><div style="display:grid;gap:1rem">`;
  
  for (const r of buys) {
    const ex = r.execution_details;
    if (cash < ex.estimated_cost_idr) continue; // skip if cannot afford
    
    // allocate exactly what analyzer suggested
    cash -= ex.estimated_cost_idr;
    
    html += `
      <div style="background:var(--card);padding:1rem;border-radius:8px;border:1px solid var(--border)">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.5rem">
          <div>
            <h3 style="font-size:1.05rem;color:#e2e8f0;margin-bottom:.2rem">${r.ticker} — ${r.company_name}</h3>
            <span class="action BUY" style="font-size:.7rem">Skor: ${r.fundamental_score} | Conf: ${r.confidence_score}%</span>
          </div>
          <div style="text-align:right">
            <div style="font-size:1.1rem;font-weight:600;color:#4ade80">${ex.calculated_lots} Lot</div>
            <div style="font-size:.75rem;color:var(--sub)">Est. Rp ${fmtB(ex.estimated_cost_idr)}</div>
          </div>
        </div>
        
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;background:#0f172a;padding:.75rem;border-radius:6px;margin-top:.75rem">
          <div><div style="font-size:.7rem;color:var(--sub)">🎯 Take Profit (TP)</div><div style="color:#4ade80;font-weight:600">Rp ${fmt(ex.take_profit_price)}</div></div>
          <div><div style="font-size:.7rem;color:var(--sub)">🛑 Stop Loss (SL)</div><div style="color:#f87171;font-weight:600">Rp ${fmt(ex.stop_loss_price)}</div></div>
          <div style="grid-column:1/-1;margin-top:.4rem;padding-top:.4rem;border-top:1px solid var(--border)">
            <div style="font-size:.7rem;color:var(--sub)">Estimasi Hold: <b style="color:#c4b5fd">Medium Term (1 - 3 Bulan)</b> untuk mencapai Fair Value.</div>
          </div>
        </div>
      </div>
    `;
  }
  
  html += `</div>`;
  document.getElementById('rekomendasi-content').innerHTML = html;
}

</script>
</body>
</html>"""


# ─── BACKEND HELPERS ──────────────────────────────────────────────────────────
def _scan_one(ticker: str, cash: float, is_gem: bool = False) -> dict:
    try:
        profile = fetch_live_profile(ticker, available_cash=cash)
        result = bot.process_stock(profile)
        result["company_name"] = profile.company_name
        result["is_gem"] = is_gem
        return result
    except Exception as e:
        return {
            "ticker": ticker + ".JK", "company_name": ticker, "action": "PASS",
            "is_gem": is_gem, "fundamental_score": 0, "confidence_score": 0,
            "risk_assessment": "HIGH_RISK", "error": str(e),
            "valuation_summary": {"fair_value_estimate": 0, "margin_of_safety_percentage": 0, "valuation_status": "N/A"},
            "execution_details": {"target_price": 0, "order_type": "LIMIT", "calculated_lots": 0,
                                   "estimated_cost_idr": 0, "stop_loss_price": 0, "take_profit_price": 0},
            "analysis_rationale": [f"Data tidak tersedia: {e}"],
        }


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_PAGE


@app.get("/api/scan-all")
async def scan_all(type: str = "lq45"):
    if type == "gems":
        # Dynamic: fresh random sample from live IDX securities list every call
        watchlist = get_dynamic_gems(exclude=IDX_WATCHLIST, n=25)
        is_gem = True
    elif type == "trending":
        watchlist = get_trending(15)
        is_gem = False
    else:
        watchlist = IDX_WATCHLIST
        is_gem = False

    cash = bot.paper_broker.get_portfolio_status().get("cash_balance_idr", 100_000_000.0)
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [loop.run_in_executor(pool, _scan_one, t, cash, is_gem) for t in watchlist]
        results = list(await asyncio.gather(*futures))
    order = {"BUY": 0, "WATCHLIST": 1, "HOLD": 2, "PASS": 3}
    return sorted(results, key=lambda r: (order.get(r.get("action", "PASS"), 3), -r.get("fundamental_score", 0)))


@app.get("/api/gems-status")
async def gems_status():
    """Returns IDX ticker cache metadata so the UI can show the data source."""
    return cache_status()


@app.get("/api/scan")
async def scan_stock(ticker: str = Query(...)):
    try:
        cash = bot.paper_broker.get_portfolio_status().get("cash_balance_idr", 100_000_000.0)
        profile = fetch_live_profile(ticker, available_cash=cash)
        result = bot.process_stock(profile)
        result["company_name"] = profile.company_name
        result["is_gem"] = False
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/history")
async def get_history(ticker: str = Query(...)):
    """Returns OHLCV + technical indicators + 5-day linear regression prediction."""
    if not ticker.endswith(".JK"):
        ticker += ".JK"
    loop = asyncio.get_event_loop()

    def _fetch():
        import numpy as np
        import pandas as pd

        t_obj = yf.Ticker(ticker)
        hist = t_obj.history(period="6mo", interval="1d")
        if hist.empty or len(hist) < 5:
            return {"dates": [], "closes": [], "error": "No data"}
            
        try:
            raw_news = t_obj.news or []
            news = [{"title": n.get("title",""), "publisher": n.get("publisher",""), "link": n.get("link","")} for n in raw_news[:5]]
        except:
            news = []

        s = hist["Close"].astype(float)
        dates = hist.index.strftime("%d %b").tolist()
        closes = [round(float(v), 2) for v in s]

        # Moving Averages
        ma20 = [None if pd.isna(v) else round(float(v), 2) for v in s.rolling(20).mean()]
        ma50 = [None if pd.isna(v) else round(float(v), 2) for v in s.rolling(50).mean()]

        # Support & Resistance (60-day Lookback)
        recent_60 = s.tail(60)
        resistance = float(recent_60.max())
        support = float(recent_60.min())

        # Volume Trend
        v = hist["Volume"].astype(float)
        v_ma20 = v.rolling(20).mean()
        vol_status = "NORMAL"
        if not v.empty and not v_ma20.empty and pd.notna(v_ma20.iloc[-1]) and v_ma20.iloc[-1] > 0:
            if v.iloc[-1] > v_ma20.iloc[-1] * 1.5:
                vol_status = "LONJAKAN (Validasi Kuat)"
            elif v.iloc[-1] < v_ma20.iloc[-1] * 0.5:
                vol_status = "SEPI (Rawan Fakeout)"

        # RSI 14
        delta = s.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi_s = (100 - (100 / (1 + rs))).round(1)
        rsi = [None if pd.isna(v) else float(v) for v in rsi_s]
        current_rsi = next((v for v in reversed(rsi) if v is not None), 50.0)

        # MACD (12, 26, 9)
        ema12 = s.ewm(span=12, adjust=False).mean()
        ema26 = s.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_cross = "BULLISH" if float(macd_line.iloc[-1]) > float(macd_signal_line.iloc[-1]) else "BEARISH"
        macd_histogram = [round(float(m - sig), 2) for m, sig in zip(macd_line, macd_signal_line)]


        # Linear Regression: fit on last 20 data points, project 5 days forward
        n = min(20, len(closes))
        x_fit = np.arange(n)
        y_fit = np.array(closes[-n:], dtype=float)
        slope, intercept = np.polyfit(x_fit, y_fit, 1)

        # Trend based on slope relative to price level
        pct_slope = slope / float(closes[-1]) * 100
        if pct_slope > 0.15:
            trend = "BULLISH"
        elif pct_slope < -0.15:
            trend = "BEARISH"
        else:
            trend = "SIDEWAYS"

        # Prediction: last actual close + 5 future points
        pred_y = [round(float(slope * (n + i) + intercept), 2) for i in range(0, 6)]
        # Build extended labels: original + 5 new trading days
        ext_dates = dates + [f"+{i}h" for i in range(1, 6)]
        # Close data extended with None for future
        ext_closes = closes + [None] * 5
        ext_ma20 = ma20 + [None] * 5
        ext_ma50 = ma50 + [None] * 5
        # Prediction dataset: None until last close, then predicted values
        pred_dataset = [None] * (len(closes) - 1) + pred_y

        # Multi-Timeframe Predictions (7d, 30d, 90d)
        curr = float(closes[-1])
        std_dev = float(s.std())
        
        def project(days):
            # 1. LinReg on recent 'days' window (or max available)
            w = min(days * 2, len(closes))
            if w < 5: return {"price": curr, "pct": 0, "cons": "NETRAL", "conf": "RENDAH", "sigs": {}}
            y_w = np.array(closes[-w:], dtype=float)
            x_w = np.arange(w)
            slp, incpt = np.polyfit(x_w, y_w, 1)
            lr_pred = slp * (w + days) + incpt
            
            # 2. EMA Trend projection
            ema = float(s.ewm(span=min(days, len(closes)), adjust=False).mean().iloc[-1])
            ema_pred = curr + (curr - ema) * 0.5 # Mean reversion/momentum blend
            
            # 3. RSI Momentum
            rsi_factor = 1.0 + ((50 - current_rsi) / 100.0) * (days / 30.0)
            rsi_pred = curr * rsi_factor
            
            # 4. Bollinger Band mean reversion (if overextended)
            bb_mid = float(s.rolling(min(20, len(closes))).mean().iloc[-1])
            bb_pred = bb_mid if abs(curr - bb_mid) > std_dev else curr
            
            # Blend
            weights = [0.4, 0.3, 0.2, 0.1]
            preds = [lr_pred, ema_pred, rsi_pred, bb_pred]
            final_price = sum(p * w for p, w in zip(preds, weights))
            
            pct = round(((final_price - curr) / curr) * 100, 2)
            cons = "NAIK" if pct > 1 else "TURUN" if pct < -1 else "NETRAL"
            
            # Confidence based on signal alignment
            lr_sig = "NAIK" if lr_pred > curr else "TURUN"
            ema_sig = "NAIK" if ema_pred > curr else "TURUN"
            rsi_sig = "NAIK" if rsi_pred > curr else "TURUN"
            bb_sig = "NAIK" if bb_pred > curr else "TURUN"
            
            sigs = [lr_sig, ema_sig, rsi_sig, bb_sig]
            aligned = sigs.count(cons)
            conf = "TINGGI" if aligned >= 3 else "SEDANG" if aligned == 2 else "RENDAH"
            if cons == "NETRAL": conf = "RENDAH"
            
            return {
                "price": round(final_price, 2),
                "pct_change": pct,
                "consensus": cons,
                "confidence": conf,
                "signals": {
                    "linear_regression": lr_sig,
                    "ema_trend": ema_sig,
                    "rsi_momentum": rsi_sig,
                    "bollinger_band": bb_sig
                }
            }
            
        predictions = {
            "7d": project(7),
            "30d": project(30),
            "90d": project(90)
        }

        return {
            "dates": ext_dates,
            "closes": ext_closes,
            "ma20": ext_ma20,
            "ma50": ext_ma50,
            "rsi": rsi,
            "current_rsi": round(current_rsi, 1),
            "macd_signal": macd_cross,
            "macd_histogram": macd_histogram,
            "trend": trend,
            "support": support,
            "resistance": resistance,
            "volume_trend": vol_status,
            "prediction": pred_dataset,  # Keep 5d chart line
            "predicted_price_5d": pred_y[-1],
            "pct_change_predicted": round((pred_y[-1] - closes[-1]) / closes[-1] * 100, 2),
            "predictions": predictions,
            "news": news
        }

    return await loop.run_in_executor(None, _fetch)

# ─── WATCHLIST API ────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
async def get_watchlist():
    return wl_store.load()

@app.post("/api/watchlist/{ticker}")
async def add_watchlist(ticker: str, company_name: str = ""):
    return wl_store.add(ticker, company_name)

@app.delete("/api/watchlist/{ticker}")
async def remove_watchlist(ticker: str):
    return wl_store.remove(ticker)



@app.get("/api/portfolio")
async def get_portfolio():
    return bot.paper_broker.get_portfolio_status()


@app.post("/api/portfolio/cash")
async def update_cash(amount: float = Query(..., description="New cash balance in IDR")):
    if amount < 0:
        raise HTTPException(status_code=400, detail="Nominal kas tidak boleh negatif")
    bot.paper_broker.cash_balance = amount
    bot.paper_broker.settled_cash = amount
    bot.paper_broker.save()
    return {"status": "updated", "cash_balance_idr": amount}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
