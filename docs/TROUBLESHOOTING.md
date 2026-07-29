# Troubleshooting

Run this first:

```bash
npm run doctor
```

## Python Not Found

Use Python 3.10, 3.11, or 3.12. Python 3.11 is recommended.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

To force a specific interpreter:

```bash
export SCRIPTCUT_PYTHON_PATH=/absolute/path/to/python
```

## FFmpeg Missing

If you installed ScriptCut from a desktop release, use the first-run checks or update to the latest release. Release builds are prepared with bundled FFmpeg for export.

If you run ScriptCut from source, install FFmpeg and ensure it is available in `PATH`:

```bash
ffmpeg -version
```

Release maintainers can also prepare the local bundle before packaging:

```bash
npm run release:ffmpeg
```

On a native Windows release machine use:

```powershell
npm run release:ffmpeg:windows
```

This path rejects unverified downloads and requires ASS subtitle support.

## Faster Whisper Reports an Unsupported float16 Compute Type

Update to ScriptCut 0.1.1 or newer. It checks which CTranslate2 modes the GPU
actually supports and automatically retries transcription on CPU when a CUDA
driver or GPU cannot run float16 efficiently.

The fallback is safe but can be slower than GPU transcription. The source video
is not modified.

## Waveform Is Unavailable for a Long Stream

Update to ScriptCut 0.1.1 or newer. Earlier builds downloaded the complete media
file into the interface and asked the browser audio decoder to hold it in
memory. Current builds generate a compact waveform through bundled FFmpeg, so
multi-hour streams do not require multi-gigabyte browser buffers.

If the waveform still cannot be generated because the file has no decodable
audio track, editing and transcription remain available. Open the job log if
transcription itself also fails.

## Backend Will Not Start

Run:

```bash
npm run dev:backend
```

Then check:

```bash
curl -s http://127.0.0.1:8642/health
```

Expected response:

```json
{"status":"ok"}
```

## AI Features Do Not Work

Local AI features require Ollama to be running, or a configured cloud provider key in Settings.

```bash
ollama list
```

Cloud providers require valid API keys. ScriptCut keeps provider settings local.

### Grok/OpenAI says the API key is incorrect

Update to ScriptCut 0.1.2 or newer, then:

1. Open **More → Settings**.
2. Select the provider that should be used by AI Editor.
3. Enter its API key and model.
4. Click **Test connection**.

Only the selected provider is used. Saving both an OpenAI key and an xAI key
does not send the same request to both providers.

The connection test reads the models available to the key. It does not send
transcript text and does not use completion tokens. If xAI reports an incorrect
key, the request reached xAI but was rejected before model processing, so it may
not appear as billable usage. xAI keys also need access to the Models and Chat
endpoints and to the selected model.

A ChatGPT Plus/Pro subscription and OpenAI API billing are separate. Create an
API key in the OpenAI API platform and make sure the API account has billing or
credits available.

### WhisperX or another transcription engine does not download

Update to ScriptCut 0.1.2 or newer. The desktop build includes Faster Whisper
and disables optional engines that are not installed. WhisperX is a separate
program dependency; downloading a `medium` model by itself cannot install it.

For the normal Windows build choose **Faster Whisper** and then `base`, `small`,
or `medium`. The selected speech model downloads automatically on the first
transcription, so no manual model installation is required. The first run can
remain on the model-loading message while the download finishes.

## Background Removal Is Disabled

Background removal requires optional Python packages such as MediaPipe and OpenCV. Check availability in the export panel or by running:

```bash
curl -s http://127.0.0.1:8642/background/capabilities
```
