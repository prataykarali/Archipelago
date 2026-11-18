import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const source = readFileSync(path.join(repoRoot, 'host_inference/ui/research_intelligence.js'), 'utf8');

function harness(search, pathname = '/research/papers') {
  const listeners = {};
  const navigations = [];
  const sandbox = {
    window: {
      archipelagoResearchReady: Promise.resolve(false),
      addEventListener(name, listener) { listeners[name] = listener; },
    },
    document: {
      addEventListener() {},
      body: { classList: { add() {} } },
    },
    location: {
      pathname, search, hash: '',
      replace(url) { navigations.push(url); },
      assign(url) { navigations.push(url); },
    },
  };
  vm.runInNewContext(source, sandbox, { filename: 'research_intelligence.js' });
  return { sandbox, navigations, load: () => listeners.load() };
}

test('a valid run ID is a nonempty string, not a stringified missing value', () => {
  const { sandbox } = harness('');
  for (const invalid of [null, undefined, '', ' ', 'undefined', 'Undefined', 'null', 'NaN', 42]) {
    assert.equal(sandbox.validRunId(invalid), false, String(invalid));
  }
  for (const valid of ['123e4567-e89b-12d3-a456-426614174000', 'run-20261118', 'abc_def']) {
    assert.equal(sandbox.validRunId(valid), true, valid);
  }
});

test('malformed or absent run IDs return the papers deep link to /research', async () => {
  for (const search of ['', '?run=undefined', '?run=null', '?run=NaN', '?run=%20']) {
    const ui = harness(search);
    await ui.load();
    assert.deepEqual(ui.navigations, ['/research'], search);
  }
});

test('valid saved-run deep links are not silently rewritten', async () => {
  const ui = harness('?run=run-20261118');
  await ui.load();
  assert.deepEqual(ui.navigations, []);
});

test('research landing page refuses to redirect on run=undefined', async () => {
  const ui = harness('?run=undefined', '/research');
  await ui.load();
  assert.deepEqual(ui.navigations, []);
});

test('valid research landing run IDs route to the papers page', async () => {
  const ui = harness('?run=run-20261118', '/research');
  await ui.load();
  assert.deepEqual(ui.navigations, ['/research/papers?run=run-20261118']);
});
