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

  {"version": 1, "repo": "/abs/path", "tracker": "markdown|linear", "machine": "Mini-One",
   "generated_at": "ISO-8601",
   "groups": {"waiting": [id...], "running": [...], "ready_auto": [...],
              "ready_prep": [...], "blocked": [...], "done": [...]},
   "tickets": [{"id", "title", "url", "status", "gate", "blocked_by": [id...],
                "waiting_on", "packet", "harness", "claimed_by"}]}

  machine     This Mac's name (`scutil --get LocalHostName`, else the hostname), what `runway whoami`
              prints. It is stamped on every claim (markdown `Claimed-by:` header, Linear claim
              comment). A ready ticket claimed by another machine is skipped and logged
              `skip <id> claimed by <machine>`.
  paused      The pause in force (the ~/.runway/pause contents), or null.
  signin      The last sign-in check, or null before any ran: {"at", "ok", "notified": [name...],
              "checks": [{"name", "ok", "detail"}]} (the _pm/runway-signin.json file).
  claimed_by  The machine that holds the ticket's claim, or null.

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
  harness  The ticket's effective harness name (its override, else the project default).

`runway pause [--until ISO-8601 | --for 1h] [--stop-now]` writes ~/.runway/pause (RUNWAY_HOME
overrides the folder), the machine-wide pause. It holds with the app closed and leaves launchd jobs loaded:

  {"until": "ISO-8601 or null", "mode": "finish|stop", "at": "ISO-8601"}

`runway resume` deletes it. While the file exists and `until` hasn't passed, `tick` logs
`paused until ...`, writes heartbeat phase `paused` and exits 0; `loop` stops between ticks the same
way (no finish step). An expired pause file is removed. Mode finish (default): a running ticket
finishes, nothing new starts. Mode stop (`--stop-now`): also SIGTERMs the running agent (agent_pid from
the heartbeat); the tick returns the ticket to ready with a "stopped by pause" comment and keeps its worktree.

`~/.runway/machine.json` holds this Mac's quiet-time rules, read at the start of every tick next to the
pause check. A missing file is no rules; an unreadable one waits (never runs on a guess):

  {"version": 1,
   "quiet_hours": {"enabled": true, "from": "09:00", "to": "17:00", "days": ["mon", ...]},
   "idle_only": {"enabled": false, "minutes": 10},
   "not_on_battery": true, "max_agents": 1}

A rule only stops a NEW start; a running agent is never touched. quiet_hours `days` are the days a window
starts on (a 22:00-06:00 window on fri runs into Saturday morning). idle_only compares HIDIdleTime
(`ioreg -c IOHIDSystem`). max_agents counts live pid files in ~/.runway/agents/ (one per running agent,
any repo; dead pids are swept). A reader that can't answer (no battery info, no ioreg) lets that rule pass.
A skipped tick logs `waiting: <reason>` and writes heartbeat phase `waiting` with a `reason` field.
`runway machine` prints the rules and whether a tick would run now, and why not.

Sign-ins are checked before a tick starts work (claims a ticket, preps a packet) and before the finish
step, never on an idle tick. Each check is a status command, not a model call: `claude auth status`
(Codex: `codex login status`), `gh auth status` when a draft PR will be opened, the Linear key when the
tracker is Linear, and both review seats when "review" is "panel". Override a command under "signin_cmds".
Any failure claims nothing: it logs `waiting: <reason>`, writes heartbeat `waiting` with that `reason` (the
app shows it as it shows quiet-time reasons), sends one notification until the check passes again, and
keeps the results in `_pm/runway-signin.json` (shown by `runway machine` and `status --json`). The next
tick checks again. A status command can report "logged in" while the token refresh is already dead, so the
rule behind it stands: the first agent call that fails on auth pauses the loop (pause_for_auth).

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
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HEADER_RE = re.compile(r"^(Status|Blocked by|Waiting on|Gate|Type|Branch|Claimed-by|Harness):\s*(.*)$", re.M)
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
    # "single": review_cmd reviews the integration branch. "panel": Joe's two-seat review (codex +
    # claude) through Ringer, see ringer_panel.py. Without Ringer or any seat report it falls back to single.
    "review": "single",
    # Which harness runs tickets by default: "claude" (the top-level commands above) or a key of
    # "harnesses". A ticket overrides it: Linear label `harness:<name>` or header `Harness: <name>`.
    "harness": "claude",
    # Named profiles. Each may set agent_cmd, prep_cmd, review_cmd, fix_cmd, pr_cmd and "parser"
    # (claude | codex | raw); missing keys fall back to the top-level ones.
    "harnesses": {},
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
    # Sign-in status commands by tool (claude, codex, gh) when the defaults don't fit this Mac.
    # A string or an argument list; exit 0 means signed in. Never a model call.
    "signin_cmds": {},
}


def machine_name() -> str:
    """This Mac's name (`scutil --get LocalHostName`), else the hostname."""
    try:
        r = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return socket.gethostname()


# ---------- machine-wide pause: ~/.runway/pause ----------

def pause_path() -> Path:
    return Path(os.environ.get("RUNWAY_HOME") or Path.home() / ".runway") / "pause"


def parse_when(text: str) -> dt.datetime:
    """ISO-8601 (naive means local time) to an aware datetime."""
    d = dt.datetime.fromisoformat(text.strip())
    return d if d.tzinfo else d.astimezone()


def parse_span(text: str) -> dt.timedelta:
    """'90s', '30m', '1h', '2d' or '1h30m'."""
    want = text.strip().lower()
    parts = re.findall(r"(\d+)([smhd])", want)
    if not parts or "".join(n + u for n, u in parts) != want:
        raise ValueError(f"bad duration {text!r}; use e.g. 30m, 1h, 2d")
    unit = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    return dt.timedelta(**{unit[u]: int(n) for n, u in parts})


def active_pause(clean: bool = True) -> dict | None:
    """The pause in force, else None. An expired pause file is removed here unless clean is False."""
    p = pause_path()
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            raise ValueError
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        data = {"until": None, "mode": "finish", "at": None}  # unreadable: stay paused, never run on a guess
    until = data.get("until")
    try:
        expired = bool(until) and parse_when(until) <= dt.datetime.now().astimezone()
    except ValueError:
        expired = False
    if expired:
        if clean:
            p.unlink(missing_ok=True)
        return None
    return data


def stop_requested() -> bool:
    pause = active_pause()
    return bool(pause and pause.get("mode") == "stop")


def paused_now(root: Path) -> bool:
    """True (after logging it and writing heartbeat phase paused) while a pause is in force."""
    pause = active_pause()
    if not pause:
        return False
    log(root, f"paused until {pause.get('until') or 'resumed'}")
    beat(root, "paused")
    return True


def write_pause(end: dt.datetime | None, mode: str) -> None:
    p = pause_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"until": end.isoformat(timespec="seconds") if end else None, "mode": mode,
                               "at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}) + "\n")
    os.replace(tmp, p)


def pause_for_auth(cfg: dict, root: Path) -> None:
    """The agent's sign-in is gone: pause the whole machine (what `runway pause` sets) and say so once.
    A pause already in force is left as it is, and so is its notification."""
    if active_pause():
        return
    write_pause(None, "finish")
    notify(cfg, root, "Runway: Claude Code needs signing in")


def cmd_pause(root: Path, until: str | None, span: str | None, stop_now: bool) -> None:
    if until and span:
        sys.exit("Use --until or --for, not both.")
    end = None
    try:
        if until:
            end = parse_when(until)
        elif span:
            end = dt.datetime.now().astimezone() + parse_span(span)
    except ValueError as e:
        sys.exit(str(e))
    write_pause(end, "stop" if stop_now else "finish")
    print("paused until " + (end.isoformat(timespec="seconds") if end else "resumed") + (" (stop)" if stop_now else ""))
    if stop_now:
        pids = set()  # every registered agent on this Mac (run_agent registers the heartbeat's agent_pid too)
        for f in agents_dir().glob("*"):
            try:
                pid = int(f.name)
            except ValueError:
                continue
            try:
                lines = f.read_text().splitlines()
            except OSError:
                continue  # the agent finished and unregistered while we scanned
            recorded = lines[1] if len(lines) > 1 else ""
            actual = process_started(pid)
            if actual is None:
                f.unlink(missing_ok=True)  # gone
            elif not recorded or recorded == actual:  # no start time: a registration from before they were recorded
                pids.add(pid)
            else:  # the pid was reused by some other process: not ours to signal
                print(f"pid {pid} is no longer a Runway agent; left alone")
                f.unlink(missing_ok=True)
        if not pids:
            print("no agent running; nothing to stop")
            return
        for pid in sorted(pids):
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"stopped agent {pid}")
            except ProcessLookupError:
                print(f"agent {pid} already gone")


def cmd_resume() -> None:
    pause_path().unlink(missing_ok=True)
    print("resumed")


# ---------- quiet-time rules: ~/.runway/machine.json ----------

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def runway_home() -> Path:
    return Path(os.environ.get("RUNWAY_HOME") or Path.home() / ".runway")


def load_machine_rules() -> dict:
    """The rules in machine.json; a missing file is no rules. Raises ValueError if unreadable."""
    try:
        data = json.loads((runway_home() / "machine.json").read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ValueError(f"machine.json unreadable ({e.__class__.__name__})")
    if not isinstance(data, dict):
        raise ValueError("machine.json unreadable (not an object)")
    return data


# Readers. Tests replace these; each returns None when the answer can't be read (that rule then lets the tick run).
def read_clock() -> dt.datetime:
    return dt.datetime.now().astimezone()


def read_on_battery() -> bool | None:
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if "Battery Power" in out:
        return True
    return False if "AC Power" in out else None


def read_idle_seconds() -> float | None:
    try:
        out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    return int(m.group(1)) / 1e9 if m else None


def agents_dir() -> Path:
    return runway_home() / "agents"


def process_started(pid: int) -> str | None:
    """When the process with this pid started (ps's lstart text), or None if it isn't running."""
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return out.strip() or None


def register_agent(pid: int, root: Path) -> None:
    """Mark an agent as running on this Mac: a file named for its pid, holding the repo path and, on a second
    line, the process start time, so a reused pid is never mistaken for the agent."""
    try:
        agents_dir().mkdir(parents=True, exist_ok=True)
        (agents_dir() / str(pid)).write_text(f"{root}\n{process_started(pid) or ''}\n")
    except OSError:
        pass  # counting is best effort; it must never take the loop down


def unregister_agent(pid: int) -> None:
    (agents_dir() / str(pid)).unlink(missing_ok=True)


def running_agents() -> int:
    """Live agents across every Runway repo on this Mac. Files of dead pids are removed here."""
    n = 0
    for f in agents_dir().glob("*"):
        try:
            pid = int(f.name)
            os.kill(pid, 0)
            try:
                lines = f.read_text().splitlines()
            except OSError:
                continue
            if len(lines) > 1 and lines[1] and lines[1] != process_started(pid):
                f.unlink(missing_ok=True)  # the pid was reused by some other process
                continue
            n += 1
        except ProcessLookupError:
            f.unlink(missing_ok=True)
        except PermissionError:
            n += 1  # alive, just not ours
        except ValueError:
            pass  # not a pid file
    return n


def in_quiet_hours(q: dict, when: dt.datetime) -> bool:
    """Is `when` inside the window? `days` are the days a window starts on, so a window that
    runs past midnight belongs to the day it began."""
    start, end = (dt.time.fromisoformat(q["from"]), dt.time.fromisoformat(q["to"]))
    days = [d.lower()[:3] for d in q.get("days", DAYS)]
    today, yesterday = DAYS[when.weekday()], DAYS[(when.weekday() - 1) % 7]
    t = when.time().replace(second=0, microsecond=0)
    if start <= end:
        return today in days and start <= t < end
    return (t >= start and today in days) or (t < end and yesterday in days)


def machine_block() -> str | None:
    """Why no new ticket may start on this Mac right now, else None."""
    try:
        rules = load_machine_rules()
    except ValueError as e:
        return str(e)  # unreadable: wait, never run on a guess
    q = rules.get("quiet_hours") or {}
    if q.get("enabled"):
        try:
            if in_quiet_hours(q, read_clock()):
                return f"quiet hours {q['from']}-{q['to']}"
        except (KeyError, ValueError):
            return "machine.json quiet_hours unreadable"
    if rules.get("not_on_battery") and read_on_battery():
        return "on battery"
    idle = rules.get("idle_only") or {}
    if idle.get("enabled"):
        secs = read_idle_seconds()
        if secs is not None and secs <= float(idle.get("minutes", 0)) * 60:
            return f"not idle ({round(secs / 60, 1)} min of {idle.get('minutes')} needed)"
    cap = rules.get("max_agents")
    if cap:
        n = running_agents()
        if n >= int(cap):
            return f"max agents ({n} running, limit {cap})"
    return None


def machine_waiting(root: Path) -> bool:
    """True (after logging the reason and writing heartbeat phase waiting) while a rule blocks a start."""
    reason = machine_block()
    if not reason:
        return False
    log(root, f"waiting: {reason}")
    beat(root, "waiting", reason=reason)
    return True


def describe_machine(root: Path | None = None) -> str:
    """What `runway machine` prints: the rules and whether a tick would run now."""
    try:
        rules = load_machine_rules()
    except ValueError as e:
        rules = None
        lines = [str(e)]
    else:
        lines = []
        q, idle = rules.get("quiet_hours") or {}, rules.get("idle_only") or {}
        if q.get("enabled"):
            lines.append(f"quiet hours  {q.get('from')}-{q.get('to')} on {','.join(q.get('days', DAYS))}")
        if idle.get("enabled"):
            lines.append(f"idle only  start after {idle.get('minutes')} min idle")
        if rules.get("not_on_battery"):
            lines.append("not on battery")
        if rules.get("max_agents"):
            lines.append(f"max agents  {rules['max_agents']}")
        if not lines:
            lines.append("no rules" + ("" if (runway_home() / "machine.json").exists() else " (no machine.json)"))
    last = read_signin(root) if root else None
    if last:
        lines.append(f"sign-ins  last checked {last.get('at')}")
        lines += [f"  {c['name']:<7} {'ok' if c['ok'] else 'FAILED'}  {c['detail']}" for c in last.get("checks", [])]
    reason = machine_block()
    lines.append("would not run now: " + reason if reason else "would run now: no rule blocks a start")
    return "\n".join(lines)


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
    s.update({k: v for k, v in extra.items() if k != "reason"})
    s.update(version=1, phase=phase, ticket=ticket, attempt=attempt, since=iso, pid=os.getpid(), agent_pid=None)
    out = {k: s[k] for k in STATE_KEYS}
    if phase == "waiting":
        out["reason"] = extra.get("reason")
    write_state(root, out)


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
    post_packet(), mark_claimed(), mark_resolved(), mark_needs_human(), mark_ready(), approve(), decline()."""

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
    def harness(self) -> str | None:
        """Per-ticket harness override from a `Harness: <name>` header, or None."""
        return self.h("Harness").lower() or None

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

    @property
    def claimed_by(self) -> str | None:
        return self.h("Claimed-by") or None

    def mark_claimed(self, branch: str, machine: str) -> None:
        self.set("Status", "claimed")
        self.set("Branch", branch)
        self.set("Claimed-by", machine)
        self.save()

    def mark_resolved(self, note: str) -> None:
        self.set("Status", "resolved")
        self.set("Claimed-by", None)
        self.comment(note)
        self.save()

    def mark_needs_human(self, why: str, detail: str) -> None:
        self.set("Status", "needs-human")
        self.set("Claimed-by", None)
        self.set("Waiting on", f"Joe, {why}, since {now()}")
        self.comment(detail)
        self.save()

    def mark_ready(self, note: str) -> None:
        """Back in the queue (a pause stopped it). Releases the claim; the branch name stays."""
        self.set("Status", "ready")
        self.set("Claimed-by", None)
        self.comment(note)
        self.save()

    def approve(self, note: str) -> None:
        self.set("Status", "ready")
        self.set("Gate", "approved")
        self.set("Claimed-by", None)
        self.set("Waiting on", None)
        self.comment(f"Joe: go. {note}".strip())
        self.save()

    def decline(self, note: str) -> None:
        drop = note.lower().startswith("drop")
        self.set("Status", "resolved" if drop else "needs-human")
        self.set("Claimed-by", None)
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
        # Split first, then fill {msg} into each argument, so the message is never
        # re-parsed by shlex (an apostrophe in a title used to crash the tick).
        # Double quotes become single so an AppleScript string stays closed.
        safe = msg.replace('"', "'")
        sh([a.replace("{msg}", safe) for a in shlex.split(cfg["notify_cmd"])], root)


SIGNIN_TOOLS = {  # key: (name Joe knows it by, status command, the command that signs in)
    "claude": ("Claude Code", "claude auth status", "claude auth login"),
    "codex": ("Codex", "codex login status", "codex login"),
    "gh": ("GitHub CLI", "gh auth status", "gh auth login"),
}


def signin_path(root: Path) -> Path:
    return root / "_pm" / "runway-signin.json"


def read_signin(root: Path) -> dict | None:
    """The last sign-in check's result (what status --json and `runway machine` show), else None."""
    try:
        data = json.loads(signin_path(root).read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def tool_signin(cfg: dict, root: Path, key: str) -> dict:
    """One status command, never a model call. A status command can say "logged in" while the token
    refresh is already dead, so the first agent call that fails on auth still pauses the loop."""
    label, default, fix = SIGNIN_TOOLS[key]
    cmd = (cfg.get("signin_cmds") or {}).get(key) or default
    try:
        r = sh(cmd, root, timeout=30)
    except subprocess.TimeoutExpired:
        return {"name": key, "ok": False, "detail": f"{label} did not answer its status check (`{default}`)"}
    if r.returncode == 127:
        return {"name": key, "ok": False, "detail": f"{label} is not installed (`{fix.split()[0]}` not found)"}
    try:
        out = json.loads(r.stdout)
    except ValueError:
        out = None
    if r.returncode != 0 or (isinstance(out, dict) and out.get("loggedIn") is False):
        return {"name": key, "ok": False, "detail": f"{label} needs signing in (`{fix}`)"}
    return {"name": key, "ok": True, "detail": f"{label} signed in"}


def linear_signin(cfg: dict) -> dict:
    """The Linear key is present (environment or keychain). Nothing goes over the network."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import linear_tracker
    lc = dict(linear_tracker.DEFAULTS, **cfg.get("linear", {}))
    try:
        linear_tracker.api_key(lc)
    except SystemExit:
        return {"name": "linear", "ok": False,
                "detail": f"Linear needs its key ({lc['api_key_env']} or the keychain item `{lc['keychain_service']}`)"}
    return {"name": "linear", "ok": True, "detail": "Linear key found"}


def harness_signin_key(cfg: dict, name: str) -> str | None:
    """Which status check covers a harness: its parser decides (claude, codex), else none."""
    parser = (harness_profiles(cfg).get(name) or {}).get("parser") or ("claude" if name == "claude" else None)
    return parser if parser in ("claude", "codex") else None


def signin_checks(cfg: dict, root: Path, harnesses, panel: bool = False, finish: bool = False) -> list:
    """Every tool the next step will use, checked. harnesses: names of the harnesses about to run.
    panel: the next step is the Ringer review panel (both its seats). finish: the finish step is next,
    so gh counts when it will open a draft PR."""
    keys = [harness_signin_key(cfg, name) for name in harnesses]
    if panel:
        keys += ["codex", "claude"]
    if cfg.get("tracker") == "github" or (finish and cfg.get("pr") == "draft"):
        keys.append("gh")
    results = [tool_signin(cfg, root, k) for k in dict.fromkeys(k for k in keys if k)]
    if cfg.get("tracker") == "linear":
        results.append(linear_signin(cfg))
    return results


def signin_waiting(cfg: dict, root: Path, harnesses, panel: bool = False, finish: bool = False) -> bool:
    """Check sign-ins before work starts. True (after logging, heartbeat `waiting` with the reason, and
    one notification until it clears) when any check fails; the caller then starts nothing."""
    results = signin_checks(cfg, root, harnesses, panel, finish)
    failing = [c for c in results if not c["ok"]]
    prev = read_signin(root) or {}
    notified = [n for n in prev.get("notified", []) if any(c["name"] == n for c in failing)]
    new = [c for c in failing if c["name"] not in notified]
    out = {"at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "ok": not failing,
           "checks": results, "notified": notified + [c["name"] for c in new]}
    p = signin_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(out) + "\n")
    os.replace(tmp, p)
    if not failing:
        return False
    reason = "; ".join(c["detail"] for c in failing)
    log(root, f"waiting: {reason}")
    beat(root, "waiting", reason=reason)
    if new:
        notify(cfg, root, "Runway: " + "; ".join(c["detail"].split(" (")[0] for c in new))
    return True


def signin_waiting_for_work(cfg: dict, root: Path, tickets: list) -> bool:
    """Only a tick with work to start checks sign-ins: a ready ticket to run, or a decision to prep."""
    me = machine_name()
    names = []
    for t in tickets:
        if t.status != "ready" or harness_error(cfg, t):
            continue
        prep_it = t.gate == "human" and will_unblock_without_joe(t, tickets)
        run_it = t.gate in RUNNABLE_GATES and unblocked(t, tickets) and (not t.claimed_by or t.claimed_by == me)
        if prep_it or run_it:
            names.append(resolve_harness(cfg, t)["name"])
    return bool(names) and signin_waiting(cfg, root, list(dict.fromkeys(names)))


def record(root: Path, rec: dict) -> None:
    p = root / "_pm" / "runway-runs.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"at": now(), **rec}) + "\n")


def harness_profiles(cfg: dict) -> dict:
    """The usable named profiles: dict values only, and no key starting with `_` (notes live there)."""
    return {k.lower(): v for k, v in (cfg.get("harnesses") or {}).items()
            if isinstance(v, dict) and not str(k).startswith("_")}


def harness_error(cfg: dict, t) -> str | None:
    """A message when the ticket's harness override names no known harness, else None."""
    name = getattr(t, "harness", None)
    if name and name.lower() != "claude" and name.lower() not in harness_profiles(cfg):
        known = ", ".join(["claude", *sorted(harness_profiles(cfg))])
        return f"unknown harness '{name}' (known: {known})"
    return None


def resolve_harness(cfg: dict, t=None) -> dict:
    """The effective profile for a ticket (the project default when t is None): the ticket's
    override, else cfg["harness"]. Top-level commands are the base; the named profile overlays them.
    An unknown override falls back to the project default (tick parks such tickets first)."""
    profiles = harness_profiles(cfg)
    default = (cfg.get("harness") or "claude").lower()
    name = (getattr(t, "harness", None) or default).lower()
    if name != "claude" and name not in profiles:
        name = default
    prof = {k: cfg.get(k, "") for k in ("agent_cmd", "prep_cmd", "review_cmd", "fix_cmd", "pr_cmd")}
    prof["parser"] = "claude"
    override = profiles.get(name)
    prof.update({k: v for k, v in (override if isinstance(override, dict) else {}).items() if v})
    prof["name"] = name
    return prof


def parse_output(parser: str, stdout: str) -> tuple[str, dict]:
    """(text, meta) from a harness's stdout. meta has session_id, cost_usd, num_turns and usage,
    each None when the harness doesn't report it. Unparseable output comes back as text unchanged."""
    meta = {"session_id": None, "cost_usd": None, "num_turns": None, "usage": None, "is_error": False,
            "subtype": None}
    if parser == "claude":
        try:
            d = json.loads(stdout)
        except ValueError:
            return stdout, meta
        if isinstance(d, dict) and "result" in d:
            meta.update(session_id=d.get("session_id"), cost_usd=d.get("total_cost_usd"),
                        num_turns=d.get("num_turns"), usage=d.get("usage"),
                        is_error=bool(d.get("is_error")), subtype=d.get("subtype"))
            return d.get("result") or "", meta
    elif parser == "codex":
        # `codex exec --json` prints one event per line: thread.started, item.completed, turn.completed.
        text, seen = "", False
        for line in stdout.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict):
                continue
            seen = True
            item = e.get("item") or {}
            if e.get("type") == "thread.started":
                meta["session_id"] = e.get("thread_id")
            elif e.get("type") == "item.completed" and item.get("type") == "agent_message":
                text = item.get("text") or text
            elif e.get("type") == "turn.completed" and e.get("usage"):
                prev = meta["usage"] or {}
                meta["usage"] = {k: prev.get(k, 0) + v for k, v in e["usage"].items() if isinstance(v, int)}
        if seen:
            return text, meta
    return stdout, meta


AUTH_RE = re.compile(r"authentication_failed|authentication_error|oauth (session|token)[^.\n]*expired|"
                     r"invalid api key|please run /login|not logged in", re.I)


def agent_failure(r, text: str, meta: dict) -> str | None:
    """Why this agent call did not really run, else None: a non-zero exit, an is_error result, or no
    turns and no output at all. The reason carries the agent's own error text."""
    said = (text or r.stdout or "").strip()
    err = (r.stderr or "").strip()
    detail = "\n".join(x for x in (said, err) if x)[-1500:] or "no output"
    if r.returncode != 0:
        return f"the agent exited {r.returncode}: {detail}"
    if meta.get("is_error"):
        return f"the agent reported an error: {detail}"
    out = (meta.get("usage") or {}).get("output_tokens")
    if meta.get("num_turns") == 0 and not out:
        return "the agent ran no turns and wrote no output"
    return None


def fix_failure_note(reason: str) -> str:
    return f"The fix pass failed ({reason.splitlines()[0][:200]}); the findings stand."


def run_agent(cfg: dict, root: Path, cmd: str, cwd: Path, prompt: str, ticket: str, kind: str, attempt: int = 1,
              harness: dict | None = None):
    """Run one agent call and log it. Returns (process, text). The harness profile's parser pulls
    the text, session id and usage out of stdout; unparseable output is returned raw."""
    harness = harness or resolve_harness(cfg)
    t0 = time.time()
    pids: list = []

    def started(pid):
        pids.append(pid)
        register_agent(pid, root)
        beat_update(root, agent_pid=pid)
    try:
        r = sh(cmd, cwd, stdin=prompt, timeout=cfg["agent_timeout_s"], on_start=started)
    finally:
        beat_update(root, agent_pid=None)
        if pids:
            unregister_agent(pids[0])
    text, meta = parse_output(harness["parser"], r.stdout)
    record(root, {"kind": kind, "ticket": ticket, "attempt": attempt, "cwd": str(cwd), "harness": harness["name"],
                  "exit": r.returncode, "secs": round(time.time() - t0),
                  "session_id": meta["session_id"], "cost_usd": meta["cost_usd"],
                  "num_turns": meta["num_turns"], "usage": meta["usage"]})
    r.failure = agent_failure(r, text, meta)
    r.auth = bool(r.failure and (meta.get("subtype") == "authentication_failed" or AUTH_RE.search(
        "\n".join((text, r.stdout or "", r.stderr or "")))))
    if r.auth:
        pause_for_auth(cfg, root)
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
    hp = resolve_harness(cfg, t)
    r, text = run_agent(cfg, root, hp["prep_cmd"], root, PREP_PROMPT.format(path=t.ref, ticket=t.text), t.id, "prep",
                        harness=hp)
    if stop_requested():
        log(root, f"stopped by pause  prep {t.id}")
        return
    packet = text.strip() if not r.failure and text.strip() else f"Prep failed:\n\n```\n{r.failure or r.stderr[-2000:]}\n```"
    t.post_packet(packet)
    notify(cfg, root, f"Decision ready: {t.id} {t.title}")


# ---------- run: the AFK lane ----------

RUN_PROMPT = """Implement this ticket in the current repository (a git worktree on its own branch).
Stay inside the ticket's scope. Work test-first: use the /tdd skill if it's available
(red-green, one slice at a time); otherwise write a failing test before the code.
If docs/agents/worker-env.md exists, read it first: it lists what this fresh worktree
lacks (env files, dependencies, local data), the repo's verify command, and paths to leave alone.
Before you call it done, run the check that would catch your most likely mistake, after your
last edit, and read its output. Claim only what that output shows.
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


def sync_base(cfg: dict, root: Path) -> bool:
    """Merge the base branch into the integration branch when base has commits it lacks,
    so tickets build on current base. Returns False on a conflict (merge aborted)."""
    ensure_integration(cfg, root)
    base, integ = cfg["base_branch"], cfg["integration_branch"]
    ahead = sh(["git", "rev-list", "--count", f"{integ}..{base}"], root)
    if ahead.returncode != 0 or ahead.stdout.strip() == "0":
        return True
    tmp = integration_worktree(cfg, root)
    r = sh(["git", "merge", "--no-ff", "-m", f"runway: merge {base} into {integ}", base], tmp)
    if r.returncode == 0:
        log(root, f"sync  merged {base} into {integ}")
        return True
    sh(["git", "merge", "--abort"], tmp)
    head = sh(["git", "rev-parse", base], root).stdout.strip()
    seen = root / "_pm" / "runway-sync-conflict"
    msg = f"Blocked: {base} does not merge cleanly into {integ}; no tickets run until it is merged by hand"
    if seen.exists() and seen.read_text().strip() == head:
        log(root, msg)  # already notified for this base head
    else:
        seen.parent.mkdir(parents=True, exist_ok=True)
        seen.write_text(head + "\n")
        notify(cfg, root, msg)
    return False


def worktrees(cfg: dict, root: Path) -> Path:
    return root / cfg["worktree_dir"].replace("{repo}", root.name)


def run_ticket(cfg: dict, root: Path, tracker, t) -> None:
    ensure_integration(cfg, root)
    branch = f"runway/{t.effort}-{t.slug}"
    wt = (worktrees(cfg, root) / f"{t.effort}-{t.slug}").resolve()
    t.mark_claimed(branch, machine_name())
    # No tracker can claim atomically, so read the claim back: if another Mac stamped it after us, it keeps it.
    now_held = next((x.claimed_by for x in tracker.load() if x.id == t.id), None)
    if now_held and now_held != machine_name():
        log(root, f"skip {t.id} claimed by {now_held}")
        return
    log(root, f"run   {t.id} {t.title}  -> {branch}")

    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
    sh(["git", "branch", "-D", branch], root)
    sh(["git", "worktree", "add", "-b", branch, str(wt), cfg["integration_branch"]], root, check=True)

    extra, ok, detail, attempt = "", False, "", 0
    hp = resolve_harness(cfg, t)
    stopped = signed_out = False
    for attempt in range(1, cfg["max_attempts"] + 1):
        if stop_requested():
            stopped = True
            break
        beat(root, "agent", t.id, attempt)
        prompt = RUN_PROMPT.format(path=t.ref, ticket=t.text, extra=extra)
        r, _ = run_agent(cfg, root, hp["agent_cmd"], wt, prompt, t.id, "run", attempt, harness=hp)
        if stop_requested():
            stopped = True
            break
        if r.auth:  # not the ticket's fault: back in the queue, loop paused machine-wide
            signed_out = True
            break
        if r.failure:
            detail = f"Agent failed on attempt {attempt}: {r.failure}"
            log(root, f"fail  {t.id} attempt {attempt}: agent did not run")
            beat_update(root, last_result="fail")
            break
        q = wt / "RUNWAY_QUESTION.md"
        if q.exists():
            detail = "Agent stopped with a question:\n\n" + q.read_text()
            break
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-m", f"runway: {t.title} (auto-commit)"], wt)
        made = sh(["git", "rev-list", "--count", f"{cfg['integration_branch']}..HEAD"], wt).stdout.strip()
        if made in ("", "0"):  # a ticket always changes something; one that doesn't needs Joe to say so
            detail = f"The agent ran but `{branch}` has no commits. Runway assumes a ticket changes something."
            log(root, f"fail  {t.id} attempt {attempt}: no commits")
            break
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
    if stopped:  # pause --stop-now: back to ready, worktree and branch kept
        t.mark_ready("stopped by pause")
        log(root, f"stopped by pause  {t.id}")
        record(root, {"kind": "outcome", "ticket": t.id, "attempts": attempt, "result": "stopped", "detail": ""})
        return
    if signed_out:  # the ticket goes back to ready; the queue behind it is untouched
        t.mark_ready("Claude Code is signed out; Runway paused. Sign in, then `runway resume`.")
        record(root, {"kind": "outcome", "ticket": t.id, "attempts": attempt, "result": "signed-out", "detail": ""})
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
        return
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

PANEL_FIX_PROMPT = """Two independent reviewers (a Codex seat and a Claude seat) reviewed the current branch
(Runway's integration branch). Triage their findings yourself and fix what deserves fixing. Never ask Joe
anything; nobody is waiting to answer, so make your best judgment on every finding.

0. If a seat's section says NO REPORT, only one reviewer ran: nothing can be "agreed", so treat every finding as
   single-seat and verify it yourself.
1. Merge duplicates. A finding both seats raise (the same problem, even worded differently) is agreed: fix it.
2. A finding only one seat raises: verify it against the code, then judge. Fix it if it is real and the fix
   is in proportion. Otherwise skip it with a one-line reason.
   - Claude-seat-only findings get extra scrutiny: that seat shares priors with the builder.
   - Codex-only findings are the cross-vendor catches; don't dismiss one for being unfamiliar.
3. Do only what the accepted findings ask; no other refactoring. Commit once.
4. Reply with a Markdown triage table and nothing after it, one row per merged finding:
   | finding | flagged by (both / codex / claude) | action (fixed / skipped) | reason (required for each skip) |

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


def panel_review(cfg: dict, root: Path, wt: Path, tlist: str, spec: str):
    """The two-seat Ringer review. Returns (findings, has_findings), or None when Ringer is missing or
    no seat wrote a report (the caller then runs the single review)."""
    pm = root / "_pm"
    out = pm / "runway-panel"
    out.mkdir(parents=True, exist_ok=True)
    brief = out / "brief.md"
    brief.write_text(f"Runway integration branch `{cfg['integration_branch']}`, reviewed against "
                     f"`{cfg['base_branch']}`.\n{spec}\nTickets:\n{tlist}\n")
    t0 = time.time()
    pids: list = []

    def started(pid):
        pids.append(pid)
        register_agent(pid, root)  # so max_agents counts the panel and pause --stop-now can stop it
    try:
        r = sh([sys.executable, str(Path(__file__).resolve().parent / "ringer_panel.py"), "--repo", str(wt),
                "--base", cfg["base_branch"], "--brief-file", str(brief), "--out", str(out),
                "--budget-s", str(max(cfg["agent_timeout_s"] - 60, 60))], root,
               timeout=cfg["agent_timeout_s"], on_start=started)
    finally:
        if pids:
            unregister_agent(pids[0])
    if r.returncode == 3:
        log(root, "ringer not found; falling back to the single review.")
        return None
    try:
        seats = json.loads(r.stdout.strip().splitlines()[-1])["seats"]
    except (ValueError, KeyError, IndexError):
        seats = {}
    sections, statuses, missing = [], {}, []
    for seat in ("codex", "claude"):
        info = seats.get(seat) or {}
        statuses[seat] = info.get("status", "MISSING")
        report = Path(info["report"]) if info.get("report") else None
        if report and report.is_file():
            text = report.read_text().strip()
            (pm / f"runway-review-{seat}.md").write_text(text + "\n")
            note = ("\n(Ringer's check rejected this report; its findings are still worth reading.)\n"
                    if statuses[seat] == "FAIL" else "")
            sections.append(f"### {seat}{note}\n{text}")
        else:
            missing.append(seat)
    if not sections:
        log(root, f"ringer panel wrote no reports (exit {r.returncode}); falling back to the single review.")
        return None
    record(root, {"kind": "review", "ticket": "finish", "harness": "ringer-panel", "exit": r.returncode,
                  "secs": round(time.time() - t0), "seats": statuses})
    log(root, "ringer panel seats: " + ", ".join(f"{k} {v}" for k, v in statuses.items()))
    has_findings = any(re.search(r"^\W*Finding:", s, re.M) for s in sections)
    findings = "\n\n".join(sections)
    for seat in missing:
        findings += (f"\n\n### {seat}\nNO REPORT (status {statuses[seat]}). This was a single-seat review: "
                     f"nothing here was cross-checked by the {seat} seat.")
    return findings, has_findings


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

    if signin_waiting(cfg, root, [resolve_harness(cfg)["name"]], panel=cfg.get("review") == "panel", finish=True):
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
    hp = resolve_harness(cfg)
    panel = panel_review(cfg, root, wt, tlist, spec) if cfg.get("review") == "panel" else None
    if panel:
        findings, has_findings = panel
    else:
        r, text = run_agent(cfg, root, hp["review_cmd"], wt,
                            REVIEW_PROMPT.format(integration=integ, base=base, spec=spec, tickets=tlist),
                            "finish", "review", harness=hp)
        findings = text.strip()
        if r.failure or not findings:
            findings, has_findings = f"Review failed ({r.failure or 'no output'}).", False
        else:
            has_findings = findings.upper().rstrip(".") != "NO FINDINGS"
    if stop_requested() or (not panel and r.auth):
        log(root, "finish stopped by pause; the review is not recorded for this head.")
        return False

    # 2. One fix pass. Kept only if the check still passes.
    fix_note = "No fix pass needed."
    triage = ""
    if has_findings:
        before = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        fix_prompt = PANEL_FIX_PROMPT if panel else FIX_PROMPT
        fr, fix_text = run_agent(cfg, root, hp["fix_cmd"] or hp["agent_cmd"], wt,
                                 fix_prompt.format(findings=findings), "finish", "fix", harness=hp)
        if fr.failure:
            sh(["git", "reset", "--hard", "-q", before], wt)
            sh(["git", "clean", "-fdq"], wt)
        if panel:
            triage = fix_text.strip() or f"(The fixer returned no triage table, exit {fr.returncode}.)"
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-qm", "runway: review fixes (auto-commit)"], wt)
        after = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        if fr.failure:
            fix_note = fix_failure_note(fr.failure)
        elif after == before:
            fix_note = "The fix pass made no changes; the findings stand."
        elif sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"]).returncode == 0:
            fix_note = f"The fix pass committed {after[:8]} and the check still passes."
        else:
            sh(["git", "reset", "--hard", "-q", before], wt)
            fix_note = "The fix pass broke the check, so it was discarded; the findings stand."
            if triage:
                triage += "\n\nThe fix commit broke the check and was discarded: every row marked fixed above was NOT applied."
    if stop_requested():
        log(root, "finish stopped by pause; the review is not recorded for this head.")
        return False
    log(root, f"review {'findings' if has_findings else 'clean'}. {fix_note}")

    # 3. Evidence: the check on the final branch.
    c = sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])
    check_out = (c.stdout + c.stderr)[-3000:]
    stat = sh(["git", "diff", "--stat", f"{base}...HEAD"], wt).stdout[-3000:]

    # 4. The PR body, /pr style.
    review_line = f"{fix_note}\n\n{findings}" if has_findings else fix_note
    if triage:
        review_line = f"{fix_note}\n\n#### Triage\n\n{triage}\n\n{findings}"
    r, body = run_agent(cfg, root, hp["pr_cmd"] or hp["review_cmd"], wt,
                        PR_PROMPT.format(integration=integ, base=base, tickets=tlist, stat=stat,
                                         check=cfg["check_cmd"], code=c.returncode, check_out=check_out,
                                         review=review_line), "finish", "pr", harness=hp)
    if stop_requested():
        log(root, "finish stopped by pause; the review is not recorded for this head.")
        return False
    body = body.strip() if r.returncode == 0 and body.strip() else (
        f"## Summary\n\n```\n{stat}\n```\n\n## Evidence\n\n`{cfg['check_cmd']}` exited {c.returncode}.\n\n"
        f"```\n{check_out}\n```\n\n## Merge danger\n\nNot assessed (the PR-body agent failed).")
    body += (f"\n\n<details><summary>Runway review</summary>\n\n{review_line}\n\n"
             f"Tickets:\n{tlist}\n</details>\n")
    (root / "_pm").mkdir(exist_ok=True)
    (root / "_pm" / "runway-review.md").write_text(
        findings + "\n\n" + fix_note + "\n" + (f"\n## Triage\n\n{triage}\n" if triage else ""))
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

def transcript(session_id: str, harness: str = "claude") -> str | None:
    """Where a harness keeps a session, or None. Claude Code: ~/.claude/projects/<cwd as a folder name>/<id>.jsonl.
    Codex: ~/.codex/sessions/YYYY/MM/DD/rollout-<time>-<id>.jsonl. Other harnesses: none we can find."""
    if harness == "claude":
        home = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        hits = list((home / "projects").glob(f"*/{session_id}.jsonl"))
    elif harness == "codex":
        home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        hits = list((home / "sessions").glob(f"**/rollout-*-{session_id}.jsonl"))
    else:
        return None
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
        path = transcript(r["session_id"], r.get("harness") or "claude") or f"session {r['session_id']} (transcript not found on this machine)"
        lines.append(f"- {path}: {r['ticket']} {r['kind']}" + (f", {why}" if why else ""))
    prompt = ("/retro Read these sessions from Runway's unattended runs on this repo. Each ran headless "
              "in its own worktree from a ticket prompt, with no human to ask. Find what made them "
              "struggle and propose environment fixes (checks, navigation, AGENTS.md cuts), not code changes. "
              "Also compare what each ticket asked for with what landed on its branch, and name any drift "
              "(work outside the ticket, or acceptance it skipped).\n\n"
              + ("\n".join(lines) if lines else "(no session ids logged)") + "\n")
    out += ["", "## Prompt for /retro", "", "Sessions that struggled:" if flagged else
            "Nothing struggled, so these are the latest runs:", "", "```", prompt.rstrip(), "```", "",
            f"Run it from the repo: `claude \"$(cat _pm/runway-retro-prompt.md)\"`"]
    (root / "_pm" / "runway-retro-prompt.md").write_text(prompt)
    (root / "_pm" / "runway-retro.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


# ---------- commands ----------

def park_bad_harness(cfg: dict, root: Path, t) -> bool:
    """Park a ready ticket whose harness override is unknown: log it and hand it to Joe. True if parked."""
    err = harness_error(cfg, t) if t.status == "ready" else None
    if not err:
        return False
    log(root, f"park  {t.id} {err}")
    t.mark_needs_human("fix the harness label", f"Runway parked this ticket: {err}. Fix the harness override, then `runway go`.")
    return True


def tick(cfg: dict, root: Path, tracker) -> bool:
    """One pass. Returns True if it did anything."""
    did = False
    if paused_now(root) or machine_waiting(root):
        return False
    beat(root, "sync", tick_started=dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    tracker.sync()
    tickets = tracker.load()
    if signin_waiting_for_work(cfg, root, tickets):
        return False
    # 1. Judgment lookahead: prep every gated ticket that is on, or headed for, the frontier.
    for t in tickets:
        if active_pause():
            return did  # a pause landed mid-tick: finish what is running, start nothing new
        if park_bad_harness(cfg, root, t):
            did = True
            continue
        if t.gate == "human" and t.status == "ready" and will_unblock_without_joe(t, tickets):
            prep(cfg, root, t)
            did = True
    # 2. AFK lane: bring base into integration, then run the first ready auto (or approved) ticket.
    if active_pause():
        return did
    if machine_waiting(root):
        return did  # a rule began (or the cap filled) during prep: start nothing new
    if not sync_base(cfg, root):
        return did
    tickets = tracker.load()
    me = machine_name()
    for t in tickets:
        if t.gate in RUNNABLE_GATES and t.status in ("ready", "claimed") and unblocked(t, tickets):
            # A ticket another Mac is running reads as claimed, not ready, so the check covers both.
            if t.claimed_by and t.claimed_by != me:
                log(root, f"skip {t.id} claimed by {t.claimed_by}")
                continue
            if t.status != "ready":
                continue
            if park_bad_harness(cfg, root, t):
                did = True
                continue
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
    loaded = tracker.load()
    groups = group_tickets(loaded)
    grouped = {t.id for ts in groups.values() for t in ts}

    def full_id(t, b: str) -> str:
        return f"{t.effort}/{b}" if b.isdigit() else b  # markdown blockers are bare numbers

    def entry(t) -> dict:
        waiting = t.status == "needs-human"
        return {"id": t.id, "title": t.title, "url": t.url or None, "status": t.status, "gate": t.gate,
                "blocked_by": [full_id(t, b) for b in t.blocked_by],
                "waiting_on": (t.h("Waiting on") or None) if waiting else None,
                "packet": t.packet if waiting else None, "harness": resolve_harness(cfg, t)["name"], "claimed_by": t.claimed_by}

    return {"version": 1, "repo": str(root), "tracker": cfg.get("tracker", "markdown"),
            "machine": machine_name(), "paused": active_pause(clean=False),
            "signin": read_signin(root),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "groups": {k: [t.id for t in ts] for k, ts in groups.items()},
            "tickets": [entry(t) for t in loaded if t.id in grouped]}


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


# ---------- the menu bar app ----------

APP_PATH = Path("/Applications/Runway.app")


def ensure_app(app: Path = APP_PATH, env=None) -> bool:
    """Open the Runway menu bar app in the background when a run starts and it isn't running, so a tick started
    by launchd or by Claude is never invisible. macOS only; a Mac without the app, RUNWAY_NO_APP, or a test run
    skips it. True when it asked macOS to open the app."""
    env = os.environ if env is None else env
    if sys.platform != "darwin" or env.get("RUNWAY_NO_APP") or env.get("PYTEST_CURRENT_TEST") or not app.exists():
        return False
    if subprocess.run(["pgrep", "-xq", "Runway"], capture_output=True).returncode == 0:
        return False
    return subprocess.run(["open", "-g", str(app)], capture_output=True).returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="target repo (git checkout Runway works in)")
    ap.add_argument("--config", help="JSON config (default: <root>/runway.json if present)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true", help="machine-readable queue (shape in the module docstring)")
    sub.add_parser("whoami", help="print this Mac's name, as stamped on claims")
    sub.add_parser("tick")
    pz = sub.add_parser("pause", help="pause every loop on this Mac (holds with the app closed)")
    pz.add_argument("--until", help="resume at this ISO-8601 time")
    pz.add_argument("--for", dest="span", help="resume after this long, e.g. 30m, 1h, 2d")
    pz.add_argument("--stop-now", action="store_true", help="also stop the running agent and return its ticket to ready")
    sub.add_parser("resume", help="delete the pause")
    sub.add_parser("machine", help="print this Mac's quiet-time rules and whether a tick would run now")
    lp = sub.add_parser("loop")
    lp.add_argument("--max-ticks", type=int, default=50)
    g = sub.add_parser("go"); g.add_argument("ticket"); g.add_argument("note", nargs="?", default="")
    n = sub.add_parser("no"); n.add_argument("ticket"); n.add_argument("note", nargs="?", default="")
    sub.add_parser("setup", help="Linear only: check the key, team and project, and create Runway's labels")
    sub.add_parser("finish", help="review the integration branch, fix once, check, and write the PR body now")
    rt = sub.add_parser("retro", help="usage per ticket, and a /retro prompt for the runs that struggled")
    rt.add_argument("--last", type=int, default=200, help="log records to read (default 200)")
    a = ap.parse_args()
    if a.cmd == "whoami":
        print(machine_name())
        return

    root = Path(a.root).resolve()
    if a.cmd == "pause":
        cmd_pause(root, a.until, a.span, a.stop_now)
        return
    if a.cmd == "resume":
        cmd_resume()
        return
    if a.cmd == "machine":
        print(describe_machine(root))
        return
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
        ensure_app()
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
                        if active_pause() or machine_block():
                            beat(root, "idle")  # paused or waiting: no finish step, and no stale phase under a dead pid
                            return
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
