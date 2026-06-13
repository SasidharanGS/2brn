import { useState, useEffect, useRef, type ReactNode } from 'react'
import { useDebugLogs, useDebugStatus } from '../../../hooks/useDebugData'

// 300px right panel: header with the live accent dot, logs/status tabs,
// mono log lines. Errors use the accent (an important cue); everything
// else stays monochrome.

type Tab = 'logs' | 'status'

function Row({ k, v, strong }: { k: string; v: ReactNode; strong?: boolean }) {
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', gap: 8, padding: '2px 0',
      borderBottom: '1px solid var(--rule)',
    }}>
      <span style={{ color: 'var(--muted)' }}>{k}</span>
      <span style={{ color: strong ? 'var(--fg)' : 'var(--muted)', textAlign: 'right' }}>{v}</span>
    </div>
  )
}

export default function DebugPanel({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<Tab>('logs')
  const logsData = useDebugLogs(tab === 'logs')
  const statusData = useDebugStatus(tab === 'status')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Keep the log tail in view
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logsData])

  return (
    <aside className="m-panel" style={{
      width: 'var(--panel-w)', flex: '0 0 auto', borderLeft: '1px solid var(--rule)',
      display: 'flex', flexDirection: 'column', boxSizing: 'border-box', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: 'var(--space-sm) var(--space-md)', borderBottom: '1px solid var(--rule)', flex: '0 0 auto',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }} />
          <span style={{
            fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
            color: 'var(--fg)', fontWeight: 400,
          }}>
            debug
          </span>
        </div>
        <button
          type="button" onClick={onClose} className="m-quiet"
          style={{
            background: 'none', border: 'none', padding: 4, cursor: 'pointer',
            fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', fontFamily: 'var(--font-sans)',
          }}
        >
          close
        </button>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 'var(--space-md)', padding: 'var(--space-sm) var(--space-md)',
        borderBottom: '1px solid var(--rule)', flex: '0 0 auto',
      }}>
        {(['logs', 'status'] as Tab[]).map(t => (
          <button
            key={t} type="button" onClick={() => setTab(t)}
            style={{
              background: 'none', border: 'none', padding: 0, cursor: 'pointer',
              color: tab === t ? 'var(--fg)' : 'var(--muted)',
              fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)',
              fontWeight: 300, fontFamily: 'var(--font-sans)', transition: 'color 0.2s ease',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Body — mono readout */}
      <div
        ref={scrollRef}
        style={{
          flex: 1, overflowY: 'auto', padding: 'var(--space-md)',
          fontFamily: 'var(--font-mono)', fontSize: '0.66rem',
          color: 'var(--muted)', lineHeight: 'var(--leading-loose)',
        }}
      >
        {tab === 'logs' ? (
          (logsData?.lines ?? []).length === 0 ? (
            <div>no log lines yet</div>
          ) : (
            logsData!.lines.map((l, i) => (
              <div key={`${l.ts}-${i}`} style={{
                color: l.level === 'ERROR' ? 'var(--accent)' : l.level === 'WARNING' ? 'var(--fg)' : 'var(--muted)',
                wordBreak: 'break-all',
              }}>
                [{l.ts}] {l.msg}
              </div>
            ))
          )
        ) : !statusData ? (
          <div>loading…</div>
        ) : (
          <>
            <Row k="daemon" v={statusData.daemon.status} strong />
            <Row k="captures today" v={statusData.daemon.capture_count_today} strong />
            <Row k="last capture" v={statusData.daemon.last_captured_at ? statusData.daemon.last_captured_at.slice(11, 19) : '—'} />
            <Row k="paused" v={String(statusData.daemon.paused)} />
            <Row k="gateway" v={statusData.gateway.reachable ? 'reachable' : 'unreachable'} strong />
            <Row k="model" v={statusData.gateway.model} />
            <Row k="activity memories" v={statusData.chroma.activity_memories} />
            <Row k="note memories" v={statusData.chroma.note_memories} />
            {statusData.last_error && (
              <div style={{ marginTop: 'var(--space-sm)', color: 'var(--accent)', wordBreak: 'break-all' }}>
                last error · {statusData.last_error.msg}
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  )
}
