# YT-Comprehend

Tiered video comprehension platform for extracting content from online videos and feeding it to LLMs.

## Quick Start

```bash
# Install
pip install -e .

# Basic usage - extracts transcript and saves to output folder
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"

# Force specific tier
yt-comprehend URL --tier 1       # Captions only (instant; yt-dlp fallback if blocked)
yt-comprehend URL --tier 2       # Audio transcription (Whisper)
yt-comprehend URL --tier 3       # Full visual analysis
yt-comprehend URL --tier gemini  # Send URL straight to Gemini (no download, free tier)

# Auto-summarize via LLM API after extraction (free-first)
yt-comprehend URL --summarize                 # Default provider (Gemini free tier)
yt-comprehend URL -s --provider openrouter    # OpenRouter free models
yt-comprehend URL -s --provider ollama        # Local Ollama (private, unlimited)
yt-comprehend URL -s --provider openai        # OpenAI (paid)
yt-comprehend URL -s --provider anthropic     # Anthropic (paid)
yt-comprehend URL -s --api-key KEY            # Pass API key directly

# Tier 2 cloud transcription (free Groq Whisper API, needs GROQ_API_KEY)
yt-comprehend URL --tier 2 --whisper-backend groq

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
├── tier3-visual/
│   ├── transcripts/
│   └── summaries/
└── gemini-direct/
    ├── transcripts/
    └── summaries/
```

## Agent / LLM Usage (no MCP required)

yt-comprehend is designed to be driven by LLMs as a plain terminal command:

```bash
yt-comprehend "URL_OR_VIDEO_ID" --llm
```

`--llm` is a one-shot agent contract:
- stdout carries **only the summary markdown** (or the transcript if summarization fails) - safe to read/pipe directly
- progress and warnings go to stderr
- transcript + summary are still saved under `output/`
- captions tier by default with automatic fallbacks (yt-dlp subtitles → Whisper); Gemini free tier summarization with free-model fallback
- the project `.env` is auto-loaded, so API keys work from any terminal

Escalate only when needed: `--llm --tier 2` (Whisper) or `--llm --tier gemini`
(zero-download video understanding), and switch summarizers with `--provider`.

For Claude Code specifically, the repo ships a skill at
`.claude/skills/yt-comprehend/SKILL.md` - copy it to `~/.claude/skills/` to make
any session recognize YouTube links and yt-comprehend mentions globally. A thin
wrapper script in `~/.local/bin` (calling `<repo>/venv/bin/yt-comprehend`) makes
the command available system-wide.

## Summarization

Two modes for generating summaries from transcripts:

### API Mode (automated)

Extracts transcript and auto-summarizes in one step using an LLM API:

```bash
yt-comprehend URL --summarize  # Gemini by default
```

Supported providers (free-first):
- **Gemini** (default) - free tier, 1M-token context handles very long transcripts in one shot;
  automatically falls back across free models (`gemini-flash-latest` → `gemini-2.5-flash` →
  `gemini-2.5-flash-lite`) on overload/rate-limit
- **OpenRouter** - rotating catalog of free models (`openrouter/free` auto-router)
- **Ollama** - fully local and private via `http://localhost:11434` (try `gemma3` or `qwen3`)
- **OpenAI** and **Anthropic** - bring your own paid key

API key setup (pick one):
- `.env` file in project root: `GEMINI_API_KEY=your-key` (or `OPENROUTER_API_KEY`,
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`) - recommended, gitignored
- Environment variable in your shell
- CLI flag: `--api-key KEY`

The Settings UI writes keys to `.env` only - never into the git-tracked `config.yaml`.

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

- **Framework**: Electron 43 with electron-vite 5 (Vite 7)
- **Frontend**: React 19 + TypeScript + Tailwind CSS 4
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
| 1 | YouTube Captions (+ yt-dlp fallback) | Instant | Most videos, quick analysis |
| 2 | faster-whisper (batched) or Groq API | Fast | No captions, accuracy-critical |
| 3 | Visual + Audio | Minutes | Slides, code, diagrams |
| gemini | Gemini video understanding (URL only) | ~1 min | Zero local compute; free tier, ~8h video/day (preview) |

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

- Python 3.11+
- ffmpeg
- Deno 2.3+ (for yt-dlp YouTube support)
- Optional but recommended for reliable YouTube downloads:
  `pip install bgutil-ytdlp-pot-provider` (PO-token provider plugin - yt-dlp
  uses it automatically when its server is running; see docs/SETUP.md)

For Tier 3 visual analysis:
```bash
pip install -e ".[visual]"
```
