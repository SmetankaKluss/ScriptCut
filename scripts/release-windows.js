#!/usr/bin/env node

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.join(__dirname, '..');
const distDir = path.join(root, 'dist');
const releaseDir = path.join(distDir, 'release-windows');
const arch = process.env.SCRIPTCUT_RELEASE_ARCH || process.arch;

function runStep(name, command, args, options = {}) {
  console.log(`\n==> ${name}`);
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    env: options.env || process.env,
    shell: process.platform === 'win32',
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function sha256(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function releaseArtifacts() {
  if (!fs.existsSync(distDir)) return [];
  return fs.readdirSync(distDir)
    .filter((name) => name.toLowerCase().endsWith('.exe'))
    .map((name) => path.join(distDir, name))
    .filter((filePath) => fs.statSync(filePath).isFile())
    .sort();
}

function cleanPreviousPackages() {
  if (!fs.existsSync(distDir)) return;
  for (const filePath of releaseArtifacts()) {
    fs.rmSync(filePath, { force: true });
  }
  fs.rmSync(path.join(distDir, 'win-unpacked'), { recursive: true, force: true });
}

function main() {
  if (process.platform !== 'win32') {
    throw new Error('Windows releases must be built and verified on native Windows.');
  }
  if (arch !== 'x64' || process.arch !== 'x64') {
    throw new Error(`The current release lane targets native Windows x64; current Node architecture is ${process.arch}.`);
  }

  fs.rmSync(releaseDir, { recursive: true, force: true });
  fs.mkdirSync(releaseDir, { recursive: true });
  cleanPreviousPackages();
  const env = {
    ...process.env,
    SCRIPTCUT_BUILD_ARCH: arch,
    SCRIPTCUT_RELEASE_ARCH: arch,
    CSC_IDENTITY_AUTO_DISCOVERY: process.env.CSC_IDENTITY_AUTO_DISCOVERY || 'false',
  };

  runStep('Generate Windows icon', 'node', ['scripts/generate-windows-icon.js'], { env });
  runStep('Prepare checksum-verified Windows FFmpeg', 'node', ['scripts/download-windows-ffmpeg.js'], { env });
  runStep('Prepare standalone Windows backend', 'npm', ['run', 'release:backend'], { env });
  runStep('Desktop QA', 'npm', ['run', 'qa:desktop'], { env });
  runStep('Build Windows NSIS installer and portable executable', 'npx', [
    'electron-builder',
    '--win',
    `--${arch}`,
  ], { env });
  runStep('Verify packaged Windows runtime and real export', 'node', ['scripts/check-windows-package.js'], { env });

  const artifacts = releaseArtifacts();
  if (artifacts.length < 2) {
    throw new Error(`Expected NSIS and portable .exe artifacts in dist, found ${artifacts.length}.`);
  }

  const checksums = artifacts
    .map((filePath) => `${sha256(filePath)}  ${path.basename(filePath)}`)
    .join('\n');
  fs.writeFileSync(path.join(releaseDir, 'SHA256SUMS.txt'), `${checksums}\n`, 'utf8');
  fs.writeFileSync(path.join(releaseDir, 'release-manifest.json'), `${JSON.stringify({
    product: 'ScriptCut',
    version: require(path.join(root, 'package.json')).version,
    platform: 'win32',
    architecture: arch,
    generatedAt: new Date().toISOString(),
    unsigned: !process.env.CSC_LINK && !process.env.WIN_CSC_LINK,
    artifacts: artifacts.map((filePath) => ({
      file: path.basename(filePath),
      bytes: fs.statSync(filePath).size,
      sha256: sha256(filePath),
    })),
  }, null, 2)}\n`, 'utf8');

  console.log('\nWindows release verified.');
  for (const artifact of artifacts) console.log(`Artifact: ${path.relative(root, artifact)}`);
  console.log(`Checksums: ${path.relative(root, path.join(releaseDir, 'SHA256SUMS.txt'))}`);
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
