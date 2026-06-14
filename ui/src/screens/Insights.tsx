import { useState, useMemo, useEffect, type ReactNode } from 'react'
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { CATEGORY_CHIP, STATE_COLORS } from '../utils/design'
import { fmtDur } from '../utils/time'
import { useInsightsData, fmtPct, deltaPct } from '../hooks/useInsightsData'
import { stateInk, inkVar } from './minimal/minimalDesign'
import type { InsightsPeriod, InsightsSummary, HeatmapCell, ComparisonMetric } from '../api/types'
import { PageHeader, Segmented, EmptyState, useKit } from '../ui-kit'

const PERIODS: readonly InsightsPeriod[] = ['day', 'week', 'month']

// Unified Insights. Data + period live in useInsightsData; the header / period
// toggle / loading / empty states are shared. The visualisations themselves are
// the per-skin leaf the epic calls out (colour recharts vs monochrome CSS).
export default function Insights() {
  const { selectedDate, period, setPeriod, summary, isLoading, isError } = useInsightsData()
  const { skin } = useKit()

  const subtitle = summary && summary.observed_seconds > 0 ? `${fmtDur(summary.observed_seconds)} on screen` : undefined

  return (
    <div style={{ padding: 'var(--k-page-pad)' }}>
      <PageHeader title="Insights" subtitle={subtitle} right={<Segmented value={period} options={PERIODS} onChange={setPeriod} />} />

      {isLoading ? (
        <div style={{ fontSize: 'var(--k-text-body)', color: 'var(--k-muted)' }}>Loading…</div>
      ) : isError ? (
        <EmptyState icon="warn" title="Couldn't load insights">The daemon may be unavailable.</EmptyState>
      ) : !summary || summary.categories.length === 0 ? (
        <EmptyState dashed icon="insights"
          title={`No data for ${summary?.range.span_days === 1 ? selectedDate : `the past ${summary?.range.span_days ?? ''} days`}`} />
      ) : skin === 'minimal' ? (
        <MinimalCharts summary={summary} />
      ) : (
        <ModernCharts summary={summary} />
      )}
    </div>
  )
}

// ── Modern (recharts, colour-coded) ───────────────────────────────────────────
function useTooltipStyle() {
  const [isLight, setIsLight] = useState(() => document.documentElement.getAttribute('data-theme') === 'light')
  useEffect(() => {
    const obs = new MutationObserver(() => setIsLight(document.documentElement.getAttribute('data-theme') === 'light'))
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [])
  return useMemo(() => {
    const s = getComputedStyle(document.documentElement)
    const bg = s.getPropertyValue('--tooltip-bg').trim()
    const text = s.getPropertyValue('--tooltip-text').trim()
    const dim = s.getPropertyValue('--text-dim').trim()
    return {
      contentStyle: { background: bg, border: 'none', borderRadius: 7, fontSize: 12, color: text, boxShadow: '0 4px 20px rgba(0,0,0,0.6)', padding: '7px 11px' },
      labelStyle: { color: text, fontWeight: 700, marginBottom: 3 }, itemStyle: { color: text },
      cursor: { fill: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)' },
      wrapperStyle: { pointerEvents: 'none' as const }, axisTickFill: dim,
    }
  }, [isLight])
}

function deltaColor(pct: number | null, positiveGood: boolean): string {
  if (pct === null || pct === 0) return 'var(--text-dim)'
  const isGood = positiveGood ? pct > 0 : pct < 0
  return isGood ? 'var(--accent)' : 'var(--danger, #e25c5c)'
}

function MCard({ title, wide, children }: { title: string; wide?: boolean; children: ReactNode }) {
  return (
    <div style={{ gridColumn: wide ? '1 / -1' : undefined, background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
      <h2 style={{ margin: '0 0 16px', fontSize: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-dim)' }}>{title}</h2>
      {children}
    </div>
  )
}

function ModernComparisonRow({ label, metric, positiveGood }: { label: string; metric: ComparisonMetric; positiveGood: boolean }) {
  const pct = deltaPct(metric.current_pct, metric.baseline_pct)
  const arrow = pct === null ? '' : pct > 0 ? '▲' : pct < 0 ? '▼' : '='
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text)' }}>{fmtPct(metric.current_pct)}</span>
        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>vs {fmtPct(metric.baseline_pct)}</span>
        {pct !== null && <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', width: 56, textAlign: 'right', color: deltaColor(pct, positiveGood) }}>{arrow} {Math.abs(pct)}%</span>}
      </div>
    </div>
  )
}

function ModernCharts({ summary }: { summary: InsightsSummary }) {
  const TT = useTooltipStyle()
  const [barActive, setBarActive] = useState(false)
  const [pieActive, setPieActive] = useState(false)
  const [pieSegment, setPieSegment] = useState(-1)
  const max = Math.max(1, ...summary.hourly_heatmap.map(c => c.pct))
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }} className="page-enter">
      <MCard title="Time by Category">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={summary.categories} barSize={14} barGap={4}
            onMouseMove={state => setBarActive(!!state?.isTooltipActive)} onMouseLeave={() => setBarActive(false)}>
            <XAxis dataKey="task_category" tick={{ fill: TT.axisTickFill, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: TT.axisTickFill, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `${v}%`} domain={[0, 'dataMax']} />
            <Tooltip {...TT} active={barActive} formatter={(value: number) => [fmtPct(value), '% of captures']} />
            <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
              {summary.categories.map(e => <Cell key={e.task_category} fill={CATEGORY_CHIP[e.task_category]?.dot ?? '#64748b'} opacity={0.85} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </MCard>

      <MCard title="Productivity Split">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart onMouseLeave={() => { setPieActive(false); setPieSegment(-1) }}>
            <Pie data={summary.productivity_states} dataKey="pct" nameKey="productivity_state" cx="50%" cy="50%" innerRadius={50} outerRadius={78}
              strokeWidth={0} paddingAngle={2} activeIndex={pieSegment}
              activeShape={(props: any) => <g key={props.name} />}
              onMouseEnter={(_, index) => { setPieActive(true); setPieSegment(index) }} style={{ cursor: 'default' }}>
              {summary.productivity_states.map(e => <Cell key={e.productivity_state} fill={STATE_COLORS[e.productivity_state] ?? '#64748b'} opacity={0.9} />)}
            </Pie>
            <Tooltip {...TT} active={pieActive} formatter={(value: number) => [fmtPct(value), '% of captures']} />
            <Legend iconSize={7} iconType="circle" wrapperStyle={{ fontSize: 11, color: TT.axisTickFill }} />
          </PieChart>
        </ResponsiveContainer>
      </MCard>

      <MCard title="Top Apps" wide>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {summary.top_apps.slice(0, 8).map(app => (
            <div key={app.app_name} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 13, width: 144, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0, color: 'var(--text-muted)' }}>{app.app_name || 'Unknown'}</span>
              <div style={{ flex: 1, borderRadius: 999, height: 6, overflow: 'hidden', background: 'var(--bg-surface-2)' }}>
                <div style={{ width: `${app.pct}%`, height: '100%', borderRadius: 999, background: 'var(--accent)', opacity: 0.65 }} />
              </div>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', width: 96, textAlign: 'right', flexShrink: 0, color: 'var(--text-dim)' }}>{fmtDur(app.seconds)} · {fmtPct(app.pct)}</span>
            </div>
          ))}
        </div>
      </MCard>

      <MCard title="Hour-of-day activity" wide>
        <div style={{ display: 'flex', gap: 3 }}>
          {summary.hourly_heatmap.map(cell => {
            const intensity = cell.pct / max
            const color = cell.dominant_state ? STATE_COLORS[cell.dominant_state] ?? 'var(--accent)' : 'var(--bg-surface-2)'
            return (
              <div key={cell.hour} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 0 }}>
                <div title={cell.pct === 0 ? `${String(cell.hour).padStart(2, '0')}:00 — no activity` : `${String(cell.hour).padStart(2, '0')}:00 — ${fmtPct(cell.pct)} (${cell.dominant_state ?? '—'})`}
                  style={{ width: '100%', borderRadius: 3, height: 28, background: cell.pct === 0 ? 'var(--bg-surface-2)' : color, opacity: cell.pct === 0 ? 0.4 : 0.25 + 0.75 * intensity }} />
                <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', visibility: cell.hour % 3 === 0 ? 'visible' : 'hidden' }}>{String(cell.hour).padStart(2, '0')}</span>
              </div>
            )
          })}
        </div>
      </MCard>

      <MCard title={`vs ${summary.comparison.baseline_label}`}>
        <ModernComparisonRow label="Active" metric={summary.comparison.active} positiveGood />
        <ModernComparisonRow label="Productive" metric={summary.comparison.productive} positiveGood />
        <ModernComparisonRow label="Distracted" metric={summary.comparison.distracted} positiveGood={false} />
      </MCard>

      <MCard title="Recurring activities">
        {summary.recurring_activities.length === 0 ? (
          <div style={{ fontSize: 12, padding: '16px 0', color: 'var(--text-dim)' }}>No recurring patterns detected.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {summary.recurring_activities.map((r, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', width: 56, flexShrink: 0, marginTop: 2, color: 'var(--accent)' }}>≈{fmtDur(r.approx_seconds)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text)' }}>{r.canonical_summary}</div>
                  <div style={{ fontSize: 10, marginTop: 2, color: 'var(--text-dim)' }}>{r.occurrences} occurrence{r.occurrences === 1 ? '' : 's'}{r.variant_count > 1 ? ` · ${r.variant_count} variants` : ''}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </MCard>
    </div>
  )
}

// ── Minimal (monochrome CSS / conic) ──────────────────────────────────────────
function MinCard({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <section style={{ gridColumn: wide ? '1 / -1' : undefined, border: '1px solid var(--rule)', padding: 'var(--space-md)', display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
      <div style={{ fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-label)', color: 'var(--muted)', fontWeight: 300 }}>{label}</div>
      {children}
    </section>
  )
}

function MinStateLabel({ state, level }: { state: string; level: number }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 'var(--text-2xs)', letterSpacing: 'var(--tracking-wide)', color: 'var(--muted)', fontWeight: 300, whiteSpace: 'nowrap' }}>
      <span aria-hidden="true" style={{ width: 7, height: 7, background: inkVar(level), flex: '0 0 auto' }} />{state}
    </span>
  )
}

function Donut({ segments, size = 150 }: { segments: { name: string; pct: number; level: number }[]; size?: number }) {
  const total = segments.reduce((s, x) => s + x.pct, 0) || 1
  let acc = 0
  const stops = segments.map(s => { const from = (acc / total) * 100; acc += s.pct; return `${inkVar(s.level)} ${from}% ${(acc / total) * 100}%` }).join(', ')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-md)' }}>
      <div style={{ width: size, height: size, borderRadius: '50%', background: `conic-gradient(${stops})`, position: 'relative' }}>
        <div style={{ position: 'absolute', inset: '26%', borderRadius: '50%', background: 'var(--bg)' }} />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm) var(--space-md)', justifyContent: 'center' }}>
        {segments.map(s => <MinStateLabel key={s.name} state={`${s.name} ${fmtPct(s.pct)}`} level={s.level} />)}
      </div>
    </div>
  )
}

function MinComparisonRow({ label, metric, positiveGood }: { label: string; metric: ComparisonMetric; positiveGood: boolean }) {
  const delta = deltaPct(metric.current_pct, metric.baseline_pct)
  const bad = delta !== null && (positiveGood ? delta < 0 : delta > 0)
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 'var(--space-md)', alignItems: 'baseline' }}>
      <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300 }}>{label}</span>
      <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 400 }}>{fmtPct(metric.current_pct)}</span>
      <span style={{ fontSize: 'var(--text-2xs)', color: bad ? 'var(--accent)' : 'var(--muted)', fontWeight: 400, letterSpacing: 'var(--tracking-snug)', whiteSpace: 'nowrap' }}>
        {delta === null ? '—' : `${delta > 0 ? '+' : ''}${delta}%`} · avg {fmtPct(metric.baseline_pct)}
      </span>
    </div>
  )
}

function hourLevel(cell: HeatmapCell, max: number): number {
  if (cell.pct === 0) return 0
  return Math.max(1, Math.round((cell.pct / max) * 4))
}

function MinimalCharts({ summary }: { summary: InsightsSummary }) {
  const maxCat = Math.max(1, ...summary.categories.map(c => c.pct))
  const maxApp = Math.max(1, ...summary.top_apps.map(a => a.pct))
  const maxHour = Math.max(1, ...summary.hourly_heatmap.map(c => c.pct))
  return (
    <>
      <div className="m-grid2">
        <MinCard label="time by category">
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 'var(--space-md)', height: 200 }}>
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', fontSize: '0.58rem', color: 'var(--muted)', textAlign: 'right', fontWeight: 300, paddingBottom: 18 }}>
              <span>{fmtPct(maxCat)}</span><span>{fmtPct((maxCat * 2) / 3)}</span><span>{fmtPct(maxCat / 3)}</span><span>0%</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${summary.categories.length}, 1fr)`, gap: 'var(--space-md)', alignItems: 'end' }}>
              {summary.categories.map(c => (
                <div key={c.task_category} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, height: '100%', justifyContent: 'flex-end' }}>
                  <div title={fmtPct(c.pct)} style={{ width: 22, height: Math.max(4, (c.pct / maxCat) * 160), background: c.pct === maxCat ? 'var(--ink-4)' : 'var(--ink-2)' }} />
                  <span style={{ fontSize: '0.58rem', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-snug)' }}>{c.task_category}</span>
                </div>
              ))}
            </div>
          </div>
        </MinCard>

        <MinCard label="productivity split">
          <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 'var(--space-sm)' }}>
            <Donut segments={summary.productivity_states.map(s => ({ name: s.productivity_state, pct: s.pct, level: stateInk(s.productivity_state) }))} />
          </div>
        </MinCard>
      </div>

      <MinCard label="top apps" wide>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {summary.top_apps.slice(0, 8).map((a, i) => (
            <div key={a.app_name} style={{ display: 'grid', gridTemplateColumns: '150px 1fr auto', gap: 'var(--space-md)', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.app_name || 'unknown'}</span>
              <div style={{ height: 8, background: 'var(--ink-0)' }}>
                <div style={{ width: `${(a.pct / maxApp) * 100}%`, height: '100%', background: i === 0 ? 'var(--ink-4)' : 'var(--ink-3)' }} />
              </div>
              <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-snug)', whiteSpace: 'nowrap' }}>{fmtDur(a.seconds)} · {fmtPct(a.pct)}</span>
            </div>
          ))}
        </div>
      </MinCard>

      <MinCard label="hour-of-day activity" wide>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: 3, alignItems: 'end', height: 60 }}>
          {summary.hourly_heatmap.map(cell => {
            const lv = hourLevel(cell, maxHour)
            return <div key={cell.hour} title={cell.pct === 0 ? `${String(cell.hour).padStart(2, '0')}:00 — no activity` : `${String(cell.hour).padStart(2, '0')}:00 — ${fmtPct(cell.pct)}`} style={{ height: lv === 0 ? 4 : 12 + (lv / 4) * 44, background: inkVar(lv) }} />
          })}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', marginTop: 'var(--space-xs)' }}>
          {['00', '03', '06', '09', '12', '15', '18', '21'].map(h => <span key={h} style={{ fontSize: '0.55rem', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-snug)' }}>{h}</span>)}
        </div>
      </MinCard>

      <div className="m-grid2" style={{ marginTop: 'var(--space-sm)' }}>
        <MinCard label={`vs ${summary.comparison.baseline_label.toLowerCase()}`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
            <MinComparisonRow label="active" metric={summary.comparison.active} positiveGood />
            <MinComparisonRow label="productive" metric={summary.comparison.productive} positiveGood />
            <MinComparisonRow label="distracted" metric={summary.comparison.distracted} positiveGood={false} />
          </div>
        </MinCard>

        <MinCard label="recurring activities">
          {summary.recurring_activities.length === 0 ? (
            <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>no recurring patterns detected.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {summary.recurring_activities.map((r, i) => (
                <div key={i} title={`≈${fmtDur(r.approx_seconds)}${r.variant_count > 1 ? ` · ${r.variant_count} variants` : ''}`} style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-md)', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.canonical_summary}</span>
                  <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300, letterSpacing: 'var(--tracking-snug)', whiteSpace: 'nowrap' }}>×{r.occurrences}</span>
                </div>
              ))}
            </div>
          )}
        </MinCard>
      </div>
    </>
  )
}
