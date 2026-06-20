import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendDir = resolve(scriptDir, '..')
const repoRoot = resolve(frontendDir, '..')
const backendDir = join(repoRoot, 'backend')
const backendPort = process.env.VITE_BACKEND_PORT || '8124'
const backendHost = process.env.VITE_BACKEND_HOST || '127.0.0.1'
const backendUrl =
  process.env.VITE_BACKEND_URL || `http://${backendHost}:${backendPort}`
const healthUrl = `${backendUrl}/api/v1/ping`

let backendProcess
let viteProcess
let shuttingDown = false

function resolvePythonCommand() {
  const candidates =
    process.platform === 'win32'
      ? [
          join(repoRoot, '.venv', 'Scripts', 'python.exe'),
          join(backendDir, 'venv', 'Scripts', 'python.exe'),
          join(backendDir, 'ppvenv', 'Scripts', 'python.exe'),
        ]
      : [
          join(repoRoot, '.venv', 'bin', 'python'),
          join(backendDir, 'venv', 'bin', 'python'),
          join(backendDir, 'ppvenv', 'bin', 'python'),
        ]

  const existing = candidates.find((candidate) => existsSync(candidate))
  if (existing) return { command: existing, args: [] }

  if (process.env.PYTHON) return { command: process.env.PYTHON, args: [] }
  if (process.platform === 'win32') return { command: 'py', args: ['-3.11'] }
  return { command: 'python3', args: [] }
}

function resolveViteCommand() {
  return join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js')
}

async function isBackendHealthy() {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 2_000)

  try {
    const response = await fetch(healthUrl, { signal: controller.signal })
    return response.ok
  } catch {
    return false
  } finally {
    clearTimeout(timeout)
  }
}

async function waitForBackend(timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs

  while (Date.now() < deadline) {
    if (await isBackendHealthy()) return true
    await new Promise((resolve) => setTimeout(resolve, 500))
  }

  return false
}

function startBackend() {
  const python = resolvePythonCommand()
  const args = [
    ...python.args,
    '-m',
    'uvicorn',
    'app.main:app',
    '--host',
    backendHost,
    '--port',
    backendPort,
    '--reload',
  ]

  console.log(`[dev] Starting backend at ${backendUrl}`)
  backendProcess = spawn(python.command, args, {
    cwd: backendDir,
    env: process.env,
    stdio: 'inherit',
  })

  backendProcess.on('exit', (code, signal) => {
    if (shuttingDown) return
    console.error(`[dev] Backend stopped (${signal || code})`)
    stopAll(code ?? 1)
  })
}

function startVite() {
  const viteEntry = resolveViteCommand()

  console.log('[dev] Starting Vite frontend')
  viteProcess = spawn(process.execPath, [viteEntry], {
    cwd: frontendDir,
    env: {
      ...process.env,
      VITE_BACKEND_URL: backendUrl,
    },
    stdio: 'inherit',
  })

  viteProcess.on('exit', (code, signal) => {
    if (shuttingDown) return
    stopAll(code ?? (signal ? 1 : 0))
  })
}

function stopAll(exitCode = 0) {
  if (shuttingDown) return
  shuttingDown = true

  if (viteProcess && !viteProcess.killed) viteProcess.kill()
  if (backendProcess && !backendProcess.killed) backendProcess.kill()

  process.exit(exitCode)
}

process.on('SIGINT', () => stopAll(0))
process.on('SIGTERM', () => stopAll(0))

if (await isBackendHealthy()) {
  console.log(`[dev] Backend already healthy at ${backendUrl}`)
} else {
  startBackend()
  const ready = await waitForBackend()

  if (!ready) {
    console.error(`[dev] Backend did not become healthy at ${healthUrl}`)
    stopAll(1)
  }
}

startVite()
