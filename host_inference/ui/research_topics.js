"use strict";

const RECENT_TOPIC_LIMIT = 10;
const status = document.getElementById("topics-status");
const list = document.getElementById("topics-list");

function latestTopics(runs) {
  const seen = new Set();
  return runs
    .filter(run => run?.run_id && typeof run.topic === "string" && run.topic.trim())
    .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
    .filter(run => {
      const key = run.topic.trim().toLocaleLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, RECENT_TOPIC_LIMIT);
}

function renderTopics(runs) {
  list.replaceChildren();
  const topics = latestTopics(runs);
  status.textContent = topics.length
    ? `Showing ${topics.length} latest topics. Open one to browse its saved paper pages.`
    : "No saved topics yet. Search a topic to collect papers.";
  for (const run of topics) {
    const card = document.createElement("article");
    card.className = "recent-topic-card";
    const title = document.createElement("h2");
    title.textContent = run.topic;
    const date = document.createElement("p");
    date.textContent = String(run.created_at || "").slice(0, 10) || "Saved search";
    const topicLink = document.createElement("a");
    topicLink.href = `/research/?run=${encodeURIComponent(run.run_id)}#paper-results`;
    topicLink.textContent = "Open saved papers →";
    const resultsLink = document.createElement("a");
    resultsLink.href = `/research/topic?run=${encodeURIComponent(run.run_id)}`;
    resultsLink.textContent = "Topic summary";
    card.append(title, date, topicLink, resultsLink);
    list.append(card);
  }
}

async function loadTopics() {
  if (!await window.archipelagoResearchReady) return;
  try {
    const response = await fetch("/api/research/intelligence/runs", { cache: "no-store" });
    if (!response.ok) throw new Error(`Research history unavailable (${response.status}).`);
    const data = await response.json();
    renderTopics(Array.isArray(data.runs) ? data.runs : []);
  } catch (error) {
    status.textContent = error.message;
  }
}

window.addEventListener("load", loadTopics);
window.addEventListener("pageshow", event => { if (event.persisted) void loadTopics(); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) void loadTopics(); });
