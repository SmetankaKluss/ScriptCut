#!/usr/bin/env node

/**
 * Native Windows verification for the unpacked Electron application.
 *
 * This validates more than file presence: the packaged backend is started,
 * readiness endpoints are queried with the per-launch token contract, and a
 * real vertical MP4 with burn-in captions plus a censorship bleep is rendered
 * through the packaged FFmpeg.
 */

const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const root = path.join(__dirname, '..');
const arch = process.env.SCRIPTCUT_BUILD_ARCH || process.arch;
const port = Number(process.env.SCRIPTCUT_WINDOWS_QA_PORT || 8765);
const token = 'scriptcut-windows-package-qa';
const resourcesDir = path.join(root, 'dist', 'win-unpacked', 'resources');
const ffmpegDir = path.join(resourcesDir, 'bin', `win32-${arch}`);
const ffmpeg = path.join(ffmpegDir, 'ffmpeg.exe');
const ffprobe = path.join(ffmpegDir, 'ffprobe.exe');
const backend = path.join(resourcesDir, 'backend-runtime', 'scriptcut-backend', 'scriptcut-backend.exe');
const backendSource = path.join(resourcesDir, 'backend');
const packagedApp = path.join(root, 'dist', 'win-unpacked', 'ScriptCut.exe');

function fail(message) {
  throw new Error(`Windows package verification failed: ${message}`);
}

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
  if (result.error || result.status !== 0) {
    fail(`${path.basename(command)} failed: ${(result.error?.message || result.stderr || result.stdout || '').trim()}`);
  }
  return result;
}

function request(method, pathname, body) {
  const payload = body === undefined ? null : Buffer.from(JSON.stringify(body));
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: '127.0.0.1',
      port,
      path: pathname,
      method,
      headers: {
        ...(payload ? {
          'Content-Type': 'application/json',
          'Content-Length': payload.length,
        } : {}),
        'X-ScriptCut-Token': token,
      },
    }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        let data = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch {
          data = text;
        }
        if ((res.statusCode || 500) >= 400) {
          reject(new Error(`${method} ${pathname} returned ${res.statusCode}: ${text}`));
          return;
        }
        resolve(data);
      });
    });
    req.on('error', reject);
    req.setTimeout(5000, () => req.destroy(new Error(`${method} ${pathname} timed out`)));
    if (payload) req.write(payload);
    req.end();
  });
}

function probeStatus(probePort, pathname = '/health') {
  return new Promise((resolve) => {
    const req = http.get({
      hostname: '127.0.0.1',
      port: probePort,
      path: pathname,
    }, (res) => {
      res.resume();
      resolve(res.statusCode || 0);
    });
    req.on('error', () => resolve(0));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(0);
    });
    req.end();
  });
}

async function waitForBackend(child, logLines) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) fail(`backend exited early with code ${child.exitCode}: ${logLines.join('\n')}`);
    try {
      const health = await request('GET', '/health');
      if (health?.status === 'ok') return;
    } catch {
      // The one-dir executable has a noticeable first cold start on CI.
    }
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
  fail(`backend did not become ready in 120 seconds: ${logLines.join('\n')}`);
}

async function waitForJob(jobId, backendLogs) {
  const deadline = Date.now() + 120_000;
  let lastJob = null;
  while (Date.now() < deadline) {
    const job = await request('GET', `/jobs/${jobId}`);
    lastJob = job;
    if (job.status === 'succeeded') return job.result;
    if (job.status === 'failed' || job.status === 'canceled') {
      fail(`export job ${job.status}: ${job.error || job.message}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  fail(
    `test export did not finish in 120 seconds. Last job: ${JSON.stringify(lastJob)}. ` +
    `Backend log tail: ${backendLogs.join('\n')}`,
  );
}

function stopBackend(child) {
  if (!child || child.exitCode !== null) return;
  spawnSync('taskkill.exe', ['/pid', String(child.pid), '/f', '/t'], {
    stdio: 'ignore',
    windowsHide: true,
  });
}

async function verifyPackagedApp(tempDir) {
  const profileDir = path.join(tempDir, 'electron profile');
  const logs = [];
  const child = spawn(packagedApp, [`--user-data-dir=${profileDir}`], {
    cwd: path.dirname(packagedApp),
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const appendLog = (chunk) => {
    const line = chunk.toString().trim();
    if (line) logs.push(line);
    if (logs.length > 30) logs.splice(0, logs.length - 30);
  };
  child.stdout.on('data', appendLog);
  child.stderr.on('data', appendLog);

  try {
    const deadline = Date.now() + 120_000;
    while (Date.now() < deadline) {
      if (child.exitCode !== null) {
        fail(`packaged app exited early with code ${child.exitCode}: ${logs.join('\n')}`);
      }
      // /health intentionally stays public for readiness probes. A protected
      // endpoint must reject this tokenless request, which proves that
      // ScriptCut.exe started its per-launch authenticated backend instead of
      // accidentally reaching an unrelated development service.
      if (await probeStatus(8642, '/system/checks') === 401) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        if (child.exitCode !== null) fail(`packaged app exited after backend startup: ${logs.join('\n')}`);
        console.log('Packaged ScriptCut.exe launch verified.');
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 750));
    }
    fail(`packaged app did not start its protected backend in 120 seconds: ${logs.join('\n')}`);
  } finally {
    stopBackend(child);
  }
}

async function main() {
  if (process.platform !== 'win32') fail('this check must run on native Windows');
  if (!['x64', 'arm64'].includes(arch)) fail(`unsupported architecture ${arch}`);

  for (const filePath of [ffmpeg, ffprobe, backend, packagedApp]) {
    if (!fs.existsSync(filePath)) fail(`missing ${path.relative(root, filePath)}`);
  }
  const manifestPath = path.join(ffmpegDir, 'bundle-manifest.json');
  if (!fs.existsSync(manifestPath)) fail(`missing ${path.relative(root, manifestPath)}`);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (manifest.platform !== 'win32' || manifest.arch !== arch) {
    fail(`FFmpeg manifest targets ${manifest.platform}-${manifest.arch}, expected win32-${arch}`);
  }
  if (!manifest.capabilities?.assSubtitles) fail('Windows FFmpeg must include the ASS subtitle filter');

  run(ffmpeg, ['-version']);
  run(ffprobe, ['-version']);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'scriptcut-windows-qa-'));
  const input = path.join(tempDir, 'windows input.mp4');
  const output = path.join(tempDir, 'windows output.mp4');
  run(ffmpeg, [
    '-hide_banner', '-loglevel', 'error', '-y',
    '-f', 'lavfi', '-i', 'color=c=0x20253a:s=640x360:r=30',
    '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
    '-t', '2',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac',
    input,
  ]);

  const logs = [];
  const child = spawn(backend, ['--host', '127.0.0.1', '--port', String(port)], {
    cwd: backendSource,
    windowsHide: true,
    env: {
      ...process.env,
      SCRIPTCUT_API_TOKEN: token,
      SCRIPTCUT_FFMPEG_PATH: ffmpeg,
      SCRIPTCUT_FFPROBE_PATH: ffprobe,
      IMAGEIO_FFMPEG_EXE: ffmpeg,
      PATH: `${ffmpegDir}${path.delimiter}${process.env.PATH || ''}`,
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const appendLog = (chunk) => {
    logs.push(chunk.toString().trim());
    if (logs.length > 30) logs.splice(0, logs.length - 30);
  };
  child.stdout.on('data', appendLog);
  child.stderr.on('data', appendLog);

  try {
    await waitForBackend(child, logs);
    const checks = await request('GET', '/system/checks');
    if (!checks?.checks?.ffmpeg?.ok) fail('packaged backend cannot execute bundled FFmpeg');
    if (!checks?.checks?.transcription?.ok) fail('packaged backend cannot load faster-whisper');
    if (!checks?.checks?.captions?.ok) fail('packaged Windows FFmpeg cannot burn captions');

    const started = await request('POST', '/jobs/export', {
      input_path: input,
      output_path: output,
      keep_segments: [{ start: 0, end: 1.8 }],
      muted_ranges: [{ start: 0.5, end: 0.9, kind: 'bleep' }],
      mode: 'precise',
      resolution: '720p',
      aspectRatio: 'vertical',
      format: 'mp4',
      captions: 'burn-in',
      captionStyle: {
        fontName: 'Arial',
        fontSize: 44,
        fontColor: '#ffffff',
        backgroundColor: '#000000',
        position: 'bottom',
        bold: true,
        preset: 'creator',
        highlightColor: '#7c73ff',
        wordsPerLine: 4,
        animation: 'pop',
      },
      words: [
        { word: 'Windows', start: 0.1, end: 0.7, confidence: 1 },
        { word: 'готов', start: 0.75, end: 1.4, confidence: 1 },
      ],
      deleted_indices: [],
    });
    if (!started?.job_id) fail('backend did not create the Windows export job');
    const result = await waitForJob(started.job_id, logs);
    if (!fs.existsSync(output) || fs.statSync(output).size < 1024) {
      fail(`test export was not created: ${JSON.stringify(result)}`);
    }
    run(ffprobe, ['-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1', output]);
    console.log(`Windows package verified with real export: ${path.relative(root, resourcesDir)}`);
  } finally {
    stopBackend(child);
  }

  try {
    await verifyPackagedApp(tempDir);
  } finally {
    fs.rmSync(tempDir, {
      recursive: true,
      force: true,
      maxRetries: 8,
      retryDelay: 250,
    });
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
