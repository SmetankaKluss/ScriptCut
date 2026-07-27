import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const __dirname = dirname(fileURLToPath(import.meta.url));
const sourcePath = resolve(__dirname, '../src/utils/censorship.ts');
const source = readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
});
const module = { exports: {} };
const run = new Function('exports', 'module', 'require', compiled.outputText);
run(module.exports, module, require);

const { findCensorMatches, parseCustomPhrases } = module.exports;

const words = [
  { word: 'Это', start: 0, end: 0.3, confidence: 1 },
  { word: 'блять,', start: 0.3, end: 0.7, confidence: 1 },
  { word: 'секретный', start: 0.7, end: 1.1, confidence: 1 },
  { word: 'проект', start: 1.1, end: 1.5, confidence: 1 },
  { word: 'готов', start: 1.5, end: 1.8, confidence: 1 },
];

assert.deepEqual(parseCustomPhrases('секретный проект, spoiler'), [
  ['секретный', 'проект'],
  ['spoiler'],
]);
assert.deepEqual(
  findCensorMatches(words, 'секретный проект').map((match) => [
    match.startWordIndex,
    match.endWordIndex,
    match.source,
  ]),
  [
    [1, 1, 'built-in'],
    [2, 3, 'custom'],
  ],
);
assert.deepEqual(
  findCensorMatches(words, '', false),
  [],
);
