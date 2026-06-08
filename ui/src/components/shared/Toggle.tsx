interface ToggleProps {
  enabled: boolean
  onToggle: () => void
  label?: string
}

export default function Toggle({ enabled, onToggle, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={onToggle}
      className="relative shrink-0 rounded-full transition-all duration-200"
      style={{
        width: 32,
        height: 18,
        background: enabled ? 'var(--accent)' : 'var(--bg-surface-3)',
        border: `1px solid ${enabled ? 'var(--accent)' : 'var(--border-2)'}`,
      }}
    >
      <span
        className="absolute top-[2px] rounded-full transition-all duration-200"
        style={{
          width: 12,
          height: 12,
          background: 'var(--toggle-knob)',
          left: enabled ? 16 : 2,
        }}
      />
    </button>
  )
}
