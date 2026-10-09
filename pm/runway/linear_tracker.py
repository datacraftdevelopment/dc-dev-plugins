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

A ticket reads its latest 50 comments (ticket text, packet, Joe's replies). `claimed_by` pages back, 50 at a
time, only when a claimed ticket's 50 don't reach the start of the current claim cycle (the previous Runway
comment that isn't a claim stamp, or the start of the ticket).

Joe answers in Linear, from any device, and the next tick picks it up:
  - add the `go` label, or comment "go <any note>"  -> approved; the note reaches the agent
  - comment "drop"                                 -> moved to Canceled
  - remove `needs-human` from a failed run          -> retried on the next tick

API key: LINEAR_API_KEY, or the macOS keychain item `runway-linear`
(security add-generic-password -s runway-linear -a "$USER" -w).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ticket_protocol  # noqa: E402
import transient  # noqa: E402

API_URL = "https://api.linear.app/graphql"
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
  comments(last: 50) { pageInfo { hasPreviousPage startCursor } nodes { body createdAt } }
  inverseRelations(first: 10) { nodes { type issue { identifier number title state { type } } } }
"""

Q_ISSUES = """query($filter: IssueFilter, $after: String) {
  issues(filter: $filter, first: 50, after: $after) {
    nodes { %s }
    pageInfo { hasNextPage endCursor }
  }
}""" % ISSUE_FIELDS

Q_ISSUE = """query($id: String!) { issue(id: $id) { %s } }""" % ISSUE_FIELDS

Q_OLDER = """query($id: String!, $before: String!) { issue(id: $id) {
  comments(last: 50, before: $before) { pageInfo { hasPreviousPage startCursor } nodes { body createdAt } } } }"""

Q_COMMENTS = """query($id: String!) { issue(id: $id) { comments(last: 50) { nodes { body createdAt } } } }"""

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
M_CREATE = """mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier url } } }"""
Q_CREATED = """query($filter: IssueFilter) { issues(filter: $filter, first: 10, orderBy: createdAt) { nodes { identifier description createdAt } } }"""
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


class LinearTicket(ticket_protocol.Ticket):
    """An issue as Linear tells it. Facts and writes only: the rules are in ticket_protocol."""
    rules = ticket_protocol.LINEAR
    effort = "linear"

    def __init__(self, node: dict, tracker: "LinearTracker"):
        self.node = node
        comments = [self._fact(c) for c in node["comments"]["nodes"]]
        self._back = node["comments"].get("pageInfo") or {}  # where the next older page starts
        super().__init__(tracker, id=node["identifier"], num=node["identifier"], title=node["title"],
                         url=node.get("url"), body=node.get("description"),
                         labels={l["name"]: l["id"] for l in node["labels"]["nodes"]},
                         comments=comments, slug_head=node["identifier"].lower())

    @staticmethod
    def _fact(c: dict) -> dict:
        return {"body": c["body"], "createdAt": c["createdAt"], "trusted": True, "who": "unknown", "assoc": "NONE"}

    def _older_comments(self) -> list[dict]:
        """The next 50 comments back from what has been read (one call), oldest first; [] at the start of history."""
        if not self._back.get("hasPreviousPage"):
            return []
        d = self.tr.api.gql(Q_OLDER, {"id": self.node["id"], "before": self._back["startCursor"]})["issue"]["comments"]
        self._back = d["pageInfo"]
        return [self._fact(c) for c in d["nodes"]]

    # -- facts --

    @property
    def closed(self) -> bool:
        return self.node["state"]["type"] in ("completed", "canceled", "duplicate")

    @property
    def held(self) -> bool:
        return self.node["state"]["type"] == "started"

    @property
    def has_children(self) -> bool:
        return bool((self.node.get("children") or {}).get("nodes"))

    @property
    def blocked_by(self) -> list[str]:
        return [r["issue"]["identifier"] for r in self.node["inverseRelations"]["nodes"] if r["type"] == "blocks"]

    # -- writes --

    def _update(self, **inp) -> None:
        self.tr.api.gql(M_UPDATE, {"id": self.node["id"], "input": inp})

    def _post(self, full: str) -> None:
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

    def _claim(self) -> None:
        self._update(stateId=self.tr.state_id(self.tr.c["claimed_state"]))

    def _close(self, reason: str, full: str | None) -> None:
        if reason == "completed":
            self._update(stateId=self.tr.state_id(self.tr.c["done_state"]))
        else:
            self._update(stateId=self.tr.state_id(None, "canceled"))

    def _release(self, add=(), remove=()) -> None:
        # Back to an unstarted state, so clearing the label makes it ready again.
        self._update(stateId=self.tr.state_id(None, "unstarted"))
        self._labels(add=add, remove=remove)

    def _relabel(self, add=(), remove=()) -> None:
        self._labels(add=add, remove=remove)


class LinearTracker(ticket_protocol.Tracker):
    rules = ticket_protocol.LINEAR

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

    def _create(self, title: str, full: str, labels: list[str]) -> str:
        """Open a new issue in the team (and project) and return its identifier ("DAT-12"). `full` is the
        marked description. A create that timed out is looked up before it is repeated."""
        inp = {"teamId": self.team["id"], "title": title, "description": full,
               "labelIds": [self.label_id(n) for n in labels]}
        if self.c["project"]:
            p = self.api.gql(Q_PROJECTS, {"name": self.c["project"]})["projects"]["nodes"]
            if not p:
                sys.exit(f"No Linear project named {self.c['project']!r}.")
            inp["projectId"] = p[0]["id"]
        since = transient.since_mark()
        found: list[str] = []

        def landed() -> bool:
            f = {"team": {"key": {"eq": self.c["team"]}}, "title": {"eq": title}}
            for n in self.api.gql(Q_CREATED, {"filter": f})["issues"]["nodes"]:
                if transient.posted_since([n], full, since, key="description"):
                    found.append(n["identifier"])
                    return True
            return False
        d = self.api.gql(M_CREATE, {"input": inp}, landed=landed)
        return d["issueCreate"]["issue"]["identifier"] if d else found[0]

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
        self._log_spec_skips(tickets)
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

    def reload(self, t: LinearTicket) -> LinearTicket:
        return LinearTicket(self.api.gql(Q_ISSUE, {"id": t.node["id"]})["issue"], self)

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
