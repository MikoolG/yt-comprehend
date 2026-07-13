---
name: yt-comprehend
description: Extract and summarize YouTube videos with the local yt-comprehend CLI. Use whenever the user shares a YouTube link (or video ID) to watch, summarize, analyze, or "check out", or mentions yt-comprehend. No MCP needed - it's a plain terminal command.
---

# yt-comprehend — YouTube comprehension for LLMs

A local CLI that turns YouTube videos into markdown transcripts and summaries.
Project root: `~/Documents/yt-comprehend` (adjust if the repo lives elsewhere).

## The one command to reach for

```bash
yt-comprehend "URL_OR_VIDEO_ID" --llm
```

`--llm` is agent mode:
- Extracts captions (tier 1, instant; auto-falls back to yt-dlp subtitles, then Whisper)
- Summarizes with the Gemini free tier (with automatic free-model fallback)
- Prints **only the summary markdown to stdout** — read it directly
- Progress and warnings go to stderr; if summarization fails, stdout carries the transcript instead
- Also saves both files under `output/<tier>/transcripts|summaries/<video-title>.md`

If `yt-comprehend` is not on PATH, run it from the project root:
`cd ~/Documents/yt-comprehend && venv/bin/yt-comprehend "URL" --llm`

## When you need something else

| Need | Command |
|---|---|
| Full transcript with timestamps (no summary) | `yt-comprehend URL --quiet` then read `output/tier1-captions/transcripts/<title>.md` |
| No captions / accuracy-critical | `yt-comprehend URL --llm --tier 2` (local Whisper; slower, downloads model on first use) |
| Zero local compute (needs GEMINI_API_KEY) | `yt-comprehend URL --llm --tier gemini` (sends URL to Gemini video understanding) |
| Different summarizer | `--provider openrouter` / `ollama` / `openai` / `anthropic` |
| Machine-readable transcript | `yt-comprehend URL --format json --quiet` |

## Notes

- Multiple links: run the command once per URL (sequentially).
- API keys live in the project `.env` (auto-loaded by the CLI). Gemini free tier is the default; if summarization errors with a key problem, tell the user to add `GEMINI_API_KEY=` to `.env`.
- Tier 2 needs ffmpeg + deno; the wrapper/venv handles PATH. First tier-2 run downloads ~1.6GB (large-v3-turbo).
- To reference a specific moment, use the `[MM:SS]` timestamps in the transcript files.
