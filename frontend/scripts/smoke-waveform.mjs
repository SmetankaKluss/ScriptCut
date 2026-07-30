import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(__dirname, '../src/components/WaveformTimeline.tsx'), 'utf8');

assert.match(source, /\/audio\/waveform/, 'Waveform must be built through the bounded backend endpoint');
assert.doesNotMatch(source, /decodeAudioData/, 'Waveform must not decode a complete stream in browser memory');
assert.doesNotMatch(source, /response\.arrayBuffer/, 'Waveform must not download a complete stream into an ArrayBuffer');
assert.match(
  source,
  /монтаж и расшифровка продолжают работать/,
  'Waveform failure must be explained as non-blocking',
);
