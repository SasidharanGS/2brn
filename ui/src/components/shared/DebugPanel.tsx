import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { LogLine } from '../../api/types'

interface Props {
  onClose: () => void
}

type Tab = 'logs' | 'status'
type LevelFilter = 'INFO' | 'WARNING' | 'ERROR'

const MIN_WIDTH = 220
const MAX_WIDTH = 700
const DEFAULT_WIDTH = 320
const MAX_LOG_ROWS = 200

/* ── Helpers for imperative log rendering ─────────────────────── */

function levelColour(level: string): string {
  if (level === 'ERROR') return 'var(--red)'
  if (level === 'WARNING') return 'var(--amber)'
  return 'var(--text-dim)'
}

/** Content-based fingerprint: two lines are the same iff ts+level+msg match. */
function logFingerprint(line: LogLine): string {
  return `${line.ts}|${line.level}|${line.msg}`
}

/** Check whether the user has an active text selection inside a container. */
function hasSelectionIn(container: HTMLElement): boolean {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || sel.rangeCount === 0) return false
  return container.contains(sel.anchorNode)
}

/** Create a DOM element for a single log row. */
function createLogRowEl(line: LogLine): HTMLDivElement {
  const row = document.createElement('div')
  row.className = 'flex gap-1.5 mb-0.5 font-mono text-[10px] leading-[1.5]'
  row.style.cssText = 'min-height:0'

  const tsSpan = document.createElement('span')
  tsSpan.style.cssText = 'color:var(--text-dim);flex-shrink:0'
  tsSpan.textContent = line.ts

  const levelSpan = document.createElement('span')
  levelSpan.style.cssText = `color:${levelColour(line.level)};flex-shrink:0;width:26px;font-weight:700`
  levelSpan.textContent = line.level.slice(0, 3)

  const msgSpan = document.createElement('span')
  msgSpan.className = 'break-all'
  msgSpan.style.cssText = 'color:var(--text-muted)'
  msgSpan.textContent = line.msg

  row.appendChild(tsSpan)
  row.appendChild(levelSpan)
  row.appendChild(msgSpan)
  return row
}

export default function DebugPanel({ onClose }: Props) {
  const [tab, setTab] = useState<Tab>('logs')
  const [filters, setFilters] = useState<Set<LevelFilter>>(
    new Set(['INFO', 'WARNING', 'ERROR'])
  )
  const [cleared, setCleared] = useState(false)
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const isDragging = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(DEFAULT_WIDTH)
  const scrollRef = useRef<HTMLDivElement>(null)
  const userScrolledUp = useRef(false)
  /** Ordered fingerprints of every line we've appended to the DOM. */
  const renderedFingerprintsRef = useRef<string[]>([])
  const clearedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => { if (clearedTimerRef.current) clearTimeout(clearedTimerRef.current) }, [])

  const handleDragMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    startX.current = e.clientX
    startWidth.current = width

    function onMouseMove(ev: MouseEvent) {
      if (!isDragging.current) return
      // Dragging left increases width (panel is on the right)
      const delta = startX.current - ev.clientX
      const next = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth.current + delta))
      setWidth(next)
    }

    function onMouseUp() {
      isDragging.current = false
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [width])

  // ── Logs query ──────────────────────────────────────────────
  const { data: logsData } = useQuery({
    queryKey: ['debug-logs'],
    queryFn: () => api.getLogs(undefined, 100),
    refetchInterval: 2000,
    enabled: tab === 'logs',
  })

  // ── Status query ─────────────────────────────────────────────
  const { data: statusData } = useQuery({
    queryKey: ['debug-status'],
    queryFn: api.getDebugStatus,
    refetchInterval: 5000,
    enabled: tab === 'status',
  })

  // ── Imperatively sync log rows into the DOM ───────────────────
  // React re-rendering destroys all DOM nodes and kills the browser's
  // text selection.  Instead we manage the row elements ourselves:
  //   • Compare fingerprints to find genuinely new tail lines
  //   • appendChild only those new lines (existing nodes untouched)
  //   • Prune old rows from the top, skipping any that hold a selection
  //   • Adjust scrollTop so the user's view doesn't jump
  useEffect(() => {
    const container = scrollRef.current
    if (!container) return

    if (cleared) {
      container.innerHTML = ''
      renderedFingerprintsRef.current = []
      return
    }

    const allLines: LogLine[] = logsData?.lines ?? []
    const visibleLines = allLines.filter(l => filters.has(l.level as LevelFilter))
    const incomingFps = visibleLines.map(logFingerprint)

    // ── Find overlap ──────────────────────────────────────────
    // The server returns a sliding window of the last N lines.
    // We need to find where the incoming batch overlaps with what
    // we've already rendered, then only append the new tail.
    const rendered = renderedFingerprintsRef.current
    let newStartIdx = 0 // index into incomingFps where new lines begin

    if (rendered.length > 0) {
      // Find the last rendered fingerprint in the incoming batch
      const lastRendered = rendered[rendered.length - 1]
      // Search backward from the end of incoming for efficiency
      let matchIdx = -1
      for (let i = incomingFps.length - 1; i >= 0; i--) {
        if (incomingFps[i] === lastRendered) {
          matchIdx = i
          break
        }
      }
      if (matchIdx >= 0) {
        // Everything after matchIdx is new
        newStartIdx = matchIdx + 1
      } else {
        // No overlap at all — server window jumped past our buffer.
        // Wipe and re-render everything.
        container.innerHTML = ''
        rendered.length = 0
        newStartIdx = 0
      }
    }

    if (newStartIdx >= incomingFps.length) {
      // Nothing new — skip entirely
      return
    }

    // ── Measure state before mutating ─────────────────────────
    const selectionActive = hasSelectionIn(container)
    const scrollBefore = container.scrollTop
    const scrollHeightBefore = container.scrollHeight

    // ── Append new rows ───────────────────────────────────────
    for (let i = newStartIdx; i < visibleLines.length; i++) {
      const el = createLogRowEl(visibleLines[i])
      container.appendChild(el)
      rendered.push(incomingFps[i])
    }

    // ── Prune old rows from top ───────────────────────────────
    while (container.children.length > MAX_LOG_ROWS) {
      const first = container.firstElementChild
      if (!first) break
      // Don't remove rows that are part of the user's selection
      if (selectionActive) {
        const sel = window.getSelection()
        if (sel && (first.contains(sel.anchorNode) || first.contains(sel.focusNode))) {
          break
        }
      }
      container.removeChild(first)
      rendered.shift()
    }

    // ── Scroll anchoring ──────────────────────────────────────
    const scrollHeightAfter = container.scrollHeight
    const heightDelta = scrollHeightAfter - scrollHeightBefore

    if (selectionActive) {
      // Keep the selected text at the same visual position.
      // New rows were appended at the bottom → scrollHeight grew.
      // If we also pruned from the top → content shifted up.
      // Adjust scrollTop to compensate for both.
      container.scrollTop = scrollBefore + heightDelta
    } else if (!userScrolledUp.current) {
      container.scrollTop = container.scrollHeight
    }
  }, [logsData, cleared, filters])

  function handleScroll() {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8
    userScrolledUp.current = !atBottom
  }

  function toggleFilter(f: LevelFilter) {
    setFilters(prev => {
      const next = new Set(prev)
      if (next.has(f)) next.delete(f)
      else next.add(f)
      return next
    })
  }

  // ── Header dot colour based on daemon status ──────────────────
  const daemonStatus = statusData?.daemon?.status
  const dotColour = daemonStatus === 'capturing'
    ? 'var(--green)'
    : daemonStatus === 'paused'
    ? 'var(--amber)'
    : 'var(--red)'

  return (
    <div
      className="flex flex-col shrink-0 border-l overflow-hidden relative"
      style={{ width, background: 'var(--bg-base)', borderColor: 'var(--border)' }}
    >
      {/* Drag handle — left edge */}
      <div
        onMouseDown={handleDragMouseDown}
        className="absolute top-0 left-0 h-full z-10"
        style={{
          width: 4,
          cursor: 'col-resize',
          background: 'transparent',
        }}
        title="Drag to resize"
      />
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 shrink-0 border-b"
        style={{ height: 34, borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-1.5">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: dotColour }}
          />
          <span
            className="text-[11px] font-mono font-medium"
            style={{ color: 'var(--accent)' }}
          >
            ⬡ debug
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-[10px] font-mono hover:opacity-80 transition-opacity"
          style={{ color: 'var(--text-dim)' }}
        >
          ✕ close
        </button>
      </div>

      {/* Tabs */}
      <div className="flex shrink-0 border-b" style={{ borderColor: 'var(--border)' }}>
        {(['logs', 'status'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-3 py-1.5 text-[11px] font-mono transition-colors"
            style={{
              color: tab === t ? 'var(--accent)' : 'var(--text-dim)',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden">
        {tab === 'logs' && (
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="h-full overflow-y-auto p-2"
          >
            {/* Log rows are imperatively managed — see useEffect above.
                React never touches the children of this div. */}
          </div>
        )}

        {tab === 'status' && (
          <div className="h-full overflow-y-auto p-2.5">
            {!statusData ? (
              <p className="text-[10px] font-mono" style={{ color: 'var(--text-dim)' }}>loading…</p>
            ) : (
              <>
                <StatusSection label="daemon">
                  <StatusRow k="status" v={statusData.daemon.status}
                    colour={statusData.daemon.status === 'capturing' ? 'var(--green)' : 'var(--amber)'} />
                  <StatusRow k="captures today" v={String(statusData.daemon.capture_count_today)}
                    colour="var(--accent)" />
                  <StatusRow k="last capture"
                    v={statusData.daemon.last_captured_at
                      ? statusData.daemon.last_captured_at.slice(11, 19)
                      : '—'} />
                  <StatusRow k="paused" v={String(statusData.daemon.paused)} />
                </StatusSection>

                <StatusSection label="gateway">
                  <StatusRow k="url" v={statusData.gateway.url} />
                  <StatusRow k="reachable"
                    v={statusData.gateway.reachable ? '● yes' : '● no'}
                    colour={statusData.gateway.reachable ? 'var(--green)' : 'var(--red)'} />
                  <StatusRow k="model" v={statusData.gateway.model} />
                </StatusSection>

                <StatusSection label="chroma">
                  <StatusRow k="activity_memories"
                    v={statusData.chroma.activity_memories.toLocaleString()}
                    colour="var(--accent)" />
                  <StatusRow k="note_memories"
                    v={statusData.chroma.note_memories.toLocaleString()}
                    colour="var(--accent)" />
                </StatusSection>

                <StatusSection label="last error">
                  {statusData.last_error ? (
                    <>
                      <StatusRow k="msg" v={statusData.last_error.msg} colour="var(--red)" />
                      <StatusRow k="at" v={statusData.last_error.ts} />
                    </>
                  ) : (
                    <StatusRow k="none" v="—" />
                  )}
                </StatusSection>
              </>
            )}
          </div>
        )}
      </div>

      {/* Footer — only on logs tab */}
      {tab === 'logs' && (
        <div
          className="flex items-center gap-1.5 px-2 shrink-0 border-t"
          style={{ height: 28, borderColor: 'var(--border)' }}
        >
          {(['INFO', 'WARNING', 'ERROR'] as LevelFilter[]).map(f => (
            <button
              key={f}
              onClick={() => toggleFilter(f)}
              className="text-[9px] font-mono px-1.5 py-0.5 rounded transition-colors"
              style={filters.has(f)
                ? { background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)' }
                : { background: 'transparent', color: 'var(--text-dim)', border: '1px solid var(--border)' }
              }
            >
              {f === 'INFO' ? 'inf' : f === 'WARNING' ? 'wrn' : 'err'}
            </button>
          ))}
          <button
            onClick={() => {
              setCleared(true)
              if (clearedTimerRef.current) clearTimeout(clearedTimerRef.current)
              clearedTimerRef.current = setTimeout(() => setCleared(false), 2100)
            }}
            className="text-[9px] font-mono ml-auto hover:opacity-80"
            style={{ color: 'var(--text-dim)' }}
          >
            clear
          </button>
        </div>
      )}
    </div>
  )
}

// ── Small helpers ────────────────────────────────────────────────────────────

function StatusSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <div
        className="text-[9px] font-mono uppercase tracking-widest mb-1"
        style={{ color: 'var(--text-dim)' }}
      >
        {label}
      </div>
      {children}
    </div>
  )
}

function StatusRow({ k, v, colour }: { k: string; v: string; colour?: string }) {
  return (
    <div
      className="flex justify-between items-center py-0.5 font-mono text-[10px]"
      style={{ borderBottom: '1px solid var(--border)' }}
    >
      <span style={{ color: 'var(--text-muted)' }}>{k}</span>
      <span style={{ color: colour ?? 'var(--text-dim)' }}>{v}</span>
    </div>
  )
}
