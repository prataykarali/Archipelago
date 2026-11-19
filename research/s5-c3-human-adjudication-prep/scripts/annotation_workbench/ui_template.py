"""Offline, accessible, strictly blinded HTML/CSS template for local browser UI."""

from __future__ import annotations

from .ui_script import WORKBENCH_JS

WORKBENCH_CSS = """
:root {
  --bg: #f6f7f9;
  --surface: #ffffff;
  --border: #d0d7de;
  --text: #1f2328;
  --muted: #57606a;
  --accent: #0969da;
  --ok: #1a7f37;
  --warn: #9a6700;
  --err: #cf222e;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 12px 20px;
}
.header-top {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
h1 { margin: 0; font-size: 1.15rem; }
.progress-wrap {
  width: 220px;
  height: 10px;
  background: #e6ebf1;
  border-radius: 5px;
  overflow: hidden;
}
.progress-fill { height: 100%; background: var(--ok); width: 0%; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}
.badge-ok { background: #dafbe1; color: var(--ok); }
.badge-warn { background: #fff8c5; color: var(--warn); }
.status-banner {
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.9rem;
}
.status-ok { background: #eaf5ff; color: #0550ae; }
.status-error { background: #ffebe9; color: var(--err); }
.layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  padding: 16px 20px;
  max-width: 1360px;
  margin: 0 auto;
}
aside, main, .panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
}
.query-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.query-item {
  text-align: left;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  cursor: pointer;
  font-size: 0.85rem;
}
.query-item.active {
  background: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}
.passage-box {
  background: #f8fafc;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 14px;
  white-space: pre-wrap;
  font-family: Georgia, serif;
  font-size: 0.98rem;
  margin: 10px 0;
  user-select: text;
}
.meta-line { font-size: 0.84rem; color: var(--muted); }
.query-callout {
  background: #f0f6fc;
  border-left: 4px solid var(--accent);
  padding: 10px 12px;
  margin: 8px 0;
  font-weight: 600;
}
.field-group { margin: 12px 0; }
.field-group label { display: block; font-weight: 600; margin-bottom: 4px; }
.radio-row { display: flex; flex-wrap: wrap; gap: 12px; }
.radio-row label { font-weight: 500; display: flex; align-items: center; gap: 6px; }
textarea, input[type="text"], input[type="number"], select {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.92rem;
}
button {
  padding: 7px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  cursor: pointer;
  font-weight: 600;
}
button.primary { background: var(--accent); color: #ffffff; border-color: var(--accent); }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.field-hint { font-size: 0.82rem; margin-top: 4px; }
.hint-ok { color: var(--ok); }
.hint-warn { color: var(--warn); }
.hint-err { color: var(--err); }
.prov-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
details.provenance-panel { margin-top: 16px; }
@media (max-width: 860px) {
  .layout { grid-template-columns: 1fr; }
}
"""


def render_workbench_html() -> str:
    """Render the complete offline, zero-CDN, strictly blinded HTML document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Archipelago S5-C3 Local Human Annotation Workbench</title>
  <style>{WORKBENCH_CSS}</style>
</head>
<body>
  <header>
    <div class="header-top">
      <div>
        <h1>S5-C3 Blinded Human Annotation Workbench (Local-Only)</h1>
        <div class="meta-line">
          <span id="overall-count">0 / 254 completed</span> &middot;
          <span id="flagged-count">Flagged: 0</span> &middot;
          <span id="invalid-count">Needs fix: 0</span>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <div class="progress-wrap" aria-label="Overall completion progress">
          <div id="overall-progress-bar" class="progress-fill" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>
        </div>
        <span id="provenance-badge" class="badge badge-warn">Provenance: Unsigned</span>
        <button id="btn-backup" type="button">Create Backup</button>
        <button id="btn-export" type="button" class="primary">Validate &amp; Export</button>
      </div>
    </div>
    <div id="status-banner" class="status-banner status-ok" role="status" aria-live="polite">
      Initializing local workbench...
    </div>
  </header>

  <div class="layout">
    <aside aria-label="Query navigation">
      <strong>Queries</strong>
      <div id="query-list" class="query-list"></div>
    </aside>

    <main>
      <div class="toolbar" aria-label="Filter and pair navigation">
        <label for="filter-select" class="meta-line">Filter:</label>
        <select id="filter-select" style="width:auto;">
          <option value="all">All Pairs</option>
          <option value="ungraded">Ungraded / Incomplete</option>
          <option value="completed">Completed</option>
          <option value="flagged">Flagged</option>
          <option value="invalid">Needs Validation Fix</option>
        </select>
        <input id="search-input" type="text" placeholder="Search pair ID or doc..." style="width:200px;" aria-label="Search pair ID or document">
        <button id="btn-prev" type="button">Previous</button>
        <span id="nav-position" class="meta-line">0 / 0</span>
        <button id="btn-next" type="button">Next</button>
        <input id="jump-index" type="number" min="1" placeholder="#" style="width:72px;" aria-label="Jump to filtered index">
        <button id="btn-jump" type="button">Go</button>
      </div>

      <div id="empty-state" hidden>
        <p>No candidate pairs match the current filter.</p>
      </div>

      <section id="pair-card" aria-label="Active candidate pair">
        <h2 id="pair-id-heading" style="margin:0 0 4px 0;"></h2>
        <div id="pair-query-meta" class="meta-line"></div>
        <div id="pair-query-text" class="query-callout"></div>
        <div id="pair-doc-meta" class="meta-line"></div>

        <div class="field-group">
          <label for="passage-text-box">Canonical Passage Text (Read-Only)</label>
          <div id="passage-text-box" class="passage-box" tabindex="0"></div>
        </div>

        <div id="pair-errors" class="status-banner status-error" hidden></div>

        <fieldset class="field-group" style="border:1px solid var(--border);border-radius:6px;padding:10px;">
          <legend style="font-weight:600;">Relevance Grade (0, 1, or 2)</legend>
          <div class="radio-row">
            <label><input type="radio" name="relevance_grade" value="0"> 0 — Irrelevant / Distractor</label>
            <label><input type="radio" name="relevance_grade" value="1"> 1 — Partially Relevant / Background</label>
            <label><input type="radio" name="relevance_grade" value="2"> 2 — Highly Relevant / Grounding Evidence</label>
          </div>
        </fieldset>

        <div class="field-group">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <label for="quote-input">Supporting Verbatim Quotation (exact substring for 1/2; blank for 0)</label>
            <button id="btn-use-selection" type="button">Use Highlighted Passage Text</button>
          </div>
          <textarea id="quote-input" rows="3" placeholder="Copy an exact verbatim substring from the passage above for grades 1 or 2. Leave blank for grade 0."></textarea>
          <div id="quote-live-status" class="field-hint"></div>
        </div>

        <div class="prov-grid">
          <div class="field-group">
            <label for="confidence-select">Confidence</label>
            <select id="confidence-select">
              <option value="">-- Select confidence --</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </div>
          <div class="field-group" style="display:flex;align-items:flex-end;">
            <label style="display:flex;align-items:center;gap:8px;font-weight:600;">
              <input id="flag-checkbox" type="checkbox"> Flag this pair for follow-up review
            </label>
          </div>
        </div>

        <div class="field-group">
          <label for="notes-input">Reviewer Notes (brief 1-sentence human justification)</label>
          <textarea id="notes-input" rows="2" placeholder="Briefly explain why this passage received grade 0, 1, or 2."></textarea>
        </div>

        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <button id="btn-save" type="button">Save Progress (Ctrl+S)</button>
          <button id="btn-save-next" type="button" class="primary">Save &amp; Next</button>
        </div>
      </section>

      <details class="provenance-panel panel" open>
        <summary style="font-weight:700;cursor:pointer;">Human Provenance &amp; Attestation Declaration (Required Before Export)</summary>
        <p class="meta-line">Never auto-populated or auto-signed. Complete and sign truthfully as the human assessor.</p>
        <div class="prov-grid">
          <div class="field-group">
            <label for="prov-reviewer-id">Reviewer Identity or Pseudonym</label>
            <input id="prov-reviewer-id" type="text" placeholder="e.g., HUMAN_ASSESSOR_01">
          </div>
          <div class="field-group">
            <label for="prov-class">Provenance Class</label>
            <select id="prov-class">
              <option value="">-- Select provenance class --</option>
              <option value="INDEPENDENT_HUMAN">INDEPENDENT_HUMAN</option>
              <option value="HUMAN_POST_AI_EXPOSURE">HUMAN_POST_AI_EXPOSURE</option>
              <option value="AI_ASSISTED_OR_GENERATED">AI_ASSISTED_OR_GENERATED</option>
              <option value="ADJUDICATED_HUMAN">ADJUDICATED_HUMAN</option>
            </select>
          </div>
          <div class="field-group">
            <label for="prov-assistance">AI-Assistance / Exposure Disclosure</label>
            <select id="prov-assistance">
              <option value="">-- Select disclosure --</option>
              <option value="NONE_INDEPENDENT_HUMAN">NONE_INDEPENDENT_HUMAN</option>
              <option value="EXPOSED_TO_AI_SUGGESTIONS">EXPOSED_TO_AI_SUGGESTIONS</option>
              <option value="AI_ASSISTED">AI_ASSISTED</option>
            </select>
          </div>
          <div class="field-group">
            <label for="prov-start-utc">Review Start Date (UTC ISO-8601)</label>
            <input id="prov-start-utc" type="text" placeholder="YYYY-MM-DDTHH:MM:SSZ">
          </div>
        </div>
        <div class="field-group">
          <label style="display:flex;align-items:flex-start;gap:8px;font-weight:500;">
            <input id="prov-attestation-check" type="checkbox" style="margin-top:4px;">
            <span id="prov-attestation-text"></span>
          </label>
          <div class="meta-line">Signed timestamp (UTC): <strong id="prov-signed-utc">(not yet signed)</strong></div>
        </div>
        <button id="btn-save-prov" type="button" class="primary">Save &amp; Sign Human Provenance</button>
      </details>
    </main>
  </div>
  <script>{WORKBENCH_JS}</script>
</body>
</html>
"""
