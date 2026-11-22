"use strict";

const activeExcelDownloads = new WeakMap();
const activeExcelControllers = new Set();
const trackedBlobUrls = new Set();

function revokeTrackedUrl(url) {
  if (!url || !trackedBlobUrls.has(url)) return;
  trackedBlobUrls.delete(url);
  try {
    URL.revokeObjectURL(url);
  } catch (_) {}
}

function cleanupExcelDownloads() {
  for (const controller of Array.from(activeExcelControllers)) {
    try { controller.abort(); } catch (_) {}
  }
  activeExcelControllers.clear();
  for (const url of Array.from(trackedBlobUrls)) {
    revokeTrackedUrl(url);
  }
}

window.addEventListener("pagehide", cleanupExcelDownloads);
window.addEventListener("beforeunload", cleanupExcelDownloads);

async function verifyXlsxBlob(blob) {
  if (!blob || blob.size < 4) return false;
  const header = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
  return header[0] === 0x50 && header[1] === 0x4b;
}

async function triggerResearchExcelDownload(excelLink, endpoint, filename, statusNode) {
  if (!excelLink || !endpoint) return;
  const existing = activeExcelDownloads.get(excelLink);
  if (existing?.inFlight) return;

  const controller = new AbortController();
  activeExcelControllers.add(controller);
  const state = { inFlight: true, controller, endpoint };
  activeExcelDownloads.set(excelLink, state);

  const originalLabel = excelLink.dataset.defaultLabel || excelLink.textContent || "Download Excel";
  excelLink.dataset.defaultLabel = originalLabel;
  excelLink.setAttribute("aria-busy", "true");
  excelLink.setAttribute("aria-disabled", "true");
  excelLink.textContent = "Downloading Excel…";

  try {
    const response = await fetch(endpoint, {
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });
    if (response.status === 401 || response.status === 403) {
      throw new Error("Your session has expired or lacks permission for this workbook. Please sign in again.");
    }
    if (!response.ok) {
      let message = `Workbook export failed (${response.status}).`;
      try {
        const errJson = await response.json();
        if (errJson?.error) message = errJson.error;
      } catch (_) {}
      throw new Error(message);
    }
    const blob = await response.blob();
    if (!(await verifyXlsxBlob(blob))) {
      throw new Error("Received an invalid Excel workbook payload.");
    }

    if (excelLink.dataset.blobUrl) {
      revokeTrackedUrl(excelLink.dataset.blobUrl);
      delete excelLink.dataset.blobUrl;
    }

    const blobUrl = URL.createObjectURL(blob);
    trackedBlobUrls.add(blobUrl);
    excelLink.dataset.blobUrl = blobUrl;

    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    setTimeout(() => revokeTrackedUrl(blobUrl), 10000);
  } catch (error) {
    if (error?.name === "AbortError") return;
    if (statusNode) {
      statusNode.textContent = error?.message || "Could not download workbook.";
    }
  } finally {
    activeExcelControllers.delete(controller);
    if (activeExcelDownloads.get(excelLink) === state) {
      activeExcelDownloads.delete(excelLink);
      excelLink.removeAttribute("aria-busy");
      excelLink.removeAttribute("aria-disabled");
      excelLink.textContent = originalLabel;
    }
  }
}

async function prepareResearchExcelLink(excelLink, endpoint, filename, statusNode) {
  if (!excelLink || !endpoint) return;
  const prev = activeExcelDownloads.get(excelLink);
  if (prev?.controller) {
    prev.controller.abort();
    activeExcelDownloads.delete(excelLink);
  }
  if (excelLink.dataset.blobUrl) {
    revokeTrackedUrl(excelLink.dataset.blobUrl);
    delete excelLink.dataset.blobUrl;
  }
  excelLink.href = endpoint;
  excelLink.download = filename;
  excelLink.removeAttribute("aria-disabled");
  excelLink.removeAttribute("aria-busy");
  excelLink.textContent = excelLink.dataset.defaultLabel || "Download Excel";
  excelLink.onclick = (event) => {
    event.preventDefault();
    triggerResearchExcelDownload(excelLink, endpoint, filename, statusNode);
  };
}

window.prepareResearchExcelLink = prepareResearchExcelLink;
window.triggerResearchExcelDownload = triggerResearchExcelDownload;
