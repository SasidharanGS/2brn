import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const TILES = [
  { label: 'Journal',  path: '/journal',  icon: '📔', desc: "Today's narrative" },
  { label: 'Timeline', path: '/timeline', icon: '⏱',  desc: 'Activity stream' },
  { label: 'Insights', path: '/insights', icon: '◎',  desc: 'Productivity data' },
  { label: 'Settings', path: '/settings', icon: '⚙',  desc: 'Configure 2brn' },
]

export default function Dashboard() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()

  const handleChat = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    navigate('/chat', { state: { initialQuestion: question } })
    setQuestion('')
  }

  return (
    <div className="page-enter p-8 max-w-[700px] mx-auto">

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-[23px] font-semibold tracking-tight mb-1" style={{ color: 'var(--text)' }}>
          your second brain
        </h1>
        <p className="text-[13px]" style={{ color: 'var(--text-dim)' }}>
          {new Date().toLocaleDateString('en-GB', {
            weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
          })}
        </p>
      </div>

      {/* Chat input */}
      <form onSubmit={handleChat} className="mb-10">
        <div
          className="flex rounded-[12px] border overflow-hidden transition-shadow duration-200 focus-within:shadow-glow"
          style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)' }}
        >
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Ask anything about your past activity…"
            className="flex-1 bg-transparent px-4 py-3 text-[14px] outline-none"
            style={{ color: 'var(--text)' }}
          />
          <button
            type="submit"
            disabled={!question.trim()}
            className="px-5 py-3 text-[13px] font-semibold transition-all duration-150 disabled:opacity-30"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Ask
          </button>
        </div>
      </form>

      {/* Tiles label */}
      <div
        className="text-[11px] font-medium tracking-[0.1em] uppercase mb-3"
        style={{ color: 'var(--text-dim)' }}
      >
        Navigate
      </div>

      {/* Tiles */}
      <div className="grid grid-cols-2 gap-2.5">
        {TILES.map(tile => (
          <button
            key={tile.path}
            onClick={() => navigate(tile.path)}
            className="nav-tile group text-left rounded-[12px] p-4 border hover:-translate-y-0.5 hover:shadow-glow-sm"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[16px]">{tile.icon}</span>
              <span className="text-[14px] font-medium" style={{ color: 'var(--text)' }}>
                {tile.label}
              </span>
            </div>
            <div className="text-[12px]" style={{ color: 'var(--text-muted)' }}>{tile.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
