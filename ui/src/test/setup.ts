// Vitest setup — runs once per test file (all environments).
// jest-dom matchers (toBeInTheDocument, etc.) are harmless under the node env;
// the React Testing Library cleanup only ever runs in the jsdom (.test.tsx) files.
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
