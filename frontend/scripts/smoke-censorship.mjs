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

const { findCensorMatches, normalizeToken, parseCustomPhrases } = module.exports;

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

const difficultRussianWords = [
  { word: 'бл*я-я-ять', start: 0, end: 0.4, confidence: 0.72 },
  { word: 'это', start: 0.4, end: 0.7, confidence: 0.98 },
  { word: 'на', start: 0.7, end: 0.85, confidence: 0.91 },
  { word: 'х', start: 0.85, end: 0.92, confidence: 0.61 },
  { word: 'у', start: 0.92, end: 1.0, confidence: 0.62 },
  { word: 'й', start: 1.0, end: 1.08, confidence: 0.63 },
  { word: 'заебааал', start: 1.08, end: 1.5, confidence: 0.76 },
  { word: 'песдец', start: 1.5, end: 1.9, confidence: 0.68 },
  { word: 'страхуй', start: 1.9, end: 2.2, confidence: 0.99 },
  { word: 'ребенок', start: 2.2, end: 2.5, confidence: 0.99 },
];

const difficultMatches = findCensorMatches(difficultRussianWords, '');
assert.deepEqual(
  difficultMatches.map((match) => [
    match.startWordIndex,
    match.endWordIndex,
    match.matchKind,
  ]),
  [
    [0, 0, 'obfuscated'],
    [2, 5, 'split'],
    [6, 6, 'exact'],
    [7, 7, 'exact'],
  ],
);
assert.equal(difficultMatches[0].startTime, 0);
assert.equal(difficultMatches[0].endTime, 0.52);
assert.equal(normalizeToken('XУЙ'), 'хуй');
assert.equal(normalizeToken('6ЛЯДЬ'), 'блядь');
