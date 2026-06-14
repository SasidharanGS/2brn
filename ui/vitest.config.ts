import { defineConfig } from 'vitest/config'

// Pure-function unit tests run in a plain Node env (no DOM/daemon). Component
// and hook tests (RTL + jsdom) can be added later behind a per-file environment.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
