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
      if (name === "opac_url" && row[name]) {
        const link = document.createElement("a");
        link.href = row[name];
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "text-violet-200 underline";
        link.textContent = "Open OPAC record";
        cell.append(link);
      } else {
        cell.textContent = row[name] || "—";
      }
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
    const daily = snapshot.opac_daily;
    const dailyStatus = document.querySelector("#daily-opac-status");
    const sectionRoot = document.querySelector("#daily-opac-sections");
    const arrivalRoot = document.querySelector("#daily-opac-arrivals");
    sectionRoot.replaceChildren();
    arrivalRoot.replaceChildren();
    if (daily && Array.isArray(daily.sections)) {
      dailyStatus.textContent = `Public OPAC pages checked ${new Date(daily.checked_at).toLocaleString()}. First arrivals results page only.`;
      for (const section of daily.sections) {
        const card = document.createElement("article");
        card.className = "rounded-xl border border-white/15 bg-[#100a2c] p-4";
        const heading = document.createElement("h4");
        heading.className = "font-semibold text-white";
        heading.textContent = section.title;
        const summary = document.createElement("p");
        summary.className = "mt-2 text-xs leading-5 text-white/70";
        summary.textContent = section.summary;
        card.append(heading, summary);
        const source = document.createElement("a");
        source.href = section.source_url;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        source.className = "mt-2 inline-block text-xs text-violet-200 underline";
        source.textContent = "Open OPAC section";
        card.append(source);
        sectionRoot.append(card);
      }
      for (const arrival of daily.new_arrivals || []) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = arrival.source_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "text-violet-200 underline";
        link.textContent = arrival.title;
        item.append(link);
        arrivalRoot.append(item);
      }
    } else {
      dailyStatus.textContent = "No daily OPAC check has been published yet.";
    }
    const updated = new Date(snapshot.source_updated_at).toLocaleString();
    status.textContent = snapshot.stale
      ? `Last export: ${updated}. This snapshot is stale; a new authorized Koha export is needed.`
      : `Last export: ${updated}. Updated automatically when the local export folder changes.`;
    const identity = snapshot.catalog_identity_status;
    if (identity) {
      status.textContent += ` Identifier coverage: ${identity.covered_holdings}/${identity.total_holdings} exported holdings. This is a keyword-filtered inventory, not the full campus catalogue.`;
    }
    const repository = document.querySelector("#repository-candidates");
    repository.replaceChildren();
    const candidates = Array.isArray(snapshot.repository_candidates) ? snapshot.repository_candidates : [];
    if (!candidates.length) {
      const item = document.createElement("li");
      item.textContent = "No repository updates are available yet.";
      repository.append(item);
    }
    for (const candidate of candidates) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = candidate.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "text-violet-200 underline";
      link.textContent = candidate.title;
      item.append(link);
      repository.append(item);
    }
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
