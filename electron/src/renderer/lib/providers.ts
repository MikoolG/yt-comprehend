// Single source of truth for summarization providers in the renderer.
// Keep in sync with the PROVIDERS registry in src/summarize.py.

export interface ProviderInfo {
  label: string
  envVar: string
  defaultModel: string
  requiresKey: boolean
  models: { value: string; label: string }[]
}

export const PROVIDERS: Record<string, ProviderInfo> = {
  gemini: {
    label: 'Google Gemini (free tier)',
    envVar: 'GEMINI_API_KEY',
    defaultModel: 'gemini-flash-latest',
    requiresKey: true,
    models: [
      { value: '', label: 'Default (gemini-flash-latest)' },
      { value: 'gemini-flash-latest', label: 'gemini-flash-latest' },
      { value: 'gemini-2.5-flash', label: 'gemini-2.5-flash' },
      { value: 'gemini-2.5-flash-lite', label: 'gemini-2.5-flash-lite' },
      { value: 'gemini-2.5-pro', label: 'gemini-2.5-pro' }
    ]
  },
  openrouter: {
    label: 'OpenRouter (free models)',
    envVar: 'OPENROUTER_API_KEY',
    defaultModel: 'openrouter/free',
    requiresKey: true,
    models: [
      { value: '', label: 'Default (openrouter/free auto-router)' },
      { value: 'openrouter/free', label: 'openrouter/free (auto)' }
    ]
  },
  ollama: {
    label: 'Ollama (local)',
    envVar: 'OLLAMA_API_KEY',
    defaultModel: 'gemma3',
    requiresKey: false,
    models: [
      { value: '', label: 'Default (gemma3)' },
      { value: 'gemma3', label: 'gemma3' },
      { value: 'gemma3:12b', label: 'gemma3:12b' },
      { value: 'qwen3', label: 'qwen3' },
      { value: 'gpt-oss:20b', label: 'gpt-oss:20b' }
    ]
  },
  openai: {
    label: 'OpenAI',
    envVar: 'OPENAI_API_KEY',
    defaultModel: 'gpt-5.4-mini',
    requiresKey: true,
    models: [
      { value: '', label: 'Default (gpt-5.4-mini)' },
      { value: 'gpt-5.4-mini', label: 'gpt-5.4-mini' },
      { value: 'gpt-5.4-nano', label: 'gpt-5.4-nano' },
      { value: 'gpt-5.4', label: 'gpt-5.4' }
    ]
  },
  anthropic: {
    label: 'Anthropic',
    envVar: 'ANTHROPIC_API_KEY',
    defaultModel: 'claude-opus-4-8',
    requiresKey: true,
    models: [
      { value: '', label: 'Default (claude-opus-4-8)' },
      { value: 'claude-opus-4-8', label: 'claude-opus-4-8' },
      { value: 'claude-sonnet-5', label: 'claude-sonnet-5' },
      { value: 'claude-haiku-4-5', label: 'claude-haiku-4-5' }
    ]
  }
}

export function getProviderInfo(provider: string): ProviderInfo {
  return (
    PROVIDERS[provider] || {
      label: provider.charAt(0).toUpperCase() + provider.slice(1),
      envVar: `${provider.toUpperCase()}_API_KEY`,
      defaultModel: 'default',
      requiresKey: true,
      models: [{ value: '', label: 'Default' }]
    }
  )
}
