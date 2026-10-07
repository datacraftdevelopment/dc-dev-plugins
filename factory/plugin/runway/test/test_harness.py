"""Offline tests for per-project / per-ticket harness profiles. Run: python3 -m pytest -q test/test_harness.py
Fake harness commands print each JSON shape (Claude Code's single object, Codex's JSONL events)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_heartbeat import make_repo  # noqa: E402

CLAUDE_OUT = {"type": "result", "result": "claude says hi", "session_id": "sess-claude",
              "total_cost_usd": 0.42, "num_turns": 3, "usage": {"input_tokens": 10, "output_tokens": 5}}
CODEX_EVENTS = [
    {"type": "thread.started", "thread_id": "thread-codex"},
    {"type": "item.completed", "item": {"id": "i0", "type": "reasoning", "text": "thinking"}},
    {"type": "item.completed", "item": {"id": "i1", "type": "agent_message", "text": "codex says hi"}},
    {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 7}},
]
CODEX_RAW = "\n".join(json.dumps(e) for e in CODEX_EVENTS)


def fake(path: Path, payload: str) -> str:
    """A fake harness: swallows stdin, writes work.txt, prints payload."""
    path.write_text("import sys\nsys.stdin.read()\nopen('work.txt','w').write('x')\nprint(%r)\n" % payload)
    return f"{sys.executable} {path}"


class Parsers(unittest.TestCase):
    def test_claude(self):
        text, meta = runway.parse_output("claude", json.dumps(CLAUDE_OUT))
        self.assertEqual(text, "claude says hi")
        self.assertEqual(meta["session_id"], "sess-claude")
        self.assertEqual(meta["cost_usd"], 0.42)
        self.assertEqual(meta["num_turns"], 3)
        self.assertEqual(meta["usage"], {"input_tokens": 10, "output_tokens": 5})

    def test_codex(self):
        text, meta = runway.parse_output("codex", CODEX_RAW)
        self.assertEqual(text, "codex says hi")
        self.assertEqual(meta["session_id"], "thread-codex")
        self.assertIsNone(meta["cost_usd"])
        self.assertEqual(meta["usage"]["output_tokens"], 7)

    def test_raw_and_garbage_fall_back_to_stdout(self):
        for name in ("claude", "codex", "raw"):
            text, meta = runway.parse_output(name, "plain words")
            self.assertEqual(text, "plain words")
            self.assertIsNone(meta["session_id"])
            self.assertIsNone(meta["cost_usd"])
            self.assertIsNone(meta["usage"])


class Resolve(unittest.TestCase):
    CFG = dict(runway.DEFAULT_CONFIG, agent_cmd="top-agent", prep_cmd="top-prep", review_cmd="top-review",
               harnesses={"codex": {"agent_cmd": "cx-agent", "prep_cmd": "cx-prep", "review_cmd": "cx-review",
                                    "parser": "codex"}})

    class T:
        def __init__(self, harness=None):
            self.harness = harness

    def test_default_is_top_level_claude(self):
        p = runway.resolve_harness(self.CFG, self.T())
        self.assertEqual((p["name"], p["agent_cmd"], p["parser"]), ("claude", "top-agent", "claude"))

    def test_project_harness_setting(self):
        p = runway.resolve_harness(dict(self.CFG, harness="codex"), self.T())
        self.assertEqual((p["name"], p["agent_cmd"], p["prep_cmd"], p["parser"]),
                         ("codex", "cx-agent", "cx-prep", "codex"))

    def test_ticket_override_wins(self):
        p = runway.resolve_harness(self.CFG, self.T("codex"))
        self.assertEqual((p["name"], p["review_cmd"]), ("codex", "cx-review"))

    def test_unknown_override_falls_back_to_default(self):
        self.assertEqual(runway.resolve_harness(self.CFG, self.T("nope"))["name"], "claude")

    def test_no_ticket_gives_project_default(self):
        self.assertEqual(runway.resolve_harness(self.CFG)["name"], "claude")


class Overrides(unittest.TestCase):
    def test_markdown_header(self):
        root = Path(tempfile.mkdtemp())
        p = root / ".scratch" / "eff" / "issues" / "01-x.md"
        p.parent.mkdir(parents=True)
        p.write_text("# T\nHarness: Codex\n")
        self.assertEqual(runway.Ticket(p, root).harness, "codex")
        p.write_text("# T\n")
        self.assertIsNone(runway.Ticket(p, root).harness)

    def test_linear_label(self):
        import linear_tracker
        t = linear_tracker.LinearTicket.__new__(linear_tracker.LinearTicket)
        t.labels = {"go": "1", "harness:codex": "2"}
        self.assertEqual(t.harness, "codex")
        t.labels = {"go": "1"}
        self.assertIsNone(t.harness)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.get("RUNWAY_HOME")
        os.environ["RUNWAY_HOME"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("RUNWAY_HOME", None) if self._env is None else os.environ.__setitem__("RUNWAY_HOME", self._env)

    def test_labelled_ticket_runs_codex_profile_others_default(self):
        root = make_repo({"01-plain": "", "02-codex": "Harness: codex"})
        claude = fake(root / "fc.py", json.dumps(CLAUDE_OUT))
        codex = fake(root / "fx.py", CODEX_RAW)
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))
        cfg.update(agent_cmd=claude, prep_cmd=claude, review_cmd=claude,
                   harnesses={"codex": {"agent_cmd": codex, "prep_cmd": codex, "review_cmd": codex,
                                        "parser": "codex"}})
        tracker = runway.make_tracker(cfg, root)
        for t in tracker.load():
            runway.run_ticket(cfg, root, tracker, t)
        recs = [json.loads(l) for l in (root / "_pm" / "runway-runs.jsonl").read_text().splitlines()]
        runs = {r["ticket"]: r for r in recs if r["kind"] == "run"}
        self.assertEqual(runs["eff/01"]["harness"], "claude")
        self.assertEqual(runs["eff/01"]["session_id"], "sess-claude")
        self.assertEqual(runs["eff/02"]["harness"], "codex")
        self.assertEqual(runs["eff/02"]["session_id"], "thread-codex")
        self.assertIsNone(runs["eff/02"]["cost_usd"])
        calls = [r for r in recs if r["kind"] in ("prep", "run", "review", "fix", "pr")]
        self.assertTrue(calls and all("harness" in r for r in calls))

    def test_status_json_reports_effective_harness(self):
        root = make_repo({"01-plain": "", "02-codex": "Harness: codex"})
        cfg = dict(runway.DEFAULT_CONFIG, harnesses={"codex": {"parser": "codex"}})
        doc = runway.status_json(cfg, root, runway.make_tracker(cfg, root))
        self.assertEqual({t["id"]: t["harness"] for t in doc["tickets"]}, {"eff/01": "claude", "eff/02": "codex"})
        cfg["harness"] = "codex"
        doc = runway.status_json(cfg, root, runway.make_tracker(cfg, root))
        self.assertEqual({t["harness"] for t in doc["tickets"]}, {"codex"})

    def test_transcript_per_harness(self):
        home = Path(tempfile.mkdtemp())
        f = home / "sessions" / "2026" / "10" / "07" / "rollout-2026-10-07T10-00-00-abc123.jsonl"
        f.parent.mkdir(parents=True)
        f.write_text("{}")
        os.environ["CODEX_HOME"] = str(home)
        try:
            self.assertEqual(runway.transcript("abc123", "codex"), str(f))
            self.assertIsNone(runway.transcript("missing", "codex"))
            self.assertIsNone(runway.transcript("abc123", "raw"))
        finally:
            del os.environ["CODEX_HOME"]


if __name__ == "__main__":
    unittest.main()
