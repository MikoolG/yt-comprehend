"""Core video comprehension engine.

Orchestrates the tiered extraction process and combines results.
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

from .extractors.captions import CaptionExtractor, CaptionExtractionError
from .extractors.audio import AudioExtractor, AudioExtractionError


@dataclass
class VideoMetadata:
    """Metadata about the analyzed video."""
    url: str
    video_id: str
    tier_used: int
    language: str
    duration: float | None = None
    has_visual_content: bool = False


@dataclass
class ComprehendResult:
    """Combined result from video comprehension."""
    metadata: VideoMetadata
    transcript_text: str
    transcript_segments: list
    visual_text: str = ""
    visual_frames: list = field(default_factory=list)
    
    @property
    def full_text(self) -> str:
        """Get complete extracted text (audio + visual)."""
        if self.visual_text:
            return f"## Audio Transcript\n\n{self.transcript_text}\n\n## Visual Content\n\n{self.visual_text}"
        return self.transcript_text
    
    def to_markdown(self, include_timestamps: bool = True, timestamp_interval: int = 30) -> str:
        """Format result as markdown for LLM consumption."""
        lines = [
            f"# Video Analysis",
            f"",
            f"**Source:** {self.metadata.url}",
            f"**Analysis Tier:** {self.metadata.tier_used}",
            f"**Language:** {self.metadata.language}",
        ]
        
        if self.metadata.duration:
            minutes = int(self.metadata.duration // 60)
            seconds = int(self.metadata.duration % 60)
            lines.append(f"**Duration:** {minutes}m {seconds}s")
        
        lines.extend(["", "---", "", "## Transcript", ""])
        
        if include_timestamps and hasattr(self.transcript_segments[0] if self.transcript_segments else None, 'start'):
            # Group by intervals
            lines.append(self._format_with_timestamps(self.transcript_segments, timestamp_interval))
        else:
            lines.append(self.transcript_text)
        
        if self.visual_text:
            lines.extend(["", "---", "", "## Visual Content (OCR)", ""])
            lines.append(self.visual_text)
        
        return "\n".join(lines)
    
    def _format_with_timestamps(self, segments: list, interval: int) -> str:
        """Format segments with timestamp groupings."""
        if not segments:
            return ""
        
        output_lines = []
        current_interval_start = 0
        current_texts = []
        
        for seg in segments:
            start = getattr(seg, 'start', 0)
            text = getattr(seg, 'text', str(seg))
            
            interval_num = int(start // interval)
            expected_start = interval_num * interval
            
            if expected_start > current_interval_start and current_texts:
                end_time = current_interval_start + interval
                output_lines.append(f"**[{self._format_time(current_interval_start)} - {self._format_time(end_time)}]**")
                output_lines.append(" ".join(current_texts))
                output_lines.append("")
                current_texts = []
                current_interval_start = expected_start
            
            current_texts.append(text.strip())
        
        if current_texts:
            output_lines.append(f"**[{self._format_time(current_interval_start)} - end]**")
            output_lines.append(" ".join(current_texts))
        
        return "\n".join(output_lines)
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"


class VideoComprehend:
    """Main video comprehension engine."""
    
    def __init__(self, config_path: Path | str | None = None):
        """
        Initialize the comprehension engine.
        
        Args:
            config_path: Path to config.yaml or None for defaults
        """
        self.config = self._load_config(config_path)
        
        # Initialize extractors lazily
        self._caption_extractor = None
        self._audio_extractor = None
        self._visual_extractor = None
    
    def _load_config(self, config_path: Path | str | None) -> dict:
        """Load configuration from file or use defaults."""
        defaults = {
            "default_tier": 1,
            "auto_escalate": True,
            "whisper": {
                "model": "medium",
                "device": "auto",
                "compute_type": "int8",
                "beam_size": 5,
                "language": None,
            },
            "visual": {
                "scene_threshold": 3.0,
                "ocr_engine": "paddleocr",
                "deduplicate": True,
                "max_frames": 100,
            },
            "output": {
                "format": "markdown",
                "include_timestamps": True,
                "timestamp_interval": 30,
            },
            "cleanup": {
                "delete_temp_files": True,
                "keep_audio": False,
                "keep_frames": False,
            },
        }
        
        if config_path:
            config_path = Path(config_path)
            if config_path.exists():
                with open(config_path) as f:
                    user_config = yaml.safe_load(f) or {}
                # Deep merge
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in defaults:
                        defaults[key].update(value)
                    else:
                        defaults[key] = value
        
        return defaults
    
    @property
    def caption_extractor(self) -> CaptionExtractor:
        """Get or create caption extractor."""
        if self._caption_extractor is None:
            self._caption_extractor = CaptionExtractor()
        return self._caption_extractor
    
    @property
    def audio_extractor(self) -> AudioExtractor:
        """Get or create audio extractor."""
        if self._audio_extractor is None:
            whisper_config = self.config.get("whisper", {})
            self._audio_extractor = AudioExtractor(
                model_name=whisper_config.get("model", "medium"),
                device=whisper_config.get("device", "auto"),
                compute_type=whisper_config.get("compute_type", "int8"),
                beam_size=whisper_config.get("beam_size", 5),
                language=whisper_config.get("language"),
            )
        return self._audio_extractor
    
    @property
    def visual_extractor(self):
        """Get or create visual extractor (may fail if deps not installed)."""
        if self._visual_extractor is None:
            try:
                from .extractors.visual import VisualExtractor
                visual_config = self.config.get("visual", {})
                self._visual_extractor = VisualExtractor(
                    scene_threshold=visual_config.get("scene_threshold", 3.0),
                    ocr_engine=visual_config.get("ocr_engine", "paddleocr"),
                    deduplicate=visual_config.get("deduplicate", True),
                    max_frames=visual_config.get("max_frames", 100),
                )
            except ImportError as e:
                raise RuntimeError(
                    "Tier 3 visual analysis requires additional dependencies. "
                    "Install with: pip install 'scenedetect[opencv]' paddlepaddle paddleocr imagededup"
                ) from e
        return self._visual_extractor
    
    def analyze(
        self,
        url: str,
        tier: int | None = None,
        auto_escalate: bool | None = None,
        progress_callback: callable = None,
    ) -> ComprehendResult:
        """
        Analyze a video and extract content.
        
        Args:
            url: Video URL (YouTube or other supported platform)
            tier: Force specific tier (1, 2, or 3) or None for default
            auto_escalate: Whether to try next tier if current fails
            progress_callback: Optional callback for progress updates
            
        Returns:
            ComprehendResult with extracted content
        """
        tier = tier or self.config.get("default_tier", 1)
        auto_escalate = auto_escalate if auto_escalate is not None else self.config.get("auto_escalate", True)
        
        # Extract video ID
        video_id = CaptionExtractor.extract_video_id(url)
        
        # Try Tier 1: Captions
        if tier <= 1:
            try:
                if progress_callback:
                    progress_callback("Trying caption extraction...")
                
                result = self.caption_extractor.extract(url)
                
                return ComprehendResult(
                    metadata=VideoMetadata(
                        url=url,
                        video_id=video_id,
                        tier_used=1,
                        language=result.language,
                    ),
                    transcript_text=result.text,
                    transcript_segments=result.segments,
                )
                
            except CaptionExtractionError as e:
                if not auto_escalate or tier > 1:
                    raise
                if progress_callback:
                    progress_callback(f"Captions unavailable: {e}. Escalating to Tier 2...")
                tier = 2
        
        # Try Tier 2: Audio transcription
        if tier <= 2:
            try:
                if progress_callback:
                    progress_callback("Starting audio transcription...")
                
                result = self.audio_extractor.extract(
                    url,
                    keep_audio=self.config.get("cleanup", {}).get("keep_audio", False),
                    progress_callback=progress_callback,
                )
                
                return ComprehendResult(
                    metadata=VideoMetadata(
                        url=url,
                        video_id=video_id,
                        tier_used=2,
                        language=result.language,
                        duration=result.duration,
                    ),
                    transcript_text=result.text,
                    transcript_segments=result.segments,
                )
                
            except AudioExtractionError as e:
                if not auto_escalate or tier > 2:
                    raise
                if progress_callback:
                    progress_callback(f"Audio transcription failed: {e}. Escalating to Tier 3...")
                tier = 3
        
        # Tier 3: Full visual analysis
        if tier == 3:
            if progress_callback:
                progress_callback("Starting full visual analysis...")
            
            # First get audio transcript
            audio_result = self.audio_extractor.extract(
                url,
                keep_audio=self.config.get("cleanup", {}).get("keep_audio", False),
                progress_callback=progress_callback,
            )
            
            # Then get visual content
            visual_result = self.visual_extractor.extract(
                url,
                keep_video=False,
                keep_frames=self.config.get("cleanup", {}).get("keep_frames", False),
                progress_callback=progress_callback,
            )
            
            return ComprehendResult(
                metadata=VideoMetadata(
                    url=url,
                    video_id=video_id,
                    tier_used=3,
                    language=audio_result.language,
                    duration=audio_result.duration,
                    has_visual_content=bool(visual_result.frames),
                ),
                transcript_text=audio_result.text,
                transcript_segments=audio_result.segments,
                visual_text=visual_result.text,
                visual_frames=visual_result.frames,
            )
        
        raise ValueError(f"Invalid tier: {tier}. Must be 1, 2, or 3.")
    
    def quick_transcript(self, url: str) -> str:
        """
        Quick method to just get transcript text.
        
        Tries captions first, falls back to audio.
        Returns plain text without metadata.
        """
        result = self.analyze(url, tier=1, auto_escalate=True)
        return result.transcript_text
