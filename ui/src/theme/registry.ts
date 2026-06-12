import type { ComponentType } from 'react'
import type { Skin } from './ThemeContext'
import Dashboard from '../components/Dashboard'
import Chat from '../components/Chat'
import Journal from '../components/Journal'
import Blog from '../components/Blog'
import Timeline from '../components/Timeline'
import Insights from '../components/Insights'
import Instructions from '../components/Instructions'
import Plugins from '../components/Plugins'
import Settings from '../components/Settings'

// ── Screen registry ───────────────────────────────────────────────────────────
// Each skin provides its own presentation components; data/logic is shared.
// A screen missing from a skin falls back to the modern implementation, so
// the minimal skin can be built (and shipped) screen-by-screen.

export type ScreenName =
  | 'home' | 'chat' | 'journal' | 'blog' | 'timeline'
  | 'insights' | 'instructions' | 'plugins' | 'settings'

const modern: Record<ScreenName, ComponentType> = {
  home: Dashboard,
  chat: Chat,
  journal: Journal,
  blog: Blog,
  timeline: Timeline,
  insights: Insights,
  instructions: Instructions,
  plugins: Plugins,
  settings: Settings,
}

// Populated screen-by-screen as the minimal skin lands (#60–#63).
const minimal: Partial<Record<ScreenName, ComponentType>> = {}

export function getScreen(skin: Skin, name: ScreenName): ComponentType {
  return (skin === 'minimal' ? minimal[name] : undefined) ?? modern[name]
}
