import type { ComponentType, ReactNode } from 'react'
import type { Skin } from './ThemeContext'
import type { ScreenName } from './routes'
import ModernShell from '../screens/modern/Shell'
import MinimalShell from '../screens/minimal/Shell'
import MinimalHome from '../screens/minimal/Home'
import MinimalChat from '../screens/minimal/Chat'
import MinimalJournal from '../screens/minimal/Journal'
import MinimalBlog from '../screens/minimal/Blog'
import MinimalTimeline from '../screens/minimal/Timeline'
import MinimalInsights from '../screens/minimal/Insights'
import Home from '../screens/modern/Home'
import Chat from '../screens/modern/Chat'
import Journal from '../screens/modern/Journal'
import Blog from '../screens/modern/Blog'
import Timeline from '../screens/modern/Timeline'
import Insights from '../screens/modern/Insights'
import Instructions from '../screens/modern/Instructions'
import Plugins from '../screens/modern/Plugins'
import Settings from '../screens/modern/Settings'

export type { ScreenName }

// ── Screen registry ───────────────────────────────────────────────────────────
// Each skin provides its own presentation components; data/logic is shared.
// A screen missing from a skin falls back to the modern implementation, so
// the minimal skin can be built (and shipped) screen-by-screen.

const modern: Record<ScreenName, ComponentType> = {
  home: Home,
  chat: Chat,
  journal: Journal,
  blog: Blog,
  timeline: Timeline,
  insights: Insights,
  instructions: Instructions,
  plugins: Plugins,
  settings: Settings,
}

// Populated screen-by-screen as the minimal skin lands (#61–#63).
const minimal: Partial<Record<ScreenName, ComponentType>> = {
  home: MinimalHome,
  chat: MinimalChat,
  journal: MinimalJournal,
  blog: MinimalBlog,
  timeline: MinimalTimeline,
  insights: MinimalInsights,
}

export function getScreen(skin: Skin, name: ScreenName): ComponentType {
  return (skin === 'minimal' ? minimal[name] : undefined) ?? modern[name]
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
