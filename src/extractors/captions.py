"""Tier 1: YouTube Caption Extraction

Fastest method - extracts existing captions directly from YouTube.
No download required, instant results.

Two routes:
- CaptionExtractor: youtube-transcript-api (primary)
- YtDlpCaptionExtractor: yt-dlp subtitle download (fallback when the
  transcript API is blocked by YouTube's anti-bot measures)
"""

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from youtube_transcript_api import (
    AgeRestricted,
    IpBlocked,
    NoTranscriptFound,
    PoTokenRequired,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)

from ..utils import group_segments_by_interval


@dataclass
class CaptionSegment:
    """A single caption segment with timing."""
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class CaptionResult:
    """Result from caption extraction."""
    video_id: str
    segments: list[CaptionSegment]
    language: str
    is_generated: bool  # True if auto-generated captions

    @property
    def text(self) -> str:
        """Get full transcript as plain text."""
        return " ".join(seg.text for seg in self.segments)

    def text_with_timestamps(self, interval: int = 30) -> str:
        """Get transcript grouped by time intervals."""
        return group_segments_by_interval(self.segments, interval)


class CaptionExtractionError(Exception):
    """Raised when caption extraction fails."""
    pass


class CaptionsBlockedError(CaptionExtractionError):
    """Raised when YouTube blocks the transcript API request.

    Distinguishable so callers can fall back to yt-dlp subtitle
    extraction instead of escalating straight to Whisper.
    """
    pass


class CaptionExtractor:
    """Extract captions from YouTube videos via youtube-transcript-api."""

    def __init__(self, preferred_languages: list[str] | None = None):
        """
        Initialize the caption extractor.

        Args:
            preferred_languages: List of language codes in preference order.
                                Defaults to ["en"] if not specified.
        """
        self.preferred_languages = preferred_languages or ["en"]
        self._api = YouTubeTranscriptApi()

    @staticmethod
    def extract_video_id(url: str) -> str:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$',  # Just the ID itself
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        raise ValueError(f"Could not extract video ID from: {url}")

    def extract(self, url_or_id: str) -> CaptionResult:
        """
        Extract captions from a YouTube video.

        Args:
            url_or_id: YouTube URL or video ID

        Returns:
            CaptionResult with segments and metadata

        Raises:
            CaptionsBlockedError: If YouTube blocks the request (try yt-dlp fallback)
            CaptionExtractionError: If captions cannot be retrieved
        """
        video_id = self.extract_video_id(url_or_id)

        try:
            # List available transcripts (API v1.x uses .list())
            transcript_list = self._api.list(video_id)

            # Try preferred languages first (manual or auto-generated)
            transcript = None
            is_generated = False

            for lang in self.preferred_languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    is_generated = transcript.is_generated
                    break
                except NoTranscriptFound:
                    continue

            # If none matched, take any available and translate
            if transcript is None:
                try:
                    transcript = next(iter(transcript_list))
                    is_generated = transcript.is_generated

                    if transcript.language_code not in self.preferred_languages:
                        try:
                            transcript = transcript.translate(self.preferred_languages[0])
                        except Exception:
                            pass  # Keep original if translation fails

                except StopIteration:
                    raise CaptionExtractionError(
                        f"No transcripts available for video: {video_id}"
                    )

            data = transcript.fetch()

            segments = [
                CaptionSegment(
                    text=item.text,
                    start=item.start,
                    duration=item.duration
                )
                for item in data
            ]

            return CaptionResult(
                video_id=video_id,
                segments=segments,
                language=transcript.language_code,
                is_generated=is_generated
            )

        except (PoTokenRequired, IpBlocked, RequestBlocked) as e:
            raise CaptionsBlockedError(
                f"YouTube blocked the transcript request ({type(e).__name__}). "
                "Falling back to yt-dlp caption download is recommended."
            ) from e
        except AgeRestricted:
            raise CaptionsBlockedError(
                f"Video is age-restricted; transcript API cannot access it: {video_id}"
            )
        except TranscriptsDisabled:
            raise CaptionExtractionError(
                f"Transcripts are disabled for video: {video_id}"
            )
        except VideoUnavailable:
            raise CaptionExtractionError(
                f"Video unavailable: {video_id}"
            )
        except NoTranscriptFound:
            raise CaptionExtractionError(
                f"No transcripts found for video: {video_id}"
            )
        except CaptionExtractionError:
            raise
        except Exception as e:
            raise CaptionExtractionError(f"Failed to extract captions: {e}")

    def is_available(self, url_or_id: str) -> bool:
        """Check if captions are available for a video."""
        try:
            video_id = self.extract_video_id(url_or_id)
            self._api.list(video_id)
            return True
        except Exception:
            return False


# --- yt-dlp subtitle fallback ----------------------------------------------

_VTT_TIMESTAMP_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})"
)
_VTT_TAG_RE = re.compile(r"<[^>]+>")


def _vtt_ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_vtt(content: str) -> list[CaptionSegment]:
    """Parse WebVTT into caption segments.

    Handles YouTube auto-caption quirks: inline word-timing tags are
    stripped and rolling duplicate lines are collapsed.
    """
    segments: list[CaptionSegment] = []
    last_line = None

    for block in re.split(r"\n\s*\n", content):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        ts_match = None
        ts_index = -1
        for i, line in enumerate(lines):
            ts_match = _VTT_TIMESTAMP_RE.search(line)
            if ts_match:
                ts_index = i
                break
        if not ts_match:
            continue

        start = _vtt_ts_to_seconds(*ts_match.groups()[:4])
        end = _vtt_ts_to_seconds(*ts_match.groups()[4:])

        for raw in lines[ts_index + 1:]:
            text = _VTT_TAG_RE.sub("", raw)
            text = re.sub(r"\s+", " ", text).strip()
            if not text or text == last_line:
                continue
            segments.append(CaptionSegment(text=text, start=start, duration=end - start))
            last_line = text

    return segments


class YtDlpCaptionExtractor:
    """Fallback: download YouTube's own captions via yt-dlp.

    Uses yt-dlp's subtitle machinery (which shares its anti-bot handling,
    incl. optional PO-token provider plugins), so it often works when
    youtube-transcript-api is blocked. No audio/video is downloaded.
    """

    def __init__(self, preferred_languages: list[str] | None = None):
        self.preferred_languages = preferred_languages or ["en"]

    def extract(self, url_or_id: str) -> CaptionResult:
        video_id = CaptionExtractor.extract_video_id(url_or_id)
        url = f"https://www.youtube.com/watch?v={video_id}"
        sub_langs = ",".join(dict.fromkeys([*self.preferred_languages, "en.*"]))

        with tempfile.TemporaryDirectory(prefix="ytc-subs-") as tmp:
            # Manual subtitles first, then auto-generated
            for flag, is_generated in (("--write-subs", False), ("--write-auto-subs", True)):
                vtt = self._download_subs(url, Path(tmp), flag, sub_langs)
                if vtt is not None:
                    segments = parse_vtt(vtt.read_text(encoding="utf-8", errors="replace"))
                    if segments:
                        # Filename is <id>.<lang>.vtt
                        parts = vtt.name.split(".")
                        language = parts[-2] if len(parts) >= 3 else "unknown"
                        return CaptionResult(
                            video_id=video_id,
                            segments=segments,
                            language=language,
                            is_generated=is_generated,
                        )

        raise CaptionExtractionError(
            f"yt-dlp found no subtitles for video: {video_id}"
        )

    @staticmethod
    def _download_subs(url: str, tmp: Path, flag: str, sub_langs: str) -> Path | None:
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--skip-download",
            flag,
            "--sub-format", "vtt",
            "--sub-langs", sub_langs,
            "-o", str(tmp / "%(id)s.%(ext)s"),
            url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
        except subprocess.TimeoutExpired:
            return None
        except subprocess.CalledProcessError as e:
            raise CaptionExtractionError(f"yt-dlp subtitle download failed: {e.stderr}")

        vtts = sorted(tmp.glob("*.vtt"))
        return vtts[0] if vtts else None
