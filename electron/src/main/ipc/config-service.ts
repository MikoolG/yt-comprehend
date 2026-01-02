import { IpcMain } from 'electron'
import { readFile, writeFile } from 'fs/promises'
import { join } from 'path'
import { parse, stringify } from 'yaml'

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

let cachedConfig: Config | null = null

export function setupConfigService(
  ipcMain: IpcMain,
  getProjectRoot: () => string
): void {
  const getConfigPath = () => join(getProjectRoot(), 'config.yaml')

  // Get entire config
  ipcMain.handle('config:getAll', async () => {
    try {
      const configPath = getConfigPath()
      const content = await readFile(configPath, 'utf-8')
      cachedConfig = parse(content) as Config
      return { success: true, config: cachedConfig }
    } catch (error) {
      return { success: false, error: String(error), config: getDefaultConfig() }
    }
  })

  // Get specific config value
  ipcMain.handle('config:get', async (_event, key: string) => {
    try {
      if (!cachedConfig) {
        const configPath = getConfigPath()
        const content = await readFile(configPath, 'utf-8')
        cachedConfig = parse(content) as Config
      }

      const value = getNestedValue(cachedConfig, key)
      return { success: true, value }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  // Set specific config value
  ipcMain.handle('config:set', async (_event, key: string, value: unknown) => {
    try {
      const configPath = getConfigPath()

      // Read current config
      const content = await readFile(configPath, 'utf-8')
      const config = parse(content) as Config

      // Set nested value
      setNestedValue(config, key, value)

      // Write back
      await writeFile(configPath, stringify(config), 'utf-8')
      cachedConfig = config

      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  // Save entire config
  ipcMain.handle('config:save', async (_event, config: Config) => {
    try {
      const configPath = getConfigPath()
      await writeFile(configPath, stringify(config), 'utf-8')
      cachedConfig = config
      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })
}

function getNestedValue(obj: Record<string, unknown>, key: string): unknown {
  const keys = key.split('.')
  let current: unknown = obj

  for (const k of keys) {
    if (current && typeof current === 'object' && k in current) {
      current = (current as Record<string, unknown>)[k]
    } else {
      return undefined
    }
  }

  return current
}

function setNestedValue(
  obj: Record<string, unknown>,
  key: string,
  value: unknown
): void {
  const keys = key.split('.')
  let current = obj

  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i]
    if (!(k in current) || typeof current[k] !== 'object') {
      current[k] = {}
    }
    current = current[k] as Record<string, unknown>
  }

  current[keys[keys.length - 1]] = value
}

function getDefaultConfig(): Config {
  return {
    default_tier: 1,
    auto_escalate: true,
    whisper: {
      model: 'medium',
      device: 'auto',
      compute_type: 'int8',
      beam_size: 5,
      language: null,
      initial_prompt: null
    },
    visual: {
      scene_threshold: 3.0,
      ocr_engine: 'paddleocr',
      deduplicate: true,
      max_frames: 100
    },
    output: {
      directory: './output',
      format: 'markdown',
      include_timestamps: true,
      timestamp_interval: 30
    },
    cleanup: {
      delete_temp_files: true,
      keep_audio: false,
      keep_frames: false
    }
  }
}
