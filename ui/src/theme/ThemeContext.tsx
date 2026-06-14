import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

// ── Theme model ───────────────────────────────────────────────────────────────
// Two independent axes, both applied as attributes on <html>:
//   skin — which design language renders ("modern" = the original look,
//          "minimal" = the monochrome text-first skin). → data-skin
//   mode — light / dark / system; resolved against the OS theme from the
//          Electron bridge. → data-theme="light" | "dark"

export type Skin = 'modern' | 'minimal'
export type ThemeMode = 'light' | 'system' | 'dark'

export const SKINS: readonly Skin[] = ['modern', 'minimal'] as const
const MODES: readonly ThemeMode[] = ['light', 'system', 'dark'] as const

const SKIN_KEY = '2brn-skin'
const MODE_KEY = '2brn-theme-mode'

function readPersisted<T extends string>(key: string, valid: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    if (v !== null && (valid as readonly string[]).includes(v)) return v as T
  } catch {}
  return fallback
}

interface ThemeContextValue {
  skin: Skin
  setSkin: (skin: Skin) => void
  mode: ThemeMode
  setMode: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [skin, setSkinState] = useState<Skin>(() => readPersisted(SKIN_KEY, SKINS, 'modern'))
  const [mode, setModeState] = useState<ThemeMode>(() => readPersisted(MODE_KEY, MODES, 'system'))
  // Assume dark until the OS theme arrives — the CSS default palette is dark,
  // so this avoids a light flash on dark systems during startup.
  const [osIsDark, setOsIsDark] = useState(true)

  useEffect(() => {
    window.electronAPI.getTheme().then(t => setOsIsDark(t === 'dark'))
    return window.electronAPI.onThemeChanged(t => setOsIsDark(t === 'dark'))
  }, [])

  useEffect(() => {
    const isDark = mode === 'dark' || (mode === 'system' && osIsDark)
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
    document.documentElement.setAttribute('data-skin', skin)
  }, [skin, mode, osIsDark])

  const setSkin = useCallback((s: Skin) => {
    try { localStorage.setItem(SKIN_KEY, s) } catch {}
    setSkinState(s)
  }, [])

  const setMode = useCallback((m: ThemeMode) => {
    try { localStorage.setItem(MODE_KEY, m) } catch {}
    setModeState(m)
  }, [])

  const value = useMemo(() => ({ skin, setSkin, mode, setMode }), [skin, setSkin, mode, setMode])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}

/** Non-throwing skin reader — returns 'modern' outside a provider (used by the
 *  ui-kit's KitProvider so primitives stay renderable in isolation/tests). */
export function useThemeSkin(): Skin {
  return useContext(ThemeContext)?.skin ?? 'modern'
}
