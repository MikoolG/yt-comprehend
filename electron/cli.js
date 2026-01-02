#!/usr/bin/env node
import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import electron from 'electron';

const __dirname = dirname(fileURLToPath(import.meta.url));
const appPath = join(__dirname, 'out/main/index.js');

// Check if built
if (!existsSync(appPath)) {
  console.error('Error: App not built. Run "npm run build" first.');
  process.exit(1);
}

// Launch electron with GPU flags to suppress Linux warnings
const proc = spawn(electron, [
  '--disable-gpu-vsync',
  '--disable-frame-rate-limit',
  appPath
], {
  stdio: 'inherit',
  env: {
    ...process.env,
    ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    ELECTRON_DISABLE_GPU: '1'
  }
});

proc.on('close', (code) => {
  process.exit(code);
});
