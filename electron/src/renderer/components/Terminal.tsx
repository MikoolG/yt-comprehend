import { useEffect, useRef, useCallback } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { TerminalSquare, RefreshCw } from 'lucide-react'
import { useAppStore } from '../stores/app-store'
import '@xterm/xterm/css/xterm.css'

const TERMINAL_ID = 'main'

export function Terminal() {
  const containerRef = useRef<HTMLDivElement>(null)
  const terminalRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const isCleaningUpRef = useRef(false)
  const cleanupRef = useRef<(() => void) | null>(null)
  const { terminalReady, setTerminalReady } = useAppStore()

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
        // Only show exit message if not cleaning up (e.g., intentional user exit)
        if (!isCleaningUpRef.current) {
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
          <TerminalSquare size={14} />
          <span>Terminal</span>
          {terminalReady && (
            <span className="w-2 h-2 rounded-full bg-green-500" title="Connected" />
          )}
        </div>
        <button
          onClick={handleRestart}
          className="p-1 hover:bg-border rounded text-text-secondary hover:text-text-primary"
          title="Restart Terminal"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Terminal container */}
      <div ref={containerRef} className="flex-1 min-h-0 p-2 overflow-hidden" />
    </div>
  )
}
