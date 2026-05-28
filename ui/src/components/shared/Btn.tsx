import React from 'react'

export type BtnVariant = 'ghost' | 'primary' | 'danger'

const btnStyles: Record<BtnVariant, React.CSSProperties> = {
  ghost:   { background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' },
  primary: { background: 'var(--accent)',        color: '#fff',              border: 'none' },
  danger:  { background: 'var(--red-bg)',        color: 'var(--red)',         border: '1px solid rgba(248,113,113,0.2)' },
}

interface BtnProps {
  onClick?: () => void
  disabled?: boolean
  children: React.ReactNode
  variant?: BtnVariant
}

export default function Btn({ onClick, disabled, children, variant = 'ghost' }: BtnProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-4 py-2 rounded-[9px] text-[13px] font-medium transition-all duration-150 disabled:opacity-40"
      style={btnStyles[variant]}
    >
      {children}
    </button>
  )
}
