# Daemon Auto-Start — Platform Gap

## Current state

The daemon (`brn_daemon`) has auto-start wired only for macOS via launchd:

- **macOS** — `daemon/com.2brn.daemon.plist` — install once, launchd keeps it alive with `KeepAlive: true`. Survives Electron being closed.
- **Windows** — nothing
- **Linux** — nothing

## Options considered

### Option A — Platform-native service files (recommended)
Write the OS-native equivalents and a one-time install helper script:

| Platform | Mechanism | File to create |
|---|---|---|
| Windows | Task Scheduler XML | `daemon/2brn-daemon.task.xml` |
| Linux | systemd user service | `daemon/2brn-daemon.service` |

A helper script (`daemon/install-autostart.py`) detects the platform and installs the right one:
```
python install-autostart.py   # installs for current OS
python install-autostart.py --uninstall
```

**Pros:** Daemon runs independently of the Electron app (same as macOS). Survives crashes via `KeepAlive` / `Restart=on-failure`. Consistent behaviour across all three platforms.

**Cons:** Three separate service file formats to maintain.

### Option B — Electron login item (`app.setLoginItem()`)
Use Electron's built-in cross-platform auto-launch API to start the full Electron app on login. The app then spawns the daemon as it does today.

**Pros:** Single code path, no native service files.

**Cons:** Auto-start launches the full UI, not just the daemon. User sees the window on login. No daemon-only background mode.

### Option C — Document as manual setup
Note the gap in the README with platform-specific manual instructions. Revisit when actively targeting Windows/Linux.

## Decision

Deferred — revisit when Windows or Linux support is actively needed.

Captured: 2026-05-10. See CLAUDE.md platform inventory for full context.
