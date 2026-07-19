# Skillsmith

**Forge new Claude Code skills from your own usage. Keep the ones you have sharp.**

Skillsmith is a [Claude Code](https://claude.com/claude-code) skill that maintains your *skill ecosystem*: it audits your skill library, keeps your CLAUDE.md aliases in sync, mines your own session transcripts for repeated workflows that deserve to become skills, tunes descriptions so skills self-invoke at the right moments, and audits which skills actually fire (from your transcripts — prose-driven; see *Honest limits*).

**Data flow, stated plainly:** the helper scripts run entirely locally. The skill itself runs inside Claude Code, so anything it analyzes — including transcript excerpts during session mining — is processed by Claude, the same exposure as the sessions themselves. Nothing goes to any *additional* third party, and the mining stage is opt-in, scoped, and cleans up its intermediate file. If your transcripts contain material that must never transit an LLM API, don't run the mining stage on them.

## The architecture it maintains: skill-backed shortcuts

Two facts about Claude Code shape everything here:

1. **CLAUDE.md is always loaded** — every session, every turn. Great for *recognition*, terrible for detail (a big file dilutes everything in it).
2. **Skills load only when invoked** — full fidelity, but only if the model notices it should invoke one.

Skillsmith maintains the split that exploits both: procedures live in skill files; CLAUDE.md keeps a compact, machine-managed index of one-line aliases whose only instruction is "invoke the skill." The bare word gets recognized (always-loaded prose); the procedure runs exactly as written (loaded skill). A sync mechanism keeps the two from drifting.

## The six stages

| Stage | What | When |
|---|---|---|
| **A — Audit** | Format, frontmatter, description quality, stale references, overlap, token weight, registration, CLAUDE.md's own weight | every run |
| **B — Alias sync** | Regenerates the managed index block in CLAUDE.md — via a validated script, shown as a diff, applied only on your explicit yes | every run |
| **C — Session mining** | Extracts *your* messages from local transcripts (bounded, taint-disciplined) and finds repeated requests, workflows, corrections, and unregistered terse phrases that should become skills, rules, or plain scripts | ask-first |
| **D — Trigger tuning** | Rewrites weak `description:` frontmatter — the surface that drives skill self-invocation | ask-first |
| **E — Chain audit** | Finds outcome→skill links ("close-out gate discovers X → migration skill handles X") and encodes them as *offers*, never automatic invocations | with A |
| **F — Usage audit** | Which skills actually fired, which are dead, which plausibly should have fired but didn't | with C |

## Design principles (hardened by adversarial review)

- **Code for invariants, prose for judgment.** The CLAUDE.md block splice is a deterministic script (`bin/skillsmith-sync`): marker validation, automatic backup, byte-verified writes, refuses corrupted files. Drift detection is a SessionStart hook (`bin/skillsmith-drift-check`), not a rule the model must remember. Only judgment (pattern recognition, wording, classification) stays with the LLM.
- **Suggest-then-approve, no exceptions.** Every mutation — including the managed block — shows you the exact change first.
- **Taint discipline.** Transcripts contain text you *pasted* from outside, not just text you wrote. Mined candidates carry verbatim source quotes and provenance; anything with side-effecting verbs requires reviewing the raw evidence before approval.
- **Chains are offers.** A skill may say "this is what X handles — run it?" It never runs X for you.
- **Fail loud.** Empty extraction aborts rather than reporting "no findings." Marker anomalies refuse rather than guess. A skill that fails to load is reported, never improvised from memory.

## What's code, what's prompt

Skillsmith's honesty rests on being clear about which guarantees are enforced by the scripts (reliable) and which are the skill's instructions to Claude (best-effort). Trust the first column; treat the second as judgment that can vary.

| Property | Enforced by |
|---|---|
| No unapproved CLAUDE.md write | **code** — `skillsmith-sync` dry-runs unless `--apply` |
| Marker validation / refuse-on-anomaly | **code** — `skillsmith-sync` |
| Backups + atomic + byte-verified writes | **code** — `skillsmith-sync` |
| Drift detection at session start | **code** — `skillsmith-drift-check` hook |
| Mining scope + exclusions + corpus cleanup | **code** — `skillsmith-extract` (0600 temp, caller's cleanup trap) |
| *Which* patterns become skills | prompt — the skill's judgment |
| Approval wording, taint review, chain offers | prompt — the skill's instructions |
| Usage audit ("which skills fired") | prompt — reads transcripts, no shipped parser |

## Install

### As a plugin

The repo is its own single-plugin marketplace (`.claude-plugin/marketplace.json`) and
uses Claude Code's standard plugin layout — `skills/` and `hooks/hooks.json` are
auto-discovered; `plugin.json` deliberately declares no component paths — so an install
brings the skill **and** the SessionStart drift hook together, skips the manual
`settings.json` step, and gives you version/update tracking. In Claude Code:

```bash
/plugin marketplace add RHSTheSecond/skillsmith
/plugin install skillsmith@skillsmith
```

Or non-interactively from a shell:

```bash
claude plugin marketplace add RHSTheSecond/skillsmith
claude plugin install skillsmith@skillsmith
```

Plugin skills are namespaced — invoke as **`skillsmith:skillsmith`** (or let it
self-invoke). The drift hook registers automatically with the install — no
`settings.json` edit; confirm with `/hooks` or `claude plugin details skillsmith`.
The hook publishes the running install's `bin/` path to `~/.claude/.skillsmith-bin`,
and the skill resolves the helper scripts through that pointer — the same SKILL.md
works for manual and plugin installs, across updates and mode switches. Install path
verified on Claude Code 2.1.214 (local + GitHub marketplace add → install → skill and
hook loaded); CI re-verifies the manifests and a full smoke install on every push.

**Switching from manual to plugin install:** remove the manual copies so a stale
version can't shadow the plugin's — `rm ~/.claude/bin/skillsmith-*`, delete the
SessionStart hook entry from `~/.claude/settings.json` (the plugin brings its own;
keeping both means duplicate drift lines every session), then start a new session so
the plugin hook rewrites `~/.claude/.skillsmith-bin`.

### Manual install

```bash
git clone https://github.com/RHSTheSecond/skillsmith && cd skillsmith
mkdir -p ~/.claude/skills/skillsmith ~/.claude/bin
cp skills/skillsmith/SKILL.md ~/.claude/skills/skillsmith/
cp bin/skillsmith-* ~/.claude/bin/ && chmod +x ~/.claude/bin/skillsmith-*
```

Then add the drift hook. If you have **no** `~/.claude/settings.json`, this complete file works as-is:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "~/.claude/bin/skillsmith-drift-check || true", "timeout": 10 } ] }
    ]
  }
}
```

If you **already have** a `settings.json`, merge instead of replacing — this preserves your existing hooks:

```bash
jq '.hooks.SessionStart += [{"hooks":[{"type":"command","command":"~/.claude/bin/skillsmith-drift-check || true","timeout":10}]}]' \
  ~/.claude/settings.json > /tmp/s.json && mv /tmp/s.json ~/.claude/settings.json
```

Then run `/hooks` and confirm a User SessionStart command hook appears. Script errors, if any, land in `~/.claude/skillsmith-drift.log`.

### First run

In any Claude Code session: **`skillsmith`**. It initializes the managed index markers in your CLAUDE.md via `skillsmith-sync --init` (shown as a diff, written only on your approval — never a hand-edit), then asks how often to nudge you to run it again (`0` = never). Backups of every write land in `~/.claude/backups/` (newest 20 kept).

**Scope note:** skillsmith manages only your **global** `~/.claude/CLAUDE.md`. Project-level `CLAUDE.md` files are out of scope.

## Personal customization: LOCAL.md

Drop a `LOCAL.md` next to the installed SKILL.md — or, for plugin installs, at `~/.claude/skillsmith/LOCAL.md` (the plugin cache is replaced on update, so a file inside it would be lost) — for machine-specific extensions (extra close-out stamps, notification channels, environment integrations). The skill applies it when present; the distributed skill never assumes it exists. Your quirks stay yours — the core stays shareable.

## Requirements

- Claude Code with skills support (`~/.claude/skills/`)
- `python3` ≥ 3.8 (the sync + extract scripts)
- macOS or Linux

## Honest limits

- Stage F measures *invocation*, not *compliance* — whether a loaded skill's steps were followed is not covered.
- Transcript parsing rides on Claude Code's internal JSONL format, which is undocumented and can change; the extraction aborts loudly on schema drift rather than reporting a false clean bill.
- Bare-word alias recognition from CLAUDE.md is probabilistic, not guaranteed — which is why Stage A audits CLAUDE.md's own weight and Stage F looks for misses.
- The alias layer exists because skill self-invocation via `description:` matching is unreliable *today*. That's an empirical claim about the harness, and the harness is actively improving — Stage F is the instrument for re-checking it. If description-matching gets good enough, the index block and sync script become happily deletable.

## Roadmap

- **v1.1 "the ladder"** — grow Stage C from "should this be a skill?" into a promotion ladder (vocabulary → skill → script → agentic workflow → persistent agent): cadence detection from the extractor's timestamps, a 4-criterion promotion test, and agent-tier retirement auditing. Humans always promote; the loop only proposes.

---

Built at Happy Labs. Adversarially reviewed (dual-reviewer CAP: GPT-5.5 + independent Claude) before release; the design principles above are what survived.
