"""LLM-based summarization for video transcripts.

Provider-agnostic, free-first. Two code paths:
- Gemini via the native google-genai SDK (default; free tier handles
  100k+ token transcripts in one shot thanks to the 1M context window)
- Everything else via one OpenAI-compatible adapter with a per-provider
  base_url (OpenAI, OpenRouter free models, local Ollama) plus a native
  Anthropic path.
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

# Provider registry.
#   kind: "gemini" (native SDK) | "anthropic" (native SDK) | "openai_compat"
#   base_url: only for openai_compat (None = api.openai.com)
#   requires_key: Ollama runs locally without a key
PROVIDERS = {
    "gemini": {
        "kind": "gemini",
        "env_var": "GEMINI_API_KEY",
        "default_model": "gemini-flash-latest",
        "label": "Google Gemini",
        "requires_key": True,
    },
    "openai": {
        "kind": "openai_compat",
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-5.4-mini",
        "base_url": None,
        "label": "OpenAI",
        "requires_key": True,
    },
    "anthropic": {
        "kind": "anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-opus-4-8",
        "label": "Anthropic",
        "requires_key": True,
    },
    "openrouter": {
        "kind": "openai_compat",
        "env_var": "OPENROUTER_API_KEY",
        "default_model": "openrouter/free",  # auto-routes across free models
        "base_url": "https://openrouter.ai/api/v1",
        "label": "OpenRouter (free models)",
        "requires_key": True,
    },
    "ollama": {
        "kind": "openai_compat",
        "env_var": "OLLAMA_API_KEY",  # unused by default; local server needs no key
        "default_model": "gemma3",
        "base_url": "http://localhost:11434/v1",
        "label": "Ollama (local)",
        "requires_key": False,
    },
}


def get_provider_info(provider: str) -> dict:
    """Get provider metadata. Returns defaults for unknown providers."""
    return PROVIDERS.get(provider, {
        "kind": "openai_compat",
        "env_var": f"{provider.upper()}_API_KEY",
        "default_model": "",
        "base_url": None,
        "label": provider.title(),
        "requires_key": True,
    })


# Free-tier models get overloaded (503) or rate-limited (429); trying the
# next-best free model is usually enough to get a result.
GEMINI_FALLBACK_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def is_gemini_transient_error(error: Exception) -> bool:
    """True for overload/quota errors where another Gemini model may work."""
    text = str(error)
    return any(marker in text for marker in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"))


def gemini_model_chain(preferred: str) -> list[str]:
    """Preferred model first, then the free fallback chain (deduplicated)."""
    return list(dict.fromkeys([preferred, *GEMINI_FALLBACK_MODELS]))


class GeminiSummarizer:
    """Summarize transcripts using the Google Gemini API (native SDK)."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-flash-latest"):
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

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text)
        models = gemini_model_chain(self._model)
        last_error = None

        for model in models:
            if progress_callback:
                progress_callback(f"Generating summary with Gemini ({model})...")
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=GenerateContentConfig(max_output_tokens=16384),
                )
                if not response.text:
                    raise SummarizationError("Gemini returned an empty response")
                return response.text.strip()
            except SummarizationError:
                raise
            except Exception as e:
                last_error = e
                if is_gemini_transient_error(e) and model != models[-1]:
                    if progress_callback:
                        progress_callback(f"{model} overloaded/rate-limited, trying next model...")
                    continue
                raise SummarizationError(f"Gemini API error: {e}") from e

        raise SummarizationError(f"Gemini API error: {last_error}") from last_error


class OpenAICompatSummarizer:
    """Summarize via any OpenAI-compatible endpoint (OpenAI, OpenRouter, Ollama, ...)."""

    def __init__(
        self,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
    ):
        info = get_provider_info(provider)
        self._provider = provider
        self._label = info["label"]
        self._base_url = info.get("base_url")
        self._requires_key = info.get("requires_key", True)
        self._api_key = api_key or os.environ.get(info["env_var"])
        self._model = model or info["default_model"]
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if self._requires_key and not self._api_key:
                info = get_provider_info(self._provider)
                raise SummarizationError(
                    f"No {self._label} API key provided. Set {info['env_var']}, "
                    "pass --api-key flag, or configure in config.yaml"
                )
            try:
                import openai

                self._client = openai.OpenAI(
                    api_key=self._api_key or "not-needed",
                    base_url=self._base_url,
                )
            except ImportError:
                raise SummarizationError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    def summarize(self, transcript_text: str, progress_callback: callable = None) -> str:
        if progress_callback:
            progress_callback(f"Generating summary with {self._label} ({self._model})...")

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text)

        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            if not content:
                raise SummarizationError(f"{self._label} returned an empty response")
            return content.strip()
        except SummarizationError:
            raise
        except Exception as e:
            raise SummarizationError(f"{self._label} API error: {e}") from e


class AnthropicSummarizer:
    """Summarize transcripts using the Anthropic API (native SDK)."""

    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-8"):
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
            progress_callback(f"Generating summary with Anthropic ({self._model})...")

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text)

        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            if response.stop_reason == "refusal":
                raise SummarizationError("Anthropic declined to process this transcript")
            return response.content[0].text.strip()
        except SummarizationError:
            raise
        except Exception as e:
            raise SummarizationError(f"Anthropic API error: {e}") from e


def create_summarizer(
    provider: str = "gemini",
    api_key: str | None = None,
    model: str | None = None,
):
    """Factory: create a summarizer for the given provider.

    Args:
        provider: Provider name (gemini, openai, anthropic, openrouter, ollama)
        api_key: API key (falls back to provider-specific env var)
        model: Model name (falls back to provider default)

    Returns:
        A summarizer instance with .summarize() method
    """
    info = get_provider_info(provider)
    resolved_model = model or info["default_model"]
    kind = info["kind"]

    if kind == "gemini":
        return GeminiSummarizer(api_key=api_key, model=resolved_model)
    if kind == "anthropic":
        return AnthropicSummarizer(api_key=api_key, model=resolved_model)
    if kind == "openai_compat":
        if not resolved_model:
            raise SummarizationError(
                f"Unknown provider: {provider}. Supported: {', '.join(PROVIDERS.keys())} "
                "(or pass --summarize-model for a custom OpenAI-compatible provider)"
            )
        return OpenAICompatSummarizer(provider, api_key=api_key, model=resolved_model)

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
