'use strict';
/* ================= Price prediction ================= */
async function pPredict() {
  needProduct();
  const m = state.meta, f = state.pageData.pred || { algo: 'linear_regression', h: 30 };
  view().innerHTML = head('Price Prediction', 'Forecast future market prices with machine learning. Time-series data is split chronologically (80% train / 20% test).') + simBanner(m.dataset) +
    `<div class="filters"><div><label>Product</label><select id="pp" class="form-select">${prodOpts(state.product)}</select></div>
    <div><label>Algorithm</label><select id="pa" class="form-select">${Object.entries(m.algorithms).map(([k, v]) => `<option value="${k}" ${f.algo === k ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></div>
    <div><label>Prediction period</label><select id="ph" class="form-select">${m.horizons.map(h => `<option value="${h}" ${f.h == h ? 'selected' : ''}>${h} days</option>`).join('')}</select></div>
    <button id="go" class="btn btn-royal"><i class="bi bi-lightning-charge me-1"></i>Generate prediction</button>
    <button id="cmp" class="btn btn-outline-navy"><i class="bi bi-bar-chart-steps me-1"></i>Compare all algorithms</button></div>
    <div id="out">${empty('bi-graph-up-arrow', 'Choose a product and generate a prediction', 'The model trains in the backend on this product’s history and forecasts the selected period.')}</div>`;
  $('#pp').onchange = e => state.product = e.target.value;
  $('#go').onclick = e => busy(e.currentTarget, async () => {
    state.pageData.pred = { algo: $('#pa').value, h: +$('#ph').value };
    const r = await api('/predict', { json: { product_id: +$('#pp').value, algorithm: $('#pa').value, horizon: +$('#ph').value } });
    renderPred(r);
  });
  $('#cmp').onclick = e => busy(e.currentTarget, async () => {
    const r = await api('/predict/compare?' + q({ product_id: $('#pp').value, horizon: $('#ph').value }));
    $('#out').innerHTML = panel('Algorithm comparison (chronological test period)', table([{ k: 'label', label: 'Algorithm', f: (v, r, i) => `<b>${esc(v)}</b>` }, { k: 'MAE', label: 'MAE', r: 1, f: v => num(v, 3) }, { k: 'MSE', label: 'MSE', r: 1, f: v => num(v, 3) }, { k: 'RMSE', label: 'RMSE', r: 1, f: v => num(v, 3) }, { k: 'R2', label: 'R²', r: 1, f: v => num(v, 3) }, { k: 'MAPE', label: 'MAPE %', r: 1, f: v => num(v, 2) }, { k: 'predicted_final', label: 'Predicted (end)', r: 1, f: v => money(v) }, { k: 'change_pct', label: 'Change', r: 1, f: v => pctHtml(v) }, { k: 'error', label: 'Note', f: v => v ? esc(v) : '' }], r.rows) + `<div class="note mt-2">${esc(r.note)} Lowest RMSE is best on past data, which does not guarantee the best future accuracy.</div>`);
  });
}
function renderPred(r) {
  const s = r.summary, mt = r.metrics, u = s.direction === 'Increase' ? 'green' : s.direction === 'Decrease' ? 'red' : 'grey';
  const last = r.forecast[r.forecast.length - 1];
  $('#out').innerHTML = `<div class="kpi-grid">
      ${kpi('Last observed price', money(r.last_value), r.last_date, 'bi-clock-history', 'navy')}
      ${kpi(`Predicted price (+${r.horizon}d)`, money(s.predicted_final), `Range ${money(last.lower)} – ${money(last.upper)}`, 'bi-graph-up-arrow', u)}
      ${kpi('Expected change', `<span class="${tone(s.change_pct)}">${pct(s.change_pct)}</span>`, `${s.change_abs >= 0 ? '+' : ''}${money(s.change_abs)} · ${badge(s.direction, u)}`, 'bi-arrow-left-right', u)}
      ${kpi('Forecast range', `${money(s.predicted_min)} – ${money(s.predicted_max)}`, `Mean ${money(s.predicted_mean)}`, 'bi-distribute-vertical', 'orange')}</div>
    <div class="row g-3 mb-3">${panel(`${esc(r.product.name)} · ${esc(r.algorithm_label)}`, box('pc', 380), 'col-xl-8')}
    ${panel('Model evaluation (test period)', table([{ k: 'm', label: 'Metric' }, { k: 'v', label: 'Value', r: 1 }], [{ m: 'MAE', v: num(mt.MAE, 3) }, { m: 'MSE', v: num(mt.MSE, 3) }, { m: 'RMSE', v: num(mt.RMSE, 3) }, { m: 'R²', v: mt.R2 == null ? '–' : num(mt.R2, 3) }, { m: 'MAPE', v: num(mt.MAPE, 2) + '%' }]) +
      `<div class="note mt-3">Chronological split: train ${r.split.train_size} days (${r.split.train_start} → ${r.split.train_end}), test ${r.split.test_size} days (${r.split.test_start} → ${r.split.test_end}). No shuffling.</div>` +
      (r.notes.length ? `<ul class="ul-clean note mt-2">${r.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : ''), 'col-xl-4')}</div>
    <div class="alert alert-warning py-2"><i class="bi bi-exclamation-triangle me-1"></i>${esc(r.disclaimer)}</div>
    ${panel('Forecast table', table([{ k: 'date', label: 'Date' }, { k: 'value', label: 'Predicted', r: 1, f: v => money(v) }, { k: 'lower', label: 'Lower', r: 1, f: v => money(v) }, { k: 'upper', label: 'Upper', r: 1, f: v => money(v) }], r.forecast, { maxH: 320 }))}`;
  const hl = r.history.map(x => x.date), fl = r.forecast.map(x => x.date), labels = [...hl, ...fl], pad = n => Array(n).fill(null);
  const tmap = Object.fromEntries((r.test || []).map(t => [t.date, t.predicted]));
  const nH = hl.length;
  const fv = [...pad(nH - 1), r.history[nH - 1].value, ...r.forecast.map(x => x.value)];
  const lo = [...pad(nH - 1), r.history[nH - 1].value, ...r.forecast.map(x => x.lower)], up = [...pad(nH - 1), r.history[nH - 1].value, ...r.forecast.map(x => x.upper)];
  mk('pc', { type: 'line', data: { labels, datasets: [
    line('Historical price', [...r.history.map(x => x.value), ...pad(fl.length)], '#0b1f44'),
    line('Backtest (model on test period)', [...hl.map(d => tmap[d] ?? null), ...pad(fl.length)], '#f59e0b', { borderDash: [5, 4], spanGaps: false }),
    line('Predicted price', fv, '#2f5bea', { borderWidth: 2.5 }),
    line('Lower bound', lo, 'rgba(47,91,234,0)', { borderWidth: 0, backgroundColor: 'transparent' }),
    line('Upper bound', up, 'rgba(47,91,234,0)', { borderWidth: 0, fill: '-1', backgroundColor: 'rgba(47,91,234,.14)' }),
  ] }, options: co({ scales: { x: xs(10), y: yfmt(v => num(v, 0)) } }) });
}

/* ================= Market trends ================= */
async function pTrends() {
  const pid = state.pageData.trendP || '';
  view().innerHTML = head('Market Trends', 'Bullish, bearish and stable movements, volatility and seasonality for every product.') +
    `<div class="filters"><div><label>Product detail</label><select id="tp" class="form-select">${prodOpts(pid || state.meta.products[0].id)}</select></div></div><div id="out">${loading()}</div>`;
  const run = async () => {
    state.pageData.trendP = $('#tp').value; $('#out').innerHTML = loading();
    try { renderTrends(await api('/trends?' + q({ product_id: $('#tp').value }))); } catch (e) { $('#out').innerHTML = errBox(e.message); }
  };
  $('#tp').onchange = run; run();
}
function renderTrends(t) {
  const s = t.selected;
  $('#out').innerHTML = `<div class="kpi-grid">${kpi('Bullish (increasing)', t.counts.increasing, 'products', 'bi-arrow-up-right-circle', 'green')}${kpi('Bearish (decreasing)', t.counts.decreasing, 'products', 'bi-arrow-down-right-circle', 'red')}${kpi('Stable', t.counts.stable, 'products', 'bi-dash-circle', 'navy')}${kpi('High volatility', t.volatility_counts.High, `${t.volatility_counts.Low} low volatility`, 'bi-lightning', 'orange')}</div>
  ${s ? `<div class="row g-3 mb-3">${panel(`${esc(s.product_name)} · ${trendBadge(s.trend)} ${volBadge(s.volatility)} volatility ${s.seasonal ? badge('Seasonal', 'blue') : ''}`,
    `<div class="btn-group btn-group-sm mb-2" id="pt">${['weekly', 'monthly', 'quarterly', 'yearly'].map((p, i) => `<button class="btn btn-outline-navy ${p === 'monthly' ? 'active' : ''}" data-p="${p}">${p[0].toUpperCase() + p.slice(1)}</button>`).join('')}</div>${box('tc', 280)}<div id="ptab" class="mt-2"></div>`, 'col-xl-8')}
    ${panel('Price movement and explanation', `<div class="row g-2 mb-3"><div class="col-6">${mini('7-day', pctHtml(s.change_7d))}</div><div class="col-6">${mini('30-day', pctHtml(s.change_30d))}</div><div class="col-6">${mini('90-day', pctHtml(s.change_90d))}</div><div class="col-6">${mini('Volatility (daily σ)', num(s.volatility_pct, 2) + '%')}</div></div>
    <ul class="ul-clean">${s.explanation.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`, 'col-xl-4')}</div>` : ''}
  ${panel('All products', table([{ k: 'product_name', label: 'Product', f: v => `<b>${esc(v)}</b>` }, { k: 'category', label: 'Category' }, { k: 'last_price', label: 'Price', r: 1, f: v => money(v) }, { k: 'change_7d', label: '7d', r: 1, f: v => pctHtml(v) }, { k: 'change_30d', label: '30d', r: 1, f: v => pctHtml(v) }, { k: 'change_90d', label: '90d', r: 1, f: v => pctHtml(v) }, { k: 'trend', label: 'Trend', f: v => trendBadge(v) }, { k: 'volatility', label: 'Volatility', f: v => volBadge(v) }, { k: 'seasonal', label: 'Seasonal', f: v => v ? badge('Yes', 'blue') : badge('No') }], t.products))}
  <div class="note mt-2">Trend: log-linear slope over the last 90 days, significant at 5% and at least ±1.5% per month. Volatility: standard deviation of daily price changes (relative ranking across products). Seasonal: calendar-month pattern explains over 25% of detrended variation (needs ≥ 400 days).</div>`;
  if (!s) return;
  const draw = p => {
    killCharts(); const rows = s.periods[p];
    mk('tc', { type: 'bar', data: { labels: rows.map(r => r.period), datasets: [{ type: 'line', label: 'Average price', data: rows.map(r => r.avg_price), borderColor: '#2f5bea', backgroundColor: '#2f5bea', yAxisID: 'y', tension: .25 }, { type: 'bar', label: 'Change vs previous period %', data: rows.map(r => r.change_pct), backgroundColor: rows.map(r => (r.change_pct || 0) >= 0 ? 'rgba(22,163,74,.5)' : 'rgba(220,38,38,.5)'), yAxisID: 'y1' }] }, options: co({ scales: { x: xs(12), y: yfmt(v => num(v, 0)), y1: { position: 'right', grid: { display: false }, ticks: { callback: v => v + '%' } } } }) });
    $('#ptab').innerHTML = table([{ k: 'period', label: 'Period' }, { k: 'avg_price', label: 'Avg price', r: 1, f: v => money(v) }, { k: 'min', label: 'Min', r: 1, f: v => money(v) }, { k: 'max', label: 'Max', r: 1, f: v => money(v) }, { k: 'change_pct', label: 'Change', r: 1, f: v => pctHtml(v) }], [...rows].reverse(), { maxH: 240 });
  };
  draw('monthly');
  $$('#pt button').forEach(b => b.onclick = () => { $$('#pt button').forEach(x => x.classList.remove('active')); b.classList.add('active'); draw(b.dataset.p); });
}

/* ================= Demand & supply ================= */
async function pDemand() {
  const f = state.pageData.ds || { product: '', category: '' };
  view().innerHTML = head('Demand & Supply', 'Market situations, shortages, excess inventory and demand forecasts.') +
    `<div class="filters"><div><label>Category</label><select id="fc" class="form-select">${catOpts(f.category)}</select></div><div><label>Product</label><select id="fp" class="form-select">${prodOpts(f.product, true)}</select></div><button id="go" class="btn btn-royal">Analyse</button></div><div id="out">${loading()}</div>`;
  const run = async () => {
    state.pageData.ds = { product: $('#fp').value, category: $('#fc').value }; $('#out').innerHTML = loading();
    try { renderDemand(await api('/demand-supply?' + q(state.pageData.ds))); } catch (e) { $('#out').innerHTML = errBox(e.message); }
  };
  $('#go').onclick = run; run();
}
function renderDemand(d) {
  const st = d.status_counts, sit = k => Object.entries(d.situation_counts).filter(([n]) => n.startsWith(k)).reduce((a, [, v]) => a + v, 0);
  const sc = { 'Shortage risk': 'red', 'Excess inventory': 'orange', Adequate: 'green' };
  $('#out').innerHTML = `<div class="kpi-grid">${kpi('Shortage risk', st['Shortage risk'], 'demand > supply by 10%, or < 7 days of stock', 'bi-exclamation-octagon', 'red')}${kpi('Excess inventory', st['Excess inventory'], 'more than 45 days of stock', 'bi-boxes', 'orange')}
    ${kpi('Possible price increase', sit('High Demand + Low'), 'high demand, low supply', 'bi-arrow-up-circle', 'green')}${kpi('Possible price decrease', sit('Low Demand + High'), 'low demand, high supply', 'bi-arrow-down-circle', 'red')}
    ${kpi('Balanced market', sit('High Demand + High'), 'high demand, high supply', 'bi-intersect', '')}${kpi('Low market activity', sit('Low Demand + Low'), 'low demand, low supply', 'bi-hourglass-split', 'navy')}</div>
    <div class="row g-3 mb-3">${panel('Demand vs supply (monthly average per product-day)', box('d1'), 'col-xl-6')}${panel(d.demand_forecast ? `Demand forecast, next 30 days (${pct((d.demand_forecast.mean_forecast / d.demand_forecast.recent_mean - 1) * 100)} vs last 30 days)` : 'Demand forecast', box('d2'), 'col-xl-6')}</div>
    ${panel('Products', table([{ k: 'product_name', label: 'Product', f: v => `<b>${esc(v)}</b>` }, { k: 'avg_demand_30d', label: 'Demand', r: 1, f: v => num(v) }, { k: 'avg_supply_30d', label: 'Supply', r: 1, f: v => num(v) }, { k: 'gap_pct', label: 'Gap', r: 1, f: v => pctHtml(v) }, { k: 'demand_growth_pct', label: 'Demand growth', r: 1, f: v => pctHtml(v) }, { k: 'supply_growth_pct', label: 'Supply growth', r: 1, f: v => pctHtml(v) }, { k: 'inventory_cover_days', label: 'Stock cover (days)', r: 1, f: v => num(v, 1) }, { k: 'status', label: 'Status', f: v => badge(v, sc[v]) }, { k: 'situation', label: 'Market situation' }], d.products))}
    <div class="note mt-2">${esc(d.rules)} Gap = (demand − supply) ÷ supply over the last 30 days. Growth compares the last 30 days with the 30 before.</div>`;
  mk('d1', { type: 'line', data: { labels: d.monthly.labels, datasets: [line('Demand', d.monthly.demand, '#2f5bea'), line('Supply', d.monthly.supply, '#f59e0b')] }, options: co({ scales: { x: xs(12), y: yfmt(v => num(v)) } }) });
  if (d.demand_forecast) { const F = d.demand_forecast, n = F.history.length;
    mk('d2', { type: 'line', data: { labels: [...F.history_labels, ...F.labels], datasets: [line('Recent demand', [...F.history, ...Array(30).fill(null)], '#0b1f44'), line('Forecast', [...Array(n - 1).fill(null), F.history[n - 1], ...F.forecast], '#2f5bea', { borderDash: [5, 4] })] }, options: co({ scales: { x: xs(8), y: yfmt(v => num(v)) } }) }); }
}

/* ================= Price optimization ================= */
const OPT_FIELDS = [['current_price', 'Current selling price'], ['cost_price', 'Product cost price'], ['competitor_price', 'Competitor price (avg)'], ['demand_qty', 'Demand quantity (per day)'], ['supply_qty', 'Supply quantity (per day)'], ['inventory', 'Inventory (units)'], ['expected_demand', 'Expected demand (per day)']];
async function pOptimize() {
  needProduct();
  view().innerHTML = head('Price Optimization', 'Combines cost, competitor, demand, trend and a fitted demand-response model to recommend a selling price.') + simBanner(state.meta.dataset) +
    `<div class="row g-3"><div class="col-xl-4"><div class="panel"><div class="panel-b"><form id="of" novalidate><label class="form-label note">Product</label><select id="op" class="form-select mb-3">${prodOpts(state.product)}</select>
    ${OPT_FIELDS.map(([k, l]) => `<div class="mb-2"><label class="form-label note mb-1">${l}</label><input class="form-control form-control-sm" type="number" step="any" min="0" id="o_${k}" required><div class="invalid-feedback">Enter a positive number.</div></div>`).join('')}
    <div class="row g-2 mt-1"><div class="col-6"><label class="form-label note mb-1">Min margin %</label><input type="number" class="form-control form-control-sm" id="o_mm" value="5" min="0" max="100" step="any"></div><div class="col-6"><label class="form-label note mb-1">Target margin %</label><input type="number" class="form-control form-control-sm" id="o_tm" value="25" min="0" max="300" step="any"></div>
    <div class="col-12"><label class="form-label note mb-1">Profit horizon (days)</label><input type="number" class="form-control form-control-sm" id="o_hz" value="30" min="1" max="365"></div></div>
    <div class="form-check mt-3"><input class="form-check-input" type="checkbox" id="o_loss"><label class="form-check-label note" for="o_loss">Allow loss-making scenario (prices below cost)</label></div>
    <button class="btn btn-royal w-100 mt-3" id="orun" type="submit"><i class="bi bi-magic me-1"></i>Recommend price</button><div class="note mt-2">Values are pre-filled from the last 30 days. Edit them to test what-if scenarios.</div></form></div></div></div>
    <div class="col-xl-8" id="out">${loading('Loading product defaults…')}</div></div>`;
  const fill = async () => {
    try { const d = await api('/optimize/defaults?product_id=' + $('#op').value); OPT_FIELDS.forEach(([k]) => $('#o_' + k).value = d[k]); $('#out').innerHTML = empty('bi-magic', 'Ready', 'Review the inputs and click “Recommend price”.'); }
    catch (e) { $('#out').innerHTML = errBox(e.message); }
  };
  $('#op').onchange = e => { state.product = e.target.value; fill(); }; fill();
  $('#of').onsubmit = ev => {
    ev.preventDefault(); let valid = true;
    OPT_FIELDS.forEach(([k]) => { const el = $('#o_' + k), v = parseFloat(el.value); const bad = !(v >= 0) || (k !== 'inventory' && v <= 0); el.classList.toggle('is-invalid', bad); if (bad) valid = false; });
    if (!valid) return toast('Fix the highlighted fields.', 'error');
    const body = { product_id: +$('#op').value, allow_loss: $('#o_loss').checked, min_margin_pct: +$('#o_mm').value, target_margin_pct: +$('#o_tm').value, horizon_days: +$('#o_hz').value };
    OPT_FIELDS.forEach(([k]) => body[k] = parseFloat($('#o_' + k).value));
    busy($('#orun'), async () => renderOpt(await api('/optimize', { json: body })));
  };
}
function renderOpt(o) {
  const R = o.recommended, C = o.current, el = o.elasticity, up = R.price_change_pct >= 0;
  $('#out').innerHTML = `<div class="rec-hero mb-3"><div class="d-flex flex-wrap justify-content-between gap-2"><div><small>Recommended selling price · ${esc(o.product.name)}</small><div class="big">${money(R.best_price)}</div>
      <div><span class="${up ? 'text-success-emphasis' : ''}" style="color:${up ? '#7ee2a0' : '#ff9a9a'}">${pct(R.price_change_pct)} (${R.price_difference >= 0 ? '+' : ''}${money(R.price_difference)}) vs current ${money(C.price)}</span></div></div>
      <div class="text-end">${badge(o.mode === 'model-based' ? 'Model-based' : 'Heuristic (not claimed optimal)', o.mode === 'model-based' ? 'green' : 'orange')}<div class="mt-2" style="max-width:340px"><small>${esc(R.strategy)}</small></div></div></div></div>
    ${o.warnings.map(w => `<div class="alert alert-warning py-2 mb-2"><i class="bi bi-exclamation-triangle me-1"></i>${esc(w)}</div>`).join('')}
    <div class="row g-2 mb-3"><div class="col-6 col-md-3">${mini('Minimum profitable price', money(R.minimum_profitable_price))}</div><div class="col-6 col-md-3">${mini('Maximum suggested price', money(R.maximum_suggested_price))}</div>
      <div class="col-6 col-md-3">${mini(`Expected profit (${R.horizon_days}d)`, moneyC(R.expected_profit))}</div><div class="col-6 col-md-3">${mini(`Expected revenue (${R.horizon_days}d)`, moneyC(R.expected_revenue))}</div></div>
    <div class="row g-3 mb-3">${panel('Current vs recommended (per day)', table([{ k: 'm', label: 'Measure' }, { k: 'c', label: 'Current', r: 1 }, { k: 'r', label: 'Recommended', r: 1 }], [
      { m: 'Selling price', c: money(C.price), r: money(R.best_price) }, { m: 'Profit per unit', c: money(C.profit_per_unit), r: money(R.profit_per_unit) }, { m: 'Profit margin', c: num(C.margin_pct, 1) + '%', r: num(R.margin_pct, 1) + '%' },
      { m: 'Expected units', c: num(C.daily_qty, 0), r: num(R.daily_qty, 0) }, { m: 'Revenue', c: money(C.daily_revenue, 0), r: money(R.daily_revenue, 0) }, { m: 'Profit', c: money(C.daily_profit, 0), r: money(R.daily_profit, 0) },
      { m: 'Profit change', c: '', r: R.profit_change_pct == null ? '–' : pct(R.profit_change_pct) }]), 'col-lg-6')}
      ${panel('How this price was chosen', `<p class="note">${esc(o.basis)}</p>${o.inventory_adjustment ? `<p class="note">${esc(o.inventory_adjustment)}</p>` : ''}<div class="note">Inventory cover: ${num(o.inventory_cover_days, 1)} days · Competitor range ${money(o.reference.competitor_min)} – ${money(o.reference.competitor_max)} · Predicted market move ${pct(o.reference.predicted_price_change_pct)}</div>`, 'col-lg-6')}</div>
    ${o.curve.length ? panel('Expected daily profit vs price (fitted demand model)', box('oc', 280) + `<div class="note mt-2">Elasticity ${num(el.elasticity, 2)} (p = ${el.p_value < .001 ? '<0.001' : num(el.p_value, 3)}, R² ${num(el.r_squared, 2)}, n = ${el.n}). Model: ${esc(el.model)}.</div>`, 'mb-3') : ''}
    ${panel('Heuristic components (weighted blend)', table([{ k: 'name', label: 'Component' }, { k: 'price', label: 'Price', r: 1, f: v => money(v) }, { k: 'weight', label: 'Weight', r: 1, f: v => num(v * 100) + '%' }], o.components) + `<div class="note mt-2">Heuristic price: ${money(o.heuristic_price)}${o.model_price ? ` · Model-optimal price: ${money(o.model_price)}` : ''}. ${esc(o.disclaimer)}</div>`)}`;
  if (o.curve.length) mk('oc', { type: 'line', data: { labels: o.curve.map(c => c.price.toFixed(2)), datasets: [line('Daily profit', o.curve.map(c => c.daily_profit), '#16a34a', { fill: true }), line('Daily revenue', o.curve.map(c => c.daily_revenue), '#2f5bea', { yAxisID: 'y1' })] }, options: co({ scales: { x: { ...xs(10), title: { display: true, text: 'Selling price' } }, y: yfmt(moneyC), y1: { position: 'right', grid: { display: false }, ticks: { callback: moneyC } } } }) });
}

/* ================= Competitors ================= */
async function pComp() {
  const f = state.pageData.cp || { category: '', product: '' };
  view().innerHTML = head('Competitor Analysis', 'How our selling price compares with competitor prices in the dataset (no web scraping).') +
    `<div class="filters"><div><label>Category</label><select id="fc" class="form-select">${catOpts(f.category)}</select></div><div><label>Product (chart)</label><select id="fp" class="form-select">${prodOpts(f.product || state.meta.products[0].id)}</select></div><button id="go" class="btn btn-royal">Analyse</button></div><div id="out">${loading()}</div>`;
  const run = async () => {
    state.pageData.cp = { category: $('#fc').value, product: $('#fp').value }; $('#out').innerHTML = loading();
    try { renderComp(await api('/competitors?' + q({ category: $('#fc').value, product_id: $('#fp').value }))); } catch (e) { $('#out').innerHTML = errBox(e.message); }
  };
  $('#go').onclick = run; run();
}
function renderComp(d) {
  const pc = d.position_counts, pb = { 'Below Market Price': 'blue', 'Competitive Price': 'green', 'Above Market Price': 'orange' };
  $('#out').innerHTML = `<div class="kpi-grid">${kpi('Below market price', pc['Below Market Price'], 'more than 3% under competitors', 'bi-arrow-down-circle', '')}${kpi('Competitive price', pc['Competitive Price'], 'within ±3%', 'bi-check-circle', 'green')}${kpi('Above market price', pc['Above Market Price'], 'more than 3% over competitors', 'bi-arrow-up-circle', 'orange')}</div>
  <div class="row g-3 mb-3">${panel(d.selected ? `${esc(d.selected.product_name)}: our price vs competitor (last 120 days)` : 'Price comparison', box('k1', 300), 'col-xl-7')}${panel('Price difference vs competitors (%)', box('k2', 300), 'col-xl-5')}</div>
  ${panel('Competitive position (last 30 days)', table([{ k: 'product_name', label: 'Product', f: v => `<b>${esc(v)}</b>` }, { k: 'our_price', label: 'Our price', r: 1, f: v => money(v) }, { k: 'avg_competitor', label: 'Avg competitor', r: 1, f: v => money(v) }, { k: 'lowest_competitor', label: 'Lowest', r: 1, f: v => money(v) }, { k: 'highest_competitor', label: 'Highest', r: 1, f: v => money(v) }, { k: 'difference', label: 'Difference', r: 1, f: v => money(v) }, { k: 'difference_pct', label: 'Diff %', r: 1, f: v => pctHtml(v) }, { k: 'position', label: 'Position', f: v => badge(v, pb[v]) }], d.products))}
  <div class="note mt-2">${esc(d.rules)}</div>`;
  if (d.selected) { const s = d.selected; mk('k1', { type: 'line', data: { labels: s.labels, datasets: [line('Our price', s.our, '#2f5bea'), line('Competitor price', s.competitor, '#dc2626'), line('Market price', s.market, '#9aa6c2', { borderDash: [4, 4] })] }, options: co({ scales: { x: xs(8), y: yfmt(v => num(v, 0)) } }) }); }
  const sorted = [...d.products].sort((a, b) => a.difference_pct - b.difference_pct);
  mk('k2', { type: 'bar', data: { labels: sorted.map(p => p.product_name), datasets: [{ label: 'Difference %', data: sorted.map(p => p.difference_pct), backgroundColor: sorted.map(p => p.difference_pct > 3 ? '#f59e0b' : p.difference_pct < -3 ? '#2f5bea' : '#16a34a') }] }, options: co({ indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: yfmt(v => v + '%'), y: { ticks: { font: { size: 10 } }, grid: { display: false } } } }) });
}

/* ================= Profit ================= */
async function pProfit() {
  const f = state.pageData.pf || { product: '', category: '' };
  view().innerHTML = head('Profit Analysis', 'Revenue = selling price × sales quantity · Profit = revenue − cost price × sales quantity.') +
    `<div class="filters"><div><label>Category</label><select id="fc" class="form-select">${catOpts(f.category)}</select></div><div><label>Product</label><select id="fp" class="form-select">${prodOpts(f.product, true)}</select></div><button id="go" class="btn btn-royal">Analyse</button></div><div id="out">${loading()}</div>`;
  const run = async () => {
    state.pageData.pf = { product: $('#fp').value, category: $('#fc').value }; $('#out').innerHTML = loading();
    try { renderProfit(await api('/profit?' + q({ product_id: $('#fp').value, category: $('#fc').value }))); } catch (e) { $('#out').innerHTML = errBox(e.message); }
  };
  $('#go').onclick = run; run();
}
function renderProfit(p) {
  const t = p.totals, F = p.forecast, cols = [{ k: 'revenue', label: 'Revenue', r: 1, f: v => moneyC(v) }, { k: 'cost', label: 'Cost', r: 1, f: v => moneyC(v) }, { k: 'profit', label: 'Profit', r: 1, f: v => `<b>${moneyC(v)}</b>` }, { k: 'margin_pct', label: 'Margin', r: 1, f: v => num(v, 1) + '%' }];
  $('#out').innerHTML = `<div class="kpi-grid">${kpi('Total revenue', moneyC(t.revenue), `${compact(t.units)} units`, 'bi-cash-stack')}${kpi('Total cost', moneyC(t.cost), '', 'bi-receipt', 'orange')}${kpi('Total profit', moneyC(t.profit), `Margin ${num(t.margin_pct, 1)}%`, 'bi-piggy-bank', 'green')}
    ${F ? kpi('Profit forecast (30d)', moneyC(F.profit_total_30d), `Last 30 days: ${moneyC(F.recent_profit_30d)}`, 'bi-graph-up-arrow', 'green') + kpi('Revenue forecast (30d)', moneyC(F.revenue_total_30d), `Last 30 days: ${moneyC(F.recent_revenue_30d)}`, 'bi-bar-chart', '') : ''}</div>
  <div class="row g-3 mb-3">${panel('Daily profit (last 90 days)', box('f1'), 'col-xl-7')}${panel('Category-wise profit', box('f2'), 'col-xl-5')}</div>
  <div class="row g-3 mb-3">${panel('Monthly profit', box('f3'), 'col-xl-7')}${panel('Annual profit', table([{ k: 'year', label: 'Year' }, ...cols, { k: 'days', label: 'Days', r: 1 }], p.annual) + '<div class="note mt-1">Years with fewer than 365 days are partial.</div>' + box('f4', 180), 'col-xl-5')}</div>
  ${F ? panel('Revenue and profit forecast (next 30 days, linear trend + seasonality)', box('f5', 300), 'mb-3') : ''}
  <div class="row g-3">${panel('Product-wise profit', table([{ k: 'product_name', label: 'Product', f: v => `<b>${esc(v)}</b>` }, { k: 'category', label: 'Category' }, { k: 'units', label: 'Units', r: 1, f: v => compact(v) }, ...cols], p.products, { maxH: 420 }), 'col-xl-7')}${panel('Category-wise', table([{ k: 'category', label: 'Category' }, ...cols], p.categories), 'col-xl-5')}</div>
  <div class="note mt-2">${esc(p.formulas)} Forecasts are estimates, not guarantees.</div>`;
  mk('f1', { type: 'line', data: { labels: p.daily.labels, datasets: [line('Profit', p.daily.profit, '#16a34a', { fill: true }), line('Revenue', p.daily.revenue, '#2f5bea', { yAxisID: 'y1' })] }, options: co({ scales: { x: xs(8), y: yfmt(moneyC), y1: { position: 'right', grid: { display: false }, ticks: { callback: moneyC } } } }) });
  mk('f2', { type: 'pie', data: { labels: p.categories.map(c => c.category), datasets: [{ data: p.categories.map(c => Math.max(c.profit, 0)), backgroundColor: PAL }] }, options: co({ interaction: { mode: 'nearest' }, plugins: { tooltip: { callbacks: { label: c => `${c.label}: ${moneyC(c.parsed)}` } } } }) });
  mk('f3', { type: 'bar', data: { labels: p.monthly.map(m => m.m), datasets: [{ label: 'Profit', data: p.monthly.map(m => m.profit), backgroundColor: p.monthly.map(m => m.profit >= 0 ? '#2f5bea' : '#dc2626') }] }, options: co({ plugins: { legend: { display: false } }, scales: { x: xs(12), y: yfmt(moneyC) } }) });
  mk('f4', { type: 'bar', data: { labels: p.annual.map(a => a.year), datasets: [{ label: 'Profit', data: p.annual.map(a => a.profit), backgroundColor: '#0b1f44' }] }, options: co({ plugins: { legend: { display: false } }, scales: { y: yfmt(moneyC) } }) });
  if (F) mk('f5', { type: 'line', data: { labels: [...F.history_labels, ...F.labels], datasets: [line('Revenue (actual)', [...F.revenue_history, ...Array(30).fill(null)], '#2f5bea'), line('Profit (actual)', [...F.profit_history, ...Array(30).fill(null)], '#16a34a'), line('Revenue forecast', [...Array(59).fill(null), F.revenue_history[59], ...F.revenue], '#2f5bea', { borderDash: [5, 4] }), line('Profit forecast', [...Array(59).fill(null), F.profit_history[59], ...F.profit], '#16a34a', { borderDash: [5, 4] })] }, options: co({ scales: { x: xs(10), y: yfmt(moneyC) } }) });
}

/* ================= Reports ================= */
async function pReports() {
  const m = state.meta;
  view().innerHTML = head('Reports', 'Generate and download analytical reports as PDF or Excel.') + simBanner(m.dataset) +
    `<div class="row g-3"><div class="col-xl-4"><div class="panel"><div class="panel-b"><form id="rf" novalidate>
      <label class="form-label note">Report</label><select id="rt" class="form-select mb-3">${Object.entries(m.report_types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select>
      <label class="form-label note">Format</label><div class="mb-3"><div class="form-check form-check-inline"><input class="form-check-input" type="radio" name="fmt" id="fpdf" value="pdf" checked><label class="form-check-label" for="fpdf">PDF</label></div><div class="form-check form-check-inline"><input class="form-check-input" type="radio" name="fmt" id="fx" value="xlsx"><label class="form-check-label" for="fx">Excel</label></div></div>
      <label class="form-label note">Product (optional)</label><select id="rp" class="form-select mb-3">${prodOpts('', true)}</select>
      <div id="predOpts" class="d-none"><label class="form-label note">Algorithm</label><select id="ra" class="form-select mb-3">${Object.entries(m.algorithms).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select></div>
      <label class="form-label note">Horizon (days)</label><select id="rh" class="form-select mb-3">${m.horizons.map(h => `<option ${h === 30 ? 'selected' : ''}>${h}</option>`).join('')}</select>
      <button class="btn btn-royal w-100" id="rgo" type="submit"><i class="bi bi-file-earmark-arrow-down me-1"></i>Generate &amp; download</button></form></div></div></div>
    <div class="col-xl-8">${panel('Recent reports', '<div id="rh2">' + loading() + '</div>')}</div></div>`;
  const sync = () => $('#predOpts').classList.toggle('d-none', $('#rt').value !== 'price_prediction' || !$('#rp').value);
  $('#rt').onchange = sync; $('#rp').onchange = sync;
  const hist = async () => { const h = await api('/reports/history'); $('#rh2').innerHTML = h.length ? table([{ k: 'type', label: 'Report' }, { k: 'format', label: 'Format', f: v => badge(v.toUpperCase(), 'blue') }, { k: 'created_at', label: 'Created' }, { k: 'id', label: '', f: v => `<a class="btn btn-sm btn-outline-secondary" href="/api/reports/download/${v}"><i class="bi bi-download"></i></a>` }], h) : empty('bi-file-earmark-text', 'No reports yet', 'Generated reports will appear here.'); };
  hist().catch(e => $('#rh2').innerHTML = errBox(e.message));
  $('#rf').onsubmit = ev => { ev.preventDefault(); busy($('#rgo'), async () => {
    const r = await api('/reports', { json: { report_type: $('#rt').value, file_format: document.querySelector('input[name=fmt]:checked').value, product_id: $('#rp').value ? +$('#rp').value : null, algorithm: $('#ra').value, horizon: +$('#rh').value } });
    toast('Report ready: ' + r.file_name); window.location.href = r.download_url; await hist();
  }); };
}

/* ================= Settings ================= */
async function pSettings() {
  const m = state.meta, list = await api('/datasets');
  view().innerHTML = head('Settings', 'Active dataset, database and application information.') +
    `<div class="row g-3"><div class="col-xl-6">${panel('Active dataset', m.dataset ? `<div class="row g-2">${[['Name', m.dataset.name], ['Source', m.dataset.source === 'sample' ? 'Simulated sample' : 'Uploaded file'], ['Rows (clean)', num(m.dataset.rows_clean)], ['Date range', `${m.dataset.date_min} → ${m.dataset.date_max}`], ['Products', m.products.length], ['Categories', m.categories.length]].map(([l, v]) => `<div class="col-6">${mini(l, esc(v))}</div>`).join('')}</div>` : empty('bi-database', 'No active dataset', 'Open Dataset Management to load one.'))}</div>
    <div class="col-xl-6">${panel('Switch dataset', `<div id="sw"></div><a href="#/datasets" class="btn btn-outline-navy btn-sm mt-2">Manage datasets</a>`)}</div>
    <div class="col-xl-6">${panel('System', `<ul class="ul-clean"><li>Application: ${esc(m.app)} v${esc(m.version)}</li><li>Database: ${esc(m.database)} (<code>price_optimization_db</code>)</li><li>Currency: ${esc(m.currency)}</li><li>Algorithms available: ${Object.values(m.algorithms).map(esc).join(', ')}</li><li>Runs fully offline: no external market API is used.</li></ul>`)}</div>
    <div class="col-xl-6">${panel('Methodology notes', `<ul class="ul-clean note"><li>Predictions are statistical estimates, never guaranteed prices.</li><li>Time-series models are evaluated with a chronological 80/20 split.</li><li>Price optimization only claims optimality when a statistically valid demand-response model exists.</li><li>Recommended prices never go below cost + minimum margin unless a loss-making scenario is chosen explicitly.</li></ul>`)}</div></div>`;
  $('#sw').innerHTML = list.length ? `<select id="swsel" class="form-select">${list.map(d => `<option value="${d.id}" ${d.is_active ? 'selected' : ''}>${esc(d.name)}</option>`).join('')}</select>` : '<div class="note">No datasets.</div>';
  const sel = $('#swsel'); if (sel) sel.onchange = async () => { try { await api(`/datasets/${sel.value}/activate`, { method: 'POST' }); toast('Dataset switched.'); await refreshMeta(); pSettings(); } catch (e) { toast(e.message, 'error'); } };
}
