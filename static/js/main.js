let currentSchema = null;
let currentRows = 500;

// Load examples from API
async function loadExamples() {
  try {
    const res = await fetch('/api/examples');
    const data = await res.json();
    const chipsEl = document.getElementById('exampleChips');
    data.examples.forEach(ex => {
      const chip = document.createElement('button');
      chip.className = 'chip';
      chip.textContent = ex.label;
      chip.onclick = () => {
        document.getElementById('promptInput').value = ex.prompt;
        document.getElementById('promptInput').focus();
      };
      chipsEl.appendChild(chip);
    });
  } catch (e) { console.warn('Could not load examples', e); }
}

function setStatus(msg, loading = false) {
  const bar = document.getElementById('statusBar');
  const spinner = document.getElementById('spinner');
  const text = document.getElementById('statusText');
  bar.style.display = 'flex';
  spinner.style.display = loading ? 'block' : 'none';
  text.textContent = msg;
}

function hideStatus() {
  document.getElementById('statusBar').style.display = 'none';
}

function showSection(id) {
  const el = document.getElementById(id);
  if (el) {
    el.style.display = 'block';
    el.style.animation = 'none';
    requestAnimationFrame(() => { el.style.animation = 'fadeUp 0.35s ease both'; });
  }
}

async function interpretPrompt() {
  const prompt = document.getElementById('promptInput').value.trim();
  if (!prompt) return;
  currentRows = parseInt(document.getElementById('rowsInput').value) || 500;

  const btn = document.getElementById('interpretBtn');
  btn.disabled = true;
  document.getElementById('schemaSection').style.display = 'none';
  document.getElementById('dataSection').style.display = 'none';
  setStatus('Sending prompt to AI interpreter…', true);

  try {
    const res = await fetch('/api/interpret', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, rows: currentRows })
    });
    if (!res.ok) throw new Error(await res.text());
    const { schema } = await res.json();
    currentSchema = schema;
    renderSchema(schema);
    showSection('schemaSection');
    setStatus(`Schema extracted — ${schema.attributes.length} attributes, ${(schema.relationships||[]).length} relationships.`);
  } catch (e) {
    setStatus('Error: ' + (e.message || 'Could not interpret prompt.'));
  }
  btn.disabled = false;
}

function renderSchema(schema) {
  document.getElementById('schemaDatasetName').textContent = schema.name || '';
  document.getElementById('attrCount').textContent = schema.attributes.length;
  document.getElementById('relCount').textContent = (schema.relationships || []).length;

  const attrList = document.getElementById('attrList');
  attrList.innerHTML = schema.attributes.map(a => {
    const distTag = a.distribution ? `<span class="tag tag-dist">${a.distribution}</span>` : '';
    const valTag = a.values ? `<span class="tag tag-dist">${a.values.slice(0,4).join(', ')}${a.values.length>4?'…':''}</span>` : '';
    const trueTag = a.true_rate !== undefined ? `<span class="tag tag-dist">${Math.round(a.true_rate*100)}% true</span>` : '';
    return `<div class="attr-item">
      <span class="attr-name">${a.name}</span>
      <div class="attr-tags">
        <span class="tag tag-type">${a.type}</span>
        ${distTag}${valTag}${trueTag}
        ${a.mean !== undefined ? `<span class="tag tag-dist">μ=${a.mean}</span>` : ''}
        ${a.std !== undefined ? `<span class="tag tag-dist">σ=${a.std}</span>` : ''}
      </div>
    </div>`;
  }).join('');

  const relList = document.getElementById('relList');
  const rels = schema.relationships || [];
  if (!rels.length) {
    relList.innerHTML = `<div class="empty-msg">No relationships detected</div>`;
    return;
  }
  relList.innerHTML = rels.map(r => `
    <div class="rel-item">
      <div class="rel-fields">
        <span>${r.from}</span>
        <span class="rel-arrow">→</span>
        <span>${r.to}</span>
        <span class="tag ${r.direction==='positive'?'tag-rel-pos':'tag-rel-neg'}" style="margin-left:6px">${r.direction}</span>
        <span class="tag tag-dist">${r.strength}</span>
      </div>
      <div class="rel-note">${r.note || ''}</div>
    </div>
  `).join('');
}

async function generateData() {
  if (!currentSchema) return;
  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  setStatus('Generating synthetic dataset…', true);
  document.getElementById('dataSection').style.display = 'none';

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema: currentSchema, rows: currentRows })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderPreview(data);
    renderStats(data);
    renderStatsGrid(data);
    showSection('dataSection');
    setStatus(`Dataset ready — ${data.total_rows.toLocaleString()} rows × ${data.columns.length} columns.`);
  } catch (e) {
    setStatus('Error: ' + (e.message || 'Generation failed.'));
  }
  btn.disabled = false;
}

function renderPreview(data) {
  const table = document.getElementById('previewTable');
  const cols = data.columns;
  const rows = data.preview;

  table.innerHTML = `
    <thead><tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => `<tr>${cols.map(c => {
      const v = row[c];
      if (v === null || v === undefined) return '<td>—</td>';
      if (typeof v === 'boolean') return `<td style="color:${v?'var(--accent)':'var(--red)'}">${v}</td>`;
      return `<td>${v}</td>`;
    }).join('')}</tr>`).join('')}</tbody>
  `;
  document.getElementById('totalRowsNote').textContent = data.total_rows.toLocaleString() + ' rows';
}

function renderStats(data) {
  document.getElementById('statsStrip').innerHTML = `
    <div class="stat-cell"><div class="stat-label">Total Rows</div><div class="stat-value accent">${data.total_rows.toLocaleString()}</div></div>
    <div class="stat-cell"><div class="stat-label">Columns</div><div class="stat-value">${data.columns.length}</div></div>
    <div class="stat-cell"><div class="stat-label">Relationships</div><div class="stat-value">${(currentSchema.relationships||[]).length}</div></div>
  `;
}

function renderStatsGrid(data) {
  const grid = document.getElementById('statsGrid');
  const stats = data.stats || {};
  grid.innerHTML = Object.entries(stats).map(([name, s]) => {
    if (s.type === 'boolean') {
      return `<div class="stat-card">
        <div class="stat-card-name">${name}</div>
        <div class="stat-row"><span class="stat-row-label">true</span><span class="stat-row-val">${s.true_pct}%</span></div>
        <div class="stat-row"><span class="stat-row-label">false</span><span class="stat-row-val">${s.false_pct}%</span></div>
        <div class="bool-bar"><div class="bool-bar-fill" style="width:${s.true_pct}%"></div></div>
      </div>`;
    }
    if (s.type === 'categorical') {
      return `<div class="stat-card">
        <div class="stat-card-name">${name}</div>
        ${Object.entries(s.distribution).slice(0,5).map(([k,v]) => `
          <div class="stat-row"><span class="stat-row-label">${k}</span><span class="stat-row-val">${v}%</span></div>
        `).join('')}
      </div>`;
    }
    if (s.type === 'integer' || s.type === 'float') {
      return `<div class="stat-card">
        <div class="stat-card-name">${name}</div>
        <div class="stat-row"><span class="stat-row-label">mean</span><span class="stat-row-val">${s.mean}</span></div>
        <div class="stat-row"><span class="stat-row-label">std</span><span class="stat-row-val">${s.std}</span></div>
        <div class="stat-row"><span class="stat-row-label">min</span><span class="stat-row-val">${s.min}</span></div>
        <div class="stat-row"><span class="stat-row-label">median</span><span class="stat-row-val">${s.median}</span></div>
        <div class="stat-row"><span class="stat-row-label">max</span><span class="stat-row-val">${s.max}</span></div>
      </div>`;
    }
    return `<div class="stat-card"><div class="stat-card-name">${name}</div><div class="stat-row"><span class="stat-row-label">type</span><span class="stat-row-val">${s.type}</span></div></div>`;
  }).join('');
}

function showTab(tab, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.sub-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + tab).style.display = 'block';
  btn.classList.add('active');
}

async function exportData(fmt) {
  if (!currentSchema) return;
  const btns = document.querySelectorAll('.btn-export');
  btns.forEach(b => b.disabled = true);
  setStatus(`Preparing ${fmt.toUpperCase()} export…`, true);

  try {
    const res = await fetch(`/api/export/${fmt}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schema: currentSchema, rows: currentRows, format: fmt })
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `syngen_dataset.${fmt === 'excel' ? 'xlsx' : fmt}`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setStatus(`${fmt.toUpperCase()} exported successfully.`);
  } catch (e) {
    setStatus('Export error: ' + e.message);
  }
  btns.forEach(b => b.disabled = false);
}

// Init
loadExamples();
