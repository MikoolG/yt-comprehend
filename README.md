# YT-Comprehend

Tiered video comprehension platform for extracting content from online videos and feeding it to LLMs.

## Quick Start

```bash
# Install
pip install -e .

# Basic usage - extracts transcript and saves to output folder
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"

# Force specific tier
yt-comprehend URL --tier 1  # Captions only (instant)
yt-comprehend URL --tier 2  # Audio transcription (Whisper)
yt-comprehend URL --tier 3  # Full visual analysis

# Auto-summarize via LLM API after extraction
yt-comprehend URL --summarize               # Uses default provider (Gemini)
yt-comprehend URL -s --provider openai      # Use OpenAI instead
yt-comprehend URL -s --provider anthropic   # Use Anthropic
yt-comprehend URL -s --api-key KEY          # Pass API key directly

# Output options
yt-comprehend URL --no-save        # Print to stdout only, don't save
yt-comprehend URL -o transcript.md # Save to specific file
yt-comprehend URL --quiet          # Save only, no stdout

# Different output formats
yt-comprehend URL --format plain   # Just text
yt-comprehend URL --format json    # Structured data

# Whisper options
yt-comprehend URL --tier 2 --model large-v3-turbo --device cuda
```

## Output Structure

By default, transcripts are saved to the output directory organized by tier:

```
output/
├── tier1-captions/
│   ├── transcripts/    # Raw transcripts with timestamps
│   │   └── video-title.md
│   └── summaries/      # LLM-generated summaries
│       └── video-title.md
├── tier2-whisper/
│   ├── transcripts/
│   └── summaries/
└── tier3-visual/
    ├── transcripts/
    └── summaries/
```

## Summarization

Two modes for generating summaries from transcripts:

### API Mode (automated)

Extracts transcript and auto-summarizes in one step using an LLM API:

```bash
yt-comprehend URL --summarize  # Gemini by default
```

Supports multiple providers: **Gemini** (default), **OpenAI**, and **Anthropic**.

API key setup (pick one):
- `.env` file in project root: `GEMINI_API_KEY=your-key` (or `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Environment variable in your shell
- `config.yaml` under `summarize.api_key`
- CLI flag: `--api-key KEY`

### Claude Mode (interactive)

Use Claude Code in the embedded terminal for interactive summarization:

1. **Extract transcript**: `yt-comprehend URL --tier 1`
2. **Claude summarizes**: Claude Code reads the transcript and creates a comprehensive summary
3. **Both saved**: Transcripts and summaries go to respective folders

## Desktop UI

A graphical interface built with Electron for a streamlined workflow.

### Quick Start

```bash
cd electron
npm install
npm run dev      # Development mode with hot reload
npm run build    # Production build
```

### Tech Stack

- **Framework**: Electron 33+ with electron-vite
- **Frontend**: React 18 + TypeScript + Tailwind CSS
- **Editor**: Monaco Editor (VS Code's editor)
- **Terminal**: xterm.js with node-pty
- **State**: Zustand
- **Layout**: react-resizable-panels

### Features

- **Video URL input** with paste button and tier selection dropdown
- **Claude/API toggle** - switch between Claude CLI and automated LLM API summarization
- **Progress bar** showing real-time extraction and summarization status via JSON events
- **File browser** for output transcripts and summaries (auto-refreshes)
- **Monaco Editor** for viewing and editing markdown files with syntax highlighting
- **Embedded terminal** with venv activated for running Claude CLI
- **Settings panel** for configuring provider, API key, model, and other options
- **Resizable panels** - drag to resize editor and terminal areas
- **Right-click context menu** for cut/copy/paste

### Keyboard Shortcuts

- `Ctrl+Enter`: Execute transcript generation
- `Ctrl+S`: Save current file in editor

### Screenshot

```
+----------------------------------------------------------+
| [URL: ________________] [📋] [Tier: v] [Execute] [⚙️]     |
+----------------------------------------------------------+
| [████████████░░░░░░░░] Transcribing with Whisper... 60%  |
+------------+---------------------------------------------+
| output/    |  # Video Analysis                          |
|  tier1-    |                                             |
|   trans/   |  **Source:** https://youtube.com/...       |
|   summa/   |  **Method:** Whisper Transcription         |
|  tier2-    |  ...                                       |
+------------+---------------------------------------------+
| Terminal          [Claude|API]                    [↻]    |
| $ claude                                                 |
+----------------------------------------------------------+
```

## Tiers

| Tier | Method | Speed | When to Use |
|------|--------|-------|-------------|
| 1 | YouTube Captions | Instant | Most videos, quick analysis |
| 2 | faster-whisper | ~2× realtime | No captions, accuracy-critical |
| 3 | Visual + Audio | Minutes | Slides, code, diagrams |

## Python API

```python
from src.comprehend import VideoComprehend

vc = VideoComprehend()
result = vc.analyze("https://youtube.com/watch?v=VIDEO_ID")

print(result.transcript_text)  # Full transcript
print(result.to_markdown())    # Formatted for LLM
```

## Setup

See [docs/SETUP.md](docs/SETUP.md) for detailed installation and configuration instructions.

## Requirements

- Python 3.10+
- ffmpeg
- Deno (for yt-dlp YouTube support)

For Tier 3 visual analysis:
```bash
pip install -e ".[visual]"
```
