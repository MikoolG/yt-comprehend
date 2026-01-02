import { IpcMain, BrowserWindow } from 'electron'
import { readFile, writeFile, readdir, stat, mkdir } from 'fs/promises'
import { join, relative, basename, extname } from 'path'
import chokidar from 'chokidar'

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

let watcher: chokidar.FSWatcher | null = null

export function setupFileService(
  ipcMain: IpcMain,
  getProjectRoot: () => string
): void {
  // Read file contents
  ipcMain.handle('files:read', async (_event, filePath: string) => {
    try {
      const content = await readFile(filePath, 'utf-8')
      return { success: true, content }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  // Write file contents
  ipcMain.handle(
    'files:write',
    async (_event, filePath: string, content: string) => {
      try {
        await writeFile(filePath, content, 'utf-8')
        return { success: true }
      } catch (error) {
        return { success: false, error: String(error) }
      }
    }
  )

  // Get file tree for output directory
  ipcMain.handle('files:tree', async (_event, dirPath?: string) => {
    const root = getProjectRoot()
    const targetDir = dirPath || join(root, 'output')

    try {
      const tree = await buildFileTree(targetDir, root)
      return { success: true, tree }
    } catch (error) {
      return { success: false, error: String(error), tree: [] }
    }
  })

  // Start watching output directory
  ipcMain.handle('files:watch', async (_event, dirPath?: string) => {
    const root = getProjectRoot()
    const targetDir = dirPath || join(root, 'output')

    // Close existing watcher
    if (watcher) {
      await watcher.close()
    }

    // Ensure directory exists
    try {
      await mkdir(targetDir, { recursive: true })
    } catch {
      // Directory may already exist
    }

    watcher = chokidar.watch(targetDir, {
      persistent: true,
      ignoreInitial: true,
      depth: 10
    })

    watcher.on('all', (eventName, filePath) => {
      const windows = BrowserWindow.getAllWindows()
      windows.forEach((win) => {
        win.webContents.send('files:changed', {
          type: eventName,
          path: filePath
        } as FileEvent)
      })
    })

    return { success: true }
  })

  // Stop watching
  ipcMain.handle('files:unwatch', async () => {
    if (watcher) {
      await watcher.close()
      watcher = null
    }
    return { success: true }
  })

  // Get output directory path
  ipcMain.handle('files:outputDir', () => {
    return join(getProjectRoot(), 'output')
  })
}

async function buildFileTree(
  dirPath: string,
  projectRoot: string
): Promise<FileNode[]> {
  const nodes: FileNode[] = []

  try {
    const entries = await readdir(dirPath, { withFileTypes: true })

    // Sort: folders first, then files, alphabetically
    const sorted = entries.sort((a, b) => {
      if (a.isDirectory() && !b.isDirectory()) return -1
      if (!a.isDirectory() && b.isDirectory()) return 1
      return a.name.localeCompare(b.name)
    })

    for (const entry of sorted) {
      const fullPath = join(dirPath, entry.name)
      const relativePath = relative(projectRoot, fullPath)

      if (entry.isDirectory()) {
        const children = await buildFileTree(fullPath, projectRoot)
        nodes.push({
          id: fullPath,
          name: entry.name,
          path: fullPath,
          isFolder: true,
          children
        })
      } else {
        // Only include markdown, text, and json files
        const ext = extname(entry.name).toLowerCase()
        if (['.md', '.txt', '.json'].includes(ext)) {
          nodes.push({
            id: fullPath,
            name: entry.name,
            path: fullPath,
            isFolder: false
          })
        }
      }
    }
  } catch {
    // Directory doesn't exist or can't be read
  }

  return nodes
}
