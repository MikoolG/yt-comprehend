import { IpcMain } from 'electron'
import { readFile, writeFile } from 'fs/promises'
import { join } from 'path'
import { parse, stringify } from 'yaml'

export interface Config {
  default_tier: number | string
  auto_escalate: boolean
  whisper: {
    model: string
    backend?: string
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
  summarize: {
    provider: string
    api_key: string | null
    model: string | null
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

      const value = getNestedValue(cachedConfig as unknown as Record<string, unknown>, key)
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
      setNestedValue(config as unknown as Record<string, unknown>, key, value)

      // Write back (never persist secrets into the git-tracked config.yaml)
      await writeFile(configPath, stringify(stripSecrets(config)), 'utf-8')
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
      await writeFile(configPath, stringify(stripSecrets(config)), 'utf-8')
      cachedConfig = config
      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  // Write an API key to the gitignored .env file (never to config.yaml)
  ipcMain.handle('config:setEnvKey', async (_event, envVar: string, value: string) => {
    try {
      if (!/^[A-Z][A-Z0-9_]*$/.test(envVar)) {
        return { success: false, error: `Invalid env var name: ${envVar}` }
      }
      const envPath = getEnvPath()
      let content = ''
      try {
        content = await readFile(envPath, 'utf-8')
      } catch {
        // No .env yet - will be created
      }

      const lines = content.split('\n')
      const prefix = `${envVar}=`
      let replaced = false
      const updated = lines.map((line) => {
        if (line.trim().startsWith(prefix)) {
          replaced = true
          return `${envVar}=${value}`
        }
        return line
      })
      if (!replaced) {
        while (updated.length && updated[updated.length - 1].trim() === '') updated.pop()
        updated.push(`${envVar}=${value}`)
      }

      await writeFile(envPath, updated.join('\n') + '\n', { encoding: 'utf-8', mode: 0o600 })
      return { success: true }
    } catch (error) {
      return { success: false, error: String(error) }
    }
  })

  // Report which env vars have values in .env (names only, never values)
  ipcMain.handle('config:getEnvKeys', async () => {
    try {
      const content = await readFile(getEnvPath(), 'utf-8')
      const keys: string[] = []
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) continue
        const eqIdx = trimmed.indexOf('=')
        if (eqIdx > 0 && trimmed.slice(eqIdx + 1).trim()) {
          keys.push(trimmed.slice(0, eqIdx).trim())
        }
      }
      return { success: true, keys }
    } catch {
      return { success: true, keys: [] }
    }
  })

  function getEnvPath(): string {
    return join(getProjectRoot(), '.env')
  }
}

// Never write API keys into the git-tracked config.yaml
function stripSecrets(config: Config): Config {
  return {
    ...config,
    summarize: { ...config.summarize, api_key: null }
  }
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
      model: 'large-v3-turbo',
      backend: 'local',
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
    },
    summarize: {
      provider: 'gemini',
      api_key: null,
      model: null
    }
  }
}
