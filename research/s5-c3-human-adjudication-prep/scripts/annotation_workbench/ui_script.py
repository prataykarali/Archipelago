"""Client-side vanilla JavaScript for the offline blinded annotation workbench."""

from __future__ import annotations

WORKBENCH_JS = r"""
(function () {
  "use strict";

  const state = {
    pairs: [],
    filteredPairs: [],
    currentIndex: 0,
    activeQuery: "ALL",
    activeFilter: "all",
    searchText: "",
    summary: null,
    provenance: null,
  };

  const el = (id) => document.getElementById(id);

  async function apiJson(url, options) {
    const resp = await fetch(url, options || {});
    const data = await resp.json();
    if (!resp.ok) {
      const err = new Error(data.error || "Request failed");
      err.payload = data;
      throw err;
    }
    return data;
  }

  function setStatus(message, isError) {
    const banner = el("status-banner");
    banner.textContent = message;
    banner.className = isError ? "status-banner status-error" : "status-banner status-ok";
  }

  function renderProgress() {
    const s = state.summary;
    if (!s) return;
    el("overall-count").textContent =
      s.completed_pairs + " / " + s.total_pairs + " completed";
    el("flagged-count").textContent = "Flagged: " + s.flagged_pairs;
    el("invalid-count").textContent = "Needs fix: " + s.invalid_pairs;
    const pct = s.total_pairs > 0 ? Math.round((s.completed_pairs / s.total_pairs) * 100) : 0;
    const bar = el("overall-progress-bar");
    bar.style.width = pct + "%";
    bar.setAttribute("aria-valuenow", String(pct));

    const provBadge = el("provenance-badge");
    if (s.provenance_valid) {
      provBadge.textContent = "Provenance: Signed";
      provBadge.className = "badge badge-ok";
    } else {
      provBadge.textContent = "Provenance: Unsigned";
      provBadge.className = "badge badge-warn";
    }

    const qList = el("query-list");
    qList.innerHTML = "";

    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = "query-item" + (state.activeQuery === "ALL" ? " active" : "");
    allBtn.textContent = "All Queries (" + s.completed_pairs + "/" + s.total_pairs + ")";
    allBtn.addEventListener("click", () => {
      state.activeQuery = "ALL";
      applyFilter(true);
    });
    qList.appendChild(allBtn);

    for (const q of s.per_query) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "query-item" + (state.activeQuery === q.query_id ? " active" : "");
      const flagSuffix = q.flagged > 0 ? " | *" + q.flagged : "";
      btn.textContent = q.query_id + " (" + q.completed + "/" + q.total + ")" + flagSuffix;
      btn.title = q.domain + ": " + q.query_text;
      btn.addEventListener("click", () => {
        state.activeQuery = q.query_id;
        applyFilter(true);
      });
      qList.appendChild(btn);
    }
  }

  function applyFilter(resetIndex) {
    const qFilter = state.activeQuery;
    const mode = state.activeFilter;
    const needle = state.searchText.trim().toLowerCase();

    state.filteredPairs = state.pairs.filter((item) => {
      if (qFilter !== "ALL" && item.query_id !== qFilter) return false;
      if (mode === "ungraded" && item.validation.complete) return false;
      if (mode === "completed" && !item.validation.complete) return false;
      if (mode === "flagged" && !item.judgment.flagged) return false;
      if (mode === "invalid" && !(item.validation.started && !item.validation.complete)) {
        return false;
      }
      if (needle) {
        const hay = (
          item.pair_id + " " + item.query_id + " " + item.candidate_doc_id
        ).toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });

    if (resetIndex || state.currentIndex >= state.filteredPairs.length) {
      state.currentIndex = 0;
    }
    renderCurrentPair();
    renderProgress();
  }

  function updateLiveQuoteStatus() {
    const item = state.filteredPairs[state.currentIndex];
    const hint = el("quote-live-status");
    if (!item) {
      hint.textContent = "";
      return;
    }
    const gradeVal = getSelectedGrade();
    const quote = el("quote-input").value;
    if (gradeVal === 0) {
      if (quote.trim() === "") {
        hint.textContent = "Grade 0: quote is blank (valid).";
        hint.className = "field-hint hint-ok";
      } else {
        hint.textContent = "Grade 0 requires supporting quotation to be blank.";
        hint.className = "field-hint hint-err";
      }
      return;
    }
    if (gradeVal === 1 || gradeVal === 2) {
      if (!quote.trim()) {
        hint.textContent = "Grade " + gradeVal + " requires an exact verbatim substring from the passage.";
        hint.className = "field-hint hint-warn";
      } else if (item.passage_text.includes(quote)) {
        hint.textContent = "Exact verbatim substring match verified.";
        hint.className = "field-hint hint-ok";
      } else {
        hint.textContent = "Quote does NOT exactly match any substring in the canonical passage.";
        hint.className = "field-hint hint-err";
      }
      return;
    }
    hint.textContent = "Select a relevance grade (0, 1, or 2).";
    hint.className = "field-hint";
  }

  function getSelectedGrade() {
    const checked = document.querySelector('input[name="relevance_grade"]:checked');
    if (!checked) return null;
    return Number(checked.value);
  }

  function setSelectedGrade(val) {
    document.querySelectorAll('input[name="relevance_grade"]').forEach((inp) => {
      inp.checked = val !== null && Number(inp.value) === Number(val);
    });
  }

  function renderCurrentPair() {
    const total = state.filteredPairs.length;
    el("nav-position").textContent = total > 0 ? (state.currentIndex + 1) + " / " + total : "0 / 0";
    el("btn-prev").disabled = state.currentIndex <= 0;
    el("btn-next").disabled = state.currentIndex >= total - 1;

    if (total === 0) {
      el("pair-card").hidden = true;
      el("empty-state").hidden = false;
      return;
    }
    el("pair-card").hidden = false;
    el("empty-state").hidden = true;

    const item = state.filteredPairs[state.currentIndex];
    el("pair-id-heading").textContent = item.pair_id + " (Pool #" + item.pair_index + ")";
    el("pair-query-meta").textContent = item.query_id + " | " + item.domain;
    el("pair-query-text").textContent = item.query_text;
    el("pair-doc-meta").textContent =
      "Document: " + item.candidate_doc_id +
      " | Chunk: " + item.candidate_chunk_id +
      " | Page: " + item.candidate_page_number +
      " | SHA-256: " + item.passage_sha256.slice(0, 16) + "...";
    el("passage-text-box").textContent = item.passage_text;

    setSelectedGrade(item.judgment.relevance_grade);
    el("quote-input").value = item.judgment.supporting_quotation || "";
    el("confidence-select").value = item.judgment.confidence || "";
    el("notes-input").value = item.judgment.reviewer_notes || "";
    el("flag-checkbox").checked = Boolean(item.judgment.flagged);

    const errBox = el("pair-errors");
    if (item.validation.started && !item.validation.complete && item.validation.errors.length > 0) {
      errBox.textContent = "Validation: " + item.validation.errors.join(" ");
      errBox.hidden = false;
    } else {
      errBox.textContent = "";
      errBox.hidden = true;
    }
    updateLiveQuoteStatus();
  }

  async function saveCurrentPair(advanceAfter) {
    const item = state.filteredPairs[state.currentIndex];
    if (!item) return;

    const grade = getSelectedGrade();
    const payload = {
      relevance_grade: grade,
      supporting_quotation: grade === 0 ? "" : el("quote-input").value,
      confidence: el("confidence-select").value,
      reviewer_notes: el("notes-input").value,
      flagged: el("flag-checkbox").checked,
    };

    try {
      const data = await apiJson("/api/pairs/" + encodeURIComponent(item.pair_id), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const idx = state.pairs.findIndex((p) => p.pair_id === item.pair_id);
      if (idx >= 0) {
        state.pairs[idx].judgment = data.judgment;
        state.pairs[idx].validation = data.validation;
      }
      state.summary = data.summary;
      setStatus(
        "Saved " + item.pair_id + " (session SHA-256: " + data.save.session_sha256.slice(0, 12) + "...)",
        false
      );
      if (advanceAfter && state.currentIndex < state.filteredPairs.length - 1) {
        state.currentIndex += 1;
      }
      applyFilter(false);
    } catch (err) {
      setStatus("Save failed: " + err.message, true);
    }
  }

  function populateProvenanceForm() {
    const p = state.provenance;
    if (!p) return;
    el("prov-reviewer-id").value = p.reviewer_identity_or_pseudonym || "";
    el("prov-class").value = p.provenance_class || "";
    el("prov-assistance").value = p.assistance_declaration || "";
    el("prov-attestation-text").textContent = p.attestation_statement || "";
    el("prov-attestation-check").checked = Boolean(p.human_attestation_confirmed);
    el("prov-start-utc").value = p.review_start_date_utc || "";
    el("prov-signed-utc").textContent = p.signed_by_human_at_utc || "(not yet signed)";
  }

  async function saveProvenance() {
    const payload = {
      reviewer_identity_or_pseudonym: el("prov-reviewer-id").value.trim(),
      provenance_class: el("prov-class").value,
      assistance_declaration: el("prov-assistance").value,
      human_attestation_confirmed: el("prov-attestation-check").checked,
      review_start_date_utc: el("prov-start-utc").value.trim(),
    };
    try {
      const data = await apiJson("/api/provenance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      state.provenance = data.provenance;
      state.summary = data.summary;
      populateProvenanceForm();
      renderProgress();
      if (data.provenance_errors.length > 0) {
        setStatus("Provenance saved with issues: " + data.provenance_errors.join(" "), true);
      } else {
        setStatus("Human provenance declaration signed and saved.", false);
      }
    } catch (err) {
      setStatus("Provenance save failed: " + err.message, true);
    }
  }

  async function createBackup() {
    try {
      const data = await apiJson("/api/backup", { method: "POST" });
      setStatus(
        "Backup created: " + data.backup_path + " (SHA-256: " + data.backup_sha256.slice(0, 12) + "...)",
        false
      );
    } catch (err) {
      setStatus("Backup failed: " + err.message, true);
    }
  }

  async function runExport() {
    try {
      const data = await apiJson("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allow_partial: false }),
      });
      setStatus(
        "Exported JSON & CSV to " + data.json_path + " (SHA-256: " + data.json_sha256.slice(0, 12) + "...)",
        false
      );
    } catch (err) {
      setStatus("Export blocked: " + err.message, true);
    }
  }

  function bindEvents() {
    el("filter-select").addEventListener("change", (ev) => {
      state.activeFilter = ev.target.value;
      applyFilter(true);
    });
    el("search-input").addEventListener("input", (ev) => {
      state.searchText = ev.target.value;
      applyFilter(true);
    });
    el("btn-prev").addEventListener("click", () => {
      if (state.currentIndex > 0) {
        state.currentIndex -= 1;
        renderCurrentPair();
      }
    });
    el("btn-next").addEventListener("click", () => {
      if (state.currentIndex < state.filteredPairs.length - 1) {
        state.currentIndex += 1;
        renderCurrentPair();
      }
    });
    el("btn-jump").addEventListener("click", () => {
      const raw = Number(el("jump-index").value);
      if (Number.isInteger(raw) && raw >= 1 && raw <= state.filteredPairs.length) {
        state.currentIndex = raw - 1;
        renderCurrentPair();
      }
    });
    el("btn-use-selection").addEventListener("click", () => {
      const sel = window.getSelection ? window.getSelection().toString() : "";
      if (!sel) {
        setStatus("Highlight text inside the canonical passage box first.", true);
        return;
      }
      el("quote-input").value = sel;
      updateLiveQuoteStatus();
    });
    document.querySelectorAll('input[name="relevance_grade"]').forEach((inp) => {
      inp.addEventListener("change", () => {
        if (Number(inp.value) === 0) {
          el("quote-input").value = "";
        }
        updateLiveQuoteStatus();
      });
    });
    el("quote-input").addEventListener("input", updateLiveQuoteStatus);
    el("btn-save").addEventListener("click", () => saveCurrentPair(false));
    el("btn-save-next").addEventListener("click", () => saveCurrentPair(true));
    el("btn-save-prov").addEventListener("click", saveProvenance);
    el("btn-backup").addEventListener("click", createBackup);
    el("btn-export").addEventListener("click", runExport);

    document.addEventListener("keydown", (ev) => {
      if (ev.ctrlKey && ev.key.toLowerCase() === "s") {
        ev.preventDefault();
        saveCurrentPair(false);
      } else if (ev.altKey && ev.key === "ArrowRight") {
        ev.preventDefault();
        el("btn-next").click();
      } else if (ev.altKey && ev.key === "ArrowLeft") {
        ev.preventDefault();
        el("btn-prev").click();
      }
    });
  }

  async function init() {
    bindEvents();
    try {
      const data = await apiJson("/api/pairs");
      state.pairs = data.pairs;
      state.summary = data.summary;
      state.provenance = data.provenance;
      populateProvenanceForm();
      applyFilter(true);
      setStatus("Loaded " + state.pairs.length + " blinded pairs (local-only mode).", false);
    } catch (err) {
      setStatus("Failed to load blinded pool: " + err.message, true);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
"""
