"""Black-box tests for bin/skillsmith-sync.

Every test invokes the script as a subprocess with the SAME interpreter running
the tests (sys.executable), so a CI matrix leg on Python 3.8 proves the script
on 3.8 — not whatever python3 happens to resolve to.
"""
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "bin" / "skillsmith-sync"
BEGIN = "<!-- skillsmith:index:begin -->"
END = "<!-- skillsmith:index:end -->"


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.md = self.dir / "CLAUDE.md"
        self.content = self.dir / "block.txt"
        self.write(self.content, "| a | b |\n")
        self.write(self.md, "top\n%s\nold\n%s\nbottom\n" % (BEGIN, END))

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def write(path, text):
        with open(str(path), "w", encoding="utf-8", newline="") as f:
            f.write(text)

    @staticmethod
    def read(path):
        with open(str(path), "r", encoding="utf-8", newline="") as f:
            return f.read()

    def sync(self, *extra, **kw):
        md = kw.pop("md", self.md)
        args = [sys.executable, str(SCRIPT)]
        if "--init" not in extra:
            args.append(str(self.content))
        args += ["--claude-md", str(md)] + list(extra)
        env = dict(os.environ, HOME=str(self.dir))  # keep real ~/.claude out of reach
        return subprocess.run(args, capture_output=True, text=True, env=env)

    # -- dry-run / apply basics ------------------------------------------------

    def test_dry_run_writes_nothing_and_prints_hash(self):
        before = self.read(self.md)
        r = self.sync()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("dry-run: no write performed", r.stdout)
        self.assertIn("source sha256:", r.stdout)
        self.assertEqual(self.read(self.md), before)

    def test_apply_splices_and_byte_verifies(self):
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("byte-verified", r.stdout)
        got = self.read(self.md)
        self.assertIn("| a | b |", got)
        self.assertNotIn("old", got)
        self.assertTrue(got.startswith("top\n"))
        self.assertTrue(got.endswith("bottom\n"))

    def test_idempotent_noop(self):
        self.sync("--apply")
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no-op", r.stdout)

    # -- sha256 binding (approved diff = applied diff) -------------------------

    def test_expected_sha_matches(self):
        m = re.search(r"source sha256: ([0-9a-f]{64})", self.sync().stdout)
        self.assertIsNotNone(m)
        r = self.sync("--apply", "--expected-sha256", m.group(1))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_expected_sha_stale_refuses(self):
        before = self.read(self.md)
        r = self.sync("--apply", "--expected-sha256", "0" * 64)
        self.assertEqual(r.returncode, 3)
        self.assertIn("changed since", r.stderr)
        self.assertEqual(self.read(self.md), before)

    # -- marker anomalies refuse, file untouched -------------------------------

    def _assert_refuses(self, md_text, code=1):
        self.write(self.md, md_text)
        r = self.sync("--apply")
        self.assertEqual(r.returncode, code, r.stderr)
        self.assertEqual(self.read(self.md), md_text)

    def test_no_markers(self):
        self._assert_refuses("just prose\n")

    def test_duplicate_begin(self):
        self._assert_refuses("%s\n%s\nx\n%s\n" % (BEGIN, BEGIN, END))

    def test_reversed_markers(self):
        self._assert_refuses("%s\nx\n%s\n" % (END, BEGIN))

    # -- content guards --------------------------------------------------------

    def test_empty_content_refused_without_allow_empty(self):
        self.write(self.content, "\n")
        before = self.read(self.md)
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self.read(self.md), before)
        self.assertEqual(self.sync("--apply", "--allow-empty").returncode, 0)

    def test_content_containing_markers_refused(self):
        self.write(self.content, BEGIN + "\n")
        self.assertEqual(self.sync("--apply").returncode, 3)

    def test_missing_content_file(self):
        self.content.unlink()
        self.assertEqual(self.sync("--apply").returncode, 3)

    # -- byte fidelity ---------------------------------------------------------

    def test_crlf_outside_block_preserved(self):
        original = "top\r\nmore\r\n%s\r\nold\r\n%s\r\ntail\r\n" % (BEGIN, END)
        self.write(self.md, original)
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = self.read(self.md)
        i, j = original.index(BEGIN), original.index(END)
        expected = (original[: i + len(BEGIN)] + "\n| a | b |\n" + original[j:])
        self.assertEqual(got, expected)  # CRLF regions byte-identical

    def test_non_utf8_md_refused_untouched(self):
        raw = b"\xff\xfe garbage " + BEGIN.encode() + b"\n" + END.encode() + b"\n"
        with open(str(self.md), "wb") as f:
            f.write(raw)
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 3)
        with open(str(self.md), "rb") as f:
            self.assertEqual(f.read(), raw)

    # -- symlinks / backups ----------------------------------------------------

    def test_symlink_preserved_target_updated(self):
        target = self.dir / "real.md"
        os.replace(str(self.md), str(target))
        self.md.symlink_to(target)
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.md.is_symlink())
        self.assertIn("| a | b |", self.read(target))

    def test_backup_created_with_private_modes(self):
        r = self.sync("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        bdir = self.dir / ".skillsmith-backups"
        backups = list(bdir.glob("CLAUDE.md.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(stat.S_IMODE(bdir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertIn("old", self.read(backups[0]))  # backup holds pre-write bytes

    def test_backup_retention_capped_at_20(self):
        for i in range(22):
            self.write(self.content, "row %d\n" % i)
            self.assertEqual(self.sync("--apply").returncode, 0)
        backups = list((self.dir / ".skillsmith-backups").glob("CLAUDE.md.*"))
        self.assertLessEqual(len(backups), 20)

    # -- init ------------------------------------------------------------------

    def test_init_creates_file_then_refuses_second_init(self):
        fresh = self.dir / "fresh" / "CLAUDE.md"
        r = self.sync("--init", "--apply", md=fresh)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(BEGIN, self.read(fresh))
        self.assertEqual(self.sync("--init", "--apply", md=fresh).returncode, 1)


if __name__ == "__main__":
    unittest.main()
