#!/usr/bin/env node

/**
 * Download a checksum-verified static FFmpeg build for Windows packaging.
 *
 * `where ffmpeg` often resolves to a Chocolatey shim. Copying that shim into
 * an Electron app works on the build machine and fails on a friend's PC. This
 * script deliberately downloads the real static executables and then delegates
 * manifest/capability generation to prepare-ffmpeg-bundle.js.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream/promises');
const { Readable } = require('stream');
const { spawnSync } = require('child_process');

const root = path.join(__dirname, '..');
const cacheDir = path.join(root, '.cache', 'windows-ffmpeg');
const configuredReleaseBase = process.env.SCRIPTCUT_WINDOWS_FFMPEG_RELEASE || '';
const target = process.arch === 'arm64' ? 'winarm64' : 'win64';
const defaultAsset = `ffmpeg-n8.1-latest-${target}-gpl-8.1.zip`;
const configuredAssetName = process.env.SCRIPTCUT_WINDOWS_FFMPEG_ASSET || '';
let assetName = configuredAssetName || defaultAsset;
const releaseResolveAttempts = Number(process.env.SCRIPTCUT_FFMPEG_RELEASE_ATTEMPTS || 6);

function fail(message) {
  throw new Error(`Windows FFmpeg preparation failed: ${message}`);
}

async function response(url, extraHeaders = {}) {
  const result = await fetch(url, {
    headers: {
      'User-Agent': 'ScriptCut-Windows-Release',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(process.env.GITHUB_TOKEN ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {}),
      ...extraHeaders,
    },
    redirect: 'follow',
  });
  if (!result.ok) fail(`${url} returned HTTP ${result.status}`);
  return result;
}

async function resolveRelease() {
  if (configuredReleaseBase) {
    const releaseBase = configuredReleaseBase.replace(/\/+$/, '');
    return {
      archiveUrl: `${releaseBase}/${assetName}`,
      checksumsUrl: `${releaseBase}/checksums.sha256`,
      downloadHeaders: {},
      source: releaseBase,
    };
  }
  const release = await (await response(
    'https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest',
  )).json();
  let archive = release?.assets?.find((asset) => asset.name === assetName);
  if (!archive && !configuredAssetName) {
    const versionedAssetPattern = new RegExp(
      `^ffmpeg-n8\\.1(?:\\.\\d+)?(?:-\\d+-g[0-9a-f]+)?-${target}-gpl-8\\.1\\.zip$`,
      'i',
    );
    const versionedAssets = (release?.assets || []).filter((asset) =>
      versionedAssetPattern.test(asset.name || ''),
    );
    if (versionedAssets.length === 1) {
      archive = versionedAssets[0];
      assetName = archive.name;
    } else if (versionedAssets.length > 1) {
      fail(
        `GitHub release contains multiple matching FFmpeg 8.1 assets for ${target}: ` +
        versionedAssets.map((asset) => asset.name).join(', '),
      );
    }
  }
  const checksums = release?.assets?.find((asset) => asset.name === 'checksums.sha256');
  if (!archive?.url || !checksums?.url) fail(`GitHub release does not contain ${assetName} and checksums.sha256`);
  return {
    archiveUrl: archive.url,
    checksumsUrl: checksums.url,
    downloadHeaders: { Accept: 'application/octet-stream' },
    source: `${release.html_url || 'https://github.com/BtbN/FFmpeg-Builds/releases'} (release ${release.id}, asset ${archive.id})`,
  };
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function resolveReleaseAndChecksum() {
  let lastError = null;
  const attempts = Math.max(1, Math.min(12, releaseResolveAttempts));
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const release = await resolveRelease();
      const checksums = await (await response(release.checksumsUrl, release.downloadHeaders)).text();
      return {
        release,
        expected: expectedChecksum(checksums),
      };
    } catch (error) {
      lastError = error;
      if (attempt === attempts) break;
      const waitMs = Math.min(30_000, attempt * 5_000);
      console.warn(
        `Windows FFmpeg release is not complete yet (attempt ${attempt}/${attempts}); ` +
        `retrying in ${Math.round(waitMs / 1000)}s: ${error.message || error}`,
      );
      await delay(waitMs);
    }
  }
  throw lastError || new Error('could not resolve a complete FFmpeg release');
}

async function download(url, destination, headers = {}) {
  const result = await response(url, headers);
  if (!result.body) fail(`${url} returned an empty response`);
  const temporary = `${destination}.download`;
  fs.rmSync(temporary, { force: true });
  await pipeline(Readable.fromWeb(result.body), fs.createWriteStream(temporary));
  fs.rmSync(destination, { force: true });
  fs.renameSync(temporary, destination);
}

function sha256(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function expectedChecksum(text) {
  for (const line of text.split(/\r?\n/)) {
    const match = line.trim().match(/^([a-fA-F0-9]{64})\s+\*?(.+)$/);
    if (match && match[2] === assetName) return match[1].toLowerCase();
  }
  fail(`checksums.sha256 does not contain ${assetName}`);
}

function findFile(directory, fileName) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = findFile(entryPath, fileName);
      if (nested) return nested;
    } else if (entry.name.toLowerCase() === fileName.toLowerCase()) {
      return entryPath;
    }
  }
  return null;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    env: options.env || process.env,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

async function main() {
  if (process.platform !== 'win32') {
    fail('run this script on a native Windows x64/arm64 machine or Windows CI runner');
  }
  if (!['x64', 'arm64'].includes(process.arch)) {
    fail(`unsupported architecture ${process.arch}; expected x64 or arm64`);
  }
  if (path.basename(assetName) !== assetName || !assetName.toLowerCase().endsWith('.zip')) {
    fail(`invalid archive name ${assetName}`);
  }

  fs.mkdirSync(cacheDir, { recursive: true });
  const { release, expected } = await resolveReleaseAndChecksum();
  const archivePath = path.join(cacheDir, assetName);
  const extractDir = path.join(cacheDir, path.basename(assetName, '.zip'));

  if (!fs.existsSync(archivePath) || sha256(archivePath) !== expected) {
    await download(release.archiveUrl, archivePath, release.downloadHeaders);
  }
  const actual = sha256(archivePath);
  if (actual !== expected) {
    fail(`SHA-256 mismatch for ${assetName}: expected ${expected}, received ${actual}`);
  }

  fs.rmSync(extractDir, { recursive: true, force: true });
  fs.mkdirSync(extractDir, { recursive: true });
  const escapedArchive = archivePath.replace(/'/g, "''");
  const escapedDestination = extractDir.replace(/'/g, "''");
  run('powershell.exe', [
    '-NoProfile',
    '-NonInteractive',
    '-Command',
    `Expand-Archive -LiteralPath '${escapedArchive}' -DestinationPath '${escapedDestination}' -Force`,
  ]);

  const ffmpeg = findFile(extractDir, 'ffmpeg.exe');
  const ffprobe = findFile(extractDir, 'ffprobe.exe');
  if (!ffmpeg || !ffprobe) fail(`could not find ffmpeg.exe and ffprobe.exe inside ${assetName}`);

  run(process.execPath, ['scripts/prepare-ffmpeg-bundle.js'], {
    env: {
      ...process.env,
      SCRIPTCUT_FFMPEG_PATH: ffmpeg,
      SCRIPTCUT_FFPROBE_PATH: ffprobe,
      SCRIPTCUT_REQUIRE_ASS: '1',
    },
  });

  const bundleDir = path.join(root, 'build', 'bin', `${process.platform}-${process.arch}`);
  const license = findFile(extractDir, 'LICENSE.txt');
  if (license) fs.copyFileSync(license, path.join(bundleDir, 'FFMPEG-LICENSE.txt'));
  fs.writeFileSync(
    path.join(bundleDir, 'FFMPEG-SOURCE.txt'),
    `${release.source}\nAsset: ${assetName}\nSHA-256: ${expected}\n`,
    'utf8',
  );

  console.log(`Checksum-verified Windows FFmpeg ready: ${assetName}`);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
