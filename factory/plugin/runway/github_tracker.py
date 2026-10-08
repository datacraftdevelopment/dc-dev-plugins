"""GitHub Issues adapter for Runway: reads the queue, and claims, finishes, parks and releases issues.

Runway's queue is the issues in one repo that carry Matt Pocock's triage labels, the same ones the
Linear adapter reads:

  ready-for-agent   AFK work. Runway runs it.                      (Gate: auto)
  ready-for-human   Needs Joe. Runway preps a packet first.         (Gate: human)
  go                Joe's approval on a ready-for-human issue.      (Gate: approved)
  needs-human       Parked: waiting on Joe. Runway never picks it.  (Status: needs-human)
  harness:<name>    Per-issue harness override.

Config: `"tracker": "github"`, and the repo from `"github": {"repo": "owner/name"}`, else from the
clone's `origin` remote. Optional `"github": {"gh": "<gh command>"}` (default `gh`).

Writes (through `gh issue edit / comment / close`; every comment starts with the 🛫 runway marker):

  claim    assign the gh user (`@me`), comment `Claimed-by: <machine> · Started on <branch>`
  resolve  close as completed, the note as the closing comment
  park     add `needs-human`, remove the assignee, comment why. Removing the label makes it ready again
  release  (pause --stop-now, signed out) remove the assignee and comment; the claim clears

The packet, approve and decline writes (ready-for-human issues) are not built yet.

Status: closed (completed or not planned) is resolved; open with `needs-human` is needs-human; open with
an assignee is claimed; anything else is ready.

Blockers: GitHub's native issue dependencies ("blocked by"); when an issue has none, a
`Blocked by: #n, #m` line at the top of its body. A blocker without Runway's labels still gates, as a
stub issue Runway never runs (like Linear's out-of-project blockers). Ids are `#n` (`owner/name#n` for
another repo).

Ticket text is the body plus comments from trusted authors only (author association OWNER, MEMBER or
COLLABORATOR). Other comments are left out and a one-line note says how many. Runway's own 🛫 marker
comments (packet, claimed_by) are read from trusted comments only, so a stranger can't forge a claim.

Cost of one `load()`, in `gh` calls: ceil(N / 50) + 1 at most, where N is the number of open and closed
issues carrying a Runway label (one GraphQL page of 50 issues each, labels, assignee count, the last 50
comments and native blockers included), plus one call only when some issue names a blocker in its body
that isn't already loaded. Nothing else is fetched. `reload()` is one call.

Auth: `gh` must be installed and signed in (`gh auth login`, or GH_TOKEN in the environment). Anything
else is one clear error naming both, not a traceback.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

MARK = "🛫 runway"  # every comment Runway writes starts with this, so Joe's are told apart
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
PAGE = 50
DEFAULTS = {
    "repo": "",
    "gh": "gh",
    "agent_label": "ready-for-agent",
    "human_label": "ready-for-human",
    "approve_label": "go",
    "needs_human_label": "needs-human",
}
AUTH_HELP = "GitHub CLI isn't ready. Install gh and run `gh auth login`, or set GH_TOKEN."
AUTH_RE = re.compile(r"gh auth login|GH_TOKEN|GITHUB_TOKEN|not logged in|authentication|bad credentials|HTTP 401",
                     re.I)

ISSUE_FIELDS = """
  number title body url state stateReason
  labels(first: 30) { nodes { name } }
  assignees(first: 10) { totalCount nodes { login } }
  comments(last: 50) { nodes { body createdAt authorAssociation } }
  blockedBy(first: 25) { nodes { number title state repository { nameWithOwner } } }
"""

Q_ISSUES = """query($owner: String!, $name: String!, $labels: [String!], $after: String) {
  repository(owner: $owner, name: $name) {
    issues(first: %d, after: $after, labels: $labels, states: [OPEN, CLOSED],
           orderBy: {field: CREATED_AT, direction: ASC}) {
      nodes { %s }
      pageInfo { hasNextPage endCursor }
    }
  }
}""" % (PAGE, ISSUE_FIELDS)

Q_ONE = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { issue(number: $number) { %s } }
}""" % ISSUE_FIELDS


def repo_from_origin(root: Path) -> str:
    r = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"], capture_output=True, text=True)
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", r.stdout.strip())
    if r.returncode != 0 or not m:
        sys.exit('No GitHub repo: set "github": {"repo": "owner/name"} in runway.json '
                 "(this clone has no github.com origin).")
    return f"{m.group(1)}/{m.group(2)}"


class GitHub:
    def __init__(self, cfg: dict):
        self.cmd = shlex.split(cfg["gh"])

    def run(self, args: list[str]) -> str:
        try:
            r = subprocess.run(self.cmd + args, capture_output=True, text=True)
        except FileNotFoundError:
            sys.exit(AUTH_HELP)
        if r.returncode != 0:
            if AUTH_RE.search(r.stderr + r.stdout):
                sys.exit(AUTH_HELP)
            raise RuntimeError(f"gh failed: {(r.stderr or r.stdout).strip()[:500]}")
        return r.stdout

    def graphql(self, query: str, **variables) -> dict:
        args = ["api", "graphql", "-f", f"query={query}"]
        for k, v in variables.items():
            if v is None:
                continue
            if isinstance(v, list):
                for item in v:
                    args += ["-f", f"{k}[]={item}"]
            elif isinstance(v, int):
                args += ["-F", f"{k}={v}"]
            else:
                args += ["-f", f"{k}={v}"]
        stdout = self.run(args)
        try:
            out = json.loads(stdout)
        except ValueError:
            raise RuntimeError(f"gh returned something that isn't JSON: {stdout[:200]}") from None
        if out.get("errors"):
            raise RuntimeError(f"GitHub API error: {out['errors']}")
        return out["data"]


def _blockers_from_body(body: str) -> list[int]:
    """`Blocked by: #n, #m` as the first non-blank line of the body."""
    for line in (body or "").splitlines():
        if line.strip():
            m = re.match(r"\s*blocked by:\s*(.+)$", line, re.I)
            return [int(n) for n in re.findall(r"#(\d+)", m.group(1))] if m else []
    return []


class GitHubTicket:
    def __init__(self, node: dict, tracker: "GitHubTracker"):
        self.node = node
        self.tr = tracker
        self.effort = "github"
        self.id = self.num = f"#{node['number']}"  # the engine matches blockers to tickets by num
        self.ref = node.get("url") or self.id
        slug = re.sub(r"[^a-z0-9]+", "-", node["title"].lower()).strip("-")[:40].rstrip("-")
        self.slug = f"gh-{node['number']}-{slug}"
        self.labels = {l["name"] for l in node["labels"]["nodes"]}
        every = sorted(node["comments"]["nodes"], key=lambda c: c["createdAt"])
        self.comments = [c for c in every if c.get("authorAssociation") in TRUSTED]
        self.untrusted = len(every) - len(self.comments)

    # -- read side --

    @property
    def title(self) -> str:
        return self.node["title"]

    @property
    def text(self) -> str:
        out = [f"# {self.title}", "", f"GitHub: {self.ref}", "", (self.node.get("body") or "").strip()]
        if self.comments or self.untrusted:
            out += ["", "## Comments"]
        for cm in self.comments:
            who = "runway" if cm["body"].startswith(MARK) else "Joe"
            out += ["", f"**{cm['createdAt'][:16]} · {who}**", "", cm["body"].strip()]
        if self.untrusted:
            out += ["", f"_{self.untrusted} comment(s) from other authors left out (not owner, member or collaborator)._"]
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
        if self.node["state"] == "CLOSED":
            return "resolved"  # completed or not planned
        if self.tr.c["needs_human_label"] in self.labels:
            return "needs-human"
        if self.node["assignees"]["totalCount"] > 0:
            return "claimed"
        return "ready"

    @property
    def gate(self) -> str:
        c = self.tr.c
        if c["human_label"] in self.labels:
            return "approved" if c["approve_label"] in self.labels else "human"
        if c["agent_label"] in self.labels:
            return "auto"
        return "none"

    @property
    def harness(self) -> str | None:
        """Per-issue harness override from a `harness:<name>` label, or None."""
        for name in self.labels:
            if name.lower().startswith("harness:"):
                return name.split(":", 1)[1].strip().lower() or None
        return None

    @property
    def blocked_by(self) -> list[str]:
        native = [self.tr.ref(b["repository"]["nameWithOwner"], b["number"])
                  for b in self.node["blockedBy"]["nodes"]]
        if native:
            return native
        return [self.tr.ref(self.tr.repo, n) for n in _blockers_from_body(self.node.get("body") or "")]

    @property
    def claimed_by(self) -> str | None:
        """The machine named in Runway's latest claim comment while the issue is claimed, else None."""
        if self.status != "claimed":
            return None
        for cm in reversed(self.comments):
            m = re.search(r"Claimed-by: (.+?)(?: · |$)", cm["body"], re.M) if cm["body"].startswith(MARK) else None
            if m:
                return m.group(1).strip()
        return None

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

    # -- write side --

    def _issue(self, verb: str, *args: str) -> None:
        self.tr.api.run(["issue", verb, self.num[1:], "--repo", self.tr.repo, *args])

    def _comment(self, body: str) -> None:
        self._issue("comment", "--body", f"{MARK} · {body.strip()}")

    def _unassign(self) -> list[str]:
        """Args that drop whoever holds the issue (the gh user when the node doesn't say)."""
        who = [a["login"] for a in self.node["assignees"].get("nodes", [])] or ["@me"]
        return ["--remove-assignee", ",".join(who)]

    def mark_claimed(self, branch: str, machine: str) -> None:
        self._issue("edit", "--add-assignee", "@me")
        self._comment(f"Claimed-by: {machine} · Started on `{branch}`.")

    def mark_resolved(self, note: str) -> None:
        self._issue("close", "--reason", "completed", "--comment", f"{MARK} · {note.strip()}")

    def mark_needs_human(self, why: str, detail: str) -> None:
        label = self.tr.c["needs_human_label"]
        self._issue("edit", "--add-label", label, *self._unassign())
        self._comment(f"Parked: {why}. Remove `{label}` to retry.\n\n{detail}")

    def mark_ready(self, note: str) -> None:
        self._issue("edit", *self._unassign())
        self._comment(note)

    def _unbuilt(self, *_a, **_k):
        raise NotImplementedError("The GitHub tracker can't write decision packets or answers yet.")

    post_packet = approve = decline = _unbuilt


class GitHubTracker:
    def __init__(self, root: Path, cfg: dict):
        self.root = root
        self.c = dict(DEFAULTS, **cfg.get("github", {}))
        self.repo = self.c["repo"] or repo_from_origin(root)
        if not re.fullmatch(r"[^/\s]+/[^/\s]+", self.repo):
            sys.exit(f'github.repo must look like "owner/name", got {self.repo!r}.')
        self.owner, self.name = self.repo.split("/")
        self.api = GitHub(self.c)

    def ref(self, repo: str, number: int) -> str:
        return f"#{number}" if repo.lower() == self.repo.lower() else f"{repo}#{number}"

    # -- the tracker interface Runway uses --

    def load(self) -> list[GitHubTicket]:
        labels = [self.c["agent_label"], self.c["human_label"]]
        nodes, after = [], None
        while True:
            d = self.api.graphql(Q_ISSUES, owner=self.owner, name=self.name, labels=labels,
                                 after=after)["repository"]["issues"]
            nodes += d["nodes"]
            if not d["pageInfo"]["hasNextPage"]:
                break
            after = d["pageInfo"]["endCursor"]
        tickets = [GitHubTicket(n, self) for n in sorted(nodes, key=lambda n: n["number"])]
        known = {t.id for t in tickets}
        stubs: dict[str, dict] = {}
        for t in tickets:
            for b in t.node["blockedBy"]["nodes"]:
                bid = self.ref(b["repository"]["nameWithOwner"], b["number"])
                if bid not in known and bid not in stubs:
                    stubs[bid] = {"number": b["number"], "title": b["title"], "state": b["state"]}
        # Body-line blockers aren't in the payload: one aliased call fetches them all.
        want = sorted({n for t in tickets if not t.node["blockedBy"]["nodes"]
                       for n in _blockers_from_body(t.node.get("body") or "")
                       if self.ref(self.repo, n) not in known | set(stubs)})
        if want:
            q = "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { %s } }" % " ".join(
                f"i{n}: issue(number: {n}) {{ number title state }}" for n in want)
            found = self.api.graphql(q, owner=self.owner, name=self.name)["repository"]
            for n in want:
                got = found.get(f"i{n}") or {"number": n, "title": f"#{n}", "state": "OPEN"}  # unknown still gates
                stubs[self.ref(self.repo, n)] = got
        for bid, b in stubs.items():
            tickets.append(GitHubTicket({
                "number": b["number"], "title": b["title"], "body": "", "url": "", "state": b["state"],
                "stateReason": None, "labels": {"nodes": []}, "assignees": {"totalCount": 0},
                "comments": {"nodes": []}, "blockedBy": {"nodes": []},
            }, self))
            tickets[-1].id = tickets[-1].num = bid
        return tickets

    def reload(self, t: GitHubTicket) -> GitHubTicket:
        d = self.api.graphql(Q_ONE, owner=self.owner, name=self.name, number=int(t.num.rsplit('#', 1)[1]))
        return GitHubTicket(d["repository"]["issue"], self)

    def sync(self) -> None:
        """Nothing to pick up yet: answering from GitHub arrives with the write side."""
