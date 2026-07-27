#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.join(__dirname, '..');
const isWindows = process.platform === 'win32';
const venvDir = process.env.SCRIPTCUT_VENV_DIR || '.venv';
const venvPath = path.join(root, venvDir);
const venvPython = isWindows
  ? path.join(venvPath, 'Scripts', 'python.exe')
  : path.join(venvPath, 'bin', 'python');

function run(command, args, options = {}) {
  console.log(`\n$ ${[command, ...args].join(' ')}`);
  const needsWindowsShell = isWindows && ['npm', 'npx'].includes(command);
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    shell: needsWindowsShell,
    ...options,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function commandExists(command, args = ['--version']) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'ignore',
    shell: false,
  });
  return result.status === 0;
}

function resolvePythonCommand() {
  if (process.env.SCRIPTCUT_PYTHON_PATH) {
    return { command: process.env.SCRIPTCUT_PYTHON_PATH, argsPrefix: [] };
  }
  const candidates = isWindows
    ? [
        { command: 'py', argsPrefix: ['-3.11'] },
        { command: 'py', argsPrefix: ['-3.12'] },
        { command: 'py', argsPrefix: ['-3.10'] },
        { command: 'python', argsPrefix: [] },
      ]
    : [
        { command: 'python3.11', argsPrefix: [] },
        { command: 'python3.12', argsPrefix: [] },
        { command: 'python3.10', argsPrefix: [] },
        { command: 'python3', argsPrefix: [] },
      ];
  for (const candidate of candidates) {
    if (commandExists(candidate.command, [...candidate.argsPrefix, '--version'])) return candidate;
  }
  throw new Error('Python 3.10-3.12 was not found. Install Python 3.11 or set SCRIPTCUT_PYTHON_PATH.');
}

function runPython(runtime, args) {
  run(runtime.command, [...runtime.argsPrefix, ...args]);
}

function main() {
  const backendOnly = process.argv.includes('--backend-only');
  const optionalOnly = process.argv.includes('--optional-only');
  console.log('Setting up ScriptCut development environment.');

  if (!backendOnly && !optionalOnly) {
    run('npm', ['ci']);
    run('npm', ['ci'], { cwd: path.join(root, 'frontend') });
  }

  if (!fs.existsSync(venvPython)) {
    const pythonCommand = resolvePythonCommand();
    runPython(pythonCommand, ['-m', 'venv', venvDir]);
  }

  run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip']);
  run(venvPython, ['-m', 'pip', 'install', 'setuptools<81', 'wheel']);
  if (optionalOnly) {
    run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements-optional.txt'], {
      cwd: path.join(root, 'backend'),
    });
  } else {
    run(venvPython, ['-m', 'pip', 'install', '-r', 'requirements.txt'], {
      cwd: path.join(root, 'backend'),
    });
  }

  console.log(
    optionalOnly
      ? '\nOptional tools installed.'
      : backendOnly
        ? '\nBackend setup complete. Run npm run doctor.'
        : '\nSetup complete. Run npm run doctor, then npm run dev.',
  );
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
