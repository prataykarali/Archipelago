"""Offline single-page HTML/CSS/JS template for the 127.0.0.1 negative-control UI.

Zero external CDN links, zero AI suggestions, zero auto-signed attestations.
"""

from __future__ import annotations

UI_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>S5-C3 Negative-Control Human Verification (Offline Local)</title>
<style>
  :root { --bg:#f7f8fa; --card:#fff; --ink:#1b2430; --muted:#5a6778; --line:#d8dee6; --accent:#1d4ed8; --ok:#15803d; --err:#b91c1c; --warn:#b45309; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--ink); line-height:1.45; }
  header { background:#111827; color:#f9fafb; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; }
  header h1 { margin:0; font-size:1.05rem; }
  .meta-bar { font-size:0.82rem; color:#d1d5db; }
  main { display:grid; grid-template-columns: 320px 1fr; gap:16px; padding:16px; max-width:1500px; margin:0 auto; }
  @media (max-width: 960px) { main { grid-template-columns: 1fr; } }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px; margin-bottom:14px; }
  .panel h2, .panel h3 { margin:0 0 10px 0; font-size:1rem; }
  .q-tab { width:100%; text-align:left; padding:10px; margin-bottom:8px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }
  .q-tab.active { border-color:var(--accent); background:#eff6ff; }
  .badge { display:inline-block; font-size:0.74rem; padding:2px 6px; border-radius:4px; background:#e5e7eb; color:#111827; }
  .badge.ok { background:#dcfce7; color:var(--ok); }
  .badge.err { background:#fee2e2; color:var(--err); }
  .badge.warn { background:#fef3c7; color:var(--warn); }
  label { display:block; font-size:0.86rem; font-weight:600; margin:8px 0 4px 0; }
  input[type="text"], select, textarea { width:100%; padding:7px 9px; border:1px solid var(--line); border-radius:5px; font:inherit; font-size:0.9rem; }
  textarea { min-height:70px; resize:vertical; }
  button { padding:7px 12px; border:1px solid var(--line); border-radius:5px; background:#fff; cursor:pointer; font:inherit; font-size:0.88rem; }
  button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .passage-box { background:#f9fafb; border:1px solid var(--line); border-radius:6px; padding:10px; margin:8px 0; font-size:0.88rem; white-space:pre-wrap; }
  .doc-list { max-height:240px; overflow:auto; border:1px solid var(--line); border-radius:6px; padding:6px; font-size:0.82rem; }
  .doc-item { padding:4px 6px; cursor:pointer; border-radius:4px; display:flex; justify-content:space-between; }
  .doc-item:hover { background:#eff6ff; }
  .issue-err { color:var(--err); font-size:0.85rem; margin:4px 0; }
  .issue-warn { color:var(--warn); font-size:0.85rem; margin:4px 0; }
  .status-banner { padding:8px 12px; border-radius:6px; margin-bottom:10px; font-size:0.88rem; background:#eef2ff; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  @media (max-width: 720px) { .grid2 { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header>
  <div>
    <h1>S5-C3 Negative-Control Human Verification (Offline 127.0.0.1)</h1>
    <div id="corpusMeta" class="meta-bar">Loading frozen eligible corpus...</div>
  </div>
  <div class="row">
    <button type="button" class="primary" id="btnSave">Save + Backup + SHA-256</button>
    <button type="button" id="btnValidate">Validate</button>
    <button type="button" id="btnExport">Export Markdown</button>
  </div>
</header>

<main>
  <aside aria-label="Query navigation and corpus inventory">
    <section class="panel">
      <h2>Negative-Control Queries</h2>
      <div id="queryTabs"></div>
    </section>
    <section class="panel">
      <h2>Eligible Corpus Inventory</h2>
      <p style="font-size:0.8rem;color:var(--muted);margin-top:0;">Strictly restricted to frozen eligible documents. Click a document to inspect its passages.</p>
      <div id="docList" class="doc-list"></div>
    </section>
    <section class="panel">
      <h2>Validation Status</h2>
      <div id="validationBox">Not yet validated.</div>
    </section>
  </aside>

  <section aria-label="Active query verification workspace">
    <div id="statusBanner" class="status-banner" role="status" aria-live="polite">Ready. All human fields start blank and require explicit entry.</div>

    <div class="panel">
      <h2 id="activeQueryHeader">Select a query</h2>
      <p id="activeQueryText" style="font-size:0.98rem;font-weight:500;"></p>
    </div>

    <div class="panel">
      <h3>1. Frozen-Corpus Search (Strictly Eligible Passages Only)</h3>
      <div class="row">
        <input type="text" id="searchInput" placeholder="Search eligible frozen corpus..." aria-label="Corpus search query" style="flex:2;">
        <select id="searchMode" aria-label="Search mode" style="flex:1;">
          <option value="substring">Substring</option>
          <option value="tokens">All Tokens</option>
          <option value="regex">Regex</option>
        </select>
        <select id="searchDocFilter" aria-label="Document filter" style="flex:1;"><option value="">All eligible documents</option></select>
        <button type="button" class="primary" id="btnSearch">Search Corpus</button>
      </div>
      <div id="searchResults" style="margin-top:10px;"></div>
    </div>

    <div class="panel">
      <h3>2. Hydrated Candidate Passages &amp; Evidence Citations</h3>
      <div id="candidatesList"></div>
      <h4 style="margin:12px 0 6px 0;font-size:0.92rem;">Recorded Supporting Evidence</h4>
      <div id="evidenceList"></div>
    </div>

    <div class="panel">
      <h3>3. Human Classification &amp; D1 Evaluation Impact (Explicit Human Entry)</h3>
      <div class="grid2">
        <div>
          <label for="selClassification">Human Answerability Classification</label>
          <select id="selClassification">
            <option value="">-- Select explicitly --</option>
            <option value="NO_ANSWER_IN_FROZEN_CORPUS">NO_ANSWER_IN_FROZEN_CORPUS (verified corpus-wide)</option>
            <option value="NO_ANSWER_IN_SELECTED_PASSAGES">NO_ANSWER_IN_SELECTED_PASSAGES (selected only / HOLD)</option>
            <option value="ANSWERABLE_IN_FROZEN_CORPUS">ANSWERABLE_IN_FROZEN_CORPUS (cite verbatim evidence)</option>
            <option value="AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION">AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION</option>
            <option value="QUESTION_REQUIRING_REVISION">QUESTION_REQUIRING_REVISION</option>
          </select>
        </div>
        <div>
          <label for="selImpact">D1 Evaluation Impact Flag</label>
          <select id="selImpact">
            <option value="">-- Select explicitly --</option>
            <option value="RETAIN_AS_VERIFIED_NEGATIVE_CONTROL">RETAIN_AS_VERIFIED_NEGATIVE_CONTROL</option>
            <option value="RECLASSIFY_AS_ANSWERABLE">RECLASSIFY_AS_ANSWERABLE</option>
            <option value="EXCLUDE_AMBIGUOUS_OR_UNSUPPORTED_PREMISE">EXCLUDE_AMBIGUOUS_OR_UNSUPPORTED_PREMISE</option>
            <option value="EXCLUDE_REQUIRES_REVISION">EXCLUDE_REQUIRES_REVISION</option>
            <option value="HOLD_UNVERIFIED_NEGATIVE_CONTROL">HOLD_UNVERIFIED_NEGATIVE_CONTROL</option>
          </select>
        </div>
        <div>
          <label for="selPremise">External Factual Premise Assessment</label>
          <select id="selPremise">
            <option value="">-- Select explicitly --</option>
            <option value="VERIFIED_REAL_FACT">VERIFIED_REAL_FACT</option>
            <option value="UNVERIFIED_OR_UNREPORTED">UNVERIFIED_OR_UNREPORTED</option>
            <option value="SYNTHETIC_OR_FALSE_PREMISE">SYNTHETIC_OR_FALSE_PREMISE</option>
          </select>
        </div>
        <div>
          <label for="selScope">Corpus Scope Checked</label>
          <select id="selScope">
            <option value="">-- Select explicitly --</option>
            <option value="INSPECTED_HYDRATED_CANDIDATES_ONLY">INSPECTED_HYDRATED_CANDIDATES_ONLY</option>
            <option value="INSPECTED_HYDRATED_CANDIDATES_AND_53_DOC_INVENTORY">INSPECTED_HYDRATED_CANDIDATES_AND_53_DOC_INVENTORY</option>
            <option value="FULL_CORPUS_SEARCH_PERFORMED">FULL_CORPUS_SEARCH_PERFORMED</option>
          </select>
        </div>
      </div>
      <label for="txtRationale">Verification Rationale (required)</label>
      <textarea id="txtRationale" placeholder="Summarize candidate inspection and corpus-wide verification..."></textarea>
      <label for="txtRevisionNotes">Revision / Exclusion Notes (required for ambiguous, unsupported, or revision-requiring questions)</label>
      <textarea id="txtRevisionNotes" placeholder="Document premise issue, ambiguity, or required revision and D1 impact..."></textarea>
    </div>

    <div class="panel">
      <h3>4. Human Provenance &amp; Attestation (Never Auto-Signed)</h3>
      <div class="grid2">
        <div>
          <label for="inpVerifierId">Human Verifier ID / Pseudonym</label>
          <input type="text" id="inpVerifierId" placeholder="Enter your human identifier">
        </div>
        <div>
          <label for="selProvClass">Provenance Class</label>
          <select id="selProvClass">
            <option value="">-- Select explicitly --</option>
            <option value="INDEPENDENT_HUMAN">INDEPENDENT_HUMAN</option>
            <option value="HUMAN_POST_AI_EXPOSURE">HUMAN_POST_AI_EXPOSURE</option>
            <option value="AI_ASSISTED_OR_GENERATED">AI_ASSISTED_OR_GENERATED (blocks D1)</option>
          </select>
        </div>
        <div>
          <label for="inpAiDisclosure">AI Assistance / Exposure Disclosure</label>
          <input type="text" id="inpAiDisclosure" placeholder="e.g., NONE_INDEPENDENT_HUMAN">
        </div>
        <div>
          <label for="inpDateUtc">Verification Timestamp (ISO-8601 UTC)</label>
          <input type="text" id="inpDateUtc" placeholder="e.g., 2026-11-19T12:30:00Z">
        </div>
      </div>
      <label for="txtAttestation">Explicit Human Attestation Statement</label>
      <input type="text" id="txtAttestation" placeholder="I personally inspected the frozen eligible corpus without AI-generated answers.">
      <label style="display:flex;align-items:center;gap:8px;font-weight:600;margin-top:10px;">
        <input type="checkbox" id="chkAttested"> I explicitly sign and confirm this human provenance attestation.
      </label>
    </div>
  </section>
</main>

<script>
let STATE = { worksheet: null, documents: [], activeQid: null, lastSearchQuery: "" };

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function setStatus(msg) { document.getElementById("statusBanner").textContent = msg; }
function activeRecord() { return (STATE.worksheet.queries || []).find(q => q.query_id === STATE.activeQid); }

async function api(path, method="GET", body=null) {
  const opts = { method, headers: {} };
  if (body !== null) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
  return data;
}

function syncFormToRecord() {
  const q = activeRecord();
  if (!q) return;
  q.human_answerability_classification = document.getElementById("selClassification").value || null;
  q.d1_evaluation_impact = document.getElementById("selImpact").value || null;
  q.external_factual_premise_assessment = document.getElementById("selPremise").value || null;
  q.corpus_scope_checked = document.getElementById("selScope").value || null;
  q.verification_rationale = document.getElementById("txtRationale").value;
  q.revision_or_exclusion_notes = document.getElementById("txtRevisionNotes").value;
  q.human_provenance = {
    verifier_id: document.getElementById("inpVerifierId").value,
    provenance_class: document.getElementById("selProvClass").value || null,
    ai_assistance_disclosure: document.getElementById("inpAiDisclosure").value,
    verification_date_utc: document.getElementById("inpDateUtc").value,
    human_attestation_text: document.getElementById("txtAttestation").value,
    human_attestation_confirmed: document.getElementById("chkAttested").checked
  };
}

function renderTabs() {
  const box = document.getElementById("queryTabs");
  box.innerHTML = "";
  for (const q of STATE.worksheet.queries) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "q-tab" + (q.query_id === STATE.activeQid ? " active" : "");
    const cls = q.human_answerability_classification || "UNCLASSIFIED";
    const badgeClass = q.human_answerability_classification ? "ok" : "warn";
    btn.innerHTML = `<strong>${esc(q.query_id)}</strong> <span class="badge ${badgeClass}">${esc(cls)}</span><div style="font-size:0.78rem;color:var(--muted);margin-top:4px;">${esc(q.domain)}</div>`;
    btn.onclick = () => { syncFormToRecord(); STATE.activeQid = q.query_id; renderAll(); };
    box.appendChild(btn);
  }
}

function renderActiveQuery() {
  const q = activeRecord();
  if (!q) return;
  document.getElementById("activeQueryHeader").textContent = `${q.query_id} (${q.legacy_query_id}) — ${q.domain}`;
  document.getElementById("activeQueryText").textContent = q.query_text;
  document.getElementById("selClassification").value = q.human_answerability_classification || "";
  document.getElementById("selImpact").value = q.d1_evaluation_impact || "";
  document.getElementById("selPremise").value = q.external_factual_premise_assessment || "";
  document.getElementById("selScope").value = q.corpus_scope_checked || "";
  document.getElementById("txtRationale").value = q.verification_rationale || "";
  document.getElementById("txtRevisionNotes").value = q.revision_or_exclusion_notes || "";
  const p = q.human_provenance || {};
  document.getElementById("inpVerifierId").value = p.verifier_id || "";
  document.getElementById("selProvClass").value = p.provenance_class || "";
  document.getElementById("inpAiDisclosure").value = p.ai_assistance_disclosure || "";
  document.getElementById("inpDateUtc").value = p.verification_date_utc || "";
  document.getElementById("txtAttestation").value = p.human_attestation_text || "";
  document.getElementById("chkAttested").checked = Boolean(p.human_attestation_confirmed);

  const cBox = document.getElementById("candidatesList");
  cBox.innerHTML = "";
  for (const cand of (q.hydrated_candidates || [])) {
    const div = document.createElement("div");
    div.className = "passage-box";
    div.innerHTML = `<div><strong>${esc(cand.passage_id)}</strong> (p.${esc(cand.page_number)}, <span class="badge ok">${esc(cand.corpus_eligibility_status)}</span>)</div>`;
    const row = document.createElement("div");
    row.className = "row";
    row.style.marginTop = "6px";
    const sel = document.createElement("select");
    sel.style.width = "auto";
    sel.innerHTML = `<option value="">contains_answer?</option><option value="NO">NO</option><option value="YES">YES</option><option value="PARTIAL_OR_AMBIGUOUS">PARTIAL_OR_AMBIGUOUS</option>`;
    sel.value = cand.contains_answer || "";
    sel.onchange = () => { cand.contains_answer = sel.value || null; if (!q.checked_passage_ids.includes(cand.passage_id)) q.checked_passage_ids.push(cand.passage_id); };
    const note = document.createElement("input");
    note.type = "text"; note.placeholder = "Inspection note..."; note.value = cand.inspection_note || ""; note.style.flex = "1";
    note.oninput = () => { cand.inspection_note = note.value; };
    const btnView = document.createElement("button");
    btnView.type = "button"; btnView.textContent = "Inspect Verbatim";
    btnView.onclick = () => inspectPassageInto(cand.passage_id, div);
    row.append(sel, note, btnView);
    div.appendChild(row);
    cBox.appendChild(div);
  }
  renderEvidence(q);
}

function renderEvidence(q) {
  const eBox = document.getElementById("evidenceList");
  const evs = q.supporting_evidence || [];
  if (!evs.length) { eBox.innerHTML = '<div style="font-size:0.84rem;color:var(--muted);">No supporting evidence citations recorded yet.</div>'; return; }
  eBox.innerHTML = evs.map(ev => `<div class="passage-box"><strong>${esc(ev.passage_id)}</strong> (${esc(ev.corpus_eligibility_status)})<br>Search: <code>${esc(ev.search_query_used)}</code><br>Excerpt: "${esc(ev.verbatim_excerpt)}"</div>`).join("");
}

async function inspectPassageInto(pid, container) {
  try {
    const data = await api("/api/passage?passage_id=" + encodeURIComponent(pid));
    let pre = container.querySelector(".verbatim-preview");
    if (!pre) { pre = document.createElement("div"); pre.className = "verbatim-preview"; pre.style.marginTop = "8px"; pre.style.borderTop = "1px solid var(--line)"; pre.style.paddingTop = "6px"; container.appendChild(pre); }
    pre.textContent = data.passage.text;
  } catch (err) { setStatus("Inspect error: " + err.message); }
}

function renderValidation(report) {
  const box = document.getElementById("validationBox");
  const badge = report.valid ? (report.ready_for_d1 ? '<span class="badge ok">VALID &amp; D1-READY</span>' : '<span class="badge warn">VALID (HOLD FOR D1)</span>') : `<span class="badge err">INVALID (${report.error_count} errors)</span>`;
  const issuesHtml = (report.issues || []).map(i => `<div class="${i.severity === "ERROR" ? "issue-err" : "issue-warn"}">[${esc(i.query_id || "GLOBAL")}] ${esc(i.code)}: ${esc(i.message)}</div>`).join("");
  box.innerHTML = badge + (issuesHtml || '<div style="margin-top:6px;font-size:0.84rem;">All checks passed.</div>');
}

function renderAll() { renderTabs(); renderActiveQuery(); }

async function loadInitial() {
  const data = await api("/api/state");
  STATE.worksheet = data.worksheet;
  STATE.documents = data.documents;
  STATE.activeQid = (data.worksheet.queries[0] || {}).query_id || null;
  document.getElementById("corpusMeta").textContent = `${data.worksheet.corpus_version} | ${data.worksheet.corpus_passage_count} eligible passages / ${data.worksheet.corpus_doc_count} docs | SHA-256: ${data.worksheet.corpus_sha256.slice(0, 16)}...`;
  const docList = document.getElementById("docList");
  const docFilter = document.getElementById("searchDocFilter");
  docList.innerHTML = "";
  for (const d of STATE.documents) {
    const opt = document.createElement("option"); opt.value = d.doc_id; opt.textContent = `${d.doc_id} (${d.passage_count})`; docFilter.appendChild(opt);
    const row = document.createElement("div"); row.className = "doc-item";
    row.innerHTML = `<span>${esc(d.doc_id)}</span><span class="badge">${esc(d.passage_count)}</span>`;
    row.onclick = async () => {
      const res = await api("/api/document?doc_id=" + encodeURIComponent(d.doc_id));
      const box = document.getElementById("searchResults");
      box.innerHTML = `<strong>Document ${esc(d.doc_id)} (${res.passages.length} eligible passages)</strong>` + res.passages.map(p => `<div class="passage-box"><strong>${esc(p.passage_id)}</strong> (p.${esc(p.page_number)})<br>${esc(p.text)}</div>`).join("");
    };
    docList.appendChild(row);
  }
  renderAll();
  renderValidation(data.validation);
}

document.getElementById("btnSearch").onclick = async () => {
  const q = document.getElementById("searchInput").value.trim();
  if (!q) return;
  try {
    syncFormToRecord();
    const res = await api("/api/search", "POST", { query: q, mode: document.getElementById("searchMode").value, doc_id: document.getElementById("searchDocFilter").value || null, query_id: STATE.activeQid });
    STATE.lastSearchQuery = q;
    const box = document.getElementById("searchResults");
    box.innerHTML = `<div><strong>${res.result.total_hits} eligible hit(s)</strong> for <code>${esc(q)}</code></div>`;
    for (const h of res.result.hits) {
      const div = document.createElement("div");
      div.className = "passage-box";
      div.innerHTML = `<div><strong>${esc(h.passage_id)}</strong> (p.${esc(h.page_number)}, <span class="badge ok">${esc(h.corpus_eligibility_status)}</span>)</div><div>${esc(h.matched_excerpt)}</div>`;
      const btnCite = document.createElement("button");
      btnCite.type = "button"; btnCite.textContent = "Cite Excerpt as Evidence"; btnCite.style.marginTop = "6px";
      btnCite.onclick = async () => {
        const cited = await api("/api/evidence", "POST", { query_id: STATE.activeQid, passage_id: h.passage_id, verbatim_excerpt: h.matched_excerpt, search_query_used: q });
        STATE.worksheet = cited.worksheet;
        renderActiveQuery();
        setStatus("Cited corpus-eligible excerpt from " + h.passage_id);
      };
      div.appendChild(btnCite);
      box.appendChild(div);
    }
  } catch (err) { setStatus("Search error: " + err.message); }
};

document.getElementById("btnSave").onclick = async () => {
  try {
    syncFormToRecord();
    const res = await api("/api/save", "POST", { worksheet: STATE.worksheet });
    STATE.worksheet = res.worksheet;
    renderValidation(res.validation);
    setStatus(`Saved. SHA-256: ${res.manifest.worksheet_sha256.slice(0, 16)}... | Backup: ${res.manifest.backup_path}`);
  } catch (err) { setStatus("Save error: " + err.message); }
};

document.getElementById("btnValidate").onclick = async () => {
  try {
    syncFormToRecord();
    const res = await api("/api/validate", "POST", { worksheet: STATE.worksheet });
    renderValidation(res.validation);
    setStatus(res.validation.valid ? "Validation PASSED." : `Validation FAILED with ${res.validation.error_count} error(s).`);
  } catch (err) { setStatus("Validate error: " + err.message); }
};

document.getElementById("btnExport").onclick = async () => {
  try {
    syncFormToRecord();
    const res = await api("/api/export", "POST", { worksheet: STATE.worksheet });
    setStatus(`Exported Markdown to ${res.export.export_path} (SHA-256: ${res.export.export_sha256.slice(0, 16)}...)`);
  } catch (err) { setStatus("Export error: " + err.message); }
};

loadInitial().catch(err => setStatus("Failed to load state: " + err.message));
</script>
</body>
</html>
"""
