import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAskNavigation } from '../hooks/useAskNavigation'
import { Page, Heading, Caption, SectionLabel, AskBox, NavTile, type IconName } from '../ui-kit'

// Unified Home — one component for both skins. Behaviour (ask → Chat, tile nav)
// is identical; the look comes entirely from the `--k-*` token contract.
const TILES: { icon: IconName; title: string; desc: string; to: string }[] = [
  { icon: 'journal',  title: 'Journal',  desc: "Today's narrative", to: '/journal'  },
  { icon: 'timeline', title: 'Timeline', desc: 'Activity stream',   to: '/timeline' },
  { icon: 'insights', title: 'Insights', desc: 'Productivity data', to: '/insights' },
  { icon: 'settings', title: 'Settings', desc: 'Configure 2brn',    to: '/settings' },
]

export default function Home() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()
  const ask = useAskNavigation()

  const submit = () => {
    if (!question.trim()) return
    ask(question)
    setQuestion('')
  }

  const today = new Date().toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })

  return (
    <Page>
      <Heading>your second brain</Heading>
      <Caption style={{ marginTop: 'var(--k-space-2xs)' }}>{today}</Caption>

      <div style={{ marginTop: 'var(--k-space-lg)' }}>
        <AskBox
          value={question}
          onChange={setQuestion}
          onSubmit={submit}
          placeholder="Ask anything about your past activity…"
        />
      </div>

      <div style={{ marginTop: 'var(--k-space-xl)' }}>
        <SectionLabel>Navigate</SectionLabel>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--k-space-sm)',
          marginTop: 'var(--k-space-sm)',
        }}>
          {TILES.map(t => (
            <NavTile key={t.to} icon={t.icon} title={t.title} desc={t.desc} onClick={() => navigate(t.to)} />
          ))}
        </div>
      </div>
    </Page>
  )
}
