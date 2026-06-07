import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getDaemonPort: () => ipcRenderer.invoke('get-daemon-port'),
  getApiToken: () => ipcRenderer.invoke('get-api-token'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  onDaemonStatus: (callback: (status: string) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, status: string) => callback(status)
    ipcRenderer.on('daemon-status', handler)
    return () => ipcRenderer.removeListener('daemon-status', handler)
  },
  getTheme: () => ipcRenderer.invoke('get-theme'),
  onThemeChanged: (callback: (theme: 'dark' | 'light') => void) => {
    const handler = (_event: Electron.IpcRendererEvent, theme: 'dark' | 'light') => callback(theme)
    ipcRenderer.on('theme-changed', handler)
    return () => ipcRenderer.removeListener('theme-changed', handler)
  },
  isDaemonOwned: () => ipcRenderer.invoke('daemon-owned'),
  restartDaemon: () => ipcRenderer.invoke('restart-daemon'),
})
