// Headless smoke test for the chat UI. Serves ui/chat statically (bypassing the
// Flask auth gate) and loads it in the system Chrome via playwright-core, then
// asserts the bundle initialises with no uncaught errors and exposes its public
// surface. Used as the safety net for the modularization refactor.
//
//   node scripts/refactor/smoke_chat_ui.mjs [ui/chat] [port]
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { chromium } from 'playwright-core';

const root = process.argv[2] || 'ui/chat';
const port = Number(process.argv[3] || 8799);
const CHROME = process.env.CHROME_PATH || '/usr/bin/google-chrome';

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
};

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  // Minimal auth mocks so the page's auth bridge does not redirect to /login.
  if (url.pathname === '/api/auth/config') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ required: false, url: '', anon_key: '' }));
    return;
  }
  if (url.pathname.startsWith('/api/')) {
    const shapes = {
      '/api/auth/me': [401, {}],
      '/api/catalog/all': [200, { documents: [], total: 0 }],
      '/api/library/data': [200, { success: true, pearson_books: [], research_papers: [] }],
    };
    const [status, body] = shapes[url.pathname] || [200, {}];
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(body));
    return;
  }
  const rel = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, '');
  const file = join(root, rel === '/' ? 'index.html' : rel);
  try {
    const data = await readFile(file);
    res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('not found');
  }
});

await new Promise((resolve) => server.listen(port, '127.0.0.1', resolve));

const errors = [];
const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
page.on('console', (msg) => {
  if (msg.type() === 'error') {
    const text = msg.text();
    // Missing backend/image assets are expected in this static harness.
    if (/Failed to load resource|net::ERR|api\/auth|404/.test(text)) return;
    errors.push(`console.error: ${text}`);
  }
});

await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(2500);

const checks = await page.evaluate(() => {
  const has = (name) => typeof window[name] === 'function';
  return {
    chatInput: !!document.getElementById('chat-input'),
    sendButton: !!document.getElementById('send-btn') || !!document.querySelector('[id*="send"]'),
    welcome: !!document.querySelector('.welcome, #welcome, [id*="welcome"]'),
    toggleGraph: has('toggleHorizontalGraphCard'),
    chooseGraph: has('chooseGraphExperience'),
    renderGraph: has('renderHorizontalGraphCard'),
    adaptive: has('submitAdaptiveAnswer'),
    topology: has('populateTopology'),
    remediation: has('openPrerequisiteRemediationReader'),
    autoPrompt: typeof autoPrompt === 'function',
    getPearson: typeof getPearsonBookEntry === 'function',
  };
});

await browser.close();
server.close();

const failed = Object.entries(checks).filter(([, ok]) => !ok).map(([k]) => k);
console.log(JSON.stringify({ errors, checks, failed }, null, 2));
if (errors.length || failed.length) {
  console.error(`\nSMOKE FAILED: ${errors.length} runtime error(s), missing: ${failed.join(', ') || 'none'}`);
  process.exit(1);
}
console.log('\nSMOKE OK');
