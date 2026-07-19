# Changelog

## v1.0.1 — 2026-07-18

Fast-follow hardening from a post-release dual-reviewer CAP (Codex gpt-5.5 + an
independent Claude adversary) on the v1.0.0 plugin packaging.

- **Helper-script resolution is now code, not prose** (both reviewers, independently):
  `skillsmith-drift-check` publishes its own bin directory to `~/.claude/.skillsmith-bin`
  on every run — whichever copy actually executes (manual `~/.claude/bin` or plugin
  cache) wins, surviving updates, mode switches, and relocated configs. SKILL.md
  resolves `$SMITH_BIN` through the pointer and uses it in every fenced command; no
  hardcoded `~/.claude/bin/skillsmith-*` remains in the skill body (CI-linted).
- Removed Stage C's legacy "script missing → inline jq fallback" — it contradicted the
  resolution preamble's STOP rule and could silently degrade the code-enforced mining
  invariants (0600 corpus, exclusions, sanity floor) to prose (Claude reviewer).
- **Single version authority:** dropped `version` from the marketplace entry —
  `plugin.json` wins per Claude Code docs, and a mismatched bump silently stops updates
  for installed users (Claude reviewer, docs-verified).
- **CI** (new `.github/workflows/ci.yml`): `claude plugin validate --strict` on both
  manifests, version-lockstep + SKILL.md hardcoded-path lint, and a full smoke install
  in an isolated config dir — marketplace add → install → all three scripts run from
  the plugin cache → bin pointer published (both reviewers flagged the missing
  regression harness).
- LOCAL.md: documented durable location `~/.claude/skillsmith/LOCAL.md` for plugin
  installs — the cache is replaced on update (Codex reviewer).
- README: plugin wording no longer implies `plugin.json` declares components (standard
  paths are auto-discovered); added a manual→plugin migration note (stale-script
  shadowing + duplicate hook); roadmap updated (extract shipped in v1.0.0).

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
