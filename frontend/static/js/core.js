'use strict';
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const state = { meta: null, product: '', pageData: {} };
const PAL = ['#2f5bea', '#16a34a', '#f59e0b', '#dc2626', '#0891b2', '#7c3aed', '#0b1f44', '#db2777', '#65a30d'];
let CUR = '₹';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isN = v => v !== null && v !== undefined && !isNaN(v);
const num = (v, d = 0) => isN(v) ? Number(v).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d }) : '–';
const money = (v, d = 2) => isN(v) ? (v < 0 ? '-' : '') + CUR + num(Math.abs(v), d) : '–';
const compact = v => { if (!isN(v)) return '–'; const a = Math.abs(v), s = v < 0 ? '-' : ''; if (a >= 1e7) return s + (a / 1e7).toFixed(2) + ' Cr'; if (a >= 1e5) return s + (a / 1e5).toFixed(2) + ' L'; if (a >= 1e3) return s + (a / 1e3).toFixed(1) + 'K'; return s + num(a, 0); };
const moneyC = v => isN(v) ? (v < 0 ? '-' : '') + CUR + compact(Math.abs(v)) : '–';
const pct = (v, d = 1) => isN(v) ? (v > 0 ? '+' : '') + Number(v).toFixed(d) + '%' : '–';
const tone = v => v > 0 ? 'pos' : v < 0 ? 'neg' : '';
const pctHtml = (v, d = 1) => `<span class="${tone(v)}">${pct(v, d)}</span>`;
const q = o => Object.entries(o).filter(([, v]) => v !== '' && v != null).map(([k, v]) => k + '=' + encodeURIComponent(v)).join('&');
const view = () => $('#view');

async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.json !== undefined) { o.method = o.method || 'POST'; o.headers = { 'Content-Type': 'application/json' }; o.body = JSON.stringify(o.json); delete o.json; }
  let r;
  try { r = await fetch('/api' + path, o); } catch (e) { throw new Error('Cannot reach the server. Is it still running?'); }
  let data = null; try { data = await r.json(); } catch (e) { /* non-JSON */ }
  if (!r.ok) throw new Error((data && data.detail) || `Request failed (${r.status})`);
  return data;
}

function toast(msg, kind = 'success') {
  const el = document.createElement('div');
  el.className = `toast align-items-center text-bg-${kind === 'error' ? 'danger' : kind === 'warn' ? 'warning' : 'success'} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${esc(msg)}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  $('#toasts').appendChild(el);
  const t = new bootstrap.Toast(el, { delay: 5000 }); t.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}
async function busy(btn, fn) {
  const html = btn.innerHTML; btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Working…';
  try { return await fn(); } catch (e) { toast(e.message, 'error'); } finally { btn.disabled = false; btn.innerHTML = html; }
}

/* ---------- charts ---------- */
const _charts = [];
function mk(id, cfg) { const el = document.getElementById(id); if (!el) return null; const c = new Chart(el, cfg); _charts.push(c); return c; }
function killCharts() { _charts.splice(0).forEach(c => c.destroy()); }
const co = (extra = {}) => ({ responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
  plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, usePointStyle: true } } }, ...extra });
const yfmt = f => ({ ticks: { callback: v => f(v) }, grid: { color: '#eef1f7' } });
const xs = (n = 10) => ({ ticks: { maxTicksLimit: n, maxRotation: 0 }, grid: { display: false } });
const line = (label, data, color, x = {}) => ({ label, data, borderColor: color, backgroundColor: color + '22', borderWidth: 2, pointRadius: 0, tension: .25, ...x });
const box = (id, h = 300) => `<div style="height:${h}px;position:relative"><canvas id="${id}"></canvas></div>`;

/* ---------- ui pieces ---------- */
const panel = (title, body, cls = '', tools = '') => `<div class="${cls}"><div class="panel"><div class="panel-h"><h3>${title}</h3>${tools}</div><div class="panel-b">${body}</div></div></div>`;
const kpi = (label, value, sub = '', icon = 'bi-graph-up', color = '') => `<div class="kpi"><div class="ic ${color}"><i class="bi ${icon}"></i></div><div><div class="lb">${esc(label)}</div><div class="vl">${value}</div><div class="sb">${sub}</div></div></div>`;
const mini = (label, value) => `<div class="mini"><div class="lb">${esc(label)}</div><div class="vl">${value}</div></div>`;
const badge = (t, c = 'grey') => `<span class="badge-soft b-${c}">${esc(t)}</span>`;
const head = (title, sub = '', actions = '') => `<div class="page-head"><div><h1>${esc(title)}</h1><p>${esc(sub)}</p></div><div>${actions}</div></div>`;
const loading = (m = 'Loading…') => `<div class="spinner-wrap"><div class="spinner-border text-primary"></div><div>${esc(m)}</div></div>`;
const empty = (icon, title, msg, btn = '') => `<div class="empty"><i class="bi ${icon}"></i><h3>${esc(title)}</h3><p>${msg}</p>${btn}</div>`;
const errBox = m => `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle me-2"></i>${esc(m)}</div>`;
const simBanner = d => d && d.source === 'sample' ? `<div class="alert-sim"><i class="bi bi-info-circle me-1"></i><b>Simulated data.</b> The active dataset is synthetic sample data generated by this application, not real market observations.</div>` : '';
const trendBadge = t => badge({ increasing: 'Bullish', decreasing: 'Bearish', stable: 'Stable' }[t] || t, { increasing: 'green', decreasing: 'red', stable: 'grey' }[t]);
const volBadge = v => badge(v, { High: 'orange', Medium: 'blue', Low: 'grey' }[v]);

function table(cols, rows, o = {}) {
  if (!rows || !rows.length) return `<div class="note p-2">No rows.</div>`;
  return `<div class="table-responsive" ${o.maxH ? `style="max-height:${o.maxH}px;overflow:auto"` : ''}><table class="table table-sm table-hover align-middle data-table"><thead><tr>${cols.map(c => `<th class="${c.r ? 'text-end' : ''}">${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td class="${c.r ? 'text-end' : ''}">${c.f ? c.f(r[c.k], r) : esc(r[c.k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
const rawTable = (cols, rows) => `<div class="table-responsive"><table class="table table-sm table-hover data-table"><thead><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(v => `<td>${v === null ? '<span class="text-muted">null</span>' : esc(typeof v === 'number' ? +v.toFixed(2) : v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;

const prodOpts = (sel, all = false) => {
  const g = {}; state.meta.products.forEach(p => (g[p.category] = g[p.category] || []).push(p));
  return (all ? '<option value="">All products</option>' : '') + Object.entries(g).map(([c, ps]) =>
    `<optgroup label="${esc(c)}">${ps.map(p => `<option value="${p.id}" ${String(sel) === String(p.id) ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}</optgroup>`).join('');
};
const catOpts = sel => '<option value="">All categories</option>' + state.meta.categories.map(c => `<option ${sel === c ? 'selected' : ''}>${esc(c)}</option>`).join('');
const needProduct = () => { if (!state.product && state.meta.products.length) state.product = String(state.meta.products[0].id); return state.product; };
