import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAskNavigation } from '../../hooks/useAskNavigation'
import Icon, { type IconName } from './Icon'
import { Label } from './primitives'

const NAV_CARDS: { icon: IconName; title: string; sub: string; to: string }[] = [
  { icon: 'journal',  title: 'journal',  sub: "today's narrative",  to: '/journal'  },
  { icon: 'timeline', title: 'timeline', sub: 'activity stream',    to: '/timeline' },
  { icon: 'insights', title: 'insights', sub: 'productivity data',  to: '/insights' },
  { icon: 'settings', title: 'settings', sub: 'configure 2brn',     to: '/settings' },
]

function NavCard({ icon, title, sub, onClick }: {
  icon: IconName; title: string; sub: string; onClick: () => void
}) {
  return (
    <button
      type="button" onClick={onClick} className="m-navcard"
      style={{
        textAlign: 'left', background: 'none', padding: 'var(--space-md)', cursor: 'pointer',
        display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', fontFamily: 'var(--font-sans)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', color: 'var(--fg)' }}>
        <Icon name={icon} size={16} />
        <span style={{ fontSize: 'var(--text-md)', fontWeight: 400 }}>{title}</span>
      </div>
      <span style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>{sub}</span>
    </button>
  )
}

export default function Home() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()
  const ask = useAskNavigation()

  const now = new Date()
  const todayLabel = [
    now.toLocaleDateString('en-GB', { weekday: 'long' }),
    '·',
    now.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' }),
  ].join(' ').toLowerCase()

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <div style={{ maxWidth: 760 }}>
        <h1 style={{
          margin: 0, fontSize: 'var(--text-hero)', fontWeight: 400,
          letterSpacing: 'var(--tracking-tight)', color: 'var(--fg)', lineHeight: 'var(--leading-tight)',
        }}>
          your second brain
        </h1>
        <div style={{
          fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300,
          letterSpacing: 'var(--tracking-wide)', marginTop: 'var(--space-xs)',
        }}>
          {todayLabel}
        </div>

        <form
          onSubmit={e => { e.preventDefault(); if (!question.trim()) return; ask(question); setQuestion('') }}
          style={{ display: 'flex', gap: 0, border: '1px solid var(--rule)', marginTop: 'var(--space-lg)' }}
        >
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="ask anything about your past activity…"
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              padding: 'var(--space-sm) var(--space-md)', color: 'var(--fg)',
              fontSize: 'var(--text-base)', fontWeight: 300, fontFamily: 'var(--font-sans)',
            }}
          />
          <button
            type="submit" className="m-fill-btn"
            style={{
              border: 'none', borderLeft: '1px solid var(--rule)', padding: '0 var(--space-md)',
              cursor: 'pointer', fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
              fontWeight: 300, fontFamily: 'var(--font-sans)',
            }}
          >
            ask
          </button>
        </form>

        <div style={{ marginTop: 'var(--space-xl)' }}>
          <Label>navigate</Label>
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            gap: 'var(--space-sm)', marginTop: 'var(--space-sm)',
          }}>
            {NAV_CARDS.map(card => (
              <NavCard key={card.to} {...card} onClick={() => navigate(card.to)} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
