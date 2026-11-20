'use strict';
/* ================= Dashboard ================= */
async function pDashboard() {
  const d = await api('/dashboard'), k = d.kpis;
  const pc = k.predicted_price_change_pct;
  view().innerHTML = head('Dashboard', `Market overview for ${d.dataset.name} · ${d.dataset.date_min} to ${d.dataset.date_max}`) + simBanner(d.dataset) +
    `<div class="kpi-grid">
      ${kpi('Total Products', num(k.total_products), `${k.categories} categories`, 'bi-box-seam')}
      ${kpi('Total Sales', compact(k.total_sales_units) + ' units', `Revenue ${moneyC(k.total_revenue)}`, 'bi-bag-check', 'navy')}
      ${kpi('Average Market Price', money(k.avg_market_price), 'Mean of all products', 'bi-tag', 'orange')}
      ${kpi('Predicted Future Price', `<span class="${tone(pc)}">${pct(pc)}</span>`, 'Avg. change, next 30 days (linear trend model)', 'bi-graph-up-arrow', pc >= 0 ? 'green' : 'red')}
      ${kpi('Average Demand', num(k.avg_demand, 0), 'Units per product per day', 'bi-people')}
      ${kpi('Expected Revenue (30d)', moneyC(k.expected_revenue_30d), `Last 30 days: ${moneyC(k.recent_revenue_30d)}`, 'bi-cash-stack', 'green')}
      ${kpi('Potential Profit (30d)', moneyC(k.potential_profit_30d), `Last 30 days: ${moneyC(k.recent_profit_30d)}`, 'bi-piggy-bank', 'green')}
      ${kpi('Market Trend Status', esc(k.trend_status), `<span class="pos">${k.bullish} bullish</span> · <span class="neg">${k.bearish} bearish</span> · ${k.stable} stable`, 'bi-activity', k.trend_status === 'Bullish' ? 'green' : k.trend_status === 'Bearish' ? 'red' : 'orange')}
    </div>
    <div class="row g-3 mb-3">
      ${panel('Price trend by category (index, first month = 100)', box('c1', 310), 'col-xl-8')}
      ${panel('Revenue share by category', box('c2', 310), 'col-xl-4')}
    </div>
    <div class="row g-3 mb-3">
      ${panel('Sales performance (monthly)', box('c3'), 'col-xl-6')}
      ${panel('Demand vs supply (monthly average per product-day)', box('c4'), 'col-xl-6')}
    </div>
    <div class="row g-3 mb-3">
      ${panel('Category-wise average price', box('c5'), 'col-xl-6')}
      ${panel('Monthly market trend (all products)', box('c6'), 'col-xl-6')}
    </div>
    <div class="row g-3">
      ${panel('Top increasing products (30 days)', table([{ k: 'product_name', label: 'Product' }, { k: 'category', label: 'Category' }, { k: 'last_price', label: 'Price', r: 1, f: v => money(v) }, { k: 'change_30d', label: 'Change', r: 1, f: v => pctHtml(v) }], d.top_increasing), 'col-xl-6')}
      ${panel('Top decreasing products (30 days)', table([{ k: 'product_name', label: 'Product' }, { k: 'category', label: 'Category' }, { k: 'last_price', label: 'Price', r: 1, f: v => money(v) }, { k: 'change_30d', label: 'Change', r: 1, f: v => pctHtml(v) }], d.top_decreasing), 'col-xl-6')}
    </div>`;
  const cats = Object.keys(d.price_trend.series);
  mk('c1', { type: 'line', data: { labels: d.price_trend.labels, datasets: cats.map((c, i) => line(c, d.price_trend.series[c], PAL[i % PAL.length])) }, options: co({ scales: { x: xs(), y: yfmt(v => v.toFixed(0)) } }) });
  mk('c2', { type: 'doughnut', data: { labels: Object.keys(d.category_revenue), datasets: [{ data: Object.values(d.category_revenue), backgroundColor: PAL, borderWidth: 2 }] }, options: co({ interaction: { mode: 'nearest' }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => `${c.label}: ${moneyC(c.parsed)}` } } } }) });
  mk('c3', { type: 'bar', data: { labels: d.sales.labels, datasets: [{ label: 'Revenue', data: d.sales.revenue, backgroundColor: '#2f5bea' }, { label: 'Profit', data: d.sales.profit, backgroundColor: '#16a34a' }] }, options: co({ scales: { x: xs(12), y: yfmt(moneyC) } }) });
  mk('c4', { type: 'line', data: { labels: d.demand_supply.labels, datasets: [line('Demand', d.demand_supply.demand.map((v, i) => v / k.total_products), '#2f5bea'), line('Supply', d.demand_supply.supply.map(v => v / k.total_products), '#f59e0b')] }, options: co({ scales: { x: xs(12), y: yfmt(v => num(v)) } }) });
  mk('c5', { type: 'bar', data: { labels: Object.keys(d.category_price), datasets: [{ label: 'Average price', data: Object.values(d.category_price), backgroundColor: PAL }] }, options: co({ plugins: { legend: { display: false } }, scales: { y: { ...yfmt(moneyC), type: 'logarithmic' }, x: xs() } }) });
  mk('c6', { type: 'line', data: { labels: d.monthly_trend.labels, datasets: [line('Price index', d.monthly_trend.index, '#2f5bea', { fill: true })] }, options: co({ scales: { x: xs(12), y: yfmt(v => v.toFixed(0)) } }) });
}

/* ================= Dataset management ================= */
function reportHtml(rep) {
  const miss = Object.entries(rep.missing_before || {}).map(([c, n]) => ({ c, n }));
  const out = Object.entries(rep.outliers_flagged || {}).map(([c, n]) => ({ c, n }));
  const notes = [...(rep.warnings || []).map(t => ['orange', t]), ...(rep.assumptions || []).map(t => ['blue', t])];
  return `<div class="d-flex align-items-center gap-2 mb-3"><h3 class="h6 m-0">Dataset validation report</h3>${badge(rep.status, rep.status === 'Passed' ? 'green' : 'orange')}</div>
  <div class="row g-2 mb-3">${[['Raw rows', num(rep.rows_raw)], ['Clean rows', num(rep.rows_clean)], ['Products', rep.products], ['Categories', rep.categories], ['Duplicates removed', rep.duplicates_removed],
      ['Invalid dates removed', rep.invalid_dates_removed], ['Invalid values → missing', rep.invalid_values_set_missing], ['Date range', `${rep.date_min} → ${rep.date_max}`]]
      .map(([l, v]) => `<div class="col-6 col-md-3">${mini(l, esc(v))}</div>`).join('')}</div>
  ${notes.length ? `<ul class="ul-clean mb-3">${notes.map(([c, t]) => `<li>${badge(c === 'orange' ? 'Warning' : 'Assumption', c)} ${esc(t)}</li>`).join('')}</ul>` : ''}
  <div class="row g-3"><div class="col-md-6"><div class="note mb-1">Missing values before cleaning (filled by per-product interpolation)</div>${table([{ k: 'c', label: 'Column' }, { k: 'n', label: 'Missing', r: 1 }], miss, { maxH: 260 })}</div>
  <div class="col-md-6"><div class="note mb-1">Outliers flagged (IQR within product, kept in data)</div>${table([{ k: 'c', label: 'Column' }, { k: 'n', label: 'Flagged', r: 1 }], out)}
  ${rep.columns_missing && rep.columns_missing.length ? `<div class="note mt-2">Columns not in file: ${esc(rep.columns_missing.join(', '))}</div>` : ''}${rep.columns_ignored && rep.columns_ignored.length ? `<div class="note">Ignored columns: ${esc(rep.columns_ignored.join(', '))}</div>` : ''}</div></div>`;
}

async function pDatasets() {
  const list = await api('/datasets');
  view().innerHTML = head('Dataset Management', 'Upload CSV or Excel files, validate and clean them, then save to MySQL.',
    `<button class="btn btn-outline-navy btn-sm" id="loadSample"><i class="bi bi-database-add me-1"></i>Load built-in sample dataset</button>`) +
    `<div class="row g-3 mb-3">
      ${panel('Upload dataset', `<div class="dropzone" id="dz" tabindex="0"><i class="bi bi-cloud-arrow-up"></i><div class="fw-semibold mt-2">Drop a CSV or Excel file here, or click to browse</div><div class="note">.csv, .xlsx, .xls · up to 25 MB · required columns: Product Name, Date, Historical Price</div></div><input type="file" id="fileIn" accept=".csv,.xlsx,.xls" hidden>
        <div class="mt-3 note">Need a template? <a href="/api/datasets/sample-file/csv">Download sample CSV</a> · <a href="/api/datasets/sample-file/xlsx">Download sample Excel</a> (simulated data)</div>`, 'col-xl-5')}
      ${panel('Saved datasets', `<div id="dsList"></div>`, 'col-xl-7')}
    </div><div id="analysis"></div><div id="viewer"></div>`;
  renderDsList(list);
  $('#loadSample').onclick = e => busy(e.currentTarget, async () => { await api('/datasets/sample', { method: 'POST' }); toast('Sample dataset loaded.'); await refreshMeta(); pDatasets(); });
  const dz = $('#dz'), fi = $('#fileIn');
  dz.onclick = () => fi.click(); dz.onkeydown = e => { if (e.key === 'Enter') fi.click(); };
  dz.ondragover = e => { e.preventDefault(); dz.classList.add('over'); }; dz.ondragleave = () => dz.classList.remove('over');
  dz.ondrop = e => { e.preventDefault(); dz.classList.remove('over'); if (e.dataTransfer.files[0]) analyse(e.dataTransfer.files[0]); };
  fi.onchange = () => fi.files[0] && analyse(fi.files[0]);
}

function renderDsList(list) {
  $('#dsList').innerHTML = list.length ? table([
    { k: 'name', label: 'Name', f: (v, r) => `<b>${esc(v)}</b> ${r.is_active ? badge('Active', 'green') : ''} ${r.source === 'sample' ? badge('Simulated', 'orange') : ''}` },
    { k: 'rows_clean', label: 'Rows', r: 1, f: v => num(v) }, { k: 'date_min', label: 'From' }, { k: 'date_max', label: 'To' },
    { k: 'id', label: '', f: (v, r) => `<div class="btn-group btn-group-sm"><button class="btn btn-outline-secondary" data-act="view" data-id="${v}" title="View data"><i class="bi bi-table"></i></button><button class="btn btn-outline-secondary" data-act="rep" data-id="${v}" title="Validation report"><i class="bi bi-clipboard-check"></i></button>${r.is_active ? '' : `<button class="btn btn-outline-primary" data-act="on" data-id="${v}" title="Activate"><i class="bi bi-check2-circle"></i></button>`}<button class="btn btn-outline-danger" data-act="del" data-id="${v}" title="Delete"><i class="bi bi-trash"></i></button></div>` }], list)
    : empty('bi-database', 'No datasets yet', 'Load the sample dataset or upload your own file to begin.');
  $$('#dsList [data-act]').forEach(b => b.onclick = async () => {
    const id = b.dataset.id, act = b.dataset.act;
    try {
      if (act === 'view') return viewer(id);
      if (act === 'rep') { const r = await api(`/datasets/${id}/report`); $('#analysis').innerHTML = `<div class="panel mb-3"><div class="panel-b">${reportHtml(r.report)}</div></div>`; return; }
      if (act === 'on') { await api(`/datasets/${id}/activate`, { method: 'POST' }); toast('Dataset activated.'); }
      if (act === 'del') { if (!confirm('Delete this dataset and all its saved data?')) return; await api(`/datasets/${id}`, { method: 'DELETE' }); toast('Dataset deleted.'); }
      await refreshMeta(); pDatasets();
    } catch (e) { toast(e.message, 'error'); }
  });
}

async function viewer(id, page = 1, pid = '') {
  const el = $('#viewer'); el.innerHTML = loading('Loading rows…');
  try {
    const d = await api(`/datasets/${id}/data?${q({ page, page_size: 20, product_id: pid })}`);
    const prods = state.meta.dataset && String(state.meta.dataset.id) === String(id) ? state.meta.products : [];
    el.innerHTML = `<div class="panel"><div class="panel-h"><h3>Cleaned data (stored in database) · ${num(d.total)} rows</h3>
      <select id="vp" class="form-select form-select-sm" style="width:200px"><option value="">All products</option>${prods.map(p => `<option value="${p.id}" ${String(pid) === String(p.id) ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</select></div>
      <div class="panel-b">${rawTable(d.columns, d.rows)}<div class="d-flex justify-content-between align-items-center mt-2"><span class="note">Page ${d.page} of ${d.pages}</span>
      <div class="btn-group btn-group-sm"><button class="btn btn-outline-secondary" id="pp" ${d.page <= 1 ? 'disabled' : ''}>Previous</button><button class="btn btn-outline-secondary" id="np" ${d.page >= d.pages ? 'disabled' : ''}>Next</button></div></div></div></div>`;
    $('#pp').onclick = () => viewer(id, page - 1, pid); $('#np').onclick = () => viewer(id, page + 1, pid);
    $('#vp').onchange = e => viewer(id, 1, e.target.value);
  } catch (e) { el.innerHTML = errBox(e.message); }
}

async function analyse(file) {
  const box = $('#analysis'); box.innerHTML = loading(`Validating and cleaning ${file.name}…`);
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await api('/datasets/upload', { method: 'POST', body: fd });
    box.innerHTML = `<div class="panel mb-3"><div class="panel-b">${reportHtml(r.report)}</div></div>
      <div class="row g-3 mb-3">${panel('Raw file preview (first 10 rows)', rawTable(r.raw_preview.columns, r.raw_preview.rows), 'col-12')}${panel('Cleaned dataset preview (first 15 rows)', rawTable(r.clean_preview.columns, r.clean_preview.rows), 'col-12')}</div>
      <div class="panel mb-3"><div class="panel-b"><h3 class="h6">Save to MySQL</h3><div class="row g-2 align-items-end"><div class="col-md-6"><label class="form-label note">Dataset name</label><input id="dsName" class="form-control" value="${esc(file.name.replace(/\.[^.]+$/, ''))}" maxlength="120" required></div>
      <div class="col-md-6"><button class="btn btn-royal" id="saveBtn"><i class="bi bi-database-check me-1"></i>Save cleaned data &amp; make active</button></div></div></div></div>`;
    $('#saveBtn').onclick = e => {
      const name = $('#dsName').value.trim();
      if (name.length < 2) return toast('Enter a dataset name (at least 2 characters).', 'error');
      busy(e.currentTarget, async () => { const s = await api('/datasets/commit', { json: { token: r.token, name } }); toast(s.message); await refreshMeta(); pDatasets(); });
    };
    box.scrollIntoView({ behavior: 'smooth' });
  } catch (e) { box.innerHTML = errBox(e.message); }
}

/* ================= EDA ================= */
async function pEda() {
  const f = state.pageData.eda || { product: '', category: '' };
  view().innerHTML = head('Data Analysis', 'Exploratory data analysis: statistics, distributions, correlations, seasonality and outliers.') +
    `<div class="filters"><div><label>Category</label><select id="fc" class="form-select">${catOpts(f.category)}</select></div><div><label>Product</label><select id="fp" class="form-select">${prodOpts(f.product, true)}</select></div><button id="go" class="btn btn-royal">Analyse</button></div><div id="out">${loading()}</div>`;
  const run = async () => {
    state.pageData.eda = { product: $('#fp').value, category: $('#fc').value };
    $('#out').innerHTML = loading();
    try { await renderEda(await api('/eda?' + q(state.pageData.eda))); } catch (e) { $('#out').innerHTML = errBox(e.message); }
  };
  $('#go').onclick = run; run();
}
function heat(c) { const a = Math.min(Math.abs(c), 1); return c >= 0 ? `rgba(47,91,234,${a * .85})` : `rgba(220,38,38,${a * .85})`; }
async function renderEda(e) {
  const L = e.correlation.labels.map(l => l.replace('_qty', '').replace('_price', ' price').replace('_', ' '));
  $('#out').innerHTML = (e.scope.note ? `<div class="note mb-2"><i class="bi bi-info-circle"></i> ${esc(e.scope.note)}</div>` : '') +
    `<div class="row g-3 mb-3">${panel(`Descriptive statistics · ${num(e.scope.rows)} rows, ${e.scope.products} product(s)`,
      table([{ k: 'column', label: 'Variable' }, ...['count', 'mean', 'median', 'mode', 'std', 'min', 'q1', 'q3', 'max', 'skew'].map(k => ({ k, label: k === 'q1' ? 'Q1' : k === 'q3' ? 'Q3' : k[0].toUpperCase() + k.slice(1), r: 1, f: v => num(v, k === 'count' ? 0 : 2) }))], e.descriptive), 'col-12')}</div>
    <div class="row g-3 mb-3">${panel('Price distribution (' + esc(e.histogram.unit) + ')', box('e1'), 'col-xl-6')}${panel('Correlation matrix', `<div class="table-responsive"><table class="table table-sm heat"><thead><tr><th></th>${L.map(l => `<th>${esc(l)}</th>`).join('')}</tr></thead><tbody>${e.correlation.matrix.map((r, i) => `<tr><th class="text-start">${esc(L[i])}</th>${r.map(c => `<td style="background:${heat(c)};color:${Math.abs(c) > .5 ? '#fff' : '#16203a'}">${c.toFixed(2)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`, 'col-xl-6')}</div>
    <div class="row g-3 mb-3">${panel('Monthly analysis (price index by calendar month)', box('e2'), 'col-xl-6')}${panel('Seasonal analysis', box('e3'), 'col-xl-6')}</div>
    <div class="row g-3 mb-3">${panel('Category comparison', box('e4', 260) + table([{ k: 'category', label: 'Category' }, { k: 'products', label: 'Products', r: 1 }, { k: 'avg_price', label: 'Avg price', r: 1, f: v => num(v, 2) }, { k: 'avg_volatility_pct', label: 'Volatility %', r: 1, f: v => num(v, 2) }, { k: 'avg_demand', label: 'Avg demand', r: 1, f: v => num(v) }, { k: 'avg_supply', label: 'Avg supply', r: 1, f: v => num(v) }, { k: 'units_sold', label: 'Units sold', r: 1, f: v => compact(v) }], e.categories), 'col-xl-7')}
      ${panel('Outlier detection (1.5 × IQR within each product)', table([{ k: 'column', label: 'Variable' }, { k: 'count', label: 'Outliers', r: 1 }, { k: 'pct', label: '% of rows', r: 1, f: v => num(v, 2) + '%' }], e.outliers) + (e.extreme_outliers.length ? `<div class="note mt-3 mb-1">Most extreme price outliers</div>` + table([{ k: 'product_name', label: 'Product' }, { k: 'date', label: 'Date' }, { k: 'historical_price', label: 'Price', r: 1, f: v => num(v, 2) }, { k: 'deviation_pct', label: 'Dev. from median', r: 1, f: v => num(v, 1) + '%' }], e.extreme_outliers) : '<div class="note mt-2">No price outliers found.</div>'), 'col-xl-5')}</div>
    <div class="row g-3" id="clusterRow"></div>`;
  mk('e1', { type: 'bar', data: { labels: e.histogram.labels, datasets: [{ label: 'Observations', data: e.histogram.counts, backgroundColor: '#2f5bea' }] }, options: co({ plugins: { legend: { display: false } }, scales: { x: xs(8), y: yfmt(v => v) } }) });
  mk('e2', { type: 'bar', data: { labels: e.monthly.labels, datasets: [{ type: 'bar', label: 'Price index', data: e.monthly.price_index, backgroundColor: '#2f5bea', yAxisID: 'y' }, { type: 'line', label: 'Demand', data: e.monthly.demand, borderColor: '#16a34a', yAxisID: 'y1', tension: .3 }, { type: 'line', label: 'Supply', data: e.monthly.supply, borderColor: '#f59e0b', yAxisID: 'y1', tension: .3 }] }, options: co({ scales: { x: xs(12), y: { min: 80, ...yfmt(v => v) }, y1: { position: 'right', grid: { display: false } } } }) });
  mk('e3', { type: 'bar', data: { labels: e.seasonal.labels, datasets: [{ label: 'Price index', data: e.seasonal.price_index, backgroundColor: PAL }] }, options: co({ plugins: { legend: { display: false } }, scales: { y: { min: 80, ...yfmt(v => v) }, x: xs() } }) });
  mk('e4', { type: 'bar', data: { labels: e.categories.map(c => c.category), datasets: [{ label: 'Avg volatility %', data: e.categories.map(c => c.avg_volatility_pct), backgroundColor: '#f59e0b' }] }, options: co({ plugins: { legend: { display: false } }, scales: { y: yfmt(v => v + '%'), x: xs() } }) });
  try {
    const c = await api('/eda/clusters?k=3');
    $('#clusterRow').innerHTML = panel('K-Means product segments (volatility vs margin)', box('e5', 300) + `<div class="note mt-2">Silhouette score: ${c.silhouette == null ? '–' : c.silhouette.toFixed(2)} (closer to 1 = better separated). Features: ${esc(c.features.join(', '))}.</div>`, 'col-xl-7') +
      panel('Segments', c.clusters.map(s => `<div class="mb-2"><b>${esc(s.label)}</b> ${badge(s.size + ' products', 'blue')}<div class="note">${esc(s.members.join(', '))}</div></div>`).join(''), 'col-xl-5');
    mk('e5', { type: 'scatter', data: { datasets: c.clusters.map((s, i) => ({ label: s.label.split(':')[0], backgroundColor: PAL[i], pointRadius: 6, data: c.products.filter(p => p.cluster === s.cluster).map(p => ({ x: p.volatility_pct, y: p.margin_pct, n: p.product_name })) })) }, options: co({ interaction: { mode: 'nearest' }, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: t => `${t.raw.n}: vol ${t.raw.x.toFixed(2)}%, margin ${t.raw.y.toFixed(1)}%` } } }, scales: { x: { title: { display: true, text: 'Daily volatility %' } }, y: { title: { display: true, text: 'Margin %' } } } }) });
  } catch (err) { $('#clusterRow').innerHTML = `<div class="note">Clustering skipped: ${esc(err.message)}</div>`; }
}
