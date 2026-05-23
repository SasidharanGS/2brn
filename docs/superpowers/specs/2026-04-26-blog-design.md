# Blog Feature — Design Spec

**Date:** 2026-04-26  
**Status:** Approved  
**Scope:** Auto-generated daily dev log inside 2brn, parallel to the existing Journal section. Publishing to external sources is out of scope for this spec.

---

## 1. Overview

Add a **Blog** section to 2brn that auto-generates a daily public-facing dev log from activity summaries, the existing daily journal, and Joplin notes. The blog is distinct from the Journal:

| | Journal | Blog |
|---|---|---|
| Tone | Personal, unfiltered | Public dev log, company-data excluded |
| Audience | Private (you only) | Public internet (eventually) |
| Source data | All activities | All activities + Joplin notes + daily journal |
| Privacy filter | None | AI-driven — LLM instructed to omit company-confidential content |
| Style | Personal reflection | Dev log / build log narrative |
| Edit guard | `edited_by_user = 1` blocks regen | Same |

Journal is **not modified** in any way. Blog is a fully parallel system.

---

## 2. Data Model

### New SQLite table: `blog_posts`

Added to `init_db()` in `db.py` using `CREATE TABLE IF NOT EXISTS` — existing databases pick it up automatically on next daemon start, no migration script needed.

```sql
CREATE TABLE IF NOT EXISTS blog_posts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    content        TEXT,
    generated_at   TEXT NOT NULL,
    edited_by_user INTEGER NOT NULL DEFAULT 0,
    UNIQUE(date)
);
```

- `date`: `YYYY-MM-DD` string, one post per day
- `edited_by_user`: `1` means user has edited this post — generator skips it on regen
- Conflict resolution: `ON CONFLICT(date) DO UPDATE SET content=excluded.content, generated_at=excluded.generated_at WHERE edited_by_user = 0`

---

## 3. Data Inputs Per Post

For a given `target_date`, the generator collects:

| Source | Query | Purpose |
|---|---|---|
| `activities` table | `summary, task_category, productivity_state WHERE date(started_at) = target_date AND summary IS NOT NULL` | Core activity context |
| `journals` table | `content WHERE date = target_date` | Day's journal as narrative seed |
| Joplin `notes` table | `title, body WHERE updated_time >= start_of_day_ms AND updated_time < start_of_next_day_ms` (Unix ms timestamps, all notebooks) | Personal learnings, ideas, captures |

All three are passed to the LLM. The LLM decides what to include — all notebooks fed in, AI instructed to filter company-confidential content.

---

## 4. Backend

### New file: `daemon/src/brn_daemon/blog.py`

Two classes, mirroring `journal.py`:

#### `BlogGenerator`

```python
class BlogGenerator:
    def __init__(self, gateway: GatewayClient): ...

    async def generate(self, target_date: date) -> str | None:
        # 1. Check edited_by_user guard — return None if set
        # 2. Fetch activity summaries for target_date from SQLite
        # 3. Fetch journal content for target_date from SQLite
        # 4. Fetch Joplin notes modified on target_date from Joplin SQLite (read-only)
        # 5. Build prompt from all three sources
        # 6. Call gateway.chat_complete() with system prompt + user prompt
        # 7. Upsert into blog_posts WHERE edited_by_user = 0
        # 8. Return generated content
```

#### `BlogMirror`

```python
class BlogMirror:
    async def mirror(self, target_date: date, content: str) -> None:
        # Create or update Joplin note titled "Blog — YYYY-MM-DD"
        # in "Blog Posts" notebook via Web Clipper API
        # Silent fallback if Joplin is closed (same as JournalMirror)
```

### System prompt

```
You are a technical writer helping a software engineer maintain a public dev log.
Given a day's activities, journal entry, and notes — write a concise dev log 
entry in first person. Focus on: what was learned, what was built, what was 
tried or experimented with.

Write for a public technical audience. Use a direct, honest, personal tone.
Structure: a short narrative opening, then **What I learned**, **What I built**, 
**Experimenting with** sections as applicable. Only include sections with content.

IMPORTANT: This is a public blog. Omit anything company-confidential — 
client names, internal system names, proprietary business logic, employer-specific 
work tasks, or anything that could identify a client or employer's internal 
systems. If an activity is purely corporate work with no public learning value, 
skip it entirely. Personal projects, open-source tools, technical learnings, 
and experiments are all fair game.
```

### New API router: `daemon/src/brn_daemon/routes/blog.py`

```
GET  /blog/{date}           → BlogPost | 404
POST /blog/{date}/generate  → triggers BlogGenerator.generate(), returns BlogPost
PUT  /blog/{date}           → saves user edits, sets edited_by_user=1, returns BlogPost
```

Request/response shapes mirror journal routes exactly.

### `main.py` changes

1. Import and register `routes/blog.py` router
2. Add APScheduler job:

```python
scheduler.add_job(
    generate_blog_post,
    trigger="cron",
    hour=int(config.blog_generation_time.split(":")[0]),
    minute=int(config.blog_generation_time.split(":")[1]),
    id="blog_daily",
    replace_existing=True,
)
```

Job runs after the 20:30 evening journal (default: 21:30) so the journal is available as input.

### `config.py` changes

Add two fields:

```python
blog_generation_time: str = "21:30"   # HH:MM, 24-hour
blog_mirror_enabled: bool = True       # Mirror posts to Joplin
```

Stored in `~/.2brn/config.json`. On settings update, the APScheduler job is rescheduled dynamically using `replace_existing=True`.

---

## 5. Frontend

### Sidebar (`App.tsx`)

New **"Blog"** nav item added after "Journal" in the left sidebar. Same icon style, same routing pattern.

### New component: `ui/src/components/Blog.tsx`

Layout mirrors `Journal.tsx`:

```
┌─────────────────────────────────────────────────────┐
│  Blog                                    [Generate] │
├──────────────┬──────────────────────────────────────┤
│              │                                      │
│  < Apr 2026 >│  ## April 26 — Dev Log               │
│              │                                      │
│  Calendar    │  Markdown content rendered via        │
│  (dates with │  MarkdownRenderer.tsx                 │
│   posts have │                                      │
│   dot marker)│  [Edit]                              │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

**Behaviour:**
- Calendar on left — same date picker as `Journal.tsx`
- Dates with existing posts show a dot indicator
- Right panel: post rendered via existing `MarkdownRenderer.tsx`
- **[Generate]** button in header — calls `POST /blog/{date}/generate`, shows loading spinner, invalidates query on success
- **[Edit]** button — switches right panel to `<textarea>`, saves via `PUT /blog/{date}` on confirm, cancellable
- Empty state (no post for date): message + "Generate post for this day" button
- Selected date defaults to today on mount

### `api/types.ts` — new interface

```typescript
export interface BlogPost {
  id: number;
  date: string;           // YYYY-MM-DD
  content: string;
  generated_at: string;   // ISO timestamp
  edited_by_user: boolean;
}
```

### `api/client.ts` — new functions

```typescript
getBlogPost(date: string): Promise<BlogPost | null>
generateBlogPost(date: string): Promise<BlogPost>
updateBlogPost(date: string, content: string): Promise<BlogPost>
```

### TanStack Query hooks (inside `Blog.tsx`)

```typescript
// Fetch post for selected date
const { data: post, isLoading } = useQuery({
  queryKey: ['blog', selectedDate],
  queryFn: () => api.getBlogPost(selectedDate),
})

// Generate
const generateMutation = useMutation({
  mutationFn: () => api.generateBlogPost(selectedDate),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blog', selectedDate] }),
})

// Save edits
const updateMutation = useMutation({
  mutationFn: (content: string) => api.updateBlogPost(selectedDate, content),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['blog', selectedDate] }),
})
```

### `Settings.tsx` — new Blog section

```
Blog
────
Daily generation time   [21:30]  (HH:MM, 24-hour)
Joplin mirror           [✓] Mirror blog posts to Joplin "Blog Posts" notebook
```

- Time input: `<input type="time">`, saved via existing `PUT /settings`
- Mirror toggle: boolean, defaults ON
- On save, daemon reschedules the APScheduler blog job dynamically

---

## 6. File Change Summary

| File | Change |
|---|---|
| `daemon/src/brn_daemon/db.py` | Add `blog_posts` table to `init_db()` |
| `daemon/src/brn_daemon/blog.py` | **New** — `BlogGenerator` + `BlogMirror` |
| `daemon/src/brn_daemon/config.py` | Add `blog_generation_time: str = "21:30"` and `blog_mirror_enabled: bool = True` |
| `daemon/src/brn_daemon/main.py` | Register blog router + APScheduler job |
| `daemon/src/brn_daemon/routes/blog.py` | **New** — GET / POST / PUT endpoints |
| `ui/src/components/Blog.tsx` | **New** — full blog UI component |
| `ui/src/App.tsx` | Add Blog nav item + route |
| `ui/src/api/client.ts` | Add 3 blog API functions |
| `ui/src/api/types.ts` | Add `BlogPost` interface |
| `ui/src/components/Settings.tsx` | Add Blog settings section |

---

## 7. Out of Scope (This Spec)

- Publishing to external platforms (GitHub Pages, RSS, Ghost, etc.)
- Blog post tagging or categorisation
- Multi-day blog post drafts
- Public URL or hosting

---

## 8. Testing

- `tests/test_blog.py` — new test file following existing test patterns
- Tests cover: `BlogGenerator.generate()` with mocked gateway, `edited_by_user` guard, empty activities/journal/notes cases
- API route tests: GET 404 on missing post, POST generates and returns, PUT sets `edited_by_user`
- Uses existing `tmp_home` + `db` fixtures from `conftest.py`
