"""Linear adapter for Runway.

Runway's queue is the issues in one Linear team (optionally one project) that carry
Matt Pocock's triage labels, which /to-tickets already applies:

  ready-for-agent   AFK work. Runway runs it.                      (Gate: auto)
  ready-for-human   Needs Joe. Runway preps a packet first.         (Gate: human)
  go                Joe's approval on a ready-for-human ticket.     (Gate: approved)
  needs-human       Parked: waiting on Joe. Runway never picks it.  (Status: needs-human)
  spec              A spec (what /to-spec publishes). Never run, even with a Runway label.

An issue with child issues is a spec too, label or not: its children are the tickets. A spec has gate
`none`, so Runway never runs it, but it still gates a ticket that names it as a blocker. The first time a
labelled spec is skipped, one line goes to `_pm/runway.log`.

Anything else in the project (wayfinder decision tickets, Joe's own issues) is ignored,
except as a blocker. Status comes from the workflow state: completed or canceled is done,
started is claimed, anything else is ready (duplicate counts as done). Blocking uses Linear's native "blocks"
relation, which is what /to-tickets and /wayfinder create.

Joe answers in Linear, from any device, and the next tick picks it up:
  - add the `go` label, or comment "go <any note>"  -> approved; the note reaches the agent
  - comment "drop"                                 -> moved to Canceled
  - remove `needs-human` from a failed run          -> retried on the next tick

API key: LINEAR_API_KEY, or the macOS keychain item `runway-linear`
(security add-generic-password -s runway-linear -a "$USER" -w).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transient  # noqa: E402

API_URL = "https://api.linear.app/graphql"
MARK = "🛫 runway"  # every comment Runway writes starts with this, so Joe's are told apart
DEFAULTS = {
    "team": "",
    "project": "",
    "agent_label": "ready-for-agent",
    "human_label": "ready-for-human",
    "approve_label": "go",
    "needs_human_label": "needs-human",
    "spec_label": "spec",
    "claimed_state": "In Progress",
    "done_state": "Done",
    "api_key_env": "LINEAR_API_KEY",
    "keychain_service": "runway-linear",
    "api_url": API_URL,
}

ISSUE_FIELDS = """
  id identifier number title description url
  state { id name type }
  labels(first: 20) { nodes { id name } }
  children(first: 1) { nodes { id } }
  comments(first: 25) { nodes { body createdAt } }
  inverseRelations(first: 10) { nodes { type issue { identifier number title state { type } } } }
"""

Q_ISSUES = """query($filter: IssueFilter, $after: String) {
  issues(filter: $filter, first: 50, after: $after) {
    nodes { %s }
    pageInfo { hasNextPage endCursor }
  }
}""" % ISSUE_FIELDS

Q_ISSUE = """query($id: String!) { issue(id: $id) { %s } }""" % ISSUE_FIELDS

Q_COMMENTS = """query($id: String!) { issue(id: $id) { comments(last: 25) { nodes { body createdAt } } } }"""

Q_TEAM ="""query($key: String!) {
  teams(first: 1, filter: { key: { eq: $key } }) {
    nodes {
      id key name
      states(first: 50) { nodes { id name type position } }
      labels(first: 100) { nodes { id name } }
    }
  }
  issueLabels(filter: { team: { null: true } }, first: 100) { nodes { id name } }
}"""

Q_PROJECTS = """query($name: String!) { projects(filter: { name: { eq: $name } }) { nodes { id name } } }"""

M_UPDATE = """mutation($id: String!, $input: IssueUpdateInput!) { issueUpdate(id: $id, input: $input) { success } }"""
M_COMMENT = """mutation($input: CommentCreateInput!) { commentCreate(input: $input) { success } }"""
M_LABEL = """mutation($input: IssueLabelCreateInput!) { issueLabelCreate(input: $input) { success issueLabel { id name } } }"""


def api_key(cfg: dict) -> str:
    key = os.environ.get(cfg["api_key_env"], "").strip()
    if not key and sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", cfg["keychain_service"], "-w"],
                           capture_output=True, text=True)
        key = r.stdout.strip()
    if not key:
        sys.exit(f"No Linear API key. Set {cfg['api_key_env']} or add the keychain item "
                 f"'{cfg['keychain_service']}' (see linear_tracker.py).")
    return key


class Linear:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.key = api_key(cfg)

    def gql(self, query: str, variables: dict | None = None, landed=None) -> dict:
        """One API call. A timeout, connection reset or 5xx is retried (transient.py), then raises
        TrackerDown. landed: for a write that isn't safe to repeat, a check that it is already there."""
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        req = urllib.request.Request(self.cfg["api_url"], data=body, method="POST", headers={
            "Content-Type": "application/json", "Authorization": self.key})

        def once() -> dict:
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if transient.is_transient(e):
                    raise
                raise RuntimeError(f"Linear API {e.code}: {e.read().decode()[:500]}") from None

        m = re.search(r"\{\s*(\w+)", query)
        out = transient.retry(once, f"Linear {m.group(1) if m else 'API call'}", landed)
        if out is None:  # a write that landed while its reply was lost
            return {}
        if out.get("errors"):
            raise RuntimeError(f"Linear API error: {out['errors']}")
        return out["data"]


class LinearTicket:
    def __init__(self, node: dict, tracker: "LinearTracker"):
        self.node = node
        self.tr = tracker
        self.num = node["identifier"]
        self.effort = "linear"
        self.id = node["identifier"]
        self.ref = node.get("url") or node["identifier"]
        slug = re.sub(r"[^a-z0-9]+", "-", node["title"].lower()).strip("-")[:40].rstrip("-")
        self.slug = f"{node['identifier'].lower()}-{slug}"
        self.labels = {l["name"]: l["id"] for l in node["labels"]["nodes"]}
        self.comments = sorted(node["comments"]["nodes"], key=lambda c: c["createdAt"])

    # -- read side --

    @property
    def title(self) -> str:
        return self.node["title"]

    @property
    def text(self) -> str:
        out = [f"# {self.title}", "", f"Linear: {self.ref}", "", (self.node.get("description") or "").strip()]
        if self.comments:
            out += ["", "## Comments"]
            for cm in self.comments:
                who = "runway" if cm["body"].startswith(MARK) else "Joe"
                out += ["", f"**{cm['createdAt'][:16]} · {who}**", "", cm["body"].strip()]
        return "\n".join(out) + "\n"

    @property
    def url(self) -> str:
        return self.node.get("url") or ""

    @property
    def packet(self) -> str | None:
        """Runway's latest comment (the decision packet, or why it parked), without the marker."""
        mine = [cm["body"] for cm in self.comments if cm["body"].startswith(MARK)]
        return mine[-1][len(MARK):].lstrip(" ·\n").strip() if mine else None

    @property
    def status(self) -> str:
        c = self.tr.c
        st = self.node["state"]["type"]
        if st in ("completed", "canceled", "duplicate"):
            return "resolved"
        if c["needs_human_label"] in self.labels:
            return "needs-human"
        if st == "started":
            return "claimed"
        return "ready"

    @property
    def is_spec(self) -> bool:
        """A spec is labelled `spec` or has child issues. Runway never runs one."""
        return self.tr.c["spec_label"] in self.labels or bool((self.node.get("children") or {}).get("nodes"))

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
    def blocked_by(self) -> list[str]:
        return [r["issue"]["identifier"] for r in self.node["inverseRelations"]["nodes"] if r["type"] == "blocks"]

    @property
    def claimed_by(self) -> str | None:
        """The machine named in the first claim comment of the current claim cycle, else None. First stamp wins, so
        two Macs that both stamped agree on the owner whichever order they read back in."""
        if self.status != "claimed":
            return None  # parked, paused or retried: the old stamp no longer holds the ticket
        owner = None
        for cm in reversed(self.comments):
            if not cm["body"].startswith(MARK):
                continue  # Joe's comments don't end a cycle
            m = re.search(r"Claimed-by: (.+?)(?: · |$)", cm["body"], re.M)
            if not m:
                break  # a park, release or note: earlier claims belong to an earlier cycle
            owner = m.group(1).strip()
        return owner

    def h(self, key: str, default: str = "") -> str:
        if key == "Waiting on" and self.status == "needs-human":
            return "Joe (see the latest runway comment)"
        return default

    def joe_replies(self) -> list[str]:
        """Joe's comments since Runway last wrote, oldest first."""
        out = []
        for cm in self.comments:
            if cm["body"].startswith(MARK):
                out = []
            else:
                out.append(cm["body"].strip())
        return out

    # -- write side --

    def _update(self, **inp) -> None:
        self.tr.api.gql(M_UPDATE, {"id": self.node["id"], "input": inp})

    def _comment(self, body: str) -> None:
        full = f"{MARK} · {body.strip()}"
        since = transient.since_mark()

        def landed() -> bool:  # a comment that timed out may already be there: look before posting again
            d = self.tr.api.gql(Q_COMMENTS, {"id": self.node["id"]})["issue"]["comments"]["nodes"]
            return transient.posted_since(d, full, since)
        self.tr.api.gql(M_COMMENT, {"input": {"issueId": self.node["id"], "body": full}}, landed=landed)

    def _labels(self, add=(), remove=()) -> None:
        add_ids = [self.tr.label_id(n) for n in add if n not in self.labels]
        rm_ids = [self.labels[n] for n in remove if n in self.labels]
        if add_ids or rm_ids:
            self._update(addedLabelIds=add_ids, removedLabelIds=rm_ids)

    def post_packet(self, packet: str) -> None:
        a = self.tr.c["approve_label"]
        self._comment(
            f"**Decision packet**\n\n_Reply with a comment starting `go` (add any choice or note after it) "
            f"or add the `{a}` label to approve. Comment `drop` to cancel it._\n\n{packet}")
        self._labels(add=[self.tr.c["needs_human_label"]])

    def mark_claimed(self, branch: str, machine: str) -> None:
        # Stamp first: a failure between the two writes then leaves the ticket ready (retried next tick), never
        # claimed with no owner on it.
        self._comment(f"Claimed-by: {machine} · Started on `{branch}`.")
        self._update(stateId=self.tr.state_id(self.tr.c["claimed_state"]))

    def mark_resolved(self, note: str) -> None:
        self._update(stateId=self.tr.state_id(self.tr.c["done_state"]))
        self._comment(note)

    def mark_needs_human(self, why: str, detail: str) -> None:
        # Back to an unstarted state, so clearing the label makes it ready again.
        self._update(stateId=self.tr.state_id(None, "unstarted"))
        # An approval is spent by the run it let through: dropping `go` here keeps sync from re-approving every tick.
        c = self.tr.c
        gated = self.gate == "approved"
        self._labels(add=[c["needs_human_label"]], remove=[c["approve_label"]])
        retry = (f"Comment `go` (or re-add the `{c['approve_label']}` label) to retry." if gated
                 else f"Remove `{c['needs_human_label']}` or comment `go` to retry.")
        self._comment(f"Parked: {why}. {retry}\n\n{detail}")

    def mark_ready(self, note: str) -> None:
        self._update(stateId=self.tr.state_id(None, "unstarted"))
        self._comment(note)

    def approve(self, note: str) -> None:
        add = [self.tr.c["approve_label"]] if self.gate == "human" else []
        self._labels(add=add, remove=[self.tr.c["needs_human_label"]])
        self._comment(f"Approved. {note}".strip())

    def decline(self, note: str) -> None:
        if note.lower().startswith("drop"):
            self._update(stateId=self.tr.state_id(None, "canceled"))
            self._comment(f"Dropped. {note}".strip())
        else:
            self._comment(f"Joe said no: {note}")


class LinearTracker:
    def __init__(self, root: Path, cfg: dict):
        self.root = root
        self.c = dict(DEFAULTS, **cfg.get("linear", {}))
        if not self.c["team"]:
            sys.exit('runway.json needs "linear": {"team": "<team key>"} (and usually "project").')
        self.api = Linear(self.c)
        self._team = None

    # -- team metadata (cached per run) --

    @property
    def team(self) -> dict:
        if self._team is None:
            d = self.api.gql(Q_TEAM, {"key": self.c["team"]})
            teams = d["teams"]["nodes"]
            if not teams:
                sys.exit(f"No Linear team with key {self.c['team']!r}.")
            self._team = teams[0]
            self._team["all_labels"] = {l["name"]: l["id"] for l in d["issueLabels"]["nodes"]}
            self._team["all_labels"].update({l["name"]: l["id"] for l in teams[0]["labels"]["nodes"]})
        return self._team

    def state_id(self, name: str | None, type_: str | None = None) -> str:
        states = sorted(self.team["states"]["nodes"], key=lambda s: s["position"])
        for s in states:
            if (name and s["name"].lower() == name.lower()) or (not name and s["type"] == type_):
                return s["id"]
        want = name or type_
        sys.exit(f"Team {self.c['team']} has no workflow state {want!r}; set it in runway.json.")

    def label_id(self, name: str) -> str:
        lid = self.team["all_labels"].get(name)
        if not lid:
            sys.exit(f"Label {name!r} doesn't exist in Linear yet. Run `runway setup`.")
        return lid

    # -- the tracker interface Runway uses --

    def _filter(self) -> dict:
        f = {"team": {"key": {"eq": self.c["team"]}}}
        if self.c["project"]:
            f["project"] = {"name": {"eq": self.c["project"]}}
        return f

    def load(self) -> list[LinearTicket]:
        nodes, after = [], None
        while True:
            d = self.api.gql(Q_ISSUES, {"filter": self._filter(), "after": after})["issues"]
            nodes += d["nodes"]
            if not d["pageInfo"]["hasNextPage"]:
                break
            after = d["pageInfo"]["endCursor"]
        tickets = [LinearTicket(n, self) for n in sorted(nodes, key=lambda n: n["number"])]
        # Blockers outside the project still gate; add them as stubs Runway never runs.
        for t in tickets:
            if self.c["spec_label"] in t.labels and t.status != "resolved":
                self._log_once(f"skip  {t.id} is labelled {self.c['spec_label']}: a spec, never run "
                               "(its child issues are the tickets)")
        known = {t.num for t in tickets}
        for t in list(tickets):
            for r in t.node["inverseRelations"]["nodes"]:
                b = r["issue"]
                if r["type"] == "blocks" and b["identifier"] not in known:
                    known.add(b["identifier"])
                    tickets.append(LinearTicket({
                        "id": "", "identifier": b["identifier"], "number": b["number"], "title": b["title"],
                        "description": "", "url": "", "state": {"type": b["state"]["type"]},
                        "labels": {"nodes": []}, "comments": {"nodes": []}, "inverseRelations": {"nodes": []},
                    }, self))
        return tickets

    def _log_once(self, line: str) -> None:
        p = self.root / "_pm" / "runway.log"
        if p.exists() and line in p.read_text():
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}  {line}\n")
        print(line)

    def reload(self, t: LinearTicket) -> LinearTicket:
        return LinearTicket(self.api.gql(Q_ISSUE, {"id": t.node["id"]})["issue"], self)

    def sync(self) -> None:
        """Turn Joe's answers in Linear into ticket state before the tick decides anything."""
        for t in self.load():
            if t.status != "needs-human":
                continue
            replies = t.joe_replies()
            last = replies[-1].lower() if replies else ""
            if t.gate == "approved" or re.match(r"go\b", last):
                t.approve("Picked up Joe's go from Linear.")
                print(f"sync  {t.id} approved in Linear")
            elif re.match(r"drop\b", last):
                t.decline("drop (from Linear)")
                print(f"sync  {t.id} dropped in Linear")

    def setup(self) -> None:
        """Check the key, team and project, and create Runway's labels on the team."""
        team = self.team
        print(f"Team: {team['name']} ({team['key']})")
        if self.c["project"]:
            p = self.api.gql(Q_PROJECTS, {"name": self.c["project"]})["projects"]["nodes"]
            print(f"Project: {self.c['project']}" + ("" if p else "  (NOT FOUND: create it in Linear first)"))
        for name in (self.c["claimed_state"], self.c["done_state"]):
            self.state_id(name)
        print(f"States: {self.c['claimed_state']}, {self.c['done_state']} ok")
        colors = {"agent_label": "#4EA7FC", "human_label": "#F2994A", "approve_label": "#4CB782", "needs_human_label": "#EB5757",
                  "spec_label": "#8B8FA3"}
        for k, color in colors.items():
            name = self.c[k]
            if name in team["all_labels"]:
                print(f"Label {name}: exists")
                continue
            d = self.api.gql(M_LABEL, {"input": {"name": name, "teamId": team["id"], "color": color}})
            team["all_labels"][name] = d["issueLabelCreate"]["issueLabel"]["id"]
            print(f"Label {name}: created")
