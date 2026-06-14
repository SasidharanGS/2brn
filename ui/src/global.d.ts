export {}

declare global {
  interface Window {
    electronAPI: {
      getDaemonPort: () => Promise<number>
      getApiToken: () => Promise<string>
      getPlatform: () => Promise<string>
      getTheme: () => Promise<'dark' | 'light'>
      onThemeChanged: (callback: (theme: 'dark' | 'light') => void) => () => void
      isDaemonOwned: () => Promise<boolean>
      restartDaemon: () => Promise<{ ok: boolean; reason?: string }>
    }
  }
}
