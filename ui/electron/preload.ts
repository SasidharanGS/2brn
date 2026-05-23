import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  getDaemonPort: () => ipcRenderer.invoke('get-daemon-port'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  onDaemonStatus: (callback: (status: string) => void) =>
    ipcRenderer.on('daemon-status', (_event, status) => callback(status)),
  getTheme: () => ipcRenderer.invoke('get-theme'),
  onThemeChanged: (callback: (theme: 'dark' | 'light') => void) =>
    ipcRenderer.on('theme-changed', (_event, theme) => callback(theme)),
})
