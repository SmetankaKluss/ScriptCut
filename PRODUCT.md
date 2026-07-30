# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Primary: Russian-speaking Twitch streamers and their friends who turn long conversational VODs into compilations and vertical clips without learning a traditional timeline editor.
- Secondary: creators who want a local-first, transcript-led workflow for YouTube Shorts, TikTok, Reels, podcasts, and social publishing.
- Inferred from the supplied brief and current repository: users may be non-technical and should not need to understand Python, FFmpeg, speech-model installation, or API billing to complete a first edit.

## Product Purpose

ScriptCut turns a local video into a word-timed transcript, lets the creator edit the recording by editing words, proposes topic-based cuts, detects speech that should be censored, and exports creator-ready videos and social packages. Success means a creator can go from a long VOD to a reviewable edit quickly while retaining manual control before destructive-looking changes are applied.

## Positioning

ScriptCut is a creator-owned, local-first editor where transcript, AI suggestions, profanity review, captions, clip packaging, and video export stay inside one reversible desktop workflow. AI is optional; the core edit and export path remains usable without a paid cloud provider.

## Operating Context

- The main workflow starts after a Twitch or conversational stream has ended and a local recording is available.
- Creators work on Windows 10/11 x64 or macOS, often with long media files and consumer hardware.
- Transcription models may download on first use; packaged builds include the local backend and FFmpeg.
- Topic edits, filler removal, profanity censorship, caption styling, vertical reframing, and export are reviewed in the desktop editor.
- Original media remains local. Transcript text leaves the device only when the user deliberately invokes a cloud AI provider.

## Capabilities and Constraints

- Word-level transcription, waveform, transcript editing, undo/redo, non-destructive edit operations, preview, autosave, recovery, and project files.
- Russian profanity and custom-phrase censorship with bleep, silence, or room tone.
- Optional local and cloud AI providers, including a Codex/ChatGPT-plan integration.
- Creator exports for source, Shorts, TikTok/Reels, and square podcast formats, with captions and social packaging.
- macOS Apple Silicon and Windows 10/11 x64 are the verified desktop targets; browser mode is for development.
- Long recordings must be processed with bounded memory and understandable progress, cancellation, retry, and recovery.
- Inferred constraint: defaults must favor reliable Russian transcription and censorship over the smallest download, while exposing a faster low-resource mode.

## Brand Commitments

- Product name: ScriptCut.
- Voice: direct, practical, creator-friendly, and non-judgmental. Error states explain what happened and the next action without blaming the user.
- Existing ScriptCut mark and wordmark remain recognizable.
- The application is open source and local-first.
- Visual direction for this redesign was delegated by the user. The selected external reference is Runway's media-centric design-system analysis from getdesign.md, adapted for an operational desktop editor rather than copied as a marketing page.

## Evidence on Hand

- Working React/Electron/FastAPI application and smoke suites in this repository.
- Existing ScriptCut wordmark and mark under `frontend/public/brand/`.
- Creator workflow documentation under `docs/`.
- No approved customer testimonials, benchmark corpus, measured transcription-accuracy claim, or licensed product photography is present; future surfaces must not fabricate them.

## Product Principles

1. Show the media, transcript, and current edit state before secondary controls.
2. Propose edits automatically, but require review and make every change reversible.
3. Pick a trustworthy local default; hide model plumbing until a creator asks for it.
4. Explain long-running work in plain language with progress, cancellation, and recovery.
5. Treat censorship as an assisted review workflow, never as an infallible automatic judgment.

## Accessibility & Inclusion

- Maintain keyboard-first editing, visible focus states, readable contrast, and non-color status cues.
- Primary controls must remain usable at common laptop widths on both macOS and Windows.
- Russian creator copy and mixed Russian/English technical terms must not break layout.
- Motion must respect reduced-motion preferences.
