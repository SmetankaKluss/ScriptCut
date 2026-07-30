---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: ["frontend/src/components/TranscriptEditor.tsx","frontend/src/components/WaveformTimeline.tsx","frontend/src/components/AIPanel.tsx","frontend/src/components/SettingsPanel.tsx","frontend/src/components/ExportDialog.tsx"]
---

# ScriptCut editor surface

- Mode: Operate.
- Scope: opening state, active editing workspace, transcript, review queue, timeline, settings/export sheets.
- Audience: Russian-speaking streamers editing long VODs on Windows and macOS, often without professional editor knowledge.
- Job: open media, understand transcription progress, edit from words, review suggested cuts/profanity, preview, and export.
- Primary action: make a reversible transcript edit; terminal action: export.
- Direction: editorial film contact sheet adapted from the Runway design analysis. The media stage is black, the transcript is a continuous paper-white working surface, state is communicated by hairlines, typography, and one mint signal.
- Approved comp: `.impeccable/mocks/scriptcut-editor-b-approved.png`.
- Memorable moment: selecting a word synchronously illuminates the transcript row and the exact corresponding waveform range; censorship remains a visible review item instead of an invisible automatic mutation.
- Constraints: preserve all existing capabilities, keyboard use, Russian/English copy, laptop widths, reduced motion, Electron desktop behavior, and test hooks.

## Implementation inventory

| Visible ingredient | Commitment | Medium |
| --- | --- | --- |
| Compact top command bar | Project identity/status left; undo, AI, export right; one mint primary action | Semantic React + CSS |
| Black video preview dock | Familiar playback controls, no ornamental frame | Existing `VideoPlayer` + CSS |
| Continuous white transcript canvas | Transcript is the largest light field; timestamps and confidence are quiet metadata; deletions remain legible | Existing `TranscriptEditor` + semantic React/CSS |
| Review queue | AI, profanity, and export tools open in a persistent right workbench without stacked decorative cards | Existing panels in a shared workbench shell |
| Precision waveform | Full-width lower lane with selection, cuts, bleep and current-time signals | Existing canvas + CSS |
| Hairline topology | Regions meet through 1px rules and tonal shifts, not shadows | CSS tokens |
| Mint signal | Active word, playhead, accepted action, and primary export only | CSS tokens |
| ScriptCut brand | Existing mark/wordmark retained, rendered monochrome where required | Existing SVG assets |
| Responsive laptop layout | Right workbench becomes overlay below 1180px; transcript/video remain usable | React state + CSS media queries |
| Motion | One coordinated panel/selection transition, disabled for reduced motion | CSS |

## Do not literalize from the comp

- Do not invent media metadata, confidence benchmarks, or automatic apply behavior.
- Do not create permanently visible controls for features that are currently modal/sheet actions.
- Do not rasterize transcript text, waveform, controls, or media.
- Do not copy the comp's English-only labels; product copy should stay creator-friendly and may remain mixed-language until localization is complete.
