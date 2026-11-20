// MechDesign Agent front end. All numbers shown come from the backend engine.
import { ScatterPlot } from './scatter.js';
// The 3D viewer depends on Three.js from a CDN; it is loaded lazily so the rest of the
// application keeps working offline (see initViewer()).

const $ = s => document.querySelector(s);
const form = $('#cfg-form');
const state = {
  example: null, materials: [], run: null, selectedId: null, view: 'feasible',
  sort: { key: 'rank', dir: 1 }, mag: null, magAuto: true, lastRequest: '',
};

const f3 = v => (v === null || v === undefined || Number.isNaN(v)) ? '–' : Number(Number(v).toPrecision(4)).toString();
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function api(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  return { ok: r.ok, status: r.status, data };
}

// ---------------------------------------------------------------- form <-> config
function setField(name, v) { const el = form.elements[name]; if (el) el.value = (v === null || v === undefined) ? '' : v; }
function configToForm(cfg) {
  for (const k of ['length_mm', 'width_mm', 'height_mm', 'load_N', 'allowable_deflection_mm']) setField(k, cfg[k]);
  setField('material.name', cfg.material?.name);
  setField('material.E_GPa', cfg.material?.E_GPa);
  setField('material.density_kg_m3', cfg.material?.density_kg_m3);
  $('#use-stress').checked = cfg.allowable_stress_MPa !== null && cfg.allowable_stress_MPa !== undefined;
  setField('allowable_stress_MPa', cfg.allowable_stress_MPa ?? form.elements['allowable_stress_MPa'].value);
  $('#use-aspect').checked = cfg.max_aspect_ratio !== null && cfg.max_aspect_ratio !== undefined;
  setField('max_aspect_ratio', cfg.max_aspect_ratio ?? form.elements['max_aspect_ratio'].value);
  for (const k of ['b_min_mm', 'b_max_mm', 'b_step_mm', 'h_min_mm', 'h_max_mm', 'h_step_mm']) setField('search.' + k, cfg.search?.[k]);
  syncOptional(); syncPreset(); updateGridCount();
}
function num(name) {
  const raw = form.elements[name].value.trim();
  if (raw === '') return null;
  const v = Number(raw);
  return Number.isFinite(v) ? v : raw; // send non-numeric text so the server can explain the error
}
function formToConfig() {
  const cfg = {
    length_mm: num('length_mm'), width_mm: num('width_mm'), height_mm: num('height_mm'),
    material: { name: form.elements['material.name'].value || 'Custom material', E_GPa: num('material.E_GPa'), density_kg_m3: num('material.density_kg_m3') },
    load_N: num('load_N'), allowable_deflection_mm: num('allowable_deflection_mm'),
    allowable_stress_MPa: $('#use-stress').checked ? num('allowable_stress_MPa') : null,
    max_aspect_ratio: $('#use-aspect').checked ? num('max_aspect_ratio') : null,
    search: {},
  };
  for (const k of ['b_min_mm', 'b_max_mm', 'b_step_mm', 'h_min_mm', 'h_max_mm', 'h_step_mm']) cfg.search[k] = num('search.' + k);
  // Required fields left blank are sent as missing so the server reports them.
  for (const k of ['length_mm', 'width_mm', 'height_mm', 'load_N', 'allowable_deflection_mm']) if (cfg[k] === null) delete cfg[k];
  if ($('#use-stress').checked && cfg.allowable_stress_MPa === null) cfg.allowable_stress_MPa = 'blank';
  if ($('#use-aspect').checked && cfg.max_aspect_ratio === null) cfg.max_aspect_ratio = 'blank';
  if (state.example && isExample(cfg)) cfg._label = state.example._label;
  return cfg;
}
function isExample(cfg) {
  const e = state.example; if (!e) return false;
  const strip = c => JSON.stringify({ ...c, _label: undefined });
  return strip(cfg) === strip({ ...e });
}
function syncOptional() {
  form.elements['allowable_stress_MPa'].disabled = !$('#use-stress').checked;
  form.elements['max_aspect_ratio'].disabled = !$('#use-aspect').checked;
}
function syncPreset() {
  const name = form.elements['material.name'].value, E = num('material.E_GPa'), rho = num('material.density_kg_m3');
  const m = state.materials.find(p => p.name === name && p.E_GPa === E && p.density_kg_m3 === rho);
  $('#material-preset').value = m ? m.name : '__custom';
  $('#material-note').textContent = m ? m.note : 'Custom material properties (enter your own E and density).';
}
function updateGridCount() {
  const n = (a, b, s) => { const x = num(a), y = num(b), z = num(s); return (x > 0 && y >= x && z > 0) ? Math.floor((y - x) / z + 1e-9) + 1 : null; };
  const nb = n('search.b_min_mm', 'search.b_max_mm', 'search.b_step_mm'), nh = n('search.h_min_mm', 'search.h_max_mm', 'search.h_step_mm');
  $('#grid-count').textContent = (nb && nh) ? `${nb} × ${nh} = ${nb * nh} candidates` : '';
  $('#example-note').hidden = !isExample(formToConfig());
}

function showErrors(errors) {
  form.querySelectorAll('.invalid').forEach(el => el.classList.remove('invalid'));
  const box = $('#errors');
  if (!errors || !errors.length) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = '<strong>Please correct the following:</strong><ul>' + errors.map(e => `<li><b>${esc(e.field)}</b>: ${esc(e.message)}</li>`).join('') + '</ul>';
  for (const e of errors) {
    const el = form.elements[e.field] || form.elements[e.field.replace(/^search$/, 'search.b_step_mm')];
    if (el && el.classList) el.classList.add('invalid');
  }
}

// ---------------------------------------------------------------- run
async function runCalc({ keepSelection = false } = {}) {
  const cfg = formToConfig();
  $('#btn-run').disabled = true;
  const r = await api('/api/run', { config: cfg });
  $('#btn-run').disabled = false;
  if (!r.ok) { showErrors(r.data.errors || [{ field: 'request', message: 'Server error ' + r.status }]); return false; }
  showErrors(null);
  updateGridCount();
  state.run = r.data;
  if (!keepSelection || !state.run.candidates.some(c => c.id === state.selectedId)) state.selectedId = null;
  state.magAuto = true;
  renderAll();
  return true;
}

function selected() {
  if (!state.run) return null;
  return state.selectedId ? state.run.candidates.find(c => c.id === state.selectedId) : state.run.current;
}

function renderAll() { renderSelected(); renderScatter(); renderTable(); renderStatement(); }

function renderStatement() {
  const el = $('#statement'), s = state.run.search;
  el.className = 'statement' + (s.n_feasible === 0 ? ' none' : '');
  el.textContent = state.run.statement;
}

function renderSelected() {
  const c = selected(); if (!c) return;
  const isCur = !state.selectedId;
  $('#sel-title').textContent = isCur ? 'Current design' : `Selected candidate b = ${f3(c.b_mm)} mm, h = ${f3(c.h_mm)} mm` + (c.rank ? ` (rank ${c.rank})` : '');
  $('#btn-adopt').disabled = isCur;
  $('#btn-show-current').disabled = isCur;
  const cfg = state.run.config;
  const nums = [
    ['b', f3(c.b_mm) + ' mm'], ['h', f3(c.h_mm) + ' mm'], ['L', f3(c.L_mm) + ' mm'], ['I', f3(c.I_mm4) + ' mm⁴'],
    ['Mass', f3(c.mass_g) + ' g'], ['Tip deflection (actual)', f3(c.deflection_mm) + ' mm'], ['Max bending stress', f3(c.stress_MPa) + ' MPa'],
  ];
  if (!isCur) nums.push(['Mass vs current', (c.mass_change_vs_current_pct >= 0 ? '+' : '') + f3(c.mass_change_vs_current_pct) + ' %']);
  $('#sel-numbers').innerHTML = nums.map(([k, v]) => `<div class="num"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('') +
    `<div class="num ${c.feasible ? 'status-ok' : 'status-bad'}"><div class="k">Status</div><div class="v">${c.feasible ? 'FEASIBLE' : 'NOT FEASIBLE'}</div></div>`;
  $('#sel-checks').innerHTML = c.checks.map(k => `<div class="${k.passed ? 'pass' : 'fail'}">${k.passed ? '✔' : '✘'} ${esc(k.text)} (${f3(100 * k.utilisation)} % of limit)</div>`).join('') +
    c.warnings.map(w => `<div class="warn">⚠ ${esc(w)}</div>`).join('');
  $('#crosscheck').hidden = true;
  render3D();
}

// ---------------------------------------------------------------- 3D
let viewer = null;
async function initViewer() {
  const el = $('#view3d');
  try {
    const { BeamViewer } = await import('./viewer3d.js');
    viewer = new BeamViewer(el);
  } catch (err) {
    console.warn('3D viewer unavailable:', err);
    el.innerHTML = '<div class="view3d-fallback"><b>3D view unavailable.</b><br>Three.js could not be loaded from the CDN ' +
      '(no internet connection?). All calculations, the plot and the table still work; the numbers below remain valid.</div>';
  }
}
function niceMag(x) {
  if (!(x > 0) || !Number.isFinite(x)) return 1;
  if (x <= 1) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(x)));
  const m = [1, 2, 5, 10].filter(k => k * p <= x).pop();
  return m * p;
}
function render3D() {
  const c = selected(); if (!c) return;
  const cfg = state.run.config;
  if (state.magAuto) {
    state.mag = c.deflection_mm > 0 ? niceMag(0.12 * c.L_mm / c.deflection_mm) : 1;
    $('#mag').value = state.mag;
  }
  viewer?.update({
    L: c.L_mm, b: c.b_mm, h: c.h_mm, F: cfg.load_N, delta: c.deflection_mm, mag: state.mag,
    shape: state.run.deflection_shape, showU: $('#show-undeformed').checked, showD: $('#show-deformed').checked,
  });
  const shown = c.deflection_mm * state.mag;
  if (!viewer) {
    $('#mag-note').innerHTML = `<b>Actual predicted tip deflection: ${f3(c.deflection_mm)} mm</b> (${f3(100 * c.deflection_mm / c.L_mm)} % of L). 3D view unavailable.`;
    return;
  }
  $('#mag-note').innerHTML = c.deflection_mm > 0
    ? `<b>Deformation shown magnified ×${f3(state.mag)}</b> (displayed tip drop ≈ ${f3(shown)} mm equivalent). ` +
      `<b>Actual predicted tip deflection: ${f3(c.deflection_mm)} mm</b> (${f3(100 * c.deflection_mm / c.L_mm)} % of L). Load arrow shows direction only.`
    : 'Zero load: no deformation to display.';
}

// ---------------------------------------------------------------- scatter
let scatter = null;
function renderScatter() {
  scatter.setData({ cands: state.run.candidates, current: state.run.current, limit: state.run.config.allowable_deflection_mm,
    selectedId: state.selectedId, logy: $('#logy').checked });
}

// ---------------------------------------------------------------- table
const COLS = [
  { key: 'rank', label: 'Rank' }, { key: 'b_mm', label: 'b [mm]' }, { key: 'h_mm', label: 'h [mm]' },
  { key: 'mass_g', label: 'Mass [g]' }, { key: 'mass_change_vs_current_pct', label: 'Δ mass vs current [%]' },
  { key: 'deflection_mm', label: 'δ tip [mm]' }, { key: 'u_def', label: 'δ/δ_allow' },
  { key: 'stress_MPa', label: 'σ max [MPa]' }, { key: 'u_str', label: 'σ/σ_allow' }, { key: 'aspect', label: 'h/b' },
  { key: 'feasible', label: 'Status', txt: true }, { key: 'reason', label: 'Why feasible / rejected', txt: true },
];
function rowVal(c, key) {
  if (key === 'u_def') return c.checks.find(k => k.name === 'tip_deflection')?.utilisation;
  if (key === 'u_str') return c.checks.find(k => k.name === 'bending_stress')?.utilisation;
  if (key === 'aspect') return c.h_mm / c.b_mm;
  return c[key];
}
function renderTable() {
  const run = state.run;
  const thead = $('#cand-table thead');
  thead.innerHTML = '<tr>' + COLS.map(c => `<th class="${c.txt ? 'txt' : ''}" data-key="${c.key}">${c.label}${state.sort.key === c.key ? (state.sort.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('') + '</tr>';
  let rows = state.view === 'feasible' ? run.candidates.filter(c => c.feasible) : [...run.candidates];
  if (state.view === 'feasible' && rows.length === 0 && run.nearest_infeasible.length) rows = run.nearest_infeasible;
  const { key, dir } = state.sort;
  rows.sort((a, b) => {
    let x = rowVal(a, key), y = rowVal(b, key);
    if (x === null || x === undefined) x = Infinity; if (y === null || y === undefined) y = Infinity;
    if (typeof x === 'boolean') { x = +x; y = +y; }
    return (x < y ? -1 : x > y ? 1 : 0) * dir;
  });
  const LIMIT = 600;
  const curB = run.current.b_mm, curH = run.current.h_mm;
  $('#cand-table tbody').innerHTML = rows.slice(0, LIMIT).map(c => {
    const ud = rowVal(c, 'u_def'), us = rowVal(c, 'u_str');
    const cls = [c.id === state.selectedId ? 'selected' : '', (c.b_mm === curB && c.h_mm === curH) ? 'is-current' : ''].join(' ');
    return `<tr data-id="${c.id}" class="${cls}" tabindex="0" aria-selected="${c.id === state.selectedId}">
      <td>${c.rank ?? '–'}</td><td>${f3(c.b_mm)}</td><td>${f3(c.h_mm)}</td><td>${f3(c.mass_g)}</td>
      <td>${(c.mass_change_vs_current_pct >= 0 ? '+' : '') + f3(c.mass_change_vs_current_pct)}</td>
      <td>${f3(c.deflection_mm)}</td><td class="${ud > 1 ? 'fail' : ''}">${f3(ud)}</td><td>${f3(c.stress_MPa)}</td>
      <td class="${us > 1 ? 'fail' : ''}">${us === undefined ? 'n/a' : f3(us)}</td><td>${f3(c.h_mm / c.b_mm)}</td>
      <td class="txt ${c.feasible ? 'pass' : 'fail'}">${c.feasible ? 'feasible' : 'rejected'}${c.warnings.length ? ' ⚠' : ''}</td>
      <td class="txt reason" title="${esc(c.warnings.join(' '))}">${esc(c.reason)}</td></tr>`;
  }).join('');
  const shownNote = rows.length > LIMIT ? ` Showing the first ${LIMIT} rows of ${rows.length} (sort to see others).` : '';
  const nf = state.view === 'feasible' && run.search.n_feasible === 0
    ? 'No feasible candidates. Showing the closest infeasible candidates for reference; constraints were NOT relaxed.'
    : `${rows.length} row(s). Ranked by mass among feasible candidates in the sampled grid (not a guaranteed global optimum).`;
  $('#table-foot').textContent = nf + shownNote + ' Click a row or a plot point to inspect it; ⚠ marks model-validity warnings (hover the reason).';
}

function select(id) {
  state.selectedId = id; state.magAuto = true;
  renderAll();
}

// ---------------------------------------------------------------- cross-check
async function crossCheck() {
  const c = selected(); if (!c) return;
  const el = $('#crosscheck'); el.hidden = false; el.textContent = 'Running FE cross-check…';
  const r = await api('/api/crosscheck', { config: formToConfig(), b_mm: c.b_mm, h_mm: c.h_mm });
  if (!r.ok) { el.textContent = 'Cross-check failed: ' + JSON.stringify(r.data.errors || r.data); return; }
  const d = r.data;
  el.innerHTML = `<b>Independent numerical cross-check</b> — closed form: δ = ${f3(d.closed_form.tip_deflection_mm)} mm, σ = ${f3(d.closed_form.max_stress_MPa)} MPa
    <table><thead><tr><th>Solver</th><th>Physics</th><th>δ tip [mm]</th><th>Relative difference</th><th>Tol.</th><th>Result</th></tr></thead><tbody>` +
    d.rows.map(x => x.pass === null ? `<tr><td>${esc(x.solver)}</td><td colspan="5">${esc(x.notes)}</td></tr>` :
      `<tr><td>${esc(x.solver)}</td><td>${esc(x.physics)}</td><td>${Number(x.tip_deflection_mm).toPrecision(6)}</td>
      <td>${'rel_diff_vs_timoshenko' in x ? `${x.rel_diff_vs_timoshenko.toExponential(2)} vs Timoshenko (${Number(x.timoshenko_deflection_mm).toPrecision(5)} mm)<br>${x.rel_diff_deflection.toExponential(2)} vs Euler–Bernoulli` : `δ ${x.rel_diff_deflection.toExponential(2)}, σ ${x.rel_diff_stress.toExponential(2)}`}</td>
      <td>${x.tolerance}</td><td class="${x.pass ? 'pass' : 'fail'}">${x.pass ? 'PASS' : 'FAIL'}</td></tr>`).join('') +
    `</tbody></table><div class="hint">${esc(d.disclaimer)}</div>`;
}

// ---------------------------------------------------------------- assistant
function addMsg(html, cls = 'bot') {
  const d = document.createElement('div'); d.className = 'msg ' + cls; d.innerHTML = html;
  $('#chat').appendChild(d); $('#chat').scrollTop = 1e9; return d;
}
const SRC = { user_stated: 'stated by you', derived_from_current: 'derived from current design', assistant_suggestion: 'suggestion – confirm' };

async function interpret(message) {
  state.lastRequest = message;
  addMsg(esc(message), 'user');
  const pending = addMsg('<i>Interpreting…</i>');
  const r = await api('/api/interpret', { message, config: formToConfig() });
  pending.remove();
  if (!r.ok || r.data.error) { addMsg('Could not interpret: ' + esc(r.data.error || r.status)); return; }
  const d = r.data;
  let h = `<div class="src">Interpretation by: ${esc(d.mode_label)}</div>`;
  if (d.llm_error) h += `<div class="warn">${esc(d.llm_error)}</div>`;
  h += `<div><b>Understood:</b> ${esc(d.summary)}</div>`;
  if (d.diffs.length || d.missing.length) {
    h += `<table class="proposal"><thead><tr><th>Parameter</th><th>Proposed (editable)</th></tr></thead><tbody>`;
    for (const x of d.diffs) h += `<tr><td>${esc(x.label)} [${esc(x.unit)}]<div class="hint">current: ${x.old ?? '–'}</div></td>
      <td><input type="number" step="any" data-field="${x.field}" value="${+Number(x.new).toPrecision(6)}" aria-label="${esc(x.label)}"></td></tr>
      <tr class="note-row"><td colspan="2"><span class="src-tag ${x.source}">${SRC[x.source]}</span> ${esc(x.note || '')}</td></tr>`;
    for (const x of d.missing) h += `<tr class="missing-row"><td><b>${esc(x.label)} [${esc(x.unit)}]</b><div class="hint">current form value: ${x.current_form_value ?? '–'}</div></td>
      <td><input type="number" step="any" data-field="${x.field}" data-missing="1" placeholder="required" aria-label="${esc(x.label)} (required)"></td></tr>
      <tr class="note-row"><td colspan="2"><span class="src-tag missing">missing</span> ${esc(x.question)}</td></tr>`;
    h += '</tbody></table>';
  } else {
    h += '<div class="hint">No parameter changes proposed.</div>';
  }
  if (d.used_from_form.length) h += `<div class="hint">Requirements that will be used unchanged from the input form (edit there if they are wrong): ` +
    d.used_from_form.map(u => `${esc(u.label)} = ${u.value ?? 'not set'}${u.value != null ? ' ' + esc(u.unit) : ''}`).join('; ') + '.</div>';
  if (d.clarifications.length) h += '<ul>' + d.clarifications.map(c => `<li class="warn">${esc(c)}</li>`).join('') + '</ul>';
  if (d.guard_notes.length) h += '<ul>' + d.guard_notes.map(c => `<li class="warn">Provenance check: ${esc(c)}</li>`).join('') + '</ul>';
  if (d.missing.length) h += `<div class="fail">Missing requirements must be entered before I can compare designs or recommend dimensions.</div>`;
  h += `<div class="actions"><button class="primary btn-apply">Apply &amp; recalculate</button><button class="secondary btn-discard">Discard</button></div>`;
  const box = addMsg(h);
  const applyBtn = box.querySelector('.btn-apply');
  const inputs = [...box.querySelectorAll('input[data-field]')];
  const check = () => { applyBtn.disabled = inputs.some(i => i.dataset.missing && (i.value.trim() === '' || !Number.isFinite(Number(i.value)))); };
  inputs.forEach(i => i.addEventListener('input', check)); check();
  box.querySelector('.btn-discard').onclick = () => { box.querySelector('.actions').innerHTML = '<span class="hint">Discarded.</span>'; };
  applyBtn.onclick = async () => {
    const cfg = JSON.parse(JSON.stringify(d.proposed_config));
    for (const i of inputs) {
      const v = i.value.trim() === '' ? null : Number(i.value);
      const parts = i.dataset.field.split('.'); let o = cfg;
      for (const p of parts.slice(0, -1)) o = o[p] = o[p] || {};
      o[parts.at(-1)] = v;
    }
    delete cfg._label;
    configToForm(cfg);
    box.querySelector('.actions').innerHTML = '<span class="hint">Applied to the input form.</span>';
    const ok = await runCalc();
    if (!ok) { addMsg('<span class="fail">The updated inputs are invalid — see the errors under the input form.</span>'); return; }
    await explain();
  };
}

async function explain() {
  const r = await api('/api/explain', { config: formToConfig(), message: state.lastRequest, selected_id: state.selectedId });
  if (!r.ok) return;
  const d = r.data;
  let h = `<div class="src">Explanation: ${esc(d.mode_label)}</div>`;
  if (d.llm_error) h += `<div class="warn">${esc(d.llm_error)}</div>`;
  h += `<div>${esc(d.text)}</div>`;
  if (d.unverified_numbers.length) h += `<div class="warn">⚠ Numbers not traceable to engine results (ignore them): ${esc(d.unverified_numbers.join(', '))}</div>`;
  if (d.unknown_placeholders.length) h += `<div class="warn">⚠ Unknown value references: ${esc(d.unknown_placeholders.join(', '))}</div>`;
  addMsg(h, d.unverified_numbers.length ? 'bot warnbox' : 'bot');
}

// ---------------------------------------------------------------- report
async function exportReport(fmt) {
  const r = await fetch('/api/report', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config: formToConfig(), selected_id: state.selectedId, format: fmt, message: state.lastRequest }) });
  if (!r.ok) { const j = await r.json(); showErrors(j.errors); return; }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'mechdesign-report.' + (fmt === 'md' ? 'md' : 'html');
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ---------------------------------------------------------------- save / load inputs (same JSON as the CLI)
function saveConfig() {
  const cfg = formToConfig();
  const blob = new Blob([JSON.stringify(cfg, null, 2) + String.fromCharCode(10)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'mechdesign-config.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
async function loadConfigFile(e) {
  const file = e.target.files[0]; e.target.value = '';
  if (!file) return;
  let cfg;
  try { cfg = JSON.parse(await file.text()); } catch (err) {
    showErrors([{ field: file.name, message: 'is not valid JSON (' + err.message + ')' }]); return;
  }
  if (!cfg || typeof cfg !== 'object' || Array.isArray(cfg)) { showErrors([{ field: file.name, message: 'must contain a JSON object' }]); return; }
  // Loaded as-is: missing fields stay blank and are reported, never filled from the example.
  configToForm({ ...cfg, material: cfg.material || {}, search: cfg.search || {} });
  state.selectedId = null;
  await runCalc();
}

// ---------------------------------------------------------------- init
async function init() {
  const [st, ex] = await Promise.all([api('/api/status'), api('/api/example')]);
  const badge = $('#mode-badge');
  if (st.data.llm_enabled) { badge.textContent = `LLM: ${st.data.llm_model}`; badge.className = 'badge llm'; }
  else { badge.textContent = 'No LLM key – rule-based fallback'; badge.className = 'badge fallback'; }
  $('#assistant-mode').innerHTML = st.data.llm_enabled
    ? `Requests are interpreted by an LLM (${esc(st.data.llm_model)}). All numbers are calculated by the deterministic engine; you review every proposed change before it is applied.`
    : `<b>No LLM API key configured.</b> Using a ${esc(st.data.fallback_label.toLowerCase())}. It understands a limited vocabulary; the structured form on the left always works.`;
  addMsg('Describe what you want (e.g. lighter, stiffer, a deflection limit). I will show the parameters I interpreted for you to review before anything is calculated.');

  state.example = ex.data.config; state.materials = ex.data.materials;
  $('#assumption-list').innerHTML = ex.data.assumptions.map(a => `<li>${esc(a)}</li>`).join('');
  $('#limitation-list').innerHTML = ex.data.limitations.map(a => `<li>${esc(a)}</li>`).join('');
  $('#material-preset').innerHTML = state.materials.map(m => `<option value="${esc(m.name)}">${esc(m.name)} (E ${m.E_GPa} GPa, ρ ${m.density_kg_m3})</option>`).join('') + '<option value="__custom">Custom…</option>';

  scatter = new ScatterPlot($('#scatter'), $('#tooltip'), select);
  $('#app-version').textContent = 'v' + st.data.version;
  initViewer().then(() => { if (state.run) render3D(); });

  configToForm(state.example);
  await runCalc();

  form.addEventListener('submit', e => { e.preventDefault(); runCalc({ keepSelection: true }); });
  form.addEventListener('input', e => { if (e.target.id !== 'material-preset') { syncPreset(); updateGridCount(); } });
  $('#use-stress').addEventListener('change', syncOptional);
  $('#use-aspect').addEventListener('change', syncOptional);
  $('#material-preset').addEventListener('change', e => {
    const m = state.materials.find(p => p.name === e.target.value);
    if (m) { setField('material.name', m.name); setField('material.E_GPa', m.E_GPa); setField('material.density_kg_m3', m.density_kg_m3); }
    else { setField('material.name', 'Custom material'); }
    syncPreset(); updateGridCount();
  });
  $('#btn-example').onclick = () => { configToForm(state.example); state.selectedId = null; runCalc(); };
  $('#btn-show-current').onclick = () => select(null);
  $('#btn-adopt').onclick = () => { const c = selected(); setField('width_mm', c.b_mm); setField('height_mm', c.h_mm); state.selectedId = null; updateGridCount(); runCalc(); };
  $('#btn-crosscheck').onclick = crossCheck;
  $('#mag').addEventListener('input', e => { const v = Number(e.target.value); if (v >= 1) { state.mag = v; state.magAuto = false; render3D(); } });
  $('#btn-mag-auto').onclick = () => { state.magAuto = true; render3D(); };
  $('#show-undeformed').onchange = render3D; $('#show-deformed').onchange = render3D;
  $('#logy').onchange = renderScatter;
  document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === t));
    state.view = t.dataset.view; renderTable();
  });
  $('#cand-table thead').addEventListener('click', e => {
    const k = e.target.closest('th')?.dataset.key; if (!k) return;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : 1 }; renderTable();
  });
  $('#cand-table tbody').addEventListener('click', e => { const id = e.target.closest('tr')?.dataset.id; if (id) select(id); });
  $('#cand-table tbody').addEventListener('keydown', e => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const id = e.target.closest('tr')?.dataset.id; if (id) { e.preventDefault(); select(id); }
  });
  $('#btn-save-cfg').onclick = saveConfig;
  $('#btn-load-cfg').onclick = () => $('#file-cfg').click();
  $('#file-cfg').addEventListener('change', loadConfigFile);
  $('#chat-form').addEventListener('submit', e => { e.preventDefault(); const v = $('#chat-input').value.trim(); if (v) { $('#chat-input').value = ''; interpret(v); } });
  document.querySelectorAll('.chip').forEach(c => c.onclick = () => interpret(c.textContent));
  $('#btn-report-html').onclick = () => exportReport('html');
  $('#btn-report-md').onclick = () => exportReport('md');
}

init();
