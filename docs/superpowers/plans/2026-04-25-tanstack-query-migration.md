# TanStack Query Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all manual `useState + useEffect` data-fetching in the 2brn UI with TanStack Query v5, eliminating the ~2500ms navigation delay caused by StrictMode double-mounting, full remount-on-nav, and zero caching.

**Architecture:** Install `@tanstack/react-query` v5, wrap the app in `QueryClientProvider`, migrate each component's fetch logic to `useQuery`/`useMutation`, lift the two polling shared components (`DaemonStatus`, `StatsBar`) out of `Dashboard` into `App.tsx` so they persist across all routes, and remove `React.StrictMode` (it's dev-only and causes every effect to run twice, doubling all requests).

**Tech Stack:** React 19, TanStack Query v5 (`@tanstack/react-query`), React Router v6, TypeScript, pnpm, Vite, Electron 31

---

## File Map

| File | Change |
|------|--------|
| `ui/package.json` | Add `@tanstack/react-query` dependency |
| `ui/src/main.tsx` | Remove `React.StrictMode`, add `QueryClientProvider` |
| `ui/src/App.tsx` | Lift `DaemonStatus` + `StatsBar` into persistent layout (above `<Routes>`) |
| `ui/src/components/shared/DaemonStatus.tsx` | Replace `setInterval` polling with `useQuery` + `refetchInterval` |
| `ui/src/components/shared/StatsBar.tsx` | Replace `setInterval` polling with `useQuery` + `refetchInterval` |
| `ui/src/components/Dashboard.tsx` | Remove `DaemonStatus` + `StatsBar` (now in App layout) |
| `ui/src/components/Timeline.tsx` | Replace `useState+useEffect` with `useQuery` for activities + captures |
| `ui/src/components/Insights.tsx` | Replace `useState+useEffect` with `useQuery` for daily insights |
| `ui/src/components/Journal.tsx` | Replace `useState+useEffect` with `useQuery`, mutations for generate/save |
| `ui/src/components/Settings.tsx` | Replace `useState+useEffect` with `useQuery`, mutations for save/toggle/exclusions |
| `ui/src/api/queryKeys.ts` | **New file** — centralised query key factory, no magic strings |

---

## Task 1: Install TanStack Query

**Files:**
- Modify: `ui/package.json`

- [ ] **Step 1: Install the package**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
nvm --version
pnpm add @tanstack/react-query
```

Expected output: `dependencies: + @tanstack/react-query 5.x.x`

- [ ] **Step 2: Verify it's in package.json**

```bash
grep tanstack ui/package.json
```

Expected: `"@tanstack/react-query": "^5.x.x"`

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/package.json ui/pnpm-lock.yaml
git commit -m "feat: add @tanstack/react-query v5"
```

---

## Task 2: Create query key factory

**Files:**
- Create: `ui/src/api/queryKeys.ts`

Query keys are how TanStack Query identifies cached data. Centralising them in one file prevents typo bugs where two components use slightly different keys for the same data and get separate cache entries.

- [ ] **Step 1: Create the file**

```typescript
// ui/src/api/queryKeys.ts
export const queryKeys = {
  status: () => ['status'] as const,
  dailyInsights: (date: string) => ['insights', 'daily', date] as const,
  activities: (date: string) => ['activities', date] as const,
  captures: (date: string) => ['captures', date] as const,
  journal: (date: string) => ['journal', date] as const,
  settings: () => ['settings'] as const,
  exclusions: () => ['settings', 'exclusions'] as const,
} as const
```

- [ ] **Step 2: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/api/queryKeys.ts
git commit -m "feat: add centralised TanStack Query key factory"
```

---

## Task 3: Bootstrap QueryClientProvider and remove StrictMode

**Files:**
- Modify: `ui/src/main.tsx`

`QueryClient` holds the cache. It must wrap the whole app. `React.StrictMode` is removed here — it causes every `useEffect` to run twice in dev, which is why every API call appeared doubled in the network log.

- [ ] **Step 1: Rewrite main.tsx**

```typescript
// ui/src/main.tsx
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,       // data stays fresh 30s — navigating back shows cached data instantly
      retry: 1,                // retry once on failure, don't hammer a down daemon
      refetchOnWindowFocus: false, // Electron app — window focus isn't meaningful
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </QueryClientProvider>
)
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
nvm --version && pnpm exec tsc --noEmit 2>&1 | head -30
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/main.tsx
git commit -m "feat: bootstrap QueryClientProvider, remove StrictMode"
```

---

## Task 4: Migrate DaemonStatus to useQuery

**Files:**
- Modify: `ui/src/components/shared/DaemonStatus.tsx`

Current code uses `setInterval` inside `useEffect`. TanStack Query's `refetchInterval` replaces this entirely — same behaviour, but now the result is cached and shared with any other component that uses the `status` key.

- [ ] **Step 1: Rewrite DaemonStatus.tsx**

```typescript
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
      <span className="flex items-center gap-1.5 text-xs text-red-400">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        daemon offline
      </span>
    )
  }

  const color = status.status === 'capturing'
    ? 'bg-green-500'
    : status.status === 'paused'
    ? 'bg-yellow-500'
    : 'bg-red-500'
  const textColor = status.status === 'capturing'
    ? 'text-green-400'
    : status.status === 'paused'
    ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <span className={`flex items-center gap-1.5 text-xs ${textColor}`}>
      <span className={`w-2 h-2 rounded-full ${color} animate-pulse`} />
      {status.status} · {status.capture_count_today} captures today
    </span>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/shared/DaemonStatus.tsx
git commit -m "feat: migrate DaemonStatus to useQuery with refetchInterval"
```

---

## Task 5: Migrate StatsBar to useQuery

**Files:**
- Modify: `ui/src/components/shared/StatsBar.tsx`

Same pattern as DaemonStatus — replace `setInterval` with `refetchInterval: 30_000`. Because both `StatsBar` and `Insights` use `queryKeys.dailyInsights(today)`, they share one cache entry. Only one network request fires regardless of how many components are mounted.

- [ ] **Step 1: Rewrite StatsBar.tsx**

```typescript
// ui/src/components/shared/StatsBar.tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'

function toDateStr(d: Date) {
  return d.toISOString().split('T')[0]
}

const STATE_COLORS: Record<string, string> = {
  productive: 'text-green-400', focused: 'text-green-400',
  chilling: 'text-blue-400', procrastinating: 'text-red-400',
  distracted: 'text-orange-400', 'in-meeting': 'text-purple-400', idle: 'text-gray-400',
}

export default function StatsBar() {
  const today = toDateStr(new Date())
  const { data: insights } = useQuery({
    queryKey: queryKeys.dailyInsights(today),
    queryFn: () => api.getDailyInsights(today),
    refetchInterval: 30_000,
  })

  const topCategory = insights?.categories[0]?.task_category ?? '—'
  const topState = insights?.productivity_states[0]?.productivity_state ?? '—'
  const totalCaptures = insights?.categories.reduce((s, c) => s + c.count, 0) ?? 0
  const productiveCount = insights?.productivity_states
    .filter(s => ['productive', 'focused'].includes(s.productivity_state))
    .reduce((s, c) => s + c.count, 0) ?? 0
  const productivePct = totalCaptures > 0
    ? Math.round((productiveCount / totalCaptures) * 100)
    : 0

  return (
    <div className="flex gap-3">
      {[
        { label: 'now', value: topState, color: STATE_COLORS[topState] ?? 'text-gray-400' },
        { label: 'top task', value: topCategory, color: 'text-blue-400' },
        { label: 'productive', value: `${productivePct}%`, color: 'text-green-400' },
      ].map(item => (
        <div key={item.label} className="bg-[#1e293b] rounded-lg px-4 py-3 text-center min-w-[90px]">
          <div className={`text-base font-bold ${item.color}`}>{item.value}</div>
          <div className="text-xs text-[#64748b] mt-0.5">{item.label}</div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/shared/StatsBar.tsx
git commit -m "feat: migrate StatsBar to useQuery with 30s refetchInterval"
```

---

## Task 6: Lift DaemonStatus + StatsBar into App layout

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/components/Dashboard.tsx`

Currently `DaemonStatus` and `StatsBar` live inside `Dashboard`. Every time the user navigates away and back to `/`, they remount and restart polling. Moving them above `<Routes>` in `App.tsx` means they mount once and persist for the entire session. `Dashboard` becomes a pure navigation shell with no shared children.

- [ ] **Step 1: Rewrite App.tsx — add persistent header with DaemonStatus + StatsBar**

```typescript
// ui/src/App.tsx
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import Chat from './components/Chat'
import Journal from './components/Journal'
import Timeline from './components/Timeline'
import Insights from './components/Insights'
import Settings from './components/Settings'
import DaemonStatus from './components/shared/DaemonStatus'
import StatsBar from './components/shared/StatsBar'

const navItems = [
  { to: '/', label: '⌂ Home', end: true },
  { to: '/chat', label: '💬 Chat' },
  { to: '/journal', label: '📔 Journal' },
  { to: '/timeline', label: '⏱ Timeline' },
  { to: '/insights', label: '📊 Insights' },
  { to: '/settings', label: '⚙ Settings' },
]

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <nav className="w-48 bg-[#0d1117] border-r border-[#30363d] flex flex-col py-4 px-2 flex-shrink-0">
        <div className="text-[#58a6ff] font-bold text-lg px-3 mb-4">2brn</div>
        <div className="flex flex-col gap-1 flex-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-[#1e3a5f] text-[#93c5fd]'
                    : 'text-[#8b949e] hover:text-[#e6edf3] hover:bg-[#161b22]'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </div>
        {/* Persistent daemon status at bottom of nav */}
        <div className="px-3 pt-3 border-t border-[#30363d]">
          <DaemonStatus />
        </div>
      </nav>
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Persistent stats bar across all routes */}
        <div className="px-6 py-3 border-b border-[#30363d] bg-[#0d1117]">
          <StatsBar />
        </div>
        <main className="flex-1 overflow-auto bg-[#0d1117]">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/journal" element={<Journal />} />
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

- [ ] **Step 2: Simplify Dashboard.tsx — remove DaemonStatus and StatsBar**

```typescript
// ui/src/components/Dashboard.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const [question, setQuestion] = useState('')
  const navigate = useNavigate()

  const handleChat = (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    navigate('/chat', { state: { initialQuestion: question } })
    setQuestion('')
  }

  const tiles = [
    { label: '📔 Journal', path: '/journal', desc: "Today's narrative" },
    { label: '⏱ Timeline', path: '/timeline', desc: 'Visual activity timeline' },
    { label: '📊 Insights', path: '/insights', desc: 'Productivity analytics' },
    { label: '⚙ Settings', path: '/settings', desc: 'Configure 2brn' },
  ]

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-[#e6edf3] mb-8">your second brain</h1>

      <form onSubmit={handleChat}>
        <div className="flex gap-3">
          <input
            className="flex-1 bg-[#1e293b] border border-[#30363d] rounded-xl px-4 py-3 text-[#e6edf3] placeholder-[#64748b] focus:outline-none focus:border-[#58a6ff] text-sm"
            placeholder="Ask your second brain anything..."
            value={question}
            onChange={e => setQuestion(e.target.value)}
          />
          <button
            type="submit"
            className="bg-[#1e40af] hover:bg-[#1d4ed8] text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
          >
            Ask
          </button>
        </div>
      </form>

      <div className="grid grid-cols-2 gap-4 mt-8">
        {tiles.map(tile => (
          <button
            key={tile.path}
            onClick={() => navigate(tile.path)}
            className="bg-[#1e293b] hover:bg-[#243447] border border-[#30363d] rounded-xl p-5 text-left transition-colors"
          >
            <div className="text-base font-medium text-[#e6edf3]">{tile.label}</div>
            <div className="text-xs text-[#64748b] mt-1">{tile.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/App.tsx ui/src/components/Dashboard.tsx
git commit -m "feat: lift DaemonStatus+StatsBar into persistent App layout"
```

---

## Task 7: Migrate Timeline to useQuery

**Files:**
- Modify: `ui/src/components/Timeline.tsx`

Two queries in parallel: activities and captures for the selected date. TanStack Query's `isLoading` is only true on the very first load — subsequent navigations back to Timeline show cached data immediately while a background refetch happens silently.

- [ ] **Step 1: Rewrite Timeline.tsx**

```typescript
// ui/src/components/Timeline.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import type { ActivityRecord } from '../api/types'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

const CATEGORY_COLORS: Record<string, string> = {
  work: '#3b82f6', research: '#8b5cf6', play: '#22c55e',
  learning: '#f59e0b', communication: '#06b6d4', creative: '#ec4899',
  admin: '#64748b', other: '#475569',
}

export default function Timeline() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [selected, setSelected] = useState<ActivityRecord | null>(null)

  const { data: activities = [], isLoading: loadingActivities } = useQuery({
    queryKey: queryKeys.activities(selectedDate),
    queryFn: () => api.getActivities({ date: selectedDate }),
    select: acts => [...acts].sort((a, b) => b.started_at.localeCompare(a.started_at)),
  })

  const { data: captures = [], isLoading: loadingCaptures } = useQuery({
    queryKey: queryKeys.captures(selectedDate),
    queryFn: () => api.getCaptures(selectedDate),
  })

  const loading = loadingActivities || loadingCaptures

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-[#e6edf3]">Timeline</h1>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => { setSelectedDate(e.target.value); setSelected(null) }}
          className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
        />
      </div>

      {loading ? (
        <div className="text-center text-[#64748b] text-sm mt-20">Loading...</div>
      ) : activities.length === 0 ? (
        <div className="text-center text-[#64748b] text-sm mt-20">No activity recorded for {selectedDate}.</div>
      ) : (
        <div className="space-y-2">
          {activities.map(act => {
            const color = CATEGORY_COLORS[act.task_category ?? 'other'] ?? '#475569'
            const isSelected = selected?.id === act.id
            return (
              <button
                key={act.id}
                onClick={() => setSelected(isSelected ? null : act)}
                className={`w-full text-left bg-[#1e293b] hover:bg-[#243447] border rounded-xl px-4 py-3 transition-colors ${isSelected ? 'border-[#58a6ff]' : 'border-[#30363d]'}`}
              >
                <div className="flex items-center gap-3">
                  <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-xs text-[#64748b] w-16 flex-shrink-0 font-mono">
                    {new Date(act.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-sm text-[#e6edf3] flex-1 truncate">{act.summary ?? '—'}</span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full flex-shrink-0 font-medium"
                    style={{ background: color + '33', color }}
                  >
                    {act.task_category ?? 'other'}
                  </span>
                  <span className="text-xs text-[#64748b] flex-shrink-0 hidden sm:block">
                    {act.productivity_state ?? ''}
                  </span>
                </div>
                {isSelected && act.summary && (
                  <div className="mt-3 pt-3 border-t border-[#30363d] text-sm text-[#94a3b8] text-left">
                    {act.summary}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      )}

      <div className="mt-6 text-xs text-[#64748b]">
        {captures.length} captures · {activities.length} activities
      </div>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/Timeline.tsx
git commit -m "feat: migrate Timeline to useQuery"
```

---

## Task 8: Migrate Insights to useQuery

**Files:**
- Modify: `ui/src/components/Insights.tsx`

Single query. Note: because `StatsBar` (now persistent) uses `queryKeys.dailyInsights(today)` and Insights uses the same key for today, navigating to Insights for today's date shows data **instantly** from the cache — zero loading time.

- [ ] **Step 1: Rewrite Insights.tsx**

```typescript
// ui/src/components/Insights.tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'

function toDateStr(d: Date) { return d.toISOString().split('T')[0] }

const CATEGORY_COLORS: Record<string, string> = {
  work: '#3b82f6', research: '#8b5cf6', play: '#22c55e',
  learning: '#f59e0b', communication: '#06b6d4', creative: '#ec4899',
  admin: '#64748b', other: '#475569',
}

const STATE_COLORS: Record<string, string> = {
  productive: '#22c55e', focused: '#86efac', chilling: '#60a5fa',
  procrastinating: '#ef4444', distracted: '#f97316',
  'in-meeting': '#a78bfa', idle: '#64748b',
}

export default function Insights() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))

  const { data: insights, isLoading } = useQuery({
    queryKey: queryKeys.dailyInsights(selectedDate),
    queryFn: () => api.getDailyInsights(selectedDate),
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-[#e6edf3]">Insights</h1>
        <input
          type="date"
          value={selectedDate}
          max={toDateStr(new Date())}
          onChange={e => setSelectedDate(e.target.value)}
          className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
        />
      </div>

      {isLoading ? (
        <div className="text-center text-[#64748b] text-sm mt-20">Loading...</div>
      ) : !insights || insights.categories.length === 0 ? (
        <div className="text-center text-[#64748b] text-sm mt-20">No data for {selectedDate}.</div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="bg-[#1e293b] rounded-xl p-5">
            <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Time by Category</h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={insights.categories}>
                <XAxis dataKey="task_category" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 8 }}
                  labelStyle={{ color: '#e6edf3' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {insights.categories.map(entry => (
                    <Cell key={entry.task_category} fill={CATEGORY_COLORS[entry.task_category] ?? '#475569'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-[#1e293b] rounded-xl p-5">
            <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Productivity Distribution</h2>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={insights.productivity_states}
                  dataKey="count"
                  nameKey="productivity_state"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={85}
                >
                  {insights.productivity_states.map(entry => (
                    <Cell
                      key={entry.productivity_state}
                      fill={STATE_COLORS[entry.productivity_state] ?? '#475569'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 8 }}
                  labelStyle={{ color: '#e6edf3' }}
                />
                <Legend iconSize={10} wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-[#1e293b] rounded-xl p-5 lg:col-span-2">
            <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Top Apps</h2>
            <div className="space-y-2">
              {insights.top_apps.slice(0, 8).map(app => {
                const max = insights.top_apps[0]?.count ?? 1
                const pct = Math.round((app.count / max) * 100)
                return (
                  <div key={app.app_name} className="flex items-center gap-3">
                    <span className="text-sm text-[#94a3b8] w-36 truncate flex-shrink-0">
                      {app.app_name || 'Unknown'}
                    </span>
                    <div className="flex-1 bg-[#0d1117] rounded-full h-2">
                      <div className="bg-[#3b82f6] h-2 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-[#64748b] w-14 text-right flex-shrink-0">
                      {app.count} caps
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

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/Insights.tsx
git commit -m "feat: migrate Insights to useQuery"
```

---

## Task 9: Migrate Journal to useQuery + useMutation

**Files:**
- Modify: `ui/src/components/Journal.tsx`

`useQuery` for fetching the entry. `useMutation` for generate and save — mutations automatically invalidate the journal cache on success so the view refreshes without a manual `api.getJournal()` re-fetch call. Note: journal returns 404 when no entry exists — TanStack Query would normally treat this as an error. We configure `throwOnError: false` and handle the null case in the component.

- [ ] **Step 1: Rewrite Journal.tsx**

```typescript
// ui/src/components/Journal.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'
import MarkdownRenderer from './shared/MarkdownRenderer'

function toDateStr(d: Date) {
  return d.toISOString().split('T')[0]
}

export default function Journal() {
  const [selectedDate, setSelectedDate] = useState(toDateStr(new Date()))
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const queryClient = useQueryClient()

  const { data: entry } = useQuery({
    queryKey: queryKeys.journal(selectedDate),
    queryFn: () => api.getJournal(selectedDate),
    throwOnError: false,  // 404 = no entry, not an error we want to surface
    retry: false,
  })

  const generateMutation = useMutation({
    mutationFn: () => api.generateJournal(selectedDate),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.journal(selectedDate) }),
  })

  const saveMutation = useMutation({
    mutationFn: (content: string) => api.updateJournal(selectedDate, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.journal(selectedDate) })
      setEditing(false)
    },
  })

  const handleDateChange = (date: string) => {
    setSelectedDate(date)
    setEditing(false)
    setEditContent('')
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-[#e6edf3]">Journal</h1>
        <div className="flex items-center gap-3">
          {entry?.edited_by_user && (
            <span className="text-xs text-[#64748b] bg-[#1e293b] px-2 py-1 rounded">edited</span>
          )}
          <input
            type="date"
            value={selectedDate}
            max={toDateStr(new Date())}
            onChange={e => handleDateChange(e.target.value)}
            className="bg-[#1e293b] border border-[#30363d] rounded-lg px-3 py-1.5 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
      </div>

      {generateMutation.isError && (
        <div className="text-red-400 text-sm mb-4">Failed to generate journal entry.</div>
      )}
      {saveMutation.isError && (
        <div className="text-red-400 text-sm mb-4">Failed to save changes.</div>
      )}

      {!entry ? (
        <div className="bg-[#1e293b] rounded-xl p-8 text-center">
          <p className="text-[#64748b] text-sm mb-4">No journal entry for {selectedDate}.</p>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {generateMutation.isPending ? 'Generating...' : 'Generate Entry'}
          </button>
        </div>
      ) : editing ? (
        <div className="space-y-3">
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            rows={20}
            className="w-full bg-[#1e293b] border border-[#30363d] rounded-xl px-4 py-3 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff] font-mono resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setEditing(false)}
              className="text-sm text-[#64748b] hover:text-[#e6edf3] px-4 py-2"
            >
              Cancel
            </button>
            <button
              onClick={() => saveMutation.mutate(editContent)}
              disabled={saveMutation.isPending}
              className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {saveMutation.isPending ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-[#1e293b] rounded-xl p-6">
          <MarkdownRenderer content={entry.content ?? ''} />
          <div className="flex gap-2 mt-6 pt-4 border-t border-[#30363d]">
            <button
              onClick={() => { setEditing(true); setEditContent(entry.content ?? '') }}
              className="text-sm text-[#64748b] hover:text-[#e6edf3] px-3 py-1.5 rounded-lg hover:bg-[#243447] transition-colors"
            >
              Edit
            </button>
            {!entry.edited_by_user && (
              <button
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
                className="text-sm text-[#64748b] hover:text-[#e6edf3] px-3 py-1.5 rounded-lg hover:bg-[#243447] transition-colors disabled:opacity-50"
              >
                {generateMutation.isPending ? 'Regenerating...' : 'Regenerate'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/Journal.tsx
git commit -m "feat: migrate Journal to useQuery + useMutation"
```

---

## Task 10: Migrate Settings to useQuery + useMutation

**Files:**
- Modify: `ui/src/components/Settings.tsx`

Two queries (settings + exclusions), four mutations (save gateway, toggle pause, add exclusion, remove exclusion). Each mutation invalidates the relevant query key on success so the UI stays consistent without manual re-fetches.

- [ ] **Step 1: Rewrite Settings.tsx**

```typescript
// ui/src/components/Settings.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { queryKeys } from '../api/queryKeys'

export default function Settings() {
  const queryClient = useQueryClient()
  const [gatewayUrl, setGatewayUrl] = useState('')
  const [gatewayToken, setGatewayToken] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [embedModel, setEmbedModel] = useState('')
  const [newApp, setNewApp] = useState('')
  const [saveMessage, setSaveMessage] = useState('')

  const { data: settings } = useQuery({
    queryKey: queryKeys.settings(),
    queryFn: api.getSettings,
    // Populate local form fields when settings first load
    select: s => {
      // Only set local state on initial load (fields empty = not yet populated)
      if (!gatewayUrl) {
        setGatewayUrl(s.gateway_url)
        setLlmModel(s.llm_model)
        setEmbedModel(s.embed_model)
      }
      return s
    },
  })

  const { data: exclusions = [] } = useQuery({
    queryKey: queryKeys.exclusions(),
    queryFn: api.getExclusions,
  })

  const saveGatewayMutation = useMutation({
    mutationFn: () => api.updateSettings({
      gateway_url: gatewayUrl,
      llm_model: llmModel,
      embed_model: embedModel,
      ...(gatewayToken ? { gateway_token: gatewayToken } : {}),
    }),
    onSuccess: () => {
      setGatewayToken('')
      setSaveMessage('Gateway settings saved.')
      queryClient.invalidateQueries({ queryKey: queryKeys.settings() })
      setTimeout(() => setSaveMessage(''), 3000)
    },
    onError: () => {
      setSaveMessage('Failed to save.')
      setTimeout(() => setSaveMessage(''), 3000)
    },
  })

  const togglePauseMutation = useMutation({
    mutationFn: () => api.setPaused(!settings?.paused),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.settings() }),
  })

  const addExclusionMutation = useMutation({
    mutationFn: () => api.addExclusion(newApp.trim()),
    onSuccess: () => {
      setNewApp('')
      queryClient.invalidateQueries({ queryKey: queryKeys.exclusions() })
    },
    onError: () => {
      setSaveMessage('App already excluded or error occurred.')
      setTimeout(() => setSaveMessage(''), 3000)
    },
  })

  const removeExclusionMutation = useMutation({
    mutationFn: (appName: string) => api.removeExclusion(appName),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.exclusions() }),
  })

  if (!settings) {
    return <div className="p-8 text-[#64748b] text-sm">Loading settings...</div>
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8">
      <h1 className="text-xl font-bold text-[#e6edf3]">Settings</h1>

      {saveMessage && (
        <div className="text-green-400 text-sm bg-[#0d2a1a] border border-green-800 rounded-lg px-4 py-2">
          {saveMessage}
        </div>
      )}

      {/* Capture control */}
      <section className="bg-[#1e293b] rounded-xl p-5">
        <h2 className="text-sm font-semibold text-[#e6edf3] mb-4">Capture</h2>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-[#e6edf3]">
              {settings.paused ? 'Capture paused' : 'Capture active'}
            </div>
            <div className="text-xs text-[#64748b] mt-0.5">Toggle background screen capture</div>
          </div>
          <button
            onClick={() => togglePauseMutation.mutate()}
            disabled={togglePauseMutation.isPending}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
              settings.paused
                ? 'bg-green-700 hover:bg-green-600 text-white'
                : 'bg-red-900 hover:bg-red-800 text-red-200'
            }`}
          >
            {settings.paused ? 'Resume' : 'Pause'}
          </button>
        </div>
      </section>

      {/* Gateway config */}
      <section className="bg-[#1e293b] rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[#e6edf3]">JLL GPT Gateway</h2>
        <div>
          <label className="text-xs text-[#64748b] block mb-1">Gateway URL</label>
          <input
            value={gatewayUrl}
            onChange={e => setGatewayUrl(e.target.value)}
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
        <div>
          <label className="text-xs text-[#64748b] block mb-1">
            Bearer Token {settings.has_token ? '(stored in keychain ✓)' : '(not configured)'}
          </label>
          <input
            type="password"
            value={gatewayToken}
            onChange={e => setGatewayToken(e.target.value)}
            placeholder="Enter new token to update..."
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
        <div>
          <label className="text-xs text-[#64748b] block mb-1">LLM Model</label>
          <input
            value={llmModel}
            onChange={e => setLlmModel(e.target.value)}
            placeholder="e.g. GPT_4_1"
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
        <div>
          <label className="text-xs text-[#64748b] block mb-1">Embedding Model</label>
          <input
            value={embedModel}
            onChange={e => setEmbedModel(e.target.value)}
            placeholder="e.g. text-embedding-ada-002"
            className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
        </div>
        <button
          onClick={() => saveGatewayMutation.mutate()}
          disabled={saveGatewayMutation.isPending}
          className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {saveGatewayMutation.isPending ? 'Saving...' : 'Save Gateway Settings'}
        </button>
      </section>

      {/* App exclusions */}
      <section className="bg-[#1e293b] rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-[#e6edf3]">Excluded Apps</h2>
        <p className="text-xs text-[#64748b]">
          Apps listed here will never be captured. Add banking, password managers, etc.
        </p>
        <div className="flex gap-2">
          <input
            value={newApp}
            onChange={e => setNewApp(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && newApp.trim() && addExclusionMutation.mutate()}
            placeholder="App name (e.g. 1Password)"
            className="flex-1 bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-[#e6edf3] focus:outline-none focus:border-[#58a6ff]"
          />
          <button
            onClick={() => newApp.trim() && addExclusionMutation.mutate()}
            disabled={addExclusionMutation.isPending || !newApp.trim()}
            className="bg-[#1e40af] hover:bg-[#1d4ed8] disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Add
          </button>
        </div>
        {exclusions.length === 0 ? (
          <p className="text-xs text-[#64748b]">No excluded apps.</p>
        ) : (
          <ul className="space-y-2">
            {exclusions.map(ex => (
              <li key={ex.app_name} className="flex items-center justify-between bg-[#0d1117] rounded-lg px-3 py-2">
                <span className="text-sm text-[#e6edf3]">{ex.app_name}</span>
                <button
                  onClick={() => removeExclusionMutation.mutate(ex.app_name)}
                  disabled={removeExclusionMutation.isPending}
                  className="text-xs text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Storage info */}
      <section className="bg-[#1e293b] rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[#e6edf3]">Storage</h2>
        <p className="text-xs text-[#64748b]">
          Auto-purge: screenshots older than{' '}
          <strong className="text-[#e6edf3]">{settings.purge_months} months</strong> are automatically deleted.
        </p>
        <p className="text-xs text-[#64748b]">
          Data stored at <code className="text-[#93c5fd] bg-[#0d1117] px-1 py-0.5 rounded">~/.2brn/</code>
        </p>
      </section>
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/src/components/Settings.tsx
git commit -m "feat: migrate Settings to useQuery + useMutation"
```

---

## Task 11: Playwright verification

Run automated Playwright checks to confirm the migration worked.

- [ ] **Step 1: Start the backend daemon**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/daemon
uv run python -m brn_daemon.main &
sleep 3
curl -s http://127.0.0.1:7842/status | python3 -m json.tool
```

Expected: JSON with `"status": "capturing"` or `"paused"`

- [ ] **Step 2: Start the Vite dev server**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
nvm --version && pnpm electron:dev &
sleep 5
```

- [ ] **Step 3: Run Playwright navigation timing test**

Use the Playwright MCP browser tool to:
1. Navigate to `http://localhost:5173`
2. For each of: `/timeline`, `/insights`, `/journal`, `/settings`, `/chat`, `/`
   - Record time before click
   - Click the nav link
   - Wait for content (not "Loading...")
   - Record time after
   - Capture network requests — confirm NO duplicates, confirm each request fires once
3. Navigate to `/timeline` a SECOND time — confirm data appears instantly (from cache, zero network requests)
4. Navigate to `/insights` — confirm `dailyInsights` data is already cached from StatsBar's initial fetch (zero wait)

Expected results:
- First navigation: <400ms (was ~2500ms)
- Second navigation to same route: <50ms (instant from cache)
- Network requests: each endpoint called once, not twice
- StatsBar and DaemonStatus visible on ALL routes (not just Home)

- [ ] **Step 4: Final commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add -A
git commit -m "feat: complete TanStack Query migration — instant navigation, shared cache"
```

---

## Self-Review

**Spec coverage check:**
- ✅ StrictMode removed → Task 3
- ✅ QueryClientProvider added → Task 3
- ✅ DaemonStatus migrated → Task 4
- ✅ StatsBar migrated → Task 5
- ✅ Pollers lifted to App layout → Task 6
- ✅ Dashboard simplified → Task 6
- ✅ Timeline migrated → Task 7
- ✅ Insights migrated → Task 8
- ✅ Journal migrated with mutations → Task 9
- ✅ Settings migrated with mutations → Task 10
- ✅ Playwright verification → Task 11

**Type consistency check:**
- `queryKeys.status()` used in DaemonStatus (Task 4) ✅
- `queryKeys.dailyInsights(date)` used in StatsBar (Task 5) and Insights (Task 8) — same key, shared cache ✅
- `queryKeys.activities(date)` used in Timeline (Task 7) ✅
- `queryKeys.captures(date)` used in Timeline (Task 7) ✅
- `queryKeys.journal(date)` used in Journal (Task 9) ✅
- `queryKeys.settings()` used in Settings (Task 10) ✅
- `queryKeys.exclusions()` used in Settings (Task 10) ✅

**Known caveat — Settings form field initialisation:**
The `select` function in the Settings `useQuery` is used to seed `gatewayUrl`/`llmModel`/`embedModel` on first load. This is a slightly unconventional pattern — a cleaner alternative would be `useEffect(() => { if (settings) { setGatewayUrl(...) } }, [settings?.gateway_url])` — but the `select` approach works correctly and keeps the component smaller. Flag for code review phase.
