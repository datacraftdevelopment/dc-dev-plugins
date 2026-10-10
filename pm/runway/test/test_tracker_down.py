"""Offline tests (DAT-46): a flaky tracker fails one tick, not the loop; a crash's orphaned claim is released.
Run: python3 -m pytest -q test_tracker_down.py
Linear is faked at urllib's urlopen, GitHub with a scripted `gh`, so the real adapters run end to end."""
import datetime as dt
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runway  # noqa: E402
import transient  # noqa: E402
from test_github_tracker import issue  # noqa: E402
from test_github_write import FAKE_GH  # noqa: E402
from test_heartbeat import make_repo, state  # noqa: E402

MARK = "\U0001f6eb runway"
CLAIM = MARK + " · Claimed-by: {} · Started on `b`."
STATES = [{"id": "s-todo", "name": "Todo", "type": "unstarted", "position": 1},
          {"id": "s-prog", "name": "In Progress", "type": "started", "position": 2},
          {"id": "s-done", "name": "Done", "type": "completed", "position": 3},
          {"id": "s-cancel", "name": "Canceled", "type": "canceled", "position": 4}]
OK = f'{sys.executable} -c "print(1)"'


def dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class Base(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()
        self._env = {k: os.environ.get(k) for k in ("RUNWAY_HOME", "HB_ROOT", "LINEAR_API_KEY", "RUNWAY_BACKOFF_S")}
        os.environ["RUNWAY_HOME"] = str(self.home)
        os.environ["LINEAR_API_KEY"] = "k"
        self.backoff = mock.patch.object(transient, "BACKOFF", (0, 0))
        self.backoff.start()
        self.sleeps = []
        self.procs = []

    def tearDown(self):
        self.backoff.stop()
        for p in self.procs:
            p.kill()
            p.wait()
        for k, v in self._env.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def live_pid(self) -> int:
        p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "runway-stand-in"])
        self.procs.append(p)
        return p.pid

    def root(self):
        root = make_repo({"01-thing": "Status: resolved"})
        cfg = json.loads((root / "runway.json").read_text())
        cfg["notify_cmd"] = f"{sys.executable} -c \"import sys; open(r'{root}/notified','a').write(sys.argv[1]+chr(10))\" {{msg}}"
        (root / "runway.json").write_text(json.dumps(cfg))
        os.environ["HB_ROOT"] = str(root)
        return root

    def notified(self, root):
        p = root / "notified"
        return p.read_text().splitlines() if p.exists() else []

    def beat_file(self, root, pid, ticket, phase="agent"):
        (root / "_pm").mkdir(exist_ok=True)
        (root / "_pm" / "runway-state.json").write_text(json.dumps(
            {"version": 1, "phase": phase, "ticket": ticket, "attempt": 1, "since": "x", "pid": pid,
             "agent_pid": None, "tick_started": "x", "last_result": None}))

    def log_text(self, root):
        p = root / "_pm" / "runway.log"
        return p.read_text() if p.exists() else ""


# ---------- the retry helper ----------

class Retry(Base):
    def test_one_timeout_then_success_returns_the_value(self):
        calls = iter([TimeoutError("slow"), "fine"])

        def fn():
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v
        self.assertEqual(transient.retry(fn, "call x"), "fine")

    def test_keeps_failing_raises_tracker_down_naming_the_call(self):
        n = []

        def fn():
            n.append(1)
            raise ConnectionResetError("reset")
        with self.assertRaises(transient.TrackerDown) as cm:
            transient.retry(fn, "Linear read")
        self.assertEqual(len(n), transient.TRIES)
        self.assertIn("Linear read", str(cm.exception))

    def test_other_errors_are_not_retried(self):
        n = []

        def fn():
            n.append(1)
            raise ValueError("bug")
        with self.assertRaises(ValueError):
            transient.retry(fn, "x")
        self.assertEqual(len(n), 1)

    def test_backoff_sleeps_between_tries(self):
        with mock.patch.object(transient, "BACKOFF", (1, 3)), mock.patch("time.sleep", self.sleeps.append):
            with self.assertRaises(transient.TrackerDown):
                transient.retry(mock.Mock(side_effect=TimeoutError("t")), "x")
        self.assertEqual(self.sleeps, [1, 3])


# ---------- Linear ----------

def lnode(i, state="unstarted", labels=("ready-for-agent",), comments=()):
    st = next(s for s in STATES if s["type"] == state)
    return {"id": f"uuid-{i}", "identifier": f"DAT-{i}", "number": i, "title": f"t{i}", "description": "",
            "url": f"https://linear.app/x/issue/DAT-{i}", "state": dict(st),
            "labels": {"nodes": [{"id": n, "name": n} for n in labels]},
            "comments": {"nodes": [{"body": b, "createdAt": f"2026-10-0{k + 1}T00:00"} for k, b in enumerate(comments)]},
            "inverseRelations": {"nodes": []}}


class FakeLinearAPI:
    """urlopen stand-in with state. faults: query text -> outcomes for the next calls of that query:
    'timeout' (nothing happens), 'timeout-after' (the write lands, the reply never comes), '503', '401'."""

    def __init__(self, *nodes):
        self.issues = {n["id"]: n for n in nodes}
        self.faults: dict[str, list[str]] = {}
        self.calls: list[str] = []

    def __call__(self, req, timeout=None):
        import linear_tracker as lt
        body = json.loads(req.data)
        q, v = body["query"], body["variables"]
        self.calls.append(q)
        fault = (self.faults.get(q) or [None]).pop(0) if self.faults.get(q) else None
        if fault == "timeout":
            raise TimeoutError("read timed out")
        if fault == "503":
            raise urllib.error.HTTPError("u", 503, "unavailable", {}, io.BytesIO(b"down"))
        if fault == "401":
            raise urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b"bad key"))
        data = self.handle(lt, q, v)
        if fault == "timeout-after":
            raise TimeoutError("read timed out")
        return io.BytesIO(json.dumps({"data": data}).encode())

    def handle(self, lt, q, v):
        if q == lt.Q_ISSUES:
            return {"issues": {"nodes": list(self.issues.values()), "pageInfo": {"hasNextPage": False, "endCursor": None}}}
        if q == lt.Q_ISSUE:
            return {"issue": self.issues[v["id"]]}
        if q == lt.Q_TEAM:
            return {"teams": {"nodes": [{"id": "t", "key": "DAT", "name": "DAT", "states": {"nodes": STATES},
                                         "labels": {"nodes": [{"id": "needs-human", "name": "needs-human"}]}}]},
                    "issueLabels": {"nodes": []}}
        if q == lt.Q_COMMENTS:
            return {"issue": {"comments": {"nodes": self.issues[v["id"]]["comments"]["nodes"][-25:]}}}
        if q == lt.M_UPDATE:
            n = self.issues[v["id"]]
            if "stateId" in v["input"]:
                n["state"] = dict(next(s for s in STATES if s["id"] == v["input"]["stateId"]))
            return {"issueUpdate": {"success": True}}
        if q == lt.M_COMMENT:
            n = self.issues[v["input"]["issueId"]]
            n["comments"]["nodes"].append({"body": v["input"]["body"], "createdAt": dt.datetime.now(dt.timezone.utc).isoformat()})
            return {"commentCreate": {"success": True}}
        raise ValueError("unknown query")

    def bodies(self, i=1):
        return [c["body"] for c in self.issues[f"uuid-{i}"]["comments"]["nodes"]]


class LinearRetry(Base):
    def tracker(self, api):
        self.patch = mock.patch("urllib.request.urlopen", api)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        return runway.make_tracker({"tracker": "linear", "linear": {"team": "DAT"}}, Path(tempfile.mkdtemp()))

    def test_timeout_once_then_success_does_not_end_the_call(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1))
        api.faults[lt.Q_ISSUE] = ["timeout"]
        tr = self.tracker(api)
        t = tr.load()[0]
        self.assertEqual(tr.reload(t).id, "DAT-1")
        self.assertEqual(api.calls.count(lt.Q_ISSUE), 2)

    def test_5xx_is_retried(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1))
        api.faults[lt.Q_ISSUES] = ["503", "503"]
        self.assertEqual(self.tracker(api).load()[0].id, "DAT-1")

    def test_auth_error_is_not_retried_and_keeps_its_message(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1))
        api.faults[lt.Q_ISSUES] = ["401"]
        with self.assertRaises(RuntimeError) as cm:
            self.tracker(api).load()
        self.assertIn("Linear API 401", str(cm.exception))
        self.assertEqual(api.calls.count(lt.Q_ISSUES), 1)

    def test_keeps_failing_raises_tracker_down(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1))
        api.faults[lt.Q_ISSUES] = ["timeout"] * 5
        with self.assertRaises(transient.TrackerDown) as cm:
            self.tracker(api).load()
        self.assertEqual(api.calls.count(lt.Q_ISSUES), transient.TRIES)
        self.assertIn("Linear", str(cm.exception))

    def test_comment_that_landed_before_the_timeout_is_not_posted_twice(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1))
        api.faults[lt.M_COMMENT] = ["timeout-after"]
        tr = self.tracker(api)
        tr.load()[0].mark_resolved("all done")
        self.assertEqual(api.bodies(), [MARK + " · all done"])

    def test_comment_that_never_landed_is_posted_on_retry(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1))
        api.faults[lt.M_COMMENT] = ["timeout"]
        self.tracker(api).load()[0].mark_resolved("all done")
        self.assertEqual(api.bodies(), [MARK + " · all done"])

    def test_close_that_landed_before_the_timeout_is_not_repeated(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1, state="started"))
        api.faults[lt.M_UPDATE] = ["timeout-after"]
        self.tracker(api).load()[0].mark_resolved("all done")
        self.assertEqual(api.calls.count(lt.M_UPDATE), 1)
        self.assertEqual(api.issues["uuid-1"]["state"]["type"], "completed")
        self.assertEqual(api.bodies(), [MARK + " · all done"])

    def test_close_that_never_landed_is_retried(self):
        import linear_tracker as lt
        api = FakeLinearAPI(lnode(1, state="started"))
        api.faults[lt.M_UPDATE] = ["timeout"]
        self.tracker(api).load()[0].mark_resolved("all done")
        self.assertEqual(api.calls.count(lt.M_UPDATE), 2)
        self.assertEqual(api.issues["uuid-1"]["state"]["type"], "completed")


# ---------- GitHub ----------

WRAP = '''#!/usr/bin/env python3
import atexit, os, sys, time
mf = os.environ["FAKE_GH_MODES"]
lines = open(mf).read().split() if os.path.exists(mf) else []
mode = lines.pop(0) if lines else "ok"
open(mf, "w").write(" ".join(lines))
with open(os.environ["FAKE_GH_LOG"] + ".modes", "a") as f:
    f.write(mode + "\\n")
if mode == "502":
    sys.stderr.write("HTTP 502: Bad Gateway\\n")
    sys.exit(1)
if mode == "reset":
    sys.stderr.write("read tcp 10.0.0.1:5000->140.82.1.1:443: read: connection reset by peer\\n")
    sys.exit(1)
if mode == "401":
    sys.stderr.write("To get started with GitHub CLI, please run:  gh auth login\\n")
    sys.exit(4)
if mode == "hang":
    time.sleep(30)
if mode == "write-then-hang":
    atexit.register(time.sleep, 30)
'''


class GitHubBase(Base):
    def setUp(self):
        super().setUp()
        self.dir = Path(tempfile.mkdtemp()).resolve()
        gh = self.dir / "gh"
        now = 'time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())'  # the fake stamps comments with the real clock
        gh.write_text(WRAP + FAKE_GH.replace('"2026-10-09T10:%02d:00Z" % k', now))
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        os.environ["FAKE_GH_DATA"] = str(self.dir / "data.json")
        os.environ["FAKE_GH_LOG"] = str(self.dir / "log")
        os.environ["FAKE_GH_MODES"] = str(self.dir / "modes")
        # The first run of a freshly written script can take over the 0.5s timeout below (macOS scans it),
        # which would kill attempt 1 before it logs. Run it once now, then forget that run.
        subprocess.run([str(gh), "--version"], capture_output=True, timeout=30)
        for leftover in ("log.modes", "modes"):
            (self.dir / leftover).unlink(missing_ok=True)
        self.cfg = {"tracker": "github", "github": {"repo": "o/r", "gh": str(gh), "timeout_s": 0.5}}

    def data(self, *issues):
        (self.dir / "data.json").write_text(json.dumps({"issues": list(issues)}))

    def modes(self, *names):
        (self.dir / "modes").write_text(" ".join(names))

    def gh_calls(self):
        p = self.dir / "log.modes"
        return p.read_text().split() if p.exists() else []

    def stored(self, n=1):
        return next(i for i in json.loads((self.dir / "data.json").read_text())["issues"] if i["number"] == n)

    def comments(self, n=1):
        return [c["body"] for c in self.stored(n)["comments"]["nodes"]]

    def tracker(self, root=None):
        return runway.make_tracker(self.cfg, root or self.dir)


class GitHubRetry(GitHubBase):
    def test_502_once_then_success_does_not_end_the_call(self):
        self.data(issue(1))
        self.modes("502")
        self.assertEqual([t.id for t in self.tracker().load()], ["#1"])
        self.assertEqual(self.gh_calls(), ["502", "ok"])

    def test_connection_reset_is_retried(self):
        self.data(issue(1))
        self.modes("reset", "reset")
        self.assertEqual([t.id for t in self.tracker().load()], ["#1"])

    def test_keeps_failing_raises_tracker_down(self):
        self.data(issue(1))
        self.modes("502", "502", "502", "502")
        with self.assertRaises(transient.TrackerDown) as cm:
            self.tracker().load()
        self.assertEqual(len(self.gh_calls()), transient.TRIES)
        self.assertIn("gh", str(cm.exception))

    def test_a_hung_gh_is_cut_off_by_its_timeout(self):
        self.data(issue(1))
        self.modes("hang", "hang", "hang")
        with self.assertRaises(transient.TrackerDown):
            self.tracker().load()
        self.assertEqual(self.gh_calls(), ["hang"] * transient.TRIES)

    def test_every_gh_call_has_a_default_timeout(self):
        self.data(issue(1))
        del self.cfg["github"]["timeout_s"]
        seen = {}
        real = subprocess.run

        def spy(*a, **kw):
            seen.update(kw)
            return real(*a, **kw)
        with mock.patch("subprocess.run", spy):
            self.tracker().load()
        self.assertGreater(seen.get("timeout") or 0, 0)

    def test_auth_error_still_stops_with_the_clear_message_and_no_retry(self):
        self.data(issue(1))
        self.modes("401")
        with self.assertRaises(SystemExit) as cm:
            self.tracker().load()
        self.assertIn("gh auth login", str(cm.exception))
        self.assertEqual(self.gh_calls(), ["401"])

    def test_comment_that_landed_before_the_hang_is_not_posted_twice(self):
        self.data(issue(1))
        self.modes("ok", "write-then-hang")  # load, then the comment lands but gh never returns
        t = self.tracker().load()[0]
        t.mark_resolved("all done")
        self.assertEqual(self.comments(), [MARK + " · all done"])
        self.assertEqual(self.stored()["state"], "CLOSED")

    def test_comment_that_never_landed_is_posted_on_retry(self):
        self.data(issue(1))
        self.modes("ok", "502")
        self.tracker().load()[0].mark_ready("back in the queue")
        self.assertEqual(self.comments(), [MARK + " · back in the queue"])

    def test_close_that_never_landed_is_retried(self):
        self.data(issue(1))
        self.modes("ok", "502")
        self.tracker().load()[0].mark_resolved("all done")
        self.assertEqual(self.stored()["state"], "CLOSED")
        self.assertEqual(self.comments(), [MARK + " · all done"])

    def test_close_whose_comment_landed_but_not_the_close_closes_without_a_second_comment(self):
        # gh posts the comment, then closes: a timeout between the two leaves a comment and an open issue.
        s = issue(1)
        s["comments"]["nodes"].append({"body": MARK + " · all done", "authorAssociation": "OWNER",
                                       "createdAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        self.data(s)
        self.modes("ok", "502")
        t = self.tracker().load()[0]
        t._close("completed", MARK + " · all done")
        self.assertEqual(self.stored()["state"], "CLOSED")
        self.assertEqual(self.comments(), [MARK + " · all done"])


# ---------- the tick ----------

class TickEndsCleanly(Base):
    def cfg(self, root):
        return dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))

    def tick(self, root, tracker):
        return runway.tick(self.cfg(root), root, tracker)

    def down(self, root, what="gh api graphql"):
        tr = runway.make_tracker(self.cfg(root), root)
        tr.load = mock.Mock(side_effect=transient.TrackerDown(what, TimeoutError("t")))
        return tr

    def test_tick_logs_one_line_and_waits_with_the_reason(self):
        root = self.root()
        self.assertFalse(self.tick(root, self.down(root)))
        s = state(root)
        self.assertEqual(s["phase"], "waiting")
        self.assertIn("gh api graphql", s["reason"])
        lines = [l for l in self.log_text(root).splitlines() if "waiting" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("gh api graphql", lines[0])

    def test_failing_ticks_notify_once_until_it_clears(self):
        root = self.root()
        for _ in range(3):
            self.tick(root, self.down(root))
        self.assertEqual(len(self.notified(root)), 1)
        self.tick(root, runway.make_tracker(self.cfg(root), root))  # tracker answers again
        self.tick(root, self.down(root))
        self.assertEqual(len(self.notified(root)), 2)

    def test_crash_mid_ticket_leaves_claim_and_worktree(self):
        root = make_repo({"01-thing": ""})
        os.environ["HB_ROOT"] = str(root)
        cfg = self.cfg(root)
        tr = runway.make_tracker(cfg, root)
        tr.reload = mock.Mock(side_effect=transient.TrackerDown("reload", TimeoutError("60s")))
        self.assertFalse(runway.tick(cfg, root, tr))  # no exception
        wts = (root / cfg["worktree_dir"]).resolve()
        self.assertTrue(any("01-thing" in p.name for p in wts.iterdir()), "the ticket's worktree is untouched")
        self.assertIn("Claimed-by", (root / ".scratch" / "eff" / "issues" / "01-thing.md").read_text())
        s = state(root)
        self.assertEqual((s["phase"], "reload" in s["reason"]), ("waiting", True))

    def run_cli(self, root, *args):
        return subprocess.run([sys.executable, runway.__file__, "--root", str(root), *args],
                              capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, RUNWAY_BACKOFF_S="0,0", RUNWAY_HOME=str(self.home)))

    def cli_root(self):
        root = self.root()
        gh = self.home / "gh"
        gh.write_text("#!/bin/sh\necho 'HTTP 503: unavailable' >&2\nexit 1\n")
        gh.chmod(0o755)
        cfg = json.loads((root / "runway.json").read_text())
        cfg.update(tracker="github", github={"repo": "o/r", "gh": str(gh)})
        (root / "runway.json").write_text(json.dumps(cfg))
        return root

    def test_tick_command_exits_zero_with_heartbeat_waiting(self):
        root = self.cli_root()
        r = self.run_cli(root, "tick")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state(root)["phase"], "waiting")

    def test_loop_command_exits_zero_and_does_not_run_finish(self):
        root = self.cli_root()
        r = self.run_cli(root, "loop", "--max-ticks", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(state(root)["phase"], "waiting")
        self.assertNotIn("idle", self.log_text(root))


# ---------- orphaned claims ----------

class Orphans(Base):
    ME = "Mini-One"

    def tick(self, root, tracker):
        ran = []
        cfg = dict(runway.DEFAULT_CONFIG, **json.loads((root / "runway.json").read_text()))
        with mock.patch.object(runway, "machine_name", return_value=self.ME), \
                mock.patch.object(runway, "run_ticket", side_effect=lambda c, r, tr, t: ran.append(t.id)), \
                mock.patch.object(runway, "sync_base", return_value=True):
            runway.tick(cfg, root, tracker)
        return ran


class LinearOrphans(Orphans):
    def setup_claim(self, by="Mini-One"):
        api = FakeLinearAPI(lnode(1, "started", comments=[CLAIM.format(by)]))
        p = mock.patch("urllib.request.urlopen", api)
        p.start()
        self.addCleanup(p.stop)
        root = self.root()
        cfg = json.loads((root / "runway.json").read_text())
        cfg.update(tracker="linear", linear={"team": "DAT"})
        (root / "runway.json").write_text(json.dumps(cfg))
        return api, root, runway.make_tracker(cfg, root)

    def test_dead_heartbeat_pid_releases_with_a_recovery_comment_then_runs(self):
        api, root, tr = self.setup_claim()
        self.beat_file(root, dead_pid(), "DAT-1", "check")
        self.assertEqual(self.tick(root, tr), ["DAT-1"])
        self.assertEqual(api.issues["uuid-1"]["state"]["type"], "unstarted")
        self.assertIn("recovered after a crash", api.bodies()[-1])
        self.assertTrue(api.bodies()[-1].startswith(MARK))

    def test_heartbeat_naming_another_ticket_is_an_orphan(self):
        api, root, tr = self.setup_claim()
        self.beat_file(root, self.live_pid(), "DAT-9")
        self.assertEqual(self.tick(root, tr), ["DAT-1"])
        self.assertIn("recovered after a crash", api.bodies()[-1])

    def test_no_heartbeat_at_all_is_an_orphan(self):
        api, root, tr = self.setup_claim()
        self.assertEqual(self.tick(root, tr), ["DAT-1"])

    def test_claim_held_by_a_live_process_is_left_alone(self):
        api, root, tr = self.setup_claim()
        self.beat_file(root, self.live_pid(), "DAT-1")
        self.assertEqual(self.tick(root, tr), [])
        self.assertEqual(api.issues["uuid-1"]["state"]["type"], "started")
        self.assertEqual(len(api.bodies()), 1)

    def test_claim_by_another_mac_is_left_alone(self):
        api, root, tr = self.setup_claim(by="Mini-Two")
        self.beat_file(root, dead_pid(), "DAT-1")
        self.assertEqual(self.tick(root, tr), [])
        self.assertEqual(api.issues["uuid-1"]["state"]["type"], "started")
        self.assertEqual(len(api.bodies()), 1)


class GitHubOrphans(GitHubBase, Orphans):
    def setup_claim(self, by="Mini-One"):
        self.data(issue(1, assignees=1, comments=[(CLAIM.format(by), "OWNER")]))
        root = self.root()
        cfg = json.loads((root / "runway.json").read_text())
        cfg.update(self.cfg)
        (root / "runway.json").write_text(json.dumps(cfg))
        return root, runway.make_tracker(cfg, root)

    def test_dead_heartbeat_pid_releases_with_a_recovery_comment_then_runs(self):
        root, tr = self.setup_claim()
        self.beat_file(root, dead_pid(), "#1", "check")
        self.assertEqual(self.tick(root, tr), ["#1"])
        self.assertEqual(self.stored()["assignees"]["totalCount"], 0)
        self.assertIn("recovered after a crash", self.comments()[-1])

    def test_claim_held_by_a_live_process_is_left_alone(self):
        root, tr = self.setup_claim()
        self.beat_file(root, self.live_pid(), "#1")
        self.assertEqual(self.tick(root, tr), [])
        self.assertEqual(self.stored()["assignees"]["totalCount"], 1)
        self.assertEqual(len(self.comments()), 1)

    def test_claim_by_another_mac_is_left_alone(self):
        root, tr = self.setup_claim(by="Mini-Two")
        self.beat_file(root, dead_pid(), "#1")
        self.assertEqual(self.tick(root, tr), [])
        self.assertEqual(self.stored()["assignees"]["totalCount"], 1)


if __name__ == "__main__":
    unittest.main()
