import { useEffect, useRef, useCallback, useState } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { TerminalSquare, RefreshCw, Zap, Settings, Key, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import { useAppStore } from '../stores/app-store'
import '@xterm/xterm/css/xterm.css'

const TERMINAL_ID = 'main'

export function Terminal() {
  const containerRef = useRef<HTMLDivElement>(null)
  const terminalRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const isCleaningUpRef = useRef(false)
  const cleanupRef = useRef<(() => void) | null>(null)
  const { terminalReady, setTerminalReady, summarizeMode, setSummarizeMode, setShowSettings, isProcessing, currentProgress } = useAppStore()

  const PROVIDER_INFO: Record<string, { label: string; envVar: string; defaultModel: string }> = {
    gemini: { label: 'Google Gemini', envVar: 'GEMINI_API_KEY', defaultModel: 'gemini-2.5-flash' },
    openai: { label: 'OpenAI', envVar: 'OPENAI_API_KEY', defaultModel: 'gpt-4o-mini' },
    anthropic: { label: 'Anthropic', envVar: 'ANTHROPIC_API_KEY', defaultModel: 'claude-sonnet-4-6' }
  }

  const [providerName, setProviderName] = useState('gemini')

  // Load current provider from config
  useEffect(() => {
    if (summarizeMode !== 'api') return
    window.api.config.get('summarize.provider').then((result) => {
      if (result.success && result.value) {
        setProviderName(String(result.value))
      }
    })
  }, [summarizeMode])

  const info = PROVIDER_INFO[providerName] || {
    label: providerName.charAt(0).toUpperCase() + providerName.slice(1),
    envVar: `${providerName.toUpperCase()}_API_KEY`,
    defaultModel: 'default'
  }

  // Initialize terminal
  const initTerminal = useCallback(async () => {
    if (!containerRef.current || terminalRef.current) return

    const term = new XTerm({
      fontFamily: 'JetBrains Mono, Menlo, Monaco, Consolas, monospace',
      fontSize: 14,
      lineHeight: 1.2,
      cursorBlink: true,
      cursorStyle: 'block',
      scrollback: 10000,
      convertEol: true,
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        cursorAccent: '#1e1e1e',
        selectionBackground: '#264f78',
        black: '#1e1e1e',
        red: '#f44747',
        green: '#6a9955',
        yellow: '#dcdcaa',
        blue: '#569cd6',
        magenta: '#c586c0',
        cyan: '#4ec9b0',
        white: '#d4d4d4',
        brightBlack: '#808080',
        brightRed: '#f44747',
        brightGreen: '#6a9955',
        brightYellow: '#dcdcaa',
        brightBlue: '#569cd6',
        brightMagenta: '#c586c0',
        brightCyan: '#4ec9b0',
        brightWhite: '#ffffff'
      }
    })

    const fitAddon = new FitAddon()
    const webLinksAddon = new WebLinksAddon()

    term.loadAddon(fitAddon)
    term.loadAddon(webLinksAddon)

    term.open(containerRef.current)
    fitAddon.fit()

    terminalRef.current = term
    fitAddonRef.current = fitAddon

    // Create PTY in main process
    const result = await window.api.terminal.create(TERMINAL_ID)

    if (result.success) {
      // Connect terminal to PTY
      term.onData((data) => {
        window.api.terminal.write(TERMINAL_ID, data)
      })

      // Receive data from PTY - store cleanup function
      const unsubscribeData = window.api.terminal.onData(TERMINAL_ID, (data) => {
        term.write(data)
      })

      // Handle PTY exit - store cleanup function
      const unsubscribeExit = window.api.terminal.onExit(TERMINAL_ID, (code) => {
        // Only show exit message for errors (non-zero) and not during cleanup
        if (!isCleaningUpRef.current && code !== 0) {
          term.writeln(`\r\n\x1b[31mTerminal exited with code ${code}\x1b[0m`)
        }
        setTerminalReady(false)
      })

      // Store cleanup functions for later
      cleanupRef.current = () => {
        unsubscribeData()
        unsubscribeExit()
      }

      setTerminalReady(true)
    } else {
      term.writeln(`\x1b[31mFailed to create terminal: ${result.error}\x1b[0m`)
    }
  }, [setTerminalReady])

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (fitAddonRef.current && terminalRef.current) {
        fitAddonRef.current.fit()
        const { cols, rows } = terminalRef.current
        window.api.terminal.resize(TERMINAL_ID, cols, rows)
      }
    }

    window.addEventListener('resize', handleResize)

    // Also observe container size changes
    const observer = new ResizeObserver(handleResize)
    if (containerRef.current) {
      observer.observe(containerRef.current)
    }

    return () => {
      window.removeEventListener('resize', handleResize)
      observer.disconnect()
    }
  }, [])

  // Initialize on mount
  useEffect(() => {
    isCleaningUpRef.current = false
    initTerminal()

    return () => {
      isCleaningUpRef.current = true
      // Clean up IPC listeners
      if (cleanupRef.current) {
        cleanupRef.current()
        cleanupRef.current = null
      }
      if (terminalRef.current) {
        terminalRef.current.dispose()
        terminalRef.current = null
      }
      window.api.terminal.kill(TERMINAL_ID)
    }
  }, [initTerminal])

  // Restart terminal
  const handleRestart = useCallback(async () => {
    // Mark as cleaning up to suppress exit message
    isCleaningUpRef.current = true

    // Clean up IPC listeners
    if (cleanupRef.current) {
      cleanupRef.current()
      cleanupRef.current = null
    }

    // Kill existing terminal
    await window.api.terminal.kill(TERMINAL_ID)

    // Clear and dispose old terminal
    if (terminalRef.current) {
      terminalRef.current.dispose()
      terminalRef.current = null
    }

    setTerminalReady(false)
    isCleaningUpRef.current = false

    // Reinitialize
    await initTerminal()
  }, [initTerminal, setTerminalReady])

  return (
    <div className="h-full flex flex-col bg-editor-bg overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-1.5 bg-sidebar-bg border-b border-border">
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          {summarizeMode === 'claude' ? <TerminalSquare size={14} /> : <Zap size={14} />}
          <span>{summarizeMode === 'claude' ? 'Terminal' : `${info.label} API`}</span>
          {summarizeMode === 'claude' && terminalReady && (
            <span className="w-2 h-2 rounded-full bg-green-500" title="Connected" />
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Summarize mode toggle */}
          <div className="flex items-center rounded overflow-hidden border border-border text-xs mr-2" title="Summarization mode">
            <button
              onClick={() => setSummarizeMode('claude')}
              className={clsx(
                'px-2 py-0.5 transition-colors',
                summarizeMode === 'claude'
                  ? 'bg-accent text-white'
                  : 'text-text-secondary hover:text-text-primary'
              )}
            >
              Claude
            </button>
            <button
              onClick={() => setSummarizeMode('api')}
              className={clsx(
                'px-2 py-0.5 transition-colors',
                summarizeMode === 'api'
                  ? 'bg-accent text-white'
                  : 'text-text-secondary hover:text-text-primary'
              )}
            >
              API
            </button>
          </div>
          {summarizeMode === 'claude' && (
            <button
              onClick={handleRestart}
              className="p-1 hover:bg-border rounded text-text-secondary hover:text-text-primary"
              title="Restart Terminal"
            >
              <RefreshCw size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Terminal container (Claude mode) */}
      <div
        ref={containerRef}
        className={clsx(
          'flex-1 min-h-0 p-2 overflow-hidden',
          summarizeMode === 'api' && 'hidden'
        )}
      />

      {/* API mode info panel */}
      {summarizeMode === 'api' && (
        <div className="flex-1 min-h-0 flex flex-col items-center justify-center p-6">
          {(() => {
            const stage = currentProgress?.stage
            const isSummarizing = isProcessing && (stage === 'summarize' || stage === 'transcript_saved')
            const isSummaryDone = stage === 'summary_complete'
            const isSummaryError = stage === 'error' && currentProgress?.message?.includes('ummariz')
            const isExtracting = isProcessing && !isSummarizing && !isSummaryDone

            // Active state: show activity
            if (isProcessing || isSummaryDone) {
              return (
                <div className="max-w-sm text-center space-y-4">
                  {isExtracting && (
                    <>
                      <div className="flex justify-center">
                        <Loader2 size={32} className="text-accent animate-spin" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-text-primary mb-1">
                          Extracting Transcript
                        </h3>
                        <p className="text-xs text-text-secondary">
                          {currentProgress?.message || 'Processing...'}
                        </p>
                      </div>
                      {currentProgress && currentProgress.progress > 0 && (
                        <div className="w-full bg-border rounded-full h-1.5">
                          <div
                            className="bg-accent h-1.5 rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(currentProgress.progress, 100)}%` }}
                          />
                        </div>
                      )}
                    </>
                  )}
                  {isSummarizing && (
                    <>
                      <div className="flex justify-center">
                        <div className="relative">
                          <Loader2 size={32} className="text-accent animate-spin" />
                          <Zap size={14} className="text-accent absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                        </div>
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-text-primary mb-1">
                          Generating Summary
                        </h3>
                        <p className="text-xs text-text-secondary">
                          Using {info.label} to summarize transcript...
                        </p>
                      </div>
                      <div className="w-full bg-border rounded-full h-1.5">
                        <div
                          className="bg-accent h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(currentProgress?.progress || 92, 100)}%` }}
                        />
                      </div>
                    </>
                  )}
                  {isSummaryDone && (
                    <>
                      <div className="flex justify-center">
                        <CheckCircle2 size={32} className="text-green-500" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-text-primary mb-1">
                          Summary Complete
                        </h3>
                        <p className="text-xs text-text-secondary">
                          Summary has been saved and opened in the editor.
                        </p>
                      </div>
                    </>
                  )}
                </div>
              )
            }

            if (isSummaryError) {
              return (
                <div className="max-w-sm text-center space-y-4">
                  <div className="flex justify-center">
                    <AlertCircle size={32} className="text-red-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-text-primary mb-1">
                      Summarization Failed
                    </h3>
                    <p className="text-xs text-red-400">
                      {currentProgress?.message}
                    </p>
                    <p className="text-xs text-text-secondary mt-2">
                      Transcript was saved successfully. Check your API key and try again.
                    </p>
                  </div>
                </div>
              )
            }

            // Idle state: show setup info
            return (
              <div className="max-w-sm text-center space-y-4">
                <div className="flex justify-center">
                  <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
                    <Zap size={24} className="text-accent" />
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-text-primary mb-1">
                    {info.label} Summarization
                  </h3>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Summaries are generated automatically after transcript extraction.
                    Just press Execute and both transcript and summary will be saved.
                  </p>
                </div>
                <div className="text-left bg-sidebar-bg rounded-lg p-3 space-y-2">
                  <div className="flex items-start gap-2">
                    <Key size={12} className="text-text-secondary mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-text-secondary">
                      <span className="text-text-primary font-medium">API Key: </span>
                      Set <code className="bg-border px-1 rounded text-[11px]">{info.envVar}</code> env
                      var or configure in{' '}
                      <button
                        onClick={() => setShowSettings(true)}
                        className="text-accent hover:underline inline-flex items-center gap-0.5"
                      >
                        <Settings size={10} />
                        Settings
                      </button>
                    </p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Zap size={12} className="text-text-secondary mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-text-secondary">
                      <span className="text-text-primary font-medium">Model: </span>
                      {info.defaultModel} (default)
                    </p>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}
