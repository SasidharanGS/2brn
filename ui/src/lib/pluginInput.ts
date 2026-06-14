// Pure parsers for the new-plugin form's free-text args/env fields. Kept out of
// the hook so they're unit-testable without React.

/** One arg per non-empty line, trimmed. Empty text → []. */
export function parseArgs(text: string): string[] {
  return text.trim().length === 0
    ? []
    : text.split('\n').map((s) => s.trim()).filter(Boolean)
}

/**
 * `KEY=value` per line → object. Skips blank lines and `#` comments; a line
 * with no `=` (or a leading `=`) is ignored. The value keeps everything after
 * the first `=` (so `=` is allowed inside values), trimmed.
 */
export function parseEnv(text: string): Record<string, string> {
  const out: Record<string, string> = {}
  text.split('\n').forEach((line) => {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) return
    const eq = trimmed.indexOf('=')
    if (eq <= 0) return
    const key = trimmed.slice(0, eq).trim()
    const value = trimmed.slice(eq + 1).trim()
    if (key) out[key] = value
  })
  return out
}
