# Security & privacy

Skillsmith installs scripts that modify your `~/.claude/CLAUDE.md` and a hook that
runs at every session start, plus a skill that reads your session transcripts.
Here's what that actually means.

## Data flow

- **The helper scripts make zero network calls.** `skillsmith-sync`,
  `skillsmith-drift-check`, and `skillsmith-extract` read and write only under your
  home directory. You can verify: `grep -rE 'http|urllib|requests|socket|curl' bin/`.
- **The skill runs inside Claude Code**, so anything it analyzes — including transcript
  excerpts during the mining stage — is processed by Claude, the same exposure as the
  sessions themselves. Nothing goes to any *additional* third party.
- **Mining is opt-in and scoped.** `skillsmith-extract` defaults to the current project;
  `--scope all` (a broader exposure) must be chosen explicitly. The extracted corpus is
  a `0600` temp file the caller deletes via a cleanup trap; the drift hook also GCs stale
  corpses. If your transcripts contain material that must never transit an LLM API, don't
  run the mining stage on them.

## Reporting a vulnerability

Email the maintainer (see the GitHub profile) rather than opening a public issue.
**Never paste transcript excerpts, CLAUDE.md contents, or webhook URLs into a public
issue** — those are exactly the sensitive artifacts this tool handles.

## What's enforced by code vs. by prompt

See the "What's code, what's prompt" table in the README. The short version: file
safety (marker validation, backups, atomic writes, byte-verify, dry-run-by-default) is
enforced by the scripts. Judgment steps (which patterns become skills, approval wording)
are the skill's instructions to Claude. Trust the code guarantees; treat the prompt
guarantees as best-effort.

## Uninstall

- **Plugin:** `/plugin uninstall skillsmith`
- **Manual:** `rm -rf ~/.claude/skills/skillsmith ~/.claude/bin/skillsmith-*`, remove the
  SessionStart hook from `~/.claude/settings.json`, and optionally
  `rm ~/.claude/.skillsmith-*`. Your CLAUDE.md keeps its managed block; delete the
  `<!-- skillsmith:index:begin/end -->` section by hand if you want it gone.

Supported version: latest release only.
