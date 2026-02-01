import { app, BrowserWindow, ipcMain, shell, Menu } from 'electron'
import { join } from 'path'
import { spawn } from 'child_process'
import { homedir } from 'os'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { setupFileService } from './ipc/file-service'
import { setupTerminalService } from './ipc/terminal-service'
import { setupProcessService } from './ipc/process-service'
import { setupConfigService } from './ipc/config-service'

// Update yt-dlp in background on startup
function updateYtDlp(projectRoot: string): void {
  const venvBin = join(projectRoot, 'venv', 'bin')
  const pipPath = join(venvBin, 'pip')
  const denoPath = join(homedir(), '.deno', 'bin')

  const env = {
    ...process.env,
    PATH: `${venvBin}:${denoPath}:${process.env.PATH}`,
    VIRTUAL_ENV: join(projectRoot, 'venv')
  }

  console.log('[yt-dlp] Checking for updates...')

  const proc = spawn(pipPath, ['install', '-U', 'yt-dlp'], {
    cwd: projectRoot,
    env: env as NodeJS.ProcessEnv,
    stdio: 'pipe'
  })

  proc.stdout?.on('data', (data: Buffer) => {
    const text = data.toString().trim()
    if (text.includes('Successfully installed')) {
      console.log('[yt-dlp] Updated:', text)
    }
  })

  proc.on('close', (code) => {
    if (code === 0) {
      console.log('[yt-dlp] Update check complete')
    } else {
      console.log('[yt-dlp] Update check failed with code:', code)
    }
  })

  proc.on('error', (err) => {
    console.log('[yt-dlp] Update check error:', err.message)
  })
}

let mainWindow: BrowserWindow | null = null

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: '#1e1e1e',
    webPreferences: {
      preload: join(__dirname, '../preload/index.mjs'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // Enable right-click context menu
  mainWindow.webContents.on('context-menu', (_event, params) => {
    const menu = Menu.buildFromTemplate([
      { label: 'Cut', role: 'cut', enabled: params.editFlags.canCut },
      { label: 'Copy', role: 'copy', enabled: params.editFlags.canCopy },
      { label: 'Paste', role: 'paste', enabled: params.editFlags.canPaste },
      { type: 'separator' },
      { label: 'Select All', role: 'selectAll' }
    ])
    menu.popup()
  })

  // Load the renderer
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// Get project root (parent of electron directory)
export function getProjectRoot(): string {
  // __dirname is electron/out/main
  // We need to go up to yt-comprehend root (3 levels up from out/main, then out of electron)
  // out/main -> out -> electron -> yt-comprehend
  return join(__dirname, '..', '..', '..')
}

app.whenReady().then(() => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.yt-comprehend.ui')

  // Default open or close DevTools by F12 in development
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Update yt-dlp in background (non-blocking)
  updateYtDlp(getProjectRoot())

  // Setup IPC services
  setupFileService(ipcMain, getProjectRoot)
  setupTerminalService(ipcMain, getProjectRoot)
  setupProcessService(ipcMain, getProjectRoot)
  setupConfigService(ipcMain, getProjectRoot)

  // App info
  ipcMain.handle('app:projectRoot', () => getProjectRoot())
  ipcMain.handle('app:pythonPath', () => {
    const root = getProjectRoot()
    return join(root, 'venv', 'bin', 'python')
  })

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
