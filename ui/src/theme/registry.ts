import type { ComponentType, ReactNode } from 'react'
import type { Skin } from './ThemeContext'
import type { ScreenName } from './routes'
import ModernShell from '../screens/modern/Shell'
import MinimalShell from '../screens/minimal/Shell'
import Home from '../screens/Home'
import Journal from '../screens/Journal'
import Blog from '../screens/Blog'
import Instructions from '../screens/Instructions'
import Chat from '../screens/Chat'
import Devices from '../screens/Devices'
import Timeline from '../screens/Timeline'
import Insights from '../screens/Insights'
import Settings from '../screens/Settings'
import Plugins from '../screens/Plugins'

export type { ScreenName }

// ── Screen registry ───────────────────────────────────────────────────────────
// Epic #93 complete: every screen is ONE component that renders in both skins
// via the ui-kit token contract (theme/tokens.css). No more per-skin screen
// forks; only the app chrome (Shell) still differs per skin below.

const screens: Record<ScreenName, ComponentType> = {
  home: Home,
  chat: Chat,
  journal: Journal,
  blog: Blog,
  timeline: Timeline,
  insights: Insights,
  instructions: Instructions,
  plugins: Plugins,
  devices: Devices,
  settings: Settings,
}

export function getScreen(name: ScreenName): ComponentType {
  return screens[name]
}

// ── Shell registry ────────────────────────────────────────────────────────────
// The app chrome (sidebar, top bar, panels) differs structurally per skin,
// so each skin owns a complete shell around the routed content.

export interface ShellProps {
  calendarApplies: boolean
  children: ReactNode
}

const shells: Record<Skin, ComponentType<ShellProps>> = {
  modern: ModernShell,
  minimal: MinimalShell,
}

export function getShell(skin: Skin): ComponentType<ShellProps> {
  return shells[skin]
}
