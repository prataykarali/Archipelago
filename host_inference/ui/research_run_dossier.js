"use strict";

const dossierEl = id => document.getElementById(id);
const DOSSIER_SECTIONS = [
  ["methods", "Methods"], ["datasets", "Datasets and benchmarks"],
  ["evaluation_metrics", "Evaluation metrics"], ["claims", "Extracted claims"]
];
const RANKING_IDENTITY_HEADERS = new Set(["Paper", "Paper Title", "Title", "Authors", "Publication Year", "Year", "Venue Name", "Venue", "Paper Link", "DOI", "Verified Sources"]);

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
  addDossierStat(stats, "Discovery fit", value("Discovery Fit Score (%)"), "◎");
  addDossierStat(stats, "Rank in search", value("Discovery Rank"), "▤");
  addDossierStat(stats, "Title match", value("Title Query Match (%)"), "◷");
  addDossierStat(stats, "Source records", value("Verified Source Count"), "✦");
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
  coverage.textContent = `${rows.length} complete discovery parameters. Fit = 50% title match + 25% abstract match + 15% recency + 10% source corroboration, normalized within this saved search. This ranks discovery fit, not scientific quality. Abstract match is zero when no abstract was supplied.`;
  metrics.append(coverage);
  metrics.append(rankingGrid(rows)); dashboard.append(metrics);
  tabs.append(dossierLink("Ranking parameters", "#run-rankings"));
  const reported = Object.entries(paper.provider_metrics || {});
  if (reported.length) {
    const provider = dossierCard("Additional provider facts", "run-provider-facts", true);
    const note = document.createElement("p");
    note.textContent = "These values are reported by connected sources. Coverage differs by provider and they do not enter the complete discovery fit score.";
    provider.append(note, rankingGrid(reported)); dashboard.append(provider);
    tabs.append(dossierLink("Provider facts", "#run-provider-facts"));
  }
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
  actions.replaceChildren();
  const xlsx = context.run ? `/api/research/intelligence/runs/${encodeURIComponent(context.run)}/xlsx?mode=standard` : "/research/example/Archipelago_State_Space_Models_Rankable.xlsx";
  const excelLink = dossierLink("Download Excel ↗", xlsx, "topic-action");
  const papersUrl = context.run ? `/research/papers?run=${encodeURIComponent(context.run)}` : "/research";
  actions.append(excelLink, dossierLink("Browse papers ↗", papersUrl, "topic-action secondary"));
  if (context.run) actions.append(dossierLink("Ask chat about this topic ↗", `/chat?research_run_id=${encodeURIComponent(context.run)}`, "topic-action secondary"));
  dossierEl("topic-papers-link").href = papersUrl;
  if (context.run) void prepareResearchExcelLink(excelLink, xlsx, `archipelago-research-${context.run.slice(0, 8)}-paper-venue-v2.xlsx`, dossierEl("topic-status"));
  const stats = dossierEl("topic-stats");
  stats.replaceChildren();
  for (const [label, count, icon] of [["Papers", dossier.paper_count, "▤"], ["Authors", dossier.author_count, "♙"], ["Source providers", Object.keys(dossier.providers).length, "✦"]]) {
    const tile = document.createElement("div"); tile.className = "topic-stat";
    const symbol = document.createElement("span"); symbol.textContent = icon;
    const copy = document.createElement("div");
    const name = document.createElement("small"); name.textContent = label;
    const value = document.createElement("strong"); value.textContent = String(count);
    copy.append(name, value); tile.append(symbol, copy); stats.append(tile);
  }
  const abstracts = dossier.papers.filter(paper => paper.abstract).length;
  const latestYear = Object.keys(dossier.years).map(Number).filter(Number.isFinite).sort((a, b) => b - a)[0];
  const topMethod = Object.entries(dossier.extracted_counts.methods || {}).sort((a, b) => b[1] - a[1])[0];
  dossierEl("topic-conclusion").textContent = `${dossier.paper_count} source-linked papers span ${Object.keys(dossier.years).length} publication years${latestYear ? `, most recently ${latestYear}` : ""}. ${abstracts} have provider abstracts. ${topMethod ? `The most frequently evidenced method term is “${topMethod[0]}” (${topMethod[1]} papers).` : "No method term was verified in the available titles or abstracts."} These are coverage observations, not a judgment of scientific quality.`;
  const coverage = dossierEl("topic-coverage");
  coverage.replaceChildren();
  const counts = DOSSIER_SECTIONS.map(([field, label]) => [label, dossier.papers.filter(p => p.extracted[field].length).length]);
  const maxCoverage = Math.max(1, ...counts.map(([, count]) => count));
  counts.forEach(([label, count]) => addDossierBar(coverage, label, count, maxCoverage));
  const yearCounts = Object.entries(dossier.years); const yearMax = Math.max(1, ...yearCounts.map(([, count]) => count));
  dossierEl("topic-years").replaceChildren();
  yearCounts.forEach(([label, count]) => addDossierBar(dossierEl("topic-years"), label, count, yearMax));
  const providers = Object.entries(dossier.providers); const providerMax = Math.max(1, ...providers.map(([, count]) => count));
  dossierEl("topic-providers").replaceChildren();
  providers.forEach(([label, count]) => addDossierBar(dossierEl("topic-providers"), label, count, providerMax));
  document.querySelector(".topic-extraction-panel").hidden = false;
  const extracted = dossierEl("topic-extracted");
  extracted.replaceChildren();
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
}

function renderSavedTopicPreview(savedRun, runId) {
  const papers = savedRun.papers || [];
  const topic = savedRun.options?.topic || "Saved topic";
  dossierEl("topic-title").textContent = topic;
  dossierEl("topic-breadcrumb").textContent = topic;
  dossierEl("topic-status").textContent = `${papers.length} saved papers. Loading detailed topic metrics…`;
  dossierEl("topic-conclusion").textContent = `${papers.length} source-linked papers saved for this topic. Detailed coverage and publication-year totals are loading.`;
  const papersUrl = `/research/papers?run=${encodeURIComponent(runId)}`;
  dossierEl("topic-actions").append(dossierLink(`Browse ${papers.length} papers ↗`, papersUrl, "topic-action"), dossierLink("Ask chat about this topic ↗", `/chat?research_run_id=${encodeURIComponent(runId)}`, "topic-action secondary"));
  dossierEl("topic-papers-link").href = papersUrl;
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
    if (run && !paperPage) {
      try {
        const savedResponse = await fetch(`/api/research/intelligence/runs/${encodeURIComponent(run)}`, { cache: "no-store" });
        if (savedResponse.ok) renderSavedTopicPreview(await savedResponse.json(), run);
      } catch (_) { /* The dossier request below can still restore this topic. */ }
    }
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Research dossier unavailable (${response.status}).`);
    const dossier = await response.json();
    if (paperPage) {
      const paperParam = params.get("paper");
      const index = paperParam === null ? NaN : Number(paperParam);
      if (!Number.isInteger(index) || index < 0 || index >= dossier.papers.length) throw new Error("Choose a paper from the ranking table.");
      renderRunPaper(dossier, dossier.papers[index], { run, example });
    } else renderRunTopic(dossier, { run, example });
  } catch (error) {
    status.textContent = `Detailed topic metrics could not load (${error.message}). Browse saved papers from the Papers link.`;
  }
  finally { if (loadProgress) loadProgress.hidden = true; }
});
