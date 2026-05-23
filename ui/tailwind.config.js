/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', '-apple-system', 'sans-serif'],
        mono: ['Geist Mono', 'JetBrains Mono', 'monospace'],
      },
      colors: {
        base:         '#0e0e12',
        accent:       '#818cf8',
        'accent-hover': '#a5b4fc',
      },
      boxShadow: {
        'glow-sm': '0 0 0 1px rgba(129,140,248,0.3), 0 0 12px rgba(129,140,248,0.1)',
        'glow':    '0 0 0 1px rgba(129,140,248,0.4), 0 0 24px rgba(129,140,248,0.15)',
      },
    },
  },
  plugins: [],
}
