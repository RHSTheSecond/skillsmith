# Skillsmith

**Forge new Claude Code skills from your own usage. Keep the ones you have sharp.**

Skillsmith is a [Claude Code](https://claude.com/claude-code) skill that maintains your *skill ecosystem*: it audits your skill library, keeps your CLAUDE.md aliases in sync, mines your own session transcripts for repeated workflows that deserve to become skills, tunes descriptions so skills self-invoke at the right moments, and measures which skills actually fire.

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

## Install

```bash
# 1. The skill
mkdir -p ~/.claude/skills/skillsmith
cp skill/SKILL.md ~/.claude/skills/skillsmith/

# 2. The scripts
mkdir -p ~/.claude/bin
cp bin/skillsmith-sync bin/skillsmith-drift-check ~/.claude/bin/
chmod +x ~/.claude/bin/skillsmith-sync ~/.claude/bin/skillsmith-drift-check

# 3. (Recommended) the drift hook — see below
```

**The drift hook.** If you have no `~/.claude/settings.json` yet, this complete file works as-is:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/bin/skillsmith-drift-check || true",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

If you already have a `settings.json`: merge — add the `"SessionStart"` array into your existing `"hooks"` object (or the whole `"hooks"` key if you have none), don't replace the file. Validate afterwards: `jq . ~/.claude/settings.json`. Script errors, if any, land in `~/.claude/skillsmith-drift.log`.

Then, in any Claude Code session: **`skillsmith`**. The first run asks how often you want to be nudged to run it again (the SessionStart hook delivers the nudge); without the hook, a calendar reminder works fine.

First run: skillsmith initializes the managed index markers in your CLAUDE.md via `skillsmith-sync --init` (shown as a diff, applied on your approval — the same validated path as every later write; it never hand-edits your file). After that the script owns everything between the markers. Backups of every write land in `~/.claude/backups/` (newest 20 kept).

## Personal customization: LOCAL.md

Drop a `LOCAL.md` next to the installed SKILL.md for machine-specific extensions (extra close-out stamps, notification channels, environment integrations). The skill applies it when present; the distributed skill never assumes it exists. Your quirks stay yours — the core stays shareable.

## Requirements

- Claude Code with skills support (`~/.claude/skills/`)
- `python3` (the sync script); `jq` helps transcript extraction (without it, the skill writes a small python extractor at runtime — workable, but a different reliability class)
- macOS or Linux

## Honest limits

- Stage F measures *invocation*, not *compliance* — whether a loaded skill's steps were followed is not covered.
- Transcript parsing rides on Claude Code's internal JSONL format, which is undocumented and can change; the extraction aborts loudly on schema drift rather than reporting a false clean bill.
- Bare-word alias recognition from CLAUDE.md is probabilistic, not guaranteed — which is why Stage A audits CLAUDE.md's own weight and Stage F looks for misses.
- The alias layer exists because skill self-invocation via `description:` matching is unreliable *today*. That's an empirical claim about the harness, and the harness is actively improving — Stage F is the instrument for re-checking it. If description-matching gets good enough, the index block and sync script become happily deletable.

## Roadmap

- `skillsmith-extract` — move Stage C's transcript extraction (find + filters + exclusions + sanity floor + temp-file lifecycle) from LLM-executed instructions into a tested script, applying "code for invariants" one layer further.

---

Built at Happy Labs. Adversarially reviewed (dual-reviewer CAP: GPT-5.5 + independent Claude) before release; the design principles above are what survived.
