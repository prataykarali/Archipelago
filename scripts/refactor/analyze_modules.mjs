// Read-only analysis: for each mutable top-level binding, list assignment
// sites and the spread of references, so module boundaries keep writes local.
import { readFileSync } from 'node:fs';
import { parse } from 'acorn';

const html = readFileSync(process.argv[2], 'utf8');
const scripts = [...html.matchAll(/<script(?![^>]*src)[^>]*>([\s\S]*?)<\/script>/g)];
const body = scripts.map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a));
const ast = parse(body, { ecmaVersion: 'latest', sourceType: 'script', locations: true });

const mutable = new Set();
for (const node of ast.body) {
  if (node.type === 'VariableDeclaration' && (node.kind === 'let' || node.kind === 'var')) {
    for (const d of node.declarations) if (d.id.type === 'Identifier') mutable.add(d.id.name);
  }
}

const writes = new Map([...mutable].map((n) => [n, []]));
const reads = new Map([...mutable].map((n) => [n, []]));

function walk(node, parent) {
  if (!node || typeof node !== 'object') return;
  if (node.type === 'AssignmentExpression' && node.left.type === 'Identifier' && mutable.has(node.left.name)) {
    writes.get(node.left.name).push(node.loc.start.line);
  }
  if (node.type === 'Identifier' && mutable.has(node.name)) {
    const isMemberProp = parent && parent.type === 'MemberExpression' && parent.property === node && !parent.computed;
    const isKey = parent && parent.type === 'Property' && parent.key === node && !parent.computed;
    const isWrite = parent && parent.type === 'AssignmentExpression' && parent.left === node;
    if (!isMemberProp && !isKey && !isWrite) reads.get(node.name).push(node.loc.start.line);
  }
  for (const key of Object.keys(node)) {
    const value = node[key];
    if (Array.isArray(value)) value.forEach((v) => walk(v, node));
    else if (value && typeof value.type === 'string') walk(value, node);
  }
}
walk(ast, null);

for (const name of [...mutable].sort()) {
  const w = writes.get(name);
  const r = reads.get(name);
  const rMin = r.length ? Math.min(...r) : 0;
  const rMax = r.length ? Math.max(...r) : 0;
  console.log(`${name.padEnd(26)} writes=[${w.join(',')}] reads=${r.length} range=${rMin}..${rMax}`);
}
