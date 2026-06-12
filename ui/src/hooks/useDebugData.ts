import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

/** Tail of the daemon log (sliding window of the last 100 lines). */
export function useDebugLogs(enabled: boolean) {
  const { data } = useQuery({
    queryKey: ['debug-logs'],
    queryFn: () => api.getLogs(undefined, 100),
    refetchInterval: 2000,
    enabled,
  })
  return data
}

/** Daemon/gateway/chroma health snapshot for the debug panel. */
export function useDebugStatus(enabled: boolean) {
  const { data } = useQuery({
    queryKey: ['debug-status'],
    queryFn: api.getDebugStatus,
    refetchInterval: 5000,
    enabled,
  })
  return data
}
