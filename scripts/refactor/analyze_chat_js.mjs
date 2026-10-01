// AST analysis for the chat UI bundle. Read-only: prints the real top-level
// program structure so the splitter can be built on facts, not indentation.
import { readFileSync } from 'node:fs';
import { parse } from 'acorn';

const html = readFileSync(process.argv[2], 'utf8');
const scripts = [...html.matchAll(/<script(?![^>]*src)[^>]*>([\s\S]*?)<\/script>/g)];
const bodies = scripts.map((m, i) => ({ i, body: m[1], offset: m.index }));
const biggest = bodies.reduce((a, b) => (b.body.length > a.body.length ? b : a));
console.log(`inline scripts: ${scripts.length}; largest index=${biggest.i}, chars=${biggest.body.length}`);

let ast;
try {
  ast = parse(biggest.body, { ecmaVersion: 'latest', sourceType: 'script', locations: true });
} catch (e) {
  console.log('parse as script failed:', e.message);
  ast = parse(biggest.body, { ecmaVersion: 'latest', sourceType: 'module', locations: true });
  console.log('parsed as module');
}

const decls = new Map();       // name -> {kind, line}
const topKinds = {};
for (const node of ast.body) {
  topKinds[node.type] = (topKinds[node.type] || 0) + 1;
  const add = (name, kind) => decls.set(name, { kind, line: node.loc.start.line });
  if (node.type === 'FunctionDeclaration') add(node.id.name, 'function');
  else if (node.type === 'VariableDeclaration') {
    for (const d of node.declarations) {
      const names = d.id.type === 'Identifier' ? [d.id.name]
        : (d.id.type === 'ObjectPattern' || d.id.type === 'ArrayPattern') ? [] : [];
      for (const n of names) add(n, node.kind);
    }
  } else if (node.type === 'ClassDeclaration' && node.id) add(node.id.name, 'class');
}

console.log('top-level statement types:', JSON.stringify(topKinds));
console.log(`top-level declarations: ${decls.size}`);
const mutable = [...decls.entries()].filter(([, v]) => v.kind === 'let' || v.kind === 'var');
console.log('mutable top-level:', JSON.stringify(mutable));
console.log('executable top-level statements:',
  ast.body.filter(n => !['FunctionDeclaration', 'VariableDeclaration', 'ClassDeclaration', 'EmptyStatement'].includes(n.type))
    .map(n => `${n.type}@${n.loc.start.line}`).join(', '));
