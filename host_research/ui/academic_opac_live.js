const liveForm = document.querySelector("#live-opac-form");
const liveStatus = document.querySelector("#live-opac-status");
const liveResults = document.querySelector("#live-opac-results");

function liveText(tag, value, className = "") {
  const element = document.createElement(tag);
  element.textContent = value || "—";
  element.className = className;
  return element;
}

function liveSource(url) {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" || parsed.hostname !== "uemk-opac.l2c2.co.in") return null;
  const link = liveText("a", "Open OPAC record ↗", "text-violet-200 underline");
  link.href = parsed.href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function renderLiveRecord(record) {
  const card = document.createElement("article");
  card.className = "rounded-xl border border-white/15 bg-[#100a2c] p-4";
  card.append(liveText("h4", record.title, "font-semibold text-white"));
  const fields = [
    ["Author", record.author], ["ISBN", record.isbn], ["Publisher", record.publisher],
    ["Year", record.year], ["Koha ID", record.biblionumber],
  ];
  for (const [name, value] of fields) {
    if (value) card.append(liveText("p", `${name}: ${value}`, "mt-1 text-sm text-white/75"));
  }
  if (record.availability) card.append(liveText("p", record.availability, "mt-1 text-sm text-white/75"));
  if (Array.isArray(record.holdings)) {
    for (const copy of record.holdings) {
      const details = [copy.library, copy.call_number && `Call: ${copy.call_number}`,
        copy.status, copy.barcode && `Barcode: ${copy.barcode}`].filter(Boolean).join(" · ");
      card.append(liveText("p", details, "mt-1 text-xs text-violet-100"));
    }
  }
  const source = liveSource(record.source_url);
  if (source) card.append(source);
  return card;
}

liveForm.addEventListener("submit", async event => {
  event.preventDefault();
  const query = document.querySelector("#live-opac-query").value.trim();
  if (!query) return;
  liveResults.replaceChildren();
  liveStatus.textContent = "Checking the live OPAC…";
  try {
    await window.archipelagoAuthReady;
    const response = await fetch(`/api/library/opac/live?q=${encodeURIComponent(query)}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Live OPAC returned ${response.status}`);
    const data = await response.json();
    const results = Array.isArray(data.results) ? data.results : [];
    liveStatus.textContent = `${results.length} result(s) · checked ${new Date(data.fetched_at).toLocaleString()}`;
    if (!results.length) liveResults.append(liveText("p", "No matching public record was found."));
    for (const result of results) {
      const card = renderLiveRecord(result);
      if (!result.holdings?.length && result.biblionumber) {
        const button = liveText("button", "Check ISBN and copies", "mt-2 block text-sm text-violet-200 underline");
        button.type = "button";
        button.addEventListener("click", async () => {
          button.disabled = true;
          button.textContent = "Checking…";
          try {
            const detail = await fetch(`/api/library/opac/live?biblionumber=${encodeURIComponent(result.biblionumber)}`, { cache: "no-store" });
            if (!detail.ok) throw new Error(`Record lookup returned ${detail.status}`);
            card.replaceWith(renderLiveRecord(await detail.json()));
          } catch (error) {
            button.disabled = false;
            button.textContent = `Try again (${error.message})`;
          }
        });
        card.append(button);
      }
      liveResults.append(card);
    }
  } catch (error) {
    liveStatus.textContent = `Could not check the live OPAC: ${error.message}`;
  }
});
