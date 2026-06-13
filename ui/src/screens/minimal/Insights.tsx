import { useInsightsData, fmtPct, deltaPct } from '../../hooks/useInsightsData'
import { fmtDur } from '../../utils/time'
import { stateInk, inkVar } from './minimalDesign'
import PageHeader from './PageHeader'
import Icon from './Icon'
import { Card, Segmented, StateLabel, EmptyState } from './primitives'
import type { InsightsPeriod, ComparisonMetric, HeatmapCell } from '../../api/types'

// Monochrome analytics: everything encodes by the --ink intensity ramp;
// the accent appears only on below-average deltas (an important cue).

/** Monochrome donut via conic-gradient + a --bg hole. */
function Donut({ segments, size = 150 }: {
  segments: { name: string; pct: number; level: number }[]; size?: number
}) {
  const total = segments.reduce((s, x) => s + x.pct, 0) || 1
  let acc = 0
  const stops = segments.map(s => {
    const from = (acc / total) * 100
    acc += s.pct
    return `${inkVar(s.level)} ${from}% ${(acc / total) * 100}%`
  }).join(', ')
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-md)' }}>
      <div style={{ width: size, height: size, borderRadius: '50%', background: `conic-gradient(${stops})`, position: 'relative' }}>
        <div style={{ position: 'absolute', inset: '26%', borderRadius: '50%', background: 'var(--bg)' }} />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm) var(--space-md)', justifyContent: 'center' }}>
        {segments.map(s => (
          <StateLabel key={s.name} state={`${s.name} ${fmtPct(s.pct)}`} level={s.level} />
        ))}
      </div>
    </div>
  )
}

function ComparisonRow({ label, metric, positiveGood }: {
  label: string; metric: ComparisonMetric; positiveGood: boolean
}) {
  const delta = deltaPct(metric.current_pct, metric.baseline_pct)
  const bad = delta !== null && (positiveGood ? delta < 0 : delta > 0)
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 'var(--space-md)', alignItems: 'baseline' }}>
      <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300 }}>{label}</span>
      <span style={{ fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 400 }}>{fmtPct(metric.current_pct)}</span>
      <span style={{
        fontSize: 'var(--text-2xs)', color: bad ? 'var(--accent)' : 'var(--muted)',
        fontWeight: 400, letterSpacing: 'var(--tracking-snug)', whiteSpace: 'nowrap',
      }}>
        {delta === null ? '—' : `${delta > 0 ? '+' : ''}${delta}%`} · avg {fmtPct(metric.baseline_pct)}
      </span>
    </div>
  )
}

/** Heatmap pct → ramp level relative to the busiest hour. */
function hourLevel(cell: HeatmapCell, max: number): number {
  if (cell.pct === 0) return 0
  return Math.max(1, Math.round((cell.pct / max) * 4))
}

const PERIODS: readonly InsightsPeriod[] = ['day', 'week', 'month']

export default function Insights() {
  const { selectedDate, period, setPeriod, summary, isLoading, isError } = useInsightsData()

  const maxCat = Math.max(1, ...(summary?.categories.map(c => c.pct) ?? []))
  const maxApp = Math.max(1, ...(summary?.top_apps.map(a => a.pct) ?? []))
  const maxHour = Math.max(1, ...(summary?.hourly_heatmap.map(c => c.pct) ?? []))

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="insights"
        subtitle={summary && summary.observed_seconds > 0 ? `${fmtDur(summary.observed_seconds)} on screen` : undefined}
        right={<Segmented value={period} options={PERIODS} onChange={setPeriod} />}
      />

      {isLoading ? (
        <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>loading…</div>

      ) : isError ? (
        <EmptyState icon={<Icon name="warn" size={28} strokeWidth={1.2} />} title="couldn't load insights">
          the daemon may be unavailable.
        </EmptyState>

      ) : !summary || summary.categories.length === 0 ? (
        <EmptyState
          dashed
          icon={<Icon name="insights" size={28} strokeWidth={1.2} />}
          title={`no data for ${summary?.range.span_days === 1 ? selectedDate : `the past ${summary?.range.span_days ?? ''} days`}`}
        />

      ) : (
        <>
          <div className="m-grid2">
            {/* time by category — vertical bars; tallest = ink-4 */}
            <Card label="time by category">
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 'var(--space-md)', height: 200 }}>
                <div style={{
                  display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
                  fontSize: '0.58rem', color: 'var(--muted)', textAlign: 'right',
                  fontWeight: 300, paddingBottom: 18,
                }}>
                  <span>{fmtPct(maxCat)}</span>
                  <span>{fmtPct((maxCat * 2) / 3)}</span>
                  <span>{fmtPct(maxCat / 3)}</span>
                  <span>0%</span>
                </div>
                <div style={{
                  display: 'grid', gridTemplateColumns: `repeat(${summary.categories.length}, 1fr)`,
                  gap: 'var(--space-md)', alignItems: 'end',
                }}>
                  {summary.categories.map(c => (
                    <div key={c.task_category} style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center',
                      gap: 6, height: '100%', justifyContent: 'flex-end',
                    }}>
                      <div
                        title={fmtPct(c.pct)}
                        style={{
                          width: 22, height: Math.max(4, (c.pct / maxCat) * 160),
                          background: c.pct === maxCat ? 'var(--ink-4)' : 'var(--ink-2)',
                        }}
                      />
                      <span style={{
                        fontSize: '0.58rem', color: 'var(--muted)', fontWeight: 300,
                        letterSpacing: 'var(--tracking-snug)',
                      }}>
                        {c.task_category}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>

            {/* productivity split — monochrome donut */}
            <Card label="productivity split">
              <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 'var(--space-sm)' }}>
                <Donut
                  segments={summary.productivity_states.map(s => ({
                    name: s.productivity_state,
                    pct: s.pct,
                    level: stateInk(s.productivity_state),
                  }))}
                />
              </div>
            </Card>
          </div>

          {/* top apps — horizontal bars on an ink-0 track */}
          <Card label="top apps" style={{ marginTop: 'var(--space-sm)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {summary.top_apps.slice(0, 8).map((a, i) => (
                <div key={a.app_name} style={{
                  display: 'grid', gridTemplateColumns: '150px 1fr auto',
                  gap: 'var(--space-md)', alignItems: 'center',
                }}>
                  <span style={{
                    fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {a.app_name || 'unknown'}
                  </span>
                  <div style={{ height: 8, background: 'var(--ink-0)' }}>
                    <div style={{
                      width: `${(a.pct / maxApp) * 100}%`, height: '100%',
                      background: i === 0 ? 'var(--ink-4)' : 'var(--ink-3)',
                    }} />
                  </div>
                  <span style={{
                    fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300,
                    letterSpacing: 'var(--tracking-snug)', whiteSpace: 'nowrap',
                  }}>
                    {fmtDur(a.seconds)} · {fmtPct(a.pct)}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* hour-of-day — 24-cell strip, height by intensity */}
          <Card label="hour-of-day activity" style={{ marginTop: 'var(--space-sm)' }}>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(24, 1fr)', gap: 3,
              alignItems: 'end', height: 60,
            }}>
              {summary.hourly_heatmap.map(cell => {
                const lv = hourLevel(cell, maxHour)
                return (
                  <div
                    key={cell.hour}
                    title={cell.pct === 0
                      ? `${String(cell.hour).padStart(2, '0')}:00 — no activity`
                      : `${String(cell.hour).padStart(2, '0')}:00 — ${fmtPct(cell.pct)}`}
                    style={{
                      height: lv === 0 ? 4 : 12 + (lv / 4) * 44,
                      background: inkVar(lv),
                    }}
                  />
                )
              })}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', marginTop: 'var(--space-xs)' }}>
              {['00', '03', '06', '09', '12', '15', '18', '21'].map(h => (
                <span key={h} style={{
                  fontSize: '0.55rem', color: 'var(--muted)', fontWeight: 300,
                  letterSpacing: 'var(--tracking-snug)',
                }}>
                  {h}
                </span>
              ))}
            </div>
          </Card>

          <div className="m-grid2" style={{ marginTop: 'var(--space-sm)' }}>
            <Card label={`vs ${summary.comparison.baseline_label.toLowerCase()}`}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                <ComparisonRow label="active"     metric={summary.comparison.active}     positiveGood={true} />
                <ComparisonRow label="productive" metric={summary.comparison.productive} positiveGood={true} />
                <ComparisonRow label="distracted" metric={summary.comparison.distracted} positiveGood={false} />
              </div>
            </Card>

            <Card label="recurring activities">
              {summary.recurring_activities.length === 0 ? (
                <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>
                  no recurring patterns detected.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                  {summary.recurring_activities.map((r, i) => (
                    <div
                      key={i}
                      title={`≈${fmtDur(r.approx_seconds)}${r.variant_count > 1 ? ` · ${r.variant_count} variants` : ''}`}
                      style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 'var(--space-md)', alignItems: 'baseline' }}
                    >
                      <span style={{
                        fontSize: 'var(--text-base)', color: 'var(--fg)', fontWeight: 300,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {r.canonical_summary}
                      </span>
                      <span style={{
                        fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300,
                        letterSpacing: 'var(--tracking-snug)', whiteSpace: 'nowrap',
                      }}>
                        ×{r.occurrences}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
