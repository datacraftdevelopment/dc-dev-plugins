"""Offline tests for machine-stamped claims (markdown tracker, two simulated machines).
Run: python3 -m unittest -v test_machine_claims"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
from test_status_json import FakeLinear, node  # noqa: E402


def make_repo(tickets: dict) -> Path:
    root = Path(tempfile.mkdtemp())
    d = root / ".scratch" / "eff" / "issues"
    d.mkdir(parents=True)
    for name, head in tickets.items():
        (d / f"{name}.md").write_text(f"# Title {name}\n{head}\n")
    return root


def tracker(root: Path):
    return runway.make_tracker({"tracker": "markdown"}, root)


class MachineName(unittest.TestCase):
    def test_scutil_then_hostname_fallback(self):
        ok = subprocess.CompletedProcess([], 0, stdout="Mini-One\n", stderr="")
        with mock.patch("subprocess.run", return_value=ok):
            self.assertEqual(runway.machine_name(), "Mini-One")
        with mock.patch("subprocess.run", side_effect=FileNotFoundError), \
                mock.patch("socket.gethostname", return_value="linuxbox"):
            self.assertEqual(runway.machine_name(), "linuxbox")
        bad = subprocess.CompletedProcess([], 1, stdout="", stderr="not set")
        with mock.patch("subprocess.run", return_value=bad), mock.patch("socket.gethostname", return_value="h"):
            self.assertEqual(runway.machine_name(), "h")

    def test_whoami_cli(self):
        out = subprocess.run([sys.executable, runway.__file__, "whoami"], capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), runway.machine_name())


class Claims(unittest.TestCase):
    def test_claim_writes_header(self):
        root = make_repo({"01-a": ""})
        tracker(root).load()[0].mark_claimed("runway/eff-01-a", "Mini-One")
        t = tracker(root).load()[0]
        self.assertEqual(t.h("Claimed-by"), "Mini-One")
        self.assertEqual(t.claimed_by, "Mini-One")
        self.assertEqual(t.status, "claimed")

    def test_unclaimed_has_no_claimed_by(self):
        self.assertIsNone(tracker(make_repo({"01-a": ""})).load()[0].claimed_by)

    def tick_with(self, me: str, root: Path, log=None) -> list:
        ran = []
        with mock.patch.object(runway, "machine_name", return_value=me), \
                mock.patch.object(runway, "run_ticket", side_effect=lambda cfg, r, tr, t: ran.append(t.id)), \
                mock.patch.object(runway, "sync_base", return_value=True), \
                mock.patch.object(runway, "log", log or mock.MagicMock()):
            runway.tick(dict(runway.DEFAULT_CONFIG), root, tracker(root))
        return ran

    def test_other_machines_ticket_is_never_run_and_skip_is_logged(self):
        root = make_repo({"01-theirs": "Claimed-by: Mini-Two", "02-free": ""})
        lg = mock.MagicMock()
        self.assertEqual(self.tick_with("Mini-One", root, lg), ["eff/02"])
        self.assertIn("skip eff/01 claimed by Mini-Two", [c.args[1] for c in lg.call_args_list])

    def test_own_claim_still_runs(self):
        self.assertEqual(self.tick_with("Mini-One", make_repo({"01-mine": "Claimed-by: Mini-One"})), ["eff/01"])

    def test_two_machines_one_ticket(self):
        root = make_repo({"01-a": ""})
        tracker(root).load()[0].mark_claimed("b", "Mini-One")
        t = tracker(root).load()[0]  # parked then approved: ready again, claim header stays
        t.set("Status", "ready")
        t.save()
        self.assertEqual(self.tick_with("Mini-Two", root), [])
        self.assertEqual(self.tick_with("Mini-One", root), ["eff/01"])

    def test_status_json_machine_and_claimed_by(self):
        root = make_repo({"01-run": "Status: claimed\nClaimed-by: Mini-Two", "02-free": ""})
        with mock.patch.object(runway, "machine_name", return_value="Mini-One"):
            d = runway.status_json({"tracker": "markdown"}, root, tracker(root))
        self.assertEqual(d["machine"], "Mini-One")
        by = {t["id"]: t for t in d["tickets"]}
        self.assertEqual(by["eff/01"]["claimed_by"], "Mini-Two")
        self.assertIsNone(by["eff/02"]["claimed_by"])
        json.dumps(d)


class LinearClaims(unittest.TestCase):
    def test_claimed_by_from_runway_comment(self):
        n = node(1, ["ready-for-agent"], "started", ["\U0001f6eb runway · Claimed-by: Mini-Two · Started on `b`."])
        self.assertEqual(FakeLinear([n]).load()[0].claimed_by, "Mini-Two")
        self.assertIsNone(FakeLinear([node(2, ["ready-for-agent"], "unstarted")]).load()[0].claimed_by)

    def test_claim_comment_names_machine(self):
        import linear_tracker as L
        t = L.LinearTicket(node(1, [], "unstarted"), mock.MagicMock())
        t._update, t._comment = mock.MagicMock(), mock.MagicMock()
        t.mark_claimed("runway/x", "Mini-One")
        self.assertIn("Claimed-by: Mini-One", t._comment.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
