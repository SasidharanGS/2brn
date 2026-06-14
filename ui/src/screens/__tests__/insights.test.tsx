import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { KitProvider } from '../../ui-kit'
import { DateProvider } from '../../context/DateContext'
import type { Skin } from '../../theme/ThemeContext'
import Insights from '../Insights'

vi.mock('../../api/client', () => ({ api: { getInsightsSummary: vi.fn() } }))

import { api } from '../../api/client'

function renderInsights(skin: Skin) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <KitProvider skin={skin}>
        <DateProvider>
          <Insights />
        </DateProvider>
      </KitProvider>
    </QueryClientProvider>,
  )
}

const metric = { current_pct: 50, baseline_pct: 40 }
const fullSummary = {
  observed_seconds: 3600,
  range: { span_days: 1 },
  categories: [{ task_category: 'work', pct: 50 }],
  productivity_states: [{ productivity_state: 'focused', pct: 60 }],
  top_apps: [{ app_name: 'Code', seconds: 1800, pct: 50 }],
  hourly_heatmap: Array.from({ length: 24 }, (_, h) => ({ hour: h, pct: h === 9 ? 50 : 0, dominant_state: h === 9 ? 'focused' : null })),
  comparison: { baseline_label: 'last week', active: metric, productive: metric, distracted: metric },
  recurring_activities: [],
}

describe('Insights (unified screen)', () => {
  beforeEach(() => vi.clearAllMocks())

  it.each<Skin>(['modern', 'minimal'])('shows the empty state when no data (%s)', async skin => {
    ;(api.getInsightsSummary as Mock).mockResolvedValue({ categories: [], range: { span_days: 1 }, observed_seconds: 0 })
    renderInsights(skin)
    expect(await screen.findByText(/No data for/i)).toBeInTheDocument()
    // The period toggle is shared chrome, present regardless of data.
    expect(screen.getByRole('button', { name: /^week$/i })).toBeInTheDocument()
  })

  it('renders the minimal monochrome charts when data is present', async () => {
    ;(api.getInsightsSummary as Mock).mockResolvedValue(fullSummary)
    renderInsights('minimal')
    expect(await screen.findByText('time by category')).toBeInTheDocument()
    expect(screen.getByText('top apps')).toBeInTheDocument()
    expect(screen.getByText('hour-of-day activity')).toBeInTheDocument()
  })

  it('renders the modern card sections when data is present', async () => {
    ;(api.getInsightsSummary as Mock).mockResolvedValue(fullSummary)
    renderInsights('modern')
    expect(await screen.findByText('Time by Category')).toBeInTheDocument()
    expect(screen.getByText('Top Apps')).toBeInTheDocument()
  })
})
