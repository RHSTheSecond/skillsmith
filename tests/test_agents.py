"""Black-box tests for bin/skillsmith-agents (the agent registry + its audit).

These cover the v1.1 verification checks that must be able to FAIL:
  (3) a registry with one healthy, one dead and one unreadable signal produces
      exactly healthy / dead / unmeasurable — and the unreadable one is LOUD.
  (5) an agent the scheduler is running that has no registry row is flagged.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "bin" / "skillsmith-agents"


def row(name, signal, **over):
    r = {"name": name, "owner": "someone", "trigger": "systemd timer, daily",
         "side_effect_class": "writes a file", "output_surface": "a log file",
         "signal": signal, "approved_on": "2026-01-01", "approved_by": "someone",
         "review_by": "2099-01-01"}
    r.update(over)
    return r


class AgentsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.registry = self.dir / "agents.json"
        self.fresh = self.dir / "fresh.log"
        self.stale = self.dir / "stale.log"
        self.fresh.write_text("ok\n", encoding="utf-8")
        self.stale.write_text("ok\n", encoding="utf-8")
        old = time.time() - 99 * 3600
        os.utime(str(self.stale), (old, old))

    def tearDown(self):
        self.tmp.cleanup()

    def write_registry(self, agents, version=1):
        with open(str(self.registry), "w", encoding="utf-8") as f:
            json.dump({"version": version, "agents": agents}, f)

    def run_agents(self, *args):
        env = dict(os.environ, HOME=str(self.dir))
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args),
                              capture_output=True, text=True, env=env)

    def audit_json(self, *args):
        r = self.run_agents("--audit", "--registry", str(self.registry), "--json", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def file_signal(self, path, hours=26, cls="delivered"):
        return {"type": "file", "path": str(path), "max_age_hours": hours, "class": cls}

    # -- (3) the three verdicts ------------------------------------------------

    def test_healthy_dead_unmeasurable(self):
        self.write_registry([
            row("alive", self.file_signal(self.fresh)),
            row("expired", self.file_signal(self.stale)),
            row("ghost", self.file_signal(self.dir / "never-written.log")),
        ])
        got = {a["name"]: a["verdict"] for a in self.audit_json()["agents"]}
        self.assertEqual(got, {"alive": "healthy", "expired": "dead",
                               "ghost": "unmeasurable"})

    def test_unmeasurable_is_loud_not_silently_healthy(self):
        self.write_registry([row("ghost", self.file_signal(self.dir / "nope.log"))])
        data = self.audit_json()
        self.assertTrue(any("unmeasurable" in f for f in data["findings"]))
        r = self.run_agents("--audit", "--registry", str(self.registry))
        self.assertIn("unmeasurable", r.stdout)
        self.assertIn("not a pass", r.stdout)

    def test_file_signal_without_max_age_is_unmeasurable_not_healthy(self):
        sig = {"type": "file", "path": str(self.fresh), "class": "delivered"}
        self.write_registry([row("no-limit", sig)])
        agent = self.audit_json()["agents"][0]
        self.assertEqual(agent["verdict"], "unmeasurable")
        self.assertIn("max_age_hours", agent["detail"])

    def test_signal_class_is_reported_not_upgraded(self):
        self.write_registry([row("alive", self.file_signal(self.fresh, cls="delivered"))])
        self.assertEqual(self.audit_json()["agents"][0]["signal_class"], "delivered")

    def test_review_overdue_is_a_finding(self):
        self.write_registry([row("alive", self.file_signal(self.fresh),
                                 review_by="2020-01-01")])
        data = self.audit_json()
        self.assertEqual(data["agents"][0]["verdict"], "healthy")
        self.assertTrue(any("review overdue" in f for f in data["findings"]))

    # -- (5) unapproved promotions --------------------------------------------

    def test_running_agent_absent_from_registry_is_flagged(self):
        self.write_registry([row("known", self.file_signal(self.fresh),
                                 unit="known.timer")])
        timers = self.dir / "timers.txt"
        timers.write_text(
            "NEXT LEFT LAST PASSED UNIT ACTIVATES\n"
            "Mon 06:05 known.timer known.service\n"
            "Tue 07:00 rogue-bot.timer rogue-bot.service\n", encoding="utf-8")
        data = self.audit_json("--running-from", str(timers))
        self.assertEqual(data["unregistered"], ["rogue-bot"])
        self.assertTrue(any("NOT in the registry" in f for f in data["findings"]))

    def test_registered_agent_matched_by_bare_name(self):
        self.write_registry([row("nightly", self.file_signal(self.fresh))])
        timers = self.dir / "timers.txt"
        timers.write_text("Mon nightly.timer nightly.service\n", encoding="utf-8")
        self.assertEqual(self.audit_json("--running-from", str(timers))["unregistered"], [])

    def test_plain_name_list_accepted_when_declared(self):
        self.write_registry([row("nightly", self.file_signal(self.fresh))])
        names = self.dir / "names.txt"
        names.write_text("nightly\n# a comment\nrogue\n", encoding="utf-8")
        data = self.audit_json("--running-from", str(names),
                               "--running-from-format", "names")
        self.assertEqual(data["unregistered"], ["rogue"])

    def test_cron_lines_do_not_invent_agents(self):
        """CAP finding: sniffing the format turned `5 6 * * * /usr/bin/foo` into an
        agent named "5" and reported it as an unapproved promotion."""
        self.write_registry([row("nightly", self.file_signal(self.fresh))])
        crontab = self.dir / "crontab.txt"
        crontab.write_text("5 6 * * * /usr/bin/python3 ~/bin/nightly.py\n"
                           "*/15 * * * * /usr/local/bin/backup-watch\n",
                           encoding="utf-8")
        data = self.audit_json("--running-from", str(crontab),
                               "--running-from-format", "names")
        self.assertEqual(data["unregistered"], [])
        self.assertTrue(any("not understood" in n for n in data["notes"]))

    def test_vendor_units_are_ignored_by_default(self):
        """CAP finding: the documented invocation flags a dozen distribution
        timers on a stock distro, and the one real finding drowns."""
        self.write_registry([row("nightly", self.file_signal(self.fresh))])
        timers = self.dir / "timers.txt"
        timers.write_text(
            "Mon logrotate.timer logrotate.service\n"
            "Mon apt-daily.timer apt-daily.service\n"
            "Mon systemd-tmpfiles-clean.timer systemd-tmpfiles-clean.service\n"
            "Mon rogue-bot.timer rogue-bot.service\n", encoding="utf-8")
        data = self.audit_json("--running-from", str(timers))
        self.assertEqual(data["unregistered"], ["rogue-bot"])
        self.assertTrue(any("vendor-owned" in n for n in data["notes"]))
        loud = self.audit_json("--running-from", str(timers), "--no-vendor-ignore")
        self.assertIn("logrotate", loud["unregistered"])

    def test_unreadable_running_from_does_not_cost_the_verdicts(self):
        """CAP finding: a typo'd path aborted the whole audit, so the user lost
        the registry verdicts they actually came for."""
        self.write_registry([row("alive", self.file_signal(self.fresh))])
        data = self.audit_json("--running-from", str(self.dir / "nope.txt"))
        self.assertEqual(data["agents"][0]["verdict"], "healthy")
        self.assertTrue(any("did NOT run" in f for f in data["findings"]))

    def test_add_refuses_file_signal_without_max_age(self):
        """CAP finding: --add wrote max_age_hours: null and exited 0, producing an
        agent that is unmeasurable by construction."""
        self.write_registry([])
        r = self.run_agents("--add", "--registry", str(self.registry),
                            "--name", "n", "--owner", "me", "--trigger", "t",
                            "--side-effect-class", "c", "--output-surface", "s",
                            "--signal-path", str(self.fresh), "--approved-by", "me",
                            "--review-by", "2099-01-01")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("max_age_hours", r.stderr)
        self.assertEqual(json.loads(self.registry.read_text(encoding="utf-8"))["agents"], [])

    def test_bad_max_age_type_does_not_blind_the_other_rows(self):
        """CAP finding: an unguarded float() on a hand-edited registry raised,
        exited 1, and lost every other agent's verdict."""
        bad = {"type": "file", "path": str(self.fresh), "max_age_hours": "26h",
               "class": "delivered"}
        self.write_registry([row("broken-row", bad),
                             row("alive", self.file_signal(self.fresh))])
        data = self.audit_json()
        got = {a["name"]: a["verdict"] for a in data["agents"]}
        self.assertEqual(got["alive"], "healthy")
        self.assertEqual(got["broken-row"], "unmeasurable")

    def test_registry_parent_directory_is_not_chmodded(self):
        """CAP finding: save() chmodded the registry's parent to 0700
        unconditionally — `--registry /tmp/agents.json` would have locked /tmp."""
        outside = self.dir / "not-mine"
        outside.mkdir(mode=0o755)
        before = os.stat(str(outside)).st_mode & 0o777
        r = self.run_agents("--init", "--registry", str(outside / "agents.json"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.stat(str(outside)).st_mode & 0o777, before)

    # -- schema integrity ------------------------------------------------------

    def test_invalid_row_is_a_finding_not_a_silent_skip(self):
        self.write_registry([{"name": "half-filled", "owner": "someone"}])
        data = self.audit_json()
        self.assertEqual(len(data["agents"]), 1)
        self.assertEqual(data["agents"][0]["verdict"], "unmeasurable")
        self.assertTrue(any("invalid registry row" in f for f in data["findings"]))

    def test_bad_signal_class_rejected(self):
        sig = {"type": "file", "path": str(self.fresh), "max_age_hours": 1,
               "class": "vibes"}
        self.write_registry([row("wishful", sig)])
        self.assertTrue(any("signal class" in f for f in self.audit_json()["findings"]))

    def test_malformed_registry_exits_3(self):
        self.registry.write_text("{not json", encoding="utf-8")
        r = self.run_agents("--audit", "--registry", str(self.registry))
        self.assertEqual(r.returncode, 3)

    def test_missing_registry_exits_3_rather_than_reporting_all_clear(self):
        r = self.run_agents("--audit", "--registry", str(self.dir / "nope.json"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("--init", r.stderr)

    def test_wrong_registry_version_exits_3(self):
        self.write_registry([], version=99)
        r = self.run_agents("--audit", "--registry", str(self.registry))
        self.assertEqual(r.returncode, 3)

    def test_empty_registry_is_valid_and_says_so(self):
        self.write_registry([])
        r = self.run_agents("--audit", "--registry", str(self.registry))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nothing has been promoted", r.stdout)

    # -- command signals are opt-in exec ---------------------------------------

    def test_command_signal_not_executed_without_allow_exec(self):
        marker = self.dir / "ran"
        sig = {"type": "command", "command": ["touch", str(marker)], "class": "delivered"}
        self.write_registry([row("cmd", sig)])
        agent = self.audit_json()["agents"][0]
        self.assertEqual(agent["verdict"], "unmeasurable")
        self.assertIn("--allow-exec", agent["detail"])
        self.assertFalse(marker.exists(), "signal command ran without --allow-exec")

    def test_command_signal_with_allow_exec(self):
        self.write_registry([
            row("ok", {"type": "command", "command": ["true"], "class": "delivered"}),
            row("broken", {"type": "command", "command": ["false"], "class": "delivered"}),
        ])
        got = {a["name"]: a["verdict"]
               for a in self.audit_json("--allow-exec")["agents"]}
        self.assertEqual(got, {"ok": "healthy", "broken": "dead"})

    def test_shell_string_command_is_refused_not_executed(self):
        """CAP finding: a shell string in a config file is a pipeline waiting to
        happen. Commands are argv lists, and there is no shell to interpret one."""
        marker = self.dir / "pwned"
        sig = {"type": "command", "command": "true; touch %s" % marker,
               "class": "delivered"}
        self.write_registry([row("sneaky", sig)])
        data = self.audit_json("--allow-exec")
        self.assertEqual(data["agents"][0]["verdict"], "unmeasurable")
        self.assertTrue(any("argv" in f for f in data["findings"]))
        self.assertFalse(marker.exists(), "a shell string was interpreted by a shell")

    def test_shell_metacharacters_in_argv_are_literal(self):
        marker = self.dir / "pwned2"
        sig = {"type": "command", "command": ["echo", "hi; touch %s" % marker],
               "class": "delivered"}
        self.write_registry([row("literal", sig)])
        self.assertEqual(self.audit_json("--allow-exec")["agents"][0]["verdict"],
                         "healthy")
        self.assertFalse(marker.exists(), "argv token was interpreted as shell")

    def test_non_positive_max_age_is_refused(self):
        """CAP finding: max_age_hours <= 0 is schema-valid but can never pass."""
        sig = {"type": "file", "path": str(self.fresh), "max_age_hours": 0,
               "class": "delivered"}
        self.write_registry([row("impossible", sig)])
        self.assertTrue(any("max_age_hours" in f for f in self.audit_json()["findings"]))

    # -- init / add ------------------------------------------------------------

    def test_init_creates_private_empty_registry_then_refuses_second_init(self):
        target = self.dir / "sub" / "agents.json"
        r = self.run_agents("--init", "--registry", str(target))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                         {"version": 1, "agents": []})
        self.assertEqual(os.stat(str(target)).st_mode & 0o777, 0o600)
        self.assertEqual(self.run_agents("--init", "--registry", str(target)).returncode, 3)

    def test_add_appends_valid_row_and_refuses_duplicate(self):
        self.write_registry([])
        args = ["--add", "--registry", str(self.registry), "--name", "nightly",
                "--owner", "me", "--trigger", "timer daily 06:05",
                "--side-effect-class", "posts to a chat space",
                "--output-surface", "the reports space",
                "--signal-type", "file", "--signal-path", str(self.fresh),
                "--max-age-hours", "26", "--signal-class", "delivered",
                "--approved-by", "me", "--review-by", "2099-01-01"]
        r = self.run_agents(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(self.registry.read_text(encoding="utf-8"))
        self.assertEqual(data["agents"][0]["name"], "nightly")
        self.assertEqual(self.run_agents(*args).returncode, 3)

    def test_add_refuses_incomplete_row(self):
        self.write_registry([])
        r = self.run_agents("--add", "--registry", str(self.registry),
                            "--name", "nightly", "--owner", "me")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(json.loads(self.registry.read_text(encoding="utf-8"))["agents"], [])

    def test_add_refuses_non_iso_review_date(self):
        self.write_registry([])
        r = self.run_agents("--add", "--registry", str(self.registry), "--name", "n",
                            "--owner", "me", "--trigger", "t", "--side-effect-class", "c",
                            "--output-surface", "s", "--signal-path", str(self.fresh),
                            "--max-age-hours", "26", "--approved-by", "me",
                            "--review-by", "someday")
        self.assertEqual(r.returncode, 3)

    def test_shipped_template_is_a_valid_registry(self):
        template = REPO / "templates" / "agents.json.example"
        data = json.loads(template.read_text(encoding="utf-8"))
        with open(str(self.registry), "w", encoding="utf-8") as f:
            json.dump(data, f)
        r = self.run_agents("--audit", "--registry", str(self.registry), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        audited = json.loads(r.stdout)["agents"]
        self.assertEqual(len(audited), len(data["agents"]))
        # every row must be schema-valid: no row may fail as an invalid registry row
        for a in audited:
            self.assertNotIn("invalid registry row", a["detail"])

    def test_version_matches_package(self):
        version = json.loads(
            (REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        r = self.run_agents("--version")
        self.assertIn(version, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
