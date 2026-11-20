'use strict';
const PAGES = {
  dashboard: ['Dashboard', 'bi-speedometer2', pDashboard], datasets: ['Dataset Management', 'bi-database', pDatasets, true], eda: ['Data Analysis', 'bi-clipboard-data', pEda],
  predict: ['Price Prediction', 'bi-graph-up-arrow', pPredict], trends: ['Market Trends', 'bi-activity', pTrends], demand: ['Demand & Supply', 'bi-arrow-left-right', pDemand],
  optimize: ['Price Optimization', 'bi-magic', pOptimize], competitors: ['Competitor Analysis', 'bi-shop', pComp], profit: ['Profit Analysis', 'bi-cash-coin', pProfit],
  reports: ['Reports', 'bi-file-earmark-bar-graph', pReports], settings: ['Settings', 'bi-gear', pSettings, true],
};
$('#nav').innerHTML = Object.entries(PAGES).map(([k, [t, i]]) => `<a href="#/${k}" data-k="${k}"><i class="bi ${i}"></i>${t}</a>`).join('');

async function refreshMeta() {
  state.meta = await api('/meta'); CUR = state.meta.currency;
  if (state.meta.user) { $('#uName').textContent = state.meta.user.name; $('#uRole').textContent = state.meta.user.role; $('#avatar').textContent = state.meta.user.name[0]; }
  if (!state.meta.products.some(p => String(p.id) === String(state.product))) state.product = '';
}

async function route() {
  document.body.classList.remove('nav-open'); killCharts();
  const key = (location.hash || '#/dashboard').slice(2).split('?')[0];
  const [title, , fn, noData] = PAGES[key] || PAGES.dashboard, k = PAGES[key] ? key : 'dashboard';
  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.k === k));
  document.title = `${title} · Price Optimization System`;
  view().innerHTML = loading();
  try {
    if (!state.meta) await refreshMeta();
    if (!state.meta.dataset && !noData) { view().innerHTML = empty('bi-database-x', 'No dataset loaded', 'Load the built-in sample dataset or upload your own CSV/Excel file to start.', '<a class="btn btn-royal" href="#/datasets">Go to Dataset Management</a>'); return; }
    await fn();
  } catch (e) { view().innerHTML = errBox(e.message); }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
$('#menuBtn').onclick = () => document.body.classList.toggle('nav-open');
$('#scrim').onclick = () => document.body.classList.remove('nav-open');

/* global search */
let st; const gs = $('#gsearch'), gr = $('#gresults');
gs.addEventListener('input', () => {
  clearTimeout(st); const v = gs.value.trim();
  if (!v) { gr.classList.remove('show'); return; }
  st = setTimeout(async () => {
    try { const r = await api('/search?q=' + encodeURIComponent(v));
      gr.innerHTML = r.length ? r.map(p => `<a class="dropdown-item" href="#/predict" data-id="${p.id}">${esc(p.name)} <small class="text-muted">${esc(p.code)}</small></a>`).join('') : '<span class="dropdown-item-text note">No matching products</span>';
      gr.classList.add('show'); $$('a', gr).forEach(a => a.onclick = () => { state.product = a.dataset.id; gr.classList.remove('show'); gs.value = ''; if (location.hash === '#/predict') route(); });
    } catch (e) { /* ignore search errors */ }
  }, 200);
});
document.addEventListener('click', e => { if (!e.target.closest('.search')) gr.classList.remove('show'); });

/* notifications */
$('#bellBtn').addEventListener('show.bs.dropdown', async () => {
  const m = $('#bellMenu'); m.innerHTML = '<div class="p-3 note">Loading…</div>';
  try { const n = await api('/notifications'); const ic = { warning: 'bi-exclamation-triangle text-warning', info: 'bi-info-circle text-primary', danger: 'bi-arrow-down-right-circle text-danger', success: 'bi-arrow-up-right-circle text-success' };
    m.innerHTML = `<div class="p-2 px-3 fw-semibold border-bottom">Market alerts</div>` + (n.length ? n.map(x => `<div class="notif"><i class="bi ${ic[x.level]}"></i><span>${esc(x.text)}</span></div>`).join('') : '<div class="p-3 note">No alerts.</div>');
    $('#bellDot').classList.add('d-none');
  } catch (e) { m.innerHTML = `<div class="p-3 note">${esc(e.message)}</div>`; }
});

(async function init() {
  try { await refreshMeta(); if (state.meta.dataset) { const n = await api('/notifications'); if (n.length) $('#bellDot').classList.remove('d-none'); } } catch (e) { /* shown by route */ }
  route();
})();
