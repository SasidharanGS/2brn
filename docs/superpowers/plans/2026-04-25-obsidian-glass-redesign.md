# Obsidian Glass UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the 2brn Electron UI with the "Obsidian Glass" aesthetic — deep charcoal backgrounds, subtle glass/blur surfaces, indigo accents, Geist typography, refined whitespace, and polished micro-details throughout.

**Architecture:** All changes are purely visual (CSS + JSX structure). No logic, API calls, or state management changes. The design system is established in `index.css` (CSS variables + base styles), `tailwind.config.js` (extended tokens), and a new `ui/src/utils/design.ts` (shared class helpers). Each component is then rewritten to use the new system.

**Tech Stack:** React 19, Tailwind v3, Geist font (Google Fonts CDN), CSS custom properties, Electron 31

---

## File Map

| File | Change |
|------|--------|
| `ui/index.html` | Add Geist font import from Google Fonts |
| `ui/src/index.css` | Full rewrite — CSS variables, base styles, animations, scrollbar |
| `ui/tailwind.config.js` | Extend with design tokens (colors, fonts, border-radius, shadows) |
| `ui/src/utils/design.ts` | New — shared class name helpers (chip colors per category/state) |
| `ui/src/App.tsx` | New persistent layout: sidebar + stats bar wiring |
| `ui/src/components/Dashboard.tsx` | Redesigned |
| `ui/src/components/Timeline.tsx` | Redesigned |
| `ui/src/components/Insights.tsx` | Redesigned |
| `ui/src/components/Journal.tsx` | Redesigned |
| `ui/src/components/Chat.tsx` | Redesigned |
| `ui/src/components/Settings.tsx` | Redesigned |
| `ui/src/components/shared/DaemonStatus.tsx` | Redesigned |
| `ui/src/components/shared/StatsBar.tsx` | Redesigned |

---

## Task 1: Font + CSS foundation

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/src/index.css`
- Modify: `ui/tailwind.config.js`

- [ ] **Step 1: Add Geist font to index.html**

```html
<!-- ui/index.html — add inside <head> before the closing tag -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Rewrite index.css**

```css
/* ui/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* Backgrounds */
  --bg-base:       #0e0e12;
  --bg-surface:    rgba(255, 255, 255, 0.04);
  --bg-surface-2:  rgba(255, 255, 255, 0.07);
  --bg-surface-3:  rgba(255, 255, 255, 0.10);
  --bg-input:      rgba(255, 255, 255, 0.06);

  /* Borders */
  --border:        rgba(255, 255, 255, 0.07);
  --border-2:      rgba(255, 255, 255, 0.12);
  --border-focus:  rgba(129, 140, 248, 0.6);

  /* Text */
  --text:          #f0f0f5;
  --text-muted:    rgba(240, 240, 245, 0.45);
  --text-dim:      rgba(240, 240, 245, 0.25);

  /* Accent — indigo */
  --accent:        #818cf8;
  --accent-hover:  #a5b4fc;
  --accent-glow:   rgba(129, 140, 248, 0.15);
  --accent-glow-2: rgba(129, 140, 248, 0.08);

  /* Semantic colours */
  --green:         #34d399;
  --green-bg:      rgba(52, 211, 153, 0.12);
  --amber:         #fbbf24;
  --amber-bg:      rgba(251, 191, 36, 0.12);
  --red:           #f87171;
  --red-bg:        rgba(248, 113, 113, 0.12);
  --blue:          #60a5fa;
  --blue-bg:       rgba(96, 165, 250, 0.12);
  --purple:        #c084fc;
  --purple-bg:     rgba(192, 132, 252, 0.12);
  --teal:          #2dd4bf;
  --teal-bg:       rgba(45, 212, 191, 0.12);
  --pink:          #f472b6;
  --pink-bg:       rgba(244, 114, 182, 0.12);

  /* Typography */
  --font-sans:  'Geist', -apple-system, sans-serif;
  --font-mono:  'Geist Mono', 'JetBrains Mono', monospace;
}

*, *::before, *::after { box-sizing: border-box; }

html, body {
  height: 100%;
  background: var(--bg-base);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  margin: 0;
}

/* Noise texture overlay for depth */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  opacity: 0.025;
  pointer-events: none;
  z-index: 9999;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

/* Focus ring */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* Glass surface utility */
.glass {
  background: var(--bg-surface);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* Pulse animation for status dots */
@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.pulse { animation: status-pulse 2.4s ease-in-out infinite; }

/* Fade-in for page transitions */
@keyframes fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
.page-enter { animation: fade-in 0.2s ease-out forwards; }

/* Skeleton shimmer */
@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-surface) 25%,
    var(--bg-surface-2) 50%,
    var(--bg-surface) 75%
  );
  background-size: 800px 100%;
  animation: shimmer 1.6s infinite;
  border-radius: 4px;
}
```

- [ ] **Step 3: Extend tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', '-apple-system', 'sans-serif'],
        mono: ['Geist Mono', 'JetBrains Mono', 'monospace'],
      },
      colors: {
        base:    '#0e0e12',
        accent:  '#818cf8',
        'accent-hover': '#a5b4fc',
      },
      boxShadow: {
        'glow-sm': '0 0 0 1px rgba(129,140,248,0.3), 0 0 12px rgba(129,140,248,0.1)',
        'glow':    '0 0 0 1px rgba(129,140,248,0.4), 0 0 24px rgba(129,140,248,0.15)',
      },
      borderRadius: {
        'xl2': '14px',
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 4: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
pnpm exec tsc --noEmit
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/index.html ui/src/index.css ui/tailwind.config.js
git commit -m "feat(design): Obsidian Glass — CSS foundation, Geist font, design tokens"
```

---

## Task 2: Shared design utilities

**Files:**
- Create: `ui/src/utils/design.ts`

- [ ] **Step 1: Create design.ts**

```typescript
// ui/src/utils/design.ts
// Centralised class/style helpers so category colours are defined once.

export const CATEGORY_CHIP: Record<string, { bg: string; text: string; dot: string }> = {
  work:          { bg: 'rgba(96,165,250,0.12)',  text: '#60a5fa', dot: '#60a5fa' },
  research:      { bg: 'rgba(192,132,252,0.12)', text: '#c084fc', dot: '#c084fc' },
  play:          { bg: 'rgba(52,211,153,0.12)',  text: '#34d399', dot: '#34d399' },
  learning:      { bg: 'rgba(251,191,36,0.12)',  text: '#fbbf24', dot: '#fbbf24' },
  communication: { bg: 'rgba(45,212,191,0.12)',  text: '#2dd4bf', dot: '#2dd4bf' },
  creative:      { bg: 'rgba(244,114,182,0.12)', text: '#f472b6', dot: '#f472b6' },
  admin:         { bg: 'rgba(148,163,184,0.12)', text: '#94a3b8', dot: '#94a3b8' },
  other:         { bg: 'rgba(100,116,139,0.12)', text: '#64748b', dot: '#64748b' },
}

export const STATE_CHIP: Record<string, { bg: string; text: string }> = {
  productive:      { bg: 'rgba(52,211,153,0.12)',  text: '#34d399' },
  focused:         { bg: 'rgba(52,211,153,0.12)',  text: '#34d399' },
  chilling:        { bg: 'rgba(96,165,250,0.12)',  text: '#60a5fa' },
  procrastinating: { bg: 'rgba(248,113,113,0.12)', text: '#f87171' },
  distracted:      { bg: 'rgba(251,146,60,0.12)',  text: '#fb923c' },
  'in-meeting':    { bg: 'rgba(192,132,252,0.12)', text: '#c084fc' },
  idle:            { bg: 'rgba(100,116,139,0.12)', text: '#64748b' },
}

export function categoryChip(cat: string | null) {
  return CATEGORY_CHIP[cat ?? 'other'] ?? CATEGORY_CHIP.other
}

export function stateChip(state: string | null) {
  return STATE_CHIP[state ?? 'idle'] ?? STATE_CHIP.idle
}

/** Inline style object for a coloured dot */
export function dotStyle(cat: string | null): React.CSSProperties {
  return { background: categoryChip(cat).dot }
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/utils/design.ts
git commit -m "feat(design): add shared category/state chip colour helpers"
```

---

## Task 3: DaemonStatus + StatsBar (persistent layout pieces)

**Files:**
- Modify: `ui/src/components/shared/DaemonStatus.tsx`
- Modify: `ui/src/components/shared/StatsBar.tsx`

- [ ] **Step 1: Rewrite DaemonStatus.tsx**

```tsx
// ui/src/components/shared/DaemonStatus.tsx
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
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--red)] pulse" />
        <span className="text-[10px] font-mono text-[var(--red)] opacity-70">offline</span>
      </div>
    )
  }

  const isCapturing = status.status === 'capturing'
  const isPaused    = status.status === 'paused'
  const dotColor    = isCapturing ? 'var(--green)' : isPaused ? 'var(--amber)' : 'var(--red)'
  const textColor   = isCapturing ? 'var(--green)' : isPaused ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="flex items-center gap-1.5">
      <span
        className="w-1.5 h-1.5 rounded-full pulse"
        style={{ background: dotColor }}
      />
      <span
        className="text-[10px] font-mono"
        style={{ color: textColor, opacity: 0.85 }}
      >
        {status.status} · {status.capture_count_today.toLocaleString()}
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite StatsBar.tsx**

```tsx
// ui/src/components/shared/StatsBar.tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import { stateChip, categoryChip } from '../../utils/design'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

export default function StatsBar() {
  const today = toDateStr(new Date())
  const { data: insights } = useQuery({
    queryKey: queryKeys.dailyInsights(today),
    queryFn: () => api.getDailyInsights(today),
    refetchInterval: 30_000,
  })

  const topState    = insights?.productivity_states[0]?.productivity_state ?? null
  const topCategory = insights?.categories[0]?.task_category ?? null
  const total       = insights?.categories.reduce((s, c) => s + c.count, 0) ?? 0
  const focusedCt   = insights?.productivity_states
    .filter(s => ['productive', 'focused'].includes(s.productivity_state))
    .reduce((s, c) => s + c.count, 0) ?? 0
  const focusPct = total > 0 ? Math.round((focusedCt / total) * 100) : 0

  const sc = stateChip(topState)
  const cc = categoryChip(topCategory)

  return (
    <div
      className="flex items-center gap-5 px-6 h-10 border-b text-[11px] shrink-0"
      style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
    >
      {/* State */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-dim)' }}>now</span>
        <span
          className="px-2 py-0.5 rounded-full font-medium text-[10px]"
          style={{ background: sc.bg, color: sc.text }}
        >
          {topState ?? '—'}
        </span>
      </div>

      <div className="w-px h-3.5" style={{ background: 'var(--border)' }} />

      {/* Category */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-dim)' }}>top</span>
        <span
          className="px-2 py-0.5 rounded-full font-medium text-[10px]"
          style={{ background: cc.bg, color: cc.text }}
        >
          {topCategory ?? '—'}
        </span>
      </div>

      <div className="w-px h-3.5" style={{ background: 'var(--border)' }} />

      {/* Focus */}
      <div className="flex items-center gap-2">
        <span style={{ color: 'var(--text-dim)' }}>focused</span>
        <span
          className="font-medium font-mono"
          style={{ color: focusPct > 50 ? 'var(--green)' : focusPct > 25 ? 'var(--amber)' : 'var(--text-muted)' }}
        >
          {focusPct}%
        </span>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/shared/DaemonStatus.tsx ui/src/components/shared/StatsBar.tsx
git commit -m "feat(design): redesign DaemonStatus + StatsBar — Obsidian Glass"
```

---

## Task 4: App layout + Dashboard

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/components/Dashboard.tsx`

- [ ] **Step 1: Rewrite App.tsx**

```tsx
// ui/src/App.tsx
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard  from './components/Dashboard'
import Chat       from './components/Chat'
import Journal    from './components/Journal'
import Timeline   from './components/Timeline'
import Insights   from './components/Insights'
import Settings   from './components/Settings'
import DaemonStatus from './components/shared/DaemonStatus'
import StatsBar     from './components/shared/StatsBar'

const NAV = [
  { to: '/',        label: 'Home',     icon: '⌂',  end: true },
  { to: '/chat',    label: 'Chat',     icon: '💬' },
  { to: '/journal', label: 'Journal',  icon: '📔' },
  { to: '/timeline',label: 'Timeline', icon: '⏱' },
  { to: '/insights',label: 'Insights', icon: '◎' },
  { to: '/settings',label: 'Settings', icon: '⚙' },
]

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>

      {/* ── Sidebar ── */}
      <aside
        className="flex flex-col w-[200px] shrink-0 border-r"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
      >
        {/* Logo */}
        <div
          className="flex items-center justify-between px-4 py-4 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <span
            className="font-mono text-[15px] font-semibold tracking-tight"
            style={{ color: 'var(--text)' }}
          >
            2<span style={{ color: 'var(--accent)' }}>brn</span>
          </span>
        </div>

        {/* Nav items */}
        <nav className="flex-1 flex flex-col gap-0.5 p-2 pt-3">
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => [
                'flex items-center gap-2.5 px-3 py-2 rounded-[9px] text-[13px] transition-all duration-150 select-none',
                isActive
                  ? 'font-medium'
                  : 'hover:opacity-100',
              ].join(' ')}
              style={({ isActive }) => isActive
                ? { background: 'var(--accent-glow)', color: 'var(--text)', fontWeight: 500 }
                : { color: 'var(--text-muted)' }
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className="text-[14px] w-[18px] text-center"
                    style={{ color: isActive ? 'var(--accent)' : undefined, opacity: isActive ? 1 : 0.6 }}
                  >
                    {item.icon}
                  </span>
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Daemon status */}
        <div
          className="px-4 py-3 border-t"
          style={{ borderColor: 'var(--border)' }}
        >
          <DaemonStatus />
        </div>
      </aside>

      {/* ── Content ── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <StatsBar />
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/"         element={<Dashboard />} />
            <Route path="/chat"     element={<Chat />} />
            <Route path="/journal"  element={<Journal />} />
            <Route path="/timeline" element={<Timeline />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>

    </div>
  )
}
```

- [ ] **Step 2: Rewrite Dashboard.tsx**

```tsx
// ui/src/components/Dashboard.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const TILES = [
  { label: 'Journal',  path: '/journal',  icon: '📔', desc: "Today's narrative" },
  { label: 'Timeline', path: '/timeline', icon: '⏱', desc: 'Activity stream' },
  { label: 'Insights', path: '/insights', icon: '◎', desc: 'Productivity data' },
  { label: 'Settings', path: '/settings', icon: '⚙', desc: 'Configure 2brn' },
]

export default function Dashboard() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()

  const handleChat = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    navigate('/chat', { state: { initialQuestion: question } })
    setQuestion('')
  }

  return (
    <div className="page-enter p-8 max-w-[720px] mx-auto">

      {/* Header */}
      <div className="mb-8">
        <h1
          className="text-[22px] font-semibold tracking-tight mb-1"
          style={{ color: 'var(--text)' }}
        >
          your second brain
        </h1>
        <p className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
          {new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </p>
      </div>

      {/* Chat input */}
      <form onSubmit={handleChat} className="mb-10">
        <div
          className="flex gap-0 border rounded-[12px] overflow-hidden transition-all duration-200 focus-within:shadow-glow"
          style={{
            background: 'var(--bg-input)',
            borderColor: 'var(--border-2)',
          }}
        >
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Ask anything about your past activity…"
            className="flex-1 bg-transparent px-4 py-3 text-[13px] outline-none placeholder:text-[var(--text-dim)]"
            style={{ color: 'var(--text)' }}
          />
          <button
            type="submit"
            disabled={!question.trim()}
            className="px-5 py-3 text-[12px] font-semibold transition-colors duration-150 disabled:opacity-30"
            style={{
              background: 'var(--accent)',
              color: '#fff',
              borderRadius: '0 10px 10px 0',
            }}
          >
            Ask
          </button>
        </div>
      </form>

      {/* Nav tiles */}
      <div
        className="text-[10px] font-medium tracking-[0.1em] uppercase mb-3"
        style={{ color: 'var(--text-dim)' }}
      >
        Navigate
      </div>
      <div className="grid grid-cols-2 gap-2.5">
        {TILES.map(tile => (
          <button
            key={tile.path}
            onClick={() => navigate(tile.path)}
            className="group text-left rounded-[12px] p-4 border transition-all duration-150 hover:-translate-y-0.5"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border)',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.background = 'var(--bg-surface-2)'
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border-2)'
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.background = 'var(--bg-surface)'
              ;(e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'
            }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[16px]">{tile.icon}</span>
              <span className="text-[13px] font-medium" style={{ color: 'var(--text)' }}>
                {tile.label}
              </span>
            </div>
            <div className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              {tile.desc}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: TypeScript check**

```bash
pnpm exec tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add ui/src/App.tsx ui/src/components/Dashboard.tsx
git commit -m "feat(design): redesign App layout + Dashboard — Obsidian Glass"
```

---

## Task 5: Timeline

**Files:**
- Modify: `ui/src/components/Timeline.tsx`

- [ ] **Step 1: Rewrite Timeline.tsx**

```tsx
// ui/src/components/Timeline.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { categoryChip, stateChip } from '../utils/design'
import type { ActivityRecord } from '../api/types'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

export default function Timeline() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [selected, setSelected] = useState<ActivityRecord | null>(null)

  const { data: activities = [], isLoading: loadActs } = useQuery({
    queryKey: queryKeys.activities(selectedDate),
    queryFn: () => api.getActivities({ date: selectedDate }),
    select: acts => [...acts].sort((a, b) => b.started_at.localeCompare(a.started_at)),
  })
  const { data: captures = [], isLoading: loadCaps } = useQuery({
    queryKey: queryKeys.captures(selectedDate),
    queryFn: () => api.getCaptures(selectedDate),
  })
  const loading = loadActs || loadCaps

  return (
    <div className="page-enter p-7">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[18px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            Timeline
          </h1>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
            {captures.length} captures · {activities.length} activities
          </p>
        </div>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => { setSelectedDate(e.target.value); setSelected(null) }}
          className="rounded-[9px] px-3 py-1.5 text-[12px] border outline-none font-mono transition-colors"
          style={{
            background: 'var(--bg-input)',
            borderColor: 'var(--border-2)',
            color: 'var(--text)',
          }}
        />
      </div>

      {/* Content */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton h-14 rounded-[10px]" />
          ))}
        </div>
      ) : activities.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center py-24 text-center"
          style={{ color: 'var(--text-muted)' }}
        >
          <div className="text-3xl mb-3 opacity-30">⏱</div>
          <div className="text-[13px]">No activity recorded for {selectedDate}</div>
        </div>
      ) : (
        <div className="space-y-1.5">
          {activities.map(act => {
            const cc = categoryChip(act.task_category)
            const sc = stateChip(act.productivity_state)
            const isSelected = selected?.id === act.id
            return (
              <button
                key={act.id}
                onClick={() => setSelected(isSelected ? null : act)}
                className="w-full text-left rounded-[10px] border px-4 py-3 transition-all duration-150"
                style={{
                  background: isSelected ? 'var(--bg-surface-2)' : 'var(--bg-surface)',
                  borderColor: isSelected ? 'var(--border-focus)' : 'var(--border)',
                  boxShadow: isSelected ? '0 0 0 1px rgba(129,140,248,0.3)' : 'none',
                }}
              >
                <div className="flex items-center gap-3">
                  {/* Colour dot */}
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: cc.dot }}
                  />
                  {/* Time */}
                  <span
                    className="text-[11px] font-mono w-10 shrink-0"
                    style={{ color: 'var(--text-dim)' }}
                  >
                    {new Date(act.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {/* Summary */}
                  <span
                    className="text-[13px] flex-1 truncate"
                    style={{ color: 'var(--text)' }}
                  >
                    {act.summary ?? '—'}
                  </span>
                  {/* Category chip */}
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium shrink-0"
                    style={{ background: cc.bg, color: cc.text }}
                  >
                    {act.task_category ?? 'other'}
                  </span>
                  {/* State */}
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full shrink-0 hidden sm:block"
                    style={{ background: sc.bg, color: sc.text }}
                  >
                    {act.productivity_state ?? '—'}
                  </span>
                </div>

                {/* Expanded detail */}
                {isSelected && act.summary && (
                  <div
                    className="mt-3 pt-3 border-t text-[12px] leading-relaxed text-left"
                    style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}
                  >
                    {act.summary}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check + commit**

```bash
pnpm exec tsc --noEmit
git add ui/src/components/Timeline.tsx
git commit -m "feat(design): redesign Timeline — Obsidian Glass"
```

---

## Task 6: Insights

**Files:**
- Modify: `ui/src/components/Insights.tsx`

- [ ] **Step 1: Rewrite Insights.tsx**

```tsx
// ui/src/components/Insights.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import { CATEGORY_CHIP, STATE_COLORS } from '../utils/colors'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

// recharts tooltip style
const TooltipStyle = {
  contentStyle: {
    background: '#1a1a22',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8,
    fontSize: 11,
    color: '#f0f0f5',
  },
  labelStyle: { color: '#f0f0f5' },
}

export default function Insights() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))

  const { data: insights, isLoading } = useQuery({
    queryKey: queryKeys.dailyInsights(selectedDate),
    queryFn: () => api.getDailyInsights(selectedDate),
  })

  const catColors = Object.fromEntries(
    Object.entries(CATEGORY_CHIP).map(([k, v]) => [k, v.dot])
  )

  return (
    <div className="page-enter p-7">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-[18px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
          Insights
        </h1>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => setSelectedDate(e.target.value)}
          className="rounded-[9px] px-3 py-1.5 text-[12px] border outline-none font-mono"
          style={{
            background: 'var(--bg-input)',
            borderColor: 'var(--border-2)',
            color: 'var(--text)',
          }}
        />
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-64 rounded-[12px]" />)}
        </div>
      ) : !insights || insights.categories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24" style={{ color: 'var(--text-muted)' }}>
          <div className="text-3xl mb-3 opacity-30">◎</div>
          <div className="text-[13px]">No data for {selectedDate}</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

          {/* Bar chart */}
          <div
            className="rounded-[12px] p-5 border"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold mb-4 tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
              Time by Category
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={insights.categories} barSize={16}>
                <XAxis dataKey="task_category" tick={{ fill: 'var(--text-dim)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip {...TooltipStyle} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {insights.categories.map(entry => (
                    <Cell key={entry.task_category} fill={catColors[entry.task_category] ?? '#64748b'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Donut chart */}
          <div
            className="rounded-[12px] p-5 border"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold mb-4 tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
              Productivity Distribution
            </h2>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={insights.productivity_states}
                  dataKey="count"
                  nameKey="productivity_state"
                  cx="50%" cy="50%"
                  innerRadius={52} outerRadius={80}
                  strokeWidth={0}
                >
                  {insights.productivity_states.map(entry => (
                    <Cell
                      key={entry.productivity_state}
                      fill={STATE_COLORS[entry.productivity_state] ?? '#64748b'}
                    />
                  ))}
                </Pie>
                <Tooltip {...TooltipStyle} />
                <Legend
                  iconSize={8}
                  wrapperStyle={{ fontSize: 10, color: 'var(--text-muted)' }}
                  iconType="circle"
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Top apps */}
          <div
            className="rounded-[12px] p-5 border lg:col-span-2"
            style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
          >
            <h2 className="text-[12px] font-semibold mb-4 tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
              Top Apps
            </h2>
            <div className="space-y-2.5">
              {insights.top_apps.slice(0, 8).map(app => {
                const max = insights.top_apps[0]?.count ?? 1
                const pct = Math.round((app.count / max) * 100)
                return (
                  <div key={app.app_name} className="flex items-center gap-3">
                    <span
                      className="text-[12px] w-36 truncate shrink-0"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {app.app_name || 'Unknown'}
                    </span>
                    <div
                      className="flex-1 rounded-full h-1.5 overflow-hidden"
                      style={{ background: 'var(--bg-surface-2)' }}
                    >
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${pct}%`, background: 'var(--accent)', opacity: 0.7 }}
                      />
                    </div>
                    <span
                      className="text-[11px] font-mono w-12 text-right shrink-0"
                      style={{ color: 'var(--text-dim)' }}
                    >
                      {app.count}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
```

Note: `Insights.tsx` references `CATEGORY_CHIP` from `utils/design` and `STATE_COLORS` from `utils/colors`. Update the import to pull both from `utils/design`:

```tsx
import { CATEGORY_CHIP } from '../utils/design'

// Add STATE_COLORS mapping directly in Insights (since utils/colors has STATE_COLORS):
import { STATE_COLORS } from '../utils/colors'
```

- [ ] **Step 2: TypeScript check + commit**

```bash
pnpm exec tsc --noEmit
git add ui/src/components/Insights.tsx
git commit -m "feat(design): redesign Insights — Obsidian Glass"
```

---

## Task 7: Journal

**Files:**
- Modify: `ui/src/components/Journal.tsx`

- [ ] **Step 1: Rewrite Journal.tsx**

```tsx
// ui/src/components/Journal.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import MarkdownRenderer from './shared/MarkdownRenderer'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

const Btn = ({
  onClick, disabled, children, variant = 'ghost',
}: {
  onClick?: () => void
  disabled?: boolean
  children: React.ReactNode
  variant?: 'ghost' | 'primary' | 'danger'
}) => {
  const styles: Record<string, React.CSSProperties> = {
    ghost:   { background: 'var(--bg-surface-2)', color: 'var(--text-muted)', border: '1px solid var(--border)' },
    primary: { background: 'var(--accent)',        color: '#fff',               border: 'none' },
    danger:  { background: 'var(--red-bg)',        color: 'var(--red)',          border: '1px solid rgba(248,113,113,0.2)' },
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-4 py-2 rounded-[9px] text-[12px] font-medium transition-all duration-150 disabled:opacity-40"
      style={styles[variant]}
    >
      {children}
    </button>
  )
}

export default function Journal() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const qc = useQueryClient()

  const { data: entry } = useQuery({
    queryKey: queryKeys.journal(selectedDate),
    queryFn: () => api.getJournal(selectedDate),
    throwOnError: false,
    retry: false,
  })

  const generateMutation = useMutation({
    mutationFn: () => api.generateJournal(selectedDate),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.journal(selectedDate) }),
  })

  const saveMutation = useMutation({
    mutationFn: (content: string) => api.updateJournal(selectedDate, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.journal(selectedDate) })
      setEditing(false)
    },
  })

  const handleDateChange = (date: string) => {
    setSelectedDate(date)
    setEditing(false)
    setEditContent('')
  }

  return (
    <div className="page-enter p-7 max-w-[760px] mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-[18px] font-semibold tracking-tight" style={{ color: 'var(--text)' }}>
            Journal
          </h1>
          {entry?.edited_by_user && (
            <span
              className="text-[10px] px-2 py-0.5 rounded-full font-medium"
              style={{ background: 'var(--amber-bg)', color: 'var(--amber)' }}
            >
              edited
            </span>
          )}
        </div>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => handleDateChange(e.target.value)}
          className="rounded-[9px] px-3 py-1.5 text-[12px] border outline-none font-mono"
          style={{
            background: 'var(--bg-input)',
            borderColor: 'var(--border-2)',
            color: 'var(--text)',
          }}
        />
      </div>

      {/* Error banners */}
      {generateMutation.isError && (
        <div
          className="mb-4 px-4 py-3 rounded-[9px] text-[12px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}
        >
          Failed to generate journal entry.
        </div>
      )}
      {saveMutation.isError && (
        <div
          className="mb-4 px-4 py-3 rounded-[9px] text-[12px] border"
          style={{ background: 'var(--red-bg)', color: 'var(--red)', borderColor: 'rgba(248,113,113,0.2)' }}
        >
          Failed to save changes.
        </div>
      )}

      {/* No entry */}
      {!entry ? (
        <div
          className="rounded-[12px] border p-10 text-center"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <div className="text-3xl mb-3 opacity-20">📔</div>
          <p className="text-[13px] mb-5" style={{ color: 'var(--text-muted)' }}>
            No journal entry for {selectedDate}
          </p>
          <Btn
            variant="primary"
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
          >
            {generateMutation.isPending ? 'Generating…' : 'Generate Entry'}
          </Btn>
        </div>

      ) : editing ? (
        <div className="space-y-3">
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            rows={22}
            className="w-full rounded-[12px] border px-4 py-3 text-[13px] font-mono resize-none outline-none transition-all"
            style={{
              background: 'var(--bg-surface)',
              borderColor: 'var(--border-2)',
              color: 'var(--text)',
              lineHeight: 1.6,
            }}
          />
          <div className="flex justify-end gap-2">
            <Btn onClick={() => setEditing(false)}>Cancel</Btn>
            <Btn
              variant="primary"
              onClick={() => saveMutation.mutate(editContent)}
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </Btn>
          </div>
        </div>

      ) : (
        <div
          className="rounded-[12px] border p-6"
          style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
        >
          <MarkdownRenderer content={entry.content ?? ''} />
          <div
            className="flex gap-2 mt-6 pt-4 border-t"
            style={{ borderColor: 'var(--border)' }}
          >
            <Btn onClick={() => { setEditing(true); setEditContent(entry.content ?? '') }}>
              Edit
            </Btn>
            {!entry.edited_by_user && (
              <Btn
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                {generateMutation.isPending ? 'Regenerating…' : 'Regenerate'}
              </Btn>
            )}
          </div>
        </div>
      )}

    </div>
  )
}
```

- [ ] **Step 2: TypeScript check + commit**

```bash
pnpm exec tsc --noEmit
git add ui/src/components/Journal.tsx
git commit -m "feat(design): redesign Journal — Obsidian Glass"
```

---

## Task 8: Chat

**Files:**
- Modify: `ui/src/components/Chat.tsx`

- [ ] **Step 1: Rewrite Chat.tsx**

```tsx
// ui/src/components/Chat.tsx
import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api/client'
import MarkdownRenderer from './shared/MarkdownRenderer'

interface Message { role: 'user' | 'assistant'; content: string; streaming?: boolean }

const CATEGORIES = ['work','research','play','learning','communication','creative','admin','other']

export default function Chat() {
  const location = useLocation()
  const initialQuestion = (location.state as { initialQuestion?: string } | null)?.initialQuestion ?? ''
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState(initialQuestion)
  const [loading, setLoading] = useState(false)
  const [dateFilter, setDateFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const hasAutoSent = useRef(false)

  useEffect(() => {
    if (initialQuestion && !hasAutoSent.current) {
      hasAutoSent.current = true
      handleSend(initialQuestion)
    }
  }, []) // eslint-disable-line

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (question: string = input) => {
    if (!question.trim() || loading) return
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: '', streaming: true },
    ])
    try {
      let acc = ''
      for await (const chunk of api.chatStream(question, dateFilter || undefined, categoryFilter || undefined)) {
        acc += chunk
        setMessages(prev => {
          const u = [...prev]
          u[u.length - 1] = { role: 'assistant', content: acc, streaming: true }
          return u
        })
      }
      setMessages(prev => {
        const u = [...prev]
        u[u.length - 1] = { role: 'assistant', content: acc, streaming: false }
        return u
      })
    } catch {
      setMessages(prev => {
        const u = [...prev]
        u[u.length - 1] = { role: 'assistant', content: 'Something went wrong. Please try again.', streaming: false }
        return u
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">

      {/* Filter bar */}
      <div
        className="flex items-center gap-2 px-5 py-2.5 border-b shrink-0 flex-wrap"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
      >
        <input
          type="date"
          value={dateFilter}
          onChange={e => setDateFilter(e.target.value)}
          className="rounded-[7px] px-2.5 py-1.5 text-[11px] border outline-none font-mono"
          style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)', color: 'var(--text)' }}
        />
        <select
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
          className="rounded-[7px] px-2.5 py-1.5 text-[11px] border outline-none"
          style={{ background: 'var(--bg-input)', borderColor: 'var(--border-2)', color: 'var(--text)' }}
        >
          <option value="">All categories</option>
          {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {(dateFilter || categoryFilter) && (
          <button
            onClick={() => { setDateFilter(''); setCategoryFilter('') }}
            className="text-[11px] px-2.5 py-1 rounded-[7px] transition-colors"
            style={{ color: 'var(--text-dim)' }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
        {messages.length === 0 && (
          <div
            className="flex flex-col items-center justify-center h-full text-center"
            style={{ color: 'var(--text-dim)' }}
          >
            <div className="text-4xl mb-3 opacity-20">💬</div>
            <div className="text-[13px]">Ask anything about your past activity</div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[78%] rounded-[12px] px-4 py-3 text-[13px] leading-relaxed"
              style={
                msg.role === 'user'
                  ? { background: 'var(--accent-glow-2)', border: '1px solid var(--accent-glow)', color: 'var(--text)' }
                  : { background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text)' }
              }
            >
              {msg.role === 'assistant'
                ? <MarkdownRenderer content={msg.content} />
                : msg.content}
              {msg.streaming && (
                <span
                  className="inline-block w-1.5 h-3.5 ml-1 rounded-sm align-middle pulse"
                  style={{ background: 'var(--accent)' }}
                />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); handleSend() }}
        className="flex gap-3 px-5 py-4 border-t shrink-0"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-surface)' }}
      >
        <input
          className="flex-1 rounded-[10px] border px-4 py-2.5 text-[13px] outline-none transition-all"
          style={{
            background: 'var(--bg-input)',
            borderColor: 'var(--border-2)',
            color: 'var(--text)',
          }}
          placeholder="Ask your second brain…"
          value={input}
          onChange={e => setInput(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-5 py-2.5 rounded-[10px] text-[13px] font-medium transition-all disabled:opacity-30"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          {loading ? '…' : '↵'}
        </button>
      </form>

    </div>
  )
}
```

- [ ] **Step 2: TypeScript check + commit**

```bash
pnpm exec tsc --noEmit
git add ui/src/components/Chat.tsx
git commit -m "feat(design): redesign Chat — Obsidian Glass"
```

---

## Task 9: Settings

**Files:**
- Modify: `ui/src/components/Settings.tsx`

- [ ] **Step 1: Rewrite Settings.tsx**

```tsx
// ui/src/components/Settings.tsx
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'

const Field = ({ label, sublabel, children }: { label: string; sublabel?: string; children: React.ReactNode }) => (
  <div>
    <label className="text-[12px] font-medium block mb-1" style={{ color: 'var(--text-muted)' }}>
      {label}
      {sublabel && <span className="ml-2 font-normal opacity-60">{sublabel}</span>}
    </label>
    {children}
  </div>
)

const Input = (props: React.InputHTMLAttributes<HTMLInputElement>) => (
  <input
    {...props}
    className="w-full rounded-[9px] border px-3 py-2 text-[13px] outline-none transition-colors"
    style={{
      background: 'var(--bg-input)',
      borderColor: 'var(--border-2)',
      color: 'var(--text)',
      ...props.style,
    }}
  />
)

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section
    className="rounded-[12px] border p-5 space-y-4"
    style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}
  >
    <h2 className="text-[12px] font-semibold tracking-wide uppercase" style={{ color: 'var(--text-muted)' }}>
      {title}
    </h2>
    {children}
  </section>
)

export default function Settings() {
  const qc = useQueryClient()
  const [gatewayUrl, setGatewayUrl]   = useState('')
  const [gatewayToken, setGatewayToken] = useState('')
  const [llmModel, setLlmModel]       = useState('')
  const [embedModel, setEmbedModel]   = useState('')
  const [newApp, setNewApp]           = useState('')
  const [saveMessage, setSaveMessage] = useState('')

  const { data: settings } = useQuery({ queryKey: queryKeys.settings(), queryFn: api.getSettings })
  const { data: exclusions = [] } = useQuery({ queryKey: queryKeys.exclusions(), queryFn: api.getExclusions })

  useEffect(() => {
    if (settings && !gatewayUrl) {
      setGatewayUrl(settings.gateway_url)
      setLlmModel(settings.llm_model)
      setEmbedModel(settings.embed_model)
    }
  }, [settings?.gateway_url]) // eslint-disable-line

  const saveGateway = useMutation({
    mutationFn: () => api.updateSettings({
      gateway_url: gatewayUrl, llm_model: llmModel, embed_model: embedModel,
      ...(gatewayToken ? { gateway_token: gatewayToken } : {}),
    }),
    onSuccess: () => {
      setGatewayToken('')
      setSaveMessage('Settings saved')
      qc.invalidateQueries({ queryKey: queryKeys.settings() })
      setTimeout(() => setSaveMessage(''), 3000)
    },
    onError: () => { setSaveMessage('Failed to save'); setTimeout(() => setSaveMessage(''), 3000) },
  })

  const togglePause = useMutation({
    mutationFn: () => api.setPaused(!settings?.paused),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.settings() }),
  })

  const addExclusion = useMutation({
    mutationFn: () => api.addExclusion(newApp.trim()),
    onSuccess: () => { setNewApp(''); qc.invalidateQueries({ queryKey: queryKeys.exclusions() }) },
    onError: () => { setSaveMessage('Already excluded'); setTimeout(() => setSaveMessage(''), 3000) },
  })

  const removeExclusion = useMutation({
    mutationFn: (name: string) => api.removeExclusion(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.exclusions() }),
  })

  if (!settings) {
    return (
      <div className="p-8 space-y-4">
        {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-36 rounded-[12px]" />)}
      </div>
    )
  }

  return (
    <div className="page-enter p-7 max-w-[640px] mx-auto space-y-4">
      <h1 className="text-[18px] font-semibold tracking-tight mb-2" style={{ color: 'var(--text)' }}>
        Settings
      </h1>

      {saveMessage && (
        <div
          className="px-4 py-3 rounded-[9px] text-[12px] border"
          style={{ background: 'var(--green-bg)', color: 'var(--green)', borderColor: 'rgba(52,211,153,0.2)' }}
        >
          {saveMessage}
        </div>
      )}

      {/* Capture */}
      <Section title="Capture">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[13px]" style={{ color: 'var(--text)' }}>
              {settings.paused ? 'Capture paused' : 'Capture active'}
            </div>
            <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Toggle background screen capture
            </div>
          </div>
          <button
            onClick={() => togglePause.mutate()}
            disabled={togglePause.isPending}
            className="px-4 py-2 rounded-[9px] text-[12px] font-medium transition-all disabled:opacity-50"
            style={
              settings.paused
                ? { background: 'var(--green-bg)', color: 'var(--green)', border: '1px solid rgba(52,211,153,0.2)' }
                : { background: 'var(--red-bg)',   color: 'var(--red)',   border: '1px solid rgba(248,113,113,0.2)' }
            }
          >
            {settings.paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </Section>

      {/* Gateway */}
      <Section title="JLL GPT Gateway">
        <Field label="Gateway URL">
          <Input value={gatewayUrl} onChange={e => setGatewayUrl(e.target.value)} />
        </Field>
        <Field
          label="Bearer Token"
          sublabel={settings.has_token ? '(stored in keychain ✓)' : '(not set)'}
        >
          <Input
            type="password"
            value={gatewayToken}
            onChange={e => setGatewayToken(e.target.value)}
            placeholder="Enter new token to update…"
          />
        </Field>
        <Field label="LLM Model">
          <Input value={llmModel} onChange={e => setLlmModel(e.target.value)} placeholder="e.g. GPT_4_1" />
        </Field>
        <Field label="Embedding Model">
          <Input value={embedModel} onChange={e => setEmbedModel(e.target.value)} placeholder="e.g. text-embedding-ada-002" />
        </Field>
        <button
          onClick={() => saveGateway.mutate()}
          disabled={saveGateway.isPending}
          className="px-5 py-2 rounded-[9px] text-[12px] font-semibold transition-all disabled:opacity-40"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          {saveGateway.isPending ? 'Saving…' : 'Save Gateway Settings'}
        </button>
      </Section>

      {/* Exclusions */}
      <Section title="Excluded Apps">
        <p className="text-[11px]" style={{ color: 'var(--text-dim)' }}>
          Apps listed here will never be captured — add password managers, banking apps, etc.
        </p>
        <div className="flex gap-2">
          <Input
            value={newApp}
            onChange={e => setNewApp(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && newApp.trim() && addExclusion.mutate()}
            placeholder="App name (e.g. 1Password)"
          />
          <button
            onClick={() => newApp.trim() && addExclusion.mutate()}
            disabled={addExclusion.isPending || !newApp.trim()}
            className="px-4 py-2 rounded-[9px] text-[12px] font-medium shrink-0 transition-all disabled:opacity-40"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Add
          </button>
        </div>
        {exclusions.length === 0 ? (
          <p className="text-[11px]" style={{ color: 'var(--text-dim)' }}>No excluded apps.</p>
        ) : (
          <ul className="space-y-1.5">
            {exclusions.map(ex => (
              <li
                key={ex.app_name}
                className="flex items-center justify-between rounded-[9px] px-3 py-2 border"
                style={{ background: 'var(--bg-surface-2)', borderColor: 'var(--border)' }}
              >
                <span className="text-[13px]" style={{ color: 'var(--text)' }}>{ex.app_name}</span>
                <button
                  onClick={() => removeExclusion.mutate(ex.app_name)}
                  className="text-[11px] transition-colors"
                  style={{ color: 'var(--red)' }}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Storage */}
      <Section title="Storage">
        <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
          Auto-purge: screenshots older than{' '}
          <span className="font-medium" style={{ color: 'var(--text)' }}>{settings.purge_months} months</span>
          {' '}are automatically deleted.
        </p>
        <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
          Data stored at{' '}
          <code
            className="px-1.5 py-0.5 rounded-[5px] font-mono text-[11px]"
            style={{ background: 'var(--bg-surface-2)', color: 'var(--accent)' }}
          >
            ~/.2brn/
          </code>
        </p>
      </Section>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check + commit**

```bash
pnpm exec tsc --noEmit
git add ui/src/components/Settings.tsx
git commit -m "feat(design): redesign Settings — Obsidian Glass"
```

---

## Task 10: Playwright verification

- [ ] **Step 1: Start the app**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run python -m brn_daemon.main &
sleep 3

cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
pnpm dev &
sleep 5
```

- [ ] **Step 2: Use Playwright MCP to navigate every route and screenshot each one**

Visit each route in order: `/`, `/chat`, `/journal`, `/timeline`, `/insights`, `/settings`

For each:
- Navigate to the route
- Wait 800ms for content
- Take a screenshot
- Confirm: correct font (Geist), glass surfaces visible, no broken layout

- [ ] **Step 3: Final commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add -A
git commit -m "feat(design): complete Obsidian Glass redesign — all routes verified"
```

---

## Self-Review

**Spec coverage:**
- ✅ Geist font — Task 1
- ✅ CSS variables design system — Task 1
- ✅ Tailwind tokens — Task 1
- ✅ Shared colour helpers — Task 2
- ✅ DaemonStatus redesign — Task 3
- ✅ StatsBar redesign — Task 3
- ✅ App layout / sidebar — Task 4
- ✅ Dashboard — Task 4
- ✅ Timeline with skeleton loading — Task 5
- ✅ Insights with recharts — Task 6
- ✅ Journal with useMutation — Task 7
- ✅ Chat with streaming — Task 8
- ✅ Settings with all mutations — Task 9
- ✅ Playwright verification — Task 10

**Placeholder scan:** None found. Every task has complete code.

**Type consistency:**
- `categoryChip(cat)` returns `{ bg, text, dot }` — used consistently in Timeline (Task 5) and StatsBar (Task 3) ✅
- `stateChip(state)` returns `{ bg, text }` — used in Timeline and StatsBar ✅
- `CATEGORY_CHIP` imported directly in Insights (Task 6) for recharts Cell fill ✅
- `queryKeys.*` keys match across all components ✅
- All `useMutation` / `useQuery` patterns match existing `api.*` signatures ✅

**One note for Insights.tsx:** It imports `STATE_COLORS` from `utils/colors`. That file exports `STATE_COLORS` as a `Record<string, string>` mapping state → hex. This is correct and compatible with recharts `Cell fill`.
