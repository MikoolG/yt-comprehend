import { IpcMain, BrowserWindow } from 'electron'
import * as pty from 'node-pty'
import { join } from 'path'
import { platform, homedir } from 'os'

interface TerminalInstance {
  pty: pty.IPty
  id: string
}

const terminals = new Map<string, TerminalInstance>()

export function setupTerminalService(
  ipcMain: IpcMain,
  getProjectRoot: () => string
): void {
  // Create a new terminal
  ipcMain.handle(
    'terminal:create',
    (
      _event,
      id: string,
      options?: { cwd?: string; shell?: string; env?: Record<string, string> }
    ) => {
      const root = getProjectRoot()
      const shell =
        options?.shell ||
        process.env.SHELL ||
        (platform() === 'win32' ? 'powershell.exe' : '/bin/bash')

      // Build environment with venv activated
      const venvBin = join(root, 'venv', 'bin')
      const denoPath = join(homedir(), '.deno', 'bin')

      const env: Record<string, string> = {
        ...process.env,
        ...options?.env,
        PATH: `${venvBin}:${denoPath}:${process.env.PATH}`,
        VIRTUAL_ENV: join(root, 'venv'),
        PYTHONUNBUFFERED: '1',
        TERM: 'xterm-256color'
      }

      // Remove undefined values
      Object.keys(env).forEach((key) => {
        if (env[key] === undefined) delete env[key]
      })

      try {
        const ptyProcess = pty.spawn(shell, [], {
          name: 'xterm-256color',
          cols: 80,
          rows: 24,
          cwd: options?.cwd || root,
          env: env as { [key: string]: string }
        })

        // Send data to renderer
        ptyProcess.onData((data) => {
          const windows = BrowserWindow.getAllWindows()
          windows.forEach((win) => {
            win.webContents.send(`terminal:data:${id}`, data)
          })
        })

        // Handle exit
        ptyProcess.onExit(({ exitCode }) => {
          const windows = BrowserWindow.getAllWindows()
          windows.forEach((win) => {
            win.webContents.send(`terminal:exit:${id}`, exitCode)
          })
          terminals.delete(id)
        })

        terminals.set(id, { pty: ptyProcess, id })

        return { success: true, pid: ptyProcess.pid }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    }
  )

  // Write data to terminal
  ipcMain.on('terminal:write', (_event, id: string, data: string) => {
    const terminal = terminals.get(id)
    if (terminal) {
      terminal.pty.write(data)
    }
  })

  // Resize terminal
  ipcMain.on(
    'terminal:resize',
    (_event, id: string, cols: number, rows: number) => {
      const terminal = terminals.get(id)
      if (terminal) {
        terminal.pty.resize(cols, rows)
      }
    }
  )

  // Kill terminal
  ipcMain.handle('terminal:kill', (_event, id: string) => {
    const terminal = terminals.get(id)
    if (terminal) {
      terminal.pty.kill()
      terminals.delete(id)
      return { success: true }
    }
    return { success: false, error: 'Terminal not found' }
  })

  // List active terminals
  ipcMain.handle('terminal:list', () => {
    return Array.from(terminals.keys())
  })
}

// Cleanup on app quit
process.on('exit', () => {
  terminals.forEach((terminal) => {
    try {
      terminal.pty.kill()
    } catch {
      // Ignore errors during cleanup
    }
  })
})
