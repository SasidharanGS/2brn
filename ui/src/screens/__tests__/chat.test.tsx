import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { KitProvider } from '../../ui-kit'
import { DateProvider } from '../../context/DateContext'
import type { Skin } from '../../theme/ThemeContext'
import Chat from '../Chat'

// chatStream isn't exercised here (empty state never calls it); stub the module
// so the import resolves under the test env.
vi.mock('../../api/client', () => ({
  api: { chatStream: vi.fn() },
}))

function renderChat(skin: Skin) {
  return render(
    <KitProvider skin={skin}>
      <DateProvider>
        <MemoryRouter>
          <Chat />
        </MemoryRouter>
      </DateProvider>
    </KitProvider>,
  )
}

describe('Chat (unified screen)', () => {
  it.each<Skin>(['modern', 'minimal'])('renders the filter bar, empty prompt and composer in %s skin', skin => {
    renderChat(skin)
    expect(screen.getByText(/Ask anything about your past activity/i)).toBeInTheDocument()
    expect(screen.getByText(/^Filter$/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /all categories/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^work$/i })).toBeInTheDocument()
    // Suggested prompts (from SUGGESTED_PROMPTS) + a send control.
    expect(screen.getByRole('button', { name: /summarise my day so far/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Ask your second brain/i)).toBeInTheDocument()
  })
})
