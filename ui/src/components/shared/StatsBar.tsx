import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { stateChip, categoryChip } from '../../utils/design'

type ThemeMode = 'light' | 'system' | 'dark'

const THEME_SEGMENTS: { value: ThemeMode; label: string }[] = [
  { value: 'light',  label: '☀️' },
  { value: 'system', label: '💻' },
  { value: 'dark',   label: '🌙' },
]

interface Props {
  themeMode: ThemeMode
  onThemeModeChange: (mode: ThemeMode) => void
}

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

export default function StatsBar({ themeMode, onThemeModeChange }: Props) {
  const today = toDateStr(new Date())
  const { data: insights } = useQuery({
    queryKey: queryKeys.dailyInsights(today),
    queryFn: () => api.getDailyInsights(today),
    refetchInterval: 30_000,
  })

  const topState    = insights?.productivity_states[0]?.productivity_state ?? null
  const topCategory = insights?.categories[0]?.task_category ?? null
  const total       = insights?.categories.reduce((s, c) => s + c.count, 0) ?? 0
  const focusedCt   = insights?.productivity_states
    .filter(s => ['productive', 'focused'].includes(s.productivity_state))
    .reduce((s, c) => s + c.count, 0) ?? 0
  const focusPct = total > 0 ? Math.round((focusedCt / total) * 100) : 0

  const sc = stateChip(topState)
  const cc = categoryChip(topCategory)
  const focusColor = focusPct > 50 ? 'var(--green)' : focusPct > 25 ? 'var(--amber)' : 'var(--text-muted)'

  return (
    <div
      className="flex items-center gap-4 px-5 h-10 shrink-0 border-b text-[12px]"
      style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
    >
      {/* State */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-dim)' }}>now</span>
        <span
          className="px-2 py-0.5 rounded-full font-medium text-[11px]"
          style={{ background: sc.bg, color: sc.text }}
        >
          {topState ?? '—'}
        </span>
      </div>

      <div className="w-px h-3.5" style={{ background: 'var(--border-2)' }} />

      {/* Category */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-dim)' }}>top</span>
        <span
          className="px-2 py-0.5 rounded-full font-medium text-[11px]"
          style={{ background: cc.bg, color: cc.text }}
        >
          {topCategory ?? '—'}
        </span>
      </div>

      <div className="w-px h-3.5" style={{ background: 'var(--border-2)' }} />

      {/* Focus */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-dim)' }}>focused</span>
        <span className="font-mono font-medium" style={{ color: focusColor }}>
          {focusPct}%
        </span>
      </div>

      <div className="ml-auto flex items-center">
        <div
          className="flex items-center rounded-[6px] p-[2px] gap-[1px]"
          style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border)' }}
        >
          {THEME_SEGMENTS.map(seg => (
            <button
              key={seg.value}
              onClick={() => onThemeModeChange(seg.value)}
              className="px-1.5 py-[2px] rounded-[4px] text-[13px] transition-all duration-150"
              style={themeMode === seg.value
                ? { background: 'var(--bg-surface-3)', color: 'var(--accent)', fontWeight: 600 }
                : { background: 'transparent', color: 'var(--text-dim)' }
              }
            >
              {seg.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
