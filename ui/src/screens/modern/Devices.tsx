import { QRCodeSVG } from 'qrcode.react'
import { useDevices } from '../../hooks/useDevices'

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
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="flex items-center justify-between px-6 py-4 shrink-0 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <div>
          <h1 className="text-[16px] font-semibold" style={{ color: 'var(--text)' }}>
            Connect a device
          </h1>
          <p className="text-[12px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
            {devices.length === 0
              ? 'No devices paired yet'
              : `${devices.length} paired ${devices.length === 1 ? 'device' : 'devices'}`}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4">
        {!lanReady && (
          <div
            className="rounded-[10px] px-4 py-3 text-[12px] flex items-start gap-2"
            style={{ background: 'var(--accent-glow)', border: '1px solid var(--border-focus)', color: 'var(--text-muted)' }}
          >
            <span aria-hidden="true">⚠️</span>
            <span>
              {lanAccess
                ? 'No LAN address found — connect this computer to Wi-Fi or Ethernet so your phone can reach it.'
                : 'LAN access is off. Turn it on in Settings and restart 2brn, then your phone can connect over Wi-Fi.'}
            </span>
          </div>
        )}

        {/* Pair a new phone */}
        <div className="rounded-[12px] p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          {created ? (
            <div className="flex flex-col items-center gap-4 text-center">
              <div>
                <h2 className="text-[14px] font-semibold" style={{ color: 'var(--text)' }}>
                  Scan this in the 2brn app
                </h2>
                <p className="text-[12px] mt-1" style={{ color: 'var(--text-dim)' }}>
                  {created.name} · Connect a device → Scan QR. This code is shown once.
                </p>
              </div>

              {pairingUrl ? (
                <div style={{ background: '#ffffff', padding: 14, borderRadius: 10 }}>
                  <QRCodeSVG value={pairingUrl} size={184} bgColor="#ffffff" fgColor="#000000" level="M" />
                </div>
              ) : (
                <p className="text-[12px] max-w-[380px]" style={{ color: 'var(--text-muted)' }}>
                  Enable LAN access (above) to show a scannable QR. You can still pair manually with the URL and
                  token below.
                </p>
              )}

              <div className="w-full max-w-[420px] flex flex-col gap-2 text-left">
                <Field label="Desktop URL" value={lanUrl ?? '— enable LAN access —'} />
                <Field label="Pairing token" value={created.token} mono />
              </div>

              <button
                onClick={dismissCreated}
                className="px-4 py-1.5 rounded-[8px] text-[12px] font-medium"
                style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)' }}
              >
                Done
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <h2 className="text-[14px] font-semibold" style={{ color: 'var(--text)' }}>
                Pair a new phone
              </h2>
              <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
                Each phone gets its own token, so you can revoke one without affecting the others.
              </p>
              <div className="flex gap-2">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') addDevice() }}
                  placeholder="Device name (e.g. My phone)"
                  className="flex-1 px-3 py-2 rounded-[8px] text-[13px]"
                  style={{ background: 'var(--bg-base)', color: 'var(--text)', border: '1px solid var(--border)' }}
                />
                <button
                  onClick={addDevice}
                  disabled={createMut.isPending}
                  className="px-3 py-2 rounded-[8px] text-[12px] font-medium whitespace-nowrap"
                  style={{ background: 'var(--accent-glow)', color: 'var(--accent)', border: '1px solid var(--border-focus)', opacity: createMut.isPending ? 0.6 : 1 }}
                >
                  {createMut.isPending ? 'Generating…' : '+ Generate pairing code'}
                </button>
              </div>
              {createMut.isError && (
                <p className="text-[12px]" style={{ color: 'var(--danger, #ef4444)' }}>
                  Couldn't create a pairing code. Is the daemon running?
                </p>
              )}
            </div>
          )}
        </div>

        {/* Paired devices */}
        <div className="flex flex-col gap-2">
          <h2 className="text-[12px] font-semibold uppercase tracking-wider px-1" style={{ color: 'var(--text-dim)' }}>
            Paired devices
          </h2>
          {isLoading && <p className="text-[12px] px-1" style={{ color: 'var(--text-dim)' }}>Loading…</p>}
          {!isLoading && devices.length === 0 && (
            <div
              className="flex flex-col items-center justify-center py-12 gap-2 rounded-[12px]"
              style={{ border: '1px dashed var(--border-2)' }}
            >
              <span className="text-[24px]">📱</span>
              <p className="text-[13px]" style={{ color: 'var(--text-muted)' }}>No phones paired yet.</p>
            </div>
          )}
          {devices.map((d) => (
            <div
              key={d.id}
              className="flex items-center justify-between px-4 py-3 rounded-[10px]"
              style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
            >
              <div>
                <p className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>{d.name}</p>
                <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
                  Added {fmtDate(d.created_at)} · last seen {fmtDate(d.last_seen_at)}
                </p>
              </div>
              <button
                onClick={() => revoke(d.id)}
                disabled={revokeMut.isPending}
                className="px-3 py-1.5 rounded-[8px] text-[12px] font-medium"
                style={{ background: 'transparent', color: 'var(--danger, #ef4444)', border: '1px solid var(--border)' }}
              >
                Revoke
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
        {label}
      </span>
      <code
        className="px-3 py-2 rounded-[8px] text-[12px] break-all select-all"
        style={{
          background: 'var(--bg-base)', color: 'var(--text)', border: '1px solid var(--border)',
          fontFamily: mono ? 'var(--font-mono, monospace)' : undefined,
        }}
      >
        {value}
      </code>
    </div>
  )
}
