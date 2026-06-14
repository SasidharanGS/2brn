import { defineConfig } from 'vitest/config'

// Pure-function unit tests run in a plain Node env (fast, no DOM). Component and
// hook tests are written as `*.test.tsx` and automatically get a jsdom DOM via
// `environmentMatchGlobs`, so the two never pay for each other's setup.
export default defineConfig({
  test: {
    environment: 'node',
    environmentMatchGlobs: [['src/**/*.test.tsx', 'jsdom']],
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
