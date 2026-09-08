# Changelog

## v1.1.0 — 2026-09-07

"The ladder" — Stage C stops asking only *"should this be a skill?"* and starts
asking *which rung* repeated work belongs on, up to and including work that should
run without anyone asking. Humans always promote; the loop only proposes.

- **The ladder (5 rungs, one test each).** vocabulary → skill → script → workflow →
  agent, each with its own promotion test rather than one test pretending to cover
  all five (the old single 4-criterion test literally blocked the skill rung and
  gated nothing at the agent rung). The agent rung carries a worked
  **bounded-cost-of-being-wrong** clause: undeletable or irreversible output passes
  only if the content class is low-stakes AND the template was human-approved AND a
  kill switch exists. Canonical worked examples ship in `docs/promotion-tests.md`.
- **Agent registry — `skillsmith-agents` (new script).** Session transcripts cannot
  see a machine you are not typing on, so the agent tier is audited from
  `~/.claude/skillsmith/agents.json` instead: one validated row per promoted agent
  (owner, trigger, side-effect class, output surface, health signal, evidence class,
  approver, review-by). `--audit` returns **healthy / dead / unmeasurable** — three
  verdicts, never two, because a signal that cannot be read means the agent is *not
  known to be working*. `--running-from <listing>` flags anything your scheduler runs
  that has no row: an unapproved promotion, made visible. Command-type signals are
  shell commands from a config file and execute only with `--allow-exec`.
- **`skillsmith-extract --plan` — privacy report with manifest pinning.** Prints what
  mining *would* read (sessions, message count, projects, exclusions applied) and
  extracts nothing. The real run consumes the manifest and **refuses (exit 5) if the
  candidate set changed** — a session added, removed, or grown after approval all
  refuse alike. You cannot approve one set and mine another.
- **Cadence is asked, not inferred.** A 14-day corpus yields at most two observations
  of a weekly pattern and topic bursts read identically to a rhythm, so Stage C asks
  the operator outright. Deterministic interval statistics stay on the v1.2 roadmap,
  where they have to beat the question to ship.
- **Extractor flattens tabs**, not just newlines — the corpus is tab-delimited, so a
  raw tab in a pasted message used to shift every later field.
- **Close-out scorecard** in the final report: counts, findings, agent verdicts,
  measured sizes, and the single highest-impact recommendation. The scorecard is
  prose — the skill's instruction is that its "files modified" line must quote what
  the scripts actually printed (a template line eventually lies on the one run that
  mattered) and that sizes are measured bytes/lines rather than eyeballed token
  estimates. Discipline, not enforcement; this project does not get to blur that.
- **Stage A audits `LOCAL.md`** for references to stages that no longer exist —
  personal overlays drift silently and invisibly.
- **SECURITY.md is now a threat model:** what is read, what is written, what reaches
  the model, what stays local, retention per artifact, `--plan` output as data,
  signal commands as executable content — and, plainly, that the governor is
  procedural and your harness permission settings are the real enforcement layer.
- 46 new tests (63 total) covering the checks that must be able to fail: plan/extract
  count equality, refusal on a mutated candidate set, tab flattening, the three agent
  verdicts, unregistered-agent detection, schema refusals, and opt-in exec.

**Caught by the pre-release adversarial pass (two independent reviewers), fixed
before tagging.** Both reviewers went after the honesty table first, as instructed,
and it did not survive intact:

- The manifest digest hashed session ids and message *counts*, so a transcript
  rewritten in place with the same number of messages would have passed the pin. It
  now hashes the **corpus text itself**, keyed by project+session — a session id that
  exists in two projects is no longer collapsed into one entry either.
- Docs claimed mining was "previewed before anything is read." `--plan` writes no
  corpus and shows nothing to a model, but counting your messages does parse them
  locally. The claim is now stated the way the code behaves — the whole point of the
  code-vs-prompt table is that it is exact.
- Command signals are now **argv lists, not shell strings**: a shell string is refused
  as an invalid row, there is no shell to interpret a pipeline hidden in a config
  file, and each command is printed before it runs. `--allow-exec` still gates *when*
  they run; nothing pretends it gates *which* program a writable registry names.
- Unreadable transcripts and unparseable lines are no longer swallowed: an unreadable
  candidate fails loudly (a partial corpus must never look complete), and unparseable
  line counts are reported in `--plan` and the run summary.
- Registry writes use a unique temp file under an exclusive lock — two overlapping
  `--add` runs could previously drop a row or collide on a shared `.tmp` path.
- `max_age_hours` is now required and must be greater than zero: `--add` previously
  wrote `null` and exited 0, producing an agent unmeasurable by construction, while a
  hand-edited `"26h"` crashed the whole audit and took every other verdict with it.
- **The sanity floor could not trip on the failure it was written for.** It divided by
  the sessions that *produced* messages, so total format drift — every session parsing
  to nothing — made the divisor zero and passed silently with an empty corpus and exit
  0. It now divides by candidate transcripts, and "nothing parsed at all" says so.
- **Two guarantees were opt-in, which is not a guarantee.** `--apply` accepted a write
  with no `--expected-sha256`, and extraction mined happily with no manifest — both
  the code-column claims. Now `--apply` requires the hash and extraction requires a
  manifest, each with an explicit, visible opt-out (`--no-pin`, `--unpinned`).
- **Pinning by message count made the flow unusable and the claim too strong.** Live
  transcripts grow while a human reads the report, so every pinned run on a busy
  machine refused. The manifest now records each transcript's length and content hash,
  and the run reads exactly those bytes: growth is outside the approved set rather
  than an error, while an added, removed, truncated, or rewritten session refuses.
  The run also re-prints the scope and counts, because a checksum cannot notice that
  someone edited the thing being checksummed.
- **`CLAUDE_CONFIG_DIR` was ignored by all four scripts.** On a relocated config tree
  every guarantee held perfectly — on files the harness never reads: Stage A audited
  an empty library, `--init` created a CLAUDE.md nobody loads, mining read the wrong
  transcripts. All four now honor it, and CI proves the writes land there.
- **The skillsmith-session exclusion missed plugin installs.** It matched the skill
  name exactly, but plugin skills invoke as `skillsmith:skillsmith` — so mining
  re-read its own sessions and manufactured frequency evidence for the candidates it
  had just discussed.
- **`--scope current` could mine other projects.** A substring fallback matched every
  project slug containing this one's while the report still said "this project only";
  it is now an exact match that fails with the candidate slugs listed.
- Harness-appended blocks (system reminders) were joined into user text before
  filtering, polluting messages and pushing short trigger words past the length cap —
  exactly the terse phrases Stage C exists to find. Filtering is now per block.
- `--running-from` no longer guesses its input format (sniffing turned a crontab's
  `5 6 * * *` into an agent named "5"), reports every line it did not understand
  instead of dropping it, and ignores distribution-shipped units by default so one
  real finding is not buried under a dozen vendor timers.
- `save()` chmodded the registry's parent directory to 0700 unconditionally —
  `--registry /tmp/agents.json` would have locked `/tmp`. It now tightens only a
  directory it created inside the config tree.
- The SessionStart hook GCs stale `--plan` manifests (they hold every project name),
  and overflow diffs — which can contain the whole CLAUDE.md — are pruned with the
  backups instead of accumulating forever. Both are now in SECURITY.md's retention
  section, along with an uninstall that actually removes them.
- CI assertions that could not fail were replaced: version lockstep now compares what
  each script's `--version` prints, and the hook check reads the shipped manifest
  rather than a pointer file any invocation would have written.

## v1.0.2 — 2026-07-18

Fixes from an independent third-party code assessment (received hours after
v1.0.1; its headline finding was real and is the reason this release exists).

- **CRITICAL compat fix in `skillsmith-sync`:** the script called
  `Path.read_text(newline="")` / `Path.write_text(newline="")` — parameters that
  only exist since Python 3.13 / 3.10. On any older interpreter (including
  Ubuntu 24.04's default 3.12) the centerpiece safety script died with a
  TypeError on its very first read. It failed *safe* (exit 3, CLAUDE.md
  untouched) but was completely nonfunctional despite a documented ≥3.8
  requirement. Reproduced on 3.12, fixed with `open()`-based IO, and now proven
  by the test suite on 3.8/3.12/latest in CI.
- **Approved diff = applied diff:** dry-run prints `source sha256:`; `--apply
  --expected-sha256 <hash>` refuses (exit 3, nothing written) if CLAUDE.md
  changed between the reviewed dry run and the write. Closes the
  time-of-check/time-of-use gap in the approval flow; SKILL.md Stage B now
  always passes the hash.
- **Test suite (new `tests/test_sync.py`, 17 cases):** marker anomalies,
  empty/marker-containing content, dry-run purity, sha binding, CRLF byte
  fidelity, non-UTF-8 refusal, symlink preservation, backup modes + retention,
  init. CI runs it on a version×OS matrix (3.8/ubuntu-22.04, 3.12 + latest
  /ubuntu, latest/macOS) with the interpreter under test.
- Backup hardening: backup dir `0700`, every backup `0600` (CLAUDE.md can hold
  sensitive operational context; backups no longer inherit default umask).
- Drift-hook log capped at 128 KB (truncate-on-start) — a persistent error can
  no longer grow `skillsmith-drift.log` without bound.
- Cadence file is read strictly: a corrupted value now warns loudly and
  disables nudges instead of being digit-squeezed into a different number
  (`"14garbage30"` is not a cadence of 1430).

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
