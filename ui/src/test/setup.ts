// Vitest setup — runs once per test file (all environments).
// jest-dom matchers (toBeInTheDocument, etc.) are harmless under the node env;
// the React Testing Library cleanup only ever runs in the jsdom (.test.tsx) files.
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom lacks ResizeObserver, which recharts' ResponsiveContainer needs — stub it
// so chart-bearing screens (Insights) can be rendered in tests.
if (!('ResizeObserver' in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}

afterEach(() => {
  cleanup()
})
