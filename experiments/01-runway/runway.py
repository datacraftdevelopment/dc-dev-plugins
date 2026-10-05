#!/usr/bin/env python3
"""Runway: a minimal judgment-aware task runner for a pm-style tracker.

The loop never waits on Joe. Each tick it:
  1. Preps a decision packet for every human-gated ticket that is (or will soon be)
     on the frontier, and parks it as needs-human. Joe answers in the tracker
     (or with `runway go NN`), and the next tick picks the answer up.
  2. Runs the next ready auto ticket: agent in a git worktree on its own branch,
     then the check command. Pass -> merged into the integration branch, resolved.
     Fail -> one retry with the failure output, then parked as needs-human.

Trackers (config key "tracker"):
  markdown (default)  pm's local markdown (.scratch/<effort>/issues/NN-slug.md) with
                      one extra header line: `Gate: human` or `Gate: auto` (default).
  linear              Linear issues, through linear_tracker.py. See its docstring.

The base branch is never touched; Joe merges the integration branch himself.

No dependencies beyond Python 3.9+ and git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

HEADER_RE = re.compile(r"^(Status|Blocked by|Waiting on|Gate|Type|Branch):\s*(.*)$", re.M)
DONE = {"resolved", "done", "closed"}
RUNNABLE_GATES = ("auto", "approved")
DEFAULT_CONFIG = {
    # "markdown" or "linear". Linear settings live under the "linear" key.
    "tracker": "markdown",
    # Prompt goes to the agent on stdin. Headless Claude Code by default.
    "agent_cmd": "claude -p --permission-mode acceptEdits",
    # Read-only prep agent. Its stdout becomes the decision packet.
    "prep_cmd": "claude -p --permission-mode plan",
    # Runs in the worktree after the agent. Exit 0 means the ticket passed.
    "check_cmd": "true",
    "integration_branch": "runway/integration",
    "base_branch": "main",
    "worktree_dir": "../.runway-worktrees",
    "max_attempts": 2,
    # Optional, e.g. osascript -e 'display notification "{msg}" with title "Runway"'
    "notify_cmd": "",
    "agent_timeout_s": 3600,
}


def now() -> str:
    # Timezone-aware, so the log lines up with UTC timestamps elsewhere.
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")


def sh(cmd, cwd: Path, stdin: str | None = None, timeout: int | None = None, check=False):
    args = shlex.split(cmd) if isinstance(cmd, str) else cmd
    r = subprocess.run(args, cwd=cwd, input=stdin, text=True, capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed in {cwd}:\n{r.stdout}\n{r.stderr}")
    return r


def log(root: Path, msg: str) -> None:
    line = f"{now()}  {msg}"
    print(line)
    p = root / "_pm" / "runway.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(line + "\n")


# ---------- markdown tracker ----------

class Ticket:
    """A ticket in pm's local markdown tracker. Other trackers mirror this interface:
    id, num, effort, slug, ref, title, text, status, gate, blocked_by, h(),
    post_packet(), mark_claimed(), mark_resolved(), mark_needs_human(), approve(), decline()."""

    def __init__(self, path: Path, root: Path | None = None):
        self.path = path
        self.root = root or path.parents[3]
        self.num = path.name.split("-", 1)[0]
        self.effort = path.parent.parent.name
        self.slug = path.stem
        self.text = path.read_text()

    def h(self, key: str, default: str = "") -> str:
        for k, v in HEADER_RE.findall(self.text):
            if k == key:
                return v.strip()
        return default

    @property
    def id(self) -> str:
        return f"{self.effort}/{self.num}"

    @property
    def ref(self) -> str:
        return str(self.path.relative_to(self.root))

    @property
    def status(self) -> str:
        return self.h("Status", "ready").lower()

    @property
    def gate(self) -> str:
        return self.h("Gate", "auto").lower()

    @property
    def blocked_by(self) -> list[str]:
        raw = self.h("Blocked by")
        return [b.strip().zfill(2) for b in re.split(r"[,\s]+", raw) if b.strip().isdigit()]

    @property
    def title(self) -> str:
        m = re.search(r"^#\s+(.+)$", self.text, re.M)
        return m.group(1).strip() if m else self.path.stem

    def set(self, key: str, value: str | None) -> None:
        pat = re.compile(rf"^{re.escape(key)}:.*$", re.M)
        if value is None:
            self.text = pat.sub("", self.text).replace("\n\n\n", "\n\n")
        elif pat.search(self.text):
            self.text = pat.sub(f"{key}: {value}", self.text, count=1)
        else:
            # insert after the last existing header line (or after the title)
            lines = self.text.splitlines(keepends=True)
            heads = [i for i, l in enumerate(lines) if HEADER_RE.match(l.rstrip("\n"))]
            idx = heads[-1] + 1 if heads else (1 if lines and lines[0].startswith("#") else 0)
            lines.insert(idx, f"{key}: {value}\n")
            self.text = "".join(lines)

    def comment(self, body: str) -> None:
        if "## Comments" not in self.text:
            self.text = self.text.rstrip() + "\n\n## Comments\n"
        self.text = self.text.rstrip() + f"\n\n**{now()} · runway**\n\n{body.strip()}\n"

    def save(self) -> None:
        self.path.write_text(self.text)

    # -- lifecycle (what the loop calls) --

    def post_packet(self, packet: str) -> None:
        self.text = self.text.rstrip() + (
            f"\n\n## Decision packet\n\n_Prepared {now()} by runway. Answer with `runway go {self.num}` "
            f"or `runway no {self.num} \"reason\"`._\n\n{packet}\n")
        self.set("Status", "needs-human")
        self.set("Waiting on", f"Joe, go/no-go on the decision packet, since {now()}")
        self.save()

    def mark_claimed(self, branch: str) -> None:
        self.set("Status", "claimed")
        self.set("Branch", branch)
        self.save()

    def mark_resolved(self, note: str) -> None:
        self.set("Status", "resolved")
        self.comment(note)
        self.save()

    def mark_needs_human(self, why: str, detail: str) -> None:
        self.set("Status", "needs-human")
        self.set("Waiting on", f"Joe, {why}, since {now()}")
        self.comment(detail)
        self.save()

    def approve(self, note: str) -> None:
        self.set("Status", "ready")
        self.set("Gate", "approved")
        self.set("Waiting on", None)
        self.comment(f"Joe: go. {note}".strip())
        self.save()

    def decline(self, note: str) -> None:
        drop = note.lower().startswith("drop")
        self.set("Status", "resolved" if drop else "needs-human")
        self.set("Waiting on", None if drop else f"Joe said no: {note}")
        self.comment(f"Joe: no. {note}".strip())
        self.save()


class MarkdownTracker:
    def __init__(self, root: Path, cfg: dict):
        self.root = root

    def load(self) -> list[Ticket]:
        return [Ticket(p, self.root) for p in sorted(self.root.glob(".scratch/*/issues/*.md"))]

    def reload(self, t: Ticket) -> Ticket:
        return Ticket(t.path, self.root)

    def sync(self) -> None:
        """Pick up answers Joe left in the tracker. Markdown answers arrive via `runway go`."""


def make_tracker(cfg: dict, root: Path):
    kind = cfg.get("tracker", "markdown")
    if kind == "markdown":
        return MarkdownTracker(root, cfg)
    if kind == "linear":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from linear_tracker import LinearTracker
        return LinearTracker(root, cfg)
    sys.exit(f"Unknown tracker {kind!r}; use 'markdown' or 'linear'.")


# ---------- frontier ----------

def by_num(tickets: list, t) -> dict:
    return {x.num: x for x in tickets if x.effort == t.effort}


def unblocked(t, tickets: list) -> bool:
    peers = by_num(tickets, t)
    return all(peers.get(b) is None or peers[b].status in DONE for b in t.blocked_by)


def will_unblock_without_joe(t, tickets: list, seen=None) -> bool:
    """True if every open blocker is auto work the loop can finish on its own."""
    seen = seen or set()
    peers = by_num(tickets, t)
    for b in t.blocked_by:
        p = peers.get(b)
        if p is None or p.status in DONE:
            continue
        if p.id in seen or p.gate not in RUNNABLE_GATES or p.status == "needs-human":
            return False
        if not will_unblock_without_joe(p, tickets, seen | {p.id}):
            return False
    return True


def notify(cfg: dict, root: Path, msg: str) -> None:
    log(root, msg)
    if cfg.get("notify_cmd"):
        sh(cfg["notify_cmd"].replace("{msg}", msg.replace('"', "'")), root)


# ---------- prep: the judgment lookahead ----------

PREP_PROMPT = """You are preparing a decision for Joe. Do NOT change any files.
Read the ticket below and the repository, then write a decision packet in Markdown
with exactly these sections:

### Decision needed
One sentence Joe can answer with "go", "no", or a one-word choice.
### Options
2-3 options, one line each, with what happens if chosen. Mark your recommendation.
### What the agent will do on "go"
The concrete plan, files likely touched, and how it will be checked.
### Risks / one-way doors
Anything hard to undo. Say "none" if none.
### Context Joe needs
At most 5 bullets. No investigation narrative.

Ticket ({path}):

{ticket}
"""


def prep(cfg: dict, root: Path, t) -> None:
    log(root, f"prep  {t.id} {t.title}")
    r = sh(cfg["prep_cmd"], root, stdin=PREP_PROMPT.format(path=t.ref, ticket=t.text),
           timeout=cfg["agent_timeout_s"])
    packet = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else f"Prep failed:\n\n```\n{r.stderr[-2000:]}\n```"
    t.post_packet(packet)
    notify(cfg, root, f"Decision ready: {t.id} {t.title}")


# ---------- run: the AFK lane ----------

RUN_PROMPT = """Implement this ticket in the current repository (a git worktree on its own branch).
Stay inside the ticket's scope. Commit your work with a clear message when done.
If you cannot finish without a human decision, write the question to RUNWAY_QUESTION.md
at the repo root and stop.

Ticket ({path}):

{ticket}
{extra}"""


def ensure_integration(cfg: dict, root: Path) -> None:
    br = cfg["integration_branch"]
    if sh(["git", "rev-parse", "--verify", br], root).returncode != 0:
        sh(["git", "branch", br, cfg["base_branch"]], root, check=True)


def run_ticket(cfg: dict, root: Path, tracker, t) -> None:
    ensure_integration(cfg, root)
    branch = f"runway/{t.effort}-{t.slug}"
    wt = (root / cfg["worktree_dir"] / f"{t.effort}-{t.slug}").resolve()
    t.mark_claimed(branch)
    log(root, f"run   {t.id} {t.title}  -> {branch}")

    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
    sh(["git", "branch", "-D", branch], root)
    sh(["git", "worktree", "add", "-b", branch, str(wt), cfg["integration_branch"]], root, check=True)

    extra, ok, detail = "", False, ""
    for attempt in range(1, cfg["max_attempts"] + 1):
        prompt = RUN_PROMPT.format(path=t.ref, ticket=t.text, extra=extra)
        sh(cfg["agent_cmd"], wt, stdin=prompt, timeout=cfg["agent_timeout_s"])
        q = wt / "RUNWAY_QUESTION.md"
        if q.exists():
            detail = "Agent stopped with a question:\n\n" + q.read_text()
            break
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-m", f"runway: {t.title} (auto-commit)"], wt)
        c = sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])
        if c.returncode == 0:
            ok = True
            break
        detail = f"Check failed on attempt {attempt}:\n\n```\n{(c.stdout + c.stderr)[-3000:]}\n```"
        extra = f"\nThe previous attempt failed the check. Fix it:\n\n{detail}\n"
        log(root, f"fail  {t.id} attempt {attempt}")

    t = tracker.reload(t)  # agent may not touch it, but reload to be safe
    if ok:
        if merge_into_integration(cfg, root, branch):
            t.mark_resolved(f"Done on `{branch}`, check passed, merged into `{cfg['integration_branch']}`.")
            log(root, f"done  {t.id}")
        else:
            ok = False
            detail = f"Check passed but `{branch}` did not merge cleanly into `{cfg['integration_branch']}`."
    if not ok:
        t.mark_needs_human("run failed or asked a question", detail or "Agent run failed with no detail.")
        notify(cfg, root, f"Blocked: {t.id} {t.title}")
    sh(["git", "worktree", "remove", "--force", str(wt)], root)


def merge_into_integration(cfg: dict, root: Path, branch: str) -> bool:
    """Merge in a throwaway worktree so the user's checkout is never disturbed."""
    tmp = (root / cfg["worktree_dir"] / "_integration").resolve()
    if not tmp.exists():
        sh(["git", "worktree", "add", str(tmp), cfg["integration_branch"]], root, check=True)
    r = sh(["git", "merge", "--no-ff", "-m", f"runway: merge {branch}", branch], tmp)
    if r.returncode != 0:
        sh(["git", "merge", "--abort"], tmp)
        return False
    return True


# ---------- commands ----------

def tick(cfg: dict, root: Path, tracker) -> bool:
    """One pass. Returns True if it did anything."""
    did = False
    tracker.sync()
    tickets = tracker.load()
    # 1. Judgment lookahead: prep every gated ticket that is on, or headed for, the frontier.
    for t in tickets:
        if t.gate == "human" and t.status == "ready" and will_unblock_without_joe(t, tickets):
            prep(cfg, root, t)
            did = True
    # 2. AFK lane: run the first ready auto (or approved) ticket.
    tickets = tracker.load()
    for t in tickets:
        if t.status == "ready" and t.gate in RUNNABLE_GATES and unblocked(t, tickets):
            run_ticket(cfg, root, tracker, t)
            return True
    return did


def cmd_status(tracker) -> None:
    tickets = tracker.load()
    groups = {"Waiting on you": [], "Running": [], "Ready (auto)": [], "Ready (needs prep)": [], "Blocked": [], "Done": []}
    for t in tickets:
        if t.gate not in RUNNABLE_GATES + ("human",):
            continue  # not Runway's (e.g. a wayfinder decision ticket)
        if t.status == "needs-human":
            groups["Waiting on you"].append(t)
        elif t.status == "claimed":
            groups["Running"].append(t)
        elif t.status in DONE:
            groups["Done"].append(t)
        elif not unblocked(t, tickets) and t.gate != "human":
            groups["Blocked"].append(t)
        elif t.gate == "human":
            groups["Ready (needs prep)"].append(t)
        else:
            groups["Ready (auto)"].append(t)
    for name, ts in groups.items():
        print(f"\n{name} ({len(ts)})")
        for t in ts:
            extra = f"  [{t.h('Waiting on')}]" if name == "Waiting on you" and t.h("Waiting on") else ""
            print(f"  {t.id:<24} {t.title}{extra}")


def find(tracker, num: str):
    key = num.zfill(2) if num.isdigit() else num
    hits = [t for t in tracker.load() if t.num == key or t.id == key or t.id.endswith("/" + key)]
    if len(hits) != 1:
        sys.exit(f"Expected one ticket for {num!r}, found {[t.id for t in hits]}. Use effort/NN.")
    return hits[0]


def cmd_answer(root: Path, tracker, num: str, go: bool, note: str) -> None:
    t = find(tracker, num)
    t.approve(note) if go else t.decline(note)
    log(root, f"answer {t.id} {'go' if go else 'no'} {note}")


def locked(root: Path):
    """Non-blocking lock so a scheduled tick never overlaps a running one."""
    import fcntl
    p = root / "_pm" / "runway.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    f = p.open("w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="target repo (git checkout Runway works in)")
    ap.add_argument("--config", help="JSON config (default: <root>/runway.json if present)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("tick")
    lp = sub.add_parser("loop")
    lp.add_argument("--max-ticks", type=int, default=50)
    g = sub.add_parser("go"); g.add_argument("ticket"); g.add_argument("note", nargs="?", default="")
    n = sub.add_parser("no"); n.add_argument("ticket"); n.add_argument("note", nargs="?", default="")
    sub.add_parser("setup", help="Linear only: check the key, team and project, and create Runway's labels")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    cfg = dict(DEFAULT_CONFIG)
    cfg_path = Path(a.config) if a.config else root / "runway.json"
    if cfg_path.exists():
        cfg.update(json.loads(cfg_path.read_text()))
    tracker = make_tracker(cfg, root)

    if a.cmd == "status":
        cmd_status(tracker)
    elif a.cmd == "setup":
        if not hasattr(tracker, "setup"):
            sys.exit("setup is only needed for the linear tracker.")
        tracker.setup()
    elif a.cmd in ("tick", "loop"):
        lock = locked(root)
        if lock is None:
            print("Another Runway run holds the lock; skipping.")
            return
        if a.cmd == "tick":
            tick(cfg, root, tracker)
        else:
            for _ in range(a.max_ticks):
                if not tick(cfg, root, tracker):
                    log(root, "idle  nothing ready without Joe")
                    break
            cmd_status(tracker)
    elif a.cmd in ("go", "no"):
        cmd_answer(root, tracker, a.ticket, a.cmd == "go", a.note)


if __name__ == "__main__":
    main()
