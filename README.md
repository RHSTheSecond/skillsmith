# Skillsmith

[![ci](https://github.com/RHSTheSecond/skillsmith/actions/workflows/ci.yml/badge.svg)](https://github.com/RHSTheSecond/skillsmith/actions/workflows/ci.yml)

**Forge new Claude Code skills from your own usage. Keep the ones you have sharp.**

*The maintenance layer for AI coding-agent workflows — evidence-backed audits, approval-gated changes.*

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
| **C — Session mining + the ladder** | Extracts *your* messages from local transcripts (bounded, taint-disciplined, and previewed by `--plan` — you see the exact set before any corpus is built) and finds repeated work — then classifies each candidate onto the promotion ladder: vocabulary → skill → script → workflow → agent | ask-first |
| **D — Trigger tuning** | Rewrites weak `description:` frontmatter — the surface that drives skill self-invocation | ask-first |
| **E — Chain audit** | Finds outcome→skill links ("close-out gate discovers X → migration skill handles X") and encodes them as *offers*, never automatic invocations | with A |
| **F — Usage audit** | Which skills actually fired, which are dead, which plausibly should have fired but didn't — plus the agent tier, audited from the registry: healthy / dead / **unmeasurable** | with C |

## The ladder: from a phrase you repeat to software that runs without you

Stage C does not only ask "should this be a skill?" It asks **which rung** a piece of
repeated work belongs on, and applies that rung's own test:

| Rung | What it is | Promotion test |
|---|---|---|
| **vocabulary / rule** | a behavior or interpretation, not a procedure | corrected toward more than once |
| **skill** | a procedure needing judgment at each step | recurs on request across ≥3 sessions; stable enough to write down |
| **script** | fixed steps, no judgment | zero mid-loop judgment · nameable inputs/outputs · failure is loud |
| **workflow** | multi-step, orchestrated, human-triggered | every step's outcome verifiable · a human still starts it |
| **agent** | runs on a clock or trigger, unattended | recurs on a trigger · no mid-loop judgment · verifiable outcome · **bounded cost of being wrong** |

Rungs are a taxonomy, not a forced march — work can be proposed directly at any rung,
and each *approval* applies that rung's test once. Worked examples, including the
boundary case that only passes through the bounded-cost clause, are in
[`docs/promotion-tests.md`](docs/promotion-tests.md).

**Humans always promote; the loop only proposes.** That is a procedural guarantee —
these are instructions to Claude, backed by your harness permission settings, not
something the scripts enforce. The one thing code *can* do is make promotions visible.

### The agent registry

An agent that runs on some other machine is invisible to session transcripts, so the
top rung is audited from a file instead: `~/.claude/skillsmith/agents.json`, one row per
promoted agent — owner, trigger, side-effect class, output surface, the **health signal**
to check, the **evidence class** that signal actually measures (`delivered` /
`acknowledged` / `acted_on`), who approved it, and when the approval must be re-justified.

```bash
skillsmith-agents --init          # an empty registry is a valid state; a missing one is not
skillsmith-agents --add  …        # the promotion ceremony writes a validated row
skillsmith-agents --audit --running-from <(systemctl list-timers --all --no-legend)
```

Distribution-shipped timers (`apt-daily`, `logrotate`, `systemd-*`, `com.apple.*`) are
ignored by default — a check that flags a dozen vendor units on first run is a check
you stop running. `--no-vendor-ignore` includes them.

The audit returns three verdicts, never two: **healthy**, **dead**, and
**unmeasurable** — a signal that cannot be read means the agent is *not known to be
working*, and saying so out loud is the point. Command-type signals are **argv lists,
not shell strings** (there is no shell, so no pipeline or `$(…)` can hide in a registry
someone else can write), they execute only with an explicit `--allow-exec`, and each one
is printed before it runs — but treat the registry like your shell profile: whoever can
write it chooses what that flag runs. Anything your scheduler is running that has no
registry row is flagged as an unapproved promotion. `--running-from` reads systemd-style
listings or a plain one-name-per-line list, and says how many lines it ignored.

## Design principles (hardened by adversarial review)

- **Code for invariants, prose for judgment.** The CLAUDE.md block splice is a deterministic script (`bin/skillsmith-sync`): marker validation, automatic backup, byte-verified writes, refuses corrupted files. Drift detection is a SessionStart hook (`bin/skillsmith-drift-check`), not a rule the model must remember. Only judgment (pattern recognition, wording, classification) stays with the LLM.
- **Suggest-then-approve, no exceptions.** Every mutation — including the managed block — shows you the exact change first.
- **Taint discipline.** Transcripts contain text you *pasted* from outside, not just text you wrote. Mined candidates carry verbatim source quotes and provenance; anything with side-effecting verbs requires reviewing the raw evidence before approval.
- **Chains are offers.** A skill may say "this is what X handles — run it?" It never runs X for you.
- **Fail loud.** Extraction that parses nothing aborts rather than reporting "no findings" — the floor divides by candidate transcripts, so total format drift trips it rather than dividing by zero. Marker anomalies refuse rather than guess. A skill that fails to load is reported, never improvised from memory.
- **Safe by default, opt out loudly.** Writing CLAUDE.md needs `--apply`; `--apply` needs the reviewed-bytes hash; mining needs an approved manifest. Each has an explicit escape hatch (`--no-pin`, `--unpinned`) that shows up in the transcript, because a guarantee only reachable by remembering a flag is a prose guarantee wearing a code costume.

## What's code, what's prompt

Skillsmith's honesty rests on being clear about which guarantees are enforced by the scripts (reliable) and which are the skill's instructions to Claude (best-effort). Trust the first column; treat the second as judgment that can vary.

| Property | Enforced by |
|---|---|
| No unapproved CLAUDE.md write | **code** — `skillsmith-sync` dry-runs unless `--apply` |
| Approved diff = applied diff | **code** — `--apply` REFUSES without `--expected-sha256` (or an explicit `--no-pin`), so the write is bound to the bytes you reviewed |
| Marker validation / refuse-on-anomaly | **code** — `skillsmith-sync` |
| Backups + atomic + byte-verified writes | **code** — `skillsmith-sync` |
| Drift detection at session start | **code** — `skillsmith-drift-check` hook |
| Mining scope + exclusions | **code** — `skillsmith-extract` (exact project match, 0600 temp files) |
| Corpus cleanup | **mixed** — the corpus is the caller's to delete (prose: a `trap` in the skill); the session-start hook GCs stale corpora and manifests as a backstop |
| Fail loud on transcript drift | **code** — the sanity floor divides by candidate transcripts, so "everything parsed to nothing" aborts (exit 4) instead of reporting no candidates |
| Approved mining set = mined set | **code** — extraction REFUSES without a `--plan` manifest (or an explicit `--unpinned`); it reads exactly the approved bytes and refuses (exit 5) on a session added, removed, truncated, or rewritten. Against accidental drift, not against someone editing the manifest — it is a checksum, and the run re-prints the scope so you can compare |
| Agent health verdicts (healthy/dead/unmeasurable) | **code** — `skillsmith-agents --audit` evaluates the declared signal |
| Registry rows are schema-valid | **code** — `--add` refuses incomplete rows; an invalid row audits as a finding |
| Unapproved promotions are visible | **code** — running agents absent from the registry are flagged |
| Signal commands are argv, never a shell string | **code** — a shell string is refused as an invalid row; there is no shell to interpret one |
| Signal commands don't run unless you say so | **code** — command signals need `--allow-exec`, and each is printed before it runs. This gates *when* a program runs, not *which*: whoever can write your registry chooses the program |
| *Which* patterns become skills | prompt — the skill's judgment |
| Which rung a candidate belongs on | prompt — the skill applies the per-rung test |
| "Humans always promote" (nothing self-promotes) | prompt — the governor is procedural; your harness permissions are the real enforcement layer |
| A row is actually written when an agent is promoted | prompt — the ceremony is an instruction, not a hook |
| Cadence ("this recurs weekly") | prompt — **asked of you**, never inferred from the corpus |
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
- `python3` ≥ 3.8 (the sync, extract, and registry scripts; CI runs the test suite on 3.8, 3.12, and latest, Linux + macOS)
- `CLAUDE_CONFIG_DIR` is honored: if you run Claude Code with a relocated config tree, skillsmith reads and writes *that* tree
- macOS or Linux

## Honest limits

- Stage F measures *invocation*, not *compliance* — whether a loaded skill's steps were followed is not covered.
- Transcript parsing rides on Claude Code's internal JSONL format, which is undocumented and can change; the extraction aborts loudly on schema drift rather than reporting a false clean bill.
- Bare-word alias recognition from CLAUDE.md is probabilistic, not guaranteed — which is why Stage A audits CLAUDE.md's own weight and Stage F looks for misses.
- The agent tier audits what the registry *declares*, not the machine — a health signal is a claim about where evidence lands, and a row that is never written is an agent skillsmith cannot see. `--running-from` narrows that gap only as far as the listing you hand it.
- `--plan` builds no corpus and shows nothing to a model, but counting your messages means it parses them locally, on your machine — "nothing is read" would be the wrong claim, and it isn't made.
- Cadence is asked, not measured: a two-week corpus cannot distinguish a weekly rhythm from a busy fortnight, so v1.1 does not pretend to.
- The alias layer exists because skill self-invocation via `description:` matching is unreliable *today*. That's an empirical claim about the harness, and the harness is actively improving — Stage F is the instrument for re-checking it. If description-matching gets good enough, the index block and sync script become happily deletable.

## Roadmap

- **v1.2** — a `skillsmith` CLI (`audit` / `collect` / `report`) over collectors that already emit structured data; a stable JSON proposal format to go with it (schema + validator + retention rule — it was deliberately held back from v1.1 rather than shipped schema-less and consumer-less); sanitized shareable reports; and, if it earns its way in, deterministic cadence detection — an interval-stats helper with a burst negative control, replacing the v1.1 "just ask the operator" answer only if it can beat it.

---

Built at Happy Labs. Adversarially reviewed (dual-reviewer CAP: GPT-5.5 + independent Claude) before release; the design principles above are what survived.
