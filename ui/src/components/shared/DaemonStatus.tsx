import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'

export default function DaemonStatus() {
  const { data: status } = useQuery({
    queryKey: queryKeys.status(),
    queryFn: api.getStatus,
    refetchInterval: 5_000,
    retry: false,
  })

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
