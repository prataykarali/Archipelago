const kinds = {
  holdings: "Holdings",
  journal_issues: "Journal issues",
  subject_counts: "Subject counts",
  subject_titles: "Subject titles",
};
let snapshot = null;

function renderKoha() {
  if (!snapshot) return;
  const kind = document.querySelector("#koha-kind").value;
  const query = document.querySelector("#koha-search").value.trim().toLowerCase();
  const all = Array.isArray(snapshot[kind]) ? snapshot[kind] : [];
  const matches = query ? all.filter(row => Object.values(row).some(value => String(value).toLowerCase().includes(query))) : all;
  document.querySelector("#koha-results").textContent = `${matches.length} of ${all.length} ${kinds[kind].toLowerCase()} shown`;
  const headers = Object.keys(all[0] || {});
  const thead = document.querySelector("#koha-head");
  const tbody = document.querySelector("#koha-body");
  thead.replaceChildren();
  tbody.replaceChildren();
  const headRow = document.createElement("tr");
  for (const name of headers) {
    const cell = document.createElement("th");
    cell.className = "p-3";
    cell.textContent = name;
    headRow.append(cell);
  }
  thead.append(headRow);
  for (const row of matches.slice(0, 250)) {
    const tr = document.createElement("tr");
    for (const name of headers) {
      const cell = document.createElement("td");
      cell.className = "p-3 text-white/75";
      cell.textContent = row[name] || "—";
      tr.append(cell);
    }
    tbody.append(tr);
  }
  if (matches.length > 250) document.querySelector("#koha-results").textContent += " · first 250 rows displayed";
}

async function loadKoha() {
  const status = document.querySelector("#koha-status");
  try {
    const response = await fetch("/api/library/koha", { cache: "no-store" });
    if (response.status === 404) {
      status.textContent = "No authorized Koha export has been published yet.";
      return;
    }
    if (!response.ok) throw new Error(`Metadata service returned ${response.status}.`);
    snapshot = await response.json();
    const updated = new Date(snapshot.source_updated_at).toLocaleString();
    status.textContent = snapshot.stale
      ? `Last export: ${updated}. This snapshot is stale; a new authorized Koha export is needed.`
      : `Last export: ${updated}. Updated automatically when the local export folder changes.`;
    const counts = document.querySelector("#koha-counts");
    counts.replaceChildren();
    for (const [key, label] of Object.entries(kinds)) {
      const card = document.createElement("div");
      card.className = "rounded-xl border border-violet-300/20 bg-violet-500/10 p-4";
      const count = document.createElement("strong");
      count.className = "block text-2xl text-white";
      count.textContent = String(snapshot.exports?.[key]?.count || 0);
      const description = document.createElement("span");
      description.className = "text-xs text-violet-200";
      description.textContent = label;
      card.append(count, description);
      counts.append(card);
    }
    renderKoha();
  } catch (error) {
    status.textContent = `Could not load Koha metadata: ${error.message}`;
  }
}

document.querySelector("#koha-kind").addEventListener("change", renderKoha);
document.querySelector("#koha-search").addEventListener("input", renderKoha);
window.addEventListener("load", loadKoha);
