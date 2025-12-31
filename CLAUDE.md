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
```

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

- **`src/cli.py`**: CLI entry point, handles arguments and output saving
- **`src/comprehend.py`**: `VideoComprehend` orchestrates tiers, auto-escalates on failure, returns `ComprehendResult`
- **`src/extractors/captions.py`**: Tier 1 - uses `youtube-transcript-api` v1.x (`.list()` / `.fetch()`)
- **`src/extractors/audio.py`**: Tier 2 - yt-dlp download + faster-whisper (lazy-loaded model)
- **`src/extractors/visual.py`**: Tier 3 - scene detection → frame extraction → dedup → OCR
- **`config.yaml`**: Default settings for whisper, visual, output directory. CLI options override.

## Notes

- `youtube-transcript-api` v1.x API: use `api.list(video_id)` not `api.list_transcripts()`
- System deps: ffmpeg, deno (required by yt-dlp for YouTube as of 2025)
- Tier 3 requires `[visual]` extra for scenedetect, paddleocr, imagededup
- Output directory can be configured in `config.yaml` under `output.directory`
