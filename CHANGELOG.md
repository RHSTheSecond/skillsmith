# Changelog

## v1.0.0 — 2026-07-17

First tagged release. Hardened through three rounds of dual-reviewer adversarial
review (Codex gpt-5.5 + an independent Claude) covering architecture, release, and
public-readiness.

- `skillsmith-sync`: **dry-run by default; writing requires `--apply`** (no unapproved
  CLAUDE.md write is possible from a bare call). Atomic writes via temp-file + replace
  on the resolved target (symlink-safe), true byte round-trip verification (preserves
  CRLF), marker-anomaly refusal, automatic rotated backups, `--init` for first-run
  markers (sets the drift baseline), `--allow-empty` guard, overflow diffs written
  `0600` under `~/.claude/backups/` (never world-readable `/tmp`).
- `skillsmith-drift-check`: SessionStart drift warning + opt-in cadence nudge;
  `--set-cadence N` validates input at set time (`0` = never); `find -L` so symlink/stow
  setups aren't silently unprotected; GC of stale mining-corpus files; errors logged.
- `skillsmith-extract` (new): guarded transcript extraction — scope control, current +
  skillsmith-session exclusions, user-text-only, corpus sanity floor, `0600` temp file,
  ISO timestamp per line.
- Packaged as a Claude Code plugin: the repo doubles as its own single-plugin
  marketplace (`.claude-plugin/marketplace.json`), so `/plugin marketplace add
  RHSTheSecond/skillsmith` → `/plugin install skillsmith@skillsmith` works directly.
  Install verified end-to-end on Claude Code 2.1.214 (marketplace add → install →
  skill + SessionStart hook load from the plugin cache; `${CLAUDE_PLUGIN_ROOT}` hook
  path and script exec bits confirmed). Manual cp-install documented as an alternative.
- `--version` on all three scripts.
