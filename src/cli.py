#!/usr/bin/env python3
"""YT-Comprehend CLI - Video comprehension for LLM consumption."""

import json
import os
import sys
import time
from pathlib import Path

import click
from rich.console import Console

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.comprehend import VideoComprehend
from src.extractors.audio import AudioExtractionError
from src.extractors.captions import CaptionExtractionError
from src.extractors.gemini_video import GeminiVideoError
from src.summarize import SummarizationError, summarize_file

console = Console()
err_console = Console(stderr=True)


def _load_project_env():
    """Load the project-root .env into os.environ (existing vars win).

    Lets API keys (GEMINI_API_KEY etc.) work from any terminal without
    sourcing the file manually - important for agent/script usage.
    """
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass  # .env is a convenience; never fail on it


def _get_safe_filename(video_id: str) -> str:
    """Get video title and convert to safe filename."""
    import re
    import subprocess

    try:
        # Use yt-dlp to get video title
        result = subprocess.run(
            ["yt-dlp", "--get-title", "--no-playlist", f"https://youtube.com/watch?v={video_id}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            title = result.stdout.strip()
            # Convert to safe filename: lowercase, replace spaces/special chars with hyphens
            safe = re.sub(r'[^\w\s-]', '', title.lower())
            safe = re.sub(r'[-\s]+', '-', safe).strip('-')
            # Limit length
            if len(safe) > 60:
                safe = safe[:60].rsplit('-', 1)[0]
            return safe
    except Exception:
        pass

    # Fallback to video ID
    return video_id


def progress_callback(message: str):
    """Print progress messages."""
    console.print(f"[dim]→ {message}[/dim]", highlight=False)


def json_progress_event(stage: str, message: str, progress: int = -1, output_path: str | None = None):
    """Emit a JSON progress event to stdout."""
    event = {
        "stage": stage,
        "message": message,
        "progress": progress,
        "timestamp": time.time(),
    }
    if output_path:
        event["output_path"] = output_path
    print(json.dumps(event), flush=True)


def make_json_progress_callback():
    """Create a progress callback that emits JSON events."""
    stage_progress = {
        "Trying caption extraction": ("caption", 10),
        "yt-dlp caption fallback": ("caption", 15),
        "Captions unavailable": ("caption", 20),
        "Escalating to Tier 2": ("escalate", 25),
        "Starting audio transcription": ("transcribe", 30),
        "Downloading audio": ("download", 40),
        "Transcribing with": ("transcribe", 60),
        "Audio transcription failed": ("transcribe", 70),
        "Escalating to Tier 3": ("escalate", 75),
        "Starting full visual analysis": ("visual", 80),
        "Sending video URL to Gemini": ("gemini", 40),
    }

    def callback(message: str):
        # Try to match known messages for progress estimation
        stage = "processing"
        progress = -1

        for pattern, (s, p) in stage_progress.items():
            if pattern in message:
                stage = s
                progress = p
                break

        json_progress_event(stage, message, progress)

    return callback


@click.command()
@click.argument("url")
@click.option(
    "--tier", "-t",
    type=click.Choice(["1", "2", "3", "gemini"]),
    default=None,
    help="Analysis tier (1=captions, 2=audio, 3=visual, gemini=direct URL via Gemini API, "
         "free tier, preview, ~8h video/day)"
)
@click.option(
    "--no-escalate",
    is_flag=True,
    default=False,
    help="Don't auto-escalate to next tier if current fails"
)
@click.option(
    "--model", "-m",
    default=None,
    help="Whisper model for Tier 2 (tiny, small, medium, large-v3, large-v3-turbo)"
)
@click.option(
    "--device", "-d",
    type=click.Choice(["auto", "cpu", "cuda"]),
    default=None,
    help="Device for Whisper inference"
)
@click.option(
    "--whisper-backend",
    type=click.Choice(["local", "groq"]),
    default=None,
    help="Tier 2 transcription backend (local=faster-whisper, groq=free cloud Whisper API)"
)
@click.option(
    "--prompt", "-p",
    default=None,
    help="Initial prompt to guide Whisper vocabulary (e.g., 'Claude Code, Anthropic, API')"
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Output file path (overrides default output location)"
)
@click.option(
    "--no-save",
    is_flag=True,
    default=False,
    help="Don't save to file, only print to stdout"
)
@click.option(
    "--format", "-f",
    "output_format",
    type=click.Choice(["markdown", "plain", "json"]),
    default="markdown",
    help="Output format"
)
@click.option(
    "--no-timestamps",
    is_flag=True,
    default=False,
    help="Exclude timestamps from output"
)
@click.option(
    "--interval", "-i",
    type=int,
    default=30,
    help="Timestamp grouping interval in seconds"
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True),
    default=None,
    help="Path to config.yaml"
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    default=False,
    help="Suppress progress output"
)
@click.option(
    "--json-progress",
    is_flag=True,
    default=False,
    help="Output JSON progress events (for UI integration)"
)
@click.option(
    "--summarize", "-s",
    is_flag=True,
    default=False,
    help="Summarize transcript via LLM API after extraction"
)
@click.option(
    "--provider",
    default=None,
    help="LLM provider for summarization (gemini, openrouter, ollama, openai, anthropic)"
)
@click.option(
    "--api-key",
    default=None,
    help="API key for summarization provider (overrides env var and config)"
)
@click.option(
    "--summarize-model",
    default=None,
    help="Model for summarization (default: provider-specific)"
)
@click.option(
    "--llm",
    is_flag=True,
    default=False,
    help="Agent mode: extract + summarize (Gemini free tier by default), print ONLY the "
         "summary markdown to stdout; progress/warnings go to stderr. Transcript and "
         "summary are still saved to output/. Designed for LLMs and scripts."
)
def main(
    url: str,
    tier: str | None,
    no_escalate: bool,
    model: str | None,
    device: str | None,
    whisper_backend: str | None,
    prompt: str | None,
    output: str | None,
    no_save: bool,
    output_format: str,
    no_timestamps: bool,
    interval: int,
    config: str | None,
    quiet: bool,
    json_progress: bool,
    summarize: bool,
    provider: str | None,
    api_key: str | None,
    summarize_model: str | None,
    llm: bool,
):
    """
    Extract video content for LLM consumption.

    URL can be a YouTube URL or video ID.

    Examples:

        yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"

        yt-comprehend URL --llm          # agent mode: summary on stdout

        yt-comprehend VIDEO_ID --tier 2 --model large-v3

        yt-comprehend URL -o transcript.md --format markdown
    """
    _load_project_env()

    if llm and json_progress:
        raise click.UsageError("--llm and --json-progress are mutually exclusive")
    if llm:
        summarize = not no_save  # summary needs a saved transcript
        quiet = True  # silence stdout chatter; --llm reports progress on stderr

    # Find config file
    config_path = config
    if not config_path:
        # Look for config in current dir or project root
        for candidate in [Path("config.yaml"), Path(__file__).parent.parent / "config.yaml"]:
            if candidate.exists():
                config_path = str(candidate)
                break

    # Initialize engine
    vc = VideoComprehend(config_path=config_path)

    # Override config with CLI options
    if model:
        vc.config["whisper"]["model"] = model
    if device:
        vc.config["whisper"]["device"] = device
    if whisper_backend:
        vc.config["whisper"]["backend"] = whisper_backend
    if prompt:
        vc.config["whisper"]["initial_prompt"] = prompt
    if api_key and not vc.config.get("summarize", {}).get("api_key"):
        vc.config.setdefault("summarize", {})["api_key"] = api_key

    # Normalize tier: "1"/"2"/"3" -> int, "gemini" stays a string
    resolved_tier = None
    if tier is not None:
        resolved_tier = tier if tier == "gemini" else int(tier)

    if summarize and no_save:
        message = "--summarize requires a saved transcript; ignoring because --no-save was passed"
        if json_progress:
            json_progress_event("warning", message, -1)
        else:
            console.print(f"[yellow]Warning:[/yellow] {message}")

    # Progress callback
    if json_progress:
        callback = make_json_progress_callback()
        json_progress_event("start", f"Starting analysis of {url}", 0)
    elif llm:
        # Keep stdout clean for the summary; progress goes to stderr
        def callback(message: str):
            err_console.print(f"[dim]→ {message}[/dim]", highlight=False)
    elif quiet:
        callback = None
    else:
        callback = progress_callback

    try:
        if not quiet and not json_progress:
            console.print(f"[bold]Analyzing:[/bold] {url}")
            console.print()

        result = vc.analyze(
            url=url,
            tier=resolved_tier,
            auto_escalate=not no_escalate,
            progress_callback=callback,
        )

        if json_progress:
            json_progress_event("analyzed", f"Analysis complete (Tier {result.metadata.tier_used})", 90)
        elif not quiet:
            console.print()
            console.print(f"[green]✓[/green] Analysis complete (Tier {result.metadata.tier_used})")
            console.print()

        # Format output
        if output_format == "json":
            output_text = json.dumps({
                "metadata": {
                    "url": result.metadata.url,
                    "video_id": result.metadata.video_id,
                    "tier_used": result.metadata.tier_used,
                    "language": result.metadata.language,
                    "duration": result.metadata.duration,
                },
                "transcript": result.transcript_text,
                "segments": [
                    {"text": s.text, "start": s.start, "end": getattr(s, 'end', s.start + getattr(s, 'duration', 0))}
                    for s in result.transcript_segments
                ],
                "visual_text": result.visual_text if result.visual_text else None,
            }, indent=2)
        elif output_format == "plain":
            output_text = result.transcript_text
            if result.visual_text:
                output_text += f"\n\n---\n\n{result.visual_text}"
        else:  # markdown
            output_text = result.to_markdown(
                include_timestamps=not no_timestamps,
                timestamp_interval=interval,
            )

        # Determine output path (save by default unless --no-save)
        output_path = None
        if output:
            output_path = Path(output)
        elif not no_save:
            # Auto-generate path based on tier
            tier_dirs = {
                1: "tier1-captions",
                2: "tier2-whisper",
                3: "tier3-visual",
                "gemini": "gemini-direct",
            }
            tier_dir = tier_dirs.get(result.metadata.tier_used, "tier1-captions")

            # Use output directory from config, or default
            output_base = Path(vc.config.get("output", {}).get("directory", "./output"))
            if not output_base.is_absolute():
                output_base = Path(__file__).parent.parent / output_base
            output_base.mkdir(parents=True, exist_ok=True)

            # Create tier subdirectories
            transcript_dir = output_base / tier_dir / "transcripts"
            transcript_dir.mkdir(parents=True, exist_ok=True)

            # Get video title for filename
            filename = _get_safe_filename(result.metadata.video_id)
            ext = {"json": ".json", "plain": ".txt", "markdown": ".md"}.get(output_format, ".md")
            output_path = transcript_dir / f"{filename}{ext}"

        # Output: save to file if path set, always print to stdout unless quiet
        if output_path:
            output_path.write_text(output_text)
            if json_progress:
                if summarize:
                    # Don't emit "complete" yet - summarization still pending
                    json_progress_event("transcript_saved", "Transcript saved", 90, str(output_path))
                else:
                    json_progress_event("complete", "Saved successfully", 100, str(output_path))
            elif not quiet:
                console.print(f"[dim]Saved to:[/dim] {output_path}")
        elif json_progress:
            json_progress_event("complete", "Analysis complete", 100)

        # Summarize via LLM API if requested
        summary_path = None
        summary_error = None
        if summarize and output_path:
            try:
                if json_progress:
                    json_progress_event("summarize", "Starting API summarization...", 92)

                # Resolve settings: cli flag > config
                sum_config = vc.config.get("summarize", {})
                resolved_provider = provider or sum_config.get("provider", "gemini")
                resolved_key = api_key or sum_config.get("api_key")
                resolved_model = summarize_model or sum_config.get("model")

                def summarize_progress(msg):
                    if json_progress:
                        json_progress_event("summarize", msg, 95)
                    elif llm:
                        err_console.print(f"[dim]-> {msg}[/dim]", highlight=False)
                    elif not quiet:
                        console.print(f"[dim]-> {msg}[/dim]", highlight=False)

                summary_path = summarize_file(
                    output_path,
                    provider=resolved_provider,
                    api_key=resolved_key,
                    model=resolved_model,
                    progress_callback=summarize_progress,
                )

                if json_progress:
                    json_progress_event(
                        "summary_complete", "Summary saved", 100, str(summary_path)
                    )
                elif llm:
                    err_console.print(f"[green]✓[/green] Summary saved to: {summary_path}")
                elif not quiet:
                    console.print(f"[green]✓[/green] Summary saved to: {summary_path}")

            except (SummarizationError, OSError, ValueError, RuntimeError) as e:
                summary_error = str(e)
                if json_progress:
                    json_progress_event("error", f"Summarization failed: {e}", -1)
                elif llm:
                    err_console.print(f"[yellow]Warning:[/yellow] Summarization failed: {e}")
                elif not quiet:
                    console.print(f"[yellow]Warning:[/yellow] Summarization failed: {e}")

        # stdout contract:
        # --llm        -> summary markdown (fallback: transcript)
        # default      -> transcript (unless quiet/-o/--json-progress)
        if llm:
            if summary_path is not None:
                print(Path(summary_path).read_text())
            else:
                if summary_error:
                    err_console.print(
                        "[yellow]Summary unavailable - printing transcript instead[/yellow]"
                    )
                print(output_text)
        elif not quiet and not output and not json_progress:
            print(output_text)

    except CaptionExtractionError as e:
        if json_progress:
            json_progress_event("error", f"Caption extraction failed: {e}", -1)
        else:
            err_console.print(f"[red]Caption extraction failed:[/red] {e}")
        sys.exit(1)
    except GeminiVideoError as e:
        if json_progress:
            json_progress_event("error", f"Gemini video analysis failed: {e}", -1)
        else:
            err_console.print(f"[red]Gemini video analysis failed:[/red] {e}")
        sys.exit(1)
    except AudioExtractionError as e:
        if json_progress:
            json_progress_event("error", f"Audio extraction failed: {e}", -1)
        else:
            err_console.print(f"[red]Audio extraction failed:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        if json_progress:
            json_progress_event("error", f"Error: {e}", -1)
        else:
            err_console.print(f"[red]Error:[/red] {e}")
            if not quiet:
                err_console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
