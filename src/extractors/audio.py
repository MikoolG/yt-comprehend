"""Tier 2: Audio Transcription

Downloads audio track and transcribes with faster-whisper.
More accurate than YouTube captions, works on any video.
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from faster_whisper import WhisperModel


def ensure_ytdlp_updated(quiet: bool = True) -> bool:
    """
    Update yt-dlp to latest version.

    Args:
        quiet: If True, suppress output

    Returns:
        True if updated successfully
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if not quiet and "Successfully installed" in result.stdout:
            print(f"[yt-dlp] Updated: {result.stdout.strip()}", file=sys.stderr)
        return result.returncode == 0
    except Exception as e:
        if not quiet:
            print(f"[yt-dlp] Update failed: {e}", file=sys.stderr)
        return False


@dataclass
class TranscriptSegment:
    """A single transcribed segment with timing and metadata."""
    text: str
    start: float
    end: float
    words: list[dict] = field(default_factory=list)  # Word-level timestamps if available
    
    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class TranscriptResult:
    """Result from audio transcription."""
    segments: list[TranscriptSegment]
    language: str
    language_probability: float
    duration: float  # Total audio duration in seconds
    
    @property
    def text(self) -> str:
        """Get full transcript as plain text."""
        return " ".join(seg.text.strip() for seg in self.segments)
    
    def text_with_timestamps(self, interval: int = 30) -> str:
        """Get transcript grouped by time intervals."""
        if not self.segments:
            return ""
        
        lines = []
        current_interval_start = 0
        current_texts = []
        
        for seg in self.segments:
            interval_num = int(seg.start // interval)
            expected_start = interval_num * interval
            
            if expected_start > current_interval_start and current_texts:
                end_time = current_interval_start + interval
                lines.append(f"[{_format_time(current_interval_start)} - {_format_time(end_time)}]")
                lines.append(" ".join(current_texts))
                lines.append("")
                current_texts = []
                current_interval_start = expected_start
            
            current_texts.append(seg.text.strip())
        
        if current_texts:
            lines.append(f"[{_format_time(current_interval_start)} - {_format_time(self.duration)}]")
            lines.append(" ".join(current_texts))
        
        return "\n".join(lines)


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class AudioExtractor:
    """Download audio and transcribe with faster-whisper."""

    def __init__(
        self,
        model_name: str = "medium",
        device: str = "auto",
        compute_type: str = "int8",
        beam_size: int = 5,
        language: str | None = None,
        initial_prompt: str | None = None,
        temp_dir: str | Path | None = None,
    ):
        """
        Initialize the audio extractor.

        Args:
            model_name: Whisper model (tiny, small, medium, large-v3, large-v3-turbo)
            device: Device to use (auto, cpu, cuda)
            compute_type: Quantization type (int8, float16, float32)
            beam_size: Beam size for decoding
            language: Force specific language or None for auto-detect
            initial_prompt: Optional text to guide Whisper's style/vocabulary
            temp_dir: Directory for temporary files
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.language = language
        self.initial_prompt = initial_prompt
        self.temp_dir = Path(temp_dir) if temp_dir else None

        self._model: WhisperModel | None = None
    
    @property
    def model(self) -> WhisperModel:
        """Lazy-load the Whisper model."""
        if self._model is None:
            device = self.device
            if device == "auto":
                # Try CUDA first, fall back to CPU
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            
            self._model = WhisperModel(
                self.model_name,
                device=device,
                compute_type=self.compute_type,
            )
        return self._model
    
    def download_audio(self, url: str, output_path: Path | None = None) -> Path:
        """
        Download audio from a video URL using yt-dlp.
        
        Args:
            url: Video URL
            output_path: Where to save the audio file
            
        Returns:
            Path to downloaded audio file
        """
        if output_path is None:
            # Use temp directory
            temp_base = self.temp_dir or Path(tempfile.gettempdir())
            temp_base.mkdir(parents=True, exist_ok=True)
            output_path = temp_base / "audio_%(id)s.%(ext)s"
        
        output_template = str(output_path)
        
        # yt-dlp command to extract best audio
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "ba[acodec^=mp4a]/ba/b",  # Best audio, prefer m4a
            "-x",  # Extract audio
            "--audio-format", "m4a",  # Convert to m4a (good for whisper)
            "--audio-quality", "0",  # Best quality
            "-o", output_template,
            "--print", "after_move:filepath",  # Print final path
            url,
        ]
        
        def run_download():
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            # Get the actual output path from yt-dlp
            audio_path = Path(result.stdout.strip().split('\n')[-1])
            if not audio_path.exists():
                raise AudioExtractionError(f"Audio file not found at: {audio_path}")
            return audio_path

        try:
            return run_download()
        except subprocess.CalledProcessError as e:
            # On 403 error, try updating yt-dlp and retry once
            if "403" in e.stderr:
                ensure_ytdlp_updated(quiet=False)
                try:
                    return run_download()
                except subprocess.CalledProcessError as e2:
                    raise AudioExtractionError(f"yt-dlp failed: {e2.stderr}")
            raise AudioExtractionError(f"yt-dlp failed: {e.stderr}")
        except Exception as e:
            raise AudioExtractionError(f"Failed to download audio: {e}")
    
    def transcribe(self, audio_path: Path | str) -> TranscriptResult:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            TranscriptResult with segments and metadata
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise AudioExtractionError(f"Audio file not found: {audio_path}")
        
        segments_iter, info = self.model.transcribe(
            str(audio_path),
            beam_size=self.beam_size,
            language=self.language,
            initial_prompt=self.initial_prompt,
            word_timestamps=True,
            vad_filter=True,  # Filter out non-speech
        )
        
        # Convert iterator to list of segments
        segments = []
        for seg in segments_iter:
            words = []
            if seg.words:
                words = [
                    {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                    for w in seg.words
                ]
            
            segments.append(TranscriptSegment(
                text=seg.text,
                start=seg.start,
                end=seg.end,
                words=words,
            ))
        
        return TranscriptResult(
            segments=segments,
            language=info.language,
            language_probability=info.language_probability,
            duration=info.duration,
        )
    
    def extract(
        self,
        url: str,
        keep_audio: bool = False,
        progress_callback: callable = None,
    ) -> TranscriptResult:
        """
        Download audio and transcribe in one step.
        
        Args:
            url: Video URL
            keep_audio: Whether to keep the audio file after transcription
            progress_callback: Optional callback for progress updates
            
        Returns:
            TranscriptResult with segments and metadata
        """
        audio_path = None
        
        try:
            if progress_callback:
                progress_callback("Downloading audio...")
            
            audio_path = self.download_audio(url)
            
            if progress_callback:
                progress_callback("Transcribing with Whisper...")
            
            result = self.transcribe(audio_path)
            
            return result
            
        finally:
            # Cleanup unless keep_audio is True
            if audio_path and audio_path.exists() and not keep_audio:
                try:
                    audio_path.unlink()
                except Exception:
                    pass  # Best effort cleanup
    
    def transcribe_stream(self, audio_path: Path | str) -> Iterator[TranscriptSegment]:
        """
        Transcribe audio and yield segments as they're processed.
        
        Useful for showing progress on long files.
        
        Args:
            audio_path: Path to audio file
            
        Yields:
            TranscriptSegment objects as they're transcribed
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise AudioExtractionError(f"Audio file not found: {audio_path}")
        
        segments_iter, info = self.model.transcribe(
            str(audio_path),
            beam_size=self.beam_size,
            language=self.language,
            word_timestamps=True,
            vad_filter=True,
        )
        
        for seg in segments_iter:
            words = []
            if seg.words:
                words = [
                    {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                    for w in seg.words
                ]
            
            yield TranscriptSegment(
                text=seg.text,
                start=seg.start,
                end=seg.end,
                words=words,
            )


class AudioExtractionError(Exception):
    """Raised when audio extraction or transcription fails."""
    pass
