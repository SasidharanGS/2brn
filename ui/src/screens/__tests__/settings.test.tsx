import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import { ThemeProvider } from '../../theme/ThemeContext'
import type { Skin } from '../../theme/ThemeContext'
import Settings from '../Settings'

vi.mock('../../api/client', () => ({
  api: {
    getSettings: vi.fn(),
    getExclusions: vi.fn().mockResolvedValue([]),
    setScreenshotPassword: vi.fn(),
    updateSettings: vi.fn(),
  },
}))

import { api } from '../../api/client'

const baseSettings = {
  paused: false, purge_months: 3, has_chat_key: false, has_embed_key: false,
  screenshot_encryption_enabled: false,
  chat_provider: { type: 'openai', base_url: '', model: '' },
  embed_provider: { type: 'openai', base_url: '', model: '' },
  capture_interval_seconds: 30, change_cooldown_seconds: 2, max_idle_tick_seconds: 60, similarity_threshold: 0.9,
  joplin_enabled: false, joplin_db_path: '',
}

beforeEach(() => {
  vi.clearAllMocks()
  ;(api.getSettings as Mock).mockResolvedValue(baseSettings)
  // ThemeProvider reads the OS theme via the Electron bridge.
  ;(globalThis as unknown as { window: Window }).window.electronAPI = {
    getTheme: () => Promise.resolve('dark'),
    onThemeChanged: () => () => {},
    isDaemonOwned: () => Promise.resolve(true),
  } as unknown as Window['electronAPI']
})

function renderSettings(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider>
        <KitProvider skin={skin}>
          <Settings />
        </KitProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('Settings (unified screen)', () => {
  it.each<Skin>(['modern', 'minimal'])('renders the core sections in %s skin', async skin => {
    renderSettings(skin)
    expect(await screen.findByText('Appearance')).toBeInTheDocument()
    expect(screen.getByText('Chat Provider')).toBeInTheDocument()
    expect(screen.getByText('Screenshot Encryption')).toBeInTheDocument()
  })

  it('validates the encryption password (mismatch) before calling the API', async () => {
    renderSettings('modern')
    await screen.findByText('Screenshot Encryption')
    const choose = screen.getByPlaceholderText(/choose a password/i)
    const confirm = screen.getByPlaceholderText(/re-enter password/i)
    fireEvent.change(choose, { target: { value: 'longenough' } })
    fireEvent.change(confirm, { target: { value: 'different!!' } })
    const btn = screen.getByRole('button', { name: /enable encryption/i }) as HTMLButtonElement
    expect(btn.disabled).toBe(false)
    fireEvent.click(btn)
    await waitFor(() => expect(screen.getByText(/Passwords do not match/i)).toBeInTheDocument())
    expect(api.setScreenshotPassword).not.toHaveBeenCalled()
  })
})
