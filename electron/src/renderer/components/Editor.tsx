import { useCallback, useEffect } from 'react'
import MonacoEditor from '@monaco-editor/react'
import { Save, X, FileText } from 'lucide-react'
import { useAppStore } from '../stores/app-store'
import clsx from 'clsx'

// Monaco worker configuration is in main.tsx

export function Editor() {
  const {
    selectedFile,
    setSelectedFile,
    fileContent,
    setFileContent,
    isDirty,
    setIsDirty
  } = useAppStore()

  // Get file extension for language detection
  const getLanguage = (path: string | null): string => {
    if (!path) return 'plaintext'
    if (path.endsWith('.md')) return 'markdown'
    if (path.endsWith('.json')) return 'json'
    if (path.endsWith('.txt')) return 'plaintext'
    return 'plaintext'
  }

  // Get filename from path
  const getFileName = (path: string | null): string => {
    if (!path) return ''
    return path.split('/').pop() || path
  }

  // Handle content change
  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (value !== undefined && value !== fileContent) {
        setFileContent(value)
        setIsDirty(true)
      }
    },
    [fileContent, setFileContent, setIsDirty]
  )

  // Save file
  const handleSave = useCallback(async () => {
    if (!selectedFile || !isDirty) return

    const result = await window.api.files.write(selectedFile, fileContent)
    if (result.success) {
      setIsDirty(false)
    } else {
      console.error('Failed to save file:', result.error)
    }
  }, [selectedFile, fileContent, isDirty, setIsDirty])

  // Close file
  const handleClose = useCallback(() => {
    setSelectedFile(null)
    setFileContent('')
    setIsDirty(false)
  }, [setSelectedFile, setFileContent, setIsDirty])

  // Keyboard shortcut: Ctrl+S to save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  // No file selected
  if (!selectedFile) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-editor-bg text-text-secondary">
        <FileText size={48} className="mb-4 opacity-30" />
        <p className="text-lg">No file selected</p>
        <p className="text-sm mt-2">
          Select a file from the sidebar to view or edit it.
        </p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-editor-bg overflow-hidden">
      {/* Tab bar */}
      <div className="flex items-center justify-between px-2 py-1 bg-sidebar-bg border-b border-border">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'text-sm px-2 py-1 rounded',
              isDirty ? 'text-yellow-400' : 'text-text-primary'
            )}
          >
            {getFileName(selectedFile)}
            {isDirty && ' *'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {isDirty && (
            <button
              onClick={handleSave}
              className="p-1.5 hover:bg-border rounded text-text-secondary hover:text-text-primary"
              title="Save (Ctrl+S)"
            >
              <Save size={16} />
            </button>
          )}
          <button
            onClick={handleClose}
            className="p-1.5 hover:bg-border rounded text-text-secondary hover:text-text-primary"
            title="Close"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <MonacoEditor
          height="100%"
          width="100%"
          language={getLanguage(selectedFile)}
          value={fileContent}
          onChange={handleEditorChange}
          theme="vs-dark"
          loading={<div className="flex items-center justify-center h-full text-text-secondary">Loading editor...</div>}
          options={{
            minimap: { enabled: false },
            wordWrap: 'on',
            fontSize: 14,
            fontFamily: 'JetBrains Mono, Menlo, Monaco, monospace',
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            padding: { top: 8 }
          }}
        />
      </div>
    </div>
  )
}
