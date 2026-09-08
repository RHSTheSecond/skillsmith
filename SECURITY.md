# Security & privacy

Skillsmith installs scripts that modify your `~/.claude/CLAUDE.md` and a hook that
runs at every session start, plus a skill that reads your session transcripts.
Here's what that actually means.

## Threat model

**What it reads.** `~/.claude/skills/`, `~/.claude/commands/`, `~/.claude/CLAUDE.md`,
your session transcripts under `~/.claude/projects/`, and — if you create one — the
agent registry at `~/.claude/skillsmith/agents.json`.

**What it writes.** The managed index block inside `CLAUDE.md` (never anything
outside the markers), backups under `~/.claude/backups/`, small state files
(`.skillsmith-last-sync`, `.skillsmith-cadence`, `.skillsmith-bin`), the drift log,
the agent registry when you add a row, and short-lived `0600` temp files: the mining
corpus and the `--plan` manifest.

**What reaches the model.** Everything the skill analyzes in a session: your skill
files, your CLAUDE.md, and — during mining — your own past messages. That is the same
exposure as the sessions those messages came from. Nothing goes to any *additional*
third party; the helper scripts make zero network calls. Verify:
`grep -rE 'http|urllib|requests|socket|curl' bin/`. The one exception is a
`command`-type registry signal you wrote and explicitly permitted with
`--allow-exec`: that runs a program you named, which can do anything you can.

**What stays local.** The corpus, the manifest, the registry, the backups, the logs.
Nothing is uploaded, and there is no telemetry.

**Retention.** The corpus and the `--plan` manifest are `0600` temp files owned by
the caller — the skill deletes them via a cleanup trap, and the SessionStart hook GCs
both, older than two hours, as a backstop. `CLAUDE.md` backups keep the newest 20
(`0600`, in a `0700` directory), and so do the overflow diff files under the same
directory — those can contain your entire CLAUDE.md, so they are pruned on the same
schedule. The drift log truncates at 128 KB. The registry is durable by design — it is
a record of approvals, so delete rows yourself when an agent is retired.

**`--plan` output is data.** The pre-mining privacy report lists your project names
and message counts. That is often the most sensitive thing on the screen; treat
pasting it anywhere as disclosure. `--plan` writes no corpus and shows nothing to a
model — but to count your messages it does parse them locally, so read it as "nothing
leaves this machine and nothing is retained," not as "nothing was read."

**Signal commands are executable content.** A `command`-type row in the agent
registry names a program `skillsmith-agents` will run. Three things bound it: the
command is an **argv list, never a shell string** (a shell string is refused as an
invalid row, and no shell is involved, so a pipeline or `$(…)` cannot hide in the
file), it runs **only with an explicit `--allow-exec`**, and each command is
**printed before it runs**. None of that changes the underlying fact: anyone who can
write your registry chooses which program that flag executes, exactly as they would
by writing your shell profile. Prefer `file` signals, which never execute anything.

**Mining is opt-in and scoped.** `skillsmith-extract` defaults to the current project;
`--scope all` (a broader exposure) must be chosen explicitly, and `--plan` shows you
the exact set first. If your transcripts contain material that must never transit an
LLM API, don't run the mining stage on them.

## What's enforced by code vs. by prompt

See the "What's code, what's prompt" table in the README for the full split. The part
that matters for trust:

- **Code** enforces file safety (marker validation, backups, atomic writes,
  byte-verify, dry-run-by-default, `--expected-sha256` binding), mining scope and
  cleanup, plan-to-extraction pinning, agent health verdicts, and registry schema.
- **Prompt** enforces every judgment: which patterns become skills, which rung a
  candidate belongs on, approval wording, taint review, chain offers — **and the
  governor itself.** "Humans always promote; the loop only proposes" is an
  instruction to Claude, not a technical control. The real enforcement layer for
  anything an agent could do to your machine is your Claude Code permission
  settings. Configure those as if the governor could fail, because it is prose.

## Reporting a vulnerability

Email the maintainer (see the GitHub profile) rather than opening a public issue.
**Never paste transcript excerpts, CLAUDE.md contents, `--plan` output, or webhook
URLs into a public issue** — those are exactly the sensitive artifacts this tool
handles.

## Uninstall

- **Plugin:** `/plugin uninstall skillsmith`
- **Manual:** `rm -rf ~/.claude/skills/skillsmith ~/.claude/bin/skillsmith-*` and remove
  the SessionStart hook from `~/.claude/settings.json`. Then the state and the
  artifacts, which are the part worth being explicit about:

  ```bash
  rm -rf ~/.claude/.skillsmith-* ~/.claude/skillsmith   # pointer, stamps, cadence, registry
  rm -f  ~/.claude/skillsmith-drift.log                 # note: no leading dot
  rm -f  ~/.claude/backups/CLAUDE.md.* \
         ~/.claude/backups/skillsmith-diff-*.diff       # up to 20 full copies of CLAUDE.md
  ```

  (Substitute `$CLAUDE_CONFIG_DIR` for `~/.claude` if you relocate it.) Your CLAUDE.md
  keeps its managed block; delete the `<!-- skillsmith:index:begin/end -->` section by
  hand if you want it gone.

Supported version: latest release only.
