# Theming — how the two skins work

2brn ships two switchable UI themes ("skins"): **modern** (the original indigo
look) and **minimal** (a monochrome, text-first design language). The user picks
one in **Settings → Appearance**; the choice persists in `localStorage`
(`2brn-skin`) and applies instantly. Light/dark/system mode is independent of
the skin and works in both.

## Architecture

Two attributes on `<html>` drive everything (set by `theme/ThemeContext.tsx`):

- `data-skin="modern" | "minimal"` — which token set renders.
- `data-theme="light" | "dark"` — the resolved mode (system is resolved in JS
  against the OS theme reported by the Electron bridge).

**Every screen is a single component that renders correctly in both skins.**
The look is supplied by a CSS **token contract** (`--k-*`), not by forking the
screen per skin. Only the app *chrome* (sidebar, top bar, panels) differs
structurally between skins, so each skin owns its own `Shell` around the routed
content.

```
ui/src/
├── hooks/                  ← ALL data/logic, shared by both skins (one hook per screen)
├── ui-kit/                 ← the shared component kit, consumed by every screen
│   ├── primitives.tsx      ← Page, PageHeader, Card, Button, Field, Segmented,
│   │                          ChatMessage, EmptyState, Markdown, … (read --k-* tokens)
│   ├── Icon.tsx            ← BRN_ICON_PATHS (SVG) + ICON_EMOJI (the icon vocabulary)
│   ├── KitProvider.tsx     ← supplies the active skin to primitives via useKit()
│   ├── kit.css             ← `.k-*` classes for pseudo-states inline styles can't express
│   └── index.ts            ← barrel: screens `import { … } from '../ui-kit'`
├── screens/
│   ├── *.tsx               ← the 10 UNIFIED screens (Home, Chat, Journal, Blog,
│   │                          Timeline, Insights, Instructions, Plugins, Devices,
│   │                          Settings) — one component each, built on the ui-kit
│   ├── modern/Shell.tsx    ← modern chrome (sidebar/top bar)
│   └── minimal/            ← minimal chrome only: Shell, chrome/ (Sidebar, TopBar,
│                              CalendarPanel, DebugPanel), Icon, minimalDesign.ts,
│                              primitives.tsx
├── components/shared/      ← genuinely shared bits (ErrorBoundary, MarkdownRenderer, …)
└── theme/
    ├── ThemeContext.tsx    ← { skin, mode } → data-skin / data-theme on <html>
    ├── tokens.css          ← the --k-* TOKEN CONTRACT (see below)
    ├── registry.ts         ← unified screen map + per-skin Shell map
    ├── routes.ts           ← shared route table (paths, screen names, calendar rules)
    └── minimal.css         ← minimal's own --bg/--fg/… vars, scoped under [data-skin='minimal']
```

### The `--k-*` token contract

`theme/tokens.css` defines **one semantic vocabulary** (`--k-bg`, `--k-fg`,
`--k-radius`, `--k-text-transform`, `--k-card-shadow`, `--k-page-pad`, …) that
every ui-kit primitive consumes — mostly through inline styles
(`style={{ padding: 'var(--k-page-pad)' }}`), with `kit.css` covering the
focus/hover states inline styles can't reach. Each skin *maps the contract onto
its own palette and scale*:

- **modern** is the default `:root`, which forwards the contract to the existing
  `index.css` variables (`--k-bg: var(--bg-base)`, `--k-radius: 12px`, …).
- **minimal** remaps the same tokens under `:root[data-skin='minimal']` to its
  own `minimal.css` variables — square corners (`--k-radius: 0`), no elevation
  (`--k-card-shadow: none`, `--k-glow: none`), lowercase (`--k-text-transform:
  lowercase`), lighter weights, an airier spacing scale, and a monochrome
  palette.

Structural treatment (radius, casing, card border/shadow, density, type scale)
is therefore expressed **as tokens**, not as forked screens. The kit reads
**only** `--k-*`; skins keep their existing `--text`/`--fg`/… variables
untouched.

### When a difference can't be a token

Pure-style differences flow through the token contract. The handful of
*structural* differences — e.g. emoji glyphs (modern) vs. line-drawn SVG icons
(minimal) — are branched explicitly inside a primitive via `useKit().skin`
(`KitProvider` supplies it). The minimal-only Tailwind scales used by the
minimal **chrome** are namespaced with an `m-` prefix in `tailwind.config.js`
(`text-m-base`, `tracking-m-label`, …) so the default scales are untouched.

## The minimal design language (short version)

The canonical spec is the design handoff (`design_handoff_2brn_minimal_theme/`).
The rules the code enforces (via the minimal token mapping + `screens/minimal/`):

1. Two colors (`--bg`/`--fg`) + `--muted` + `--rule`; **one accent** (muted
   red) used only for live/important cues — the capturing dot, the "now" dot,
   worse-than-baseline deltas, errors, destructive confirms.
2. State is encoded by the **intensity ramp** `--ink-0…4`
   (`screens/minimal/minimalDesign.ts` maps productivity states to levels);
   categories are neutral pills. Never hue.
3. Inter, weights **300/400 only**. All UI text lowercase, written in content
   (never `text-transform`). Document/daemon content is exempt.
4. No box-shadow, no gradients (except the donut's `conic-gradient`), no
   border-radius beyond the **3px pill** (and the handoff's own rounded
   switch/dots).
5. Hovers transition `color 0.2s ease` (`--muted → --fg`); ghost buttons also
   move their border. No other motion.

## Adding a new screen (checklist)

1. **Logic first** — put all data fetching/mutations/state in a hook under
   `ui/src/hooks/`. No presentation in the hook.
2. Add the route to `ui/src/theme/routes.ts` (path, screen name, `hasCalendar`).
3. Build **one** `ui/src/screens/YourScreen.tsx`, composing ui-kit primitives
   (`import { Page, PageHeader, Card, … } from '../ui-kit'`). The look comes
   entirely from the `--k-*` contract — don't hardcode colors, radii, or casing.
4. Register the screen in `ui/src/theme/registry.ts` (the `screens` map).
5. If the design needs a difference the contract can't express yet, **add a new
   `--k-*` token** in `theme/tokens.css` (mapped in both the `:root` and
   `[data-skin='minimal']` blocks) — prefer that over branching. Only branch on
   `useKit().skin` for genuinely structural differences.
6. Add a nav entry: emoji + label + path in `screens/modern/Shell.tsx`'s `NAV`;
   the minimal sidebar derives its entry from `routes.ts`, but the screen's icon
   name must exist in `ui-kit/Icon.tsx` (`BRN_ICON_PATHS` / `ICON_EMOJI`).
7. Add the route to `ui/scripts/capture-screenshots.mjs` `SECTIONS` and
   regenerate the gallery (`pnpm screenshots` with `pnpm dev` running) — it
   captures every screen in both skins × both modes.

**What this architecture buys (and costs):** a UI change is now made **once**,
in the single screen component, and both skins follow from the token contract —
no more maintaining two parallel screen trees. The cost moves into the contract:
the `--k-*` vocabulary has to be rich enough to express both designs, and only
the per-skin `Shell` (chrome) is still authored twice.

## Verifying you didn't break the other skin

The gallery script doubles as a regression harness: capture before and after
your change and pixel-diff. Two captures of *identical* code differ by ~30 px
per image (the live status footer), so anything in the hundreds of pixels is
real. The daemon is fully stubbed (`stubResponse` in the script) — update the
stubs when the API surface grows, or screens will render their error state in
the gallery. The UI also has Vitest unit tests (`pnpm test`) covering the pure
hooks/helpers and the token contract.
