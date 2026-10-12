"""The queue plan: what happens to each ticket next, decided in one place.

Pure: no git, tracker, clock or I/O. `plan(tickets, machine, finish_mode, harness_cfg)` reads only the ticket
interface (id, effort, num, gate, status, claimed_by, blocked_by, harness) and returns a QueuePlan. Pause, quiet
hours, sign-ins and orphan release stay outside it. See docs/specs/queue-plan.md.

`harness_cfg` is the runway config dict: the plan reads its `harness` default, its `harnesses` profiles and the
top-level commands the profiles overlay.

Precedence for one ticket, first match wins:
  1. ready with an unknown harness label               -> park   (any gate, any owner, Runway's or not)
  2. terminal, waiting or claimed status               -> done / waiting / running_here / running_elsewhere /
                                                          claimed_unknown_owner
  3. human gate, ready (lookahead, ignores claim stamps) -> prep, or blocked behind another decision
  4. auto/approved gate, ready: owner, then blockers   -> running_elsewhere / blocked / run (first) / queued
A status outside those leaves the ticket out of the steps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DONE = {"resolved", "done", "closed"}
RUNNABLE_GATES = ("auto", "approved")
RUNWAY_GATES = RUNNABLE_GATES + ("human",)

STEPS = ("run", "queued", "prep", "park", "waiting", "running_here", "running_elsewhere",
         "claimed_unknown_owner", "blocked", "done")


@dataclass
class Step:
    ticket: object
    kind: str
    reason: str

    @property
    def id(self) -> str:
        return self.ticket.id


@dataclass
class Finish:
    """The tracker half of finish's gate. verdict: finish, wait or off. `finish --force` skips it."""
    verdict: str
    reason: str


@dataclass
class QueuePlan:
    steps: list = field(default_factory=list)       # one Step per Runway ticket, in tracker order
    run_now: object = None                          # the first runnable ticket (a candidate, not a promise)
    prep: list = field(default_factory=list)        # gated tickets the tick should prep this pass
    park: list = field(default_factory=list)        # Steps: ready tickets with an unknown harness label
    harnesses_needed: list = field(default_factory=list)  # harness names of the run, queued and prep tickets
    finish: Finish = None
    idle_reason: str | None = None                  # why nothing can run, when run_now is None


# ---------- harness rules ----------

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


# ---------- blocker rules ----------

def _index(tickets: list) -> dict:
    """Every loaded ticket (Runway's or not, stubs included), keyed by (effort, num)."""
    return {(x.effort, x.num): x for x in tickets}


def _open_blockers(t, peers: dict) -> list:
    """The blockers still open. A blocker that isn't loaded counts as done."""
    found = (peers.get((t.effort, b)) for b in t.blocked_by)
    return [p for p in found if p is not None and p.status not in DONE]


def unblocked(t, tickets: list) -> bool:
    return not _open_blockers(t, _index(tickets))


def _auto_finishable(t, peers: dict, seen: frozenset) -> bool:
    """True if every open blocker is auto work the loop can finish on its own (a cycle never is)."""
    for p in _open_blockers(t, peers):
        if p.id in seen or p.gate not in RUNNABLE_GATES or p.status == "needs-human":
            return False
        if not _auto_finishable(p, peers, seen | {p.id}):
            return False
    return True


def will_unblock_without_joe(t, tickets: list, seen=None) -> bool:
    return _auto_finishable(t, _index(tickets), frozenset(seen or ()) | {t.id})


def _joe_waits(cfg: dict, t) -> bool:
    return t.status == "needs-human" or t.gate == "human" or bool(harness_error(cfg, t) and t.status == "ready")


def _roots(t, peers: dict) -> list:
    """The open tickets at the end of t's blocker chain (open, with no open blockers of their own).
    Empty when the chain never ends: a cycle."""
    roots, seen, stack = [], {t.id}, [t]
    while stack:
        cur = stack.pop()
        ahead = _open_blockers(cur, peers)
        if not ahead and cur is not t:
            roots.append(cur)
        for p in reversed(ahead):
            if p.id not in seen:
                seen.add(p.id)
                stack.append(p)
    return sorted(roots, key=lambda r: [x.id for x in peers.values()].index(r.id))


# ---------- the plan ----------

def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def finish_verdict(tickets: list, finish_mode: str) -> Finish:
    """Off wins, an empty queue counts as all done, and an unknown mode behaves like idle."""
    mine = [t for t in tickets if t.gate in RUNWAY_GATES]
    if finish_mode == "off":
        return Finish("off", "finish is off")
    if any(t.status == "claimed" for t in mine):
        return Finish("wait", "a ticket is claimed")
    open_ = [t for t in mine if t.status not in DONE]
    if finish_mode == "all_done" and open_:
        return Finish("wait", f"{len(open_)} open under all_done")
    return Finish("finish", "all done" if not open_ else "idle")


def plan(tickets: list, machine: str, finish_mode: str, harness_cfg: dict) -> QueuePlan:
    cfg = harness_cfg
    peers = _index(tickets)
    out = QueuePlan(finish=finish_verdict(tickets, finish_mode))
    needed: list = []

    def add(t, kind: str, reason: str) -> Step:
        s = Step(t, kind, reason)
        if t.gate in RUNWAY_GATES:
            out.steps.append(s)
        return s

    def need(t) -> None:
        name = resolve_harness(cfg, t)["name"]
        if name not in needed:
            needed.append(name)

    def blocked_reason(t) -> str:
        names = ", ".join(p.id for p in _open_blockers(t, peers))
        roots = _roots(t, peers)
        if not roots:
            return f"blocked by {names}, in a blocker cycle"
        return f"blocked by {names}" + (", waiting on you" if any(_joe_waits(cfg, r) for r in roots) else "")

    for t in tickets:
        err = harness_error(cfg, t) if t.status == "ready" else None
        if err:
            out.park.append(add(t, "park", err))
            continue
        if t.gate not in RUNWAY_GATES:
            continue
        if t.status in DONE:
            add(t, "done", "done")
        elif t.status == "needs-human":
            add(t, "waiting", "waiting on you")
        elif t.status == "claimed":
            if not t.claimed_by:
                add(t, "claimed_unknown_owner", "claimed, but the claim has no machine stamp")
            elif t.claimed_by == machine:
                add(t, "running_here", "running on this Mac")
            else:
                add(t, "running_elsewhere", f"running on {t.claimed_by}")
        elif t.status != "ready":
            continue
        elif t.gate == "human":
            if _auto_finishable(t, peers, frozenset({t.id})):
                out.prep.append(t)
                need(t)
                add(t, "prep", "decision to prepare for you")
            else:
                add(t, "blocked", blocked_reason(t))
        elif t.claimed_by and t.claimed_by != machine:
            add(t, "running_elsewhere", f"claimed by {t.claimed_by}")
        elif _open_blockers(t, peers):
            add(t, "blocked", blocked_reason(t))
        elif out.run_now is None:
            out.run_now = t
            need(t)
            add(t, "run", "next to run")
        else:
            need(t)
            add(t, "queued", f"ready, behind {out.run_now.id}")

    out.harnesses_needed = needed
    if out.run_now is None:
        out.idle_reason = _idle_reason(cfg, out, peers)
    return out


def _idle_reason(cfg: dict, p: QueuePlan, peers: dict) -> str:
    """One line on why nothing can run, counting what is stuck behind what."""
    behind: dict = {}
    cycle = 0
    for s in p.steps:
        if s.kind != "blocked":
            continue
        roots = _roots(s.ticket, peers)
        cycle += not roots
        for r in roots:
            behind.setdefault(r.id, [r, 0])[1] += 1
    parts = []
    for r, n in behind.values():
        verb = "waits" if n == 1 else "wait"
        parts.append(f"{_plural(n, 'ticket', 'tickets')} {verb} on {r.id}" + (" (waiting on you)" if _joe_waits(cfg, r) else ""))
    if cycle:
        parts.append(f"{_plural(cycle, 'ticket is', 'tickets are')} stuck in a blocker cycle")
    if p.park:
        parts.append(f"{_plural(len(p.park), 'ticket is', 'tickets are')} parked on a bad harness label")
    if p.prep:
        parts.append(f"{_plural(len(p.prep), 'ticket needs', 'tickets need')} prep first")
    if not parts:
        waiting = sum(s.kind == "waiting" for s in p.steps)
        running = sum(s.kind in ("running_here", "running_elsewhere", "claimed_unknown_owner") for s in p.steps)
        if waiting:
            parts.append(f"{_plural(waiting, 'ticket waits', 'tickets wait')} on you")
        if running:
            parts.append(f"{running} running")
    return "nothing can run: " + ("; ".join(parts) or "no ticket is ready")
