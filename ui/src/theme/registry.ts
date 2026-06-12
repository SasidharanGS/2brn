import type { ComponentType } from 'react'
import type { Skin } from './ThemeContext'
import Home from '../screens/modern/Home'
import Chat from '../screens/modern/Chat'
import Journal from '../screens/modern/Journal'
import Blog from '../screens/modern/Blog'
import Timeline from '../screens/modern/Timeline'
import Insights from '../screens/modern/Insights'
import Instructions from '../screens/modern/Instructions'
import Plugins from '../screens/modern/Plugins'
import Settings from '../screens/modern/Settings'

// ── Screen registry ───────────────────────────────────────────────────────────
// Each skin provides its own presentation components; data/logic is shared.
// A screen missing from a skin falls back to the modern implementation, so
// the minimal skin can be built (and shipped) screen-by-screen.

export type ScreenName =
  | 'home' | 'chat' | 'journal' | 'blog' | 'timeline'
  | 'insights' | 'instructions' | 'plugins' | 'settings'

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

// Populated screen-by-screen as the minimal skin lands (#60–#63).
const minimal: Partial<Record<ScreenName, ComponentType>> = {}

export function getScreen(skin: Skin, name: ScreenName): ComponentType {
  return (skin === 'minimal' ? minimal[name] : undefined) ?? modern[name]
}
