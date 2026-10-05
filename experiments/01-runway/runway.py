#!/usr/bin/env python3
"""Runway: a minimal judgment-aware task runner for a pm-style tracker.

The loop never waits on Joe. Each tick it:
  1. Preps a decision packet for every human-gated ticket that is (or will soon be)
     on the frontier, and parks it as needs-human. Joe answers with `runway go NN`.
  2. Runs the next ready auto ticket: agent in a git worktree on its own branch,
     then the check command. Pass -> merged into the integration branch, resolved.
     Fail -> one retry with the failure output, then parked as needs-human.

Tracker format is pm's local markdown (.scratch/<effort>/issues/NN-slug.md) with
one extra header line: `Gate: human` (needs Joe's go) or `Gate: auto` (default).
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
DEFAULT_CONFIG = {
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
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


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


class Ticket:
    def __init__(self, path: Path):
        self.path = path
        self.num = path.name.split("-", 1)[0]
        self.effort = path.parent.parent.name
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


def load(root: Path) -> list[Ticket]:
    return [Ticket(p) for p in sorted(root.glob(".scratch/*/issues/*.md"))]


def by_num(tickets: list[Ticket], t: Ticket) -> dict[str, Ticket]:
    return {x.num: x for x in tickets if x.effort == t.effort}


def unblocked(t: Ticket, tickets: list[Ticket]) -> bool:
    peers = by_num(tickets, t)
    return all(peers.get(b) is None or peers[b].status in DONE for b in t.blocked_by)


def will_unblock_without_joe(t: Ticket, tickets: list[Ticket], seen=None) -> bool:
    """True if every open blocker is auto work the loop can finish on its own."""
    seen = seen or set()
    peers = by_num(tickets, t)
    for b in t.blocked_by:
        p = peers.get(b)
        if p is None or p.status in DONE:
            continue
        if p.id in seen or p.gate == "human" or p.status == "needs-human":
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


def prep(cfg: dict, root: Path, t: Ticket) -> None:
    log(root, f"prep  {t.id} {t.title}")
    r = sh(cfg["prep_cmd"], root, stdin=PREP_PROMPT.format(path=t.path.relative_to(root), ticket=t.text),
           timeout=cfg["agent_timeout_s"])
    packet = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else f"Prep failed:\n\n```\n{r.stderr[-2000:]}\n```"
    t.text = t.text.rstrip() + f"\n\n## Decision packet\n\n_Prepared {now()} by runway. Answer with `runway go {t.num}` or `runway no {t.num} \"reason\"`._\n\n{packet}\n"
    t.set("Status", "needs-human")
    t.set("Waiting on", f"Joe, go/no-go on the decision packet, since {now()}")
    t.save()
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


def run_ticket(cfg: dict, root: Path, t: Ticket) -> None:
    ensure_integration(cfg, root)
    slug = t.path.stem
    branch = f"runway/{t.effort}-{slug}"
    wt = (root / cfg["worktree_dir"] / f"{t.effort}-{slug}").resolve()
    t.set("Status", "claimed")
    t.set("Branch", branch)
    t.save()
    log(root, f"run   {t.id} {t.title}  -> {branch}")

    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
    sh(["git", "branch", "-D", branch], root)
    sh(["git", "worktree", "add", "-b", branch, str(wt), cfg["integration_branch"]], root, check=True)

    extra, ok, detail = "", False, ""
    for attempt in range(1, cfg["max_attempts"] + 1):
        prompt = RUN_PROMPT.format(path=t.path.relative_to(root), ticket=t.text, extra=extra)
        a = sh(cfg["agent_cmd"], wt, stdin=prompt, timeout=cfg["agent_timeout_s"])
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

    t = Ticket(t.path)  # agent may not touch it, but reload to be safe
    if ok:
        merged = merge_into_integration(cfg, root, branch)
        if merged:
            t.set("Status", "resolved")
            t.comment(f"Done on `{branch}`, check passed, merged into `{cfg['integration_branch']}`.")
            log(root, f"done  {t.id}")
        else:
            ok = False
            detail = f"Check passed but `{branch}` did not merge cleanly into `{cfg['integration_branch']}`."
    if not ok:
        t.set("Status", "needs-human")
        t.set("Waiting on", f"Joe, run failed or asked a question, since {now()}")
        t.comment(detail or "Agent run failed with no detail.")
        notify(cfg, root, f"Blocked: {t.id} {t.title}")
    t.save()
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

def tick(cfg: dict, root: Path) -> bool:
    """One pass. Returns True if it did anything."""
    did = False
    tickets = load(root)
    # 1. Judgment lookahead: prep every gated ticket that is on, or headed for, the frontier.
    for t in tickets:
        if t.gate == "human" and t.status == "ready" and will_unblock_without_joe(t, tickets):
            prep(cfg, root, t)
            did = True
    # 2. AFK lane: run the first ready auto (or approved) ticket.
    tickets = load(root)
    for t in tickets:
        if t.status == "ready" and t.gate in ("auto", "approved") and unblocked(t, tickets):
            run_ticket(cfg, root, t)
            return True
    return did


def cmd_status(root: Path) -> None:
    tickets = load(root)
    groups = {"Waiting on you": [], "Running": [], "Ready (auto)": [], "Ready (needs prep)": [], "Blocked": [], "Done": []}
    for t in tickets:
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
            extra = f"  [{t.h('Waiting on')}]" if name == "Waiting on you" else ""
            print(f"  {t.id:<24} {t.title}{extra}")


def find(root: Path, num: str) -> Ticket:
    num = num.zfill(2)
    hits = [t for t in load(root) if t.num == num or t.id == num or t.id.endswith("/" + num)]
    if len(hits) != 1:
        sys.exit(f"Expected one ticket for {num!r}, found {[t.id for t in hits]}. Use effort/NN.")
    return hits[0]


def cmd_answer(root: Path, num: str, go: bool, note: str) -> None:
    t = find(root, num)
    if go:
        t.set("Status", "ready")
        t.set("Gate", "approved")
        t.set("Waiting on", None)
        t.comment(f"Joe: go. {note}".strip())
    else:
        t.set("Status", "resolved" if note.lower().startswith("drop") else "needs-human")
        t.set("Waiting on", f"Joe said no: {note}" if not note.lower().startswith("drop") else None)
        t.comment(f"Joe: no. {note}".strip())
    t.save()
    log(root, f"answer {t.id} {'go' if go else 'no'} {note}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="target repo (pm-style .scratch tracker)")
    ap.add_argument("--config", help="JSON config (default: <root>/runway.json if present)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("tick")
    lp = sub.add_parser("loop")
    lp.add_argument("--max-ticks", type=int, default=50)
    g = sub.add_parser("go"); g.add_argument("ticket"); g.add_argument("note", nargs="?", default="")
    n = sub.add_parser("no"); n.add_argument("ticket"); n.add_argument("note", nargs="?", default="")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    cfg = dict(DEFAULT_CONFIG)
    cfg_path = Path(a.config) if a.config else root / "runway.json"
    if cfg_path.exists():
        cfg.update(json.loads(cfg_path.read_text()))

    if a.cmd == "status":
        cmd_status(root)
    elif a.cmd == "tick":
        tick(cfg, root)
    elif a.cmd == "loop":
        for _ in range(a.max_ticks):
            if not tick(cfg, root):
                log(root, "idle  nothing ready without Joe")
                break
        cmd_status(root)
    elif a.cmd in ("go", "no"):
        cmd_answer(root, a.ticket, a.cmd == "go", a.note)


if __name__ == "__main__":
    main()
