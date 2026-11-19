"""Self-contained offline HTML template for the 127.0.0.1 A/C Adjudication UI."""

from __future__ import annotations

ADJUDICATION_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>S5-C3 Offline Human A/C Adjudication Workbench</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem 1.5rem; background: #f6f7f9; color: #1b222c; }
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #d0d7de; padding-bottom: 0.75rem; margin-bottom: 1rem; }
  .badge { background: #1f6feb; color: #fff; padding: 0.25rem 0.6rem; border-radius: 4px; font-size: 0.85rem; }
  .card { background: #fff; border: 1px solid #d0d7de; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  pre { white-space: pre-wrap; background: #f3f4f6; padding: 0.75rem; border-radius: 4px; font-size: 0.9rem; }
  label { display: block; font-weight: 600; margin-top: 0.5rem; }
  input, select, textarea { width: 100%; box-sizing: border-box; padding: 0.45rem; margin-top: 0.2rem; border: 1px solid #8c959f; border-radius: 4px; }
  button { background: #1f6feb; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; margin-top: 0.75rem; }
  button.secondary { background: #57606a; margin-right: 0.5rem; }
  .status { margin-top: 0.5rem; font-weight: 600; }
  .err { color: #cf222e; }
  .ok { color: #1a7f37; }
</style>
</head>
<body>
<header>
  <div>
    <h1 style="margin:0;">S5-C3 Human A/C Adjudication Workbench (Offline Local Only)</h1>
    <small>Loopback 127.0.0.1 only &bull; Zero AI suggestions &bull; Human rationale required for every disagreement</small>
  </div>
  <div class="badge" id="progress-badge">Loading...</div>
</header>

<section class="card" aria-label="Disagreement navigation">
  <button class="secondary" id="prev-btn" type="button">Previous</button>
  <button class="secondary" id="next-btn" type="button">Next</button>
  <span id="item-label"></span>
</section>

<section class="card" id="item-panel" aria-label="Current disagreement item">
  <h2 id="pair-heading">No disagreements loaded</h2>
  <p><strong>Query:</strong> <span id="query-text"></span></p>
  <p><strong>Passage ID:</strong> <code id="passage-id"></code></p>
  <pre id="passage-text"></pre>
  <div class="grid">
    <div>
      <h3>Reviewer A (INDEPENDENT_HUMAN)</h3>
      <p>Grade: <strong id="rev-a-grade"></strong> | Confidence: <span id="rev-a-conf"></span></p>
      <p>Quote: <code id="rev-a-quote"></code></p>
      <p>Notes: <span id="rev-a-notes"></span></p>
    </div>
    <div>
      <h3>Reviewer C (INDEPENDENT_HUMAN)</h3>
      <p>Grade: <strong id="rev-c-grade"></strong> | Confidence: <span id="rev-c-conf"></span></p>
      <p>Quote: <code id="rev-c-quote"></code></p>
      <p>Notes: <span id="rev-c-notes"></span></p>
    </div>
  </div>
  <hr>
  <h3>Human Adjudication Decision</h3>
  <label for="adj-grade">Adjudicated Grade (0, 1, or 2)</label>
  <select id="adj-grade">
    <option value="">-- Select human grade --</option>
    <option value="0">0 - Irrelevant / Distractor</option>
    <option value="1">1 - Partially Relevant / Background</option>
    <option value="2">2 - Highly Relevant / Grounding Evidence</option>
  </select>
  <label for="adj-quote">Verbatim Supporting Quotation (exact substring for 1/2; blank for 0)</label>
  <textarea id="adj-quote" rows="2"></textarea>
  <label for="adj-rationale">Human Adjudication Rationale (required, &ge; 10 chars)</label>
  <textarea id="adj-rationale" rows="3"></textarea>
  <label for="adj-id">Human Adjudicator ID</label>
  <input id="adj-id" type="text" placeholder="e.g. ADJ_HUMAN_01">
  <button id="save-decision-btn" type="button">Save Human Decision</button>
  <div class="status" id="decision-status" role="status"></div>
</section>

<section class="card" aria-label="Human adjudicator provenance">
  <h2>Human Adjudicator Provenance Attestation (Never Auto-Signed)</h2>
  <label for="prov-id">Adjudicator ID</label>
  <input id="prov-id" type="text">
  <label for="prov-class">Provenance Class</label>
  <select id="prov-class">
    <option value="">-- Select --</option>
    <option value="ADJUDICATED_HUMAN">ADJUDICATED_HUMAN</option>
    <option value="NOT_REQUIRED_ZERO_DISAGREEMENTS">NOT_REQUIRED_ZERO_DISAGREEMENTS</option>
  </select>
  <label for="prov-assist">Assistance Declaration</label>
  <select id="prov-assist">
    <option value="">-- Select --</option>
    <option value="NONE_INDEPENDENT_HUMAN">NONE_INDEPENDENT_HUMAN</option>
  </select>
  <label for="prov-signer">Attestation Signer (Human Name / Pseudonym)</label>
  <input id="prov-signer" type="text">
  <label><input id="prov-signed" type="checkbox" style="width:auto;"> I attest this adjudication was performed independently by a human without AI generation.</label>
  <button id="save-prov-btn" type="button">Save Human Provenance Attestation</button>
  <div class="status" id="prov-status" role="status"></div>
</section>

<script>
let worksheet = null;
let currentIdx = 0;

async function loadWorksheet() {
  const res = await fetch('/api/worksheet');
  const data = await res.json();
  worksheet = data.worksheet;
  document.getElementById('progress-badge').textContent =
    data.completed_count + ' / ' + data.total_disagreements + ' adjudicated';
  const p = worksheet.adjudicator_provenance || {};
  document.getElementById('prov-id').value = p.adjudicator_id || '';
  document.getElementById('prov-class').value = p.provenance_class || '';
  document.getElementById('prov-assist').value = p.assistance_declaration || '';
  document.getElementById('prov-signer').value = p.attestation_signer || '';
  document.getElementById('prov-signed').checked = Boolean(p.human_attestation_signed);
  renderCurrent();
}

function renderCurrent() {
  const items = (worksheet && worksheet.disagreements) || [];
  if (!items.length) {
    document.getElementById('pair-heading').textContent = '0 disagreements to adjudicate.';
    return;
  }
  currentIdx = Math.max(0, Math.min(currentIdx, items.length - 1));
  const item = items[currentIdx];
  document.getElementById('item-label').textContent = 'Item ' + (currentIdx + 1) + ' of ' + items.length;
  document.getElementById('pair-heading').textContent = item.pair_id + ' (' + item.query_id + ')';
  document.getElementById('query-text').textContent = item.query_text;
  document.getElementById('passage-id').textContent = item.passage_id;
  document.getElementById('passage-text').textContent = item.passage_text || '[Passage text not loaded]';
  document.getElementById('rev-a-grade').textContent = item.reviewer_a.relevance_grade;
  document.getElementById('rev-a-conf').textContent = item.reviewer_a.confidence;
  document.getElementById('rev-a-quote').textContent = item.reviewer_a.supporting_quotation;
  document.getElementById('rev-a-notes').textContent = item.reviewer_a.reviewer_notes;
  document.getElementById('rev-c-grade').textContent = item.reviewer_c.relevance_grade;
  document.getElementById('rev-c-conf').textContent = item.reviewer_c.confidence;
  document.getElementById('rev-c-quote').textContent = item.reviewer_c.supporting_quotation;
  document.getElementById('rev-c-notes').textContent = item.reviewer_c.reviewer_notes;
  document.getElementById('adj-grade').value = item.adjudicated_grade === null ? '' : String(item.adjudicated_grade);
  document.getElementById('adj-quote').value = item.adjudication_evidence_quote || '';
  document.getElementById('adj-rationale').value = item.adjudication_rationale || '';
  document.getElementById('adj-id').value = item.adjudicator_id || '';
}

document.getElementById('prev-btn').addEventListener('click', () => { currentIdx--; renderCurrent(); });
document.getElementById('next-btn').addEventListener('click', () => { currentIdx++; renderCurrent(); });

document.getElementById('save-decision-btn').addEventListener('click', async () => {
  const items = (worksheet && worksheet.disagreements) || [];
  if (!items.length) return;
  const item = items[currentIdx];
  const gradeVal = document.getElementById('adj-grade').value;
  const payload = {
    pair_id: item.pair_id,
    adjudicated_grade: gradeVal === '' ? null : Number(gradeVal),
    adjudication_evidence_quote: document.getElementById('adj-quote').value,
    adjudication_rationale: document.getElementById('adj-rationale').value,
    adjudicator_id: document.getElementById('adj-id').value,
  };
  const res = await fetch('/api/decision', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  const el = document.getElementById('decision-status');
  el.textContent = data.message || data.error;
  el.className = 'status ' + (res.ok ? 'ok' : 'err');
  if (res.ok) await loadWorksheet();
});

document.getElementById('save-prov-btn').addEventListener('click', async () => {
  const payload = {
    adjudicator_id: document.getElementById('prov-id').value,
    provenance_class: document.getElementById('prov-class').value,
    assistance_declaration: document.getElementById('prov-assist').value,
    attestation_signer: document.getElementById('prov-signer').value,
    human_attestation_signed: document.getElementById('prov-signed').checked,
  };
  const res = await fetch('/api/provenance', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  });
  const data = await res.json();
  const el = document.getElementById('prov-status');
  el.textContent = data.message || data.error;
  el.className = 'status ' + (res.ok ? 'ok' : 'err');
  if (res.ok) await loadWorksheet();
});

loadWorksheet();
</script>
</body>
</html>
"""
