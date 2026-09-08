"""Black-box tests for bin/skillsmith-extract.

Same discipline as test_sync.py: the script runs as a subprocess under the SAME
interpreter running the tests, against a frozen fixture $HOME, so a 3.8 CI leg
proves the script on 3.8.

These cover the v1.1 verification checks that must be able to FAIL:
  (1) --plan counts equal what extraction then processes, and a candidate set
      mutated after --plan makes the pinned extraction REFUSE.
  (6) the extractor flattens tabs (the corpus is tab-delimited).
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "bin" / "skillsmith-extract"


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.projects = self.home / ".claude" / "projects"
        self.projects.mkdir(parents=True)
        self.corpora = []
        self.session("-Users-me-proj1", "aaaaaaaa-1111-1111-1111-111111111111",
                     ["hop it", "ctc that", "chat me the tldr", "a\tb\tc"])
        self.session("-Users-me-proj1", "bbbbbbbb-2222-2222-2222-222222222222",
                     ["awd", "flip it", "drop the card"])
        self.session("-Users-me-proj2", "cccccccc-3333-3333-3333-333333333333",
                     ["triage this", "cap it", "hop"])

    def tearDown(self):
        for c in self.corpora:
            Path(c).unlink(missing_ok=True)
        self.tmp.cleanup()

    # -- fixture helpers -------------------------------------------------------

    def session(self, project, sid, messages, extra_events=()):
        d = self.projects / project
        d.mkdir(parents=True, exist_ok=True)
        path = d / (sid + ".jsonl")
        with open(str(path), "w", encoding="utf-8") as f:
            for i, m in enumerate(messages):
                f.write(json.dumps({"type": "user",
                                    "timestamp": "2026-09-%02dT10:00:00Z" % (i + 1),
                                    "message": {"content": m}}) + "\n")
            for ev in extra_events:
                f.write(json.dumps(ev) + "\n")
        return path

    def run_extract(self, *args):
        env = dict(os.environ, HOME=str(self.home))
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args),
                              capture_output=True, text=True, env=env)

    def plan(self, *args):
        r = self.run_extract("--plan", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        manifest = [ln.split(" ", 1)[1] for ln in r.stdout.splitlines()
                    if ln.startswith("manifest: ")][0]
        return r, manifest

    def corpus_from(self, result):
        path = result.stdout.strip().splitlines()[0]
        self.corpora.append(path)
        return Path(path)

    @staticmethod
    def lines(path):
        with open(str(path), encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f]

    # -- (1) plan/extract equality + manifest pinning --------------------------

    def test_plan_counts_equal_what_extraction_processes(self):
        r, manifest = self.plan("--scope", "all", "--days", "14")
        self.assertIn("your messages   : 10", r.stdout)
        self.assertIn("sessions        : 3", r.stdout)
        run = self.run_extract("--manifest", manifest)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(len(self.lines(self.corpus_from(run))), 10)

    def test_plan_writes_no_corpus_and_manifest_is_private(self):
        tmpdir = Path(tempfile.gettempdir())
        before = set(tmpdir.glob("skillsmith-corpus-*"))
        _, manifest = self.plan("--scope", "all")
        self.assertEqual(set(tmpdir.glob("skillsmith-corpus-*")), before,
                         "--plan must report, not extract")
        self.assertEqual(stat.S_IMODE(os.stat(manifest).st_mode), 0o600)
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["totals"], {"sessions": 3, "messages": 10})
        self.assertEqual(len(data["sessions"]), 3)

    def test_session_added_after_plan_refuses(self):
        _, manifest = self.plan("--scope", "all")
        self.session("-Users-me-proj2", "dddddddd-4444-4444-4444-444444444444",
                     ["new one", "new two", "new three"])
        r = self.run_extract("--manifest", manifest)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("candidate set changed", r.stderr)
        self.assertIn("added", r.stderr)

    def test_session_that_grew_is_accepted_and_its_tail_is_not_mined(self):
        """CAP finding: transcripts are appended to constantly, so refusing on
        growth made the pinned flow unusable on a machine with any other session
        open. The approved BYTES are what gets read; the tail is simply outside
        the approved set."""
        _, manifest = self.plan("--scope", "all")
        path = (self.projects / "-Users-me-proj1"
                / "bbbbbbbb-2222-2222-2222-222222222222.jsonl")
        with open(str(path), "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "timestamp": "2026-09-09T10:00:00Z",
                                "message": {"content": "typed after approval"}}) + "\n")
        r = self.run_extract("--manifest", manifest)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = "\n".join(self.lines(self.corpus_from(r)))
        self.assertEqual(len(body.splitlines()), 10)
        self.assertNotIn("typed after approval", body)

    def test_truncated_session_refuses(self):
        _, manifest = self.plan("--scope", "all")
        path = (self.projects / "-Users-me-proj1"
                / "bbbbbbbb-2222-2222-2222-222222222222.jsonl")
        with open(str(path), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "timestamp": "2026-09-01T10:00:00Z",
                                "message": {"content": "awd"}}) + "\n")
        r = self.run_extract("--manifest", manifest)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("rewritten or truncated", r.stderr)

    def test_session_removed_after_plan_refuses(self):
        _, manifest = self.plan("--scope", "all")
        (self.projects / "-Users-me-proj2"
         / "cccccccc-3333-3333-3333-333333333333.jsonl").unlink()
        r = self.run_extract("--manifest", manifest)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("removed", r.stderr)

    def test_unchanged_set_is_accepted_twice(self):
        _, manifest = self.plan("--scope", "all")
        for _ in range(2):
            r = self.run_extract("--manifest", manifest)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.corpus_from(r)

    def test_manifest_version_mismatch_refused(self):
        _, manifest = self.plan("--scope", "all")
        with open(manifest, encoding="utf-8") as f:
            data = json.load(f)
        data["manifest_version"] = 99
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(data, f)
        r = self.run_extract("--manifest", manifest)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_unreadable_manifest_refused(self):
        r = self.run_extract("--manifest", str(self.home / "nope.json"))
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_plan_and_manifest_are_mutually_exclusive(self):
        r = self.run_extract("--plan", "--manifest", "x")
        self.assertEqual(r.returncode, 3)

    def test_plan_names_scope_all_exposure(self):
        r, _ = self.plan("--scope", "all")
        self.assertIn("EVERY project", r.stdout)
        self.assertIn("project names are data", r.stdout)

    def test_same_count_content_replacement_refuses(self):
        """CAP finding: a digest over counts alone would let a transcript be
        rewritten in place with different text and still pass."""
        _, manifest = self.plan("--scope", "all")
        self.session("-Users-me-proj2", "cccccccc-3333-3333-3333-333333333333",
                     ["something else", "entirely different", "three messages still"])
        r = self.run_extract("--manifest", manifest)
        self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
        self.assertIn("rewritten or truncated", r.stderr)

    def test_same_session_id_in_two_projects_is_not_collapsed(self):
        """CAP finding: keying the digest by session id alone collapses a session
        id that exists in two projects."""
        dup = "aaaaaaaa-1111-1111-1111-111111111111"
        self.session("-Users-me-proj2", dup, ["p2 one", "p2 two", "p2 three"])
        r, manifest = self.plan("--scope", "all")
        self.assertIn("sessions        : 4", r.stdout)
        with open(manifest, encoding="utf-8") as f:
            keys = [s["key"] for s in json.load(f)["sessions"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("me/proj1/" + dup, keys)
        self.assertIn("me/proj2/" + dup, keys)
        run = self.run_extract("--manifest", manifest)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(len(self.lines(self.corpus_from(run))), 13)

    def test_unreadable_candidate_transcript_is_counted_not_hidden(self):
        """CAP finding: an unreadable transcript used to be swallowed entirely —
        neither mined nor mentioned. It is now excluded AND counted, so the plan
        report has no silent bucket."""
        victim = (self.projects / "-Users-me-proj2"
                  / "cccccccc-3333-3333-3333-333333333333.jsonl")
        os.chmod(str(victim), 0o000)

        def restore():
            try:
                os.chmod(str(victim), 0o600)
            except OSError:
                pass
        self.addCleanup(restore)
        if os.access(str(victim), os.R_OK):
            self.skipTest("running as a user that ignores file modes (root)")
        r, _ = self.plan("--scope", "all")
        self.assertIn("transcripts that could not be read: 1", r.stdout)
        self.assertIn("sessions        : 2", r.stdout)

    def test_malformed_lines_are_counted_not_hidden(self):
        path = self.session("-Users-me-proj1", "99999999-9999-9999-9999-999999999999",
                            ["real one", "real two", "real three"])
        with open(str(path), "a", encoding="utf-8") as f:
            f.write("{ this is not json\n")
        r, _ = self.plan("--scope", "all")
        self.assertIn("unparseable lines: 1", r.stdout)

    # -- (6) tab flattening ----------------------------------------------------

    def test_tabs_in_user_text_are_flattened(self):
        r = self.run_extract("--unpinned", "--scope", "all", "--days", "14")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = self.lines(self.corpus_from(r))
        self.assertTrue(lines)
        for ln in lines:
            self.assertEqual(len(ln.split("\t")), 4,
                             "a raw tab in user text shifted the corpus fields: %r" % ln)
        self.assertTrue(any("a ␉ b ␉ c" in ln for ln in lines))

    def test_newlines_still_flattened(self):
        self.session("-Users-me-proj1", "eeeeeeee-5555-5555-5555-555555555555",
                     ["line one\nline two", "b", "c"])
        r = self.run_extract("--unpinned", "--scope", "all")
        lines = self.lines(self.corpus_from(r))
        self.assertTrue(any("line one ⏎ line two" in ln for ln in lines))

    # -- scope / exclusion invariants (unchanged in v1.1, still enforced) ------

    def test_scope_current_limits_to_one_project(self):
        r = self.run_extract("--unpinned", "--scope", "current", "--project=-Users-me-proj2")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = self.lines(self.corpus_from(r))
        self.assertEqual(len(lines), 3)
        self.assertTrue(all("me/proj2" in ln for ln in lines))

    def test_excluded_session_is_not_mined(self):
        r = self.run_extract("--unpinned", "--scope", "all", "--exclude-session",
                             "cccccccc-3333-3333-3333-333333333333")
        lines = self.lines(self.corpus_from(r))
        self.assertEqual(len(lines), 7)
        r2, _ = self.plan("--scope", "all", "--exclude-session",
                          "cccccccc-3333-3333-3333-333333333333")
        self.assertIn("current/named sessions excluded : 1", r2.stdout)

    def test_session_where_skillsmith_fired_is_excluded(self):
        self.session("-Users-me-proj1", "ffffffff-6666-6666-6666-666666666666",
                     ["mine me", "and me", "me too"],
                     extra_events=[{"type": "assistant", "message": {"content": [
                         {"type": "tool_use", "name": "Skill",
                          "input": {"skill": "skillsmith"}}]}}])
        r, _ = self.plan("--scope", "all")
        self.assertIn("sessions where skillsmith ran   : 1", r.stdout)
        run = self.run_extract("--unpinned", "--scope", "all")
        self.assertNotIn("mine me", "\n".join(self.lines(self.corpus_from(run))))

    def test_sanity_floor_trips_loudly(self):
        r = self.run_extract("--unpinned", "--scope", "all", "--min-per-session", "50")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("sanity floor", r.stderr)

    def test_total_schema_drift_aborts_instead_of_reporting_no_candidates(self):
        """CAP finding (the important one): the sanity floor divided by the number
        of sessions that PRODUCED messages, so total drift — every session yielding
        nothing — made the divisor zero and the check pass silently. That is the
        exact failure the check exists to catch."""
        for d in self.projects.iterdir():
            for f in d.glob("*.jsonl"):
                rows = [json.loads(ln) for ln in self.lines(f) if ln.strip()]
                with open(str(f), "w", encoding="utf-8") as out:
                    for ev in rows:
                        ev["type"] = "human"          # the schema drifted
                        out.write(json.dumps(ev) + "\n")
        r = self.run_extract("--unpinned", "--scope", "all")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("NOTHING parsed at all", r.stderr)

    def test_bare_invocation_refuses_to_mine_unapproved(self):
        """CAP finding: pinning was opt-in, so a dropped flag mined an unapproved
        set and exited 0. The unpinned path is now explicit."""
        r = self.run_extract("--scope", "all")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("--unpinned", r.stderr)

    def test_namespaced_skillsmith_session_is_excluded(self):
        """CAP finding: plugin installs invoke `skillsmith:skillsmith`, so an
        exact-match exclusion missed every skillsmith session for plugin users —
        and mining its own sessions manufactures frequency evidence."""
        self.session("-Users-me-proj1", "77777777-7777-7777-7777-777777777777",
                     ["mine me", "and me", "me too"],
                     extra_events=[{"type": "assistant", "message": {"content": [
                         {"type": "tool_use", "name": "Skill",
                          "input": {"skill": "skillsmith:skillsmith"}}]}}])
        r, _ = self.plan("--scope", "all")
        self.assertIn("sessions where skillsmith ran   : 1", r.stdout)

    def test_scope_current_does_not_fuzzy_match_other_projects(self):
        """CAP finding: a substring fallback mined every project whose slug
        contained this one's, while the report still said 'this project only'."""
        r = self.run_extract("--unpinned", "--scope", "current",
                             "--project=-Users-me-nonexistent")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("--project=", r.stderr)

    def test_carriage_returns_are_flattened(self):
        self.session("-Users-me-proj1", "88888888-8888-8888-8888-888888888888",
                     ["crlf\r\nblock", "b", "c"])
        r = self.run_extract("--unpinned", "--scope", "all")
        for ln in self.lines(self.corpus_from(r)):
            self.assertNotIn("\r", ln)

    def test_harness_blocks_do_not_swallow_the_user_message(self):
        """CAP finding: noise prefixes were matched against the JOINED blocks, so
        a short trigger word arriving with a long system-reminder block was both
        polluted and pushed past MAX_LEN — dropping exactly the terse phrases
        Stage C exists to find."""
        d = self.projects / "-Users-me-proj1"
        path = d / "66666666-6666-6666-6666-666666666666.jsonl"
        reminder = "<system-reminder>" + ("x" * 2000) + "</system-reminder>"
        with open(str(path), "w", encoding="utf-8") as f:
            for msg in ("hop", "ctc", "awd"):
                f.write(json.dumps({"type": "user", "timestamp": "2026-09-01T10:00:00Z",
                                    "message": {"content": [
                                        {"type": "text", "text": msg},
                                        {"type": "text", "text": reminder}]}}) + "\n")
        r = self.run_extract("--unpinned", "--scope", "all")
        body = "\n".join(self.lines(self.corpus_from(r)))
        self.assertIn("\thop", body)
        self.assertNotIn("system-reminder", body)

    def test_claude_config_dir_is_honored(self):
        """CAP finding: hardcoding ~/.claude means every guarantee holds
        perfectly, on a directory the harness never reads."""
        alt = self.home / "alt-config"
        (alt / "projects" / "-Users-me-elsewhere").mkdir(parents=True)
        with open(str(alt / "projects" / "-Users-me-elsewhere" / "ee.jsonl"),
                  "w", encoding="utf-8") as f:
            for m in ("only here", "second", "third"):
                f.write(json.dumps({"type": "user", "timestamp": "2026-09-01T10:00:00Z",
                                    "message": {"content": m}}) + "\n")
        env = dict(os.environ, HOME=str(self.home), CLAUDE_CONFIG_DIR=str(alt))
        r = subprocess.run([sys.executable, str(SCRIPT), "--plan", "--scope", "all"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("your messages   : 3", r.stdout)
        self.assertIn("me/elsewhere", r.stdout)

    def test_version_matches_package(self):
        version = json.loads(
            (REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        r = self.run_extract("--version")
        self.assertIn(version, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
