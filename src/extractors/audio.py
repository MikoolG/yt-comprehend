"""Tier 2: Audio Transcription

Downloads audio track with yt-dlp and transcribes it.
More accurate than YouTube captions, works on any video.

Backends:
- local (default): faster-whisper with batched inference
- groq: Groq's free Whisper API (fast cloud transcription, needs GROQ_API_KEY)

Note: for reliable YouTube downloads in 2026, installing the optional
`bgutil-ytdlp-pot-provider` PO-token plugin is recommended (yt-dlp picks it
up automatically when its server is running). See docs/SETUP.md.
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import group_segments_by_interval

# Errors in yt-dlp stderr that a version update or retry may fix
_RETRYABLE_DOWNLOAD_ERRORS = ("403", "PO Token", "po token", "Sign in to confirm")


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
        return group_segments_by_interval(self.segments, interval, end_time=self.duration)


class AudioExtractionError(Exception):
    """Raised when audio extraction or transcription fails."""
    pass


class AudioExtractor:
    """Download audio and transcribe with faster-whisper or Groq."""

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "int8",
        beam_size: int = 5,
        language: str | None = None,
        initial_prompt: str | None = None,
        temp_dir: str | Path | None = None,
        backend: str = "local",
        groq_api_key: str | None = None,
    ):
        """
        Initialize the audio extractor.

        Args:
            model_name: Whisper model (tiny, small, medium, large-v3,
                        large-v3-turbo, distil-large-v3.5)
            device: Device to use (auto, cpu, cuda) - handled by CTranslate2
            compute_type: Quantization type (int8, float16, float32)
            beam_size: Beam size for decoding
            language: Force specific language or None for auto-detect
            initial_prompt: Optional text to guide Whisper's style/vocabulary
            temp_dir: Directory for temporary files
            backend: "local" (faster-whisper) or "groq" (free cloud Whisper API)
            groq_api_key: Groq API key (falls back to GROQ_API_KEY env var)
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.language = language
        self.initial_prompt = initial_prompt
        self.temp_dir = Path(temp_dir) if temp_dir else None
        self.backend = backend
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")

        self._model = None
        self._pipeline = None

    @property
    def model(self):
        """Lazy-load the Whisper model (CTranslate2 resolves device='auto')."""
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    @property
    def pipeline(self):
        """Lazy-load the batched inference pipeline (~4x faster than sequential)."""
        if self._pipeline is None:
            from faster_whisper import BatchedInferencePipeline

            self._pipeline = BatchedInferencePipeline(model=self.model)
        return self._pipeline

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
            temp_base = self.temp_dir or Path(tempfile.gettempdir())
            temp_base.mkdir(parents=True, exist_ok=True)
            output_path = temp_base / "audio_%(id)s.%(ext)s"

        output_template = str(output_path)

        # Audio-only opus avoids most SABR-era video-format failures
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "bestaudio/best",
            "-x",  # Extract audio
            "--audio-format", "opus",
            "--audio-quality", "0",
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
            audio_path = Path(result.stdout.strip().split('\n')[-1])
            if not audio_path.exists():
                raise AudioExtractionError(f"Audio file not found at: {audio_path}")
            return audio_path

        try:
            return run_download()
        except subprocess.CalledProcessError as e:
            # On 403 / PO-token errors, try updating yt-dlp and retry once
            if any(marker in e.stderr for marker in _RETRYABLE_DOWNLOAD_ERRORS):
                ensure_ytdlp_updated(quiet=False)
                try:
                    return run_download()
                except subprocess.CalledProcessError as e2:
                    raise AudioExtractionError(
                        f"yt-dlp failed: {e2.stderr}\n"
                        "Hint: installing the bgutil-ytdlp-pot-provider plugin "
                        "usually fixes persistent PO-token/403 errors."
                    )
            raise AudioExtractionError(f"yt-dlp failed: {e.stderr}")
        except AudioExtractionError:
            raise
        except Exception as e:
            raise AudioExtractionError(f"Failed to download audio: {e}")

    def transcribe(self, audio_path: Path | str) -> TranscriptResult:
        """
        Transcribe an audio file with the configured backend.

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptResult with segments and metadata
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise AudioExtractionError(f"Audio file not found: {audio_path}")

        if self.backend == "groq":
            return self._transcribe_groq(audio_path)
        return self._transcribe_local(audio_path)

    def _transcribe_local(self, audio_path: Path) -> TranscriptResult:
        """Transcribe with faster-whisper (batched, falling back to sequential)."""
        kwargs = dict(
            beam_size=self.beam_size,
            language=self.language,
            initial_prompt=self.initial_prompt,
            word_timestamps=True,
        )

        try:
            segments_iter, info = self.pipeline.transcribe(
                str(audio_path), batch_size=8, **kwargs
            )
        except Exception:
            # Batched pipeline can fail on unusual audio/args; sequential is safe
            segments_iter, info = self.model.transcribe(
                str(audio_path), vad_filter=True, **kwargs
            )

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

    def _transcribe_groq(self, audio_path: Path) -> TranscriptResult:
        """Transcribe via Groq's free Whisper API (OpenAI-compatible)."""
        if not self.groq_api_key:
            raise AudioExtractionError(
                "Groq backend selected but no API key found. "
                "Set GROQ_API_KEY or switch whisper.backend to 'local'."
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise AudioExtractionError(
                "openai package required for the Groq backend. Run: pip install openai"
            )

        client = OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        try:
            with open(audio_path, "rb") as f:
                resp = client.audio.transcriptions.create(
                    model="whisper-large-v3-turbo",
                    file=f,
                    response_format="verbose_json",
                    language=self.language or None,
                )
        except Exception as e:
            raise AudioExtractionError(f"Groq transcription failed: {e}") from e

        raw_segments = getattr(resp, "segments", None) or []
        segments = [
            TranscriptSegment(
                text=getattr(s, "text", s.get("text", "") if isinstance(s, dict) else ""),
                start=getattr(s, "start", s.get("start", 0) if isinstance(s, dict) else 0),
                end=getattr(s, "end", s.get("end", 0) if isinstance(s, dict) else 0),
            )
            for s in raw_segments
        ]

        duration = getattr(resp, "duration", None) or (segments[-1].end if segments else 0.0)

        return TranscriptResult(
            segments=segments,
            language=getattr(resp, "language", None) or (self.language or "unknown"),
            language_probability=1.0,
            duration=float(duration),
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
                label = "Groq Whisper API" if self.backend == "groq" else "Whisper"
                progress_callback(f"Transcribing with {label}...")

            return self.transcribe(audio_path)

        finally:
            # Cleanup unless keep_audio is True
            if audio_path and audio_path.exists() and not keep_audio:
                try:
                    audio_path.unlink()
                except Exception:
                    pass  # Best effort cleanup
