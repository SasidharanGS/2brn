import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useThemeSkin, type Skin } from '../theme/ThemeContext'

// The ui-kit's skin context. Primitives read `useKit().skin` to branch where the
// two designs differ structurally (e.g. emoji vs SVG icons); pure-style
// differences come from the `--k-*` token contract (theme/tokens.css), not here.

interface KitValue {
  skin: Skin
}

const KitContext = createContext<KitValue | null>(null)

/** Supplies the active skin to all kit primitives. Mounted once near the app
 *  root from the resolved theme skin; tests/previews can force a skin via the
 *  optional `skin` prop without a ThemeProvider. */
export function KitProvider({ skin, children }: { skin?: Skin; children: ReactNode }) {
  const active = useThemeSkin()
  const value = useMemo<KitValue>(() => ({ skin: skin ?? active }), [skin, active])
  return <KitContext.Provider value={value}>{children}</KitContext.Provider>
}

export function useKit(): KitValue {
  const ctx = useContext(KitContext)
  if (!ctx) throw new Error('useKit must be used inside <KitProvider>')
  return ctx
}
