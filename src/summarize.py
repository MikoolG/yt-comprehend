"""LLM-based summarization for video transcripts.

Provider-agnostic: currently supports Gemini, extensible to any LLM API.
"""

import os
from pathlib import Path


class SummarizationError(Exception):
    """Error during summarization."""

    pass


SUMMARY_PROMPT = """You are an expert video content analyst. Given the following video transcript, generate a comprehensive summary in markdown format.

## Required Sections:

### Overview
What the video is about, who the speaker/presenter is (if identifiable), and the target audience.

### Key Points and Takeaways
A bulleted list of the most important points and actionable takeaways.

### Detailed Breakdown
A section-by-section breakdown of the video content, organized by topic. Use subheadings for each major topic discussed.

### Notable Mentions
Any tools, technologies, people, books, resources, or links mentioned in the video.

### Final Summary
A concise 2-3 paragraph summary capturing the essence of the video.

---

## Transcript:

{transcript}
"""

# Provider registry: provider name -> (env var for API key, default model, pip package)
PROVIDERS = {
    "gemini": {
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
        "package": "google-genai",
        "label": "Google Gemini",
    },
    "openai": {
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "package": "openai",
        "label": "OpenAI",
    },
    "anthropic": {
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-6",
        "package": "anthropic",
        "label": "Anthropic",
    },
}


def get_provider_info(provider: str) -> dict:
    """Get provider metadata. Returns defaults for unknown providers."""
    return PROVIDERS.get(provider, {
        "env_var": f"{provider.upper()}_API_KEY",
        "default_model": "",
        "package": provider,
        "label": provider.title(),
    })


class GeminiSummarizer:
    """Summarize transcripts using Google Gemini API."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash"):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model = model
        self._client = None

    @property
    def client(self):
        """Lazy-load the genai client."""
        if self._client is None:
            if not self._api_key:
                raise SummarizationError(
                    "No Gemini API key provided. Set GEMINI_API_KEY environment variable, "
                    "pass --api-key flag, or configure in config.yaml"
                )
            try:
                from google import genai

                self._client = genai.Client(api_key=self._api_key)
            except ImportError:
                raise SummarizationError(
                    "google-genai package not installed. Run: pip install google-genai"
                )
        return self._client

    def summarize(self, transcript_text: str, progress_callback: callable = None) -> str:
        from google.genai.types import GenerateContentConfig

        if progress_callback:
            progress_callback("Generating summary with Gemini...")

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text)

        try:
            response = self.client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=GenerateContentConfig(
                    max_output_tokens=8192,
                    thinking_config={"thinking_budget": 0},
                ),
            )
            return response.text.strip()
        except Exception as e:
            raise SummarizationError(f"Gemini API error: {e}") from e


class OpenAISummarizer:
    """Summarize transcripts using OpenAI API."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini"):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise SummarizationError(
                    "No OpenAI API key provided. Set OPENAI_API_KEY environment variable, "
                    "pass --api-key flag, or configure in config.yaml"
                )
            try:
                import openai

                self._client = openai.OpenAI(api_key=self._api_key)
            except ImportError:
                raise SummarizationError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    def summarize(self, transcript_text: str, progress_callback: callable = None) -> str:
        if progress_callback:
            progress_callback("Generating summary with OpenAI...")

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text)

        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise SummarizationError(f"OpenAI API error: {e}") from e


class AnthropicSummarizer:
    """Summarize transcripts using Anthropic API."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6"):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self._api_key:
                raise SummarizationError(
                    "No Anthropic API key provided. Set ANTHROPIC_API_KEY environment variable, "
                    "pass --api-key flag, or configure in config.yaml"
                )
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                raise SummarizationError(
                    "anthropic package not installed. Run: pip install anthropic"
                )
        return self._client

    def summarize(self, transcript_text: str, progress_callback: callable = None) -> str:
        if progress_callback:
            progress_callback("Generating summary with Anthropic...")

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text)

        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            raise SummarizationError(f"Anthropic API error: {e}") from e


def create_summarizer(
    provider: str = "gemini",
    api_key: str | None = None,
    model: str | None = None,
):
    """Factory: create a summarizer for the given provider.

    Args:
        provider: Provider name (gemini, openai, anthropic)
        api_key: API key (falls back to provider-specific env var)
        model: Model name (falls back to provider default)

    Returns:
        A summarizer instance with .summarize() method
    """
    info = get_provider_info(provider)
    resolved_model = model or info["default_model"]

    if provider == "gemini":
        return GeminiSummarizer(api_key=api_key, model=resolved_model)
    elif provider == "openai":
        return OpenAISummarizer(api_key=api_key, model=resolved_model)
    elif provider == "anthropic":
        return AnthropicSummarizer(api_key=api_key, model=resolved_model)
    else:
        raise SummarizationError(
            f"Unknown provider: {provider}. Supported: {', '.join(PROVIDERS.keys())}"
        )


def summarize_file(
    transcript_path: str | Path,
    output_path: str | Path | None = None,
    provider: str = "gemini",
    api_key: str | None = None,
    model: str | None = None,
    progress_callback: callable = None,
) -> Path:
    """Summarize a transcript file and save the result.

    Args:
        transcript_path: Path to the transcript file
        output_path: Path to save summary (auto-derived if None)
        provider: LLM provider name
        api_key: API key override
        model: Model name override
        progress_callback: Optional callback for progress updates

    Returns:
        Path to the saved summary file
    """
    transcript_path = Path(transcript_path)
    if not transcript_path.exists():
        raise SummarizationError(f"Transcript file not found: {transcript_path}")

    transcript_text = transcript_path.read_text()

    # Derive output path: /transcripts/ -> /summaries/
    if output_path is None:
        output_path = Path(str(transcript_path).replace("/transcripts/", "/summaries/"))
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    summarizer = create_summarizer(provider=provider, api_key=api_key, model=model)
    summary = summarizer.summarize(transcript_text, progress_callback)
    output_path.write_text(summary)

    return output_path
