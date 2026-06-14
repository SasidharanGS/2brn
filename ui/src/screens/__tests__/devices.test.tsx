import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import type { Skin } from '../../theme/ThemeContext'
import Devices from '../Devices'

vi.mock('../../api/client', () => ({
  api: {
    listDevices: vi.fn(),
    getConnectionInfo: vi.fn(),
    createDevice: vi.fn(),
    revokeDevice: vi.fn(),
  },
}))

import { api } from '../../api/client'

function renderDevices(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KitProvider skin={skin}>
        <Devices />
      </KitProvider>
    </QueryClientProvider>,
  )
}

describe('Devices (unified screen)', () => {
  beforeEach(() => vi.clearAllMocks())

  it.each<Skin>(['modern', 'minimal'])('shows the pair form + LAN-off warning when no LAN (%s)', async skin => {
    ;(api.listDevices as Mock).mockResolvedValue([])
    ;(api.getConnectionInfo as Mock).mockResolvedValue({ lan_access: false, lan_urls: [], hostname: 'h', port: 7842 })
    renderDevices(skin)
    expect(await screen.findByText(/LAN access is off/i)).toBeInTheDocument()
    expect(screen.getByText(/Pair a new phone/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Device name/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate pairing code/i })).toBeInTheDocument()
  })

  it('lists paired devices with a revoke action', async () => {
    ;(api.listDevices as Mock).mockResolvedValue([
      { id: 7, name: 'My phone', created_at: '2026-06-14T10:00:00Z', last_seen_at: null },
    ])
    ;(api.getConnectionInfo as Mock).mockResolvedValue({ lan_access: true, lan_urls: ['http://192.168.1.5:7842'], hostname: 'h', port: 7842 })
    renderDevices('modern')
    expect(await screen.findByText('My phone')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /revoke/i })).toBeInTheDocument()
    // LAN ready → no warning banner.
    expect(screen.queryByText(/LAN access is off/i)).not.toBeInTheDocument()
  })
})
