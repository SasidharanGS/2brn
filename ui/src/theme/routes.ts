// Route table shared by every skin's shell and the router. Presentation
// (labels, icons, casing) is per-skin; the paths and calendar rules are not.

export type ScreenName =
  | 'home' | 'chat' | 'journal' | 'blog' | 'timeline'
  | 'insights' | 'instructions' | 'plugins' | 'devices' | 'settings'

export interface AppRoute {
  to: string
  screen: ScreenName
  end?: boolean
  hasCalendar: boolean
}

export const ROUTES: AppRoute[] = [
  { to: '/',              screen: 'home',         end: true, hasCalendar: false },
  { to: '/chat',          screen: 'chat',                    hasCalendar: true  },
  { to: '/journal',       screen: 'journal',                 hasCalendar: true  },
  { to: '/blog',          screen: 'blog',                    hasCalendar: true  },
  { to: '/timeline',      screen: 'timeline',                hasCalendar: true  },
  { to: '/insights',      screen: 'insights',                hasCalendar: true  },
  { to: '/instructions',  screen: 'instructions',            hasCalendar: false },
  { to: '/plugins',       screen: 'plugins',                 hasCalendar: false },
  { to: '/devices',       screen: 'devices',                 hasCalendar: false },
  { to: '/settings',      screen: 'settings',                hasCalendar: false },
]
