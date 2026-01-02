import { create } from 'zustand'

export interface FileNode {
  id: string
  name: string
  path: string
  isFolder: boolean
  children?: FileNode[]
}

export interface ProgressEvent {
  stage: string
  message: string
  progress: number
  timestamp: number
  output_path?: string
}

interface AppState {
  // URL input
  url: string
  setUrl: (url: string) => void

  // Tier selection
  tier: 1 | 2 | 3
  setTier: (tier: 1 | 2 | 3) => void

  // Processing state
  isProcessing: boolean
  setIsProcessing: (isProcessing: boolean) => void

  // Progress
  currentProgress: ProgressEvent | null
  setCurrentProgress: (progress: ProgressEvent | null) => void
  progressMessages: string[]
  addProgressMessage: (message: string) => void
  clearProgressMessages: () => void

  // File tree
  fileTree: FileNode[]
  setFileTree: (tree: FileNode[]) => void
  refreshFileTree: () => Promise<void>

  // Selected file
  selectedFile: string | null
  setSelectedFile: (path: string | null) => void

  // File content
  fileContent: string
  setFileContent: (content: string) => void
  isDirty: boolean
  setIsDirty: (dirty: boolean) => void

  // Terminal
  terminalReady: boolean
  setTerminalReady: (ready: boolean) => void

  // Settings panel
  showSettings: boolean
  setShowSettings: (show: boolean) => void

  // Output directory
  outputDir: string
  setOutputDir: (dir: string) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  // URL
  url: '',
  setUrl: (url) => set({ url }),

  // Tier
  tier: 1,
  setTier: (tier) => set({ tier }),

  // Processing
  isProcessing: false,
  setIsProcessing: (isProcessing) => set({ isProcessing }),

  // Progress
  currentProgress: null,
  setCurrentProgress: (progress) => set({ currentProgress: progress }),
  progressMessages: [],
  addProgressMessage: (message) =>
    set((state) => ({
      progressMessages: [...state.progressMessages.slice(-50), message]
    })),
  clearProgressMessages: () => set({ progressMessages: [] }),

  // File tree
  fileTree: [],
  setFileTree: (tree) => set({ fileTree: tree }),
  refreshFileTree: async () => {
    try {
      const result = await window.api.files.getTree()
      if (result.success) {
        set({ fileTree: result.tree })
      }
    } catch (error) {
      console.error('Failed to refresh file tree:', error)
    }
  },

  // Selected file
  selectedFile: null,
  setSelectedFile: (path) => set({ selectedFile: path }),

  // File content
  fileContent: '',
  setFileContent: (content) => set({ fileContent: content }),
  isDirty: false,
  setIsDirty: (dirty) => set({ isDirty: dirty }),

  // Terminal
  terminalReady: false,
  setTerminalReady: (ready) => set({ terminalReady: ready }),

  // Settings
  showSettings: false,
  setShowSettings: (show) => set({ showSettings: show }),

  // Output dir
  outputDir: '',
  setOutputDir: (dir) => set({ outputDir: dir })
}))
