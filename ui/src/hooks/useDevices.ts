import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import type { CreatedDevice } from '../api/types'
import { buildPairingUrl } from '../lib/pairing'

/**
 * Paired-device list + pairing flow, shared by both skins.
 *
 * Minting returns the plaintext token exactly once; we hold it in `created`
 * only long enough to render the QR / manual token, then the caller dismisses
 * it. `lanReady` tells the screen whether a phone can actually reach the daemon
 * (LAN access on + a LAN IP available) so it can warn before pairing.
 */
export function useDevices() {
  const qc = useQueryClient()

  const { data: devices = [], isLoading } = useQuery({
    queryKey: queryKeys.devices(),
    queryFn: api.listDevices,
  })
  const { data: connInfo } = useQuery({
    queryKey: queryKeys.connectionInfo(),
    queryFn: api.getConnectionInfo,
  })

  const [name, setName] = useState('')
  const [created, setCreated] = useState<CreatedDevice | null>(null)

  const createMut = useMutation({
    mutationFn: (deviceName: string) => api.createDevice(deviceName),
    onSuccess: (device) => {
      setCreated(device)
      setName('')
      qc.invalidateQueries({ queryKey: queryKeys.devices() })
    },
  })
  const revokeMut = useMutation({
    mutationFn: (id: number) => api.revokeDevice(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.devices() }),
  })

  const lanUrl = connInfo?.lan_urls[0] ?? null
  const lanAccess = connInfo?.lan_access ?? false
  const lanReady = lanAccess && !!lanUrl
  const pairingUrl = useMemo(
    () => (lanUrl && created ? buildPairingUrl(lanUrl, created.token) : null),
    [lanUrl, created],
  )

  function addDevice() {
    if (createMut.isPending) return
    createMut.mutate(name.trim() || 'phone')
  }

  return {
    devices, isLoading,
    connInfo, lanUrl, lanAccess, lanReady,
    name, setName, addDevice,
    created, pairingUrl, dismissCreated: () => setCreated(null),
    revoke: (id: number) => revokeMut.mutate(id),
    createMut, revokeMut,
  }
}
