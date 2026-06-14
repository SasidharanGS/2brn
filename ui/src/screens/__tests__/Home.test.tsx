import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { KitProvider } from '../../ui-kit'
import type { Skin } from '../../theme/ThemeContext'
import Home from '../Home'

// Probe that surfaces where the ask box navigated to, plus the question it
// carried in router state — lets us assert the ask → Chat behaviour.
function ChatProbe() {
  const loc = useLocation()
  const q = (loc.state as { initialQuestion?: string } | null)?.initialQuestion
  return <div>chat-screen:{q}</div>
}

function renderHome(skin: Skin) {
  return render(
    <KitProvider skin={skin}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<ChatProbe />} />
        </Routes>
      </MemoryRouter>
    </KitProvider>,
  )
}

describe('Home (unified screen)', () => {
  it.each<Skin>(['modern', 'minimal'])('renders heading, ask box and the 4 nav tiles in %s skin', skin => {
    renderHome(skin)
    expect(screen.getByRole('heading', { name: /your second brain/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/ask anything/i)).toBeInTheDocument()
    for (const title of ['Journal', 'Timeline', 'Insights', 'Settings']) {
      expect(screen.getByText(title)).toBeInTheDocument()
    }
  })

  it('submitting the ask box navigates to Chat with the question', () => {
    renderHome('modern')
    fireEvent.change(screen.getByPlaceholderText(/ask anything/i), { target: { value: 'what did I do?' } })
    fireEvent.click(screen.getByRole('button', { name: /ask/i }))
    expect(screen.getByText('chat-screen:what did I do?')).toBeInTheDocument()
  })

  it('does not navigate when the question is blank (button stays disabled)', () => {
    renderHome('modern')
    const btn = screen.getByRole('button', { name: /ask/i }) as HTMLButtonElement
    expect(btn.disabled).toBe(true)
    fireEvent.click(btn)
    expect(screen.queryByText(/chat-screen:/)).not.toBeInTheDocument()
  })

  it('uses line-SVG icons in minimal and emoji (no svg) in modern', () => {
    const { container: minimal } = renderHome('minimal')
    expect(minimal.querySelectorAll('svg').length).toBeGreaterThanOrEqual(4)

    const { container: modern } = renderHome('modern')
    // Modern tiles use emoji text, not SVG icons.
    const modernTiles = within(modern).getAllByRole('button').filter(b => /Journal|Timeline|Insights|Settings/.test(b.textContent ?? ''))
    expect(modernTiles).toHaveLength(4)
    expect(modern.querySelectorAll('svg')).toHaveLength(0)
  })
})
