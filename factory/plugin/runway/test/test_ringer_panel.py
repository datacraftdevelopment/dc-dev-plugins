"""Offline tests for the two-seat Ringer review panel (ringer_panel.py and finish's `review: panel`).
Run: python3 -m pytest -q test/test_ringer_panel.py
A fake `ringer` on PATH stands in for the real one: `lint` checks the manifest is filled, `run` writes
fake seat reports. FAKE_SEATS says what each seat does: ok | bad (report whose check fails) | none."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_heartbeat import git, make_repo  # noqa: E402

HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / "ringer_panel.py"
TEMPLATE = HERE / "fixtures" / "ringer-panel" / "manifest.template.json"

FAKE_RINGER = '''#!/usr/bin/env python3
import json, os, sys
cmd, manifest = sys.argv[1], sys.argv[2]
text = open(manifest).read()
m = json.loads(text)
if cmd == "lint":
    if any("{{" + n + "}}" in text for n in ("RUN_SLUG", "WORKDIR", "REVIEW_SCOPE", "ARTIFACT_PATH_OR_DIFF_COMMAND", "REVIEW_FOCUS", "KIT_DIR")):
        print("unfilled placeholder"); sys.exit(1)
    sys.exit(0)
seats = dict(p.split("=") for p in os.environ["FAKE_SEATS"].split(","))
code = 0
for t in m["tasks"]:
    how = seats.get(t["key"].split("-")[1], "none")
    d = os.path.join(m["workdir"], t["key"])
    os.makedirs(d, exist_ok=True)
    if how == "none":
        print(t["key"], "FAIL (no report)"); code = 1; continue
    body = "## Summary\\nNO FINDINGS\\n" if how == "ok" else "## Summary\\nFinding: x\\nPriority: P1\\n"
    if t["key"] == "review-claude" and how == "ok":
        body = "## Summary\\nFinding: a bug\\nEvidence: f.py:1\\nImpact: i\\nFix: f\\nPriority: P1\\nConfidence: high\\n"
    open(os.path.join(d, "report.md"), "w").write(body)
    if how == "bad":
        print(t["key"], "FAIL (check)"); code = 1
    else:
        print(t["key"], "PASS")
sys.exit(code)
'''


def kit_root():
    """A fake Ringer clone holding only the panel template."""
    root = Path(tempfile.mkdtemp()).resolve()
    dest = root / "local" / "templates" / "adversarial-review-panel"
    dest.mkdir(parents=True)
    shutil.copy(TEMPLATE, dest / "manifest.template.json")
    return root


def fake_bin():
    d = Path(tempfile.mkdtemp()).resolve()
    (d / "ringer").write_text(FAKE_RINGER.replace("/usr/bin/env python3", sys.executable))
    (d / "ringer").chmod(0o755)
    return d


class Panel(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo({"01-thing": ""})
        (self.repo / "a.txt").write_text("x")
        git(self.repo, "checkout", "-qb", "feature")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "change")
        self.out = Path(tempfile.mkdtemp()).resolve() / "out"
        self.brief = self.out.parent / "brief.md"
        self.brief.write_text('Tickets: 01 "quoted" {{BRIEF}} \\ back')
        self.root = kit_root()
        self.bin = fake_bin()

    def run_panel(self, seats="codex=ok,claude=ok", ringer=True, root=True):
        env = dict(os.environ, FAKE_SEATS=seats, PATH=str(self.bin) if ringer else "/usr/bin:/bin")
        env.pop("RINGER_ROOT", None)
        if root:
            env["RINGER_ROOT"] = str(self.root)
        env["HOME"] = str(self.out.parent)  # no ~/Agentic-Mini here
        return subprocess.run([sys.executable, str(PANEL), "--repo", str(self.repo), "--base", "main",
                               "--brief-file", str(self.brief), "--out", str(self.out)],
                              capture_output=True, text=True, env=env)

    def test_both_seats(self):
        r = self.run_panel()
        self.assertEqual(r.returncode, 0, r.stderr)
        seats = json.loads(r.stdout)["seats"]
        self.assertEqual({k: v["status"] for k, v in seats.items()}, {"codex": "PASS", "claude": "PASS"})
        self.assertIn("NO FINDINGS", (self.out / "review-codex.md").read_text())
        self.assertIn("a bug", (self.out / "review-claude.md").read_text())
        self.assertEqual(seats["codex"]["report"], str(self.out / "review-codex.md"))

    def test_manifest_is_filled_and_scoped(self):
        self.run_panel()
        m = json.loads((self.out / "manifest.json").read_text())
        for name in ("RUN_SLUG", "WORKDIR", "REVIEW_SCOPE", "ARTIFACT_PATH_OR_DIFF_COMMAND", "REVIEW_FOCUS", "KIT_DIR"):
            self.assertNotIn("{{" + name + "}}", json.dumps(m))
        self.assertEqual([t["key"] for t in m["tasks"]], ["review-codex", "review-claude"])
        self.assertEqual([t["model"] for t in m["tasks"]], ["gpt-6-astra", "claude-fable-5"])
        self.assertTrue(all(t["timeout_s"] == 1800 for t in m["tasks"]))
        spec = m["tasks"][0]["spec"]
        self.assertIn(f"git -C {self.repo} diff main...HEAD", spec)
        self.assertIn('Tickets: 01 "quoted" {{BRIEF}} \\ back', spec)  # brief inlined verbatim
        self.assertIn("single review worker", spec)  # worker preamble kept
        self.assertTrue(Path(m["workdir"]).resolve().is_relative_to(self.out.resolve()))
        self.assertIn(str(self.root / "templates" / "adversarial-review"), m["tasks"][0]["check"])

    def test_one_seat_missing(self):
        r = self.run_panel("codex=ok,claude=none")
        self.assertEqual(r.returncode, 0)
        seats = json.loads(r.stdout)["seats"]
        self.assertEqual(seats["codex"]["status"], "PASS")
        self.assertEqual(seats["claude"]["status"], "MISSING")
        self.assertFalse((self.out / "review-claude.md").exists())

    def test_failed_check_keeps_report_marked_fail(self):
        r = self.run_panel("codex=bad,claude=ok")
        self.assertEqual(r.returncode, 0)
        seats = json.loads(r.stdout)["seats"]
        self.assertEqual(seats["codex"]["status"], "FAIL")
        self.assertEqual(seats["claude"]["status"], "PASS")
        self.assertTrue((self.out / "review-codex.md").exists())

    def test_no_reports_exits_1(self):
        r = self.run_panel("codex=none,claude=none")
        self.assertEqual(r.returncode, 1)
        seats = json.loads(r.stdout)["seats"]
        self.assertEqual({v["status"] for v in seats.values()}, {"MISSING"})

    def test_ringer_not_found_exits_3(self):
        r = self.run_panel(ringer=False, root=False)
        self.assertEqual(r.returncode, 3)
        self.assertEqual(r.stdout.strip() + r.stderr.strip(), "ringer not found")

    def test_ringer_root_without_path(self):
        shutil.copy(self.bin / "ringer", self.root / "ringer.py")
        r = self.run_panel(ringer=False)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_machine_paths_shipped(self):
        for f in (PANEL, HERE.parent / "runway.py"):
            self.assertNotIn("/Users/joe", f.read_text(), f.name)

    @unittest.skipUnless(shutil.which("ringer"), "ringer not installed")
    def test_manifest_passes_real_lint(self):
        sys.path.insert(0, str(PANEL.parent))
        import ringer_panel
        found = ringer_panel.find_ringer()
        if not found:
            self.skipTest("ringer clone with the panel kit not found")
        cmd, root = found
        manifest = ringer_panel.build_manifest(
            ringer_panel.load_template(root / ringer_panel.TEMPLATE), self.repo, "main", "the brief",
            self.out / "work", root / "templates" / "adversarial-review")
        self.out.mkdir(parents=True)
        (self.out / "m.json").write_text(json.dumps(manifest))
        r = subprocess.run([*cmd, "lint", str(self.out / "m.json")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class FinishPanel(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo({"01-thing": "Status: resolved"})
        git(self.repo, "checkout", "-qb", "runway/integration")
        (self.repo / "feature.txt").write_text("x")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "ticket work")
        git(self.repo, "checkout", "-q", "main")
        self.bin = fake_bin()
        self.rroot = kit_root()
        home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("PATH", "RINGER_ROOT", "FAKE_SEATS", "RUNWAY_HOME", "HOME")}
        os.environ.update(RUNWAY_HOME=str(home), HOME=str(home), RINGER_ROOT=str(self.rroot))
        # The fix agent records its prompt; the review/pr agent prints a single-review marker.
        (self.repo / "fix_agent.py").write_text(
            'import sys\nopen(%r, "a").write(sys.stdin.read() + "\\n=====\\n")\nopen("fixed.txt", "w").write("x")\n'
            % str(self.repo / "prompts.log"))
        (self.repo / "single_review.py").write_text("import sys, json\nsys.stdin.read()\n"
                                                    "print(json.dumps({'result': '- single review finding'}))\n")
        cfg = json.loads((self.repo / "runway.json").read_text())
        cfg.update(review="panel", review_cmd=f"{sys.executable} {self.repo / 'single_review.py'}",
                   fix_cmd=f"{sys.executable} {self.repo / 'fix_agent.py'}",
                   pr_cmd=f"{sys.executable} {self.repo / 'single_review.py'}")
        (self.repo / "runway.json").write_text(json.dumps(cfg))
        (self.repo / ".gitignore").write_text(".scratch/\n_pm/\nseen.jsonl\nrunway.json\nprompts.log\n"
                                              "fix_agent.py\nsingle_review.py\n")

    def tearDown(self):
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def finish(self, seats=None, ringer=True):
        os.environ["PATH"] = (f"{self.bin}:" if ringer else "") + "/usr/bin:/bin:" + os.path.dirname(sys.executable)
        os.environ["FAKE_SEATS"] = seats or ""
        if not ringer:
            os.environ["RINGER_ROOT"] = "/nonexistent"
        r = subprocess.run([sys.executable, str(HERE.parent / "runway.py"), "--root", str(self.repo), "finish"],
                           capture_output=True, text=True, env=os.environ)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rows = [json.loads(line) for line in (self.repo / "_pm" / "runway-runs.jsonl").read_text().splitlines()]
        return rows

    def test_panel_runs_and_both_reports_reach_the_fix_pass(self):
        rows = self.finish("codex=ok,claude=ok")
        pm = self.repo / "_pm"
        self.assertIn("NO FINDINGS", (pm / "runway-review-codex.md").read_text())
        self.assertIn("a bug", (pm / "runway-review-claude.md").read_text())
        panel = [r for r in rows if r["kind"] == "review"]
        self.assertEqual(len(panel), 1)
        self.assertEqual(panel[0]["harness"], "ringer-panel")
        self.assertEqual(panel[0]["seats"], {"codex": "PASS", "claude": "PASS"})
        prompt = (self.repo / "prompts.log").read_text()
        self.assertIn("### codex", prompt)
        self.assertIn("### claude", prompt)
        self.assertNotIn("single review finding", prompt)

    def test_one_seat_missing_still_uses_panel(self):
        rows = self.finish("codex=none,claude=ok")
        panel = [r for r in rows if r["kind"] == "review"][0]
        self.assertEqual(panel["seats"], {"codex": "MISSING", "claude": "PASS"})
        self.assertFalse((self.repo / "_pm" / "runway-review-codex.md").exists())
        self.assertTrue((self.repo / "_pm" / "runway-review-claude.md").exists())

    def test_ringer_missing_falls_back_to_single(self):
        rows = self.finish(ringer=False)
        review = [r for r in rows if r["kind"] == "review"]
        self.assertEqual([r["harness"] for r in review], ["claude"])
        self.assertIn("single review finding", (self.repo / "prompts.log").read_text())
        self.assertIn("ringer not found", (self.repo / "_pm" / "runway.log").read_text())

    def test_no_reports_falls_back_to_single(self):
        rows = self.finish("codex=none,claude=none")
        review = [r for r in rows if r["kind"] == "review"]
        self.assertEqual([r["harness"] for r in review], ["claude"])
        self.assertIn("single review finding", (self.repo / "prompts.log").read_text())

    def test_default_is_single(self):
        self.assertEqual(runway.DEFAULT_CONFIG["review"], "single")


if __name__ == "__main__":
    unittest.main()
