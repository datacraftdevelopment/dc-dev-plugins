"""chores.json is what the app's Chores section reads: valid, versioned, and every entry well formed."""
import json
import re
from pathlib import Path

CHORES = Path(__file__).resolve().parents[1] / "chores.json"


def load():
    return json.loads(CHORES.read_text())


def test_version_and_list():
    data = load()
    assert data["version"] == 1
    assert isinstance(data["chores"], list) and data["chores"]


def test_every_chore_is_well_formed():
    seen = set()
    for chore in load()["chores"]:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", chore["id"]), chore
        assert chore["id"] not in seen
        seen.add(chore["id"])
        for key in ("title", "why", "run"):
            assert isinstance(chore[key], str) and chore[key].strip(), (chore["id"], key)
        assert chore["cwd"] in ("checkout", "repo"), chore["id"]
        assert isinstance(chore.get("show_if", ""), str)
        assert isinstance(chore.get("confirm", False), bool)
        assert set(chore) <= {"id", "title", "why", "run", "cwd", "show_if", "confirm"}, chore["id"]


def test_no_chore_touches_launch_agents_or_worker_permissions():
    for chore in load()["chores"]:
        text = chore["run"] + chore.get("show_if", "")
        for banned in ("launchctl", "schedule.sh", "LaunchAgents", "agent_cmd", "runway.json"):
            assert banned not in text, (chore["id"], banned)


def test_placeholders_are_known():
    for chore in load()["chores"]:
        for name in re.findall(r"\{(\w+)\}", chore["run"]):
            assert name in ("runway", "repo", "checkout"), (chore["id"], name)
        if "{repo}" in chore["run"]:
            assert chore["cwd"] == "repo", chore["id"]
