# 2brn Electron App Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure `electron-builder` to produce a `2brn.dmg` that bundles the Python daemon, uses a brain emoji app icon, and installs to `/Applications/2brn.app`.

**Architecture:** Three files added to `ui/`: `scripts/generate-icon.sh` renders the 🧠 emoji to `.icns` using Pillow + macOS `iconutil`; `electron-builder.yml` configures the build with `extraResources` to copy `daemon/src/` and `daemon/.venv/` into `Contents/Resources/daemon/` (where `main.ts` already looks in production); `build/icon.icns` is the generated icon asset. No changes to any app logic.

**Tech Stack:** electron-builder 24, Pillow (daemon venv), macOS `sips`, macOS `iconutil`, pnpm

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `ui/scripts/generate-icon.sh` | **Create** | Renders brain emoji PNG → iconset → `.icns` |
| `ui/build/icon.icns` | **Create** (generated) | App icon consumed by electron-builder |
| `ui/electron-builder.yml` | **Create** | electron-builder config: app id, icon, dmg target, extraResources |

---

### Task 1: Create the icon generation script and generate `icon.icns`

**Files:**
- Create: `ui/scripts/generate-icon.sh`
- Create (generated): `ui/build/icon.icns`

- [ ] **Step 1: Create `ui/scripts/generate-icon.sh`**

```bash
mkdir -p /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/scripts
```

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/scripts/generate-icon.sh` with this exact content:

```bash
#!/usr/bin/env bash
# generate-icon.sh — render the brain emoji to ui/build/icon.icns
# Uses: daemon/.venv Pillow, macOS sips, macOS iconutil
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VENV_PYTHON="$REPO_ROOT/daemon/.venv/bin/python3"
BUILD_DIR="$REPO_ROOT/ui/build"
ICONSET_DIR="$BUILD_DIR/icon.iconset"
OUTPUT_ICNS="$BUILD_DIR/icon.icns"
SOURCE_PNG="$BUILD_DIR/icon_1024.png"

mkdir -p "$ICONSET_DIR"

# Step 1: render brain emoji at 1024x1024 using Pillow + Apple Color Emoji font
export OUTPUT_PNG="$SOURCE_PNG"
"$VENV_PYTHON" - <<'PYEOF'
import os
from PIL import Image, ImageDraw, ImageFont

size = 1024
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 960)
bbox = draw.textbbox((0, 0), "\U0001f9e0", font=font, embedded_color=True)
x = (size - (bbox[2] - bbox[0])) // 2 - bbox[0]
y = (size - (bbox[3] - bbox[1])) // 2 - bbox[1]
draw.text((x, y), "\U0001f9e0", font=font, embedded_color=True)
img.save(os.environ["OUTPUT_PNG"], "PNG")
PYEOF

echo "Rendered brain emoji to $SOURCE_PNG"

# Step 2: generate all required iconset sizes with sips
for SIZE in 16 32 64 128 256 512 1024; do
  sips -z $SIZE $SIZE "$SOURCE_PNG" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png" > /dev/null
  if [[ $SIZE -le 512 ]]; then
    DOUBLE=$((SIZE * 2))
    sips -z $DOUBLE $DOUBLE "$SOURCE_PNG" --out "$ICONSET_DIR/icon_${SIZE}x${SIZE}@2x.png" > /dev/null
  fi
done

echo "Generated iconset sizes"

# Step 3: compile .icns
iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICNS"
echo "✓ Icon generated at $OUTPUT_ICNS"

# Cleanup
rm -rf "$ICONSET_DIR" "$SOURCE_PNG"
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/scripts/generate-icon.sh
```

- [ ] **Step 3: Run the script to generate the icon**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
bash ui/scripts/generate-icon.sh
```

Expected output:
```
Rendered brain emoji to /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/build/icon_1024.png
Generated iconset sizes
✓ Icon generated at /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/build/icon.icns
```

- [ ] **Step 4: Verify the icon was created**

```bash
ls -lh /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/build/icon.icns
```

Expected: file exists, size > 100KB. Example:
```
-rw-r--r--  1 sasidharan.govindan  staff   512K Apr 25 19:30 icon.icns
```

- [ ] **Step 5: Visually verify the icon looks correct**

```bash
qlookup /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/build/icon.icns 2>/dev/null || open /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/build/icon.icns
```

Expected: macOS opens a preview showing the 🧠 brain emoji.

- [ ] **Step 6: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/scripts/generate-icon.sh ui/build/icon.icns
git commit -m "$(cat <<'EOF'
feat: add brain emoji app icon and icon generation script

Renders 🧠 via Pillow + Apple Color Emoji + iconutil.
Committed as ui/build/icon.icns for electron-builder.

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

### Task 2: Create `electron-builder.yml`

**Files:**
- Create: `ui/electron-builder.yml`

- [ ] **Step 1: Create `ui/electron-builder.yml`**

Create `/Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/electron-builder.yml` with this exact content:

```yaml
appId: com.sasidharan.2brn
productName: 2brn
directories:
  output: release
  buildResources: build

mac:
  icon: build/icon.icns
  target:
    - target: dmg
      arch: [arm64, x64]
  category: public.app-category.productivity

dmg:
  title: "2brn"

extraResources:
  - from: ../daemon/src
    to: daemon/src
  - from: ../daemon/.venv
    to: daemon/.venv
  - from: ../daemon/pyproject.toml
    to: daemon/pyproject.toml
```

- [ ] **Step 2: Add `release/` to `.gitignore`**

The `release/` directory will contain the built `.dmg` files (350–450 MB each) — it must not be committed.

Check if `.gitignore` exists at repo root:

```bash
cat /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.gitignore 2>/dev/null | grep release || echo "not present"
```

If `release` is not already in `.gitignore`, append it:

```bash
echo "ui/release/" >> /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/.gitignore
```

- [ ] **Step 3: Commit**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
git add ui/electron-builder.yml .gitignore
git commit -m "$(cat <<'EOF'
feat: add electron-builder config for macOS DMG packaging

Bundles daemon/src + daemon/.venv into Contents/Resources/daemon
via extraResources. Produces arm64 + x64 DMGs in ui/release/.
No code signing (personal use).

Co-Authored-By: Claude Opus 4.6 <noreply@openclaude.dev>
EOF
)"
```

---

### Task 3: Run the build and verify the DMG

**Files:**
- No new files — this task runs and validates the build.

> **Note:** This build will take 5–15 minutes and produce a ~400 MB DMG. The `.venv` copy is the slow part.

- [ ] **Step 1: Trigger nvm lazy init and verify pnpm is available**

```bash
nvm --version
pnpm --version
```

Expected: both print version strings (e.g. `0.39.7` and `9.x.x`).

- [ ] **Step 2: Run the build**

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui
pnpm electron:build
```

Expected: build runs, TypeScript compiles, Vite bundles, electron-builder packages. Final lines should look like:

```
  • building        target=DMG arch=arm64 file=release/2brn-0.1.0-arm64.dmg
  • building        target=DMG arch=x64 file=release/2brn-0.1.0-x64.dmg
  • build success
```

If build fails with `"cannot find module 'electron-builder'"`:
```bash
pnpm install
pnpm electron:build
```

- [ ] **Step 3: Verify DMG files were produced**

```bash
ls -lh /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/release/*.dmg
```

Expected: two `.dmg` files, each 300–500 MB:
```
-rw-r--r--  ...  380M  ...  2brn-0.1.0-arm64.dmg
-rw-r--r--  ...  380M  ...  2brn-0.1.0-x64.dmg
```

- [ ] **Step 4: Install the correct DMG for your machine**

Check your architecture:
```bash
uname -m
```
- `arm64` → install `2brn-0.1.0-arm64.dmg`
- `x86_64` → install `2brn-0.1.0-x64.dmg`

Open the DMG:
```bash
open /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn/ui/release/2brn-0.1.0-arm64.dmg
# (adjust filename to match your arch)
```

Drag `2brn.app` to the `/Applications` folder in the DMG window.

- [ ] **Step 5: First-launch Gatekeeper bypass**

Because the app is unsigned, macOS blocks the first launch:
1. Open `/Applications` in Finder
2. Right-click `2brn.app` → **Open**
3. In the dialog: click **Open**

Expected: the 2brn UI launches with the brain emoji in the Dock.

- [ ] **Step 6: Verify `start-2brn.sh` works end-to-end**

`APP_PATH` in `start-2brn.sh` is already empty — `open -a "2brn"` works now that the app is installed. Run:

```bash
cd /Users/sasidharan.govindan/Library/CloudStorage/OneDrive-JLL/Documents/GitHub/2brn
./start-2brn.sh
```

Expected (gateway already running):
```
✓ Gateway already running on port 8888.
→ Opening 2brn...
```

And 2brn opens from `/Applications/2brn.app`.

---

## Notes

- **Re-running the build:** `pnpm electron:build` from `ui/` is idempotent — it overwrites `release/`.
- **Updating the icon:** Run `bash ui/scripts/generate-icon.sh` again, then rebuild.
- **The `.venv` in the bundle is a snapshot.** If you update daemon dependencies (`uv sync`), rebuild the app to pick up the new venv.
- **`release/` is gitignored** — DMGs are never committed. The sources (`electron-builder.yml`, `generate-icon.sh`, `icon.icns`) are committed.
- **`icon.icns` is committed** so the build works without running `generate-icon.sh` first on a fresh clone.
