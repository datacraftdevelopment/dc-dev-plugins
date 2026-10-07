#!/usr/bin/env python3
"""Runway: a minimal judgment-aware task runner for a pm-style tracker.

The loop never waits on Joe. Each tick it:
  1. Preps a decision packet for every human-gated ticket that is (or will soon be)
     on the frontier, and parks it as needs-human. Joe answers in the tracker
     (or with `runway go NN`), and the next tick picks the answer up.
  2. Runs the next ready auto ticket: agent in a git worktree on its own branch,
     then the check command. Pass -> merged into the integration branch, resolved.
     Fail -> one retry with the failure output, then parked as needs-human.

When the queue is finished, `loop` runs a finish step once per integration head:
a review of the whole branch against the tickets, one fix pass, the check, and a
PR body (written to _pm/runway-pr.md, or opened as a draft PR with "pr": "draft").

Every agent call is logged to _pm/runway-runs.jsonl with its session id and token
usage when the agent prints Claude Code's JSON output. `runway retro` turns that log
into a /retro prompt pointing at the runs that struggled.

While it works, Runway keeps `_pm/runway-state.json` current, so the app can show what it is
doing right now. Written atomically (temp file + rename) at every phase change:

  {"version": 1, "phase": "sync|prep|agent|check|merge|finish|idle|stopped", "ticket": "DAT-11 or null",
   "attempt": 1, "since": "ISO-8601", "pid": 12345, "agent_pid": 12346, "tick_started": "ISO-8601",
   "last_result": "pass|fail|park|null"}

  since        When this phase began. tick_started: when the current tick began.
  attempt      Agent attempt number during agent and check, else null.
  agent_pid    The agent's child process while one runs (agent, prep, finish), else null.
  last_result  pass = last ticket merged, fail = a check failed (a retry may follow), park = last
               ticket parked as needs-human.
  idle         Written on a normal exit. A crash leaves the last phase behind, so a reader tells a
               stale file from a live one by whether `pid` is still running. stopped = Ctrl-C.

`runway status --json` prints the queue as one JSON object, the contract the Mac app reads.
Version 1 (additive changes keep the version; renames or removals bump it):

  {"version": 1, "repo": "/abs/path", "tracker": "markdown|linear", "generated_at": "ISO-8601",
   "groups": {"waiting": [id...], "running": [...], "ready_auto": [...],
              "ready_prep": [...], "blocked": [...], "done": [...]},
   "tickets": [{"id", "title", "url", "status", "gate", "blocked_by": [id...],
                "waiting_on", "packet", "harness"}]}

  groups   Ticket ids in queue order (the order `tick` would take them), same grouping as the
           text output: waiting = "Waiting on you", ready_prep = "Ready (needs prep)".
  tickets  One entry per Runway ticket (gate auto, human or approved), in tracker order.
  id       Linear identifier ("DAT-12") or markdown "<effort>/<NN>".
  url      Linear issue URL; markdown: the file path relative to the repo. null if unknown.
  status   resolved, claimed, needs-human or ready (markdown may carry other values as written).
  gate     auto, human or approved.
  blocked_by  Ids, in the same form as id.
  waiting_on  Who or what the ticket waits on, or null.
  packet   Latest decision packet text for waiting tickets (Linear: Runway's latest comment;
           markdown: the last "## Decision packet" section), else null.
  harness  Reserved, always null for now.

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
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

HEADER_RE = re.compile(r"^(Status|Blocked by|Waiting on|Gate|Type|Branch):\s*(.*)$", re.M)
DONE = {"resolved", "done", "closed"}
RUNNABLE_GATES = ("auto", "approved")
DEFAULT_CONFIG = {
    # "markdown" or "linear". Linear settings live under the "linear" key.
    "tracker": "markdown",
    # Prompt goes to the agent on stdin. Headless Claude Code by default. With
    # --output-format json, Runway records the session id and token usage of each call.
    "agent_cmd": "claude -p --output-format json --permission-mode acceptEdits",
    # Read-only prep agent. Its output becomes the decision packet.
    "prep_cmd": "claude -p --output-format json --permission-mode plan",
    # Finish step. Review and PR-body agents should be read-only; fix_cmd defaults to agent_cmd.
    "review_cmd": "claude -p --output-format json --allowedTools \"Read,Grep,Glob,Skill,Bash(git diff:*),Bash(git log:*)\"",
    "fix_cmd": "",
    "pr_cmd": "",
    # When loop runs the finish step: "all_done" (every Runway ticket done), "idle"
    # (whenever the queue stops, even with decisions waiting) or "off".
    "finish": "all_done",
    # "file": write the PR body to _pm/runway-pr.md. "draft": also push the integration
    # branch and open (or update) a draft PR with gh.
    "pr": "file",
    # Optional pointer to the spec (a path, URL or Linear issue) for the review.
    "spec": "",
    # Runs in the worktree after the agent. Exit 0 means the ticket passed.
    "check_cmd": "true",
    "integration_branch": "runway/integration",
    "base_branch": "main",
    # Per repo, so sibling repos never share a merge worktree. {repo} is the repo folder name.
    "worktree_dir": "../.runway-worktrees/{repo}",
    "max_attempts": 2,
    # Optional, e.g. osascript -e 'display notification "{msg}" with title "Runway"'
    "notify_cmd": "",
    "agent_timeout_s": 3600,
}


def now() -> str:
    # Timezone-aware, so the log lines up with UTC timestamps elsewhere.
    return dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")


def sh(cmd, cwd: Path, stdin: str | None = None, timeout: int | None = None, check=False, on_start=None):
    """Run a command. on_start(pid) is called once the child is running."""
    args = shlex.split(cmd) if isinstance(cmd, str) else cmd
    try:
        p = subprocess.Popen(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE if stdin is not None else None)
    except FileNotFoundError as e:  # e.g. claude or gh not installed
        r = subprocess.CompletedProcess(args, 127, "", str(e))
    else:
        if on_start:
            on_start(p.pid)
        try:
            out, err = p.communicate(stdin, timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            raise
        r = subprocess.CompletedProcess(args, p.returncode, out, err)
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


# ---------- heartbeat: _pm/runway-state.json ----------

_STATE: dict = {}
STATE_KEYS = ("version", "phase", "ticket", "attempt", "since", "pid", "agent_pid", "tick_started", "last_result")


def write_state(root: Path, state: dict) -> None:
    """Atomic: write a temp file in the same folder, then rename over the real one."""
    p = root / "_pm" / "runway-state.json"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        os.replace(tmp, p)
    except OSError:
        pass  # the heartbeat must never take the loop down


def beat(root: Path, phase: str, ticket: str | None = None, attempt: int | None = None, **extra) -> None:
    """Record a phase change. extra can set last_result or tick_started."""
    iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    s = _STATE.setdefault(str(root), {"tick_started": iso, "last_result": None})
    s.update(extra)
    s.update(version=1, phase=phase, ticket=ticket, attempt=attempt, since=iso, pid=os.getpid(), agent_pid=None)
    write_state(root, {k: s[k] for k in STATE_KEYS})


def beat_update(root: Path, **fields) -> None:
    """Change agent_pid or last_result without starting a new phase."""
    s = _STATE.get(str(root))
    if s:
        s.update(fields)
        write_state(root, {k: s[k] for k in STATE_KEYS})


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
    def url(self) -> str:
        return self.ref

    @property
    def packet(self) -> str | None:
        """The latest decision packet section, or None."""
        found = re.findall(r"^## Decision packet\n(.*?)(?=^## |\Z)", self.text, re.M | re.S)
        return found[-1].strip() if found else None

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


def record(root: Path, rec: dict) -> None:
    p = root / "_pm" / "runway-runs.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"at": now(), **rec}) + "\n")


def run_agent(cfg: dict, root: Path, cmd: str, cwd: Path, prompt: str, ticket: str, kind: str, attempt: int = 1):
    """Run one agent call and log it. Returns (process, text). With Claude Code's
    --output-format json, text is the result field; otherwise it's raw stdout."""
    t0 = time.time()
    try:
        r = sh(cmd, cwd, stdin=prompt, timeout=cfg["agent_timeout_s"], on_start=lambda pid: beat_update(root, agent_pid=pid))
    finally:
        beat_update(root, agent_pid=None)
    text, meta = r.stdout, {}
    try:
        d = json.loads(r.stdout)
        if isinstance(d, dict) and "result" in d:
            text, meta = d.get("result") or "", d
    except ValueError:
        pass
    record(root, {"kind": kind, "ticket": ticket, "attempt": attempt, "cwd": str(cwd),
                  "exit": r.returncode, "secs": round(time.time() - t0),
                  "session_id": meta.get("session_id"), "cost_usd": meta.get("total_cost_usd"),
                  "num_turns": meta.get("num_turns"), "usage": meta.get("usage")})
    return r, text


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
    beat(root, "prep", t.id)
    log(root, f"prep  {t.id} {t.title}")
    r, text = run_agent(cfg, root, cfg["prep_cmd"], root, PREP_PROMPT.format(path=t.ref, ticket=t.text), t.id, "prep")
    packet = text.strip() if r.returncode == 0 and text.strip() else f"Prep failed:\n\n```\n{r.stderr[-2000:]}\n```"
    t.post_packet(packet)
    notify(cfg, root, f"Decision ready: {t.id} {t.title}")


# ---------- run: the AFK lane ----------

RUN_PROMPT = """Implement this ticket in the current repository (a git worktree on its own branch).
Stay inside the ticket's scope. Work test-first: use the /tdd skill if it's available
(red-green, one slice at a time); otherwise write a failing test before the code.
Commit your work with a clear message when done.
If you cannot finish without a human decision, write the question to RUNWAY_QUESTION.md
at the repo root and stop.

Ticket ({path}):

{ticket}
{extra}"""


def ensure_integration(cfg: dict, root: Path) -> None:
    br = cfg["integration_branch"]
    if sh(["git", "rev-parse", "--verify", br], root).returncode != 0:
        sh(["git", "branch", br, cfg["base_branch"]], root, check=True)


def worktrees(cfg: dict, root: Path) -> Path:
    return root / cfg["worktree_dir"].replace("{repo}", root.name)


def run_ticket(cfg: dict, root: Path, tracker, t) -> None:
    ensure_integration(cfg, root)
    branch = f"runway/{t.effort}-{t.slug}"
    wt = (worktrees(cfg, root) / f"{t.effort}-{t.slug}").resolve()
    t.mark_claimed(branch)
    log(root, f"run   {t.id} {t.title}  -> {branch}")

    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
    sh(["git", "branch", "-D", branch], root)
    sh(["git", "worktree", "add", "-b", branch, str(wt), cfg["integration_branch"]], root, check=True)

    extra, ok, detail, attempt = "", False, "", 0
    for attempt in range(1, cfg["max_attempts"] + 1):
        beat(root, "agent", t.id, attempt)
        prompt = RUN_PROMPT.format(path=t.ref, ticket=t.text, extra=extra)
        run_agent(cfg, root, cfg["agent_cmd"], wt, prompt, t.id, "run", attempt)
        q = wt / "RUNWAY_QUESTION.md"
        if q.exists():
            detail = "Agent stopped with a question:\n\n" + q.read_text()
            break
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-m", f"runway: {t.title} (auto-commit)"], wt)
        beat(root, "check", t.id, attempt)
        c = sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])
        if c.returncode == 0:
            ok = True
            break
        detail = f"Check failed on attempt {attempt}:\n\n```\n{(c.stdout + c.stderr)[-3000:]}\n```"
        extra = f"\nThe previous attempt failed the check. Fix it:\n\n{detail}\n"
        log(root, f"fail  {t.id} attempt {attempt}")
        beat_update(root, last_result="fail")

    t = tracker.reload(t)  # agent may not touch it, but reload to be safe
    if ok:
        beat(root, "merge", t.id)
        if merge_into_integration(cfg, root, branch):
            t.mark_resolved(f"Done on `{branch}`, check passed, merged into `{cfg['integration_branch']}`.")
            log(root, f"done  {t.id}")
        else:
            ok = False
            detail = f"Check passed but `{branch}` did not merge cleanly into `{cfg['integration_branch']}`."
    if not ok:
        t.mark_needs_human("run failed or asked a question", detail or "Agent run failed with no detail.")
        notify(cfg, root, f"Blocked: {t.id} {t.title}")
    beat_update(root, last_result="pass" if ok else "park")
    record(root, {"kind": "outcome", "ticket": t.id, "attempts": attempt,
                  "result": "done" if ok else "needs-human", "detail": detail[:500]})
    sh(["git", "worktree", "remove", "--force", str(wt)], root)


def integration_worktree(cfg: dict, root: Path) -> Path:
    """Runway's own checkout of the integration branch, so the user's checkout is never disturbed."""
    tmp = (worktrees(cfg, root) / "_integration").resolve()
    if not tmp.exists():
        sh(["git", "worktree", "add", str(tmp), cfg["integration_branch"]], root, check=True)
    return tmp


def merge_into_integration(cfg: dict, root: Path, branch: str) -> bool:
    tmp = integration_worktree(cfg, root)
    r = sh(["git", "merge", "--no-ff", "-m", f"runway: merge {branch}", branch], tmp)
    if r.returncode != 0:
        sh(["git", "merge", "--abort"], tmp)
        return False
    return True


# ---------- finish: review, fix, PR body ----------

REVIEW_PROMPT = """You are reviewing a finished build before Joe merges it. Do NOT change any files.
The current branch, `{integration}`, holds the tickets below, each built separately and
merged together. Review the whole change (`git diff {base}...HEAD`) against the spec and
the tickets. If the /code-review skill is available, use it. Look for bugs, tickets that are
missing or half done, and places where separately built tickets don't fit together.

Reply with only a Markdown list of findings, most severe first, each with file:line and why
it matters. If nothing is worth fixing, reply with exactly: NO FINDINGS
{spec}
Tickets:
{tickets}
"""

FIX_PROMPT = """Fix these review findings on the current branch (Runway's integration branch).
Do only what the findings ask; no other refactoring. If you judge a finding wrong, skip it
and say why in the commit message. Commit when done.

{findings}
"""

PR_PROMPT = """Write the pull request body for merging `{integration}` into `{base}`. Do NOT change any files.
If the /pr skill is available, use it. Otherwise use exactly these three sections:

## Summary
The smallest picture that shows the change's shape (a call tree, file tree, diff sketch or
Mermaid diagram), with at most three lines of text.
## Evidence
Proof that it works, taken from the check output below. Claim nothing the output doesn't show.
## Merge danger
Two-way door (easy to walk back) or one-way door (migrations, removed APIs, data changes),
and the blast radius: what breaks if it's wrong.

Start directly with the Summary heading. No preamble.

Tickets:
{tickets}

Diff stat:
{stat}

Check (`{check}`) exited {code}:
{check_out}

Review findings: {review}
"""


def runway_tickets(tickets: list) -> list:
    return [t for t in tickets if t.gate in RUNNABLE_GATES + ("human",)]


def finish(cfg: dict, root: Path, tracker, force: bool = False) -> bool:
    """Review the integration branch as a whole, fix once, check, and write the PR body.
    Runs once per integration head unless forced. Returns True if it ran."""
    base, integ = cfg["base_branch"], cfg["integration_branch"]
    if sh(["git", "rev-parse", "--verify", integ], root).returncode != 0:
        return False
    ahead = sh(["git", "rev-list", "--count", f"{base}..{integ}"], root).stdout.strip()
    tickets = runway_tickets(tracker.load())
    if not force:
        mode = cfg["finish"]
        if mode == "off" or ahead in ("", "0") or any(t.status == "claimed" for t in tickets):
            return False
        if mode == "all_done" and not all(t.status in DONE for t in tickets):
            return False
    state_p = root / "_pm" / "runway-finish.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {}
    head = sh(["git", "rev-parse", integ], root).stdout.strip()
    if not force and state.get("head") == head:
        return False

    beat(root, "finish")
    log(root, f"finish {integ} ({ahead} commits ahead of {base})")
    wt = integration_worktree(cfg, root)
    sh(["git", "reset", "--hard", "-q"], wt)
    sh(["git", "clean", "-fdq"], wt)
    done = [t for t in tickets if t.status in DONE]
    open_ = [t for t in tickets if t.status not in DONE]
    tlist = "\n".join([f"- {t.id} {t.title} ({t.ref})" for t in done] +
                      [f"- NOT DONE: {t.id} {t.title} ({t.status})" for t in open_]) or "- (none listed)"
    spec = f"\nSpec: {cfg['spec']}\n" if cfg.get("spec") else ""

    # 1. Review the whole branch against the tickets.
    r, text = run_agent(cfg, root, cfg["review_cmd"], wt,
                        REVIEW_PROMPT.format(integration=integ, base=base, spec=spec, tickets=tlist),
                        "finish", "review")
    findings = text.strip()
    if r.returncode != 0 or not findings:
        findings, has_findings = f"Review failed (exit {r.returncode}).", False
    else:
        has_findings = findings.upper().rstrip(".") != "NO FINDINGS"

    # 2. One fix pass. Kept only if the check still passes.
    fix_note = "No fix pass needed."
    if has_findings:
        before = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        run_agent(cfg, root, cfg["fix_cmd"] or cfg["agent_cmd"], wt, FIX_PROMPT.format(findings=findings),
                  "finish", "fix")
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-qm", "runway: review fixes (auto-commit)"], wt)
        after = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        if after == before:
            fix_note = "The fix pass made no changes; the findings stand."
        elif sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"]).returncode == 0:
            fix_note = f"The fix pass committed {after[:8]} and the check still passes."
        else:
            sh(["git", "reset", "--hard", "-q", before], wt)
            fix_note = "The fix pass broke the check, so it was discarded; the findings stand."
    log(root, f"review {'findings' if has_findings else 'clean'}. {fix_note}")

    # 3. Evidence: the check on the final branch.
    c = sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])
    check_out = (c.stdout + c.stderr)[-3000:]
    stat = sh(["git", "diff", "--stat", f"{base}...HEAD"], wt).stdout[-3000:]

    # 4. The PR body, /pr style.
    review_line = f"{fix_note}\n\n{findings}" if has_findings else fix_note
    r, body = run_agent(cfg, root, cfg["pr_cmd"] or cfg["review_cmd"], wt,
                        PR_PROMPT.format(integration=integ, base=base, tickets=tlist, stat=stat,
                                         check=cfg["check_cmd"], code=c.returncode, check_out=check_out,
                                         review=review_line), "finish", "pr")
    body = body.strip() if r.returncode == 0 and body.strip() else (
        f"## Summary\n\n```\n{stat}\n```\n\n## Evidence\n\n`{cfg['check_cmd']}` exited {c.returncode}.\n\n"
        f"```\n{check_out}\n```\n\n## Merge danger\n\nNot assessed (the PR-body agent failed).")
    body += (f"\n\n<details><summary>Runway review</summary>\n\n{review_line}\n\n"
             f"Tickets:\n{tlist}\n</details>\n")
    (root / "_pm").mkdir(exist_ok=True)
    (root / "_pm" / "runway-review.md").write_text(findings + "\n\n" + fix_note + "\n")
    pr_file = root / "_pm" / "runway-pr.md"
    pr_file.write_text(body)

    where = str(pr_file.relative_to(root))
    if cfg["pr"] == "draft":
        where = open_draft_pr(cfg, root, pr_file, len(done)) or where
    head = sh(["git", "rev-parse", integ], root).stdout.strip()
    state_p.write_text(json.dumps({"head": head, "at": now()}))
    record(root, {"kind": "finish", "ticket": "finish", "findings": has_findings, "fix": fix_note,
                  "check_exit": c.returncode, "pr": where})
    verdict = "check passes" if c.returncode == 0 else "CHECK FAILS"
    notify(cfg, root, f"Ready for review: {len(done)} tickets on {integ}, {verdict}. PR: {where}")
    return True


def open_draft_pr(cfg: dict, root: Path, body_file: Path, n: int) -> str | None:
    """Push the integration branch and open or update a draft PR. Returns its URL, or None."""
    integ, base = cfg["integration_branch"], cfg["base_branch"]
    if not shutil.which("gh") or sh(["git", "remote", "get-url", "origin"], root).returncode != 0:
        log(root, "pr    skipped: needs gh and an origin remote")
        return None
    p = sh(["git", "push", "-q", "-u", "origin", integ], root)
    if p.returncode != 0:
        log(root, f"pr    push failed: {p.stderr.strip()[-300:]}")
        return None
    v = sh(["gh", "pr", "view", integ, "--json", "url,state", "-q", "select(.state==\"OPEN\") | .url"], root)
    if v.returncode == 0 and v.stdout.strip():
        sh(["gh", "pr", "edit", integ, "--body-file", str(body_file)], root)
        url = v.stdout.strip()
    else:
        r = sh(["gh", "pr", "create", "--draft", "--base", base, "--head", integ,
                "--title", f"Runway: {n} tickets ready to merge", "--body-file", str(body_file)], root)
        url = r.stdout.strip().splitlines()[-1] if r.returncode == 0 and r.stdout.strip() else None
        if not url:
            log(root, f"pr    gh pr create failed: {r.stderr.strip()[-300:]}")
    return url


# ---------- retro: feed the struggles to /retro ----------

def transcript(session_id: str) -> str | None:
    """Claude Code keeps each session as ~/.claude/projects/<cwd as a folder name>/<id>.jsonl."""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    hits = list((home / "projects").glob(f"*/{session_id}.jsonl"))
    return str(hits[0]) if hits else None


def cmd_retro(root: Path, last: int) -> None:
    p = root / "_pm" / "runway-runs.jsonl"
    if not p.exists():
        sys.exit("No runs logged yet (_pm/runway-runs.jsonl).")
    recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()][-last:]
    calls = [r for r in recs if r["kind"] in ("prep", "run", "review", "fix", "pr")]
    outcomes = {r["ticket"]: r for r in recs if r["kind"] == "outcome"}
    finishes = [r for r in recs if r["kind"] == "finish"]

    # Usage per ticket.
    rows, tot = {}, {"calls": 0, "tokens": 0, "cost": 0.0, "secs": 0}
    for r in calls:
        u = r.get("usage") or {}
        tok = sum(v for k, v in u.items() if k.endswith("tokens") and isinstance(v, int))
        row = rows.setdefault(r["ticket"], {"calls": 0, "tokens": 0, "cost": 0.0, "secs": 0})
        for d in (row, tot):
            d["calls"] += 1; d["tokens"] += tok; d["cost"] += r.get("cost_usd") or 0; d["secs"] += r.get("secs") or 0
    out = ["# Runway retro", "", f"From the last {len(recs)} log records in `_pm/runway-runs.jsonl`.", "",
           "## Usage", "", "| Ticket | Calls | Tokens | Cost (USD) | Agent time | Result |", "|---|---|---|---|---|---|"]
    for k, v in list(rows.items()) + [("total", tot)]:
        o = outcomes.get(k)
        res = f"{o['result']} after {o['attempts']}" if o else ""
        out.append(f"| {k} | {v['calls']} | {v['tokens']:,} | {v['cost']:.2f} | {v['secs'] // 60}m{v['secs'] % 60:02d}s | {res} |")
    if not any(r.get("usage") for r in calls):
        out += ["", "No token data: add `--output-format json` to the agent commands in runway.json."]

    # Which sessions struggled.
    flagged = []
    for r in calls:
        o, why = outcomes.get(r["ticket"]), ""
        if r["kind"] == "run" and o and o["result"] != "done":
            why = f"parked as needs-human: {o['detail'][:160]}".replace("\n", " ")
        elif r["kind"] == "run" and r["attempt"] > 1:
            why = f"needed attempt {r['attempt']} (the first failed the check)"
        elif r["kind"] == "run" and o and o["attempts"] > 1:
            why = "failed the check on this attempt"
        elif r["kind"] == "fix" or r["exit"] != 0:
            why = "review fix pass" if r["kind"] == "fix" else f"{r['kind']} exited {r['exit']}"
        if why:
            flagged.append((r, why))
    for f in finishes:
        if f.get("findings"):
            out += ["", f"Finish review had findings. {f['fix']}"]
    pick = flagged or [(r, "") for r in calls if r["kind"] == "run"][-10:]
    lines = []
    for r, why in pick:
        if not r.get("session_id"):
            continue
        path = transcript(r["session_id"]) or f"session {r['session_id']} (transcript not found on this machine)"
        lines.append(f"- {path}: {r['ticket']} {r['kind']}" + (f", {why}" if why else ""))
    prompt = ("/retro Read these sessions from Runway's unattended runs on this repo. Each ran headless "
              "in its own worktree from a ticket prompt, with no human to ask. Find what made them "
              "struggle and propose environment fixes (checks, navigation, AGENTS.md cuts), not code changes.\n\n"
              + ("\n".join(lines) if lines else "(no session ids logged)") + "\n")
    out += ["", "## Prompt for /retro", "", "Sessions that struggled:" if flagged else
            "Nothing struggled, so these are the latest runs:", "", "```", prompt.rstrip(), "```", "",
            f"Run it from the repo: `claude \"$(cat _pm/runway-retro-prompt.md)\"`"]
    (root / "_pm" / "runway-retro-prompt.md").write_text(prompt)
    (root / "_pm" / "runway-retro.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


# ---------- commands ----------

def tick(cfg: dict, root: Path, tracker) -> bool:
    """One pass. Returns True if it did anything."""
    did = False
    beat(root, "sync", tick_started=dt.datetime.now().astimezone().isoformat(timespec="seconds"))
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


GROUPS = [("waiting", "Waiting on you"), ("running", "Running"), ("ready_auto", "Ready (auto)"),
          ("ready_prep", "Ready (needs prep)"), ("blocked", "Blocked"), ("done", "Done")]


def group_tickets(tickets: list) -> dict:
    """Runway's tickets by group key, each in tracker (queue) order."""
    groups = {key: [] for key, _ in GROUPS}
    for t in tickets:
        if t.gate not in RUNNABLE_GATES + ("human",):
            continue  # not Runway's (e.g. a wayfinder decision ticket)
        if t.status == "needs-human":
            groups["waiting"].append(t)
        elif t.status == "claimed":
            groups["running"].append(t)
        elif t.status in DONE:
            groups["done"].append(t)
        elif not unblocked(t, tickets) and t.gate != "human":
            groups["blocked"].append(t)
        elif t.gate == "human":
            groups["ready_prep"].append(t)
        else:
            groups["ready_auto"].append(t)
    return groups


def cmd_status(tracker) -> None:
    groups = group_tickets(tracker.load())
    for key, name in GROUPS:
        ts = groups[key]
        print(f"\n{name} ({len(ts)})")
        for t in ts:
            extra = f"  [{t.h('Waiting on')}]" if key == "waiting" and t.h("Waiting on") else ""
            print(f"  {t.id:<24} {t.title}{extra}")


def status_json(cfg: dict, root: Path, tracker) -> dict:
    """The `status --json` document. Shape is documented in the module docstring."""
    groups = group_tickets(tracker.load())

    def full_id(t, b: str) -> str:
        return f"{t.effort}/{b}" if b.isdigit() else b  # markdown blockers are bare numbers

    def entry(t) -> dict:
        waiting = t.status == "needs-human"
        return {"id": t.id, "title": t.title, "url": t.url or None, "status": t.status, "gate": t.gate,
                "blocked_by": [full_id(t, b) for b in t.blocked_by],
                "waiting_on": (t.h("Waiting on") or None) if waiting else None,
                "packet": t.packet if waiting else None, "harness": None}

    return {"version": 1, "repo": str(root), "tracker": cfg.get("tracker", "markdown"),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "groups": {k: [t.id for t in ts] for k, ts in groups.items()},
            "tickets": [entry(t) for ts in groups.values() for t in ts]}


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
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true", help="machine-readable queue (shape in the module docstring)")
    sub.add_parser("tick")
    lp = sub.add_parser("loop")
    lp.add_argument("--max-ticks", type=int, default=50)
    g = sub.add_parser("go"); g.add_argument("ticket"); g.add_argument("note", nargs="?", default="")
    n = sub.add_parser("no"); n.add_argument("ticket"); n.add_argument("note", nargs="?", default="")
    sub.add_parser("setup", help="Linear only: check the key, team and project, and create Runway's labels")
    sub.add_parser("finish", help="review the integration branch, fix once, check, and write the PR body now")
    rt = sub.add_parser("retro", help="usage per ticket, and a /retro prompt for the runs that struggled")
    rt.add_argument("--last", type=int, default=200, help="log records to read (default 200)")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    cfg = dict(DEFAULT_CONFIG)
    cfg_path = Path(a.config) if a.config else root / "runway.json"
    if cfg_path.exists():
        cfg.update(json.loads(cfg_path.read_text()))
    tracker = make_tracker(cfg, root)

    if a.cmd == "status":
        if a.json:
            print(json.dumps(status_json(cfg, root, tracker), indent=2))
        else:
            cmd_status(tracker)
    elif a.cmd == "setup":
        if not hasattr(tracker, "setup"):
            sys.exit("setup is only needed for the linear tracker.")
        tracker.setup()
    elif a.cmd == "retro":
        cmd_retro(root, a.last)
    elif a.cmd in ("tick", "loop", "finish"):
        lock = locked(root)
        if lock is None:
            print("Another Runway run holds the lock; skipping.")
            return
        try:
            if a.cmd == "tick":
                tick(cfg, root, tracker)
            elif a.cmd == "finish":
                finish(cfg, root, tracker, force=True)
            else:
                for _ in range(a.max_ticks):
                    if not tick(cfg, root, tracker):
                        log(root, "idle  nothing ready without Joe")
                        finish(cfg, root, tracker)
                        break
                cmd_status(tracker)
        except KeyboardInterrupt:
            beat(root, "stopped")
            raise
        beat(root, "idle")
    elif a.cmd in ("go", "no"):
        cmd_answer(root, tracker, a.ticket, a.cmd == "go", a.note)


if __name__ == "__main__":
    main()
