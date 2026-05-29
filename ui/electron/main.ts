import { app, BrowserWindow, ipcMain, nativeTheme } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import * as fs from 'fs'
import * as path from 'path'
import * as http from 'http'

const DAEMON_PORT = 7842
const DAEMON_HOST = '127.0.0.1'

function log(level: 'info' | 'warn' | 'error', msg: string): void {
  const ts = new Date().toISOString().substring(11, 23)
  const prefix = `[${ts}] [2brn]`
  if (level === 'error') console.error(prefix, msg)
  else if (level === 'warn') console.warn(prefix, msg)
  else console.log(prefix, msg)
}
let daemon: ChildProcess | null = null
let mainWindow: BrowserWindow | null = null
let daemonRestartAttempts = 0
let healthPollTimer: ReturnType<typeof setInterval> | null = null

function isDev(): boolean {
  return !app.isPackaged
}

function resolveReal(p: string): string | null {
  // Electron on macOS cannot spawn symlinks — must use the fully resolved real path
  try {
    if (fs.existsSync(p)) return fs.realpathSync(p)
  } catch {}
  return null
}

function getDaemonCwd(): string {
  if (isDev()) {
    // In dev: main.ts is at ui/electron/main.ts
    // __dirname after build = ui/dist/electron/
    // repo root is 3 levels up from dist/electron/
    // daemon dir = <repo_root>/daemon
    const repoRoot = path.resolve(__dirname, '..', '..', '..')
    const candidate = path.join(repoRoot, 'daemon')
    if (fs.existsSync(candidate)) return candidate
    // Fallback: try 2 levels up (in case dist layout differs)
    const candidate2 = path.resolve(__dirname, '..', '..', 'daemon')
    if (fs.existsSync(candidate2)) return candidate2
    // Last fallback: relative to app path
    return path.join(app.getAppPath(), '..', 'daemon')
  }
  return path.join(process.resourcesPath, 'daemon')
}

function buildPythonPath(daemonCwd: string): string {
  // brn_daemon uses src-layout installed via .pth file — we must include both
  // the src/ directory (where brn_daemon package lives) and the venv site-packages
  // (where all dependencies live). The .pth file only activates with a proper venv
  // activation, so we set PYTHONPATH manually instead.
  const sitePackages = path.join(daemonCwd, '.venv', 'lib')
  // Find the versioned python dir (e.g. python3.14) inside lib/
  let versionedLib = ''
  try {
    const entries = fs.readdirSync(sitePackages)
    const pyDir = entries.find(e => e.startsWith('python'))
    if (pyDir) versionedLib = path.join(sitePackages, pyDir, 'site-packages')
  } catch {}
  const src = path.join(daemonCwd, 'src')
  return [src, versionedLib].filter(Boolean).join(path.delimiter)
}

function resolvePython(daemonCwd: string): { cmd: string; args: string[]; extraEnv: Record<string, string> } {
  log('info', `daemonCwd = ${daemonCwd}`)

  // Prefer .venv Python — resolve symlinks since Electron cannot spawn symlinks on macOS
  const venvPython = resolveReal(path.join(daemonCwd, '.venv', 'bin', 'python3'))
    ?? resolveReal(path.join(daemonCwd, '.venv', 'bin', 'python'))
  if (venvPython) {
    const pythonPath = buildPythonPath(daemonCwd)
    log('info', `using venv python: ${venvPython}`)
    log('info', `PYTHONPATH: ${pythonPath}`)
    return { cmd: venvPython, args: ['-m', 'uvicorn', 'brn_daemon.main:app', '--host', '127.0.0.1', '--port', String(DAEMON_PORT)], extraEnv: { PYTHONPATH: pythonPath } }
  }

  log('info', `.venv not found at ${daemonCwd}/.venv, trying uv fallback`)

  // Fallback: uv (also needs symlink resolution)
  const uvCandidates = [
    '/opt/homebrew/bin/uv',
    '/usr/local/bin/uv',
    `${process.env.HOME}/.cargo/bin/uv`,
    `${process.env.HOME}/.local/bin/uv`,
  ]
  for (const uvPath of uvCandidates) {
    const real = resolveReal(uvPath)
    if (real) {
      log('info', `using uv: ${real}`)
      return { cmd: real, args: ['run', 'python', '-m', 'uvicorn', 'brn_daemon.main:app', '--host', '127.0.0.1', '--port', String(DAEMON_PORT)], extraEnv: {} }
    }
  }

  log('error', 'could not find python or uv — spawn will fail')
  return { cmd: 'python3', args: ['-m', 'uvicorn', 'brn_daemon.main:app', '--host', '127.0.0.1', '--port', String(DAEMON_PORT)], extraEnv: {} }
}

function probeDaemon(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(
      { hostname: DAEMON_HOST, port: DAEMON_PORT, path: '/status', timeout: 2000 },
      (res) => { resolve(res.statusCode === 200); res.resume() }
    )
    req.on('error', () => resolve(false))
    req.on('timeout', () => { req.destroy(); resolve(false) })
    req.end()
  })
}

function startDaemon(): void {
  const daemonCwd = getDaemonCwd()
  const { cmd, args: daemonArgs, extraEnv } = resolvePython(daemonCwd)
  log('info', `spawning: ${cmd} ${daemonArgs.join(' ')} (cwd: ${daemonCwd})`)

  daemon = spawn(cmd, daemonArgs, {
    cwd: daemonCwd,
    env: { ...process.env, ...extraEnv },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  daemon.stdout?.on('data', (data: Buffer) => {
    log('info', data.toString().trim())
  })

  daemon.stderr?.on('data', (data: Buffer) => {
    log('error', data.toString().trim())
  })

  daemon.on('exit', (code) => {
    log('info', `exited with code ${code}`)
    if (daemonRestartAttempts < 3) {
      daemonRestartAttempts++
      setTimeout(startDaemon, 10_000)
    } else {
      mainWindow?.webContents.send('daemon-status', 'error')
    }
  })
}

function pollDaemonHealth(): void {
  let failures = 0
  healthPollTimer = setInterval(() => {
    // Guard: don't send to destroyed webContents
    if (!mainWindow || mainWindow.isDestroyed()) return

    const req = http.get(
      { hostname: DAEMON_HOST, port: DAEMON_PORT, path: '/status', timeout: 3000 },
      (res) => {
        if (!mainWindow || mainWindow.isDestroyed()) return
        if (res.statusCode === 200) {
          failures = 0
          daemonRestartAttempts = 0
          mainWindow.webContents.send('daemon-status', 'ok')
        }
        res.resume() // consume response to free socket
      }
    )
    req.on('error', () => {
      failures++
      if (failures >= 2 && mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('daemon-status', 'offline')
      }
    })
    req.end()
  }, 5000)
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#0e0e12' : '#f8f7f4',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  if (isDev()) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../index.html'))
  }
}

ipcMain.handle('get-daemon-port', () => DAEMON_PORT)
ipcMain.handle('get-platform', () => process.platform)
ipcMain.handle('get-theme', () => nativeTheme.shouldUseDarkColors ? 'dark' : 'light')

ipcMain.handle('daemon-owned', () => daemon !== null)

ipcMain.handle('restart-daemon', () => {
  if (!daemon) return { ok: false, reason: 'not-owned' }
  daemon.removeAllListeners('exit')
  daemon.once('exit', () => {
    daemonRestartAttempts = 0
    startDaemon()
  })
  daemon.kill('SIGTERM')
  daemon = null
  return { ok: true }
})

nativeTheme.on('updated', () => {
  mainWindow?.webContents.send('theme-changed', nativeTheme.shouldUseDarkColors ? 'dark' : 'light')
})

app.whenReady().then(async () => {
  const alreadyRunning = await probeDaemon()
  if (alreadyRunning) {
    log('info', 'already running on port 7842 (launchd) — skipping spawn')
  } else {
    startDaemon()
  }
  createWindow()
  pollDaemonHealth()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (healthPollTimer) clearInterval(healthPollTimer)
  if (process.platform !== 'darwin') app.quit()
})

app.on('quit', () => {
  if (healthPollTimer) clearInterval(healthPollTimer)
  daemon?.kill()
})
