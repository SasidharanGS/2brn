import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import { DateProvider } from '../../context/DateContext'
import type { Skin } from '../../theme/ThemeContext'
import Journal from '../Journal'

// Minimal api stub — the prose screens read these through useJournalEntry.
vi.mock('../../api/client', () => ({
  api: {
    getSettings: vi.fn().mockResolvedValue({}),
    getJournal: vi.fn(),
    generateJournal: vi.fn(),
    updateJournal: vi.fn(),
  },
}))

import { api } from '../../api/client'

function renderJournal(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KitProvider skin={skin}>
        <DateProvider>
          <MemoryRouter>
            <Journal />
          </MemoryRouter>
        </DateProvider>
      </KitProvider>
    </QueryClientProvider>,
  )
}

describe('Journal (unified screen)', () => {
  beforeEach(() => vi.clearAllMocks())

  it.each<Skin>(['modern', 'minimal'])('shows the empty state + generate action when no entry exists (%s)', async skin => {
    ;(api.getJournal as Mock).mockResolvedValue(null)
    renderJournal(skin)
    expect(await screen.findByText(/No journal entry for/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /generate entry/i })).toBeInTheDocument()
  })

  it('renders the entry markdown + edited badge, and hides Regenerate when user-edited', async () => {
    ;(api.getJournal as Mock).mockResolvedValue({ content: '# Hello world', edited_by_user: true })
    renderJournal('modern')
    expect(await screen.findByText('Hello world')).toBeInTheDocument()
    expect(screen.getByText('edited')).toBeInTheDocument()
    // Two "Edit" actions are expected: the schedule editor and the doc footer.
    expect(screen.getAllByRole('button', { name: /^edit$/i }).length).toBeGreaterThanOrEqual(1)
    expect(screen.queryByRole('button', { name: /regenerate/i })).not.toBeInTheDocument()
  })

  it('shows Regenerate when the entry is not user-edited', async () => {
    ;(api.getJournal as Mock).mockResolvedValue({ content: 'auto entry', edited_by_user: false })
    renderJournal('minimal')
    expect(await screen.findByText('auto entry')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument()
  })
})
