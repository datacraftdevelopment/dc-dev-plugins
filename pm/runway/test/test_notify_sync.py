"""notify() survives quotes in a message; tick() merges base into integration first."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "runway.py"
spec = importlib.util.spec_from_file_location("runway_engine", ENGINE)
runway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runway)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "runway@example.com")
    git(root, "config", "user.name", "runway")
    (root / ".gitignore").write_text("_pm/\n")
    (root / "a.txt").write_text("one\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    cfg = dict(runway.DEFAULT_CONFIG)
    return root, cfg


def test_notify_with_apostrophe_and_double_quote(tmp_path):
    out = tmp_path / "argv.json"
    writer = tmp_path / "w.py"
    writer.write_text(f"import json, sys; open({str(out)!r}, 'w').write(json.dumps(sys.argv[1:]))\n")
    cfg = {"notify_cmd": f"{sys.executable} {writer} -e 'display notification \"{{msg}}\" with title \"Runway\"'"}
    (tmp_path / "_pm").mkdir()
    runway.notify(cfg, tmp_path, 'Blocked: DAT-18 the factory plugin\'s "runway" skill')
    assert json.loads(out.read_text()) == [
        "-e", "display notification \"Blocked: DAT-18 the factory plugin's 'runway' skill\" with title \"Runway\""]


def test_sync_merges_new_base_commits(tmp_path):
    root, cfg = make_repo(tmp_path)
    assert runway.sync_base(cfg, root)  # creates integration, nothing to merge
    (root / "b.txt").write_text("new on main\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "main moves")
    assert runway.sync_base(cfg, root)
    assert git(root, "show", "runway/integration:b.txt") == "new on main"
    assert "sync  merged main into runway/integration" in (root / "_pm" / "runway.log").read_text()


def test_sync_conflict_aborts_and_skips_tickets(tmp_path, monkeypatch):
    root, cfg = make_repo(tmp_path)
    runway.ensure_integration(cfg, root)
    wt = runway.integration_worktree(cfg, root)
    (wt / "a.txt").write_text("integration\n")
    git(wt, "commit", "-qam", "integration edit")
    (root / "a.txt").write_text("main\n")
    git(root, "commit", "-qam", "main edit")
    integ_head = git(root, "rev-parse", "runway/integration")

    notes = []
    monkeypatch.setattr(runway, "notify", lambda c, r, m: notes.append(m))
    ran = []
    monkeypatch.setattr(runway, "run_ticket", lambda *a: ran.append(a))
    monkeypatch.setattr(runway, "signin_waiting_for_work", lambda *a: False)

    class Tracker:
        def sync(self): pass
        def load(self):
            t = type("T", (), {"gate": "auto", "status": "ready", "blocked_by": [], "id": "X-1", "num": "1"})()
            return [t]

    assert runway.tick(cfg, root, Tracker()) is False
    assert ran == []
    assert git(root, "rev-parse", "runway/integration") == integ_head
    assert git(wt, "status", "--porcelain") == ""
    assert len(notes) == 1 and "does not merge cleanly" in notes[0]
    runway.tick(cfg, root, Tracker())  # same base head: logged, not re-notified
    assert len(notes) == 1
