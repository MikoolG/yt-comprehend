import { useState, useEffect } from 'react'
import { X, Save } from 'lucide-react'

interface Config {
  default_tier: number
  auto_escalate: boolean
  whisper: {
    model: string
    device: string
    compute_type: string
    beam_size: number
    language: string | null
    initial_prompt: string | null
  }
  output: {
    directory: string
    format: string
    include_timestamps: boolean
    timestamp_interval: number
  }
}

interface SettingsProps {
  onClose: () => void
}

export function Settings({ onClose }: SettingsProps) {
  const [config, setConfig] = useState<Config | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load config on mount
  useEffect(() => {
    const loadConfig = async () => {
      const result = await window.api.config.getAll()
      if (result.success) {
        setConfig(result.config)
      } else {
        setError(result.error)
      }
      setLoading(false)
    }

    loadConfig()
  }, [])

  // Handle save
  const handleSave = async () => {
    if (!config) return

    setSaving(true)
    setError(null)

    const result = await window.api.config.save(config as never)
    if (result.success) {
      onClose()
    } else {
      setError(result.error)
    }

    setSaving(false)
  }

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-sidebar-bg rounded-lg p-6">
          <p className="text-text-secondary">Loading settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-sidebar-bg rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-border rounded text-text-secondary hover:text-text-primary"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {error && (
            <div className="bg-red-500/20 border border-red-500 text-red-400 px-4 py-2 rounded">
              {error}
            </div>
          )}

          {config && (
            <>
              {/* General */}
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase mb-3">
                  General
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Default Tier</label>
                    <select
                      value={config.default_tier}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          default_tier: Number(e.target.value)
                        })
                      }
                      className="w-40"
                    >
                      <option value={1}>1 - Captions</option>
                      <option value={2}>2 - Whisper</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Auto-escalate on failure</label>
                    <input
                      type="checkbox"
                      checked={config.auto_escalate}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          auto_escalate: e.target.checked
                        })
                      }
                      className="w-5 h-5"
                    />
                  </div>
                </div>
              </section>

              {/* Whisper */}
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase mb-3">
                  Whisper (Tier 2)
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Model</label>
                    <select
                      value={config.whisper.model}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          whisper: { ...config.whisper, model: e.target.value }
                        })
                      }
                      className="w-40"
                    >
                      <option value="tiny">tiny</option>
                      <option value="small">small</option>
                      <option value="medium">medium</option>
                      <option value="large-v3">large-v3</option>
                      <option value="large-v3-turbo">large-v3-turbo</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Device</label>
                    <select
                      value={config.whisper.device}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          whisper: { ...config.whisper, device: e.target.value }
                        })
                      }
                      className="w-40"
                    >
                      <option value="auto">auto</option>
                      <option value="cpu">cpu</option>
                      <option value="cuda">cuda</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Compute Type</label>
                    <select
                      value={config.whisper.compute_type}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          whisper: {
                            ...config.whisper,
                            compute_type: e.target.value
                          }
                        })
                      }
                      className="w-40"
                    >
                      <option value="int8">int8</option>
                      <option value="float16">float16</option>
                      <option value="float32">float32</option>
                    </select>
                  </div>
                </div>
              </section>

              {/* Output */}
              <section>
                <h3 className="text-sm font-semibold text-text-secondary uppercase mb-3">
                  Output
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Format</label>
                    <select
                      value={config.output.format}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          output: { ...config.output, format: e.target.value }
                        })
                      }
                      className="w-40"
                    >
                      <option value="markdown">Markdown</option>
                      <option value="plain">Plain Text</option>
                      <option value="json">JSON</option>
                    </select>
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Include Timestamps</label>
                    <input
                      type="checkbox"
                      checked={config.output.include_timestamps}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          output: {
                            ...config.output,
                            include_timestamps: e.target.checked
                          }
                        })
                      }
                      className="w-5 h-5"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <label className="text-sm">Timestamp Interval (sec)</label>
                    <input
                      type="number"
                      value={config.output.timestamp_interval}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          output: {
                            ...config.output,
                            timestamp_interval: Number(e.target.value)
                          }
                        })
                      }
                      className="w-20 text-center"
                      min={5}
                      max={300}
                    />
                  </div>
                </div>
              </section>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-border hover:bg-border/70 text-text-primary rounded"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded flex items-center gap-2"
          >
            <Save size={16} />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
