#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.join(__dirname, '..');
const isWindows = process.platform === 'win32';
const venvDir = process.env.SCRIPTCUT_VENV_DIR || '.venv';
const python = isWindows
  ? path.join(root, venvDir, 'Scripts', 'python.exe')
  : path.join(root, venvDir, 'bin', 'python');
const backendDir = path.join(root, 'backend');
const buildDir = path.join(root, 'build');
const distDir = path.join(buildDir, 'backend-runtime');
const workDir = path.join(buildDir, 'pyinstaller-work');
const specDir = path.join(buildDir, 'pyinstaller-spec');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || root,
    stdio: 'inherit',
    shell: false,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!fs.existsSync(python)) {
  throw new Error(`Backend virtualenv was not found at ${python}. Run npm run setup:backend first.`);
}

run(python, ['-m', 'pip', 'install', '-r', 'requirements-build.txt'], { cwd: backendDir });

const collectPackages = [
  'faster_whisper',
  'tokenizers',
  'av',
];
const collectBinaryDataPackages = ['ctranslate2'];
const hiddenImports = [
  'uvicorn.logging',
  'uvicorn.loops.auto',
  'uvicorn.protocols.http.auto',
  'uvicorn.protocols.websockets.auto',
  'uvicorn.lifespan.on',
];
const metadataPackages = [
  'imageio',
  'imageio-ffmpeg',
  'moviepy',
  'faster-whisper',
  'huggingface-hub',
  'tokenizers',
  'openai',
  'anthropic',
];

const args = [
  '-m',
  'PyInstaller',
  '--noconfirm',
  '--clean',
  '--onedir',
  '--name',
  'scriptcut-backend',
  '--distpath',
  distDir,
  '--workpath',
  workDir,
  '--specpath',
  specDir,
  '--paths',
  backendDir,
];

for (const packageName of collectPackages) {
  args.push('--collect-all', packageName);
}
for (const packageName of collectBinaryDataPackages) {
  args.push('--collect-binaries', packageName, '--collect-data', packageName);
}
for (const moduleName of hiddenImports) {
  args.push('--hidden-import', moduleName);
}
for (const packageName of metadataPackages) {
  args.push('--copy-metadata', packageName);
}
args.push(path.join(backendDir, 'launcher.py'));

run(python, args);

const executable = isWindows
  ? path.join(distDir, 'scriptcut-backend', 'scriptcut-backend.exe')
  : path.join(distDir, 'scriptcut-backend', 'scriptcut-backend');
if (!fs.existsSync(executable)) {
  throw new Error(`Packaged backend executable was not created: ${executable}`);
}
if (!isWindows) fs.chmodSync(executable, 0o755);

// Electron always points MoviePy/ImageIO at ScriptCut's verified platform
// FFmpeg. Keeping ImageIO's second bundled binary wastes ~45-50 MB per app.
const imageioBundledFfmpeg = path.join(
  distDir,
  'scriptcut-backend',
  '_internal',
  'imageio_ffmpeg',
  'binaries',
);
fs.rmSync(imageioBundledFfmpeg, { recursive: true, force: true });

console.log(`Standalone backend ready: ${path.relative(root, executable)}`);
