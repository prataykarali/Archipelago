"use strict";

const preparedResearchExports = new WeakMap();

async function prepareResearchExcelLink(link, endpoint, filename, status) {
  const previous = preparedResearchExports.get(link);
  if (previous) URL.revokeObjectURL(previous);
  preparedResearchExports.delete(link);
  const generation = String(Number(link.dataset.exportGeneration || 0) + 1);
  link.dataset.exportGeneration = generation;
  link.href = '#';
  link.removeAttribute('download');
  link.setAttribute('aria-disabled', 'true');
  link.textContent = 'Preparing Excel…';
  link.onclick = event => event.preventDefault();
  try {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Excel export failed (${response.status})`);
    const workbook = await response.blob();
    const signature = new Uint8Array(await workbook.slice(0, 2).arrayBuffer());
    if (signature[0] !== 0x50 || signature[1] !== 0x4b) throw new Error('The export response was not an Excel workbook.');
    const url = URL.createObjectURL(workbook);
    if (link.dataset.exportGeneration !== generation) {
      URL.revokeObjectURL(url);
      return;
    }
    preparedResearchExports.set(link, url);
    link.href = url;
    link.download = filename;
    link.removeAttribute('aria-disabled');
    link.textContent = 'Download paper data (Excel)';
    link.onclick = null;
  } catch (error) {
    if (link.dataset.exportGeneration !== generation) return;
    link.textContent = 'Retry preparing Excel';
    link.onclick = event => {
      event.preventDefault();
      void prepareResearchExcelLink(link, endpoint, filename, status);
    };
    if (status) status.textContent = error.message || 'Could not prepare the Excel workbook.';
  }
}
