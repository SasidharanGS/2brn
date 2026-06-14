/**
 * Build the pairing deep link the mobile app scans:
 *   twobrn://pair?u=<encodeURIComponent(url)>&t=<encodeURIComponent(token)>
 *
 * Kept byte-for-byte identical to the mobile parser
 * (2brn-mobile/src/connection/pairing.ts) — URI-encoding (not base64) so it
 * decodes with the built-in decodeURIComponent on both sides. Pure + tiny so
 * it stays trivially testable once the UI test runner lands (epic #94, part 1).
 */
export function buildPairingUrl(baseUrl: string, token: string): string {
  return `twobrn://pair?u=${encodeURIComponent(baseUrl)}&t=${encodeURIComponent(token)}`
}
