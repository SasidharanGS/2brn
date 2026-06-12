import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'

/** Live daemon status (capturing/paused + today's capture count); undefined while offline. */
export function useDaemonStatus() {
  const { data: status } = useQuery({
    queryKey: queryKeys.status(),
    queryFn: api.getStatus,
    refetchInterval: 5_000,
    retry: false,
  })
  return status
}
