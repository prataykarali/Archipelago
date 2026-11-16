"use strict";

const RANKING_NAMES = ["Papers", "Authors", "Publications"];

function rankingText(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return String(value);
}

function rankingCompare(left, right, column, direction) {
  const a = left.values[column];
  const b = right.values[column];
  const aMissing = a === null || a === undefined || a === "";
  const bMissing = b === null || b === undefined || b === "";
  if (aMissing !== bMissing) return aMissing ? 1 : -1;
  if (aMissing) return 0;
  if (typeof a === "number" && typeof b === "number") return (a - b) * direction;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" }) * direction;
}

function renderRankingPreview(root, preview) {
  if (!root || !preview?.sheets) return;
  let active = "Papers";
  let sortColumn = -1;
  let direction = -1;
  let query = "";
  root.replaceChildren();

  const tabs = document.createElement("div");
  tabs.className = "ranking-tabs";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Ranking sheet");
  const search = document.createElement("input");
  search.type = "search";
  search.className = "ranking-search";
  search.placeholder = "Find a paper, author or venue";
  search.setAttribute("aria-label", "Filter ranking rows");
  const meta = document.createElement("p");
  meta.className = "ranking-meta";
  const scroll = document.createElement("div");
  scroll.className = "ranking-scroll";
  scroll.tabIndex = 0;
  scroll.setAttribute("aria-label", "Scrollable ranking table");
  const table = document.createElement("table");
  table.className = "ranking-table";
  scroll.append(table);
  root.append(tabs, search, meta, scroll);

  function draw() {
    tabs.replaceChildren();
    for (const name of RANKING_NAMES) {
      const sheet = preview.sheets[name];
      const button = document.createElement("button");
      button.type = "button";
      button.className = name === active ? "active" : "";
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", String(name === active));
      button.textContent = `${name}  ${sheet?.rows.length || 0}`;
      button.addEventListener("click", () => {
        active = name;
        sortColumn = -1;
        direction = -1;
        draw();
      });
      tabs.append(button);
    }
    const sheet = preview.sheets[active];
    if (!sheet) { meta.textContent = "This sheet is unavailable."; table.replaceChildren(); return; }
    const matches = sheet.rows.filter(row => !query || row.values.some(value => rankingText(value).toLocaleLowerCase().includes(query)));
    if (sortColumn >= 0) matches.sort((a, b) => rankingCompare(a, b, sortColumn, direction));
    meta.textContent = `${matches.length} of ${sheet.rows.length} ${active.toLowerCase()} · ${sheet.headers.length} columns · click a heading to sort · scroll sideways for all parameters`;
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    sheet.headers.forEach((header, index) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.setAttribute("aria-sort", sortColumn === index ? (direction === 1 ? "ascending" : "descending") : "none");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${header}${sortColumn === index ? direction === 1 ? " ↑" : " ↓" : " ↕"}`;
      button.addEventListener("click", () => {
        direction = sortColumn === index ? -direction : (typeof sheet.rows.find(row => row.values[index] != null)?.values[index] === "number" ? -1 : 1);
        sortColumn = index;
        draw();
      });
      th.append(button);
      headRow.append(th);
    });
    head.append(headRow);
    const body = document.createElement("tbody");
    for (const row of matches) {
      const tr = document.createElement("tr");
      sheet.headers.forEach((_, index) => {
        const td = document.createElement("td");
        const value = rankingText(row.values[index]);
        const link = row.links?.[String(index)];
        if (link && link.startsWith("https://")) {
          const anchor = document.createElement("a");
          anchor.href = link;
          anchor.target = "_blank";
          anchor.rel = "noopener noreferrer";
          anchor.textContent = value || "Open source ↗";
          td.append(anchor);
        } else {
          td.textContent = value || "—";
          if (!value) td.classList.add("empty");
        }
        tr.append(td);
      });
      body.append(tr);
    }
    table.replaceChildren(head, body);
  }
  search.addEventListener("input", () => { query = search.value.trim().toLocaleLowerCase(); draw(); });
  draw();
}

window.renderRankingPreview = renderRankingPreview;

window.addEventListener("load", async () => {
  const sample = document.getElementById("sample-ranking-preview");
  if (!sample) return;
  try {
    const response = await fetch("/research/example/rankings.json");
    if (!response.ok) throw new Error(`Example unavailable (${response.status})`);
    const preview = await response.json();
    renderRankingPreview(sample, preview);
    document.getElementById("sample-retrieved").textContent = `${preview.topic} · retrieved ${preview.retrieved_at.slice(0, 10)} · sample data from public providers`;
  } catch (error) { sample.textContent = error.message; }
});
