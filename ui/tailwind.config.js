/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // Resolve through the CSS variables so the stacks follow the active
        // skin (modern → Geist, minimal → Inter; see index.css / theme/minimal.css).
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      colors: {
        base:         '#0e0e12',
        // Skin-aware: resolves through CSS variables, so utilities follow the
        // data-skin / data-theme attributes on <html> (see src/theme/).
        accent: { DEFAULT: 'var(--accent)', strong: 'var(--accent-strong)', hover: 'var(--accent-hover)' },
        // Minimal-skin palette (defined in src/theme/minimal.css)
        bg:    'var(--bg)',
        fg:    'var(--fg)',
        muted: 'var(--muted)',
        rule:  'var(--rule)',
        ink: {
          0: 'var(--ink-0)', 1: 'var(--ink-1)', 2: 'var(--ink-2)',
          3: 'var(--ink-3)', 4: 'var(--ink-4)',
        },
      },
      boxShadow: {
        'glow-sm': '0 0 0 1px rgba(129,140,248,0.3), 0 0 12px rgba(129,140,248,0.1)',
        'glow':    '0 0 0 1px rgba(129,140,248,0.4), 0 0 24px rgba(129,140,248,0.15)',
      },
      // ── Minimal-skin scales ────────────────────────────────────────────────
      // Namespaced with an `m-` prefix so the default scales (used by the
      // modern skin) are untouched. Handoff name → utility: the spec's
      // `text-base` is `text-m-base`, `tracking-label` is `tracking-m-label`,
      // `leading-loose` is `leading-m-loose`, spacing `md` is `m-md`.
      fontSize: {
        'm-2xs': '0.65rem', 'm-xs': '0.7rem', 'm-sm': '0.75rem', 'm-base': '0.8rem',
        'm-md': '0.85rem', 'm-lg': '0.95rem', 'm-xl': '1.05rem', 'm-2xl': '1.4rem',
        'm-display': 'clamp(1.4rem, 3vw, 2.2rem)',
        'm-hero':    'clamp(1.6rem, 3.2vw, 2.2rem)',
      },
      letterSpacing: {
        'm-tight': '-0.02em', 'm-snug': '0.05em', 'm-wide': '0.1em',
        'm-wider': '0.15em', 'm-nav': '0.2em', 'm-label': '0.25em',
      },
      lineHeight: {
        'm-tight': '1.2', 'm-snug': '1.5', 'm-normal': '1.6',
        'm-relaxed': '1.7', 'm-loose': '1.75',
      },
      spacing: {
        'm-xs': '0.5rem', 'm-sm': '1rem', 'm-md': '2rem', 'm-lg': '4rem', 'm-xl': '8rem',
      },
      borderRadius: {
        pill: '3px', // the ONLY radius in the minimal system
      },
      maxWidth: {
        measure: '560px', // minimal reading width for prose
      },
    },
  },
  plugins: [],
}
