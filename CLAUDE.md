# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Setup

```bash
source venv/bin/activate
export PATH="$HOME/.deno/bin:$PATH"
```

## Project Overview

YT-Comprehend is a tiered video comprehension system for extracting content from YouTube videos for LLM consumption. It operates in three tiers of increasing depth:

- **Tier 1 (Captions)**: YouTube transcript API - instant, works for most videos
- **Tier 2 (Audio)**: yt-dlp + faster-whisper transcription - more accurate, ~2× realtime
- **Tier 3 (Visual)**: Scene detection + OCR + frame analysis - for slides, code, diagrams

## Build/Install

```bash
pip install -e .              # Development install
pip install -e ".[visual]"    # With Tier 3 deps
pip install -e ".[dev]"       # With pytest, black, ruff
```

## Lint/Format

```bash
ruff check src/
black src/
```

## CLI Usage

```bash
yt-comprehend URL                    # Auto-selects best tier, saves to output/
yt-comprehend URL --tier 2           # Force Whisper transcription
yt-comprehend URL --tier 2 --model large-v3-turbo --device cuda
yt-comprehend URL --no-save          # Print to stdout only
yt-comprehend URL --quiet            # Save only, no stdout output
yt-comprehend URL -o out.md          # Save to specific file
yt-comprehend URL --json-progress    # JSON progress events for UI integration
```

## Desktop UI

The project includes an Electron-based desktop UI for a graphical workflow.

### Setup & Run

```bash
cd electron
npm install              # Install dependencies
npm run dev              # Development mode with hot reload
npm run build            # Build for production
```

### UI Features

- **Video URL input**: Enter/paste YouTube URLs
- **Tier selection**: Choose between Tier 1 (Captions) and Tier 2 (Whisper)
- **Execute button**: Start transcript generation with progress indicator
- **File browser**: View output files (transcripts and summaries)
- **Monaco Editor**: View and edit markdown files with syntax highlighting
- **Embedded terminal**: Run Claude CLI and other commands

### UI Workflow

1. Enter a YouTube URL in the input field
2. Select the tier (1 for fast captions, 2 for Whisper transcription)
3. Click "Execute" to generate the transcript
4. View the generated file in the editor panel
5. Use the embedded terminal to run Claude CLI for summarization:
   ```bash
   claude   # Start Claude CLI in the terminal
   ```

### Keyboard Shortcuts

- `Ctrl+Enter`: Execute transcript generation
- `Ctrl+S`: Save current file

## Output Structure

Transcripts are saved by default to the output directory:

```
output/
├── tier1-captions/
│   ├── transcripts/     # Raw transcripts with timestamps
│   └── summaries/       # Claude Code generated summaries
├── tier2-whisper/
│   ├── transcripts/
│   └── summaries/
└── tier3-visual/
    ├── transcripts/
    └── summaries/
```

## Video Comprehension Workflow

When asked to analyze a YouTube video:

1. **Extract transcript** using the CLI:
   ```bash
   yt-comprehend "URL" --tier 1 --quiet   # Fast, captions
   yt-comprehend "URL" --tier 2 --quiet   # Accurate, Whisper
   ```

2. **Read the saved transcript** from `output/<tier>/transcripts/<video-name>.md`

3. **Generate comprehensive summary** including:
   - Overview (what the video is about, target audience)
   - Key points and takeaways
   - Detailed breakdown by topic/section
   - Notable mentions (tools, people, resources)
   - Final summary

4. **Save the summary** to `output/<tier>/summaries/<video-name>.md`

## Architecture

### Python Backend

- **`src/cli.py`**: CLI entry point, handles arguments and output saving
- **`src/comprehend.py`**: `VideoComprehend` orchestrates tiers, auto-escalates on failure, returns `ComprehendResult`
- **`src/extractors/captions.py`**: Tier 1 - uses `youtube-transcript-api` v1.x (`.list()` / `.fetch()`)
- **`src/extractors/audio.py`**: Tier 2 - yt-dlp download + faster-whisper (lazy-loaded model)
- **`src/extractors/visual.py`**: Tier 3 - scene detection → frame extraction → dedup → OCR
- **`config.yaml`**: Default settings for whisper, visual, output directory. CLI options override.

### Electron UI

**Tech Stack:**
- Electron 33+ with electron-vite bundler
- React 18 + TypeScript
- Tailwind CSS for styling
- Zustand for state management
- Monaco Editor (local bundle, not CDN)
- xterm.js + node-pty for terminal
- react-resizable-panels for layout
- react-arborist for file tree
- chokidar for file watching

**Main Process (`electron/src/main/`):**
- `index.ts`: Window management, app lifecycle, context menu
- `ipc/file-service.ts`: File reading, writing, watching with chokidar
- `ipc/terminal-service.ts`: PTY terminal management (node-pty)
- `ipc/process-service.ts`: Spawn yt-comprehend CLI with JSON progress
- `ipc/config-service.ts`: Read/write config.yaml

**Preload (`electron/src/preload/`):**
- `index.ts`: Secure IPC bridge via contextBridge

**Renderer (`electron/src/renderer/`):**
- `main.tsx`: Entry point, Monaco worker configuration
- `App.tsx`: Main layout with resizable panels
- `stores/app-store.ts`: Zustand state management
- `components/Header.tsx`: URL input, tier selector, execute button
- `components/FileTree.tsx`: Output directory browser with dynamic height
- `components/Editor.tsx`: Monaco editor for markdown files
- `components/Terminal.tsx`: xterm.js terminal with scrollback
- `components/ProgressPanel.tsx`: Progress bar and status messages
- `components/Settings.tsx`: Configuration modal

## Notes

- `youtube-transcript-api` v1.x API: use `api.list(video_id)` not `api.list_transcripts()`
- System deps: ffmpeg, deno (required by yt-dlp for YouTube as of 2025)
- Tier 3 requires `[visual]` extra for scenedetect, paddleocr, imagededup
- Output directory can be configured in `config.yaml` under `output.directory`
