"""The ticket protocol: the rules every tracker adapter shares, written once.

An adapter (GitHub, Linear, or the in-memory one the tests use) supplies facts and writes. This module turns
them into the ticket interface the engine uses: gate, status, is_spec, harness, claimed_by, packet, text,
the park / approve / decline / release / packet wording, and sync's go and drop rules.

Facts (an adapter ticket sets these in `__init__` by calling `Ticket.__init__`, and defines the three
properties):
  id, num, title, url, body, labels, comments (as dicts: body, createdAt, trusted, who, assoc)
  closed        the issue is done or cancelled (resolved)
  held          the tracker says someone holds it (an assignee, a started state)
  has_children  it has sub-issues or child issues (a spec)
  blocked_by    ids of the tickets that gate it

Writes (each an adapter method; the protocol decides which, in what order, with what words):
  _post(full)                  post a comment; `full` is already marked
  _claim()                     take the ticket (assign, or move to the started state)
  _close(reason, full)         resolve it: reason is "completed" or "not planned"; `full` is the comment to
                               close with, or None when the protocol posts it afterwards
  _release(add, remove)        give the ticket back (unassign, or move to unstarted) and change labels
  _relabel(add, remove)        change labels only

Trackers differ only in wording (`Rules`) and in write order; the trust, go and park rules are the same for both.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

MARK = "🛫 runway"  # every comment Runway writes starts with this, so Joe's are told apart
ANSWER_RE = re.compile(r"(go|drop)\b", re.I)
GO_RE = re.compile(r"go\b[\s:,.-]*", re.I)


@dataclass(frozen=True)
class Rules:
    name: str                   # "GitHub": the word in ticket text, the sync note and the log lines
    children: str               # what a spec's children are called: "sub-issues", "child issues"
    where: str                  # how sync says where Joe answered: "on GitHub", "in Linear"
    trust_label: str            # who counts as trusted, for the one-line note and the log
    close_with_comment: bool    # write order: close and comment in one write, else close then comment


GITHUB = Rules(name="GitHub", children="sub-issues", where="on GitHub",
               trust_label="owner, member or collaborator", close_with_comment=True)
LINEAR = Rules(name="Linear", children="child issues", where="in Linear",
               trust_label="the workspace's members", close_with_comment=False)


# How long a Mac has to finish a claim (the stamp, then the assignment or state change) before a later stamp
# means it never did. Two live Macs stamp seconds apart; a dead one's stamp is older than this by the next tick.
CLAIM_LEASE = dt.timedelta(minutes=5)


def _when(stamp: str) -> dt.datetime:
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def marked(body: str) -> str:
    return f"{MARK} · {body.strip()}"


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].rstrip("-")


class Ticket:
    rules: Rules
    effort: str

    def __init__(self, tracker, *, id: str, num: str, title: str, url: str, body: str, labels,
                 comments: list[dict], slug_head: str):
        self.tr = tracker
        self.id, self.num = id, num
        self.title = title
        self.url = url or ""
        self.body = body or ""
        self.ref = url or id
        self.slug = f"{slug_head}-{slugify(title)}"
        self.labels = labels
        every = sorted(comments, key=lambda c: c["createdAt"])
        self.comments = [c for c in every if c["trusted"]]
        self.untrusted = len(every) - len(self.comments)
        self.strangers = [c for c in every if not c["trusted"]]

    # -- read side --

    @property
    def text(self) -> str:
        out = [f"# {self.title}", "", f"{self.rules.name}: {self.ref}", "", self.body.strip()]
        if self.comments or self.untrusted:
            out += ["", "## Comments"]
        for cm in self.comments:
            who = "runway" if cm["body"].startswith(MARK) else "Joe"
            out += ["", f"**{cm['createdAt'][:16]} · {who}**", "", cm["body"].strip()]
        if self.untrusted:
            out += ["", f"_{self.untrusted} comment(s) from other authors left out (not {self.rules.trust_label})._"]
        return "\n".join(out) + "\n"

    @property
    def packet(self) -> str | None:
        """Runway's latest comment (the decision packet, or why it parked), without the marker."""
        mine = [cm["body"] for cm in self.comments if cm["body"].startswith(MARK)]
        return mine[-1][len(MARK):].lstrip(" ·\n").strip() if mine else None

    @property
    def status(self) -> str:
        if self.closed:
            return "resolved"
        if self.tr.c["needs_human_label"] in self.labels:
            return "needs-human"
        if self.held:
            return "claimed"
        return "ready"

    @property
    def is_spec(self) -> bool:
        """A spec is labelled `spec` or has children. Runway never runs one."""
        return self.tr.c["spec_label"] in self.labels or self.has_children

    @property
    def gate(self) -> str:
        c = self.tr.c
        if self.is_spec:
            return "none"
        if c["human_label"] in self.labels:
            return "approved" if c["approve_label"] in self.labels else "human"
        if c["agent_label"] in self.labels:
            return "auto"
        return "none"

    @property
    def harness(self) -> str | None:
        """Per-ticket harness override from a `harness:<name>` label, or None."""
        for name in self.labels:
            if name.lower().startswith("harness:"):
                return name.split(":", 1)[1].strip().lower() or None
        return None

    @property
    def claimed_by(self) -> str | None:
        """The machine that holds the current claim cycle, else None. First stamp wins, so two Macs that both
        stamped agree on the owner whichever order they read back in. A stamp is abandoned when a later stamp
        lands more than CLAIM_LEASE after it: a Mac only stamps a ticket it saw ready, so the earlier claim never
        completed (its Mac died between the stamp and the claim), and the later stamp takes over."""
        if self.status != "claimed":
            return None  # parked, paused or retried: the old stamp no longer holds the ticket
        stamps = []
        for cm in reversed(self.comments):
            if not cm["body"].startswith(MARK):
                continue  # Joe's comments don't end a cycle
            m = re.search(r"Claimed-by: (.+?)(?: · |$)", cm["body"], re.M)
            if not m:
                break  # a park, release or note: earlier claims belong to an earlier cycle
            stamps.append((m.group(1).strip(), _when(cm["createdAt"])))
        owner = None
        for who, at in reversed(stamps):
            if owner is None or at - owner[1] > CLAIM_LEASE:
                owner = (who, at)
        return owner[0] if owner else None

    def h(self, key: str, default: str = "") -> str:
        if key == "Waiting on" and self.status == "needs-human":
            return "Joe (see the latest runway comment)"
        return default

    def joe_replies(self) -> list[str]:
        """Trusted comments since Runway last wrote, oldest first."""
        out = []
        for cm in self.comments:
            if cm["body"].startswith(MARK):
                out = []
            else:
                out.append(cm["body"].strip())
        return out

    def stranger_calls(self) -> list[dict]:
        """Untrusted comments since Runway last wrote that try to say go or drop."""
        mark = max((cm["createdAt"] for cm in self.comments if cm["body"].startswith(MARK)), default="")
        return [c for c in self.strangers if c["createdAt"] > mark and ANSWER_RE.match(c["body"].strip())]

    # -- write side --

    def _comment(self, body: str) -> None:
        self._post(marked(body))

    def mark_claimed(self, branch: str, machine: str) -> None:
        # Stamp first: a failure between the two writes then leaves the ticket ready (retried next tick), never
        # claimed with no owner on it.
        self._comment(f"Claimed-by: {machine} · Started on `{branch}`.")
        self._claim()

    def _finish(self, reason: str, body: str) -> None:
        full = marked(body)
        if self.rules.close_with_comment:
            self._close(reason, full)
        else:
            self._close(reason, None)
            self._post(full)

    def mark_resolved(self, note: str) -> None:
        self._finish("completed", note)

    def mark_needs_human(self, why: str, detail: str) -> None:
        c = self.tr.c
        label, approve = c["needs_human_label"], c["approve_label"]
        gated = self.gate == "approved"
        # An approval is spent by the run it let through: dropping `go` here keeps sync from re-approving every tick.
        self._release(add=[label], remove=[approve])
        if gated:
            retry = f"Comment `go` (or re-add the `{approve}` label) to retry."
        else:
            retry = f"Remove `{label}` or comment `go` to retry."
        self._comment(f"Parked: {why}. {retry}\n\n{detail}")

    def mark_ready(self, note: str) -> None:
        self._release()
        self._comment(note)

    def post_packet(self, packet: str) -> None:
        a = self.tr.c["approve_label"]
        self._comment(
            f"**Decision packet**\n\n_Reply with a comment starting `go` (add any choice or note after it) "
            f"or add the `{a}` label to approve. Comment `drop` to cancel it._\n\n{packet}")
        self._relabel(add=[self.tr.c["needs_human_label"]])

    def approve(self, note: str) -> None:
        c = self.tr.c
        add = [c["approve_label"]] if self.gate == "human" else []
        self._relabel(add=add, remove=[c["needs_human_label"]])
        self._comment(f"Approved. {note}".strip())

    def decline(self, note: str) -> None:
        if note.lower().startswith("drop"):
            self._finish("not planned", f"Dropped. {note}")
        else:
            self._comment(f"Joe said no: {note}")


class Tracker:
    """The tracker-wide rules: the spec-skip log line, the once-only log, and sync. `rules`, `root`, `c` and
    `load()` come from the adapter."""
    rules: Rules

    def _log_once(self, line: str) -> None:
        p = self.root / "_pm" / "runway.log"
        if p.exists() and line in p.read_text():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}  {line}\n")
        print(line)

    def create(self, title: str, body: str, labels: list[str]) -> str:
        """Open a new ticket and return its ref. The body starts with the 🛫 marker so a later read never takes
        it for Joe's. The adapter's `_create(title, full, labels)` does the write."""
        return self._create(title, marked(body), labels)

    def _log_spec_skips(self, tickets) -> None:
        for t in tickets:
            if self.c["spec_label"] in t.labels and t.status != "resolved":
                self._log_once(f"skip  {t.id} is labelled {self.c['spec_label']}: a spec, never run "
                               f"(its {self.rules.children} are the tickets)")

    def sync(self) -> None:
        """Turn Joe's answers in the tracker into ticket state before the tick decides anything."""
        r = self.rules
        for t in self.load():
            if t.status != "needs-human":
                continue
            for c in t.stranger_calls():
                self._log_once(f"sync  {t.id} ignored '{c['body'].strip().split()[0]}' from {c['who']} "
                               f"({c['assoc']}) at {c['createdAt']}: not {r.trust_label}")
            replies = t.joe_replies()
            last = replies[-1] if replies else ""
            said_go = bool(GO_RE.match(last))
            if t.gate == "approved" or said_go:
                t.approve(GO_RE.sub("", last, count=1) if said_go else "")
                print(f"sync  {t.id} approved {r.where}")
            elif re.match(r"drop\b", last, re.I):
                t.decline(f"drop (from {r.name})")
                print(f"sync  {t.id} dropped {r.where}")
