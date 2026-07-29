#!/usr/bin/env node

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const pkg = require(path.join(root, 'package.json'));

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}

const windowsTargets = (pkg.build?.win?.target || []).map((entry) => entry.target || entry);
assert(windowsTargets.includes('nsis'), 'Windows package must include an NSIS installer');
assert(windowsTargets.includes('portable'), 'Windows package must include a portable executable');
assert.strictEqual(pkg.build?.win?.icon, 'build/icon.ico');

const resources = pkg.build?.extraResources || [];
assert(
  resources.some((entry) => entry.to === 'backend-runtime/scriptcut-backend'),
  'Packaged apps must include the standalone backend runtime',
);
assert(
  resources.some((entry) => entry.to === 'bin'),
  'Packaged apps must include the platform FFmpeg bundle',
);

const bridge = read('electron/python-bridge.js');
assert(bridge.includes("'scriptcut-backend.exe'"), 'Electron must resolve the Windows backend executable');
assert(bridge.includes("spawn('taskkill'"), 'Electron must terminate the Windows backend process tree');
assert(bridge.includes('120000'), 'Packaged backend must allow for first-launch antivirus scanning');
assert(bridge.includes("windowsHide: process.platform === 'win32'"), 'Windows backend must not open a console window');
assert(
  read('electron/bundled-tools.js').includes('SCRIPTCUT_FFMPEG_PATH'),
  'The standalone backend must receive ScriptCut bundled FFmpeg',
);

const main = read('electron/main.js');
const frontend = read('frontend/index.html');
assert(main.includes('http://127.0.0.1:${BACKEND_PORT}'), 'Electron backend URL must use the protected IPv4 origin');
assert(main.includes('createStartupWindow()'), 'Packaged app must show startup feedback while the backend initializes');
assert(frontend.includes('http://127.0.0.1:*'), 'CSP must permit the protected local backend origin');

const launcher = read('backend/launcher.py');
assert(launcher.includes('multiprocessing.freeze_support()'), 'PyInstaller backend must support frozen worker processes');
assert(
  read('scripts/desktop-qa.js').includes('needsWindowsShell'),
  'Desktop QA must launch npm.cmd through the Windows command shell',
);
const setup = read('scripts/setup.js');
assert(setup.includes("['npm', 'npx'].includes(command)"), 'Setup must use the Windows shell only for npm scripts');
assert(setup.includes('shell: false'), 'Setup must launch Python directly so pip specifiers are not shell redirects');

for (const script of [
  'scripts/download-windows-ffmpeg.js',
  'scripts/check-windows-package.js',
  'scripts/release-windows.js',
  'scripts/generate-windows-icon.js',
  'scripts/run-backend-smoke.js',
]) {
  assert(fs.existsSync(path.join(root, script)), `Missing ${script}`);
}

const windowsFfmpegDownloader = read('scripts/download-windows-ffmpeg.js');
assert(
  windowsFfmpegDownloader.includes('versionedAssetPattern'),
  'Windows FFmpeg resolution must support versioned release asset names',
);
assert(
  windowsFfmpegDownloader.includes('expectedChecksum(checksums)'),
  'Versioned Windows FFmpeg downloads must remain checksum verified',
);

console.log('Desktop packaging configuration smoke checks passed.');
