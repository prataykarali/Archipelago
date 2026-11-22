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
  if (!Array.isArray(dossier?.paper_headers) || !Array.isArray(paper?.rankable_values)) return [];
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
  if (className) a.className = className;
  if (typeof href === "string" && href.startsWith("https://")) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
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
  if (!root || value === null || value === undefined || value === "") return;
  const tile = document.createElement("div"); tile.className = "paper-stat";
  const symbol = document.createElement("span"); symbol.className = "paper-stat-icon"; symbol.textContent = icon;
  const body = document.createElement("div");
  const name = document.createElement("small"); name.textContent = label;
  const count = document.createElement("strong"); count.textContent = dossierText(value);
  body.append(name, count); tile.append(symbol, body); root.append(tile);
}

function addDossierBar(root, label, count, maximum) {
  if (!root) return;
  const row = document.createElement("div"); row.className = "topic-bar-row";
  const text = document.createElement("span"); text.textContent = label;
  const track = document.createElement("div"); track.className = "topic-bar-track";
  const fill = document.createElement("i"); fill.style.width = `${Math.round(count / Math.max(maximum, 1) * 100)}%`;
  track.append(fill);
  const number = document.createElement("strong"); number.textContent = String(count);
  row.append(text, track, number); root.append(row);
}

function addExtractionCard(dashboard, field, label, facts) {
  if (!dashboard) return;
  const safeFacts = Array.isArray(facts) ? facts : [];
  const card = dossierCard(`${label} · ${safeFacts.length}`, `run-${field}`);
  if (!safeFacts.length) {
    const empty = document.createElement("p"); empty.className = "run-empty";
    empty.textContent = `No named ${label.toLowerCase()} were verified in the source title or abstract.`;
    card.append(empty);
  } else {
    const list = document.createElement("ul");
    for (const fact of safeFacts) {
      const item = document.createElement("li");
      const name = document.createElement("strong"); name.textContent = fact.name || "";
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
  const coverSpan = document.querySelector(".paper-cover span");
  if (coverSpan) coverSpan.textContent = "PAPER";
  
  const topicLink = dossierEl("paper-topic-link");
  if (topicLink) {
    topicLink.textContent = dossier.topic || "Topic overview";
    topicLink.href = `/research/topic?${query}`;
  }
  
  const titleEl = dossierEl("paper-title");
  if (titleEl) titleEl.textContent = paper.title || "Untitled Paper";
  
  const authorsEl = dossierEl("paper-authors");
  if (authorsEl) authorsEl.textContent = Array.isArray(paper.authors) ? paper.authors.join(" · ") : "";
  
  const venueEl = dossierEl("paper-venue");
  if (venueEl) venueEl.textContent = [paper.venue, paper.year].filter(Boolean).join(" · ");
  
  const subtitleEl = dossierEl("paper-subtitle");
  if (subtitleEl) {
    const retrieved = dossier.retrieved_at ? `Retrieved ${String(dossier.retrieved_at).slice(0, 10)} · ` : "";
    const sourceCount = Array.isArray(paper.sources) ? paper.sources.length : 0;
    subtitleEl.textContent = `${retrieved}${paper.abstract ? "source title and abstract" : "source title only"} · ${sourceCount} source records`;
  }
  
  const tags = dossierEl("paper-tags");
  if (tags) {
    tags.replaceChildren();
    const methods = Array.isArray(paper.extracted?.methods) ? paper.extracted.methods : [];
    for (const fact of methods.slice(0, 4)) {
      const tag = document.createElement("span"); tag.textContent = fact.name; tags.append(tag);
    }
  }
  
  const actions = dossierEl("paper-actions");
  if (actions) {
    actions.replaceChildren();
    if (paper.url) actions.append(dossierLink("Open provider record ↗", paper.url, "paper-action-secondary"));
    if (/^10\.\d{4,9}\/\S+$/i.test(paper.doi || "")) actions.append(dossierLink("Open DOI ↗", `https://doi.org/${encodeURIComponent(paper.doi)}`, "paper-action-secondary"));
    actions.append(dossierLink("Topic extraction ↗", `/research/topic?${query}`, "paper-action-secondary"));
  }
  
  const value = header => {
    if (!Array.isArray(dossier.paper_headers) || !Array.isArray(paper.rankable_values)) return null;
    const idx = dossier.paper_headers.indexOf(header);
    return idx >= 0 ? paper.rankable_values[idx] : null;
  };
  
  const stats = dossierEl("paper-stat-strip");
  if (stats) {
    stats.replaceChildren();
    addDossierStat(stats, "Discovery fit", value("Discovery Fit Score (%)"), "◎");
    addDossierStat(stats, "Rank in search", value("Discovery Rank"), "▤");
    addDossierStat(stats, "Title match", value("Title Query Match (%)"), "◷");
    addDossierStat(stats, "Source records", value("Verified Source Count"), "✦");
  }
  
  const tabs = dossierEl("paper-tabs");
  if (tabs) tabs.replaceChildren();
  
  const dashboard = dossierEl("paper-dashboard");
  if (dashboard) dashboard.replaceChildren();
  
  if (dashboard && tabs) {
    const abstract = dossierCard("Abstract", "run-abstract", true);
    const abstractText = document.createElement("p");
    abstractText.textContent = paper.abstract || "No abstract was supplied by the selected providers.";
    abstract.append(abstractText);
    dashboard.append(abstract);
    tabs.append(dossierLink("Abstract", "#run-abstract"));
    
    for (const [field, label] of DOSSIER_SECTIONS) {
      addExtractionCard(dashboard, field, label, paper.extracted?.[field] || []);
      tabs.append(dossierLink(label, `#run-${field}`));
    }
    
    const metrics = dossierCard("Ranking parameters and coverage", "run-rankings", true);
    const rows = rankingRows(dossier, paper);
    const coverage = document.createElement("p");
    coverage.className = "run-ranking-coverage";
    coverage.textContent = `${rows.length} complete discovery parameters. Fit = 50% title match + 25% abstract match + 15% recency + 10% source corroboration, normalized within this saved search. This ranks discovery fit, not scientific quality. Abstract match is zero when no abstract was supplied.`;
    metrics.append(coverage);
    metrics.append(rankingGrid(rows));
    dashboard.append(metrics);
    tabs.append(dossierLink("Ranking parameters", "#run-rankings"));
    
    if (Array.isArray(dossier.authors) && Array.isArray(paper.author_keys) && paper.author_keys.length) {
      const authors = dossierCard("Authors in this search", "run-author-rankings", true);
      const note = document.createElement("p");
      note.textContent = "Byline measures use only the saved papers in this search. They do not claim a global author impact rank.";
      authors.append(note);
      paper.author_keys.forEach((key, index) => {
        const author = dossier.authors.find(item => item.key === key);
        if (!author) return;
        const heading = document.createElement("h3");
        heading.textContent = (Array.isArray(paper.authors) ? paper.authors[index] : null) || author.values[0];
        authors.append(heading, rankingGrid((dossier.author_headers || []).slice(1).map((lbl, off) => [lbl, author.values[off + 1]])));
      });
      dashboard.append(authors);
      tabs.append(dossierLink("Authors", "#run-author-rankings"));
    }
    
    const reported = Object.entries(paper.provider_metrics || {});
    if (reported.length) {
      const provider = dossierCard("Additional provider facts", "run-provider-facts", true);
      const note = document.createElement("p");
      note.textContent = "These values are reported by connected sources. Coverage differs by provider and they do not enter the complete discovery fit score.";
      provider.append(note, rankingGrid(reported));
      dashboard.append(provider);
      tabs.append(dossierLink("Provider facts", "#run-provider-facts"));
    }
    
    const sourcesList = Array.isArray(paper.sources) ? paper.sources : [];
    const sources = dossierCard(`Source records · ${sourcesList.length}`, "run-sources", true);
    const sourceUl = document.createElement("ul");
    for (const source of sourcesList) {
      const item = document.createElement("li"); item.append(dossierLink(`${source.name} ↗`, source.url)); sourceUl.append(item);
    }
    sources.append(sourceUl);
    dashboard.append(sources);
    tabs.append(dossierLink("Sources", "#run-sources"));
  }
  
  const audit = document.querySelector(".paper-audit");
  if (audit) audit.remove();
}

function renderRunTopic(dossier, context) {
  const query = context.run ? `run=${encodeURIComponent(context.run)}` : "example=state-space-models";
  
  const titleEl = dossierEl("topic-title");
  if (titleEl) titleEl.textContent = dossier.topic || "Research Topic";
  
  const breadcrumbEl = dossierEl("topic-breadcrumb");
  if (breadcrumbEl) breadcrumbEl.textContent = dossier.topic || "Topic overview";
  
  const paperCount = Number(dossier.paper_count || (Array.isArray(dossier.papers) ? dossier.papers.length : 0));
  const retrievedText = dossier.retrieved_at ? ` · retrieved ${String(dossier.retrieved_at).slice(0, 10)}` : "";
  const abstractsCount = Array.isArray(dossier.papers) ? dossier.papers.filter(p => p.abstract).length : 0;
  
  const statusEl = dossierEl("topic-status");
  if (statusEl) {
    statusEl.textContent = `${paperCount} source-linked papers${retrievedText} · ${abstractsCount} with provider abstracts`;
  }
  
  const actions = dossierEl("topic-actions");
  const xlsx = context.run ? `/api/research/intelligence/runs/${encodeURIComponent(context.run)}/xlsx?mode=standard` : "/research/example/Archipelago_State_Space_Models_Rankable.xlsx";
  const excelLink = dossierLink("Download Excel ↗", xlsx, "topic-action");
  const papersUrl = context.run ? `/research/papers?run=${encodeURIComponent(context.run)}` : "/research";
  
  if (actions) {
    actions.replaceChildren();
    actions.append(excelLink, dossierLink("Browse papers ↗", papersUrl, "topic-action secondary"));
    if (context.run) {
      actions.append(dossierLink("Ask chat about this topic ↗", `/chat?research_run_id=${encodeURIComponent(context.run)}`, "topic-action secondary"));
    }
  }
  
  const papersLink = dossierEl("topic-papers-link");
  if (papersLink) papersLink.href = papersUrl;

  if (context.run && typeof prepareResearchExcelLink === "function") {
    void prepareResearchExcelLink(excelLink, xlsx, `archipelago-research-${context.run.slice(0, 8)}-paper-venue-v2.xlsx`, statusEl);
  }
  
  const stats = dossierEl("topic-stats");
  if (stats) {
    stats.replaceChildren();
    const providersCount = dossier.providers ? Object.keys(dossier.providers).length : 0;
    const authorCount = dossier.author_count || 0;
    for (const [label, count, icon] of [["Papers", paperCount, "▤"], ["Authors", authorCount, "♙"], ["Source providers", providersCount, "✦"]]) {
      const tile = document.createElement("div"); tile.className = "topic-stat";
      const symbol = document.createElement("span"); symbol.textContent = icon;
      const copy = document.createElement("div");
      const name = document.createElement("small"); name.textContent = label;
      const value = document.createElement("strong"); value.textContent = String(count);
      copy.append(name, value); tile.append(symbol, copy); stats.append(tile);
    }
  }
  
  const papersList = Array.isArray(dossier.papers) ? dossier.papers : [];
  const yearsObj = dossier.years || {};
  const latestYear = Object.keys(yearsObj).map(Number).filter(Number.isFinite).sort((a, b) => b - a)[0];
  const reported = Object.fromEntries(DOSSIER_SECTIONS.map(([field]) => [field, papersList.filter(paper => paper.extracted?.[field]?.length).length]));
  
  const conclusion = dossierEl("topic-conclusion");
  if (conclusion) {
    conclusion.textContent = `${paperCount} source-linked papers span ${Object.keys(yearsObj).length} publication years${latestYear ? `, most recently ${latestYear}` : ""}. ${abstractsCount} have provider abstracts; ${reported.methods || 0} report methods, ${reported.datasets || 0} name datasets or benchmarks, ${reported.evaluation_metrics || 0} report evaluation metrics, and ${reported.claims || 0} contain extracted claims. These counts describe source coverage, not scientific quality.`;
  }
  
  const coverage = dossierEl("topic-coverage");
  if (coverage) {
    coverage.replaceChildren();
    const counts = DOSSIER_SECTIONS.map(([field, label]) => [label, papersList.filter(p => p.extracted?.[field]?.length).length]);
    const maxCoverage = Math.max(1, ...counts.map(([, count]) => count));
    counts.forEach(([label, count]) => addDossierBar(coverage, label, count, maxCoverage));
  }
  
  const yearsEl = dossierEl("topic-years");
  if (yearsEl) {
    const yearCounts = Object.entries(yearsObj);
    const yearMax = Math.max(1, ...yearCounts.map(([, count]) => count));
    yearsEl.replaceChildren();
    yearCounts.forEach(([label, count]) => addDossierBar(yearsEl, label, count, yearMax));
  }
  
  const providersEl = dossierEl("topic-providers");
  if (providersEl) {
    const providerCounts = Object.entries(dossier.providers || {});
    const providerMax = Math.max(1, ...providerCounts.map(([, count]) => count));
    providersEl.replaceChildren();
    providerCounts.forEach(([label, count]) => addDossierBar(providersEl, label, count, providerMax));
  }
  
  const paperCountBadge = dossierEl("topic-paper-count");
  if (paperCountBadge) paperCountBadge.textContent = `${paperCount} papers`;
  
  const paperList = dossierEl("topic-paper-list");
  if (paperList) {
    paperList.replaceChildren();
    if (!papersList.length) {
      const empty = document.createElement("p");
      empty.className = "topic-empty";
      empty.textContent = "No saved papers for this topic yet.";
      paperList.append(empty);
    } else {
      papersList.forEach((paper, index) => {
        const card = document.createElement("article");
        card.className = "topic-paper-card";
        
        const head = document.createElement("div");
        head.className = "topic-paper-head";
        const number = document.createElement("span");
        number.className = "topic-paper-number";
        number.textContent = String(index + 1).padStart(2, "0");
        
        const paperUrl = `/research/paper?${query}&paper=${index}`;
        const titleLink = document.createElement("a");
        titleLink.className = "topic-paper-title";
        titleLink.href = paperUrl;
        titleLink.textContent = paper.title || "Untitled Paper";
        head.append(number, titleLink);
        card.append(head);
        
        const authors = document.createElement("p");
        authors.className = "topic-paper-authors";
        authors.textContent = [
          Array.isArray(paper.authors) ? paper.authors.join(", ") : "",
          paper.venue,
          paper.year
        ].filter(Boolean).join(" · ") || "";
        card.append(authors);
        
        const badges = document.createElement("div");
        badges.className = "topic-paper-badges";
        const methodsCount = paper.extracted?.methods?.length || 0;
        const datasetsCount = paper.extracted?.datasets?.length || 0;
        const metricsCount = paper.extracted?.evaluation_metrics?.length || 0;
        const claimsCount = paper.extracted?.claims?.length || 0;
        const sourceCount = paper.sources?.length || 0;
        
        if (methodsCount) {
          const b = document.createElement("span"); b.textContent = `${methodsCount} methods`; badges.append(b);
        }
        if (datasetsCount) {
          const b = document.createElement("span"); b.textContent = `${datasetsCount} datasets`; badges.append(b);
        }
        if (metricsCount) {
          const b = document.createElement("span"); b.textContent = `${metricsCount} metrics`; badges.append(b);
        }
        if (claimsCount) {
          const b = document.createElement("span"); b.textContent = `${claimsCount} claims`; badges.append(b);
        }
        if (sourceCount) {
          const b = document.createElement("span"); b.textContent = `${sourceCount} sources`; badges.append(b);
        }
        card.append(badges);
        
        if (paper.abstract) {
          const abstract = document.createElement("p");
          abstract.className = "topic-paper-abstract";
          abstract.textContent = paper.abstract.length > 240 ? `${paper.abstract.slice(0, 240)}…` : paper.abstract;
          card.append(abstract);
        }
        
        const foot = document.createElement("div");
        foot.className = "topic-paper-foot";
        const viewLink = document.createElement("a");
        viewLink.href = paperUrl;
        viewLink.textContent = "Open complete paper OKF →";
        foot.append(viewLink);
        
        if (paper.url) foot.append(dossierLink("Source record ↗", paper.url));
        if (paper.doi) foot.append(dossierLink("DOI ↗", `https://doi.org/${encodeURIComponent(paper.doi)}`));
        card.append(foot);
        
        paperList.append(card);
      });
    }
  }
}

function renderSavedTopicPreview(savedRun, runId) {
  const papers = Array.isArray(savedRun?.papers) ? savedRun.papers : [];
  const topic = savedRun?.options?.topic || "Saved topic";
  
  const title = dossierEl("topic-title"); if (title) title.textContent = topic;
  const breadcrumb = dossierEl("topic-breadcrumb"); if (breadcrumb) breadcrumb.textContent = topic;
  const status = dossierEl("topic-status"); if (status) status.textContent = `${papers.length} saved papers. Loading detailed topic metrics…`;
  const conclusion = dossierEl("topic-conclusion"); if (conclusion) conclusion.textContent = `${papers.length} source-linked papers saved for this topic. Detailed coverage and publication-year totals are loading.`;
  
  const papersUrl = `/research/papers?run=${encodeURIComponent(runId)}`;
  const actions = dossierEl("topic-actions");
  if (actions) {
    actions.append(
      dossierLink(`Browse ${papers.length} papers ↗`, papersUrl, "topic-action"),
      dossierLink("Ask chat about this topic ↗", `/chat?research_run_id=${encodeURIComponent(runId)}`, "topic-action secondary")
    );
  }
  const papersLink = dossierEl("topic-papers-link");
  if (papersLink) papersLink.href = papersUrl;
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
    if (status) status.textContent = "Choose a research run from the search page.";
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
      if (!Number.isInteger(index) || index < 0 || index >= (dossier.papers || []).length) {
        throw new Error("Choose a paper from the ranking table.");
      }
      renderRunPaper(dossier, dossier.papers[index], { run, example });
    } else {
      renderRunTopic(dossier, { run, example });
    }
  } catch (error) {
    if (status) {
      status.textContent = `Detailed topic metrics could not load (${error.message}). Browse saved papers from the Papers link.`;
    }
  } finally {
    if (loadProgress) loadProgress.hidden = true;
  }
});
