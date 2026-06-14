import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import type { Skin } from '../../theme/ThemeContext'
import Plugins from '../Plugins'

vi.mock('../../api/client', () => ({
  api: {
    listPlugins: vi.fn(),
    listPluginRules: vi.fn().mockResolvedValue([]),
    listPluginTools: vi.fn().mockResolvedValue([]),
  },
}))

import { api } from '../../api/client'

function renderPlugins(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KitProvider skin={skin}>
        <Plugins />
      </KitProvider>
    </QueryClientProvider>,
  )
}

describe('Plugins (unified screen)', () => {
  beforeEach(() => vi.clearAllMocks())

  it.each<Skin>(['modern', 'minimal'])('shows the empty state + add action (%s)', async skin => {
    ;(api.listPlugins as Mock).mockResolvedValue([])
    renderPlugins(skin)
    expect(await screen.findByText(/Plugins extend 2brn with MCP servers/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^add$/i })).toBeInTheDocument()
  })

  it('auto-selects the first plugin and shows its detail + Rules', async () => {
    ;(api.listPlugins as Mock).mockResolvedValue([
      { id: 1, name: 'joplin', command: 'node', args: ['x.js'], env_keys: [], enabled: true, last_health_ok: true, last_health_error: null },
    ])
    renderPlugins('modern')
    // Name appears in the list and the detail header.
    expect((await screen.findAllByText('joplin')).length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('healthy')).toBeInTheDocument()
    expect(screen.getByText('Rules')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new rule/i })).toBeInTheDocument()
  })
})
