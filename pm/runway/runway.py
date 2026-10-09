#!/usr/bin/env python3
"""Runway: a minimal judgment-aware task runner for a pm-style tracker.

The loop never waits on Joe. Each tick it:
  1. Preps a decision packet for every human-gated ticket that is (or will soon be)
     on the frontier, and parks it as needs-human. Joe answers in the tracker
     (or with `runway go NN`), and the next tick picks the answer up.
  2. Runs the next ready auto ticket: agent in a git worktree on its own branch,
     then the check command. Pass -> merged into the integration branch, resolved.
     Fail -> one retry with the failure output, then parked as needs-human.

When the queue is finished, `loop` runs a finish step once per integration head
that carries new ticket work (heads moved only by `runway: merge <base> into <integration>` syncs
are skipped and recorded; `runway finish` always runs):
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

  {"version": 1, "repo": "/abs/path", "tracker": "markdown|linear|github", "machine": "Mini-One",
   "generated_at": "ISO-8601",
   "groups": {"waiting": [id...], "running": [...], "ready_auto": [...],
              "ready_prep": [...], "blocked": [...], "done": [...]},
   "tickets": [{"id", "title", "url", "status", "gate", "blocked_by": [id...],
                "waiting_on", "packet", "harness", "claimed_by", "errored"}]}

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
  errored  The kind of the ticket's latest attempt that didn't merge, from _pm/runway-runs.jsonl
           (agent-failed, no-commits, check-failed, merge-conflict, signed-out), or null. A merge clears it.

`runway discuss <ticket>` writes _pm/discuss/<id>.md (ticket text, packet, Runway's park comment, blockers,
attempts with kind, check exit and transcript path, the ticket's log lines) and replaces the process with an
interactive `claude` in the repo root, told to follow the runway skill's "Talk a ticket through" section. It
takes a waiting ticket or an errored one (a ticket still being retried counts); anything else exits non-zero
and starts nothing. `runway discuss --loop` is for the loop itself and always runs: _pm/discuss/loop.md holds
the heartbeat, `launchctl print` for the job, the pause, the last sign-in check, log tails and the last runs.
Always the claude harness. A GitHub brief carries trusted authors' comments only.

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

A tracker that doesn't answer (timeout, connection reset, 5xx; Linear or GitHub, every `gh` call has a
`timeout_s`, default 60) is retried twice with a 1s then 3s backoff (transient.py; RUNWAY_BACKOFF_S="0,0"
turns the wait off). Still failing, the tick ends: one `waiting: tracker not answering: <call>` log line,
heartbeat `waiting` with that reason, one notification until the tracker answers again (state in
`_pm/runway-tracker.json`), exit 0, the ticket and its worktree left as they are. Auth errors are not
retried. A comment or close that timed out is looked up before it is repeated, so it never posts twice.
At the start of a tick, a ticket claimed by this Mac that no live Runway process holds (the heartbeat's
pid is dead, or it names another ticket) is a crash's orphan: it goes back to ready with a "recovered after
a crash" comment and runs again. A claim held by a live process, or by another Mac, is never touched.

Trackers (config key "tracker"):
  markdown (default)  pm's local markdown (.scratch/<effort>/issues/NN-slug.md) with
                      one extra header line: `Gate: human` or `Gate: auto` (default).
  linear              Linear issues, through linear_tracker.py. See its docstring.
  github              A repo's GitHub Issues, through github_tracker.py (claims, closes, parks and releases ready-for-agent issues; repo from
                      "github": {"repo": "owner/name"} or the clone's origin). See its docstring.

The base branch is touched only by `"merge": "on_pass"`: a passing review with no hold merges the integration
branch into base at exactly the reviewed SHA (`gh pr merge --match-head-commit` for "pr": "draft", a local
`git merge --no-ff` plus push for "pr": "file"). Otherwise Joe merges the integration branch himself.

No dependencies beyond Python 3.9+ and git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import field, make_dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transient  # noqa: E402

HEADER_RE = re.compile(r"^(Status|Blocked by|Waiting on|Gate|Type|Branch|Claimed-by|Harness):\s*(.*)$", re.M)
DONE = {"resolved", "done", "closed"}
RUNNABLE_GATES = ("auto", "approved")
DEFAULT_CONFIG = {
    # "markdown", "linear" or "github". Linear settings live under the "linear" key.
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
    # What the round's pass/fail verdict is for. "off": only record it. "shadow": record it and say what
    # would have merged. "on_pass": a pass with no hold merges the reviewed commit into base. Only on_pass ever merges.
    "merge": "off",
    # With merge shadow or on_pass, a failed review files a fix ticket instead of running the fix pass.
    # This is the most reviews per batch: the first plus (review_rounds - 1) re-reviews after a fix ticket.
    "review_rounds": 2,
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


MARK = "🛫 runway"  # every body and comment Runway writes starts with this, so Joe's are told apart


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

    def create(self, title: str, body: str, labels: list[str], effort: str | None = None) -> str:
        """Write the next numbered issue file and return its id ("<effort>/<NN>"). The effort is the one
        under .scratch/ unless there are several, then it must be named. The body starts with the 🛫 marker."""
        efforts = sorted(p.parent.name for p in self.root.glob(".scratch/*/issues"))
        if effort is None:
            if len(efforts) != 1:
                raise ValueError(f"name the effort to create in: {efforts or 'none under .scratch/'}")
            effort = efforts[0]
        folder = self.root / ".scratch" / effort / "issues"
        folder.mkdir(parents=True, exist_ok=True)
        nums = [int(p.name.split("-", 1)[0]) for p in folder.glob("*.md") if p.name.split("-", 1)[0].isdigit()]
        num = f"{max(nums, default=0) + 1:02d}"
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50].strip("-") or "ticket"
        text = f"# {title}\n\nStatus: ready\n"
        if labels:
            text += f"Labels: {', '.join(labels)}\n"
        text += f"\n{MARK} · {body.strip()}\n"
        (folder / f"{num}-{slug}.md").write_text(text)
        return f"{effort}/{num}"

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
    if kind == "github":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from github_tracker import GitHubTracker
        return GitHubTracker(root, cfg)
    sys.exit(f"Unknown tracker {kind!r}; use 'markdown', 'linear' or 'github'.")


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


def answering_model(model_usage) -> str | None:
    """The model that did most of the work in a Claude result's `modelUsage` (the costliest entry)."""
    if not isinstance(model_usage, dict) or not model_usage:
        return None

    def cost(m):
        u = model_usage[m]
        return (u.get("costUSD") or 0) if isinstance(u, dict) else 0
    return max(model_usage, key=cost)


def parse_output(parser: str, stdout: str) -> tuple[str, dict]:
    """(text, meta) from a harness's stdout. meta has session_id, cost_usd, num_turns, usage and model
    (which model answered, from Claude's modelUsage), each None when the harness doesn't report it.
    Unparseable output comes back as text unchanged."""
    meta = {"session_id": None, "cost_usd": None, "num_turns": None, "usage": None, "is_error": False,
            "subtype": None, "model": None}
    if parser == "claude":
        try:
            d = json.loads(stdout)
        except ValueError:
            return stdout, meta
        if isinstance(d, dict) and "result" in d:
            meta.update(session_id=d.get("session_id"), cost_usd=d.get("total_cost_usd"),
                        num_turns=d.get("num_turns"), usage=d.get("usage"),
                        is_error=bool(d.get("is_error")), subtype=d.get("subtype"),
                        model=answering_model(d.get("modelUsage")))
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
                  "num_turns": meta["num_turns"], "usage": meta["usage"], "model": meta["model"]})
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
/tdd asks you to confirm test seams with the user; this run is headless, so there is no one to
ask. In this run the agreed seams are the ones the ticket or its spec names. If they name none,
test at the existing public interface of the module being changed. Don't stop to confirm seams.
Only a new module or a changed public interface is a reason to write RUNWAY_QUESTION.md.
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
    t.mark_claimed(branch, machine_name())
    # No tracker can claim atomically, so read the claim back: if another Mac stamped it after us, it keeps it.
    now_held = next((x.claimed_by for x in tracker.load() if x.id == t.id), None)
    if now_held and now_held != machine_name():
        log(root, f"skip {t.id} claimed by {now_held}")
        return
    log(root, f"run   {t.id} {t.title}  -> {branch}")

    settle(cfg, root, tracker, t, attempt(cfg, root, t))


# How one build attempt ended. `kind` is one of: stopped, signed-out, question, agent-failed, no-commits,
# check-failed, merge-conflict, merged. `detail` is the text a human needs, or ''.
# make_dataclass, not @dataclass: this file uses `from __future__ import annotations`, and @dataclass on string
# annotations looks the module up in sys.modules, which fails when a test loads runway.py by file path.
Outcome = make_dataclass("Outcome", [("kind", str), ("attempts", int), ("detail", str, field(default=""))],
                         namespace={"__module__": __name__})


def attempt(cfg: dict, root: Path, t) -> Outcome:
    """Build the ticket in a fresh worktree: agent, check, retry, then merge into integration.
    Never touches the tracker, `notify` or the outcome `record`; the caller decides what the outcome means.
    Live effects (run_agent records, auth pause, fail beats, phases) stay here. Exceptions stay exceptions."""
    branch = f"runway/{t.effort}-{t.slug}"
    wt = (worktrees(cfg, root) / f"{t.effort}-{t.slug}").resolve()
    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
    sh(["git", "branch", "-D", branch], root)
    sh(["git", "worktree", "add", "-b", branch, str(wt), cfg["integration_branch"]], root, check=True)

    extra, detail, n, kind = "", "", 0, "agent-failed"
    hp = resolve_harness(cfg, t)
    for n in range(1, cfg["max_attempts"] + 1):
        if stop_requested():
            return Outcome("stopped", n)
        beat(root, "agent", t.id, n)
        prompt = RUN_PROMPT.format(path=t.ref, ticket=t.text, extra=extra)
        r, _ = run_agent(cfg, root, hp["agent_cmd"], wt, prompt, t.id, "run", n, harness=hp)
        if stop_requested():
            return Outcome("stopped", n)
        if r.auth:  # not the ticket's fault: back in the queue, loop paused machine-wide
            return Outcome("signed-out", n)
        if r.failure:
            log(root, f"fail  {t.id} attempt {n}: agent did not run")
            beat_update(root, last_result="fail")
            return Outcome("agent-failed", n, f"Agent failed on attempt {n}: {r.failure}")
        q = wt / "RUNWAY_QUESTION.md"
        if q.exists():
            return Outcome("question", n, "Agent stopped with a question:\n\n" + q.read_text())
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-m", auto_commit_msg(t)], wt)
        made = sh(["git", "rev-list", "--count", f"{cfg['integration_branch']}..HEAD"], wt).stdout.strip()
        if made in ("", "0"):  # a ticket always changes something; one that doesn't needs Joe to say so
            log(root, f"fail  {t.id} attempt {n}: no commits")
            return Outcome("no-commits", n,
                           f"The agent ran but `{branch}` has no commits. Runway assumes a ticket changes something.")
        beat(root, "check", t.id, n)
        c = sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])
        record(root, {"kind": "check", "ticket": t.id, "attempt": n, "exit": c.returncode})
        if c.returncode == 0:
            beat(root, "merge", t.id)
            if merge_into_integration(cfg, root, branch, commit_ref(t)):
                return Outcome("merged", n, detail)  # detail may still carry an earlier attempt's check failure
            return Outcome("merge-conflict", n,
                           f"Check passed but `{branch}` did not merge cleanly into `{cfg['integration_branch']}`.")
        kind = "check-failed"
        detail = f"Check failed on attempt {n}:\n\n```\n{(c.stdout + c.stderr)[-3000:]}\n```"
        extra = f"\nThe previous attempt failed the check. Fix it:\n\n{detail}\n"
        log(root, f"fail  {t.id} attempt {n}")
        beat_update(root, last_result="fail")
    return Outcome(kind, n, detail or "Agent run failed with no detail.")


# What Runway does next for each Outcome kind. write: the ticket's new status; notify: ping Joe; result: the
# `result` of the outcome row in runway-runs.jsonl; last_result: heartbeat value (None leaves it as it is);
# worktree/branch: whether settle removes them (a stopped run keeps both so it resumes where it left off).
_PARK = dict(write="needs-human", notify=True, result="needs-human", last_result="park",
             worktree="remove", branch="keep")
SETTLE = {
    "stopped": dict(write="ready", notify=False, result="stopped", last_result=None, worktree="keep", branch="keep"),
    "signed-out": dict(write="ready", notify=False, result="signed-out", last_result=None,
                       worktree="remove", branch="keep"),
    "merged": dict(write="resolved", notify=False, result="done", last_result="pass",
                   worktree="remove", branch="keep"),
    "question": _PARK, "agent-failed": _PARK, "no-commits": _PARK, "check-failed": _PARK, "merge-conflict": _PARK,
}


def settle(cfg: dict, root: Path, tracker, t, outcome: Outcome) -> None:
    """Act on an Outcome per its SETTLE row: reload the ticket, write the tracker, notify, heartbeat, record,
    clean up. The one place a build attempt's ending turns into effects."""
    row = SETTLE[outcome.kind]
    branch = f"runway/{t.effort}-{t.slug}"
    wt = (worktrees(cfg, root) / f"{t.effort}-{t.slug}").resolve()
    t = tracker.reload(t)  # agent may not touch it, but reload to be safe
    if row["write"] == "resolved":
        t.mark_resolved(f"Done on `{branch}`, check passed, merged into `{cfg['integration_branch']}`.")
        log(root, f"done  {t.id}")
    elif row["write"] == "needs-human":
        t.mark_needs_human("run failed or asked a question", outcome.detail or "Agent run failed with no detail.")
    elif outcome.kind == "signed-out":  # the queue behind it is untouched
        t.mark_ready("Claude Code is signed out; Runway paused. Sign in, then `runway resume`.")
    else:  # stopped: pause --stop-now
        t.mark_ready("stopped by pause")
        log(root, f"stopped by pause  {t.id}")
    if row["notify"]:
        notify(cfg, root, f"Blocked: {t.id} {t.title}")
    if row["last_result"]:
        beat_update(root, last_result=row["last_result"])
    record(root, {"kind": "outcome", "ticket": t.id, "attempts": outcome.attempts, "result": row["result"],
                  "outcome": outcome.kind, "detail": outcome.detail[:500]})
    if row["worktree"] == "remove":
        sh(["git", "worktree", "remove", "--force", str(wt)], root)
    if row["branch"] == "remove":
        sh(["git", "branch", "-D", branch], root)


def integration_worktree(cfg: dict, root: Path) -> Path:
    """Runway's own checkout of the integration branch, so the user's checkout is never disturbed."""
    tmp = (worktrees(cfg, root) / "_integration").resolve()
    if not tmp.exists():
        sh(["git", "worktree", "add", str(tmp), cfg["integration_branch"]], root, check=True)
    return tmp


def commit_ref(t) -> str:
    """The ticket's reference for a commit subject: `(#12)` on GitHub, `(DAT-41)` on Linear (which links it),
    nothing for pm's local tickets. Matt's /code-review reads these to find the tickets behind a change."""
    return f"({t.id})" if getattr(t, "effort", "") in ("github", "linear") else ""


def auto_commit_msg(t) -> str:
    return " ".join(p for p in ("runway:", t.title, commit_ref(t), "(auto-commit)") if p)


def refs_block(done: list) -> str:
    """The PR body's ticket list. `Refs`, never `Closes`: Runway closes an issue when its branch merges into
    integration, so merging the PR must not try to close it again."""
    lines = []
    for t in done:
        eff = getattr(t, "effort", "")
        if eff == "github":
            lines.append(f"Refs {t.id}")
        elif eff == "linear":
            lines.append(f"Refs {t.ref}")
    return "\n".join(lines)


def merge_into_integration(cfg: dict, root: Path, branch: str, ref: str = "") -> bool:
    tmp = integration_worktree(cfg, root)
    msg = f"runway: merge {branch}" + (f" {ref}" if ref else "")
    r = sh(["git", "merge", "--no-ff", "-m", msg, branch], tmp)
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

Start your reply with a line `Reviewed: <sha>`, the full output of `git rev-parse HEAD` as you see it
(the head under review is {head}); a reply without it is thrown away. Then a Markdown list of findings,
most severe first, each with file:line and why it matters. If nothing is worth fixing, reply with
exactly: NO FINDINGS
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

JUDGE_PROMPT = """You are the judge for a finished Runway round. Do NOT change any files. Decide pass or fail for the
current branch (`{integration}`, reviewed against `{base}`; `git diff {base}...HEAD` shows the change).
The check `{check}` was run after the last edit and exited {code}.

Triage the review findings with these rules:
1. Merge duplicates. A finding both seats raise (the same problem, even worded differently) is BLOCKING unless
   you show from the code that it is wrong.
2. A finding only one seat raises: verify it against the code first. Blocking only if it is real and matters;
   otherwise non-blocking, or drop it with a reason. Claude-seat-only findings get extra scrutiny: that seat
   shares priors with the builder. Codex-only findings are the cross-vendor catches; don't dismiss one for
   being unfamiliar.
3. If a seat's section says NO REPORT, only one reviewer ran: treat every finding as single-seat.
4. For every acceptance criterion in every done ticket below, name the evidence (a test, a file:line, a command
   output). A criterion with no evidence is a blocking finding.
5. Never ask anyone anything. Make your best judgment.

Reply with one JSON object and nothing after it:
{{"verdict": "pass" or "fail",
  "blocking": ["finding, with file:line and why"],
  "non_blocking": ["finding"],
  "criteria": [{{"ticket": "id", "criterion": "text", "evidence": "what shows it, or empty if none"}}]}}
"verdict" is "pass" only when "blocking" is empty.

Done tickets and their text:
{tickets}

Review findings (fix pass: {fix_note}):
{findings}
"""


def _json_objects(text: str):
    dec, i = json.JSONDecoder(), 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            yield obj
        i = end


def parse_verdict(text: str):
    """The judge's JSON object, normalised, or None when nothing parseable came back."""
    for obj in reversed(list(_json_objects(text or ""))):
        if "verdict" not in obj:
            continue

        def strs(key):
            v = obj.get(key)
            return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []
        raw = obj.get("criteria")
        crit = [c for c in (raw if isinstance(raw, list) else []) if isinstance(c, dict)]
        return {"verdict": str(obj.get("verdict")).strip().lower(), "blocking": strs("blocking"),
                "non_blocking": strs("non_blocking"),
                "criteria": [{"ticket": str(c.get("ticket", "")), "criterion": str(c.get("criterion", "")),
                              "evidence": str(c.get("evidence") or "").strip()} for c in crit]}
    return None


def decide_verdict(check_exit: int, parsed, valid_reviews=None) -> dict:
    """pass/fail for the round. Fails on a red check, an unparseable judge, any blocking finding or a
    criterion with no evidence. Never passes by default."""
    blocking = list(parsed["blocking"]) if parsed else []
    non_blocking = list(parsed["non_blocking"]) if parsed else []
    criteria = list(parsed["criteria"]) if parsed else []
    if check_exit != 0:
        blocking.insert(0, f"The check failed after the last edit (exit {check_exit}).")
    if valid_reviews == 0:
        blocking.insert(0, "No review seat proved which commit it reviewed (no valid Reviewed: <sha> report).")
    if parsed is None:
        blocking.insert(0, "The judge returned nothing parseable, so nothing was shown to pass.")
    for c in criteria:
        if not c["evidence"]:
            blocking.append(f"No evidence for acceptance criterion ({c['ticket']}): {c['criterion']}")
    ok = parsed is not None and parsed["verdict"] == "pass" and check_exit == 0 and not blocking and valid_reviews != 0
    return {"verdict": "pass" if ok else "fail", "blocking": blocking, "non_blocking": non_blocking,
            "criteria": criteria}


def hold_reason(pr_body: str, tickets: list) -> str:
    """Why the batch must never auto-merge, or '' when it may: the PR body's merge danger says one-way (or says
    nothing clear), or any ticket was gated for a human (needs-human, or a human gate Joe later approved)."""
    if any(t.gate in ("human", "approved") or t.status == "needs-human" for t in tickets):
        return "a ticket was gated for a human"
    m = re.search(r"^#+\s*Merge danger\s*$(.*?)(?=^#+\s|\Z)", pr_body, re.M | re.S | re.I)
    door = re.search(r"\b(one|two)[- ]way\b", m.group(1), re.I) if m else None
    if door is None:
        return "the merge danger is not stated"
    return "one-way door" if door.group(1).lower() == "one" else ""


def is_one_way(pr_body: str, tickets: list) -> bool:
    """True when the batch must never auto-merge (see hold_reason)."""
    return bool(hold_reason(pr_body, tickets))


def verdict_line(v: dict, merge: str, hold: bool, sha: str = "") -> str:
    n = len(v["blocking"])
    if v["verdict"] != "pass":
        return f"Review: FAIL, {n} blocking finding{'' if n == 1 else 's'}"
    if hold:
        return "Review: PASS (hold: one-way door, never auto-merges)"
    if merge == "shadow":
        return "Review: PASS (would merge" + (f" {sha}" if sha else "") + ")"
    return "Review: PASS (would merge)" if merge == "on_pass" else "Review: PASS"


def verdict_report(v: dict, line: str, hold: bool, sha: str) -> str:
    bl = lambda xs: "\n".join(f"- {x}" for x in xs) or "- none"
    rows = "\n".join(f"| {c['ticket']} | {c['criterion'].replace('|', '/')} | "
                     f"{c['evidence'].replace('|', '/') or 'NONE'} |" for c in v["criteria"])
    table = ("| ticket | criterion | evidence |\n|---|---|---|\n" + rows) if rows else "none listed"
    return (f"{line}\n\nReviewed SHA: `{sha}`  \nHold: {'yes' if hold else 'no'}\n\n"
            f"### Blocking findings\n\n{bl(v['blocking'])}\n\n### Non-blocking findings\n\n{bl(v['non_blocking'])}"
            f"\n\n### Acceptance criteria and evidence\n\n{table}\n")


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

Start directly with the Summary heading. No preamble. Do not write `Closes`, `Fixes` or `Resolves`
for a ticket: Runway closes tickets itself and adds the `Refs` lines.

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


def reviewed_sha(text: str):
    """The sha on a report's `Reviewed: <sha>` line, or None. Only the first non-blank line counts."""
    for line in text.splitlines():
        if line.strip():
            m = re.match(r"^\W*Reviewed:\s*`?([0-9a-fA-F]{7,40})\b", line.strip())
            return m.group(1).lower() if m else None
    return None


def sha_matches(claimed, head: str) -> bool:
    return bool(claimed) and len(claimed) >= 7 and head.lower().startswith(claimed)


def panel_review(cfg: dict, root: Path, wt: Path, tlist: str, spec: str):
    """The two-seat Ringer review. Returns (findings, has_findings, seat_rows), or None when Ringer is missing or
    no seat wrote a report (the caller then runs the single review)."""
    pm = root / "_pm"
    out = pm / "runway-panel"
    out.mkdir(parents=True, exist_ok=True)
    # Old seat reports go first, so a seat that writes nothing this run can't be answered by last run's.
    for seat in ("codex", "claude"):
        (pm / f"runway-review-{seat}.md").unlink(missing_ok=True)
    integ, base = cfg["integration_branch"], cfg["base_branch"]
    head = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
    brief = out / "brief.md"
    brief.write_text(f"Runway integration branch `{integ}`, reviewed against `{base}`.\n"
                     f"Review the range `{base}...{integ}`, current head {head}. Ignore any other commit.\n"
                     f"Start your report with a line `Reviewed: <sha>`: the full output of `git rev-parse HEAD`\n"
                     f"in the tree you reviewed (it must be {head}). A report without it, or with another sha, is discarded.\n"
                     f"{spec}\nTickets:\n{tlist}\n")
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
        rjson = json.loads(r.stdout.strip().splitlines()[-1])
        seats = rjson["seats"]
    except (ValueError, KeyError, IndexError):
        rjson, seats = {}, {}
    sections, statuses, missing, seat_rows = [], {}, [], []
    run_id = rjson.get("run_id") or time.strftime("runway-%Y%m%d-%H%M%S", time.gmtime(t0))
    for seat in ("codex", "claude"):
        info = seats.get(seat) or {}
        statuses[seat] = info.get("status", "MISSING")
        report = Path(info["report"]) if info.get("report") else None
        claimed = None
        if report and report.is_file():
            text = report.read_text().strip()
            claimed = reviewed_sha(text)
            if sha_matches(claimed, head):
                (pm / f"runway-review-{seat}.md").write_text(text + "\n")
                note = ("\n(Ringer's check rejected this report; its findings are still worth reading.)\n"
                        if statuses[seat] == "FAIL" else "")
                sections.append(f"### {seat}{note}\n{text}")
            else:
                why = "no Reviewed: line" if claimed is None else f"reviewed {claimed}, not {head[:12]}"
                log(root, f"{seat} seat report discarded: {why}.")
                statuses[seat] = "STALE" if claimed else "NO SHA"
                missing.append(seat)
        else:
            missing.append(seat)
        seat_rows.append({"seat": seat, "run_id": run_id, "sha": claimed, "at": now(),
                          "status": statuses[seat]})
    if not seat_rows or all(r["status"] == "MISSING" for r in seat_rows):
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
    return findings, has_findings, seat_rows


def ticket_work_since(cfg: dict, root: Path, reviewed) -> bool:
    """True if anything but Runway's own base syncs landed on the integration branch since `reviewed`.
    A missing, unreadable or non-ancestor reviewed head counts as work (finish re-runs, as it always did)."""
    integ = cfg["integration_branch"]
    if not isinstance(reviewed, str) or not reviewed:
        return True
    if sh(["git", "merge-base", "--is-ancestor", reviewed, integ], root).returncode != 0:
        return True
    r = sh(["git", "rev-list", "--first-parent", "--format=%s", f"{reviewed}..{integ}"], root)
    if r.returncode != 0:
        return True
    sync = f"runway: merge {cfg['base_branch']} into {integ}"
    subjects = [l for l in r.stdout.splitlines() if l and not l.startswith("commit ")]
    return any(sub != sync for sub in subjects)


def reset_worktree(wt: Path, reset: bool = True) -> None:
    """Make Runway's integration worktree match its commit: tracked files reset, untracked files and
    ignored build caches (a deleted folder's __pycache__) removed. `-X` takes only what .gitignore names,
    so nothing hand-made is lost beyond what the first `git clean -fd` already took in this private worktree."""
    if reset:
        sh(["git", "reset", "--hard", "-q"], wt)
    sh(["git", "clean", "-fdq"], wt)
    sh(["git", "clean", "-fdXq"], wt)


def finish(cfg: dict, root: Path, tracker, force: bool = False) -> bool:
    """Review the integration branch as a whole, fix once, check, and write the PR body.
    Runs once per integration head that carries new ticket work (base syncs alone don't), unless forced.
    Returns True if it ran."""
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
    try:
        state = json.loads(state_p.read_text()) if state_p.exists() else {}
    except (OSError, ValueError):
        state = {}  # unreadable: no reviewed head, so finish runs as it always did
    if not isinstance(state, dict):
        state = {}
    head = sh(["git", "rev-parse", integ], root).stdout.strip()
    if not force and state.get("head") == head:
        return False
    if not force and not ticket_work_since(cfg, root, state.get("head")):
        # Only base syncs moved the head: nothing new to review. Record it so the next check is cheap.
        (root / "_pm").mkdir(exist_ok=True)
        state_p.write_text(json.dumps({**state, "head": head, "at": now()}))
        return False

    if signin_waiting(cfg, root, [resolve_harness(cfg)["name"]], panel=cfg.get("review") == "panel", finish=True):
        return False
    beat(root, "finish")
    log(root, f"finish {integ} ({ahead} commits ahead of {base})")
    wt = integration_worktree(cfg, root)
    reset_worktree(wt)
    done = [t for t in tickets if t.status in DONE]
    open_ = [t for t in tickets if t.status not in DONE]
    tlist = "\n".join([f"- {t.id} {t.title} ({t.ref})" for t in done] +
                      [f"- NOT DONE: {t.id} {t.title} ({t.status})" for t in open_]) or "- (none listed)"
    spec = f"\nSpec: {cfg['spec']}\n" if cfg.get("spec") else ""

    # 1. Review the whole branch against the tickets.
    hp = resolve_harness(cfg)
    review_head = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
    panel = panel_review(cfg, root, wt, tlist, spec) if cfg.get("review") == "panel" else None
    if panel:
        findings, has_findings, seat_rows = panel
    else:
        r, text = run_agent(cfg, root, hp["review_cmd"], wt,
                            REVIEW_PROMPT.format(integration=integ, base=base, spec=spec, tickets=tlist,
                                                 head=review_head),
                            "finish", "review", harness=hp)
        findings = text.strip()
        claimed = reviewed_sha(findings)
        status = "PASS"
        if r.failure or not findings:
            findings, has_findings = f"Review failed ({r.failure or 'no output'}).", False
            status = "MISSING"
        elif not sha_matches(claimed, review_head):
            why = "no Reviewed: line" if claimed is None else f"reviewed {claimed}, not {review_head[:12]}"
            log(root, f"single review discarded: {why}.")
            findings, has_findings = f"Review discarded ({why}). NO REPORT.", False
            status = "STALE" if claimed else "NO SHA"
        else:
            findings = re.sub(r"^\s*\W*Reviewed:[^\n]*\n?", "", findings, count=1).strip()
            has_findings = findings.upper().rstrip(".") != "NO FINDINGS"
        seat_rows = [{"seat": "single", "run_id": f"single-{int(time.time())}", "sha": claimed, "at": now(),
                      "status": status}]
    if stop_requested() or (not panel and r.auth):
        log(root, "finish stopped by pause; the review is not recorded for this head.")
        return False

    # 2. One fix pass. Kept only if the check still passes. With merge shadow/on_pass there is none:
    # a failed review files a fix ticket, so every fix is reviewed before it can merge.
    files_tickets = cfg.get("merge", "off") in ("shadow", "on_pass")
    fix_note = "No fix pass needed."
    triage = ""
    if has_findings and files_tickets:
        fix_note = "No fix pass (merge is on): a failed review files a fix ticket instead."
    elif has_findings:
        before = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        fix_prompt = PANEL_FIX_PROMPT if panel else FIX_PROMPT
        fr, fix_text = run_agent(cfg, root, hp["fix_cmd"] or hp["agent_cmd"], wt,
                                 fix_prompt.format(findings=findings), "finish", "fix", harness=hp)
        if fr.failure:
            sh(["git", "reset", "--hard", "-q", before], wt)
            reset_worktree(wt, reset=False)
        if panel:
            triage = fix_text.strip() or f"(The fixer returned no triage table, exit {fr.returncode}.)"
        sh(["git", "add", "-A"], wt)
        sh(["git", "commit", "-qm", "runway: review fixes (auto-commit)"], wt)
        after = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
        if fr.failure:
            fix_note = fix_failure_note(fr.failure)
        elif after == before:
            fix_note = "The fix pass made no changes; the findings stand."
        elif (reset_worktree(wt, reset=False) or sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])).returncode == 0:
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
    reset_worktree(wt, reset=False)
    c = sh(cfg["check_cmd"], wt, timeout=cfg["agent_timeout_s"])
    check_out = (c.stdout + c.stderr)[-3000:]
    stat = sh(["git", "diff", "--stat", f"{base}...HEAD"], wt).stdout[-3000:]

    # 3b. The judge: pass/fail from the final state. Reads only; the check result is already in hand.
    sha = sh(["git", "rev-parse", "HEAD"], wt).stdout.strip()
    ttext = "\n\n".join(f"### {t.id} {t.title}\n{t.text[:4000]}" for t in done) or "(none)"
    jr, judge_text = run_agent(cfg, root, hp["review_cmd"], wt,
                               JUDGE_PROMPT.format(integration=integ, base=base, check=cfg["check_cmd"],
                                                   code=c.returncode, tickets=ttext, fix_note=fix_note,
                                                   findings=findings), "finish", "judge", harness=hp)
    valid_reviews = sum(1 for r_ in seat_rows if r_["status"] in ("PASS", "FAIL"))
    verdict = decide_verdict(c.returncode, None if jr.failure else parse_verdict(judge_text), valid_reviews)
    if stop_requested():
        log(root, "finish stopped by pause; the review is not recorded for this head.")
        return False

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
    why_hold = hold_reason(body, tickets)
    hold = bool(why_hold)
    vline = verdict_line(verdict, cfg.get("merge", "off"), hold, sha)
    held = verdict["verdict"] == "pass" and hold and cfg.get("merge", "off") in ("shadow", "on_pass")
    body = vline + "\n\n" + (f"Held for Joe: {why_hold}\n\n" if held else "") + body
    refs = refs_block(done)
    if refs:
        body += f"\n\n## Tickets\n\n{refs}"
    body += (f"\n\n<details><summary>Runway review</summary>\n\n{review_line}\n\n"
             f"Tickets:\n{tlist}\n</details>\n")
    (root / "_pm").mkdir(exist_ok=True)
    (root / "_pm" / "runway-review.md").write_text(
        verdict_report(verdict, vline, hold, sha) + "\n## Findings\n\n" + findings + "\n\n" + fix_note + "\n"
        + (f"\n## Triage\n\n{triage}\n" if triage else ""))
    pr_file = root / "_pm" / "runway-pr.md"
    pr_file.write_text(body)

    where = str(pr_file.relative_to(root))
    if cfg["pr"] == "draft":
        where = open_draft_pr(cfg, root, pr_file, len(done)) or where
    head = sh(["git", "rev-parse", integ], root).stdout.strip()
    new_state = {"head": head, "at": now()}
    fix_msg = None
    if files_tickets:
        new_state, fix_msg = fix_ticket_step(cfg, root, tracker, state, new_state, verdict, done, tickets,
                                             c, check_out, findings, sha)
    state_p.write_text(json.dumps(new_state))
    record(root, {"kind": "finish", "ticket": "finish", "findings": has_findings, "fix": fix_note,
                  "check_exit": c.returncode, "pr": where})
    record(root, {"kind": "verdict", "ticket": "finish", "sha": sha, "verdict": verdict["verdict"],
                  "blocking": verdict["blocking"], "non_blocking": verdict["non_blocking"],
                  "criteria": verdict["criteria"], "hold": hold, "merge": cfg.get("merge", "off"),
                  "seats": seat_rows})
    check_note = "check passes" if c.returncode == 0 else "CHECK FAILS"
    merged = (cfg.get("merge", "off") == "on_pass" and verdict["verdict"] == "pass" and not hold
              and merge_reviewed(cfg, root, sha, where if where.startswith("http") else None))
    if merged:
        notify(cfg, root, f"Merged {len(done)} tickets into {base}")
    elif fix_msg:
        notify(cfg, root, fix_msg)
    else:
        notify(cfg, root, f"Ready for review: {len(done)} tickets on {integ}, {check_note}. {vline}. PR: {where}")
    return True


def merge_reviewed(cfg: dict, root: Path, sha: str, pr_url: str | None) -> bool:
    """Merge the reviewed commit, and only that commit, into the base branch (merge: on_pass, no hold).
    "draft": ready the PR, then `gh pr merge --match-head-commit <sha>`, so a head that moved merges nothing.
    "file": `git merge --no-ff <sha>` in a throwaway worktree on base, then push; a conflict aborts.
    Logs why when it does not merge and leaves the PR for the next finish. Returns True after a merge."""
    base, integ = cfg["base_branch"], cfg["integration_branch"]
    now_head = sh(["git", "rev-parse", integ], root).stdout.strip()
    if now_head != sha:
        log(root, f"merge skipped: {integ} is at {now_head[:12]}, the review was of {sha[:12]}")
        return False
    if cfg["pr"] == "draft":
        if not pr_url:
            log(root, "merge skipped: no draft PR to merge")
            return False
        r = sh(["gh", "pr", "ready", integ], root)
        if r.returncode != 0:
            log(root, f"merge skipped: gh pr ready failed: {r.stderr.strip()[-300:]}")
            return False
        r = sh(["gh", "pr", "merge", integ, "--merge", "--match-head-commit", sha], root)
        if r.returncode != 0:
            log(root, f"merge skipped: gh pr merge refused {sha[:12]}: {r.stderr.strip()[-300:]}")
            return False
    else:
        wt = Path(tempfile.mkdtemp(prefix="runway-merge-"))
        try:
            if sh(["git", "worktree", "add", "-q", "--detach", str(wt), base], root).returncode != 0:
                log(root, f"merge skipped: could not check out {base}")
                return False
            r = sh(["git", "merge", "--no-ff", "-m", f"runway: merge {integ} {sha[:12]}", sha], wt)
            if r.returncode != 0:
                sh(["git", "merge", "--abort"], wt)
                log(root, f"merge skipped: {sha[:12]} conflicts with {base}")
                return False
            r = sh(["git", "push", "-q", "origin", f"HEAD:refs/heads/{base}"], wt)
            if r.returncode != 0:
                log(root, f"merge skipped: push to {base} failed: {r.stderr.strip()[-300:]}")
                return False
        finally:
            sh(["git", "worktree", "remove", "--force", str(wt)], root)
    log(root, f"merge {sha[:12]} into {base}")
    record(root, {"kind": "merge", "ticket": "finish", "sha": sha, "pr": pr_url, "base": base, "mode": cfg["pr"]})
    return True


FIX_TITLE = "Fix review findings on {integ} (round {n})"


def is_fix_ticket(t, cfg: dict) -> bool:
    return t.title.startswith(FIX_TITLE.split(" (round")[0].format(integ=cfg["integration_branch"]))


def ticket_comment(t, body: str) -> None:
    (getattr(t, "comment", None) or t._comment)(body)
    if hasattr(t, "save"):
        t.save()


def fix_ticket_step(cfg, root, tracker, state, new_state, verdict, done, tickets, c, check_out, findings, sha):
    """Round bookkeeping for a failed review under merge shadow/on_pass. Returns (state to write, notify text
    or None). A pass clears the round. A fail files one fix ticket (or comments on the open one for the same
    failure); a fail after the last allowed round parks the open fix ticket instead of filing another."""
    batch = sorted(t.id for t in done if not is_fix_ticket(t, cfg))
    keep = dict(state) if state.get("batch") == batch else {}  # a new non-fix ticket merged: new batch
    rnd = int(keep.get("round", 0))
    if sha != keep.get("sha"):
        rnd += 1
    reviews = list(keep.get("reviews", []))
    out = {**new_state, "batch": batch, "sha": sha, "round": rnd}
    if verdict["verdict"] == "pass":
        return {"head": new_state["head"], "at": new_state["at"], "batch": batch, "sha": sha, "round": 0}, None
    blocking = verdict["blocking"]
    review_text = "\n".join(f"- {b}" for b in blocking) + (f"\n\n{findings}" if findings else "")
    if sha != keep.get("sha"):
        reviews.append(review_text)
    out["reviews"] = reviews
    fix_id = keep.get("fix_ticket")
    sig = hashlib.sha1("\n".join(sorted(b.strip() for b in blocking)).encode()).hexdigest()[:12]
    key = hashlib.sha1(f"{sha}|{cfg['check_cmd']}|{sig}".encode()).hexdigest()[:12]
    open_fix = next((t for t in tickets if fix_id and t.id == fix_id), None)
    if fix_id:
        out["fix_ticket"] = fix_id
    if rnd >= int(cfg.get("review_rounds", 2)):
        if open_fix is None:
            return out, f"Review failed twice, no fix ticket to park ({len(blocking)} blocking)"
        both = "\n\n---\n\n".join(f"Review {i + 1}:\n\n{r}" for i, r in enumerate(reviews))
        open_fix.mark_needs_human("the re-review failed too", both)
        return out, f"Review failed twice, {fix_id} parked for Joe"
    if open_fix is not None and open_fix.status not in DONE and key == keep.get("fix_key"):
        ticket_comment(open_fix, f"Review failed again on `{sha[:8]}` with the same findings.\n\n{review_text}")
        return out, f"Review failed again, fix ticket {fix_id} already open"
    refs = refs_block([t for t in done if not is_fix_ticket(t, cfg)])
    body = "The review of the integration branch failed. Fix these, then Runway reviews the new head.\n\n"
    body += "## Blocking findings\n\n" + "\n".join(f"- {b}" for b in blocking)
    if c.returncode != 0:
        body += f"\n\n## Failing check (`{cfg['check_cmd']}`, exit {c.returncode})\n\n```\n{check_out}\n```"
    if refs:
        body += f"\n\n{refs}"
    try:
        new_id = tracker.create(FIX_TITLE.format(integ=cfg["integration_branch"], n=rnd), body, ["ready-for-agent"])
    except Exception as e:  # a tracker hiccup must not lose the finish
        log(root, f"fix ticket not filed: {e}")
        return out, f"Review failed, could not file a fix ticket ({str(e)[:100]})"
    out.update({"fix_ticket": new_id, "fix_key": key})
    return out, f"Review failed, fix ticket {new_id} filed"


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
    calls = [r for r in recs if r["kind"] in ("prep", "run", "review", "fix", "judge", "pr")]
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


# ---------- discuss: talk a ticket (or the loop) through with Joe ----------

ERROR_KINDS = ("agent-failed", "no-commits", "check-failed", "merge-conflict", "signed-out")


def read_runs(root: Path) -> list:
    try:
        lines = (root / "_pm" / "runway-runs.jsonl").read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def attempt_kind(rec: dict) -> str | None:
    """The kind of a row that did not merge, or None. A row names its kind (the attempt-outcome refactor) or,
    before that lands, it is read from the legacy outcome result and detail, or from a non-zero agent/check exit."""
    if rec.get("outcome") in ERROR_KINDS:
        return rec["outcome"]
    if rec.get("kind") == "run" and rec.get("exit") not in (0, None):
        return "agent-failed"
    if rec.get("kind") == "check" and rec.get("exit") not in (0, None):
        return "check-failed"
    if rec.get("kind") != "outcome" or rec.get("result") in ("done", "stopped"):
        return None
    if rec.get("result") == "signed-out":
        return "signed-out"
    d = rec.get("detail") or ""
    for prefix, kind in (("Agent failed", "agent-failed"), ("The agent ran but", "no-commits"),
                         ("Check failed", "check-failed"), ("Check passed but", "merge-conflict")):
        if d.startswith(prefix):
            return kind
    return None if d.startswith("Agent stopped with a question") else "agent-failed"


def errored_kinds(root: Path) -> dict:
    """Per ticket id, the latest kind of attempt that did not merge, cleared when the ticket merges."""
    out: dict = {}
    for rec in read_runs(root):
        tid = rec.get("ticket")
        if not tid:
            continue
        if rec.get("kind") == "outcome" and rec.get("result") == "done":
            out.pop(tid, None)
        elif (kind := attempt_kind(rec)):
            out[tid] = kind
    return out


def safe_name(ident: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", ident).strip("-") or "ticket"


def tail_lines(path: Path) -> list:
    try:
        return path.read_text().splitlines()
    except OSError:
        return []


def runway_comment(t) -> str | None:
    """Runway's latest comment on the ticket (a decision packet or why it parked), else None."""
    if hasattr(t, "comments"):  # GitHub: trusted comments only, so a stranger's text never lands here
        return t.packet
    found = re.findall(r"^\*\*[^\n]* · runway\*\*\n\n(.*?)(?=^\*\*\d|\Z)", t.text, re.M | re.S)
    return found[-1].strip() if found else None


def exec_claude(root: Path, prompt: str) -> None:
    """Hand Terminal to an interactive claude in the repo root. Always the claude harness. Never returns."""
    os.chdir(root)
    os.execvp("claude", ["claude", prompt])


def launchctl_print(label: str) -> str:
    try:
        r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        return f"(launchctl unavailable: {e})"
    return (r.stdout + r.stderr).strip() or "(no output)"


def ticket_brief(root: Path, loaded: list, t) -> str:
    runs = [r for r in read_runs(root) if r.get("ticket") == t.id]
    out = [f"# Discuss {t.id}: {t.title}", "", f"- URL: {t.url or '(none)'}", f"- Gate: {t.gate}", f"- Status: {t.status}",
           f"- Waiting on: {t.h('Waiting on') or '(nothing)'}", f"- Errored: {errored_kinds(root).get(t.id) or 'no'}",
           "", "## Ticket", "", t.text.strip()]
    packet = t.packet
    if packet:
        out += ["", "## Latest decision packet", "", packet]
    comment = runway_comment(t)
    if comment and comment != packet:
        out += ["", "## Runway's latest comment", "", comment]
    peers = {x.id: x for x in loaded}
    out += ["", "## Blockers", ""]
    for b in t.blocked_by:
        x = peers.get(f"{t.effort}/{b}" if b.isdigit() else b)
        out.append(f"- {x.id if x else b}: {x.status if x else 'unknown'}" + (f" ({x.title})" if x else ""))
    if not t.blocked_by:
        out.append("(none)")
    out += ["", "## Attempts", ""]
    for r in runs:
        if r.get("kind") == "outcome":
            kind = attempt_kind(r) or ("merged" if r.get("result") == "done" else r.get("result"))
            out.append(f"- outcome: {kind}, result {r.get('result')}, after {r.get('attempts')} attempt(s)")
            if r.get("detail"):
                out += ["", "  ```", *("  " + l for l in r["detail"].splitlines()), "  ```", ""]
        elif r.get("kind") == "check":
            out.append(f"- attempt {r.get('attempt')} check: exit {r.get('exit')}" + (" (check-failed)" if r.get("exit") else ""))
        elif r.get("kind") in ("run", "prep", "fix"):
            sid = r.get("session_id")
            path = transcript(sid, r.get("harness") or "claude") if sid else None
            out.append(f"- {r['kind']} attempt {r.get('attempt')} ({r.get('harness') or 'claude'}): exit {r.get('exit')}"
                       + (f", transcript {path}" if path else (", transcript not found" if sid else "")))
    if not runs:
        out.append("(no runs logged for this ticket)")
    mine = [l for l in tail_lines(root / "_pm" / "runway.log") if t.id in l][-40:]
    out += ["", "## Log lines (_pm/runway.log, last 40 that name the ticket)", "", "```", *mine, "```"]
    return "\n".join(out) + "\n"


def write_brief(root: Path, name: str, text: str) -> str:
    d = root / "_pm" / "discuss"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(text)
    return f"_pm/discuss/{name}"


def cmd_discuss(cfg: dict, root: Path, tracker, num: str) -> None:
    loaded = tracker.load()
    t = find(type("Loaded", (), {"load": lambda self: loaded})(), num)
    if t.id not in {x.id for x in group_tickets(loaded)["waiting"]} and t.id not in errored_kinds(root):
        sys.exit(f"{t.id} is not waiting on Joe and has no attempt that failed to merge; nothing to discuss.")
    rel = write_brief(root, safe_name(t.id) + ".md", ticket_brief(root, loaded, t))
    exec_claude(root, f"Read {rel}, the brief for ticket {t.id}, and follow the runway skill's "
                      f"\"Talk a ticket through\" section. Wait for Joe before posting anything.")


def loop_label(root: Path) -> str:
    return "com.joe.runway." + re.sub(r"[^A-Za-z0-9]", "-", root.name)  # as schedule.sh names it


def loop_brief(root: Path) -> str:
    hb = read_heartbeat(root)
    pid = hb.get("pid")
    alive = process_alive(pid)
    label = loop_label(root)
    signin = read_signin(root)
    pz = active_pause(clean=False)
    runs = [json.dumps(r) for r in read_runs(root)[-8:]]
    stale = not alive and hb.get("phase") not in (None, "idle", "stopped", "paused", "waiting")
    return "\n".join([
        "# Discuss the loop", "",
        f"Repo: {root}", f"Job label: {label}", "",
        "## Heartbeat (_pm/runway-state.json)", "",
        "```json", json.dumps(hb, indent=2) if hb else "(no heartbeat file)", "```",
        f"pid {pid}: {'running' if alive else 'not running'}"
        + (" (stale: the loop died mid-phase)" if stale else ""), "",
        f"## launchctl print gui/{os.getuid()}/{label}", "", "```", launchctl_print(label), "```", "",
        "## Pause", "", json.dumps(pz) if pz else "(none)", "",
        "## Last sign-in check (_pm/runway-signin.json)", "", "```json",
        json.dumps(signin, indent=2) if signin else "(none yet)", "```", "",
        "## Last 80 lines of _pm/runway.log", "", "```", *tail_lines(root / "_pm" / "runway.log")[-80:], "```", "",
        "## Last 80 lines of the job's stdout/stderr (_pm/launchd.log)", "", "```",
        *tail_lines(root / "_pm" / "launchd.log")[-80:], "```", "",
        "## Last run rows (_pm/runway-runs.jsonl)", "", "```", *(runs or ["(none)"]), "```", ""])


def cmd_discuss_loop(root: Path) -> None:
    rel = write_brief(root, "loop.md", loop_brief(root))
    exec_claude(root, f"Read {rel}, the brief for the Runway loop in this repo, and follow the runway skill's "
                      f"\"Talk a ticket through\" section, the Loop in error part. Wait for Joe before doing anything.")


# ---------- commands ----------

def park_bad_harness(cfg: dict, root: Path, t) -> bool:
    """Park a ready ticket whose harness override is unknown: log it and hand it to Joe. True if parked."""
    err = harness_error(cfg, t) if t.status == "ready" else None
    if not err:
        return False
    log(root, f"park  {t.id} {err}")
    t.mark_needs_human("fix the harness label", f"Runway parked this ticket: {err}. Fix the harness override, then `runway go`.")
    return True


_DOWN: set[str] = set()  # repos whose last tick ended because the tracker wasn't answering


def tracker_down_path(root: Path) -> Path:
    return root / "_pm" / "runway-tracker.json"


def tracker_is_down(root: Path) -> bool:
    return str(root) in _DOWN


def tracker_waiting(cfg: dict, root: Path, e: transient.TrackerDown) -> None:
    """End the tick cleanly: one log line, heartbeat `waiting` with the reason, one notification until the
    tracker answers again. The ticket and its worktree stay as they are; the next tick tries again."""
    reason = f"tracker not answering: {e}"
    log(root, f"waiting: {reason}")
    beat(root, "waiting", reason=reason)
    _DOWN.add(str(root))
    p = tracker_down_path(root)
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"since": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                                     "call": e.what}) + "\n")
        except OSError:
            pass
        notify(cfg, root, f"Runway: tracker is not answering ({e.what})")


def tracker_answered(root: Path) -> None:
    tracker_down_path(root).unlink(missing_ok=True)


def read_heartbeat(root: Path) -> dict:
    try:
        data = json.loads((root / "_pm" / "runway-state.json").read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def process_alive(pid) -> bool:
    """A live Runway process by this pid: not this process, and not an unrelated one that reused the pid."""
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except OSError:
        return False
    try:
        cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return True  # can't look: assume it is Runway rather than release a ticket it holds
    return "runway" in cmd.lower()


def agent_registered_alive(pid) -> bool:
    """Is pid a registered agent still running (same start time as when it registered)?"""
    try:
        lines = (agents_dir() / str(int(pid))).read_text().splitlines()
        actual = process_started(int(pid))
    except (OSError, ValueError, TypeError):
        return False
    return actual is not None and (len(lines) < 2 or not lines[1] or lines[1] == actual)


def release_orphans(root: Path, tickets: list, beat_before: dict) -> bool:
    """A ticket claimed by this Mac that no live Runway process holds is a crash's leftover: back to ready,
    with a comment, so it runs again. beat_before: the heartbeat as the previous process left it."""
    me = machine_name()
    alive = process_alive(beat_before.get("pid"))
    agent = beat_before.get("agent_pid")
    if not alive and agent and agent_registered_alive(agent):
        return False  # the loop died but its agent is still working: leave the claim and the worktree alone
    released = False
    for t in tickets:
        if t.status != "claimed" or t.claimed_by != me:
            continue
        if alive and beat_before.get("ticket") == t.id:
            continue  # a live process is running it
        t.mark_ready("Released: recovered after a crash. This Mac had claimed it but no Runway process was "
                     "still running it, so it goes back in the queue and runs again.")
        log(root, f"recovered {t.id}: claimed by this Mac, no live Runway process holds it")
        released = True
    return released


def tick(cfg: dict, root: Path, tracker) -> bool:
    """One pass. Returns True if it did anything. A tracker that won't answer ends the pass, not the process."""
    _DOWN.discard(str(root))
    try:
        return _tick(cfg, root, tracker)
    except transient.TrackerDown as e:
        tracker_waiting(cfg, root, e)
        return False


def _tick(cfg: dict, root: Path, tracker) -> bool:
    did = False
    if paused_now(root) or machine_waiting(root):
        return False
    before = read_heartbeat(root)  # the last process's, before this tick's first beat overwrites it
    beat(root, "sync", tick_started=dt.datetime.now().astimezone().isoformat(timespec="seconds"))
    tracker.sync()
    tickets = tracker.load()
    tracker_answered(root)
    if release_orphans(root, tickets, before):
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

    errored = errored_kinds(root)

    def entry(t) -> dict:
        waiting = t.status == "needs-human"
        return {"id": t.id, "title": t.title, "url": t.url or None, "status": t.status, "gate": t.gate,
                "blocked_by": [full_id(t, b) for b in t.blocked_by],
                "waiting_on": (t.h("Waiting on") or None) if waiting else None,
                "packet": t.packet if waiting else None, "harness": resolve_harness(cfg, t)["name"], "claimed_by": t.claimed_by,
                "errored": errored.get(t.id)}

    return {"version": 1, "repo": str(root), "tracker": cfg.get("tracker", "markdown"),
            "machine": machine_name(), "paused": active_pause(clean=False),
            "signin": read_signin(root),
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "groups": {k: [t.id for t in ts] for k, ts in groups.items()},
            "tickets": [entry(t) for t in loaded if t.id in grouped]}


def find(tracker, num: str):
    key = num.zfill(2) if num.isdigit() else num
    hits = [t for t in tracker.load() if t.num in (key, "#" + num) or t.id == key or t.id.endswith("/" + key)]
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
    sub.add_parser("setup", help="Linear or GitHub: check the sign-in and project/repo, and create Runway's labels")
    sub.add_parser("finish", help="review the integration branch, fix once, check, and write the PR body now")
    ds = sub.add_parser("discuss", help="open a claude session to talk a waiting or errored ticket (or --loop) through")
    ds.add_argument("ticket", nargs="?")
    ds.add_argument("--loop", action="store_true", help="the loop itself (stale heartbeat, failed tick, sign-in), not a ticket")
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
    if a.cmd == "discuss":
        if a.loop == bool(a.ticket):
            sys.exit("Give a ticket to discuss, or --loop for the loop itself (not both).")
        if a.loop:
            cmd_discuss_loop(root)
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
            sys.exit("setup is only needed for the linear and github trackers.")
        tracker.setup()
    elif a.cmd == "retro":
        cmd_retro(root, a.last)
    elif a.cmd == "discuss":
        cmd_discuss(cfg, root, tracker, a.ticket)
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
                        if tracker_is_down(root):
                            return  # tracker not answering: heartbeat stays `waiting`, no finish step, exit 0
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
        except transient.TrackerDown as e:  # finish or the status print lost the tracker
            tracker_waiting(cfg, root, e)
            return
        if not tracker_is_down(root):
            beat(root, "idle")
    elif a.cmd in ("go", "no"):
        cmd_answer(root, tracker, a.ticket, a.cmd == "go", a.note)


if __name__ == "__main__":
    try:
        main()
    except transient.TrackerDown as e:  # status, setup, go, no: say so in a line instead of a traceback
        sys.exit(f"Tracker not answering: {e}")
