# Continuous Integration

The recommended GitHub Actions checks for ScriptCut are:

```bash
npm install --package-lock=false --no-audit --no-fund
npm ci --prefix frontend
python -m pip install fastapi pydantic python-multipart requests
npm run lint
npm run build --prefix frontend
npm run smoke:backend
python -m compileall -q backend
```

The Linux backend smoke checks intentionally use minimal Python dependencies so
that lane does not install the full transcription and ML stack.

The Windows lane uses `windows-latest`, installs the complete core dependency
set, downloads checksum-verified FFmpeg, and runs `npm run qa:desktop`.

For release candidates, dispatch the workflow with `package_windows=true`.
That job runs `npm run release:windows`, builds NSIS and portable executables,
starts the packaged backend, and performs a real captioned/bleep video export
before uploading artifacts.

After a successful packaging run, dispatch
`.github/workflows/publish-windows-alpha.yml` with the verified run ID. The
promotion job downloads that exact artifact, checks both SHA-256 values, gives
the installer and portable build stable public names, and updates the Windows
prerelease.
