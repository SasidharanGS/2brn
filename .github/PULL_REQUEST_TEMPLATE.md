## What & why

<!-- What does this change do, and why? Link any related issue, e.g. "Closes #123". -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Docs
- [ ] CI / tooling

## Checklist

- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, …)
- [ ] Daemon: `uv run ruff check src/` and `uv run pyright src/brn_daemon` pass
- [ ] Daemon: `uv run --extra dev pytest tests/` passes (coverage ≥ 60%)
- [ ] UI: `pnpm exec tsc --noEmit` passes
- [ ] Added/updated tests where it makes sense
- [ ] Updated docs (README / `docs/`) where behaviour changed
- [ ] Change is additive and degrades gracefully (no data loss if a provider/integration is offline)

## Notes for reviewers

<!-- Anything tricky, screenshots, or follow-ups. -->
