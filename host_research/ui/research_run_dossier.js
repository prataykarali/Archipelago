"use strict";

const dossierEl = id => document.getElementById(id);
const DOSSIER_SECTIONS = [
  ["methods", "Methods"], ["datasets", "Datasets and benchmarks"],
  ["evaluation_metrics", "Evaluation metrics"], ["claims", "Extracted claims"]
];
const ABSTRACT_PREVIEW_CHARS = 280;
const RANKING_SUMMARY_HEADERS = ["Citation Count", "Citations per Year", "Topic Relevance Score", "Field-Weighted Citation Impact (FWCI)", "Reference Count"];
const RANKING_IDENTITY_HEADERS = new Set(["Paper", "Paper Title", "Title", "Authors", "Publication Year", "Year", "Venue Name", "Venue", "Paper link", "DOI"]);

function reportedRankingValue(value) {
  return value !== null && value !== undefined && value !== "" &&
    !(typeof value === "string" && value.startsWith("=HYPERLINK("));
}

function rankingRows(dossier, paper) {
  return dossier.paper_headers.map((header, index) => [header, paper.rankable_values[index]])
    .filter(([header]) => !RANKING_IDENTITY_HEADERS.has(header));
}

function rankingGrid(rows) {
  const grid = document.createElement("dl"); grid.className = "run-metric-grid";
  rows.forEach(([header, raw]) => {
    const item = document.createElement("div");
    if (!reportedRankingValue(raw)) item.className = "run-metric-missing";
    const term = document.createElement("dt"); term.textContent = header;
    const description = document.createElement("dd");
    description.textContent = reportedRankingValue(raw) ? dossierText(raw) : "Not reported";
    item.append(term, description); grid.append(item);
  });
  return grid;
}

function dossierLink(label, href, className = "") {
  const a = document.createElement("a");
  a.textContent = label;
  a.href = href;
  a.className = className;
  if (href.startsWith("https://")) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
  return a;
}

function dossierText(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  return String(value);
}

function dossierCard(title, id, wide = false) {
  const card = document.createElement("section");
  card.className = `run-extract-card${wide ? " run-wide" : ""}`;
  card.id = id;
  const h = document.createElement("h2"); h.textContent = title;
  card.append(h);
  return card;
}

function addDossierStat(root, label, value, icon) {
  if (value === null || value === undefined || value === "") return;
  const tile = document.createElement("div"); tile.className = "paper-stat";
  const symbol = document.createElement("span"); symbol.className = "paper-stat-icon"; symbol.textContent = icon;
  const body = document.createElement("div");
  const name = document.createElement("small"); name.textContent = label;
  const count = document.createElement("strong"); count.textContent = dossierText(value);
  body.append(name, count); tile.append(symbol, body); root.append(tile);
}

function addDossierBar(root, label, count, maximum) {
  const row = document.createElement("div"); row.className = "topic-bar-row";
  const text = document.createElement("span"); text.textContent = label;
  const track = document.createElement("div"); track.className = "topic-bar-track";
  const fill = document.createElement("i"); fill.style.width = `${Math.round(count / Math.max(maximum, 1) * 100)}%`;
  track.append(fill);
  const number = document.createElement("strong"); number.textContent = String(count);
  row.append(text, track, number); root.append(row);
}

function addExtractionCard(dashboard, field, label, facts) {
  const card = dossierCard(`${label} · ${facts.length}`, `run-${field}`);
  if (!facts.length) {
    const empty = document.createElement("p"); empty.className = "run-empty";
    empty.textContent = `No named ${label.toLowerCase()} were verified in the source title or abstract.`;
    card.append(empty);
  } else {
    const list = document.createElement("ul");
    for (const fact of facts) {
      const item = document.createElement("li");
      const name = document.createElement("strong"); name.textContent = fact.name;
      item.append(name);
      if (fact.evidence) {
        const quote = document.createElement("blockquote");
        quote.textContent = `“${fact.evidence}”`;
        item.append(quote);
      }
      list.append(item);
    }
    card.append(list);
  }
  dashboard.append(card);
}

function renderRunPaper(dossier, paper, context) {
  const query = context.run ? `run=${encodeURIComponent(context.run)}` : "example=state-space-models";
  document.querySelector(".paper-cover span").textContent = "PAPER";
  dossierEl("paper-topic-link").textContent = dossier.topic;
  dossierEl("paper-topic-link").href = `/research/topic?${query}`;
  dossierEl("paper-title").textContent = paper.title;
  dossierEl("paper-authors").textContent = paper.authors.join(" · ");
  dossierEl("paper-venue").textContent = [paper.venue, paper.year].filter(Boolean).join(" · ");
  dossierEl("paper-subtitle").textContent = `Retrieved ${dossier.retrieved_at.slice(0, 10)} · ${paper.abstract ? "source title and abstract" : "source title only"} · ${paper.sources.length} source records`;
  const tags = dossierEl("paper-tags");
  for (const fact of paper.extracted.methods.slice(0, 4)) {
    const tag = document.createElement("span"); tag.textContent = fact.name; tags.append(tag);
  }
  const actions = dossierEl("paper-actions");
  if (paper.url) actions.append(dossierLink("Open provider record ↗", paper.url));
  if (/^10\.\d{4,9}\/\S+$/i.test(paper.doi)) actions.append(dossierLink("Open DOI ↗", `https://doi.org/${encodeURIComponent(paper.doi)}`));
  actions.append(dossierLink("Topic extraction ↗", `/research/topic?${query}`));
  const value = header => paper.rankable_values[dossier.paper_headers.indexOf(header)];
  const stats = dossierEl("paper-stat-strip");
  addDossierStat(stats, "Citations", value("Citation Count"), "❞");
  addDossierStat(stats, "Citations / year", value("Citations per Year"), "◷");
  addDossierStat(stats, "Relevance", value("Topic Relevance Score"), "◎");
  addDossierStat(stats, "FWCI · OpenAlex", value("Field-Weighted Citation Impact (FWCI)"), "▥");
  addDossierStat(stats, "References", value("Reference Count"), "▤");
  const tabs = dossierEl("paper-tabs");
  const dashboard = dossierEl("paper-dashboard");
  const abstract = dossierCard("Abstract", "run-abstract", true);
  const abstractText = document.createElement("p");
  abstractText.textContent = paper.abstract || "No abstract was supplied by the selected providers.";
  abstract.append(abstractText); dashboard.append(abstract);
  tabs.append(dossierLink("Abstract", "#run-abstract"));
  for (const [field, label] of DOSSIER_SECTIONS) {
    addExtractionCard(dashboard, field, label, paper.extracted[field]);
    tabs.append(dossierLink(label, `#run-${field}`));
  }
  const metrics = dossierCard("Ranking parameters and coverage", "run-rankings", true);
  const rows = rankingRows(dossier, paper);
  const coverage = document.createElement("p");
  coverage.className = "run-ranking-coverage";
  coverage.textContent = `${rows.filter(([, value]) => reportedRankingValue(value)).length} of ${rows.length} ranking parameters filled. Search-scoped counts use these retrieved papers only. Evidence flags show whether the retrieved record reports the item; provider metrics remain blank when unreported.`;
  metrics.append(coverage);
  metrics.append(rankingGrid(rows)); dashboard.append(metrics);
  tabs.append(dossierLink("Ranking parameters", "#run-rankings"));
  const sources = dossierCard(`Source records · ${paper.sources.length}`, "run-sources", true);
  const sourceList = document.createElement("ul");
  for (const source of paper.sources) {
    const item = document.createElement("li"); item.append(dossierLink(`${source.name} ↗`, source.url)); sourceList.append(item);
  }
  sources.append(sourceList); dashboard.append(sources);
  tabs.append(dossierLink("Sources", "#run-sources"));
  const audit = document.querySelector(".paper-audit");
  if (audit) audit.remove();
}

function renderRunTopic(dossier, context) {
  const query = context.run ? `run=${encodeURIComponent(context.run)}` : "example=state-space-models";
  dossierEl("topic-title").textContent = dossier.topic;
  dossierEl("topic-breadcrumb").textContent = dossier.topic;
  dossierEl("topic-status").textContent = `${dossier.paper_count} source-linked papers · retrieved ${dossier.retrieved_at.slice(0, 10)} · ${dossier.papers.filter(paper => paper.abstract).length} with provider abstracts`;
  const actions = dossierEl("topic-actions");
  const xlsx = context.run ? `/api/research/intelligence/runs/${encodeURIComponent(context.run)}/xlsx?mode=standard` : "/research/example/Archipelago_State_Space_Models_Rankable.xlsx";
  const excelLink = dossierLink("Download Excel ↗", xlsx, "topic-action");
  actions.append(excelLink, dossierLink("Ranking tables ↗", context.run ? `/research/papers?run=${encodeURIComponent(context.run)}` : "/research/rankings", "topic-action secondary"));
  if (context.run) void prepareResearchExcelLink(excelLink, xlsx, `archipelago-research-${context.run.slice(0, 8)}-standard.xlsx`, dossierEl("topic-status"));
  const stats = dossierEl("topic-stats");
  for (const [label, count, icon] of [["Papers", dossier.paper_count, "▤"], ["Authors", dossier.author_count, "♙"], ["Source providers", Object.keys(dossier.providers).length, "✦"]]) {
    const tile = document.createElement("div"); tile.className = "topic-stat";
    const symbol = document.createElement("span"); symbol.textContent = icon;
    const copy = document.createElement("div");
    const name = document.createElement("small"); name.textContent = label;
    const value = document.createElement("strong"); value.textContent = String(count);
    copy.append(name, value); tile.append(symbol, copy); stats.append(tile);
  }
  const coverage = dossierEl("topic-coverage");
  const counts = DOSSIER_SECTIONS.map(([field, label]) => [label, dossier.papers.filter(p => p.extracted[field].length).length]);
  const maxCoverage = Math.max(1, ...counts.map(([, count]) => count));
  counts.forEach(([label, count]) => addDossierBar(coverage, label, count, maxCoverage));
  const yearCounts = Object.entries(dossier.years); const yearMax = Math.max(1, ...yearCounts.map(([, count]) => count));
  yearCounts.forEach(([label, count]) => addDossierBar(dossierEl("topic-years"), label, count, yearMax));
  const providers = Object.entries(dossier.providers); const providerMax = Math.max(1, ...providers.map(([, count]) => count));
  providers.forEach(([label, count]) => addDossierBar(dossierEl("topic-providers"), label, count, providerMax));
  document.querySelector(".topic-extraction-panel").hidden = false;
  const extracted = dossierEl("topic-extracted");
  for (const [field, label] of DOSSIER_SECTIONS) {
    const group = document.createElement("section"); group.className = "topic-extract-group";
    const title = document.createElement("h3"); title.textContent = label;
    const list = document.createElement("ul");
    const entries = Object.entries(dossier.extracted_counts[field]);
    if (!entries.length) { const empty = document.createElement("li"); empty.textContent = "No verified names"; list.append(empty); }
    for (const [name, count] of entries) {
      const item = document.createElement("li");
      const term = document.createElement("span"); term.textContent = name;
      const value = document.createElement("strong"); value.textContent = String(count);
      item.append(term, value); list.append(item);
    }
    group.append(title, list); extracted.append(group);
  }
  dossierEl("topic-paper-count").textContent = `${dossier.paper_count} papers`;
  const list = dossierEl("topic-paper-list");
  for (const paper of dossier.papers) {
    const card = document.createElement("article"); card.className = "topic-paper-card";
    const title = dossierLink(paper.title, `/research/paper?${query}&paper=${paper.index}`, "topic-paper-title");
    const authors = document.createElement("p"); authors.className = "topic-paper-authors";
    authors.textContent = [paper.authors.join(", "), paper.year, paper.venue].filter(Boolean).join(" · ");
    const abstract = document.createElement("p"); abstract.className = "topic-paper-abstract";
    abstract.textContent = paper.abstract ? `${paper.abstract.slice(0, ABSTRACT_PREVIEW_CHARS)}${paper.abstract.length > ABSTRACT_PREVIEW_CHARS ? "…" : ""}` : "Source metadata only.";
    const badges = document.createElement("div"); badges.className = "topic-paper-badges";
    const rankings = rankingRows(dossier, paper);
    const coverage = document.createElement("span");
    coverage.textContent = `${rankings.filter(([, value]) => reportedRankingValue(value)).length}/${rankings.length} ranking fields reported`;
    badges.append(coverage);
    for (const header of RANKING_SUMMARY_HEADERS) {
      const value = paper.rankable_values[dossier.paper_headers.indexOf(header)];
      if (!reportedRankingValue(value)) continue;
      const badge = document.createElement("span"); badge.textContent = `${header}: ${dossierText(value)}`; badges.append(badge);
    }
    for (const [field, label] of DOSSIER_SECTIONS) {
      if (!paper.extracted[field].length) continue;
      const badge = document.createElement("span"); badge.textContent = `${paper.extracted[field].length} ${label.toLowerCase()}`; badges.append(badge);
    }
    const allRankings = document.createElement("details");
    allRankings.className = "topic-ranking-details";
    const rankingSummary = document.createElement("summary");
    rankingSummary.textContent = "All ranking parameters and missing values";
    allRankings.append(rankingSummary, rankingGrid(rankings));
    card.append(title, authors, abstract, badges, allRankings); list.append(card);
  }
}

window.addEventListener("load", async () => {
  const params = new URLSearchParams(location.search);
  const run = params.get("run");
  const example = params.get("example");
  const paperPage = document.body.dataset.researchPage === "paper";
  const status = dossierEl(paperPage ? "paper-subtitle" : "topic-status");
  const loadProgress = dossierEl(paperPage ? "paper-load-progress" : "topic-load-progress");
  if (!run && !example) {
    if (params.has(paperPage ? "key" : "name")) return;
    status.textContent = "Choose a research run from the search page.";
    if (loadProgress) loadProgress.hidden = true;
    return;
  }
  try {
    if (!await window.archipelagoResearchReady) throw new Error("Sign in to view this research dossier.");
    if (example && example !== "state-space-models") throw new Error("Unknown example.");
    if (run && !/^[a-f0-9-]{36}$/i.test(run)) throw new Error("Invalid research run.");
    const url = run ? `/api/research/intelligence/runs/${encodeURIComponent(run)}/dossier` : "/research/example/dossiers.json";
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Research dossier unavailable (${response.status}).`);
    const dossier = await response.json();
    if (paperPage) {
      const paperParam = params.get("paper");
      const index = paperParam === null ? NaN : Number(paperParam);
      if (!Number.isInteger(index) || index < 0 || index >= dossier.papers.length) throw new Error("Choose a paper from the ranking table.");
      renderRunPaper(dossier, dossier.papers[index], { run, example });
    } else renderRunTopic(dossier, { run, example });
  } catch (error) { status.textContent = error.message; }
  finally { if (loadProgress) loadProgress.hidden = true; }
});
