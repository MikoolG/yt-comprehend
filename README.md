# YT-Comprehend

Tiered video comprehension platform for extracting content from online videos and feeding it to LLMs.

## Quick Start

```bash
# Install
pip install -e .

# Basic usage - auto-selects best available method
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"

# Force specific tier
yt-comprehend URL --tier 1  # Captions only (instant)
yt-comprehend URL --tier 2  # Audio transcription (Whisper)
yt-comprehend URL --tier 3  # Full visual analysis

# Save to file
yt-comprehend URL -o transcript.md

# Different output formats
yt-comprehend URL --format plain   # Just text
yt-comprehend URL --format json    # Structured data

# Whisper options
yt-comprehend URL --tier 2 --model large-v3-turbo --device cuda
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

See [SETUP.md](SETUP.md) for detailed installation and configuration instructions.

## Requirements

- Python 3.10+
- ffmpeg
- Deno (for yt-dlp YouTube support)

For Tier 3 visual analysis:
```bash
pip install -e ".[visual]"
```
