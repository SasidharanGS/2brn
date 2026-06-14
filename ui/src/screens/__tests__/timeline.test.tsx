import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import { DateProvider } from '../../context/DateContext'
import type { Skin } from '../../theme/ThemeContext'
import Timeline from '../Timeline'

vi.mock('../../api/client', () => ({
  api: {
    getActivities: vi.fn(),
    getCaptures: vi.fn(),
    getSessions: vi.fn(),
  },
}))

import { api } from '../../api/client'

function renderTimeline(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KitProvider skin={skin}>
        <DateProvider>
          <Timeline />
        </DateProvider>
      </KitProvider>
    </QueryClientProvider>,
  )
}

const emptySessions = { blocks: [], totals: { observed_seconds: 0, by_category: {} } }

describe('Timeline (unified screen)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(api.getCaptures as Mock).mockResolvedValue([])
    ;(api.getSessions as Mock).mockResolvedValue(emptySessions)
  })

  it.each<Skin>(['modern', 'minimal'])('shows the no-activity empty state (%s)', async skin => {
    ;(api.getActivities as Mock).mockResolvedValue([])
    renderTimeline(skin)
    expect(await screen.findByText(/No activity recorded for/i)).toBeInTheDocument()
  })

  it.each<Skin>(['modern', 'minimal'])('renders an activity row + hour rail (%s)', async skin => {
    ;(api.getActivities as Mock).mockResolvedValue([
      { id: 1, started_at: '2026-06-14T09:30:00', summary: 'Wrote the report', task_category: 'work', productivity_state: 'focused' },
    ])
    renderTimeline(skin)
    expect(await screen.findByText('Wrote the report')).toBeInTheDocument()
    // Hour rail tick exposes the hour as its title (09:00 am).
    expect(screen.getAllByTitle(/09:00 am/i).length).toBeGreaterThanOrEqual(1)
  })
})
