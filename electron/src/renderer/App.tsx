import { useEffect } from 'react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { Header } from './components/Header'
import { FileTree } from './components/FileTree'
import { Editor } from './components/Editor'
import { Terminal } from './components/Terminal'
import { ProgressPanel } from './components/ProgressPanel'
import { Settings } from './components/Settings'
import { useAppStore } from './stores/app-store'

export default function App() {
  const {
    isProcessing,
    showSettings,
    setShowSettings,
    refreshFileTree,
    setOutputDir
  } = useAppStore()

  // Initialize app
  useEffect(() => {
    const init = async () => {
      // Get output directory
      const outputDir = await window.api.files.outputDir()
      setOutputDir(outputDir)

      // Start watching files
      await window.api.files.watch()

      // Initial file tree load
      await refreshFileTree()

      // Listen for file changes
      const unsubscribe = window.api.files.onChanged(() => {
        refreshFileTree()
      })

      return () => {
        unsubscribe()
        window.api.files.unwatch()
      }
    }

    init()
  }, [refreshFileTree, setOutputDir])

  return (
    <div className="h-screen flex flex-col bg-editor-bg text-text-primary">
      {/* Header with controls */}
      <Header />

      {/* Progress indicator when running */}
      {isProcessing && <ProgressPanel />}

      {/* Main content */}
      <Group orientation="vertical" className="flex-1 min-h-0">
        <Panel defaultSize="55%" minSize="20%">
          <Group orientation="horizontal" className="h-full">
            {/* File tree sidebar */}
            <Panel defaultSize="20%" minSize="15%" maxSize="40%">
              <div className="h-full">
                <FileTree />
              </div>
            </Panel>

            <Separator className="w-1 bg-border hover:bg-accent transition-colors" />

            {/* Editor */}
            <Panel defaultSize="80%">
              <div className="h-full">
                <Editor />
              </div>
            </Panel>
          </Group>
        </Panel>

        <Separator className="h-1 bg-border hover:bg-accent transition-colors" />

        {/* Terminal */}
        <Panel defaultSize="45%" minSize="20%">
          <div className="h-full">
            <Terminal />
          </div>
        </Panel>
      </Group>

      {/* Settings modal */}
      {showSettings && <Settings onClose={() => setShowSettings(false)} />}
    </div>
  )
}
