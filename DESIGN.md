---
name: ScriptCut
description: A transcript-first, local media editor built as a precise film-lab contact sheet.
colors:
  editor-bg: "#0b0d0c"
  editor-panel: "#101311"
  editor-surface: "#171a18"
  editor-border: "#2b302d"
  editor-accent: "#71d9b0"
  editor-accent-hover: "#8ee6c2"
  editor-accent-ink: "#08110d"
  editor-text: "#f3f5f3"
  editor-text-muted: "#a6aea8"
  editor-paper: "#f4f4ef"
  editor-paper-soft: "#e9ebe6"
  editor-ink: "#111411"
  editor-ink-muted: "#677069"
  editor-danger: "#ff716d"
  editor-success: "#71d9b0"
  editor-warning: "#e7bd63"
  editor-word-hover: "rgba(35, 128, 91, 0.10)"
  editor-word-selected: "rgba(35, 128, 91, 0.22)"
  editor-word-deleted: "rgba(193, 57, 54, 0.14)"
  editor-word-filler: "rgba(174, 119, 24, 0.18)"
  transcript-rule: "#d7dad5"
  paper-signal: "#176b4c"
  paper-signal-rule: "#23805b"
  paper-danger: "#a02f2c"
  paper-warning: "#855d11"
  paper-placeholder: "#7d867f"
  timeline-rule: "#252a27"
  waveform: "#69716b"
typography:
  headline:
    fontFamily: "Onest Variable, Onest, Segoe UI Variable, Segoe UI, ui-sans-serif, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 500
    lineHeight: "normal"
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Onest Variable, Onest, Segoe UI Variable, Segoe UI, ui-sans-serif, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: "1.25rem"
    letterSpacing: "-0.02em"
  transcript:
    fontFamily: "Onest Variable, Onest, Segoe UI Variable, Segoe UI, ui-sans-serif, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: "1.5rem"
    letterSpacing: "normal"
  body:
    fontFamily: "Onest Variable, Onest, Segoe UI Variable, Segoe UI, ui-sans-serif, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: "1rem"
    letterSpacing: "normal"
  label:
    fontFamily: "Onest Variable, Onest, Segoe UI Variable, Segoe UI, ui-sans-serif, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: "1rem"
    letterSpacing: "normal"
  mono:
    fontFamily: "SFMono-Regular, Cascadia Mono, Consolas, monospace"
    fontSize: "0.625rem"
    fontWeight: 400
    lineHeight: "normal"
    letterSpacing: "normal"
rounded:
  default: "4px"
  md: "6px"
  lg: "8px"
  full: "9999px"
spacing:
  "0.5": "2px"
  "1": "4px"
  "1.5": "6px"
  "2": "8px"
  "2.5": "10px"
  "3": "12px"
  "4": "16px"
  "5": "20px"
components:
  button-primary:
    backgroundColor: "{colors.editor-accent}"
    textColor: "{colors.editor-accent-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.default}"
    padding: "0 12px"
    height: "32px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.editor-text-muted}"
    typography: "{typography.body}"
    rounded: "{rounded.default}"
    padding: "0 12px"
    height: "32px"
  input-search:
    backgroundColor: "{colors.editor-paper-soft}"
    textColor: "{colors.editor-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.default}"
    padding: "4px 8px"
    height: "26px"
  word-handle-selected:
    backgroundColor: "{colors.editor-word-selected}"
    textColor: "{colors.editor-ink}"
    typography: "{typography.transcript}"
    rounded: "{rounded.default}"
    padding: "2px 4px"
  tab-review-active:
    backgroundColor: "transparent"
    textColor: "{colors.editor-accent}"
    typography: "{typography.body}"
    rounded: "0"
    padding: "10px 12px"
  segmented-option-active:
    backgroundColor: "rgba(113, 217, 176, 0.15)"
    textColor: "{colors.editor-accent}"
    typography: "{typography.label}"
    rounded: "{rounded.default}"
    padding: "8px"
  transcript-row:
    backgroundColor: "{colors.editor-paper}"
    textColor: "{colors.editor-ink}"
    typography: "{typography.transcript}"
    rounded: "0"
    padding: "12px 16px"
  review-row:
    backgroundColor: "{colors.editor-panel}"
    textColor: "{colors.editor-text}"
    typography: "{typography.body}"
    rounded: "0"
    padding: "12px 16px"
  video-control-primary:
    backgroundColor: "{colors.editor-paper}"
    textColor: "{colors.editor-ink}"
    rounded: "{rounded.default}"
    size: "32px"
    height: "32px"
    width: "32px"
---

# Design System: ScriptCut

## Overview

**Creative North Star: "The Transcript Contact Sheet"**

ScriptCut treats a long recording like a film lab treats a contact sheet: the black media stage holds the source, while a continuous Working Paper transcript exposes every usable moment as editable evidence. The result is editorial, precise, local-first, and calm under long-form workload. It refuses the dense timeline-first editor wall; words are the primary handles of the video, and the waveform is their instrument of verification.

The visual world is built from Projection Black, Working Paper, Graphite Rule, and one Live Mint signal. Surfaces remain flat and tool-like. Hairlines, tonal fields, exact alignment, and tightly controlled type establish hierarchy; color and motion appear only when they communicate live position, selection, review, acceptance, or risk.

**Key Characteristics:**

- A black media stage beside a dominant, continuous paper transcript.
- Dense but breathable editorial typography led by Onest and measured by compact monospace metadata.
- Graphite hairlines and tonal fields instead of decorative cards or ambient elevation.
- One mint live signal connecting transcript selection, playhead, accepted action, and primary export.
- Reversible, reviewable controls that expose state without turning the editor into a dashboard.

## Colors

The palette behaves like a dark projection room wrapped around a marked-up paper transcript: near-neutrals carry structure, while mint is scarce enough to remain meaningful.

### Primary

- **Live Mint** (`editor-accent`, #71d9b0): primary export, active review tabs, selected timeline spans, progress, focus, and accepted states.
- **Live Mint Hover** (`editor-accent-hover`, #8ee6c2): hover response for solid mint actions.
- **Paper Signal** (`paper-signal`, #176b4c): accessible mint-derived text on Working Paper.
- **Paper Signal Rule** (`paper-signal-rule`, #23805b): the inset edge on an active transcript row.

### Neutral

- **Projection Black** (`editor-bg`, #0b0d0c): application shell and video-stage ground.
- **Workbench Black** (`editor-panel`, #101311): persistent review and waveform surfaces.
- **Graphite Surface** (`editor-surface`, #171a18): dark fields, menus, and quiet control fills.
- **Graphite Rule** (`editor-border`, #2b302d): primary dark-surface dividers and control strokes.
- **Working Paper** (`editor-paper`, #f4f4ef): the continuous transcript canvas and light primary video control.
- **Soft Paper** (`editor-paper-soft`, #e9ebe6): search and selected-action fields inside the transcript.
- **Transcript Rule** (`transcript-rule`, #d7dad5): row boundaries on Working Paper.
- **Projection Text** (`editor-text`, #f3f5f3) and **Projection Muted** (`editor-text-muted`, #a6aea8): dark-surface foreground hierarchy.
- **Carbon Ink** (`editor-ink`, #111411), **Graphite Ink** (`editor-ink-muted`, #677069), and **Paper Placeholder** (`paper-placeholder`, #7d867f): transcript foreground hierarchy.
- **Timeline Rule** (`timeline-rule`, #252a27) and **Waveform Graphite** (`waveform`, #69716b): precision lanes, ticks, and audio amplitude.

### Functional

- **Cut Red** (`editor-danger`, #ff716d) and **Paper Cut Red** (`paper-danger`, #a02f2c): deletions, low confidence, errors, and destructive review.
- **Review Amber** (`editor-warning`, #e7bd63) and **Paper Review Amber** (`paper-warning`, #855d11): room tone, uncertainty, and warnings.
- **Accepted Mint** (`editor-success`, #71d9b0): confirmed, complete, or applied status.

### State Washes

- **Word Hover** (`editor-word-hover`, rgba(35, 128, 91, 0.10)): the lightest paper interaction wash.
- **Word Selected** (`editor-word-selected`, rgba(35, 128, 91, 0.22)): the stronger selected-word fill.
- **Word Deleted** (`editor-word-deleted`, rgba(193, 57, 54, 0.14)): reversible deletion history.
- **Word Filler** (`editor-word-filler`, rgba(174, 119, 24, 0.18)): reviewable filler or hesitation state.

**The One Live Signal Rule.** Live Mint is reserved for present position, selection, acceptance, focus, and the primary terminal action; it does not decorate passive surfaces.

## Typography

**Display Font:** Onest Variable (with Onest, Segoe UI Variable, Segoe UI, and system sans-serif fallbacks)  
**Body Font:** Onest Variable (with the same fallbacks)  
**Label/Mono Font:** SFMono-Regular (with Cascadia Mono, Consolas, and monospace fallbacks)

**Character:** Onest keeps dense Russian and mixed-language editing copy contemporary and open without feeling consumer-soft. Monospace is strictly instrumental: timecodes, confidence, duration, coordinates, and ruler labels.

### Hierarchy

- **Headline** (500, 1.35rem, normal): the Smart Transcript heading; the single largest operational title.
- **Title** (600, 0.875rem, 1.25rem): product identity and compact region titles.
- **Transcript** (400, 0.8125rem, 1.5rem): the editable word stream, with generous line-height for targeting individual words.
- **Body** (400, 0.75rem, 1rem): controls, review explanations, buttons, and workbench copy.
- **Label** (500, 0.6875rem, 1rem): compact field labels and review metadata.
- **Mono** (400, 0.625rem, normal): timestamps, confidence values, timeline ticks, and numeric status.

**The Working Copy Rule.** Transcript text may breathe; interface text stays compact. Do not enlarge controls to compete with the words being edited.

## Layout

The editor is a fixed-height desktop workbench. A compact command bar (56px) spans the top. Below it, a narrow media dock occupies 34% of the main lane with a 320px minimum and 520px maximum; the transcript takes all remaining central width. The review workbench is a fixed 360px right rail, and the precision waveform forms a 192px lower lane beneath media and transcript.

Spacing follows the implemented 2, 4, 6, 8, 10, 12, 16, and 20px rhythm. The transcript rows use a stable three-column measure—60px timecode, fluid words, 48px confidence—with 12px gaps and 12px by 16px row padding. Major regions meet edge-to-edge so the largest light field reads as one continuous sheet, not a stack of cards.

At 1180px and below, the review workbench becomes a right overlay at `min(390px, 44vw)` and the media dock becomes 38% wide with a 300px minimum. At 860px and below, the workbench becomes `min(430px, 58vw)` and the media dock becomes 42% wide with a 250px minimum. Compact metadata begins hiding at the 640px utility breakpoint. At 1280px and above, the AI workbench opens by default.

**The Transcript Dominance Rule.** Preserve a legible media check and a usable waveform, but give the continuous transcript the largest uninterrupted working field.

## Elevation & Depth

The system is flat and structural at rest. Depth comes from Projection Black against Working Paper, small tonal steps between dark surfaces, and 1px rules. Shadows are limited to transient overlays: the narrow-width workbench casts a directional shadow back into the editor, the more-tools menu uses the framework's extra-large floating shadow, and the reframe preview uses an oversized mask shadow to dim excluded media.

### Shadow Vocabulary

- **Workbench Overlay** (`-24px 0 48px rgba(0, 0, 0, 0.32)`): separates the review rail only when it overlays the workspace below 1180px.
- **Menu Float** (`0 20px 25px -5px rgb(0 0 0 / 0.10), 0 8px 10px -6px rgb(0 0 0 / 0.10)`): applies only to the transient more-tools menu.
- **Reframe Mask** (`0 0 0 9999px rgba(0, 0, 0, 0.28)`): dims media outside a vertical or square safe frame; it is a viewport tool, not surface elevation.

**The Flat-by-Default Rule.** A persistent editor region never earns depth from a decorative shadow; use a hairline or a tonal field unless the surface is temporarily overlaying another one.

## Shapes

The form language is predominantly rectilinear. Workspace regions, transcript rows, review rows, and timeline lanes have square corners and meet on graphite hairlines. Small interactive targets use restrained 4px corners; compact menus use 6px corners; only larger first-run actions reach 8px. Circular geometry is reserved for playhead knobs, checkboxes, and other genuinely radial indicators.

Word handles use a 3px corner in the shipped stylesheet, just softer than the surrounding paper grid. This slight rounding helps each word read as a manipulable handle without turning the transcript into a cloud of pills.

**The Structural Edge Rule.** Round the control, not the canvas: never put the transcript, media stage, workbench, or timeline inside large-radius cards.

## Components

Components are restrained, reviewable, and tool-like. Their states are carried by tone, a precise border, and sparse mint—not by ornamental depth.

### Buttons

- **Shape:** compact controls use restrained corners (4px); the topbar action height is 32px with 12px horizontal padding.
- **Primary:** Live Mint with Accent Ink, used for Export and confirmed batch actions.
- **Hover / Focus:** solid mint actions shift to Live Mint Hover; every keyboard focus uses a 2px Live Mint outline with a 2px offset. Pressed state stays flat.
- **Ghost:** transparent with Projection Muted text; hover introduces Graphite Surface and Projection Text.
- **Icon Control:** 32px square. The video play control inverts to Working Paper and Carbon Ink; active editing tools use a low-opacity mint field.

### Chips

- **Style:** word handles are text-sized chips only during interaction, with 3px corners, 2px by 4px padding, and a transparent border at rest.
- **State:** hover adds the faintest green rule; selection uses Word Selected; active playback uses a lighter mint wash; deletion remains visible through Cut Red wash and strike-through.

### Cards / Containers

- **Corner Style:** persistent rows remain square; only bounded status blocks and transient controls use 4–8px corners.
- **Background:** review rows stay on Workbench Black; bounded secondary fields may use Graphite Surface. Transcript rows stay on Working Paper or a mint active wash.
- **Shadow Strategy:** none at rest; see Elevation & Depth for overlay-only exceptions.
- **Border:** 1px Graphite Rule on dark surfaces or Transcript Rule on paper.
- **Internal Padding:** review and transcript rows use 12px by 16px; compact field groups use 8–12px.

### Inputs / Fields

- **Style:** 1px structural stroke, 4px corners, compact 4–8px padding, and a tonal fill appropriate to the material: Soft Paper in the transcript, Graphite Surface in the workbench.
- **Focus:** border shifts to Live Mint; the global keyboard focus outline remains visible.
- **Error / Disabled:** errors use Cut Red text with a translucent red field; disabled controls remain present at 40–50% opacity and keep their label.

### Navigation

The command bar is a single 56px black strip with ScriptCut identity and project state left, then open/save, undo/redo, AI, export, and overflow actions right. Review tabs divide the workbench evenly; the active tab uses mint text and a 2px bottom rule, while inactive tabs remain muted and borderless. Below 1180px the workbench navigation moves with the overlay rather than collapsing into a second navigation system.

### Transcript Row

Each row is a three-column editorial record: monospace timecode, a fluid word stream, and monospace confidence. Rows are divided by a Transcript Rule; the active row receives a pale mint wash and a 3px Paper Signal Rule on the left. Search, selection, edits, and low confidence remain independently legible at word level.

### Review Row

Review rows use full-width hairline-separated bands, not stacked cards. They lead with the matched text, then time/source/confidence metadata, an explicit applied state, and paired Verify/Apply actions. Suggestions never look applied until the creator confirms them.

### Waveform Timeline

The lower lane combines a compact label/control header, ruler, waveform, edit-event lane, and marker lane. Graphite amplitude is neutral; mint selection and playhead, Cut Red deletion or low confidence, and Review Amber room tone line up precisely with transcript time.

Motion is terse: common color and progress transitions use 150ms standard easing; the workbench enters in 180ms with a 14px horizontal settle and `cubic-bezier(0.16, 1, 0.3, 1)`. All animation and transition durations collapse under reduced-motion preference.

## Do's and Don'ts

### Do:

- **Do** keep Working Paper as the largest light field and the transcript as the primary editing surface.
- **Do** align selected words, active transcript rows, waveform ranges, and the playhead through the same Live Mint signal.
- **Do** use 1px rules and tonal shifts to explain region boundaries before reaching for elevation.
- **Do** keep timestamps, confidence, duration, and ruler labels in compact monospace.
- **Do** show review, applied, deleted, warning, disabled, and low-confidence states with text or shape as well as color.
- **Do** preserve a visible 2px Live Mint keyboard focus outline and reduced-motion behavior.

### Don't:

- **Don't** turn the workspace into a grid of floating rounded cards.
- **Don't** use Live Mint as decorative fill on passive regions or for unrelated secondary actions.
- **Don't** replace the continuous transcript with a conventional timeline-first editing wall.
- **Don't** hide deletions, censorship, AI suggestions, or confidence behind invisible automatic state.
- **Don't** introduce gradients, ambient shadows, glass effects, or oversized display typography into the operational editor.
- **Don't** let responsive behavior collapse the transcript merely to keep the review workbench permanently docked.
