import { QRCodeSVG } from 'qrcode.react'
import { useDevices } from '../../hooks/useDevices'
import PageHeader from './PageHeader'
import Icon from './Icon'
import { Card, GhostButton, EmptyState, Label, lineInput } from './primitives'

function fmtDate(iso: string | null): string {
  if (!iso) return 'never'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return (
    d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) +
    ' ' +
    d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  )
}

export default function Devices() {
  const {
    devices, isLoading, lanUrl, lanAccess, lanReady,
    name, setName, addDevice, created, pairingUrl, dismissCreated,
    revoke, createMut, revokeMut,
  } = useDevices()

  return (
    <div style={{ padding: 'var(--space-lg)' }}>
      <PageHeader
        title="connect a device"
        subtitle={devices.length === 0
          ? 'no devices paired'
          : `${devices.length} paired ${devices.length === 1 ? 'device' : 'devices'}`}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)', maxWidth: 620 }}>
        {!lanReady && (
          <div style={{
            border: '1px solid var(--muted)', padding: 'var(--space-md)',
            fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300,
            lineHeight: 'var(--leading-normal)',
          }}>
            {lanAccess
              ? 'no lan address found — connect this computer to wi-fi or ethernet so your phone can reach it.'
              : 'lan access is off. turn it on in settings and restart 2brn, then your phone can connect over wi-fi.'}
          </div>
        )}

        <Card label="pair a new phone">
          {created ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--space-md)', textAlign: 'center' }}>
              <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>
                {created.name} · scan in the 2brn app (connect a device → scan qr). shown once.
              </div>
              {pairingUrl ? (
                <div style={{ background: '#ffffff', padding: 14 }}>
                  <QRCodeSVG value={pairingUrl} size={184} bgColor="#ffffff" fgColor="#000000" level="M" />
                </div>
              ) : (
                <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300, maxWidth: 360 }}>
                  enable lan access to show a scannable qr. you can still pair manually with the url + token below.
                </div>
              )}
              <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)', textAlign: 'left' }}>
                <TokenField label="desktop url" value={lanUrl ?? '— enable lan access —'} />
                <TokenField label="pairing token" value={created.token} mono />
              </div>
              <GhostButton accent onClick={dismissCreated}>done</GhostButton>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>
                each phone gets its own token, so you can revoke one without affecting the others.
              </div>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') addDevice() }}
                placeholder="device name (e.g. my phone)"
                style={lineInput}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <GhostButton accent onClick={addDevice} disabled={createMut.isPending}>
                  <Icon name="plus" size={13} />{createMut.isPending ? 'generating…' : 'generate pairing code'}
                </GhostButton>
              </div>
              {createMut.isError && (
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300 }}>
                  couldn't create a pairing code. is the daemon running?
                </div>
              )}
            </div>
          )}
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          <Label>paired devices</Label>
          {isLoading && (
            <div style={{ fontSize: 'var(--text-base)', color: 'var(--muted)', fontWeight: 300 }}>loading…</div>
          )}
          {!isLoading && devices.length === 0 && (
            <EmptyState dashed icon={<Icon name="devices" size={30} strokeWidth={1.2} />}>
              no phones paired yet.
            </EmptyState>
          )}
          {devices.map((d) => (
            <div key={d.id} style={{
              border: '1px solid var(--rule)', padding: 'var(--space-md)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-md)',
            }}>
              <div>
                <div style={{ fontSize: 'var(--text-md)', color: 'var(--fg)', fontWeight: 400 }}>{d.name}</div>
                <div style={{
                  fontSize: 'var(--text-2xs)', color: 'var(--muted)', fontWeight: 300,
                  letterSpacing: 'var(--tracking-wide)', marginTop: 2,
                }}>
                  added {fmtDate(d.created_at)} · last seen {fmtDate(d.last_seen_at)}
                </div>
              </div>
              <GhostButton onClick={() => revoke(d.id)} disabled={revokeMut.isPending}>revoke</GhostButton>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function TokenField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <Label>{label}</Label>
      <code style={{
        fontSize: 'var(--text-2xs)', color: 'var(--fg)', wordBreak: 'break-all', userSelect: 'all',
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-sans)',
        border: '1px solid var(--rule)', padding: '6px 8px',
      }}>
        {value}
      </code>
    </div>
  )
}
