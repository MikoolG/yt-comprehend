import { IpcMain, BrowserWindow } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import { readFile } from 'fs/promises'
import { join } from 'path'
import { homedir } from 'os'
import { parse } from 'yaml'

export interface YtComprehendOptions {
  url: string
  tier?: 1 | 2 | 3
  model?: string
  device?: 'auto' | 'cpu' | 'cuda'
  quiet?: boolean
  jsonProgress?: boolean
  summarize?: boolean
}

export interface ProgressEvent {
  stage: string
  message: string
  progress: number
  timestamp: number
  output_path?: string
}

let currentProcess: ChildProcess | null = null

export function setupProcessService(
  ipcMain: IpcMain,
  getProjectRoot: () => string
): void {
  // Run yt-comprehend
  ipcMain.handle('process:run', async (_event, options: YtComprehendOptions) => {
    const root = getProjectRoot()

    // Kill any existing process
    if (currentProcess) {
      currentProcess.kill()
      currentProcess = null
    }

    // Build command arguments
    const args: string[] = [options.url]

    if (options.tier) {
      args.push('--tier', String(options.tier))
    }
    if (options.model) {
      args.push('--model', options.model)
    }
    if (options.device) {
      args.push('--device', options.device)
    }
    if (options.quiet) {
      args.push('--quiet')
    }
    if (options.jsonProgress) {
      args.push('--json-progress')
    }
    if (options.summarize) {
      args.push('--summarize')
    }

    // Load .env file from project root
    const dotEnv: Record<string, string> = {}
    try {
      const envContent = await readFile(join(root, '.env'), 'utf-8')
      for (const line of envContent.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) continue
        const eqIdx = trimmed.indexOf('=')
        if (eqIdx > 0) {
          dotEnv[trimmed.slice(0, eqIdx).trim()] = trimmed.slice(eqIdx + 1).trim()
        }
      }
    } catch {
      // No .env file, that's fine
    }

    // Read config to get API key + provider for environment (Settings UI override)
    let configEnv: Record<string, string> = {}
    try {
      const configContent = await readFile(join(root, 'config.yaml'), 'utf-8')
      const config = parse(configContent) as Record<string, unknown>
      const summarizeConfig = config.summarize as Record<string, unknown> | undefined
      if (summarizeConfig?.api_key) {
        const provider = String(summarizeConfig.provider || 'gemini')
        configEnv[`${provider.toUpperCase()}_API_KEY`] = String(summarizeConfig.api_key)
      }
    } catch {
      // Config read failed, continue without
    }

    // Environment with venv activated
    const venvBin = join(root, 'venv', 'bin')
    const denoPath = join(homedir(), '.deno', 'bin')

    // Priority: config.yaml (Settings UI) > .env file > system env
    const env: Record<string, string> = {
      ...process.env,
      ...dotEnv,
      ...configEnv,
      PATH: `${venvBin}:${denoPath}:${process.env.PATH}`,
      VIRTUAL_ENV: join(root, 'venv'),
      PYTHONUNBUFFERED: '1'
    }

    // Remove undefined values
    Object.keys(env).forEach((key) => {
      if (env[key] === undefined) delete env[key]
    })

    // Use Python directly to avoid calling Electron app
    const pythonPath = join(root, 'venv', 'bin', 'python')
    const cliPath = join(root, 'src', 'cli.py')

    console.log('[process-service] Running:', pythonPath, cliPath, args)
    console.log('[process-service] CWD:', root)

    return new Promise((resolve) => {
      try {
        currentProcess = spawn(pythonPath, [cliPath, ...args], {
          cwd: root,
          env: env as NodeJS.ProcessEnv
        })

        const pid = currentProcess.pid
        console.log('[process-service] Process started, PID:', pid)

        // Helper to broadcast to all windows (gets fresh window list each time)
        const broadcast = (channel: string, data: unknown) => {
          BrowserWindow.getAllWindows().forEach((win) => {
            if (!win.isDestroyed()) {
              win.webContents.send(channel, data)
            }
          })
        }

        currentProcess.stdout?.on('data', (data: Buffer) => {
          const text = data.toString()

          // Try to parse JSON progress events
          const lines = text.split('\n').filter((l) => l.trim())
          for (const line of lines) {
            try {
              const event = JSON.parse(line) as ProgressEvent
              broadcast('process:progress', event)
            } catch {
              // Not JSON, send as raw stdout
              broadcast('process:stdout', line)
            }
          }
        })

        currentProcess.stderr?.on('data', (data: Buffer) => {
          const text = data.toString()
          broadcast('process:stderr', text)
        })

        currentProcess.on('close', (code) => {
          broadcast('process:complete', {
            success: code === 0,
            exitCode: code
          })
          currentProcess = null
        })

        currentProcess.on('error', (error) => {
          broadcast('process:error', String(error))
          currentProcess = null
          resolve({ success: false, error: String(error) })
        })

        resolve({ success: true, pid })
      } catch (error) {
        resolve({ success: false, error: String(error) })
      }
    })
  })

  // Kill current process
  ipcMain.handle('process:kill', () => {
    if (currentProcess) {
      currentProcess.kill()
      currentProcess = null
      return { success: true }
    }
    return { success: false, error: 'No process running' }
  })

  // Check if process is running
  ipcMain.handle('process:isRunning', () => {
    return currentProcess !== null
  })
}
