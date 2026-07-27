#!/usr/bin/env node

const path = require('path');
const { spawnSync } = require('child_process');
const { resolvePythonRuntime } = require('../electron/python-runtime');
const { bundledToolEnv } = require('../electron/bundled-tools');

const root = path.join(__dirname, '..');

try {
  const runtime = resolvePythonRuntime();
  const result = spawnSync(
    runtime.command,
    [...runtime.argsPrefix, 'scripts/smoke_backend.py'],
    {
      cwd: path.join(root, 'backend'),
      stdio: 'inherit',
      shell: false,
      env: {
        ...process.env,
        ...bundledToolEnv(true),
      },
    },
  );
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
