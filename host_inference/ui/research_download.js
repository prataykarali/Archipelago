"use strict";

const preparedResearchExports = new WeakMap();
const activeResearchControllers = new WeakMap();
const trackedExportControllers = new Set();
const trackedExportUrls = new Set();
const RESEARCH_EXPORT_SCHEMA = "paper-venue-v2";

function revokeResearchExportUrl(url) {
  if (!url) return;
  trackedExportUrls.delete(url);
  try { URL.revokeObjectURL(url); } catch (_) {}
}

function cleanupResearchExports() {
  for (const controller of Array.from(trackedExportControllers)) {
    try { controller.abort(); } catch (_) {}
  }
  trackedExportControllers.clear();
  for (const url of Array.from(trackedExportUrls)) {
    revokeResearchExportUrl(url);
  }
}

window.addEventListener("pagehide", cleanupResearchExports);
window.addEventListener("beforeunload", cleanupResearchExports);

async function prepareResearchExcelLink(link, endpoint, filename, status) {
  if (!link || !endpoint) return;
  const prevController = activeResearchControllers.get(link);
  if (prevController) {
    try { prevController.abort(); } catch (_) {}
    trackedExportControllers.delete(prevController);
  }
  const previous = preparedResearchExports.get(link);
  if (previous) revokeResearchExportUrl(previous);
  preparedResearchExports.delete(link);

  const generation = String(Number(link.dataset.exportGeneration || 0) + 1);
  link.dataset.exportGeneration = generation;
  link.href = "#";
  link.removeAttribute("download");
  link.setAttribute("aria-disabled", "true");
  link.setAttribute("aria-busy", "true");
  link.textContent = "Preparing Excel…";
  link.onclick = event => event.preventDefault();

  const controller = new AbortController();
  activeResearchControllers.set(link, controller);
  trackedExportControllers.add(controller);

  try {
    const response = await fetch(endpoint, {
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (response.status === 401 || response.status === 403) {
      throw new Error("Your session has expired or lacks permission for this workbook. Please sign in again.");
    }
    if (!response.ok) throw new Error(`Excel export failed (${response.status})`);
    if (response.headers.get("X-Archipelago-Export-Schema") !== RESEARCH_EXPORT_SCHEMA) {
      throw new Error("This export is outdated. Refresh the Research page and retry.");
    }
    const workbook = await response.blob();
    const signature = new Uint8Array(await workbook.slice(0, 2).arrayBuffer());
    if (signature[0] !== 0x50 || signature[1] !== 0x4b) {
      throw new Error("The export response was not an Excel workbook.");
    }
    const url = URL.createObjectURL(workbook);
    if (link.dataset.exportGeneration !== generation) {
      revokeResearchExportUrl(url);
      return;
    }
    trackedExportUrls.add(url);
    preparedResearchExports.set(link, url);
    link.href = url;
    link.download = filename;
    link.removeAttribute("aria-disabled");
    link.removeAttribute("aria-busy");
    link.textContent = "Download paper data (Excel)";
    link.onclick = null;
  } catch (error) {
    if (error?.name === "AbortError" || link.dataset.exportGeneration !== generation) return;
    link.removeAttribute("aria-busy");
    link.textContent = "Retry preparing Excel";
    link.onclick = event => {
      event.preventDefault();
      void prepareResearchExcelLink(link, endpoint, filename, status);
    };
    if (status) status.textContent = error.message || "Could not prepare the Excel workbook.";
  } finally {
    trackedExportControllers.delete(controller);
    if (activeResearchControllers.get(link) === controller) {
      activeResearchControllers.delete(link);
    }
  }
}
