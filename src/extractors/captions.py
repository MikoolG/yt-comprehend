"""Tier 1: YouTube Caption Extraction

Fastest method - extracts existing captions directly from YouTube.
No download required, instant results.
"""

import re
from dataclasses import dataclass
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


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
        if not self.segments:
            return ""
        
        lines = []
        current_interval_start = 0
        current_texts = []
        
        for seg in self.segments:
            # Check if we've moved to a new interval
            interval_num = int(seg.start // interval)
            expected_start = interval_num * interval
            
            if expected_start > current_interval_start and current_texts:
                # Output previous interval
                end_time = current_interval_start + interval
                lines.append(f"[{_format_time(current_interval_start)} - {_format_time(end_time)}]")
                lines.append(" ".join(current_texts))
                lines.append("")
                current_texts = []
                current_interval_start = expected_start
            
            current_texts.append(seg.text)
        
        # Don't forget the last interval
        if current_texts:
            lines.append(f"[{_format_time(current_interval_start)} - end]")
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


class CaptionExtractor:
    """Extract captions from YouTube videos."""
    
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
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
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
            CaptionExtractionError: If captions cannot be retrieved
        """
        video_id = self.extract_video_id(url_or_id)
        
        try:
            # List available transcripts (API v1.x uses .list() instead of .list_transcripts())
            transcript_list = self._api.list(video_id)

            # Try to find preferred language (manual first, then auto-generated)
            transcript = None
            is_generated = False

            # First try manual transcripts
            for lang in self.preferred_languages:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    is_generated = transcript.is_generated
                    break
                except NoTranscriptFound:
                    continue

            # If no manual found, try any available and translate
            if transcript is None:
                try:
                    # Get any available transcript
                    transcript = next(iter(transcript_list))
                    is_generated = transcript.is_generated

                    # Try to translate to preferred language if different
                    if transcript.language_code not in self.preferred_languages:
                        try:
                            transcript = transcript.translate(self.preferred_languages[0])
                        except Exception:
                            pass  # Keep original if translation fails

                except StopIteration:
                    raise CaptionExtractionError(
                        f"No transcripts available for video: {video_id}"
                    )

            # Fetch the actual transcript data
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


class CaptionExtractionError(Exception):
    """Raised when caption extraction fails."""
    pass
