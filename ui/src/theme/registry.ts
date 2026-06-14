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
import MinimalInsights from '../screens/minimal/Insights'
import MinimalPlugins from '../screens/minimal/Plugins'
import MinimalSettings from '../screens/minimal/Settings'
import Insights from '../screens/modern/Insights'
import Plugins from '../screens/modern/Plugins'
import Settings from '../screens/modern/Settings'

export type { ScreenName }

// ── Screen registry ───────────────────────────────────────────────────────────
// `shared` holds screens unified onto ONE component tree (epic #93) — these
// render in every skin via the ui-kit token contract. Screens not yet migrated
// still have a per-skin fork in `modern`/`minimal`; the minimal fork falls back
// to the modern one when absent, so the app stays shippable mid-migration.

const shared: Partial<Record<ScreenName, ComponentType>> = {
  home: Home,
  journal: Journal,
  blog: Blog,
  instructions: Instructions,
  chat: Chat,
  devices: Devices,
  timeline: Timeline,
}

const modern: Partial<Record<ScreenName, ComponentType>> = {
  insights: Insights,
  plugins: Plugins,
  settings: Settings,
}

const minimal: Partial<Record<ScreenName, ComponentType>> = {
  insights: MinimalInsights,
  plugins: MinimalPlugins,
  settings: MinimalSettings,
}

export function getScreen(skin: Skin, name: ScreenName): ComponentType {
  // Unified screens win; otherwise the per-skin fork (minimal → modern fallback).
  return shared[name] ?? (skin === 'minimal' ? minimal[name] : undefined) ?? modern[name]!
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
