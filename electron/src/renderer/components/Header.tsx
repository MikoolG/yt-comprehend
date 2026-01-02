import { useCallback, useEffect } from 'react'
import { Play, Square, Settings, Loader2, Clipboard } from 'lucide-react'
import { useAppStore } from '../stores/app-store'
import clsx from 'clsx'

export function Header() {
  const {
    url,
    setUrl,
    tier,
    setTier,
    isProcessing,
    setIsProcessing,
    setCurrentProgress,
    addProgressMessage,
    clearProgressMessages,
    refreshFileTree,
    setShowSettings,
    setSelectedFile
  } = useAppStore()

  // Handle paste from clipboard
  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (text) {
        setUrl(text.trim())
      }
    } catch (error) {
      console.error('Failed to read clipboard:', error)
    }
  }, [setUrl])

  // Handle execute
  const handleExecute = useCallback(async () => {
    if (!url.trim() || isProcessing) return

    setIsProcessing(true)
    clearProgressMessages()
    setCurrentProgress(null)

    try {
      await window.api.process.run({
        url: url.trim(),
        tier,
        jsonProgress: true
      })
    } catch (error) {
      addProgressMessage(`Error: ${error}`)
      setIsProcessing(false)
    }
  }, [
    url,
    tier,
    isProcessing,
    setIsProcessing,
    clearProgressMessages,
    setCurrentProgress,
    addProgressMessage
  ])

  // Handle stop
  const handleStop = useCallback(async () => {
    await window.api.process.kill()
    setIsProcessing(false)
    addProgressMessage('Process stopped by user')
  }, [setIsProcessing, addProgressMessage])

  // Auto-run Claude to summarize after transcript completes
  const runClaudeSummarize = useCallback((transcriptPath: string) => {
    // Derive summary path from transcript path
    const summaryPath = transcriptPath.replace('/transcripts/', '/summaries/')

    // Build the Claude command
    const claudePrompt = `Read the transcript at "${transcriptPath}" and generate a comprehensive summary including:
- Overview (what the video is about, target audience)
- Key points and takeaways
- Detailed breakdown by topic/section
- Notable mentions (tools, people, resources)
- Final summary

Save the summary to "${summaryPath}"`

    // Send command to terminal
    const command = `claude "${claudePrompt.replace(/"/g, '\\"').replace(/\n/g, ' ')}"\n`
    window.api.terminal.write('main', command)

    addProgressMessage('Starting Claude to generate summary...')
  }, [addProgressMessage])

  // Listen for process events
  useEffect(() => {
    const unsubProgress = window.api.process.onProgress((event) => {
      setCurrentProgress(event)
      addProgressMessage(`[${event.stage}] ${event.message}`)

      // If complete, auto-select the output file and run Claude
      if (event.stage === 'complete' && event.output_path) {
        setTimeout(() => {
          refreshFileTree()
          setSelectedFile(event.output_path!)
          // Auto-run Claude to summarize
          runClaudeSummarize(event.output_path!)
        }, 500)
      }
    })

    const unsubStdout = window.api.process.onStdout((data) => {
      addProgressMessage(data)
    })

    const unsubStderr = window.api.process.onStderr((data) => {
      addProgressMessage(`[stderr] ${data}`)
    })

    const unsubComplete = window.api.process.onComplete((result) => {
      setIsProcessing(false)
      if (result.success) {
        addProgressMessage('Completed successfully!')
        refreshFileTree()
      } else {
        addProgressMessage(`Process exited with code ${result.exitCode}`)
      }
    })

    const unsubError = window.api.process.onError((error) => {
      setIsProcessing(false)
      addProgressMessage(`Error: ${error}`)
    })

    return () => {
      unsubProgress()
      unsubStdout()
      unsubStderr()
      unsubComplete()
      unsubError()
    }
  }, [
    setCurrentProgress,
    addProgressMessage,
    setIsProcessing,
    refreshFileTree,
    setSelectedFile,
    runClaudeSummarize
  ])

  // Keyboard shortcut: Ctrl+Enter to execute
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'Enter' && !isProcessing) {
        handleExecute()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleExecute, isProcessing])

  return (
    <header className="bg-header-bg border-b border-border px-4 py-3 flex items-center gap-4">
      {/* URL Input */}
      <div className="flex-1 flex items-center gap-2">
        <label htmlFor="url" className="text-sm text-text-secondary whitespace-nowrap">
          Video URL:
        </label>
        <input
          id="url"
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://youtube.com/watch?v=... or video ID"
          className="flex-1 min-w-0"
          disabled={isProcessing}
        />
        <button
          onClick={handlePaste}
          disabled={isProcessing}
          className="bg-sidebar-bg hover:bg-border text-text-primary p-2"
          title="Paste from clipboard"
        >
          <Clipboard size={16} />
        </button>
      </div>

      {/* Tier Selector */}
      <div className="flex items-center gap-2">
        <label htmlFor="tier" className="text-sm text-text-secondary">
          Tier:
        </label>
        <select
          id="tier"
          value={tier}
          onChange={(e) => setTier(Number(e.target.value) as 1 | 2 | 3)}
          disabled={isProcessing}
          className="w-32"
        >
          <option value={1}>1 - Captions</option>
          <option value={2}>2 - Whisper</option>
          <option value={3} disabled>
            3 - Visual (soon)
          </option>
        </select>
      </div>

      {/* Execute/Stop Button */}
      {isProcessing ? (
        <button
          onClick={handleStop}
          className="bg-red-600 hover:bg-red-700 text-white flex items-center gap-2"
        >
          <Square size={16} />
          Stop
        </button>
      ) : (
        <button
          onClick={handleExecute}
          disabled={!url.trim()}
          className={clsx(
            'flex items-center gap-2 text-white',
            url.trim()
              ? 'bg-accent hover:bg-accent-hover'
              : 'bg-gray-600 cursor-not-allowed'
          )}
        >
          {isProcessing ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Play size={16} />
          )}
          Execute
        </button>
      )}

      {/* Settings Button */}
      <button
        onClick={() => setShowSettings(true)}
        className="bg-sidebar-bg hover:bg-border text-text-primary p-2"
        title="Settings"
      >
        <Settings size={18} />
      </button>
    </header>
  )
}
