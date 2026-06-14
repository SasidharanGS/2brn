import type { CSSProperties } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { useDevices } from '../hooks/useDevices'
import { Page, PageHeader, Card, Button, Notice, TokenField, SectionLabel, EmptyState, Icon } from '../ui-kit'

function fmtDate(iso: string | null): string {
  if (!iso) return 'never'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return (
    d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ' ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  )
}

const cardTitle: CSSProperties = {
  fontSize: 'var(--k-text-title)', color: 'var(--k-fg)',
  fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'],
  textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'],
}

// Unified Devices ("Connect a device") — one component for both skins.
export default function Devices() {
  const {
    devices, isLoading, lanUrl, lanAccess, lanReady,
    name, setName, addDevice, created, pairingUrl, dismissCreated,
    revoke, createMut, revokeMut,
  } = useDevices()

  const subtitle = devices.length === 0
    ? 'No devices paired yet'
    : `${devices.length} paired ${devices.length === 1 ? 'device' : 'devices'}`

  return (
    <Page max={640}>
      <PageHeader title="Connect a device" subtitle={subtitle} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-md)' }}>
        {!lanReady && (
          <Notice>
            {lanAccess
              ? 'No LAN address found — connect this computer to Wi-Fi or Ethernet so your phone can reach it.'
              : 'LAN access is off. Turn it on in Settings and restart 2brn, then your phone can connect over Wi-Fi.'}
          </Notice>
        )}

        <Card>
          {created ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--k-space-md)', textAlign: 'center' }}>
              <div style={cardTitle}>Scan this in the 2brn app</div>
              <div style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-dim)', textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'] }}>
                {created.name} · Connect a device → Scan QR. This code is shown once.
              </div>
              {pairingUrl ? (
                <div style={{ background: '#ffffff', padding: 14, borderRadius: 'var(--k-radius)' }}>
                  <QRCodeSVG value={pairingUrl} size={184} bgColor="#ffffff" fgColor="#000000" level="M" />
                </div>
              ) : (
                <div style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)', maxWidth: 380 }}>
                  Enable LAN access (above) to show a scannable QR. You can still pair manually with the URL and token below.
                </div>
              )}
              <div style={{ width: '100%', maxWidth: 420, display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)', textAlign: 'left' }}>
                <TokenField label="Desktop URL" value={lanUrl ?? '— enable LAN access —'} />
                <TokenField label="Pairing token" value={created.token} mono />
              </div>
              <Button variant="soft" onClick={dismissCreated}>Done</Button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
              <div style={cardTitle}>Pair a new phone</div>
              <div style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-dim)', textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'] }}>
                Each phone gets its own token, so you can revoke one without affecting the others.
              </div>
              <input
                className="k-input" value={name}
                onChange={e => setName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') addDevice() }}
                placeholder="Device name (e.g. My phone)"
                style={{ width: '100%', fontSize: 'var(--k-text-sm)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Button variant="soft" onClick={addDevice} disabled={createMut.isPending}>
                  <Icon name="plus" size={13} />{createMut.isPending ? 'Generating…' : 'Generate pairing code'}
                </Button>
              </div>
              {createMut.isError && (
                <div style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-danger)' }}>
                  Couldn't create a pairing code. Is the daemon running?
                </div>
              )}
            </div>
          )}
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--k-space-sm)' }}>
          <SectionLabel>Paired devices</SectionLabel>
          {isLoading && <div style={{ fontSize: 'var(--k-text-body)', color: 'var(--k-muted)' }}>Loading…</div>}
          {!isLoading && devices.length === 0 && (
            <EmptyState dashed icon="devices">No phones paired yet.</EmptyState>
          )}
          {devices.map(d => (
            <Card key={d.id} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--k-space-md)' }}>
              <div>
                <div style={{ fontSize: 'var(--k-text-title)', color: 'var(--k-fg)', fontWeight: 'var(--k-emphasis-weight)' as CSSProperties['fontWeight'] }}>{d.name}</div>
                <div style={{ fontSize: 'var(--k-text-meta)', color: 'var(--k-muted)', marginTop: 2, textTransform: 'var(--k-text-transform)' as CSSProperties['textTransform'] }}>
                  Added {fmtDate(d.created_at)} · last seen {fmtDate(d.last_seen_at)}
                </div>
              </div>
              <Button onClick={() => revoke(d.id)} disabled={revokeMut.isPending}>Revoke</Button>
            </Card>
          ))}
        </div>
      </div>
    </Page>
  )
}
