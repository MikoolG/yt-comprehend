# YT-Comprehend: Video Comprehension Platform Setup Guide

This document provides complete setup instructions for the YT-Comprehend video analysis platform. Pass this to Claude Code to configure your environment.

## Overview

YT-Comprehend is a tiered video comprehension system designed to extract content from online videos (primarily YouTube) for LLM consumption. It operates in three tiers of increasing depth:

| Tier | Method | Speed | Use Case |
|------|--------|-------|----------|
| **1 - Captions** | YouTube transcript API | Instant | Quick comprehension, most videos |
| **2 - Audio** | yt-dlp + faster-whisper | ~2× realtime | No captions, accuracy-critical |
| **3 - Visual** | Scene detection + OCR + frames | Minutes | Slides, code, diagrams, full context |

## System Requirements

- **OS**: Ubuntu 24.04 (tested), Linux generally
- **RAM**: 8GB minimum, 16GB+ recommended for Tier 2/3
- **Storage**: 2GB for models, temp space for video processing
- **Python**: 3.10+
- **GPU**: Optional but improves Tier 2/3 significantly

## Environment Setup

### 1. System Dependencies

```bash
# Core dependencies
sudo apt update
sudo apt install -y ffmpeg python3-pip python3-venv git

# Deno runtime (required for yt-dlp YouTube support as of 2025)
curl -fsSL https://deno.land/install.sh | sh
# Add to PATH: export DENO_INSTALL="$HOME/.deno" && export PATH="$DENO_INSTALL/bin:$PATH"
# Add the above to ~/.bashrc or ~/.zshrc

# For Tier 3 visual analysis (optional initially)
sudo apt install -y libgl1-mesa-glx libglib2.0-0
```

### 2. Project Setup

```bash
# Create project directory
mkdir -p ~/projects/yt-comprehend
cd ~/projects/yt-comprehend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (see requirements.txt below)
pip install -r requirements.txt
```

### 3. Model Downloads (Automatic on First Run)

faster-whisper models download automatically on first use:
- `tiny` (~75MB) - Fast, lower accuracy
- `small` (~500MB) - Good balance for quick tasks
- `medium` (~1.5GB) - **Recommended default**
- `large-v3` (~3GB) - Best accuracy, slower
- `large-v3-turbo` (~1.6GB) - Near large-v3 accuracy, 8× faster (GPU recommended)

## Project Structure

```
yt-comprehend/
├── SETUP.md                 # This file
├── requirements.txt         # Python dependencies
├── config.yaml              # User configuration
├── src/
│   ├── __init__.py
│   ├── cli.py               # Main CLI entry point
│   ├── comprehend.py        # Core comprehension engine
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── captions.py      # Tier 1: YouTube caption extraction
│   │   ├── audio.py         # Tier 2: Audio transcription
│   │   └── visual.py        # Tier 3: Visual analysis
│   └── utils.py             # Helpers and formatters
├── output/                  # Default output directory
└── temp/                    # Temporary files (auto-cleaned)
```

## Dependencies

### requirements.txt

```
# Core
youtube-transcript-api>=0.6.2
yt-dlp>=2024.12.1
faster-whisper>=1.0.0

# CLI
click>=8.1.0
rich>=13.0.0

# Configuration
pyyaml>=6.0

# Tier 3 - Visual Analysis (install separately if needed)
# scenedetect[opencv]>=0.6.4
# paddleocr>=2.7.0
# paddlepaddle>=2.6.0  # or paddlepaddle-gpu for CUDA
# imagededup>=0.3.2
# pillow>=10.0.0
```

### Installing Tier 3 Dependencies (When Ready)

```bash
# Scene detection and frame extraction
pip install "scenedetect[opencv]>=0.6.4"

# OCR - Choose based on hardware:
# CPU only:
pip install paddlepaddle paddleocr

# With CUDA GPU:
pip install paddlepaddle-gpu paddleocr

# Image deduplication
pip install imagededup pillow
```

## Configuration

### config.yaml

```yaml
# YT-Comprehend Configuration

# Default tier to use (1, 2, or 3)
default_tier: 1

# Whisper settings (Tier 2)
whisper:
  model: "medium"           # tiny, small, medium, large-v3, large-v3-turbo
  device: "auto"            # auto, cpu, cuda
  compute_type: "int8"      # int8, float16, float32
  beam_size: 5
  language: null            # null for auto-detect, or "en", "es", etc.

# Visual analysis settings (Tier 3)
visual:
  scene_threshold: 3.0      # Lower = more sensitive scene detection
  ocr_engine: "paddleocr"   # paddleocr, tesseract
  extract_every_n_seconds: null  # If set, extract frames at interval instead of scene detection
  deduplicate: true         # Remove near-duplicate frames
  
# Output settings
output:
  directory: "./output"
  format: "markdown"        # markdown, json, plain
  include_timestamps: true
  timestamp_interval: 30    # Group text by N-second intervals (for readability)

# Cleanup
cleanup:
  delete_temp_files: true
  keep_audio: false         # Keep downloaded audio after transcription
  keep_frames: false        # Keep extracted frames after OCR
```

## Usage

### Basic CLI Usage

```bash
# Activate environment
cd ~/projects/yt-comprehend
source venv/bin/activate

# Basic usage - auto-selects best tier, saves to output/
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"

# Force specific tier
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID" --tier 1  # Captions only
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID" --tier 2  # Audio transcription
yt-comprehend "https://youtube.com/watch?v=VIDEO_ID" --tier 3  # Full visual analysis

# Output options
yt-comprehend URL --no-save           # Print to stdout only, don't save to file
yt-comprehend URL --quiet             # Save only, suppress stdout output
yt-comprehend URL -o ./my-transcript.md  # Save to specific file
yt-comprehend URL --format json
yt-comprehend URL --no-timestamps

# Whisper options (Tier 2)
yt-comprehend URL --tier 2 --model large-v3-turbo --device cuda

# Copy to clipboard (requires xclip)
yt-comprehend URL --no-save | xclip -selection clipboard
```

### Output Structure

By default, transcripts are saved to the output directory organized by tier:

```
output/
├── tier1-captions/
│   ├── transcripts/    # Raw transcripts with timestamps
│   │   └── video-title.md
│   └── summaries/      # Claude Code generated summaries
│       └── video-title.md
├── tier2-whisper/
│   ├── transcripts/
│   └── summaries/
└── tier3-visual/
    ├── transcripts/
    └── summaries/
```

### Python API Usage

```python
from src.comprehend import VideoComprehend

vc = VideoComprehend()

# Auto-tier (tries captions first, falls back to audio)
result = vc.analyze("https://youtube.com/watch?v=VIDEO_ID")

# Specific tier
result = vc.analyze(url, tier=2)

# Access results
print(result.text)              # Full transcript
print(result.segments)          # Timestamped segments
print(result.metadata)          # Video info
print(result.visual_content)    # OCR results (Tier 3)
```

## Tier Implementation Details

### Tier 1: Caption Extraction

Uses `youtube-transcript-api` to fetch existing captions directly from YouTube. No download required.

**Pros**: Instant, no compute needed, works for 80%+ of videos
**Cons**: Accuracy varies (60-85% for auto-generated), not all videos have captions

**When captions fail**:
- Video has captions disabled
- Private/age-restricted video
- Live stream without captions
- Very new upload (captions not yet generated)

### Tier 2: Audio Transcription

Downloads audio track only (not full video) via `yt-dlp`, transcribes with `faster-whisper`.

**Resource usage** (medium model, int8, CPU):
- Memory: ~2GB
- Speed: ~2× realtime (30min video ≈ 15min processing)
- Disk: 50-150MB audio file (temporary)

**GPU acceleration** (if available):
- Memory: ~4GB VRAM
- Speed: ~10-20× realtime
- Use: `--device cuda --compute-type float16`

### Tier 3: Visual Analysis

Full pipeline for videos with important visual content (slides, code, diagrams):

1. **Scene Detection** (PySceneDetect): Identifies scene changes/slide transitions
2. **Frame Extraction** (FFmpeg): Captures representative frames
3. **Deduplication** (imagededup): Removes near-identical frames
4. **OCR** (PaddleOCR): Extracts text from frames
5. **Integration**: Combines audio transcript with visual text, synchronized by timestamp

**When to use Tier 3**:
- Technical presentations with code
- Slide-based content
- Tutorials with on-screen text
- Videos where visual content differs from spoken content

**Resource usage**:
- Significantly more processing time (5-15min for 30min video)
- Temp storage for extracted frames
- GPU strongly recommended for PaddleOCR

## Troubleshooting

### yt-dlp YouTube errors

YouTube frequently updates; keep yt-dlp current:
```bash
pip install -U yt-dlp
```

If still failing, ensure Deno is installed and in PATH.

### Whisper model download fails

Models download from Hugging Face. If network issues:
```bash
# Manual download
pip install huggingface-hub
huggingface-cli download Systran/faster-whisper-medium --local-dir ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium
```

### Out of memory (Tier 2)

```bash
# Use smaller model
yt-comprehend URL --model small

# Or force int8 quantization
yt-comprehend URL --compute-type int8
```

### PaddleOCR import errors (Tier 3)

Often due to OpenCV conflicts:
```bash
pip uninstall opencv-python opencv-python-headless
pip install opencv-python-headless
```

## Integration with Claude Code

The primary use case is extracting video content for Claude Code to analyze and summarize. Recommended workflow:

### Workflow

1. **Extract transcript**: Run `yt-comprehend URL --tier 1` (or tier 2 for better accuracy)
2. **Transcript saved**: Automatically saved to `output/<tier>/transcripts/<video-name>.md`
3. **Claude Code analyzes**: Read the transcript and generate a comprehensive summary
4. **Summary saved**: Save to `output/<tier>/summaries/<video-name>.md`

### Summary Contents

Claude Code generates summaries including:
- Overview (what the video is about, target audience)
- Key points and takeaways
- Detailed breakdown by topic/section
- Notable mentions (tools, people, resources)
- Final summary

### Timestamp References

For longer videos, the tool segments output by timestamp intervals, making it easy to reference specific sections:

```
[00:00 - 00:30] Introduction to the topic...
[00:30 - 01:00] First main point discussed...
```

You can then ask Claude: "In the section around 00:30, they mention X - can you elaborate on that?"

## Future Enhancements

Planned features for the visual analysis tier:

- **Multimodal LLM integration**: Send extracted frames to LLaVA/GPT-4V for diagram interpretation
- **Smart frame selection**: ML-based detection of "important" frames vs transitions
- **Code block extraction**: Specialized handling for programming content
- **Slide reconstruction**: Group OCR text by detected slide boundaries
- **Audio-visual sync**: Better alignment of spoken words with on-screen content
