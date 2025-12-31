#!/usr/bin/env python3
"""YT-Comprehend CLI - Video comprehension for LLM consumption."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.comprehend import VideoComprehend, ComprehendResult
from src.extractors.captions import CaptionExtractionError
from src.extractors.audio import AudioExtractionError

console = Console()


def progress_callback(message: str):
    """Print progress messages."""
    console.print(f"[dim]→ {message}[/dim]", highlight=False)


@click.command()
@click.argument("url")
@click.option(
    "--tier", "-t",
    type=click.IntRange(1, 3),
    default=None,
    help="Force specific analysis tier (1=captions, 2=audio, 3=visual)"
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
    "--output", "-o",
    type=click.Path(),
    default=None,
    help="Output file path (default: stdout)"
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
def main(
    url: str,
    tier: int | None,
    no_escalate: bool,
    model: str | None,
    device: str | None,
    output: str | None,
    output_format: str,
    no_timestamps: bool,
    interval: int,
    config: str | None,
    quiet: bool,
):
    """
    Extract video content for LLM consumption.
    
    URL can be a YouTube URL or video ID.
    
    Examples:
    
        yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"
        
        yt-comprehend VIDEO_ID --tier 2 --model large-v3
        
        yt-comprehend URL -o transcript.md --format markdown
    """
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
    
    # Progress callback
    callback = None if quiet else progress_callback
    
    try:
        if not quiet:
            console.print(f"[bold]Analyzing:[/bold] {url}")
            console.print()
        
        result = vc.analyze(
            url=url,
            tier=tier,
            auto_escalate=not no_escalate,
            progress_callback=callback,
        )
        
        if not quiet:
            console.print()
            console.print(f"[green]✓[/green] Analysis complete (Tier {result.metadata.tier_used})")
            console.print()
        
        # Format output
        if output_format == "json":
            import json
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
        
        # Output
        if output:
            output_path = Path(output)
            output_path.write_text(output_text)
            if not quiet:
                console.print(f"[dim]Saved to:[/dim] {output_path}")
        else:
            # Print to stdout (without rich formatting for piping)
            print(output_text)
    
    except CaptionExtractionError as e:
        console.print(f"[red]Caption extraction failed:[/red] {e}")
        sys.exit(1)
    except AudioExtractionError as e:
        console.print(f"[red]Audio extraction failed:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if not quiet:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
