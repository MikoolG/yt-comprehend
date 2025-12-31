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
yt-comprehend URL                    # Auto-selects best tier
yt-comprehend URL --tier 2           # Force Whisper transcription
yt-comprehend URL --tier 2 --model large-v3-turbo --device cuda
yt-comprehend URL -o out.md --format json --quiet
```

## Architecture

- **`src/comprehend.py`**: `VideoComprehend` orchestrates tiers, auto-escalates on failure, returns `ComprehendResult`
- **`src/extractors/captions.py`**: Tier 1 - uses `youtube-transcript-api` v1.x (`.list()` / `.fetch()`)
- **`src/extractors/audio.py`**: Tier 2 - yt-dlp download + faster-whisper (lazy-loaded model)
- **`src/extractors/visual.py`**: Tier 3 - scene detection → frame extraction → dedup → OCR
- **`config.yaml`**: Default settings for whisper, visual, cleanup. CLI options override.

## Notes

- `youtube-transcript-api` v1.x API: use `api.list(video_id)` not `api.list_transcripts()`
- System deps: ffmpeg, deno (required by yt-dlp for YouTube as of 2025)
- Tier 3 requires `[visual]` extra for scenedetect, paddleocr, imagededup
