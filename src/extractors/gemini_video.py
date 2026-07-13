"""Gemini direct-URL tier: zero-download video comprehension.

Sends the YouTube URL straight to the Gemini API's video-understanding
endpoint - no yt-dlp, no Whisper, no local compute. Works on the free
tier (public videos only, currently up to 8 hours of YouTube video per
day; the YouTube-URL feature is flagged preview by Google).
"""

import os
from dataclasses import dataclass

TRANSCRIPT_PROMPT = """Watch this video and produce a detailed transcript-style breakdown in markdown.

Requirements:
- Transcribe the spoken content faithfully (light cleanup of filler words is fine).
- Group the content into sections with `[MM:SS]` timestamps at each section start.
- If the video shows important visual content (slides, code, diagrams, on-screen text),
  describe it inline in blockquotes where it appears.
- Do not summarize or editorialize - this is a transcript, not a summary.
"""


class GeminiVideoError(Exception):
    """Raised when Gemini direct video analysis fails."""
    pass


@dataclass
class GeminiVideoResult:
    """Result from Gemini direct-URL video analysis."""
    video_id: str
    text: str
    language: str = "unknown"


class GeminiVideoExtractor:
    """Analyze a YouTube video by URL via the Gemini API (free tier)."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-flash-latest"):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model = model

    def extract(self, url_or_id: str, progress_callback: callable = None) -> GeminiVideoResult:
        from .captions import CaptionExtractor

        video_id = CaptionExtractor.extract_video_id(url_or_id)
        url = f"https://www.youtube.com/watch?v={video_id}"

        if not self._api_key:
            raise GeminiVideoError(
                "Gemini direct tier requires a Gemini API key. "
                "Set GEMINI_API_KEY, pass --api-key, or configure in config.yaml"
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise GeminiVideoError(
                "google-genai package not installed. Run: pip install google-genai"
            )

        from ..summarize import gemini_model_chain, is_gemini_transient_error

        client = genai.Client(api_key=self._api_key)
        contents = types.Content(
            parts=[
                types.Part(file_data=types.FileData(file_uri=url)),
                types.Part(text=TRANSCRIPT_PROMPT),
            ]
        )

        models = gemini_model_chain(self._model)
        response = None
        for model in models:
            if progress_callback:
                progress_callback(f"Sending video URL to Gemini for direct analysis ({model})...")
            try:
                response = client.models.generate_content(model=model, contents=contents)
                break
            except Exception as e:
                if is_gemini_transient_error(e) and model != models[-1]:
                    if progress_callback:
                        progress_callback(f"{model} overloaded/rate-limited, trying next model...")
                    continue
                raise GeminiVideoError(f"Gemini video analysis failed: {e}") from e

        text = (response.text or "").strip() if response else ""
        if not text:
            raise GeminiVideoError("Gemini returned an empty response for this video.")

        return GeminiVideoResult(video_id=video_id, text=text)
