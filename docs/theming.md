# Theming — how the two skins work

2brn ships two switchable UI themes ("skins"): **modern** (the original indigo
look) and **minimal** (a monochrome, text-first design language). The user picks
one in **Settings → Appearance**; the choice persists in `localStorage`
(`2brn-skin`) and applies instantly. Light/dark/system mode is independent of
the skin and works in both.

## Architecture

A skin is **a presentation package, not a stylesheet**. The two skins differ
structurally (icons, text casing, chart technology, chrome layout), so CSS
variables alone couldn't express them. Instead:

```
ui/src/
├── hooks/                  ← ALL data/logic, shared by both skins
├── screens/
│   ├── modern/             ← modern presentation (Shell + 9 screens)
│   └── minimal/            ← minimal presentation (Shell, chrome/, 9 screens,
│                              Icon, primitives, minimalDesign, Prose, …)
├── components/shared/      ← modern chrome + genuinely shared bits
│                              (ErrorBoundary, MarkdownRenderer)
└── theme/
    ├── ThemeContext.tsx    ← { skin, mode } → data-skin / data-theme on <html>
    ├── registry.ts         ← per-skin screen map + per-skin Shell
    ├── routes.ts           ← shared route table (paths, calendar rules)
    └── minimal.css         ← minimal tokens + chrome CSS, all scoped
                               under [data-skin='minimal']
```

Two attributes on `<html>` drive everything:

- `data-skin="modern" | "minimal"` — which token set and component package render.
- `data-theme="light" | "dark"` — the resolved mode (system is resolved in JS
  against the OS theme reported by the Electron bridge).

Color tokens flow through CSS variables, so Tailwind utilities like
`text-accent` resolve correctly under either skin. Minimal-only type/spacing
scales are namespaced with an `m-` prefix in `tailwind.config.js`
(`text-m-base`, `tracking-m-label`, …) so the default scales used by modern are
untouched.

## The minimal design language (short version)

The canonical spec is the design handoff (`design_handoff_2brn_minimal_theme/`).
The rules the code enforces:

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
3. Build `ui/src/screens/modern/YourScreen.tsx` and
   `ui/src/screens/minimal/YourScreen.tsx`, both consuming the same hook.
   For the minimal one, compose from `screens/minimal/primitives.tsx`
   (Card, GhostButton, Pill, Label, StateLabel, Segmented, EmptyState, Field,
   `lineInput`, Switch), `Icon.tsx`, and `PageHeader.tsx`; wrap markdown in
   `Prose.tsx`.
4. Register both in `ui/src/theme/registry.ts`. (A screen missing from the
   minimal map silently falls back to modern — useful while iterating.)
5. Add a nav entry: emoji + label in `screens/modern/Shell.tsx`'s `NAV`;
   the minimal sidebar derives its entry from `routes.ts`, but the icon name
   must exist in `screens/minimal/Icon.tsx` (`BRN_ICON_PATHS`).
6. Add the route to `ui/scripts/capture-screenshots.mjs` `SECTIONS` and
   regenerate the gallery (`pnpm screenshots` with `pnpm dev` running) —
   it captures every screen in both skins × both modes.

**The trade-off this architecture accepts:** every future UI change is made
twice, once per skin. That's deliberate — it buys pixel fidelity to both
designs and keeps each skin's code simple.

## Verifying you didn't break the other skin

The gallery script doubles as a regression harness: capture before and after
your change and pixel-diff. Two captures of *identical* code differ by ~30 px
per image (the live status footer), so anything in the hundreds of pixels is
real. The daemon is fully stubbed (`stubResponse` in the script) — update the
stubs when the API surface grows, or screens will render their error state in
the gallery.
