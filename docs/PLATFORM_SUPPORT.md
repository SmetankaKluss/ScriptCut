# Platform Support

This page describes the current ScriptCut alpha support boundary. It is intentionally specific so creators can choose the right download before spending time on setup.

| Platform | Current status | Distribution | Notes |
| --- | --- | --- | --- |
| macOS Apple Silicon (arm64) | Verified alpha path | GitHub Release DMG | Portable FFmpeg/FFprobe and the standalone backend are bundled and verified inside the packaged app. |
| macOS Intel (x64) | Preparation supported, release not yet published | Source / maintainer build | Build and validate on a native Intel Mac with a matching x64 FFmpeg bundle before publishing an Intel DMG. |
| Windows 10/11 x64 | Verified alpha path | [NSIS installer + portable `.exe`](https://github.com/SmetankaKluss/ScriptCut/releases/tag/windows-alpha-v0.1.0) | Standalone backend and checksum-verified static FFmpeg are bundled. A native Windows runner completed a real captioned/bleep export and launched the packaged app before publication. |
| Linux | Source development only | No public installer | Do not treat the current AppImage config as a supported release until packaging, FFmpeg, and export have been verified on Linux. |
| Browser at `localhost:5173` | Development and testing only | Local dev server | Browser mode can upload media and download exports, but it does not provide the desktop app's native file access or autosave workflow. |

## What The Desktop Alpha Includes

- Electron desktop application.
- Standalone local FastAPI backend runtime.
- Portable FFmpeg and FFprobe for the matching macOS or Windows architecture.
- Export preflight and a caption capability check.

## Current Alpha Prerequisite

The packaged desktop alpha does not require a separate Python installation. Source development and maintainer builds still use Python 3.11.

Windows release details and SmartScreen guidance are in
[WINDOWS_RU.md](./WINDOWS_RU.md).

## Caption Delivery

Each release records whether its FFmpeg bundle can render ASS subtitles. When it can, creator captions are burned into the exported video. When it cannot, ScriptCut uses the tested video plus `.srt` sidecar fallback. The export panel shows the actual behavior before export.

## Maintainer Release Check

Run this on the target Mac before creating a public alpha:

```bash
npm run release:ffmpeg
npm run release:backend
npm run release:platform
```

The release flow then packages the matching architecture, verifies the FFmpeg bundle inside the Electron app, and records architecture and caption capability in the release manifest.
