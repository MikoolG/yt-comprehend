"""Tier 3: Visual Analysis

Full video comprehension with scene detection, frame extraction, and OCR.
Extracts visual content like slides, code, diagrams alongside audio.

Requires additional dependencies:
    pip install "scenedetect[opencv]" paddlepaddle paddleocr imagededup pillow
"""

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Optional imports - may not be installed
try:
    from scenedetect import detect, ContentDetector, SceneManager
    from scenedetect.video_splitter import split_video_ffmpeg
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

try:
    from imagededup.methods import PHash
    IMAGEDEDUP_AVAILABLE = True
except ImportError:
    IMAGEDEDUP_AVAILABLE = False


@dataclass
class FrameContent:
    """Content extracted from a single video frame."""
    timestamp: float
    frame_path: Path
    ocr_text: str = ""
    confidence: float = 0.0
    scene_index: int = 0


@dataclass
class VisualResult:
    """Result from visual analysis."""
    frames: list[FrameContent]
    video_duration: float
    total_frames_extracted: int
    total_frames_after_dedup: int
    
    @property
    def text(self) -> str:
        """Get all OCR text concatenated."""
        return "\n\n".join(
            f"[{_format_time(f.timestamp)}] {f.ocr_text}"
            for f in self.frames
            if f.ocr_text.strip()
        )
    
    def text_with_context(self, audio_segments: list = None) -> str:
        """
        Combine visual OCR with audio transcript.
        
        Args:
            audio_segments: Optional list of audio segments to interleave
        """
        if not audio_segments:
            return self.text
        
        # Merge visual and audio by timestamp
        combined = []
        
        frame_idx = 0
        for seg in audio_segments:
            # Add any frames that occur before this segment ends
            while frame_idx < len(self.frames):
                frame = self.frames[frame_idx]
                if frame.timestamp <= seg.end:
                    if frame.ocr_text.strip():
                        combined.append(f"[VISUAL @ {_format_time(frame.timestamp)}]\n{frame.ocr_text}")
                    frame_idx += 1
                else:
                    break
            
            combined.append(f"[AUDIO @ {_format_time(seg.start)}]\n{seg.text}")
        
        # Add remaining frames
        for frame in self.frames[frame_idx:]:
            if frame.ocr_text.strip():
                combined.append(f"[VISUAL @ {_format_time(frame.timestamp)}]\n{frame.ocr_text}")
        
        return "\n\n".join(combined)


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class VisualExtractor:
    """Extract visual content from videos using scene detection and OCR."""
    
    def __init__(
        self,
        scene_threshold: float = 3.0,
        min_scene_duration: float = 2.0,
        ocr_engine: str = "paddleocr",
        deduplicate: bool = True,
        dedup_threshold: float = 0.95,
        max_frames: int = 100,
        temp_dir: Path | str | None = None,
    ):
        """
        Initialize the visual extractor.
        
        Args:
            scene_threshold: Sensitivity for scene detection (lower = more scenes)
            min_scene_duration: Minimum seconds between scene changes
            ocr_engine: OCR engine to use (paddleocr, tesseract)
            deduplicate: Whether to remove near-duplicate frames
            dedup_threshold: Similarity threshold for deduplication (0-1)
            max_frames: Maximum frames to process
            temp_dir: Directory for temporary files
        """
        self._check_dependencies()
        
        self.scene_threshold = scene_threshold
        self.min_scene_duration = min_scene_duration
        self.ocr_engine = ocr_engine
        self.deduplicate = deduplicate
        self.dedup_threshold = dedup_threshold
        self.max_frames = max_frames
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "yt-comprehend"
        
        self._ocr_model = None
    
    def _check_dependencies(self):
        """Check that required dependencies are available."""
        missing = []
        
        if not SCENEDETECT_AVAILABLE:
            missing.append("scenedetect[opencv]")
        if not PADDLEOCR_AVAILABLE:
            missing.append("paddleocr paddlepaddle")
        if not IMAGEDEDUP_AVAILABLE:
            missing.append("imagededup")
        
        if missing:
            raise VisualExtractionError(
                f"Missing dependencies for Tier 3 visual analysis. Install with:\n"
                f"pip install {' '.join(missing)}"
            )
    
    @property
    def ocr_model(self):
        """Lazy-load OCR model."""
        if self._ocr_model is None:
            if self.ocr_engine == "paddleocr":
                self._ocr_model = PaddleOCR(
                    use_angle_cls=True,
                    lang='en',
                    show_log=False,
                )
            else:
                raise VisualExtractionError(f"Unsupported OCR engine: {self.ocr_engine}")
        return self._ocr_model
    
    def download_video(self, url: str, output_path: Path | None = None) -> Path:
        """
        Download video from URL using yt-dlp.
        
        Args:
            url: Video URL
            output_path: Where to save the video
            
        Returns:
            Path to downloaded video
        """
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        if output_path is None:
            output_path = self.temp_dir / "video_%(id)s.%(ext)s"
        
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "-o", str(output_path),
            "--print", "after_move:filepath",
            url,
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            video_path = Path(result.stdout.strip().split('\n')[-1])
            
            if not video_path.exists():
                raise VisualExtractionError(f"Video not found at: {video_path}")
            
            return video_path
            
        except subprocess.CalledProcessError as e:
            raise VisualExtractionError(f"yt-dlp failed: {e.stderr}")
    
    def detect_scenes(self, video_path: Path) -> list[tuple[float, float]]:
        """
        Detect scene changes in video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            List of (start_time, end_time) tuples for each scene
        """
        scenes = detect(
            str(video_path),
            ContentDetector(threshold=self.scene_threshold, min_scene_len=int(self.min_scene_duration * 30)),
        )
        
        return [(s[0].get_seconds(), s[1].get_seconds()) for s in scenes]
    
    def extract_frames(
        self,
        video_path: Path,
        timestamps: list[float],
        output_dir: Path | None = None,
    ) -> list[Path]:
        """
        Extract frames at specific timestamps.
        
        Args:
            video_path: Path to video
            timestamps: List of timestamps (seconds) to extract
            output_dir: Where to save frames
            
        Returns:
            List of paths to extracted frame images
        """
        if output_dir is None:
            output_dir = self.temp_dir / "frames"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        frame_paths = []
        
        for i, ts in enumerate(timestamps[:self.max_frames]):
            output_path = output_dir / f"frame_{i:04d}_{ts:.1f}s.png"
            
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(output_path),
            ]
            
            try:
                subprocess.run(cmd, capture_output=True, check=True)
                if output_path.exists():
                    frame_paths.append(output_path)
            except subprocess.CalledProcessError:
                continue  # Skip failed frames
        
        return frame_paths
    
    def deduplicate_frames(self, frame_paths: list[Path]) -> list[Path]:
        """
        Remove near-duplicate frames using perceptual hashing.
        
        Args:
            frame_paths: List of frame image paths
            
        Returns:
            Filtered list with duplicates removed
        """
        if not frame_paths or not IMAGEDEDUP_AVAILABLE:
            return frame_paths
        
        # Get directory containing frames
        frame_dir = frame_paths[0].parent
        
        phasher = PHash()
        encodings = phasher.encode_images(image_dir=str(frame_dir))
        
        # Find duplicates
        duplicates = phasher.find_duplicates(
            encoding_map=encodings,
            max_distance_threshold=int((1 - self.dedup_threshold) * 64),  # Convert to hamming distance
        )
        
        # Build set of files to remove (keep first occurrence)
        to_remove = set()
        for original, dupes in duplicates.items():
            to_remove.update(dupes)
        
        # Filter frame paths
        return [p for p in frame_paths if p.name not in to_remove]
    
    def ocr_frame(self, frame_path: Path) -> tuple[str, float]:
        """
        Extract text from a frame using OCR.
        
        Args:
            frame_path: Path to frame image
            
        Returns:
            Tuple of (extracted_text, average_confidence)
        """
        result = self.ocr_model.ocr(str(frame_path), cls=True)
        
        if not result or not result[0]:
            return "", 0.0
        
        texts = []
        confidences = []
        
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0]
                conf = line[1][1]
                texts.append(text)
                confidences.append(conf)
        
        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return full_text, avg_conf
    
    def extract(
        self,
        url: str,
        keep_video: bool = False,
        keep_frames: bool = False,
        progress_callback: callable = None,
    ) -> VisualResult:
        """
        Full visual extraction pipeline.
        
        Args:
            url: Video URL
            keep_video: Whether to keep downloaded video
            keep_frames: Whether to keep extracted frames
            progress_callback: Optional callback for progress updates
            
        Returns:
            VisualResult with extracted visual content
        """
        video_path = None
        frame_dir = None
        
        try:
            # Download video
            if progress_callback:
                progress_callback("Downloading video...")
            video_path = self.download_video(url)
            
            # Detect scenes
            if progress_callback:
                progress_callback("Detecting scenes...")
            scenes = self.detect_scenes(video_path)
            
            # Get timestamps (middle of each scene)
            timestamps = [(s[0] + s[1]) / 2 for s in scenes]
            
            # If no scenes detected, sample at regular intervals
            if not timestamps:
                # Get video duration
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
                result = subprocess.run(cmd, capture_output=True, text=True)
                duration = float(result.stdout.strip())
                
                # Sample every 30 seconds
                timestamps = list(range(0, int(duration), 30))
            
            # Extract frames
            if progress_callback:
                progress_callback(f"Extracting {len(timestamps)} frames...")
            frame_paths = self.extract_frames(video_path, timestamps)
            total_extracted = len(frame_paths)
            
            # Deduplicate
            if self.deduplicate and frame_paths:
                if progress_callback:
                    progress_callback("Removing duplicate frames...")
                frame_paths = self.deduplicate_frames(frame_paths)
            
            # OCR each frame
            if progress_callback:
                progress_callback(f"Running OCR on {len(frame_paths)} frames...")
            
            frames = []
            for i, frame_path in enumerate(frame_paths):
                # Extract timestamp from filename
                ts = float(frame_path.stem.split('_')[-1].replace('s', ''))
                
                ocr_text, confidence = self.ocr_frame(frame_path)
                
                frames.append(FrameContent(
                    timestamp=ts,
                    frame_path=frame_path,
                    ocr_text=ocr_text,
                    confidence=confidence,
                    scene_index=i,
                ))
            
            # Get video duration for result
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0
            
            return VisualResult(
                frames=frames,
                video_duration=duration,
                total_frames_extracted=total_extracted,
                total_frames_after_dedup=len(frames),
            )
            
        finally:
            # Cleanup
            if video_path and video_path.exists() and not keep_video:
                try:
                    video_path.unlink()
                except Exception:
                    pass
            
            if not keep_frames and frame_paths:
                for fp in frame_paths:
                    try:
                        fp.unlink()
                    except Exception:
                        pass


class VisualExtractionError(Exception):
    """Raised when visual extraction fails."""
    pass
