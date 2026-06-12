import { chromium } from 'playwright'
import { mkdir, writeFile } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = path.resolve(__dirname, '../../docs/screenshots')
const BASE_URL = process.env.VITE_URL ?? 'http://localhost:5173'

const TODAY = new Date().toISOString().slice(0, 10)

const SECTIONS = [
  { route: '/',             name: 'home',         hasCalendar: false },
  { route: '/chat',         name: 'chat',         hasCalendar: true  },
  { route: '/journal',      name: 'journal',      hasCalendar: true  },
  { route: '/blog',         name: 'blog',         hasCalendar: true  },
  { route: '/timeline',     name: 'timeline',     hasCalendar: true  },
  { route: '/insights',     name: 'insights',     hasCalendar: true  },
  { route: '/instructions', name: 'instructions', hasCalendar: false },
  { route: '/plugins',      name: 'plugins',      hasCalendar: false },
  { route: '/settings',     name: 'settings',     hasCalendar: false },
]

const THEMES = ['dark', 'light']
const SKINS = ['modern', 'minimal']

const STUB_STATUS = {
  status: 'capturing',
  capture_count_today: 42,
  last_captured_at: new Date().toISOString(),
  daemon_version: '0.1.0',
}

const STUB_ACTIVITIES = [
  { id: 1, capture_id: 1, started_at: new Date(Date.now() - 3600000).toISOString(), ended_at: new Date().toISOString(), summary: 'Working on the 2brn UI', tags: 'coding,react', task_category: 'work', task_category_confidence: 0.95, productivity_state: 'deep_work', productivity_confidence: 0.9, category_overridden_by_user: false },
  { id: 2, capture_id: 2, started_at: new Date(Date.now() - 7200000).toISOString(), ended_at: new Date(Date.now() - 3600000).toISOString(), summary: 'Reading documentation', tags: 'research', task_category: 'research', task_category_confidence: 0.85, productivity_state: 'productive', productivity_confidence: 0.8, category_overridden_by_user: false },
  { id: 3, capture_id: 3, started_at: new Date(Date.now() - 10800000).toISOString(), ended_at: new Date(Date.now() - 7200000).toISOString(), summary: 'Writing tests for daemon module', tags: 'testing,python', task_category: 'work', task_category_confidence: 0.92, productivity_state: 'deep_work', productivity_confidence: 0.88, category_overridden_by_user: false },
]

const STUB_CAPTURES = [
  { id: 1, captured_at: new Date().toISOString(), app_name: 'Visual Studio Code', window_title: 'capture-screenshots.mjs — 2brn', file_path: null, trigger: 'interval', monitor_index: 0 },
  { id: 2, captured_at: new Date(Date.now() - 60000).toISOString(), app_name: 'Safari', window_title: 'Playwright Docs', file_path: null, trigger: 'interval', monitor_index: 0 },
]

const STUB_JOURNAL = {
  date: TODAY,
  content: `# Journal — ${TODAY}\n\nToday was a productive day focused on the 2brn project. Spent most of the morning implementing the screenshot export feature using Playwright. The work required understanding the Electron + Vite dev server setup and how to mock API responses for headless capture.\n\n## Highlights\n- Implemented Playwright-based screenshot script\n- Mocked all daemon API endpoints\n- Captured all 9 sections in both light and dark themes\n\n## Tomorrow\n- Review generated screenshots\n- Share with design team for feedback`,
  generated_at: new Date().toISOString(),
  edited_by_user: false,
}

const STUB_BLOG = {
  date: TODAY,
  content: `# Building a Local-First Second Brain\n\nI've been working on 2brn, a desktop app that continuously captures your screen, runs OCR, and uses AI to build a rich activity history — all stored locally.\n\n## Why Local-First?\n\nPrivacy matters. Your screen captures contain sensitive information: code, emails, documents. By keeping everything on-device with AES-256-GCM encryption, you own your data completely.\n\n## The Architecture\n\nThe system has two main components: a FastAPI daemon that handles capture and inference, and an Electron/React UI for exploration. They communicate over a loopback HTTP API on port 7842.\n\n## What's Next\n\nI'm working on a plugin system that lets MCP servers react to your activity in real time. Stay tuned!`,
  generated_at: new Date().toISOString(),
  edited_by_user: false,
}

const STUB_DAILY_INSIGHTS = {
  date: TODAY,
  categories: [
    { task_category: 'coding', count: 28, avg_confidence: 0.92 },
    { task_category: 'research', count: 8, avg_confidence: 0.85 },
    { task_category: 'communication', count: 4, avg_confidence: 0.78 },
    { task_category: 'other', count: 2, avg_confidence: 0.6 },
  ],
  productivity_states: [
    { productivity_state: 'deep_work', count: 22 },
    { productivity_state: 'productive', count: 14 },
    { productivity_state: 'distracted', count: 4 },
    { productivity_state: 'idle', count: 2 },
  ],
  top_apps: [
    { app_name: 'Visual Studio Code', count: 24 },
    { app_name: 'Terminal', count: 10 },
    { app_name: 'Safari', count: 6 },
    { app_name: 'Slack', count: 2 },
  ],
}

const STUB_INSIGHTS_SUMMARY = {
  period: 'day',
  date: TODAY,
  range: { start: TODAY, end: TODAY, span_days: 1 },
  total_captures: 42,
  observed_seconds: 23400,
  categories: [
    { task_category: 'coding', count: 28, pct: 66.7, avg_confidence: 0.92 },
    { task_category: 'research', count: 8, pct: 19.0, avg_confidence: 0.85 },
    { task_category: 'communication', count: 4, pct: 9.5, avg_confidence: 0.78 },
    { task_category: 'other', count: 2, pct: 4.8, avg_confidence: 0.6 },
  ],
  productivity_states: [
    { productivity_state: 'deep_work', count: 22, pct: 52.4 },
    { productivity_state: 'productive', count: 14, pct: 33.3 },
    { productivity_state: 'distracted', count: 4, pct: 9.5 },
    { productivity_state: 'idle', count: 2, pct: 4.8 },
  ],
  top_apps: [
    { app_name: 'Visual Studio Code', count: 24, seconds: 13380, pct: 57.1 },
    { app_name: 'Terminal', count: 10, seconds: 5580, pct: 23.8 },
    { app_name: 'Safari', count: 6, seconds: 3360, pct: 14.3 },
    { app_name: 'Slack', count: 2, seconds: 1080, pct: 4.8 },
  ],
  // Deterministic so re-captures stay pixel-comparable
  hourly_heatmap: [0, 0, 0, 0, 0, 0, 0, 8, 22, 64, 58, 41, 17, 33, 52, 71, 47, 24, 9, 0, 4, 2, 0, 0]
    .map((pct, hour) => ({
      hour,
      pct,
      dominant_state: pct > 0 ? 'deep_work' : null,
      by_state_pct: { deep_work: 0.6, productive: 0.3, distracted: 0.1 },
    })),
  comparison: {
    baseline_label: '7-day average',
    active: { current_pct: 85.7, baseline_pct: 78.2 },
    productive: { current_pct: 85.7, baseline_pct: 72.1 },
    distracted: { current_pct: 9.5, baseline_pct: 18.3 },
  },
  recurring_activities: [
    { canonical_summary: 'Writing TypeScript code in VS Code', pct: 45.2, occurrences: 19, variant_count: 3, approx_seconds: 1500 },
    { canonical_summary: 'Running terminal commands', pct: 23.8, occurrences: 10, variant_count: 2, approx_seconds: 600 },
    { canonical_summary: 'Browsing documentation', pct: 14.3, occurrences: 6, variant_count: 4, approx_seconds: 900 },
  ],
}

const STUB_SETTINGS = {
  chat_provider: { type: 'openai', base_url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  embed_provider: { type: 'openai', base_url: 'https://api.openai.com/v1', model: 'text-embedding-3-small' },
  has_chat_key: true,
  has_embed_key: true,
  capture_interval_seconds: 60,
  change_cooldown_seconds: 10,
  max_idle_tick_seconds: 300,
  similarity_threshold: 0.92,
  purge_months: 3,
  paused: false,
  blog_mirror_enabled: false,
  screenshot_encryption_enabled: false,
  journal_schedule: { hour: 22, minute: 0 },
  blog_schedule: { frequency: 'daily', hour: 23, minute: 0, day: 1, days_of_week: [] },
  joplin_enabled: false,
  joplin_db_path: '',
}

const STUB_DEBUG_STATUS = {
  daemon: { status: 'capturing', capture_count_today: 42, last_captured_at: new Date().toISOString(), paused: false },
  gateway: { url: 'https://api.openai.com/v1', reachable: true, model: 'gpt-4o' },
  chroma: { activity_memories: 420, note_memories: 15 },
  last_error: null,
}

const STUB_SESSIONS = {
  blocks: [
    { start: `${TODAY}T07:53:00`, end: `${TODAY}T09:10:00`, monitor_index: 0, app_name: 'Visual Studio Code', task_category: 'work', duration_seconds: 4620, summary: 'Writing tests for daemon module' },
    { start: `${TODAY}T09:15:00`, end: `${TODAY}T09:50:00`, monitor_index: 0, app_name: 'Safari', task_category: 'research', duration_seconds: 2100, summary: 'Reading documentation' },
    { start: `${TODAY}T09:55:00`, end: `${TODAY}T11:20:00`, monitor_index: 0, app_name: 'Visual Studio Code', task_category: 'work', duration_seconds: 5100, summary: 'Working on the 2brn UI' },
  ],
  totals: { observed_seconds: 11820, by_category: { work: 9720, research: 2100 } },
}

const STUB_LOGS = {
  lines: [
    { ts: '09:53:04', level: 'INFO', msg: 'capture #42 saved' },
    { ts: '09:53:05', level: 'INFO', msg: 'ocr ok — 1240 chars' },
    { ts: '09:53:07', level: 'INFO', msg: 'inference → deep_work / work' },
    { ts: '09:53:08', level: 'INFO', msg: 'embedded — chroma upsert ok' },
  ],
}

function stubResponse(url) {
  const p = new URL(url).pathname
  if (p === '/status') return STUB_STATUS
  if (p.startsWith('/activities')) return STUB_ACTIVITIES
  if (p.startsWith('/captures')) return STUB_CAPTURES
  if (p.match(/^\/journal\//)) return STUB_JOURNAL
  if (p.match(/^\/blog\//)) return STUB_BLOG
  if (p.startsWith('/insights/daily')) return STUB_DAILY_INSIGHTS
  if (p.startsWith('/insights/summary')) return STUB_INSIGHTS_SUMMARY
  if (p === '/settings') return STUB_SETTINGS
  if (p.startsWith('/settings/exclusions')) return []
  if (p.startsWith('/settings')) return STUB_SETTINGS
  if (p.startsWith('/instructions')) return []
  if (p.startsWith('/plugins')) return []
  if (p.startsWith('/plugin-rules')) return []
  if (p.startsWith('/sessions')) return STUB_SESSIONS
  if (p.startsWith('/logs')) return STUB_LOGS
  if (p.startsWith('/debug/status')) return STUB_DEBUG_STATUS
  return {}
}

async function setupMocks(page, skin) {
  // Mock window.electronAPI + pin the skin — must be set before page load
  await page.addInitScript((s) => {
    localStorage.setItem('2brn-skin', s)
    window.electronAPI = {
      getDaemonPort: () => Promise.resolve(7842),
      getApiToken: () => Promise.resolve('mock-token'),
      getPlatform: () => Promise.resolve('darwin'),
      getTheme: () => Promise.resolve('dark'),
      onThemeChanged: () => () => {},
      onDaemonStatus: () => () => {},
      isDaemonOwned: () => Promise.resolve(true),
      restartDaemon: () => Promise.resolve({ ok: true }),
    }
  }, skin)

  // Intercept all daemon API calls (127.0.0.1:7842)
  await page.route('http://127.0.0.1:7842/**', async (route) => {
    const url = route.request().url()
    const method = route.request().method()
    if (method === 'GET' || method === 'POST' || method === 'PUT' || method === 'PATCH' || method === 'DELETE') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(stubResponse(url)),
      })
    } else {
      await route.continue()
    }
  })
}

async function forceTheme(page, theme) {
  await page.evaluate((t) => {
    document.documentElement.setAttribute('data-theme', t === 'light' ? 'light' : 'dark')
  }, theme)
  await page.waitForTimeout(200)
}

async function capture(page, filePath) {
  await page.waitForTimeout(700)
  await page.screenshot({ path: filePath, fullPage: false })
  console.log('  saved:', path.relative(process.cwd(), filePath))
}

/** Find the calendar / debug toggle for the active skin. */
function chromeButton(page, skin, kind) {
  // modern: "\u25c8 calendar" / "\u2b21 debug" sidebar buttons; minimal: plain rail labels
  const label = skin === 'modern'
    ? (kind === 'calendar' ? '\u25c8 calendar' : '\u2b21 debug')
    : kind
  return page.locator('button', { hasText: label }).first()
}

async function run() {
  await mkdir(OUT_DIR, { recursive: true })

  const browser = await chromium.launch({ headless: true })
  const gallery = []

  for (const skin of SKINS) {
    for (const theme of THEMES) {
      console.log(`\n=== ${skin} / ${theme} ===`)

      // New context + page per skin/theme so init scripts apply cleanly
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
      const page = await context.newPage()
      page.on('pageerror', err => console.error(`  [pageerror ${skin}/${theme}]`, String(err).slice(0, 200)))
      await setupMocks(page, skin)

      const suffix = `${skin}-${theme}`

      for (const section of SECTIONS) {
        console.log(`\n[${suffix}] ${section.name}`)

        await page.goto(`${BASE_URL}/#${section.route}`, { waitUntil: 'networkidle' })
        await forceTheme(page, theme)

        if (section.hasCalendar) {
          const calBtn = chromeButton(page, skin, 'calendar')

          // Each goto reloads the shell, so the calendar starts at the skin's
          // default: open on modern, closed on minimal.
          if (skin === 'modern') {
            await calBtn.click()
            await page.waitForTimeout(300)
          }

          const defaultFile = path.join(OUT_DIR, `${section.name}--default--${suffix}.png`)
          await capture(page, defaultFile)
          gallery.push({ file: path.basename(defaultFile), section: section.name, variant: 'default', skin, theme })

          await calBtn.click()
          await page.waitForTimeout(400)

          const calFile = path.join(OUT_DIR, `${section.name}--calendar-open--${suffix}.png`)
          await capture(page, calFile)
          gallery.push({ file: path.basename(calFile), section: section.name, variant: 'calendar-open', skin, theme })

          await calBtn.click()
          await page.waitForTimeout(200)

        } else {
          const defaultFile = path.join(OUT_DIR, `${section.name}--default--${suffix}.png`)
          await capture(page, defaultFile)
          gallery.push({ file: path.basename(defaultFile), section: section.name, variant: 'default', skin, theme })
        }

        // Debug panel variant — only on home
        if (section.name === 'home') {
          const dbgBtn = chromeButton(page, skin, 'debug')
          await dbgBtn.click()
          await page.waitForTimeout(400)

          const dbgFile = path.join(OUT_DIR, `home--debug-panel--${suffix}.png`)
          await capture(page, dbgFile)
          gallery.push({ file: path.basename(dbgFile), section: 'home', variant: 'debug-panel', skin, theme })

          await dbgBtn.click()
          await page.waitForTimeout(200)
        }
      }

      await context.close()
    }
  }

  await browser.close()
  await generateGallery(gallery)
  console.log('\nDone!')
  console.log('Gallery:', path.join(OUT_DIR, 'index.html'))
  console.log('Images:', gallery.length)
}

async function generateGallery(items) {
  const sections = [...new Set(items.map(i => i.section))]

  const sectionBlocks = sections.map(s => {
    const sectionItems = items.filter(i => i.section === s)
    const thumbs = sectionItems.map(i => `
      <figure style="margin:0">
        <a href="${i.file}" target="_blank">
          <img src="${i.file}" alt="${i.file}" loading="lazy" style="width:100%;border-radius:8px;border:1px solid #2a2a3a;display:block;transition:opacity .2s" onmouseover="this.style.opacity='.8'" onmouseout="this.style.opacity='1'">
        </a>
        <figcaption style="font-size:11px;color:#666;margin-top:6px;font-family:monospace">${i.variant} · ${i.skin} · ${i.theme}</figcaption>
      </figure>`).join('\n')

    return `
    <section style="margin-bottom:48px">
      <h2 style="text-transform:capitalize;font-size:18px;border-bottom:1px solid #222;padding-bottom:10px;margin-bottom:20px;color:#c0c0d0">${s}</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:20px">
        ${thumbs}
      </div>
    </section>`
  }).join('\n')

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>2brn — Screenshot Gallery</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e0e0e0; padding: 40px 32px; max-width: 1440px; margin: 0 auto; }
    h1 { font-size: 28px; font-weight: 600; letter-spacing: -0.5px; margin-bottom: 8px; }
    .meta { color: #555; font-size: 13px; margin-bottom: 40px; font-family: monospace; }
    img { cursor: pointer; }
  </style>
</head>
<body>
  <h1>2<span style="color:#818cf8">brn</span> — Screenshot Gallery</h1>
  <p class="meta">Generated ${new Date().toISOString()} · ${items.length} images</p>
  ${sectionBlocks}
</body>
</html>`

  await writeFile(path.join(OUT_DIR, 'index.html'), html)
}

run().catch(err => { console.error(err); process.exit(1) })
