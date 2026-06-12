import { useDaemonStatus } from '../../hooks/useDaemonStatus'

export default function DaemonStatus() {
  const status = useDaemonStatus()

  if (!status) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full pulse" style={{ background: 'var(--red)' }} />
        <span className="text-[11px] font-mono" style={{ color: 'var(--red)', opacity: 0.7 }}>offline</span>
      </div>
    )
  }

  const isCapturing = status.status === 'capturing'
  const isPaused    = status.status === 'paused'
  const dotColor  = isCapturing ? 'var(--green)' : isPaused ? 'var(--amber)' : 'var(--red)'
  const textColor = isCapturing ? 'var(--green)' : isPaused ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full pulse" style={{ background: dotColor }} />
      <span className="text-[11px] font-mono" style={{ color: textColor, opacity: 0.85 }}>
        {status.status} · {status.capture_count_today.toLocaleString()}
      </span>
    </div>
  )
}
