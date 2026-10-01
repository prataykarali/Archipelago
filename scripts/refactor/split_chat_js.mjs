// AST-based ES-module splitter for the chat UI inline bundle.
//
// Strategy
//   1. Parse the one large inline <script> as a classic script (acorn).
//   2. Centralise mutable top-level `let`/`var` in js/00-state.js and rewrite
//      every reference to `state.<name>` (byte-preserving for everything else).
//   3. Group the remaining top-level statements into feature modules (~330
//      lines) at statement boundaries; export each module's declarations and
//      generate explicit imports for names owned by other modules.
//   4. js/index.js imports the modules in original order, preserving the
//      evaluation order of top-level statements and IIFEs.
//   5. js/expose.js re-publishes the public surface on `window` so inline
//      `onclick=` handlers and legacy classic scripts keep working.
//
//   node scripts/refactor/split_chat_js.mjs ui/chat/index.html --dry-run
//   node scripts/refactor/split_chat_js.mjs ui/chat/index.html --write
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { parse } from 'acorn';

const TARGET_LINES = 330;

const htmlPath = process.argv[2] || 'ui/chat/index.html';
const urlPrefix = '/js';
const dryRun = process.argv.includes('--dry-run');
const write = process.argv.includes('--write');
const outDir = join(dirname(htmlPath), 'js');

const html = readFileSync(htmlPath, 'utf8');
const blockRe = /<script(?![^>]*\bsrc\b)[^>]*>([\s\S]*?)<\/script>/g;
const blocks = [];
let m;
while ((m = blockRe.exec(html)) !== null) {
  blocks.push({ body: m[1], start: m.index, end: m.index + m[0].length });
}
const big = blocks.reduce((a, b) => (b.body.length > a.body.length ? b : a));
const ast = parse(big.body, { ecmaVersion: 'latest', sourceType: 'script', locations: true });

// ── declarations ───────────────────────────────────────────────────────────
const declared = (node) => {
  const out = [];
  if (node.type === 'FunctionDeclaration' && node.id) out.push({ name: node.id.name, kind: 'function' });
  else if (node.type === 'ClassDeclaration' && node.id) out.push({ name: node.id.name, kind: 'class' });
  else if (node.type === 'VariableDeclaration') {
    for (const d of node.declarations) {
      if (d.id.type === 'Identifier') out.push({ name: d.id.name, kind: node.kind, init: d.init });
    }
  }
  return out;
};

const statements = ast.body.map((node, index) => {
  const decls = declared(node);
  return { node, index, decls, start: node.start, end: node.end, lines: node.loc.end.line - node.loc.start.line + 1 };
});

// Local binding names anywhere inside a statement (params, inner vars) — used
// to avoid generating an import that a local binding would clash with.
function localBindings(node, acc = new Set(), isRoot = true) {
  if (!node || typeof node !== 'object') return acc;
  if (node.type === 'FunctionDeclaration' || node.type === 'FunctionExpression' || node.type === 'ArrowFunctionExpression') {
    for (const p of node.params) collectPattern(p, acc);
    if ((node.type === 'FunctionDeclaration' || node.type === 'FunctionExpression') && node.id && !isRoot) acc.add(node.id.name);
  }
  if (node.type === 'VariableDeclarator') collectPattern(node.id, acc);
  if (node.type === 'CatchClause' && node.param) collectPattern(node.param, acc);
  for (const key of Object.keys(node)) {
    const value = node[key];
    if (Array.isArray(value)) value.forEach((v) => localBindings(v, acc, false));
    else if (value && typeof value.type === 'string') localBindings(value, acc, false);
  }
  return acc;
}
function collectPattern(pat, acc) {
  if (!pat) return;
  if (pat.type === 'Identifier') acc.add(pat.name);
  else if (pat.type === 'ObjectPattern') pat.properties.forEach((p) => collectPattern(p.value || p.argument, acc));
  else if (pat.type === 'ArrayPattern') pat.elements.forEach((e) => collectPattern(e, acc));
  else if (pat.type === 'AssignmentPattern') collectPattern(pat.left, acc);
  else if (pat.type === 'RestElement') collectPattern(pat.argument, acc);
}

// ── mutable state centralisation ───────────────────────────────────────────
const stateNames = new Set();
const stateInits = [];
for (const st of statements) {
  for (const d of st.decls) {
    if ((d.kind === 'let' || d.kind === 'var')) {
      stateNames.add(d.name);
      stateInits.push({ name: d.name, init: d.init ? big.body.slice(d.init.start, d.init.end) : 'undefined' });
    }
  }
}

// Statements that only declare mutable state disappear from the modules.
const keepStatements = statements.filter(
  (st) => !(st.decls.length && st.decls.every((d) => stateNames.has(d.name))),
);

// ── module grouping ────────────────────────────────────────────────────────
const modules = [];
let current = { stats: [], lines: 0 };
for (const st of keepStatements) {
  if (current.stats.length && current.lines + st.lines > TARGET_LINES) {
    modules.push(current);
    current = { stats: [], lines: 0 };
  }
  current.stats.push(st);
  current.lines += st.lines;
}
if (current.stats.length) modules.push(current);

// name -> module index (only non-state top-level declarations)
const owner = new Map();
modules.forEach((mod, index) => {
  mod.decls = new Set();
  for (const st of mod.stats) for (const d of st.decls) {
    if (!stateNames.has(d.name)) mod.decls.add(d.name);
  }
  for (const name of mod.decls) owner.set(name, index);
});

const slug = (mod, index) => {
  const first = [...mod.decls][0] || `module-${index}`;
  const snake = first.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase().replace(/[^a-z0-9]+/g, '-');
  return `${String(index).padStart(2, '0')}-${snake.slice(0, 28)}`;
};
modules.forEach((mod, index) => { mod.file = `${slug(mod, index)}.js`; });

// ── reference collection (for imports) ─────────────────────────────────────
function references(node, acc) {
  if (!node || typeof node !== 'object') return acc;
  if (node.type === 'Identifier') { acc.add(node.name); return acc; }
  for (const key of Object.keys(node)) {
    if (node.type === 'MemberExpression' && key === 'property' && !node.computed) continue;
    if (node.type === 'Property' && key === 'key' && !node.computed) continue;
    if (node.type === 'MethodDefinition' && key === 'key' && !node.computed) continue;
    if ((node.type === 'VariableDeclarator' && key === 'id')) continue;
    if ((node.type === 'FunctionDeclaration' || node.type === 'ClassDeclaration') && key === 'id') continue;
    const value = node[key];
    if (Array.isArray(value)) value.forEach((v) => references(v, acc));
    else if (value && typeof value.type === 'string') references(value, acc);
  }
  return acc;
}

// ── text edits: rewrite bare state references to state.<name> ──────────────
const edits = [];
function collectStateEdits(node, parent) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'Identifier' && stateNames.has(node.name)) {
    const skip =
      (parent && parent.type === 'MemberExpression' && parent.property === node && !parent.computed) ||
      (parent && parent.type === 'Property' && parent.key === node && !parent.computed && !parent.shorthand) ||
      (parent && parent.type === 'VariableDeclarator' && parent.id === node) ||
      (parent && parent.type === 'AssignmentExpression' && parent.left === node && parent.operator === '=') ;
    const isAssignTarget = parent && parent.type === 'AssignmentExpression' && parent.left === node;
    if (!skip || isAssignTarget) edits.push({ start: node.start, end: node.end, text: `state.${node.name}` });
  }
  for (const key of Object.keys(node)) {
    const value = node[key];
    if (Array.isArray(value)) value.forEach((v) => collectStateEdits(v, node));
    else if (value && typeof value.type === 'string') collectStateEdits(value, node);
  }
}
for (const st of keepStatements) collectStateEdits(st.node, null);

// Never rewrite declaration ids of NON-state names (they are untouched anyway).
function applyEdits(text, source) {
  const sorted = [...edits].sort((a, b) => b.start - a.start);
  let out = source;
  for (const e of sorted) out = out.slice(0, e.start) + e.text + out.slice(e.end);
  return out;
}

// Extract each kept statement's source (with state refs rewritten).  Start from
// the previous statement's end so comments/blank lines between top-level
// statements are preserved instead of being silently dropped.
function statementSource(st) {
  const startOffset = st.index > 0 ? statements[st.index - 1].end : 0;
  const raw = big.body.slice(startOffset, st.end);
  const localEdits = edits
    .filter((e) => e.start >= startOffset && e.end <= st.end)
    .sort((a, b) => b.start - a.start);
  let out = raw;
  for (const e of localEdits) {
    const s = e.start - startOffset;
    const t = e.end - startOffset;
    out = out.slice(0, s) + e.text + out.slice(t);
  }
  return out.replace(/^\n+/, '');
}

// ── build module sources ───────────────────────────────────────────────────
const importLines = (mod, index) => {
  const local = new Set();
  for (const st of mod.stats) {
    for (const d of st.decls) local.add(d.name);
    for (const name of localBindings(st.node)) local.add(name);
  }
  const needed = new Map(); // fromModuleFile -> Set(names)
  const refs = new Set();
  for (const st of mod.stats) references(st.node, refs);
  const usesState = [...refs].some((name) => stateNames.has(name));
  for (const name of refs) {
    if (stateNames.has(name) || mod.decls.has(name) || local.has(name)) continue;
    const target = owner.get(name);
    if (target === undefined || target === index) continue;
    const file = modules[target].file;
    if (!needed.has(file)) needed.set(file, new Set());
    needed.get(file).add(name);
  }
  const lines = [...needed.entries()]
    .map(([file, names]) => `import { ${[...names].sort().join(', ')} } from './${file}';`);
  if (usesState) lines.unshift(`import { state } from './00-state.js';`);
  return lines.join('\n');
};

const files = [];
for (const [index, mod] of modules.entries()) {
  const header = `// Auto-split from ui/chat/index.html — ${mod.file}\n// Feature module ${index + 1} of ${modules.length}.\n`;
  const imports = importLines(mod, index);
  const body = mod.stats.map(statementSource).join('\n\n');
  const exports = [...mod.decls].sort();
  const exportLine = exports.length ? `\nexport { ${exports.join(', ')} };\n` : '';
  files.push({ path: join(outDir, mod.file), content: `${header}${imports ? imports + '\n\n' : '\n'}${body}\n${exportLine}` });
}

// state module
const stateBody = stateInits.map((s) => `  ${s.name}: ${s.init},`).join('\n');
files.unshift({
  path: join(outDir, '00-state.js'),
  content: `// Auto-split from ui/chat/index.html — centralised mutable UI state.\n// All modules read/write these through this single object.\nexport const state = {\n${stateBody}\n};\n`,
});

// index + expose modules
const indexContent = `// Auto-split from ui/chat/index.html — module entry point.\n// Import order preserves the original top-level evaluation order.\n${modules
  .map((mod) => `import './${mod.file}';`)
  .join('\n')}\nimport './expose.js';\n`;
files.push({ path: join(outDir, 'index.js'), content: indexContent });

const allNames = [...owner.keys()].sort();
files.push({
  path: join(outDir, 'expose.js'),
  content: `// Re-publish the public surface on window so inline onclick handlers and\n// legacy classic scripts keep working, exactly like the old global script.\n${modules
    .map((mod) => (mod.decls.size ? `import { ${[...mod.decls].sort().join(', ')} } from './${mod.file}';` : ''))
    .filter(Boolean)
    .join('\n')}\n\nconst api = {\n${allNames.map((n) => `  ${n},`).join('\n')}\n};\nfor (const [name, value] of Object.entries(api)) {\n  window[name] = value;\n}\n`,
});

console.log(`modules: ${modules.length + 2}; declarations: ${owner.size}; state bindings: ${stateNames.size}`);
for (const f of files) {
  const lines = f.content.split('\n').length;
  console.log(`  ${f.path.replace(outDir + '/', '').padEnd(42)} ${String(lines).padStart(4)} lines`);
}

if (dryRun || !write) {
  console.log('(dry run — pass --write to apply)');
  process.exit(0);
}

mkdirSync(outDir, { recursive: true });
for (const f of files) writeFileSync(f.path, f.content);

// Syntax-check every generated module.
let failed = 0;
for (const f of files) {
  try {
    execFileSync('node', ['--check', f.path], { stdio: 'pipe' });
  } catch (err) {
    failed += 1;
    console.error(`SYNTAX ERROR in ${f.path}\n${err.stderr?.toString().slice(0, 600)}`);
  }
}

// Swap the inline bundle for the module entry.
const replacement = `<script type="module" src="${urlPrefix}/index.js"></script>`;
const next = html.slice(0, big.start) + replacement + html.slice(big.end);
writeFileSync(htmlPath, next);
console.log(`\nrewrote ${htmlPath}: inline script -> ${replacement}`);
console.log(failed ? `${failed} module(s) failed syntax check` : 'all modules parse cleanly');
process.exit(failed ? 1 : 0);
