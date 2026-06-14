import type { CSSProperties } from 'react'

// 2brn icon set — thin-line, geometric, stroke 1.5, currentColor.
// Matches the design language's custom-SVG iconography (no emoji, no fills).
// Paths extracted from the design handoff prototype (BRN_ICON_PATHS).
const BRN_ICON_PATHS = {
  home: '<path d="M3 9.5 12 3l9 6.5"/><path d="M5 9v11h14V9"/>',
  chat: '<path d="M4 5h16v10H9l-4 4v-4H4z"/>',
  journal: '<path d="M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z"/><path d="M9 4v16"/>',
  blog: '<path d="M4 20l1-4L16 5l3 3L8 19z"/><path d="M14 7l3 3"/>',
  timeline: '<circle cx="12" cy="12" r="8"/><path d="M12 8v4l3 2"/>',
  insights: '<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.3 1 2.5h6c0-1.2.3-1.8 1-2.5A6 6 0 0 0 12 3z"/>',
  instructions: '<rect x="5" y="4" width="14" height="17" rx="1"/><path d="M9 4V3h6v1"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  plugins: '<path d="M9 3v5M15 3v5"/><path d="M7 8h10v3a5 5 0 0 1-10 0z"/><path d="M12 16v5"/>',
  devices: '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 18h2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M22 12h-3M5 12H2M19 19l-2-2M7 7 5 5M19 5l-2 2M7 17l-2 2"/>',
  calendar: '<rect x="4" y="5" width="16" height="16" rx="1"/><path d="M4 9h16M8 3v4M16 3v4"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m20 20-4-4"/>',
  send: '<path d="M5 12h13M12 5l7 7-7 7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="1"/><path d="M8 20h8M12 16v4"/>',
  moon: '<path d="M20 14A8 8 0 0 1 10 4a7 7 0 1 0 10 10z"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevronL: '<path d="M15 6l-6 6 6 6"/>',
  chevronR: '<path d="M9 6l6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M4 20h4L18 10l-4-4L4 16z"/><path d="M13 5l4 4"/>',
  refresh: '<path d="M4 12a8 8 0 0 1 14-5l2 2M20 12a8 8 0 0 1-14 5l-2-2"/><path d="M20 4v3h-3M4 20v-3h3"/>',
  dot: '<circle cx="12" cy="12" r="4"/>',
  warn: '<path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18v.5"/>',
} as const

export type IconName = keyof typeof BRN_ICON_PATHS

interface IconProps {
  name: IconName
  size?: number
  strokeWidth?: number
  style?: CSSProperties
}

export default function Icon({ name, size = 16, strokeWidth = 1.5, style }: IconProps) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      style={{ flex: '0 0 auto', display: 'block', ...style }}
      dangerouslySetInnerHTML={{ __html: BRN_ICON_PATHS[name] }}
    />
  )
}
