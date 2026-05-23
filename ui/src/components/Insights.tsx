import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { CATEGORY_CHIP, STATE_COLORS } from '../utils/design'
import { useAppDate } from '../context/DateContext'

function useTooltipStyle() {
  return useMemo(() => {
    const s = getComputedStyle(document.documentElement)
    const bg   = s.getPropertyValue('--tooltip-bg').trim()
    const text = s.getPropertyValue('--tooltip-text').trim()
    const dim  = s.getPropertyValue('--text-dim').trim()
    const isLight = document.documentElement.classList.contains('light')
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
  }, [document.documentElement.classList.contains('light')])
}

export default function Insights() {
  const { selectedDate } = useAppDate()
  const TT = useTooltipStyle()

  // Explicit tooltip-active state for each chart so we can force-clear it on
  // mouse-leave rather than relying on Recharts' internal SVG mouseleave logic,
  // which is unreliable in Electron's Chromium runtime.
  const [barActive,  setBarActive]  = useState(false)
  const [pieActive,  setPieActive]  = useState(false)
  const [pieSegment, setPieSegment] = useState(-1)

  const { data: insights, isLoading } = useQuery({
    queryKey: queryKeys.dailyInsights(selectedDate),
    queryFn: () => api.getDailyInsights(selectedDate),
  })

  return (
    <div className="page-enter p-7">

      <div className="flex items-center mb-6">
        <h1 className="text-[19px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
          Insights
        </h1>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-64 rounded-[12px]" />)}
        </div>

      ) : !insights || insights.categories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24">
          <div className="text-4xl mb-4 opacity-20">◎</div>
          <div className="text-[14px]" style={{ color: 'var(--text-muted)' }}>No data for {selectedDate}</div>
        </div>

      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

          {/* Bar chart */}
          <div
            className="rounded-[12px] border p-5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Time by Category
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={insights.categories}
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
                />
                <Tooltip {...TT} active={barActive} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {insights.categories.map(entry => (
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

          {/* Donut */}
          <div
            className="rounded-[12px] border p-5"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Productivity Split
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart
                onMouseLeave={() => { setPieActive(false); setPieSegment(-1) }}
              >
                <Pie
                  data={insights.productivity_states}
                  dataKey="count"
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
                  {insights.productivity_states.map(entry => (
                    <Cell
                      key={entry.productivity_state}
                      fill={STATE_COLORS[entry.productivity_state] ?? '#64748b'}
                      opacity={0.9}
                    />
                  ))}
                </Pie>
                <Tooltip {...TT} active={pieActive} />
                <Legend
                  iconSize={7}
                  iconType="circle"
                  wrapperStyle={{ fontSize: 11, color: TT.axisTickFill }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Top apps */}
          <div
            className="rounded-[12px] border p-5 lg:col-span-2"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold tracking-[0.08em] uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
              Top Apps
            </h2>
            <div className="space-y-2.5">
              {insights.top_apps.slice(0, 8).map(app => {
                const max = insights.top_apps[0]?.count ?? 1
                const pct = Math.round((app.count / max) * 100)
                return (
                  <div key={app.app_name} className="flex items-center gap-3">
                    <span className="text-[13px] w-36 truncate shrink-0" style={{ color: 'var(--text-muted)' }}>
                      {app.app_name || 'Unknown'}
                    </span>
                    <div className="flex-1 rounded-full h-1.5 overflow-hidden" style={{ background: 'var(--bg-surface-2)' }}>
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, background: 'var(--accent)', opacity: 0.65 }}
                      />
                    </div>
                    <span className="text-[11px] font-mono w-10 text-right shrink-0" style={{ color: 'var(--text-dim)' }}>
                      {app.count}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

        </div>
      )}
    </div>
  )
}

