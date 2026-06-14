import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import type { Skin } from '../../theme/ThemeContext'
import Instructions from '../Instructions'

vi.mock('../../api/client', () => ({
  api: {
    listInstructions: vi.fn(),
    createInstruction: vi.fn(),
    updateInstruction: vi.fn(),
    deleteInstruction: vi.fn(),
  },
}))

import { api } from '../../api/client'

function renderInstructions(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KitProvider skin={skin}>
        <MemoryRouter>
          <Instructions />
        </MemoryRouter>
      </KitProvider>
    </QueryClientProvider>,
  )
}

describe('Instructions (unified screen)', () => {
  beforeEach(() => vi.clearAllMocks())

  it.each<Skin>(['modern', 'minimal'])('shows the empty state + new-instruction action (%s)', async skin => {
    ;(api.listInstructions as Mock).mockResolvedValue([])
    renderInstructions(skin)
    expect(await screen.findByText(/No instructions yet\. Add one/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new instruction/i })).toBeInTheDocument()
  })

  it('lists instructions with a switch and a two-step delete', async () => {
    ;(api.listInstructions as Mock).mockResolvedValue([
      { id: 1, title: 'Rename Opencode tabs', body: 'classify as Opencode', enabled: true },
    ])
    ;(api.deleteInstruction as Mock).mockResolvedValue({})
    renderInstructions('modern')
    expect(await screen.findByText('Rename Opencode tabs')).toBeInTheDocument()
    expect(screen.getByRole('switch')).toBeInTheDocument()

    // Delete is a two-step confirm.
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument()
    expect(api.deleteInstruction).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }))
    await waitFor(() => expect(api.deleteInstruction).toHaveBeenCalledWith(1))
  })
})
