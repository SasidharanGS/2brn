import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { CATEGORY_CHIP, STATE_COLORS } from '../utils/design'
import { useAppDate } from '../context/DateContext'
import type { InsightsPeriod, HeatmapCell, ComparisonMetric } from '../api/types'

function useIsLight(): boolean {
  const [isLight, setIsLight] = useState(
    () => document.documentElement.classList.contains('light')
  )
  useEffect(() => {
    const obs = new MutationObserver(() => {
      setIsLight(document.documentElement.classList.contains('light'))
    })
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return isLight
}

function useTooltipStyle() {
  const isLight = useIsLight()
  return useMemo(() => {
    const s = getComputedStyle(document.documentElement)
    const bg   = s.getPropertyValue('--tooltip-bg').trim()
    const text = s.getPropertyValue('--tooltip-text').trim()
    const dim  = s.getPropertyValue('--text-dim').trim()
    return {
      contentStyle: {
        background: bg,
        border: 'none',
        borderRadius: 7,
        fontSize: 12,
        color: text,
        boxShadow: '0 4px 20px rgba(0,0,0,0.6)',
        padding: '7px 11px',
      },
      labelStyle:   { color: text, fontWeight: 700, marginBottom: 3 },
      itemStyle:    { color: text },
      cursor:       { fill: isLight ? 'rgba(0,0,0,0.04)' : 'rgba(255,255,255,0.05)' },
      wrapperStyle: { pointerEvents: 'none' as const },
      axisTickFill: dim,
    }
  }, [isLight])
}

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtPct(p: number): string {
  return `${p.toFixed(1)}%`
}

function deltaPct(current: number, baseline: number): number | null {
  if (baseline <= 0) return current > 0 ? null : 0
  return Math.round(((current - baseline) / baseline) * 100)
}

function deltaColor(pct: number | null, positiveGood: boolean): string {
  if (pct === null || pct === 0) return 'var(--text-dim)'
  const isPositive = pct > 0
  const isGood = positiveGood ? isPositive : !isPositive
  return isGood ? 'var(--accent)' : 'var(--danger, #e25c5c)'
}

// ── Period toggle ──────────────────────────────────────────────────────────

const PERIOD_LABELS: { value: InsightsPeriod; label: string }[] = [
  { value: 'day',   label: 'Day' },
  { value: 'week',  label: 'Week' },
  { value: 'month', label: 'Month' },
]

function PeriodToggle({ value, onChange }: { value: InsightsPeriod; onChange: (v: InsightsPeriod) => void }) {
  return (
    <div
      className="inline-flex rounded-[8px] p-0.5 border"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      {PERIOD_LABELS.map(({ value: v, label }) => {
        const active = v === value
        return (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className="px-3 py-1 text-[12px] font-medium rounded-[6px] transition-colors"
            style={{
              background: active ? 'var(--accent)' : 'transparent',
              color: active ? 'white' : 'var(--text-muted)',
            }}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}

// ── Cards ───────────────────────────────────────────────────────────────────

function HeatmapCard({ cells }: { cells: HeatmapCell[] }) {
  const max = Math.max(1, ...cells.map(c => c.pct))
  return (
    <div
      className="rounded-[12px] border p-5 lg:col-span-2"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
        Hour-of-day activity
      </h2>
      <div className="flex gap-[3px]">
        {cells.map(cell => {
          const intensity = cell.pct / max
          const color = cell.dominant_state
            ? STATE_COLORS[cell.dominant_state] ?? 'var(--accent)'
            : 'var(--bg-surface-2)'
          const showLabel = cell.hour % 3 === 0
          return (
            <div key={cell.hour} className="flex-1 flex flex-col items-center gap-1 min-w-0">
              <div
                title={
                  cell.pct === 0
                    ? `${String(cell.hour).padStart(2, '0')}:00 — no activity`
                    : `${String(cell.hour).padStart(2, '0')}:00 — ${fmtPct(cell.pct)} (${cell.dominant_state ?? '—'})`
                }
                className="w-full rounded-[3px]"
                style={{
                  height: 28,
                  background: cell.pct === 0 ? 'var(--bg-surface-2)' : color,
                  opacity: cell.pct === 0 ? 0.4 : 0.25 + 0.75 * intensity,
                }}
              />
              <span
                className="text-[9px] font-mono"
                style={{ color: 'var(--text-dim)', visibility: showLabel ? 'visible' : 'hidden' }}
              >
                {String(cell.hour).padStart(2, '0')}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ComparisonRow({
  label, metric, positiveGood,
}: {
  label: string
  metric: ComparisonMetric
  positiveGood: boolean
}) {
  const pct = deltaPct(metric.current_pct, metric.baseline_pct)
  const arrow = pct === null ? '' : pct > 0 ? '▲' : pct < 0 ? '▼' : '='
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-b-0" style={{ borderColor: 'var(--border)' }}>
      <span className="text-[13px]" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <div className="flex items-center gap-4">
        <span className="text-[13px] font-mono" style={{ color: 'var(--text)' }}>
          {fmtPct(metric.current_pct)}
        </span>
        <span className="text-[11px] font-mono" style={{ color: 'var(--text-dim)' }}>
          vs {fmtPct(metric.baseline_pct)}
        </span>
        {pct !== null && (
          <span
            className="text-[11px] font-mono w-14 text-right"
            style={{ color: deltaColor(pct, positiveGood) }}
          >
            {arrow} {Math.abs(pct)}%
          </span>
        )}
      </div>
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────

export default function Insights() {
  const { selectedDate } = useAppDate()
  const TT = useTooltipStyle()
  const [period, setPeriod] = useState<InsightsPeriod>('day')

  // Explicit tooltip-active state for each chart (Electron Chromium quirk).
  const [barActive,  setBarActive]  = useState(false)
  const [pieActive,  setPieActive]  = useState(false)
  const [pieSegment, setPieSegment] = useState(-1)

  const { data: summary, isLoading, isError } = useQuery({
    queryKey: queryKeys.insightsSummary(selectedDate, period),
    queryFn: () => api.getInsightsSummary(selectedDate, period),
  })

  return (
    <div className="page-enter p-7">

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[19px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
          Insights
        </h1>
        <PeriodToggle value={period} onChange={setPeriod} />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-64 rounded-[12px]" />)}
        </div>

      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-24">
          <div className="text-4xl mb-4 opacity-20">⚠️</div>
          <div className="text-[14px]" style={{ color: 'var(--text-muted)' }}>
            Couldn't load insights — the daemon may be unavailable.
          </div>
        </div>
      ) : !summary || summary.categories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24">
          <div className="text-4xl mb-4 opacity-20">◎</div>
          <div className="text-[14px]" style={{ color: 'var(--text-muted)' }}>
            No data for {summary?.range.span_days === 1 ? selectedDate : `the past ${summary?.range.span_days ?? ''} days`}
          </div>
        </div>

      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

          {/* Bar chart — Time by Category (%) */}
          <div
            className="rounded-[12px] border p-5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Time by Category
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={summary.categories}
                barSize={14}
                barGap={4}
                onMouseMove={state => setBarActive(!!state?.isTooltipActive)}
                onMouseLeave={() => setBarActive(false)}
              >
                <XAxis
                  dataKey="task_category"
                  tick={{ fill: TT.axisTickFill, fontSize: 11 }}
                  axisLine={false} tickLine={false}
                />
                <YAxis
                  tick={{ fill: TT.axisTickFill, fontSize: 11 }}
                  axisLine={false} tickLine={false}
                  tickFormatter={(v: number) => `${v}%`}
                  domain={[0, 'dataMax']}
                />
                <Tooltip
                  {...TT}
                  active={barActive}
                  formatter={(value: number) => [fmtPct(value), '% of captures']}
                />
                <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
                  {summary.categories.map(entry => (
                    <Cell
                      key={entry.task_category}
                      fill={CATEGORY_CHIP[entry.task_category]?.dot ?? '#64748b'}
                      opacity={0.85}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Donut — Productivity Split (%) */}
          <div
            className="rounded-[12px] border p-5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Productivity Split
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart onMouseLeave={() => { setPieActive(false); setPieSegment(-1) }}>
                <Pie
                  data={summary.productivity_states}
                  dataKey="pct"
                  nameKey="productivity_state"
                  cx="50%" cy="50%"
                  innerRadius={50} outerRadius={78}
                  strokeWidth={0}
                  paddingAngle={2}
                  activeIndex={pieSegment}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  activeShape={(props: any) => <g key={props.name} />}
                  onMouseEnter={(_, index) => { setPieActive(true); setPieSegment(index) }}
                  onMouseLeave={() => { setPieActive(false); setPieSegment(-1) }}
                  style={{ cursor: 'default' }}
                >
                  {summary.productivity_states.map(entry => (
                    <Cell
                      key={entry.productivity_state}
                      fill={STATE_COLORS[entry.productivity_state] ?? '#64748b'}
                      opacity={0.9}
                    />
                  ))}
                </Pie>
                <Tooltip
                  {...TT}
                  active={pieActive}
                  formatter={(value: number) => [fmtPct(value), '% of captures']}
                />
                <Legend
                  iconSize={7}
                  iconType="circle"
                  wrapperStyle={{ fontSize: 11, color: TT.axisTickFill }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Top apps — % of total captures */}
          <div
            className="rounded-[12px] border p-5 lg:col-span-2"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Top Apps
            </h2>
            <div className="space-y-2.5">
              {summary.top_apps.slice(0, 8).map(app => (
                <div key={app.app_name} className="flex items-center gap-3">
                  <span className="text-[13px] w-36 truncate shrink-0" style={{ color: 'var(--text-muted)' }}>
                    {app.app_name || 'Unknown'}
                  </span>
                  <div className="flex-1 rounded-full h-1.5 overflow-hidden" style={{ background: 'var(--bg-surface-2)' }}>
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${app.pct}%`, background: 'var(--accent)', opacity: 0.65 }}
                    />
                  </div>
                  <span className="text-[11px] font-mono w-16 text-right shrink-0" style={{ color: 'var(--text-dim)' }}>
                    {fmtPct(app.pct)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Hour-of-day heatmap */}
          <HeatmapCard cells={summary.hourly_heatmap} />

          {/* Comparison */}
          <div
            className="rounded-[12px] border p-5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase" style={{ color: 'var(--text-dim)' }}>
                vs {summary.comparison.baseline_label}
              </h2>
            </div>
            <ComparisonRow label="Active"      metric={summary.comparison.active}      positiveGood={true} />
            <ComparisonRow label="Productive"  metric={summary.comparison.productive}  positiveGood={true} />
            <ComparisonRow label="Distracted"  metric={summary.comparison.distracted}  positiveGood={false} />
          </div>

          {/* Recurring activities */}
          <div
            className="rounded-[12px] border p-5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Recurring activities
            </h2>
            {summary.recurring_activities.length === 0 ? (
              <div className="text-[12px] py-4" style={{ color: 'var(--text-dim)' }}>
                No recurring patterns detected.
              </div>
            ) : (
              <div className="space-y-2.5">
                {summary.recurring_activities.map((r, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="text-[11px] font-mono w-14 shrink-0 mt-0.5" style={{ color: 'var(--accent)' }}>
                      {fmtPct(r.pct)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] truncate" style={{ color: 'var(--text)' }}>
                        {r.canonical_summary}
                      </div>
                      <div className="text-[10px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
                        {r.session_count} session{r.session_count === 1 ? '' : 's'}
                        {r.variant_count > 1 ? ` · ${r.variant_count} variants` : ''}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  )
}
