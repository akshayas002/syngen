/* ═══════════════════════════════════════════
   SynGen v2.0 — Frontend Logic
   ═══════════════════════════════════════════ */

let currentSchema = null;
let editingFieldIndex = -1;

// ── Null rate slider ──────────────────────────────
document.getElementById('cfgNullRate').addEventListener('input', function () {
  document.getElementById('cfgNullVal').textContent = Math.round(this.value * 100) + '%';
});

// ── Load examples ─────────────────────────────────
async function loadExamples() {
  try {
    const res = await fetch('/api/examples');
    const { examples } = await res.json();
    const el = document.getElementById('exampleChips');
    examples.forEach(ex => {
      const b = document.createElement('button');
      b.className = 'chip';
      b.innerHTML = `<span>${ex.icon}</span>${ex.label}`;
      b.onclick = () => { document.getElementById('promptInput').value = ex.prompt; };
      el.appendChild(b);
    });
  } catch (e) { console.warn('Examples load failed', e); }
}

// ── Toast status ──────────────────────────────────
function toast(msg, loading = false) {
  const t = document.getElementById('statusToast');
  const sp = document.getElementById('toastSpinner');
  t.style.display = 'flex';
  sp.style.display = loading ? 'block' : 'none';
  document.getElementById('toastText').textContent = msg;
}
function hideToast() { document.getElementById('statusToast').style.display = 'none'; }

function showZone(id) {
  const el = document.getElementById(id);
  el.style.display = 'block';
  el.style.animation = 'none';
  requestAnimationFrame(() => el.style.animation = 'fadeUp .35s ease both');
}

// ── STEP 1: Interpret ─────────────────────────────
async function interpretPrompt() {
  const prompt = document.getElementById('promptInput').value.trim();
  if (!prompt) return;
  const rows = parseInt(document.getElementById('rowsInput').value) || 500;
  const btn = document.getElementById('interpretBtn');
  btn.disabled = true;
  document.getElementById('schemaZone').style.display = 'none';
  document.getElementById('dataZone').style.display = 'none';
  toast('Sending to Groq (llama-3.3-70b)…', true);

  try {
    const res = await fetch('/api/interpret', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, rows }),
    });
    if (!res.ok) throw new Error(await res.text());
    const { schema, model } = await res.json();
    currentSchema = schema;
    currentSchema._rows = rows;
    renderSchema(schema);
    showZone('schemaZone');
    toast(`Schema ready via ${model} — ${schema.attributes.length} attributes, ${(schema.relationships || []).length} relationships.`);
  } catch (e) {
    toast('Error: ' + (e.message || 'Interpretation failed.'));
  }
  btn.disabled = false;
}

// ── Render schema ─────────────────────────────────
function renderSchema(schema) {
  document.getElementById('schemaNameTag').textContent = schema.name || '';
  document.getElementById('attrBadge').textContent = schema.attributes.length;
  document.getElementById('relBadge').textContent = (schema.relationships || []).length;

  // Attributes
  const attrEl = document.getElementById('attrList');
  if (!schema.attributes.length) {
    attrEl.innerHTML = '<div class="empty-hint">No attributes yet. Add one →</div>';
  } else {
    attrEl.innerHTML = schema.attributes.map((a, i) => {
      const distTag = a.distribution ? `<span class="tag tag-dist">${a.distribution}</span>` : '';
      const valTag  = a.values ? `<span class="tag tag-dist">${a.values.slice(0, 3).join(', ')}${a.values.length > 3 ? '…' : ''}</span>` : '';
      const trueTag = a.true_rate !== undefined ? `<span class="tag tag-dist">${Math.round(a.true_rate * 100)}% true</span>` : '';
      const nullTag = a.nullable ? `<span class="tag tag-dist">${Math.round(a.nullable * 100)}% null</span>` : '';
      const uniTag  = a.unique ? `<span class="tag tag-rel-pos">unique</span>` : '';
      return `<div class="attr-item" onclick="openEditFieldModal(${i})">
        <div class="attr-left">
          <span class="attr-name">${a.name}</span>
          <div class="attr-tags">
            <span class="tag tag-type">${a.type}</span>
            ${distTag}${valTag}${trueTag}${nullTag}${uniTag}
            ${a.mean !== undefined ? `<span class="tag tag-dist">μ ${a.mean}</span>` : ''}
          </div>
        </div>
        <div class="attr-actions">
          <button class="icon-btn" onclick="event.stopPropagation();removeField(${i})" title="Remove">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2l8 8M10 2L2 10" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>
          </button>
        </div>
      </div>`;
    }).join('');
  }

  // Relationships
  const relEl = document.getElementById('relList');
  const rels = schema.relationships || [];
  if (!rels.length) {
    relEl.innerHTML = '<div class="empty-hint">No relationships detected</div>';
  } else {
    relEl.innerHTML = rels.map(r => `
      <div class="rel-item">
        <div class="rel-row">
          <span style="color:var(--text)">${r.from}</span>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="color:var(--text3)"><path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span style="color:var(--text)">${r.to}</span>
          <span class="tag ${r.direction === 'positive' ? 'tag-rel-pos' : 'tag-rel-neg'}">${r.direction}</span>
          <span class="tag tag-dist">${r.strength}</span>
        </div>
        <div class="rel-note">${r.note || ''}</div>
      </div>`).join('');
  }
}

function resetSchema() {
  document.getElementById('schemaZone').style.display = 'none';
  document.getElementById('dataZone').style.display = 'none';
  document.getElementById('promptInput').focus();
  currentSchema = null;
  hideToast();
}

// ── STEP 2: Generate ──────────────────────────────
async function generateData() {
  if (!currentSchema) return;
  const rows = parseInt(document.getElementById('rowsInput').value) || 500;
  currentSchema._rows = rows;

  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  document.getElementById('dataZone').style.display = 'none';
  toast('Running data engine…', true);

  // Apply global null rate to all attributes if > 0
  const nullRate = parseFloat(document.getElementById('cfgNullRate').value) || 0;
  if (nullRate > 0) {
    currentSchema.attributes = currentSchema.attributes.map(a =>
      a.type === 'uuid' || a.unique ? a : { ...a, nullable: nullRate }
    );
  }

  try {
    const res = await fetch('/api/generate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema: currentSchema, rows }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderMetrics(data, rows);
    renderPreviewTable(data);
    renderColStats(data.stats);
    renderCharts(data.stats);
    showZone('dataZone');
    document.getElementById('exportRows').value = rows;
    toast(`Dataset ready — ${data.total_rows.toLocaleString()} rows × ${data.columns.length} columns.`);
  } catch (e) {
    toast('Error: ' + (e.message || 'Generation failed.'));
  }
  btn.disabled = false;
}

function renderMetrics(data, rows) {
  document.getElementById('metricsStrip').innerHTML = `
    <div class="metric-cell"><div class="metric-label">Total Rows</div><div class="metric-val hi">${data.total_rows.toLocaleString()}</div></div>
    <div class="metric-cell"><div class="metric-label">Columns</div><div class="metric-val">${data.columns.length}</div></div>
    <div class="metric-cell"><div class="metric-label">Relationships</div><div class="metric-val">${(currentSchema.relationships || []).length}</div></div>
  `;
}

function renderPreviewTable(data) {
  const cols = data.columns;
  const rows = data.preview;
  document.getElementById('previewTable').innerHTML = `
    <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => `<tr>${cols.map(c => {
      const v = row[c];
      if (v === null || v === undefined) return '<td class="td-null">null</td>';
      if (v === true)  return `<td class="td-true">true</td>`;
      if (v === false) return `<td class="td-false">false</td>`;
      const s = String(v);
      return `<td title="${s}">${s.length > 28 ? s.slice(0, 25) + '…' : s}</td>`;
    }).join('')}</tr>`).join('')}</tbody>
  `;
  document.getElementById('totalRowsLabel').textContent = data.total_rows.toLocaleString() + ' rows';
}

function renderColStats(stats) {
  const grid = document.getElementById('colstatsGrid');
  if (!stats) { grid.innerHTML = ''; return; }
  grid.innerHTML = Object.entries(stats).map(([name, s]) => {
    let inner = '';
    if (s.type === 'integer' || s.type === 'float') {
      inner = ['mean','std','min','p25','median','p75','max'].map(k =>
        s[k] !== undefined ? `<div class="cs-row"><span class="cs-key">${k}</span><span class="cs-val">${s[k]}</span></div>` : ''
      ).join('');
    } else if (s.type === 'boolean') {
      inner = `<div class="cs-row"><span class="cs-key">true</span><span class="cs-val">${s.true_pct}%</span></div>
               <div class="cs-row"><span class="cs-key">false</span><span class="cs-val">${s.false_pct}%</span></div>
               <div class="bool-track"><div class="bool-fill" style="width:${s.true_pct}%"></div></div>`;
    } else if (s.type === 'categorical') {
      inner = `<div class="cs-row"><span class="cs-key">unique</span><span class="cs-val">${s.unique}</span></div>
               <div class="cat-bar-wrap">${Object.entries(s.distribution).slice(0, 6).map(([k, v]) => `
                 <div class="cat-bar-row">
                   <span class="cat-bar-label" title="${k}">${k}</span>
                   <div class="cat-bar-track"><div class="cat-bar-fill" style="width:${v}%"></div></div>
                   <span class="cat-bar-pct">${v}%</span>
                 </div>`).join('')}</div>`;
    } else {
      inner = `<div class="cs-row"><span class="cs-key">type</span><span class="cs-val">${s.type}</span></div>
               <div class="cs-row"><span class="cs-key">count</span><span class="cs-val">${s.count}</span></div>`;
    }
    const nullLine = s.null_count ? `<div class="cs-row"><span class="cs-key">nulls</span><span class="cs-val" style="color:var(--a3)">${s.null_count}</span></div>` : '';
    return `<div class="cs-card"><div class="cs-name">${s.label || name}</div>${inner}${nullLine}</div>`;
  }).join('');
}

function renderCharts(stats) {
  const grid = document.getElementById('chartsGrid');
  if (!stats) { grid.innerHTML = ''; return; }
  const numericFields = Object.entries(stats).filter(([, s]) => s.histogram);
  if (!numericFields.length) {
    grid.innerHTML = '<div class="empty-hint" style="padding:2rem">No numeric fields to chart.</div>';
    return;
  }
  grid.innerHTML = numericFields.map(([name, s]) => {
    const bars = s.histogram;
    const maxCount = Math.max(...bars.map(b => b.count), 1);
    const barsHtml = bars.map(b => {
      const h = Math.max(4, Math.round((b.count / maxCount) * 76));
      return `<div class="bar-col" style="height:${h}px" title="${b.label}: ${b.count}"></div>`;
    }).join('');
    return `<div class="chart-card">
      <div class="chart-title">${s.label || name} — histogram</div>
      <div class="mini-chart">${barsHtml}</div>
      <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:10px;color:var(--text3);margin-top:4px">
        <span>${s.min}</span><span>median ${s.median}</span><span>${s.max}</span>
      </div>
    </div>`;
  }).join('');
}

// ── TABS ──────────────────────────────────────────
function switchTab(tab, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tab).style.display = 'block';
  btn.classList.add('active');
}

// ── EXPORT ────────────────────────────────────────
async function doExport(fmt) {
  if (!currentSchema) return;
  const rows = parseInt(document.getElementById('exportRows').value) || 500;
  document.querySelectorAll('.btn-export').forEach(b => b.disabled = true);
  toast(`Preparing ${fmt.toUpperCase()}… (${rows.toLocaleString()} rows)`, true);
  try {
    const res = await fetch(`/api/export/${fmt}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema: currentSchema, rows, format: fmt }),
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `syngen_${currentSchema.name?.replace(/\s+/g, '_').toLowerCase() || 'dataset'}.${fmt === 'excel' ? 'xlsx' : fmt}`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast(`${fmt.toUpperCase()} export complete — ${rows.toLocaleString()} rows.`);
  } catch (e) {
    toast('Export error: ' + e.message);
  }
  document.querySelectorAll('.btn-export').forEach(b => b.disabled = false);
}

// ── FIELD MODAL ───────────────────────────────────
function onTypeChange() {
  const t = document.getElementById('mFieldType').value;
  document.getElementById('numericOpts').style.display    = ['integer','float'].includes(t)     ? 'block' : 'none';
  document.getElementById('categoricalOpts').style.display = t === 'categorical'                ? 'block' : 'none';
  document.getElementById('booleanOpts').style.display     = t === 'boolean'                   ? 'block' : 'none';
  document.getElementById('dateOpts').style.display        = t === 'date'                      ? 'block' : 'none';
}

function openAddFieldModal() {
  editingFieldIndex = -1;
  document.getElementById('modalTitle').textContent     = 'Add Field';
  document.getElementById('modalSaveLabel').textContent = 'Add Field';
  clearModal();
  document.getElementById('modalBackdrop').style.display = 'flex';
  onTypeChange();
}

function openEditFieldModal(i) {
  editingFieldIndex = i;
  const a = currentSchema.attributes[i];
  document.getElementById('modalTitle').textContent     = 'Edit Field';
  document.getElementById('modalSaveLabel').textContent = 'Save Changes';
  document.getElementById('mFieldName').value   = a.name || '';
  document.getElementById('mFieldLabel').value  = a.label || '';
  document.getElementById('mFieldType').value   = a.type || 'integer';
  document.getElementById('mDist').value        = a.distribution || 'normal';
  document.getElementById('mMean').value        = a.mean ?? 50;
  document.getElementById('mStd').value         = a.std ?? 15;
  document.getElementById('mMin').value         = a.min ?? '';
  document.getElementById('mMax').value         = a.max ?? '';
  document.getElementById('mValues').value      = (a.values || []).join(', ');
  document.getElementById('mWeights').value     = (a.weights || a.probabilities || []).join(', ');
  document.getElementById('mTrueRate').value    = a.true_rate ?? 0.5;
  document.getElementById('mDateStart').value   = a.start || '2020-01-01';
  document.getElementById('mDateEnd').value     = a.end || '2024-12-31';
  document.getElementById('mNullable').value    = a.nullable ?? 0;
  document.getElementById('mPrefix').value      = a.prefix || '';
  document.getElementById('mUnique').checked    = !!a.unique;
  document.getElementById('modalBackdrop').style.display = 'flex';
  onTypeChange();
}

function clearModal() {
  ['mFieldName','mFieldLabel','mValues','mWeights','mMin','mMax','mPrefix'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('mFieldType').value  = 'integer';
  document.getElementById('mDist').value       = 'normal';
  document.getElementById('mMean').value       = 50;
  document.getElementById('mStd').value        = 15;
  document.getElementById('mTrueRate').value   = 0.5;
  document.getElementById('mDateStart').value  = '2020-01-01';
  document.getElementById('mDateEnd').value    = '2024-12-31';
  document.getElementById('mNullable').value   = 0;
  document.getElementById('mUnique').checked   = false;
}

function closeModal() {
  document.getElementById('modalBackdrop').style.display = 'none';
}

async function saveField() {
  const t = document.getElementById('mFieldType').value;
  const field = {
    name:  document.getElementById('mFieldName').value.trim().replace(/\s+/g, '_') || 'field',
    label: document.getElementById('mFieldLabel').value.trim() || undefined,
    type:  t,
  };
  if (['integer','float'].includes(t)) {
    field.distribution = document.getElementById('mDist').value;
    field.mean  = parseFloat(document.getElementById('mMean').value) || 50;
    field.std   = parseFloat(document.getElementById('mStd').value) || 15;
    const mn = document.getElementById('mMin').value; if (mn !== '') field.min = parseFloat(mn);
    const mx = document.getElementById('mMax').value; if (mx !== '') field.max = parseFloat(mx);
  }
  if (t === 'categorical') {
    field.values  = document.getElementById('mValues').value.split(',').map(s => s.trim()).filter(Boolean);
    const wStr    = document.getElementById('mWeights').value;
    if (wStr)     field.weights = wStr.split(',').map(Number);
  }
  if (t === 'boolean')    field.true_rate = parseFloat(document.getElementById('mTrueRate').value) || 0.5;
  if (t === 'date')       { field.start = document.getElementById('mDateStart').value; field.end = document.getElementById('mDateEnd').value; }
  const nl = parseFloat(document.getElementById('mNullable').value); if (nl > 0) field.nullable = nl;
  const pf = document.getElementById('mPrefix').value.trim(); if (pf) field.prefix = pf;
  if (document.getElementById('mUnique').checked) field.unique = true;

  if (editingFieldIndex >= 0) {
    currentSchema.attributes[editingFieldIndex] = field;
  } else {
    currentSchema.attributes.push(field);
  }
  renderSchema(currentSchema);
  closeModal();
}

async function removeField(i) {
  currentSchema.attributes.splice(i, 1);
  renderSchema(currentSchema);
}

// ── Init ──────────────────────────────────────────
loadExamples();
