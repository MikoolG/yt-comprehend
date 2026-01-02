import { contextBridge, ipcRenderer } from 'electron'

// Type definitions for the API
export interface FileNode {
  id: string
  name: string
  path: string
  isFolder: boolean
  children?: FileNode[]
}

export interface FileEvent {
  type: 'add' | 'change' | 'unlink' | 'addDir' | 'unlinkDir'
  path: string
}

export interface ProgressEvent {
  stage: string
  message: string
  progress: number
  timestamp: number
  output_path?: string
}

export interface YtComprehendOptions {
  url: string
  tier?: 1 | 2 | 3
  model?: string
  device?: 'auto' | 'cpu' | 'cuda'
  quiet?: boolean
  jsonProgress?: boolean
}

export interface CompletionResult {
  success: boolean
  exitCode: number
}

export interface Config {
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
  visual: {
    scene_threshold: number
    ocr_engine: string
    deduplicate: boolean
    max_frames: number
  }
  output: {
    directory: string
    format: string
    include_timestamps: boolean
    timestamp_interval: number
  }
  cleanup: {
    delete_temp_files: boolean
    keep_audio: boolean
    keep_frames: boolean
  }
}

// API exposed to renderer
const api = {
  // File operations
  files: {
    read: (path: string) => ipcRenderer.invoke('files:read', path),
    write: (path: string, content: string) =>
      ipcRenderer.invoke('files:write', path, content),
    getTree: (path?: string) => ipcRenderer.invoke('files:tree', path),
    watch: (path?: string) => ipcRenderer.invoke('files:watch', path),
    unwatch: () => ipcRenderer.invoke('files:unwatch'),
    outputDir: () => ipcRenderer.invoke('files:outputDir'),
    onChanged: (callback: (event: FileEvent) => void) => {
      const handler = (_: Electron.IpcRendererEvent, event: FileEvent) =>
        callback(event)
      ipcRenderer.on('files:changed', handler)
      return () => ipcRenderer.removeListener('files:changed', handler)
    }
  },

  // Terminal operations
  terminal: {
    create: (
      id: string,
      options?: { cwd?: string; shell?: string; env?: Record<string, string> }
    ) => ipcRenderer.invoke('terminal:create', id, options),
    write: (id: string, data: string) =>
      ipcRenderer.send('terminal:write', id, data),
    resize: (id: string, cols: number, rows: number) =>
      ipcRenderer.send('terminal:resize', id, cols, rows),
    kill: (id: string) => ipcRenderer.invoke('terminal:kill', id),
    list: () => ipcRenderer.invoke('terminal:list'),
    onData: (id: string, callback: (data: string) => void) => {
      const channel = `terminal:data:${id}`
      const handler = (_: Electron.IpcRendererEvent, data: string) =>
        callback(data)
      ipcRenderer.on(channel, handler)
      return () => ipcRenderer.removeListener(channel, handler)
    },
    onExit: (id: string, callback: (code: number) => void) => {
      const channel = `terminal:exit:${id}`
      const handler = (_: Electron.IpcRendererEvent, code: number) =>
        callback(code)
      ipcRenderer.on(channel, handler)
      return () => ipcRenderer.removeListener(channel, handler)
    }
  },

  // Process operations (yt-comprehend)
  process: {
    run: (options: YtComprehendOptions) =>
      ipcRenderer.invoke('process:run', options),
    kill: () => ipcRenderer.invoke('process:kill'),
    isRunning: () => ipcRenderer.invoke('process:isRunning'),
    onProgress: (callback: (event: ProgressEvent) => void) => {
      const handler = (_: Electron.IpcRendererEvent, event: ProgressEvent) =>
        callback(event)
      ipcRenderer.on('process:progress', handler)
      return () => ipcRenderer.removeListener('process:progress', handler)
    },
    onStdout: (callback: (data: string) => void) => {
      const handler = (_: Electron.IpcRendererEvent, data: string) =>
        callback(data)
      ipcRenderer.on('process:stdout', handler)
      return () => ipcRenderer.removeListener('process:stdout', handler)
    },
    onStderr: (callback: (data: string) => void) => {
      const handler = (_: Electron.IpcRendererEvent, data: string) =>
        callback(data)
      ipcRenderer.on('process:stderr', handler)
      return () => ipcRenderer.removeListener('process:stderr', handler)
    },
    onComplete: (callback: (result: CompletionResult) => void) => {
      const handler = (_: Electron.IpcRendererEvent, result: CompletionResult) =>
        callback(result)
      ipcRenderer.on('process:complete', handler)
      return () => ipcRenderer.removeListener('process:complete', handler)
    },
    onError: (callback: (error: string) => void) => {
      const handler = (_: Electron.IpcRendererEvent, error: string) =>
        callback(error)
      ipcRenderer.on('process:error', handler)
      return () => ipcRenderer.removeListener('process:error', handler)
    }
  },

  // Config operations
  config: {
    getAll: () => ipcRenderer.invoke('config:getAll'),
    get: (key: string) => ipcRenderer.invoke('config:get', key),
    set: (key: string, value: unknown) =>
      ipcRenderer.invoke('config:set', key, value),
    save: (config: Config) => ipcRenderer.invoke('config:save', config)
  },

  // App info
  app: {
    getProjectRoot: () => ipcRenderer.invoke('app:projectRoot'),
    getPythonPath: () => ipcRenderer.invoke('app:pythonPath')
  }
}

// Expose to renderer
contextBridge.exposeInMainWorld('api', api)

// Type declaration for window.api
export type ElectronAPI = typeof api
